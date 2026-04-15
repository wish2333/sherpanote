"""GPU detection for sherpa-onnx CUDA acceleration.

Checks for NVIDIA GPU hardware, CUDA toolkit, and verifies that
the installed sherpa-onnx build actually includes CUDA support.
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Windows: prevent subprocess calls from flashing a console window.
_SUBPROCESS_FLAGS = 0
if sys.platform == "win32":
    _SUBPROCESS_FLAGS = 0x08000000  # CREATE_NO_WINDOW


@dataclass(frozen=True)
class GpuStatus:
    """Result of GPU detection."""

    available: bool
    gpu_name: str
    cuda_version: str
    reason: str
    onnx_provider: str  # "cuda" if available, "cpu" otherwise


def detect_gpu() -> GpuStatus:
    """Detect NVIDIA GPU and CUDA availability for sherpa-onnx.

    Returns:
        GpuStatus with availability info and human-readable reason.
    """
    # Non-Windows platforms: GPU support not available yet
    if platform.system() != "Windows":
        return GpuStatus(
            available=False,
            gpu_name="",
            cuda_version="",
            reason=f"{platform.system()} GPU acceleration is not yet supported",
            onnx_provider="cpu",
        )

    # Step 1: Check for NVIDIA GPU via nvidia-smi
    gpu_name = _detect_nvidia_gpu()
    if not gpu_name:
        return GpuStatus(
            available=False,
            gpu_name="",
            cuda_version="",
            reason="No NVIDIA GPU detected",
            onnx_provider="cpu",
        )

    # Step 2: Get CUDA version from nvidia-smi
    cuda_version = _detect_cuda_version()
    if not cuda_version:
        return GpuStatus(
            available=False,
            gpu_name=gpu_name,
            cuda_version="",
            reason=f"Found {gpu_name} but CUDA toolkit not detected",
            onnx_provider="cpu",
        )

    # Step 3: Verify sherpa-onnx has CUDA provider compiled in
    if not _verify_sherpa_cuda():
        return GpuStatus(
            available=False,
            gpu_name=gpu_name,
            cuda_version=cuda_version,
            reason="This build does not include CUDA support (CPU-only build)",
            onnx_provider="cpu",
        )

    logger.info("GPU detected: %s, CUDA %s", gpu_name, cuda_version)
    return GpuStatus(
        available=True,
        gpu_name=gpu_name,
        cuda_version=cuda_version,
        reason="",
        onnx_provider="cuda",
    )


def _detect_nvidia_gpu() -> str:
    """Query nvidia-smi for GPU name. Returns empty string if not found."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=_SUBPROCESS_FLAGS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _detect_cuda_version() -> str:
    """Extract CUDA version from nvidia-smi output."""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=_SUBPROCESS_FLAGS,
        )
        if result.returncode == 0:
            match = re.search(r"CUDA Version:\s*(\S+)", result.stdout)
            if match:
                return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _verify_sherpa_cuda() -> bool:
    """Verify that sherpa-onnx was built with CUDA support.

    The CUDA variant of sherpa-onnx has a version string containing
    '+cuda' (e.g. '1.12.38+cuda'). We check this instead of importing
    onnxruntime directly, because sherpa-onnx bundles onnxruntime
    internally and does not expose it as a separate Python package.
    """
    try:
        import sherpa_onnx  # type: ignore[import-untyped]
    except ImportError:
        logger.info("sherpa_onnx not importable for CUDA verification")
        return False

    version = getattr(sherpa_onnx, "__version__", "")
    is_cuda = "+cuda" in version
    if is_cuda:
        logger.info("sherpa-onnx CUDA build detected: %s", version)
    else:
        logger.info("sherpa-onnx is CPU-only build: %s", version)
    return is_cuda
