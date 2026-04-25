"""
Factory — pipeline orchestrator.

Runs the full training + conversion pipeline in order:
  1. sensor_processing.py   (tabular RF model)
  2. land_use.py             (building facade YOLOv8)
  3. trash_model.py          (trash detection YOLOv8)
  4. onnx_conversion.py      (export all models to ONNX for Edge Impulse)

Usage:
    python Factory.py               # run all stages
    python Factory.py --skip-vision # skip the long YOLOv8 training stages
"""

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
SCRIPTS = ROOT / "Scripts"

STAGES = [
    #("sensor",  SCRIPTS / "sensor_processing.py"),
    ("vision",  SCRIPTS / "land_use.py"),
    ("trash",   SCRIPTS / "trash_model.py"),
    ("convert", SCRIPTS / "onnx_conversion.py"),
]


def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "factory.log"),
        ],
    )
    return logging.getLogger("factory")


def run_stage(name: str, script: Path, log: logging.Logger) -> bool:
    log.info("--- Stage: %-10s (%s) ---", name.upper(), script.name)
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
    )
    elapsed = time.time() - t0

    if result.returncode == 0:
        log.info("[OK] Stage %s completed in %.1f s", name, elapsed)
        return True
    else:
        log.error("[FAIL] Stage %s FAILED (exit code %d) after %.1f s", name, result.returncode, elapsed)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="HackUPC Qualcomm training pipeline")
    parser.add_argument("--skip-vision", action="store_true", help="Skip land_use.py (long GPU training)")
    parser.add_argument("--skip-trash",  action="store_true", help="Skip trash_model.py")
    parser.add_argument("--only",        help="Run only this stage (sensor|vision|trash|convert)")
    args = parser.parse_args()

    log = setup_logging(ROOT / "logs")
    log.info("==========================================")
    log.info("   HackUPC Qualcomm -- Training Pipeline  ")
    log.info("==========================================")

    results: dict[str, bool] = {}
    t_start = time.time()

    for name, script in STAGES:
        if args.only and name != args.only:
            log.info("Skipping stage %s (--only %s)", name, args.only)
            continue
        if args.skip_vision and name == "vision":
            log.info("Skipping stage vision (--skip-vision)")
            continue
        if args.skip_trash and name == "trash":
            log.info("Skipping stage trash (--skip-trash)")
            continue

        ok = run_stage(name, script, log)
        results[name] = ok

        if not ok:
            log.error("Pipeline aborted at stage: %s", name)
            sys.exit(1)

    total = time.time() - t_start
    log.info("------------------------------------------")
    log.info("Pipeline complete in %.1f s (%.1f min)", total, total / 60)
    for name, ok in results.items():
        log.info("  %-10s  %s", name, "[OK]" if ok else "[FAILED]")

    models_dir = ROOT / "models"
    if models_dir.exists():
        onnx_files = list(models_dir.glob("*.onnx"))
        log.info("Edge Impulse-ready ONNX files in %s:", models_dir)
        for f in onnx_files:
            size_mb = f.stat().st_size / 1024 ** 2
            log.info("  %s  (%.1f MB)", f.name, size_mb)


if __name__ == "__main__":
    main()
