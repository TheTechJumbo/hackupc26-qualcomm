"""
Plant Health Sensor Classifier — atmospheric suitability for vegetation growth.

Uses only atmospheric features (light intensity, temperature, humidity) to classify
whether the local environment is suitable for plant growth. Handles the longitudinal
dataset by computing 24-hour rolling means (window=4 × 6-hour readings) per plant
during training. At inference on-device, no Plant_ID is needed — the Arduino Uno Q
maintains a circular buffer of the last 4 sensor readings and computes means locally.

Label encoding (stored as stress_level):
  Healthy          -> 0  -> can_grow = 1 (true)
  Moderate Stress  -> 1  -> can_grow = 1 (true)
  High Stress      -> 2  -> can_grow = 0 (false)

Train/test split strategy:
  Plant-aware split (last 20% of Plant_IDs held out) prevents temporal leakage
  and simulates deployment at new atmospheric locations with no prior history.

Edge Impulse compatibility:
  - sklearn RandomForest -> skl2onnx -> ONNX opset 12
  - 6 float32 inputs, 1 binary output (can_grow: 0 or 1)
  - Model size well within Arduino Uno Q 4 GB RAM budget

Output: models/tabular_rf_model.pkl
"""

import logging
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.yaml"

STRESS_MAP = {"Healthy": 0, "Moderate Stress": 1, "High Stress": 2}


def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "sensor_processing.log"),
        ],
    )
    return logging.getLogger("sensor")


