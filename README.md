# hackupc26-qualcomm

Multi-modal edge AI pipeline for urban environmental monitoring. Trains three models (plant health sensor classification, building facade detection, trash detection) and exports them to ONNX opset 12 for Qualcomm NPU deployment via Edge Impulse.

## Models

| Model | Type | Target |
|-------|------|--------|
| Plant Health | RandomForest (sklearn → ONNX) | Atmospheric sensor data (light, temp, humidity) |
| Building Facade | YOLOv11n segmentation | Urban landcover imagery |
| Trash Detection | YOLOv11n segmentation | TACO dataset |

## Setup & Running

### 1. Check your CUDA version

```bash
python test_torch_cuda.py
```

Note the CUDA version printed. If it differs from `11.8`, update the base image and PyTorch wheel in `Dockerfile` to match:

```dockerfile
# Example: swap cu118 → cu121 for CUDA 12.1
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04
RUN pip install torch==2.2.0+cu121 --index-url https://download.pytorch.org/whl/cu121
```

### 2. Download datasets

Pull datasets from Hugging Face and place them under a `Data/` directory in the project root:

```
https://huggingface.co/datasets/KishPrak/EcoDragonData
```

Expected layout:
```
Data/
├── sensor/          # Plant health atmospheric readings
├── urban_landcover/ # Building facade imagery
└── taco/            # Trash detection imagery
```

Update paths in `config.yaml` if your layout differs.

### 3. Build and run

```bash
docker compose up --build
```

This runs `Factory.py`, which trains all models and exports them to `models/` as ONNX files ready for Edge Impulse ingestion.

## Output

Trained artifacts land in:
- `models/` — `.onnx` and `.pkl` files for Edge Impulse upload
- `vision_runs/` — YOLO training checkpoints
- `logs/factory.log` — pipeline run log

## Requirements

- Docker with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- GPU with ≥ 8 GB VRAM recommended (tested on RTX 3060 12 GB)
