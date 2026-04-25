"""
Agricultural Sensor Data — Random Forest classifier.

Reads the CSV, injects photoresistor noise into Solar_Radiation,
trains a RandomForest on the features listed in config.yaml, and saves the model.

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
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.yaml"


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
    df = pd.read_csv(csv_path)
    log.info("Rows: %d | Columns: %s", len(df), list(df.columns))

    # Solar_Radiation_Noisy is derived at runtime; every other feature must exist in the CSV.
    derived = {"Solar_Radiation_Noisy"}
    csv_features = [f for f in sc["features"] if f not in derived]
    required = list(dict.fromkeys([sc["noise_source_col"], sc["target"]] + csv_features))

    missing = [c for c in required if c not in df.columns]
    if missing:
        log.error("Missing columns: %s", missing)
        log.error("Available columns: %s", list(df.columns))
        sys.exit(1)

    before = len(df)
    df = df.dropna(subset=required)
    dropped = before - len(df)
    if dropped:
        log.warning("Dropped %d rows with NaN values in key columns", dropped)

    log.info("Clean rows for training: %d", len(df))
    return df


def inject_noise(df: pd.DataFrame, sc: dict, log: logging.Logger) -> pd.DataFrame:
    """Scale Solar_Radiation to [0,1] then add Gaussian noise to simulate cheap photoresistor."""
    scaler = MinMaxScaler()
    src_col = sc["noise_source_col"]
    df = df.copy()
    df["Solar_Radiation_Scaled"] = scaler.fit_transform(df[[src_col]])

    np.random.seed(sc["noise_seed"])
    noise = np.random.normal(0, sc["noise_std"], len(df))
    df["Solar_Radiation_Noisy"] = np.clip(df["Solar_Radiation_Scaled"] + noise, 0, 1)

    log.info(
        "Noise injection — source: %s | std: %.3f | noisy range: [%.4f, %.4f]",
        src_col, sc["noise_std"],
        df["Solar_Radiation_Noisy"].min(),
        df["Solar_Radiation_Noisy"].max(),
    )
    return df


def train(sc: dict, log: logging.Logger):
    csv_path = (ROOT / sc["data"]).resolve()
    if not csv_path.exists():
        log.error("CSV not found: %s", csv_path)
        sys.exit(1)

    df = load_and_validate(csv_path, sc, log)
    df = inject_noise(df, sc, log)

    features = sc["features"]
    target = sc["target"]
    log.info("Features: %s | Target: %s", features, target)

    X = df[features].values.astype("float32")
    y = df[target].values

    log.info("Class distribution:\n%s", pd.Series(y).value_counts().to_string())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=sc["test_size"],
        random_state=sc["random_state"],
        stratify=y,
    )
    log.info("Split — train: %d | test: %d", len(X_train), len(X_test))

    rf = RandomForestClassifier(
        n_estimators=sc["n_estimators"],
        max_depth=sc["max_depth"],
        n_jobs=sc["n_jobs"],
        random_state=sc["random_state"],
    )

    log.info(
        "Training RandomForest — n_estimators: %d | max_depth: %d | n_jobs: %d",
        sc["n_estimators"], sc["max_depth"], sc["n_jobs"],
    )
    t0 = time.time()
    rf.fit(X_train, y_train)
    log.info("Training done in %.2f s", time.time() - t0)

    y_pred = rf.predict(X_test)
    accuracy = (y_pred == y_test).mean()
    log.info("Test accuracy: %.4f (%.1f%%)", accuracy, accuracy * 100)
    log.info(
        "Classification report:\n%s",
        classification_report(y_test, y_pred, zero_division=0),
    )

    importances = dict(zip(features, rf.feature_importances_))
    log.info("Feature importances: %s", {k: f"{v:.4f}" for k, v in importances.items()})

    return rf


def main() -> None:
    with open(CONFIG_PATH) as f:
        cfg_full = yaml.safe_load(f)

    log = setup_logging(ROOT / "logs")
    log.info("=== Agricultural Sensor Model Training ===")

    sc = cfg_full["sensor_model"]
    rf = train(sc, log)

    out_path = (ROOT / sc["output"]).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(rf, out_path)
    log.info("Model saved: %s", out_path)
    log.info("=== sensor_processing.py complete ===")


if __name__ == "__main__":
    main()
