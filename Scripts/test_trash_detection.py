"""
Trash detection inference test.
Usage: python Scripts/test_trash_detection.py <image1.jpg> [image2.jpg ...]

Prints one JSON object per image matching the Arduino sensor output format:
  {"image": "...", "trash_detected": bool, "trash_class": str|null,
   "confidence": float|null, "boxes": [[x1,y1,x2,y2], ...]}
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.yaml"


def infer(model, image_path: Path) -> dict:
    results = model.predict(str(image_path), verbose=False)
    r = results[0]

    if r.boxes is None or len(r.boxes) == 0:
        return {
            "image": image_path.name,
            "trash_detected": False,
            "trash_class": None,
            "confidence": None,
            "boxes": [],
        }

    best_idx = int(r.boxes.conf.argmax())
    return {
        "image": image_path.name,
        "trash_detected": True,
        "trash_class": model.names[int(r.boxes.cls[best_idx].item())],
        "confidence": round(float(r.boxes.conf[best_idx].item()), 4),
        "boxes": [list(map(lambda v: round(v, 1), box)) for box in r.boxes.xyxy.tolist()],
    }


def main() -> None:
    from ultralytics import YOLO  # noqa: PLC0415

    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    weights = ROOT / cfg["project"]["output_dir"] / "trash_model_weights.pt"
    if not weights.exists():
        print(f"[ERROR] Weights not found: {weights}", file=sys.stderr)
        print("Run Factory.py (or trash_model.py) first to train the model.", file=sys.stderr)
        sys.exit(1)

    images = [Path(p) for p in sys.argv[1:]]
    if not images:
        print("Usage: python Scripts/test_trash_detection.py <image> [...]", file=sys.stderr)
        sys.exit(1)

    print(f"Model : {weights}")
    model = YOLO(str(weights))

    for img in images:
        if not img.exists():
            print(f"[WARN] Not found: {img}", file=sys.stderr)
            continue
        result = infer(model, img)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