def load_and_validate(csv_path: Path, sc: dict, log: logging.Logger) -> pd.DataFrame:
    log.info("Loading dataset: %s", csv_path)
    df = pd.read_csv(csv_path, parse_dates=[sc["timestamp_col"]])
    log.info("Rows: %d | Columns: %s", len(df), list(df.columns))

    required = [sc["timestamp_col"], sc["plant_id_col"], sc["target"]] + sc["raw_features"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        log.error("Missing columns: %s", missing)
        log.error("Available columns: %s", list(df.columns))
        sys.exit(1)

    before = len(df)
    df = df.dropna(subset=required)
    dropped = before - len(df)
    if dropped:
        log.warning("Dropped %d rows with NaN in required columns", dropped)

    # Encode stress levels and derive binary target
    df["stress_level"] = df[sc["target"]].map(STRESS_MAP)
    unmapped = df["stress_level"].isna().sum()
    if unmapped:
        bad = df.loc[df["stress_level"].isna(), sc["target"]].unique()
        log.error("Unknown target values (not in STRESS_MAP): %s", bad)
        sys.exit(1)

    threshold = sc["healthy_threshold"]
    df["can_grow"] = (df["stress_level"] <= threshold).astype(np.int32)

    log.info("Stress level distribution (0=Healthy, 1=Moderate Stress, 2=High Stress):")
    for lvl, count in df["stress_level"].value_counts().sort_index().items():
        label = {0: "Healthy", 1: "Moderate Stress", 2: "High Stress"}[lvl]
        log.info("  %d (%s): %d rows", lvl, label, count)

    pos = int(df["can_grow"].sum())
    neg = len(df) - pos
    log.info(
        "Binary target — can_grow=1 (healthy/low-stress): %d | can_grow=0 (high-stress): %d",
        pos, neg,
    )

    return df


def add_rolling_features(df: pd.DataFrame, sc: dict, log: logging.Logger) -> pd.DataFrame:
    """
    Compute per-plant rolling means over the previous WINDOW readings for each
    raw atmospheric feature. min_periods=1 ensures valid output from the first
    reading (mean of available samples, not NaN).

    At inference there is no Plant_ID — the device keeps a FIFO buffer of the
    last WINDOW sensor readings and computes the mean before calling the model.
    """
    window = sc["rolling_window"]
    df = df.sort_values([sc["plant_id_col"], sc["timestamp_col"]]).copy()

    for col in sc["raw_features"]:
        rolled_col = f"{col}_24h_mean"
        df[rolled_col] = (
            df.groupby(sc["plant_id_col"])[col]
            .transform(lambda x: x.rolling(window, min_periods=1).mean())
        )

    log.info(
        "Added rolling features: window=%d readings = %d hours at 6h sampling",
        window, window * 6,
    )
    return df


def plant_aware_split(df: pd.DataFrame, sc: dict, log: logging.Logger):
    """
    Hold out the last ceil(test_size * n_plants) Plant_IDs as the test set.
    Simulates deployment in a new atmospheric location (no prior plant history).
    Prevents temporal leakage that a random row split would introduce.
    """
    plants = sorted(df[sc["plant_id_col"]].unique())
    n_test = max(1, round(len(plants) * sc["test_size"]))
    test_plants = plants[-n_test:]
    train_plants = plants[:-n_test]

    train_df = df[df[sc["plant_id_col"]].isin(train_plants)].copy()
    test_df = df[df[sc["plant_id_col"]].isin(test_plants)].copy()

    log.info(
        "Train plants: %s (%d rows) | Test plants: %s (%d rows)",
        train_plants, len(train_df), test_plants, len(test_df),
    )
    return train_df, test_df


def evaluate(
    rf: RandomForestClassifier,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_cols: list,
    log: logging.Logger,
) -> float:
    y_pred = rf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    log.info("Test accuracy: %.4f (%.1f%%)", acc, acc * 100)
    log.info(
        "Classification report:\n%s",
        classification_report(
            y_test, y_pred,
            target_names=["High Stress / false (0)", "Healthy or Low Stress / true (1)"],
            zero_division=0,
        ),
    )

    cm = confusion_matrix(y_test, y_pred)
    log.info("Confusion matrix (rows=actual, cols=predicted):\n%s", cm)

    importances = sorted(zip(feature_cols, rf.feature_importances_), key=lambda x: -x[1])
    log.info("Feature importances:")
    for col, imp in importances:
        log.info("  %-35s %.4f", col, imp)

    unique_preds = np.unique(y_pred)
    if len(unique_preds) == 1:
        log.warning(
            "RELIABILITY WARNING: model predicts only class %s — "
            "check class imbalance or whether features are informative for test plants.",
            unique_preds[0],
        )

    return acc


def train(sc: dict, log: logging.Logger) -> RandomForestClassifier:
    csv_path = (ROOT / sc["data"]).resolve()
    if not csv_path.exists():
        log.error("CSV not found: %s", csv_path)
        sys.exit(1)

    df = load_and_validate(csv_path, sc, log)
    df = add_rolling_features(df, sc, log)

    feature_cols = sc["features"]
    log.info("Feature vector (%d features): %s", len(feature_cols), feature_cols)

    train_df, test_df = plant_aware_split(df, sc, log)

    X_train = train_df[feature_cols].values.astype("float32")
    y_train = train_df["can_grow"].values
    X_test = test_df[feature_cols].values.astype("float32")
    y_test = test_df["can_grow"].values

    log.info(
        "Train class balance — 0: %d, 1: %d",
        int((y_train == 0).sum()), int((y_train == 1).sum()),
    )
    log.info(
        "Test  class balance — 0: %d, 1: %d",
        int((y_test == 0).sum()), int((y_test == 1).sum()),
    )

    rf = RandomForestClassifier(
        n_estimators=sc["n_estimators"],
        max_depth=sc["max_depth"],
        n_jobs=sc["n_jobs"],
        random_state=sc["random_state"],
        class_weight="balanced",
    )

    log.info(
        "Training RandomForest — n_estimators=%d, max_depth=%d, class_weight=balanced",
        sc["n_estimators"], sc["max_depth"],
    )
    t0 = time.time()
    rf.fit(X_train, y_train)
    log.info("Training complete in %.2f s", time.time() - t0)

    acc = evaluate(rf, X_test, y_test, feature_cols, log)

    if acc < 0.60:
        log.warning(
            "RELIABILITY WARNING: test accuracy %.1f%% is below 60%%. "
            "Consider adding more features or adjusting the healthy_threshold.",
            acc * 100,
        )

    return rf


def main() -> None:
    with open(CONFIG_PATH) as f:
        cfg_full = yaml.safe_load(f)

    log = setup_logging(ROOT / "logs")
    log.info("=== Plant Health Atmospheric Classifier — Training ===")

    sc = cfg_full["sensor_model"]
    rf = train(sc, log)

    out_path = (ROOT / sc["output"]).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(rf, out_path)
    log.info("Model saved: %s", out_path)
    log.info("=== sensor_processing.py complete ===")


if __name__ == "__main__":
    main()
