"""
ONNX Conversion — exports both models to ONNX for Edge Impulse ingestion.

Part A: RandomForest (sklearn)   → models/tabular_rf_model.onnx  (disabled)
Part B: YOLO11 roadside model    → models/vision_roadside_model.onnx
Part C: YOLO11 trash model       → models/trash_model.onnx

Upload Part B and Part C to Edge Impulse → Object Detection (YOLOv11).
Edge Impulse accepts ONNX at opset 12; all exports use that version.
"""

import logging
import sys
from pathlib import Path

import joblib
import yaml
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

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
            logging.FileHandler(log_dir / "onnx_conversion.log"),
        ],
    )
    return logging.getLogger("onnx")


def convert_sensor_model(sc_cfg: dict, onnx_cfg: dict, out_dir: Path, log: logging.Logger) -> None:
    pkl_path = (ROOT / sc_cfg["output"]).resolve()
    if not pkl_path.exists():
        log.error("RF model not found: %s — run sensor_processing.py first", pkl_path)
        sys.exit(1)

    log.info("Loading RandomForest from: %s", pkl_path)
    rf = joblib.load(pkl_path)

    n_features = len(sc_cfg["features"])
    initial_type = [("float_input", FloatTensorType([None, n_features]))]
    log.info("Converting to ONNX (opset %d) — %d input features", onnx_cfg["opset"], n_features)

    onx = convert_sklearn(rf, initial_types=initial_type, target_opset=onnx_cfg["opset"])

    out_path = out_dir / "tabular_rf_model.onnx"
    with open(out_path, "wb") as f:
        f.write(onx.SerializeToString())

    log.info("Tabular ONNX saved: %s", out_path)


def convert_yolo_model(weights_path: Path, out_path: Path, onnx_cfg: dict, log: logging.Logger) -> None:
    from ultralytics import YOLO  # noqa: PLC0415

    if not weights_path.exists():
        log.error("Weights not found: %s", weights_path)
        return

    log.info("Loading YOLO weights: %s", weights_path)
    model = YOLO(str(weights_path))

    log.info("Exporting to ONNX (opset %d, simplify=%s)...", onnx_cfg["opset"], onnx_cfg["simplify"])
    exported = model.export(
        format="onnx",
        opset=onnx_cfg["opset"],
        simplify=onnx_cfg["simplify"],
        imgsz=640,
    )

    exported_path = Path(exported) if exported else None
    if exported_path and exported_path.exists():
        exported_path.rename(out_path)
        log.info("ONNX saved: %s", out_path)
    else:
        log.warning("Export returned unexpected path: %s", exported)


def main() -> None:
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    log = setup_logging(ROOT / "logs")
    log.info("=== ONNX Model Conversion ===")

    onnx_cfg = cfg["onnx"]
    out_dir = (ROOT / onnx_cfg["output_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("Output directory: %s", out_dir)

    # --- Part A: Tabular RandomForest ---
    log.info("--- Part A: Tabular RF → ONNX ---")
    #convert_sensor_model(cfg["sensor_model"], onnx_cfg, out_dir, log)

    # --- Part B: Roadside vision model ---
    log.info("--- Part B: Roadside Vision Model → ONNX ---")
    vc = cfg["vision_model"]
    roadside_weights = ROOT / vc["project"] / vc["name"] / "weights" / "best.pt"
    convert_yolo_model(roadside_weights, out_dir / "vision_roadside_model.onnx", onnx_cfg, log)

    # --- Part C: Trash model ---
    log.info("--- Part C: Trash Model → ONNX ---")
    tc = cfg["trash_model"]
    #trash_weights = ROOT / tc["project"] / tc["name"] / "weights" / "best.pt"
    #convert_yolo_model(trash_weights, out_dir / "trash_model.onnx", onnx_cfg, log)

    log.info("=== onnx_conversion.py complete ===")
    log.info("Edge Impulse models ready in: %s", out_dir)


if __name__ == "__main__":
    main()
