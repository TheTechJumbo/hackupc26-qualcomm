# NVIDIA CUDA 11.8 base — matches PyTorch 2.x GPU requirements
# RTX 3060 (Ampere) is fully supported on CUDA 11.8+
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.11 1

WORKDIR /app

# Install Python deps first (cached layer — only rebuilds if requirements change)
COPY requirements.txt .

# Pin PyTorch to the cu118 wheel before the rest of requirements.
# Without an explicit index URL, pip resolves torch>=2.1.0 to torch-2.11.0+cu130,
# which requires CUDA driver API >= 13000. The host driver only supports up to
# CUDA 12.x, so PyTorch falls back to CPU. cu118 is the highest CUDA version
# confirmed to work on this machine.
RUN pip install --no-cache-dir \
    "torch>=2.2.0,<2.3.0" \
    "torchvision>=0.17.0,<0.18.0" \
    --index-url https://download.pytorch.org/whl/cu118

RUN pip install -r requirements.txt

# Copy project files
COPY . .

# Ensure output directories exist
RUN mkdir -p models logs vision_runs

# Default: run the full pipeline
CMD ["python", "Factory.py"]
