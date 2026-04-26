"""
Building Facade Segmentation — YOLOv8n-seg training.
Outputs: vision_runs/roadside_model/weights/best.pt
         models/vision_roadside_weights.pt  (copy for Edge Impulse handoff)
"""

import argparse
import json
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
            logging.FileHandler(log_dir / "land_use.log"),
        ],
    )
    return logging.getLogger("land_use")


def resolve_device(cfg_device: str) -> str:
    if cfg_device == "auto":
        return "0" if torch.cuda.is_available() else "cpu"
    return cfg_device


def infer(image_path: Path, model) -> dict:
    """Return whether the scene is suitable for planting (no building facade detected)."""
    results = model.predict(str(image_path), verbose=False)
    r = results[0]
    has_facade = r.boxes is not None and len(r.boxes) > 0
    confidence = round(float(r.boxes.conf.max().item()), 4) if has_facade else None
    return {"suitable_for_planting": not has_facade, "confidence": confidence}


def log_gpu_info(log: logging.Logger) -> None:
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
        log.info("GPU detected: %s  (%.1f GB VRAM)", name, vram)
    else:
        log.warning("No CUDA GPU detected — training on CPU (will be slow)")


def main() -> None:
    from ultralytics import YOLO  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Building facade segmentation — train or infer")
    parser.add_argument("--infer", metavar="IMAGE", help="Run inference on IMAGE and print JSON result")
    args = parser.parse_args()

    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    if args.infer:
        weights = ROOT / cfg["project"]["output_dir"] / "vision_roadside_weights.pt"
        if not weights.exists():
            print(f"[ERROR] Weights not found: {weights}", file=sys.stderr)
            sys.exit(1)
        model = YOLO(str(weights))
        print(json.dumps(infer(Path(args.infer), model)))
        return

    log = setup_logging(ROOT / "logs")
    log.info("=== Building Facade Segmentation Training ===")
    log.info("Config loaded from: %s", CONFIG_PATH)

    log_gpu_info(log)
    device = resolve_device(cfg["gpu"]["device"])
    half = cfg["gpu"]["half"] and device != "cpu"
    log.info("Device: %s | FP16: %s", device, half)

    vc = cfg["vision_model"]
    data_yaml = (ROOT / vc["data"]).resolve()

    if not data_yaml.exists():
        log.error("data.yaml not found: %s", data_yaml)
        sys.exit(1)

    log.info("Dataset: %s", data_yaml)
    log.info(
        "Hyperparameters — epochs: %d | imgsz: %d | batch: %d | workers: %d",
        vc["epochs"], vc["imgsz"], vc["batch"], vc["workers"],
    )

    log.info("Loading base model: %s", vc["base_model"])
    model = YOLO(vc["base_model"])

    log.info("Training started...")
    t0 = time.time()

    results = model.train(
        data=str(data_yaml),
        epochs=vc["epochs"],
        imgsz=vc["imgsz"],
        batch=vc["batch"],
        workers=vc["workers"],
        device=device,
        half=half,
        project=str(ROOT / vc["project"]),
        name=vc["name"],
        exist_ok=True,
    )

    elapsed = time.time() - t0
    log.info("Training finished in %.1f s (%.1f min)", elapsed, elapsed / 60)

    best_weights = ROOT / vc["project"] / vc["name"] / "weights" / "best.pt"
    if not best_weights.exists():
        log.error("Expected weights not found: %s — training may have failed", best_weights)
        sys.exit(1)

    log.info("Best weights: %s", best_weights)

    metrics = results.results_dict
    map50 = metrics.get("metrics/mAP50(M)", metrics.get("metrics/mAP50(B)", "n/a"))
    map50_95 = metrics.get("metrics/mAP50-95(M)", metrics.get("metrics/mAP50-95(B)", "n/a"))
    log.info("Final metrics — mAP50: %s | mAP50-95: %s", map50, map50_95)

    models_dir = ROOT / cfg["project"]["output_dir"]
    models_dir.mkdir(exist_ok=True)
    dst = models_dir / "vision_roadside_weights.pt"
    shutil.copy2(best_weights, dst)
    log.info("Weights copied to: %s (for ONNX conversion)", dst)
    log.info("=== land_use.py complete ===")


if __name__ == "__main__":
    main()
