"""
Trash Detection Model — YOLOv8n-seg trained on TACO-1.

3,375 training images, 59 trash categories, YOLOv8 segmentation format.
Fine-tuned from COCO pretrained yolov8n-seg.pt weights.

Output: vision_runs/trash_model/weights/best.pt
        models/trash_model_weights.pt  (copy for ONNX conversion)
"""

import logging
import shutil
import sys
import time
from pathlib import Path

import torch
import yaml

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
            logging.FileHandler(log_dir / "trash_model.log"),
        ],
    )
    return logging.getLogger("trash")


def resolve_device(cfg_device: str) -> str:
    if cfg_device == "auto":
        return "0" if torch.cuda.is_available() else "cpu"
    return cfg_device


def log_gpu_info(log: logging.Logger) -> None:
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
        log.info("GPU detected: %s  (%.1f GB VRAM)", name, vram)
    else:
        log.warning("No CUDA GPU detected — training on CPU (will be slow)")


def log_dataset_info(data_yaml: Path, log: logging.Logger) -> None:
    with open(data_yaml) as f:
        meta = yaml.safe_load(f)
    nc = meta.get("nc", "?")
    names = meta.get("names", [])
    log.info("Dataset: %s", data_yaml)
    log.info("Classes (%s): %s ... %s", nc, names[:5], names[-3:] if len(names) > 5 else "")

    for split in ("train", "val", "test"):
        split_path = data_yaml.parent / meta.get(split, f"{split}/images")
        count = len(list(split_path.glob("*.jpg"))) + len(list(split_path.glob("*.png")))
        log.info("  %-6s images: %d", split, count)


def run_inference_sample(model, data_yaml: Path, log: logging.Logger) -> None:
    """Quick sanity-check against a single validation image."""
    val_dir = data_yaml.parent / "valid" / "images"
    images = list(val_dir.glob("*.jpg"))[:1] + list(val_dir.glob("*.png"))[:1]
    if not images:
        log.info("No validation images found for sanity-check")
        return

    sample = images[0]
    log.info("Inference sanity-check on: %s", sample.name)
    results = model.predict(str(sample), verbose=False)
    r = results[0]
    n_det = len(r.boxes) if r.boxes is not None else 0
    if n_det > 0:
        classes = [model.names[int(c)] for c in r.boxes.cls.tolist()]
        log.info("Detections: %d | classes: %s", n_det, classes)
    else:
        log.info("No detections on sample (normal for early/unseen images)")


def main() -> None:
    from ultralytics import YOLO  # noqa: PLC0415

    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    log = setup_logging(ROOT / "logs")
    log.info("=== Trash Detection Model Training ===")

    log_gpu_info(log)
    device = resolve_device(cfg["gpu"]["device"])
    half = cfg["gpu"]["half"] and device != "cpu"
    log.info("Device: %s | FP16: %s", device, half)

    tc = cfg["trash_model"]
    data_yaml = (ROOT / tc["data"]).resolve()

    if not data_yaml.exists():
        log.error("data.yaml not found: %s", data_yaml)
        sys.exit(1)

    log_dataset_info(data_yaml, log)
    log.info(
        "Hyperparameters — epochs: %d | imgsz: %d | batch: %d | workers: %d",
        tc["epochs"], tc["imgsz"], tc["batch"], tc["workers"],
    )

    log.info("Loading base model: %s", tc["base_model"])
    model = YOLO(tc["base_model"])

    log.info("Training started...")
    t0 = time.time()

    results = model.train(
        data=str(data_yaml),
        epochs=tc["epochs"],
        imgsz=tc["imgsz"],
        batch=tc["batch"],
        workers=tc["workers"],
        device=device,
        half=half,
        project=str(ROOT / tc["project"]),
        name=tc["name"],
        exist_ok=True,
    )

    elapsed = time.time() - t0
    log.info("Training finished in %.1f s (%.1f min)", elapsed, elapsed / 60)

    best_weights = ROOT / tc["project"] / tc["name"] / "weights" / "best.pt"
    if not best_weights.exists():
        log.error("Expected weights not found: %s — training may have failed", best_weights)
        sys.exit(1)

    log.info("Best weights: %s", best_weights)

    metrics = results.results_dict
    map50 = metrics.get("metrics/mAP50(M)", metrics.get("metrics/mAP50(B)", "n/a"))
    map50_95 = metrics.get("metrics/mAP50-95(M)", metrics.get("metrics/mAP50-95(B)", "n/a"))
    log.info("Final metrics — mAP50: %s | mAP50-95: %s", map50, map50_95)

    # Load trained model and run inference check
    trained_model = YOLO(str(best_weights))
    run_inference_sample(trained_model, data_yaml, log)

    # Copy to models/ for ONNX conversion step
    models_dir = ROOT / cfg["project"]["output_dir"]
    models_dir.mkdir(exist_ok=True)
    dst = models_dir / "trash_model_weights.pt"
    shutil.copy2(best_weights, dst)
    log.info("Weights copied to: %s (for ONNX conversion)", dst)

    log.info("=== trash_model.py complete ===")


if __name__ == "__main__":
    main()
