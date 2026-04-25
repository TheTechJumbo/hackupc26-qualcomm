#!/usr/bin/env python3
"""
PyTorch + CUDA environment diagnostic.

Run inside the Docker container to verify GPU access and diagnose mismatches.

    docker compose run --rm training python test_torch_cuda.py
    # or directly: python test_torch_cuda.py
"""

import subprocess
import sys


def banner(title: str) -> None:
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print("=" * 55)


def check_versions() -> "torch":
    banner("Python & PyTorch Versions")
    print(f"Python : {sys.version}")

    try:
        import torch
    except ImportError:
        print("ERROR: PyTorch is not installed.")
        sys.exit(1)

    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA build target : {torch.version.cuda}")
    try:
        print(f"cuDNN version     : {torch.backends.cudnn.version()}")
    except Exception:
        print("cuDNN version     : unavailable")

    return torch


def check_host_driver() -> None:
    banner("Host GPU Driver (nvidia-smi)")
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if any(kw in line for kw in ("Driver Version", "CUDA Version", "GPU Name", "|")):
                    stripped = line.strip()
                    if stripped:
                        print(stripped)
        else:
            print("nvidia-smi returned non-zero — no GPU visible to this process.")
            print("Make sure the container is started with --gpus all.")
    except FileNotFoundError:
        print("nvidia-smi not found (expected in runtime images — check container toolkit).")
    except subprocess.TimeoutExpired:
        print("nvidia-smi timed out.")


def check_cuda_available(torch: "torch") -> bool:
    banner("CUDA Availability")
    available = torch.cuda.is_available()
    print(f"torch.cuda.is_available() : {available}")

    if not available:
        print(f"\nPyTorch was compiled for CUDA {torch.version.cuda}.")
        print("The host driver reported above must support that CUDA version.")
        print("\nLikely cause: torch cu130 requires driver API >= 13000,")
        print("but your driver only supports up to CUDA 12.x.")
        print("\nRecommended fix (known to work on this setup):")
        print("  pip install 'torch>=2.2.0' torchvision \\")
        print("      --index-url https://download.pytorch.org/whl/cu118")
        print("\nOr rebuild the Docker image — the Dockerfile now handles this.")
        return False

    banner("Detected GPUs")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        vram_gb = props.total_memory / (1024 ** 3)
        print(f"GPU {i}: {props.name}")
        print(f"  VRAM              : {vram_gb:.1f} GB")
        print(f"  Compute Capability: {props.major}.{props.minor}")
        print(f"  Multi-processors  : {props.multi_processor_count}")

    return True


def smoke_test(torch: "torch") -> bool:
    banner("CUDA Smoke Test  (1000x1000 matmul, FP32 + FP16)")
    try:
        # FP32
        a = torch.randn(1000, 1000, device="cuda")
        b = torch.randn(1000, 1000, device="cuda")
        c = torch.mm(a, b)
        torch.cuda.synchronize()
        print(f"FP32 matmul : OK  — output shape {tuple(c.shape)}")

        # FP16 (required by YOLOv8 with half=True)
        a16, b16 = a.half(), b.half()
        c16 = torch.mm(a16, b16)
        torch.cuda.synchronize()
        print(f"FP16 matmul : OK  — output shape {tuple(c16.shape)}")

        # Memory stats
        allocated = torch.cuda.memory_allocated() / (1024 ** 2)
        reserved  = torch.cuda.memory_reserved()  / (1024 ** 2)
        print(f"\nVRAM allocated : {allocated:.1f} MB")
        print(f"VRAM reserved  : {reserved:.1f} MB")

        return True
    except Exception as exc:
        print(f"SMOKE TEST FAILED: {exc}")
        return False


def main() -> None:
    print("\nPyTorch + CUDA Diagnostic  —  hackupc26-qualcomm")

    torch = check_versions()
    check_host_driver()
    cuda_ok = check_cuda_available(torch)

    if cuda_ok:
        smoke_ok = smoke_test(torch)
        banner("Result")
        if smoke_ok:
            print(f"PASS — PyTorch {torch.__version__} + CUDA {torch.version.cuda} is working.")
            print("GPU training is available for YOLOv8 and future torch-based models.")
        else:
            print("PARTIAL — CUDA detected but operations failed. Check the error above.")
        sys.exit(0 if smoke_ok else 1)
    else:
        banner("Result")
        print("FAIL — CUDA unavailable. See recommended fix above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
