"""Whisper.cpp binary registry and management.

Provides platform-specific binary metadata, download URLs,
and installation status checks for the whisper.cpp CLI tool.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_IS_MACOS = sys.platform == "darwin"

logger = logging.getLogger(__name__)

# whisper.cpp version to use for all platforms.
WHISPER_CPP_VERSION = "1.8.4"

# GitHub release base URL.
GITHUB_RELEASE_BASE = (
    f"https://github.com/ggerganov/whisper.cpp/releases/download/v{WHISPER_CPP_VERSION}"
)


@dataclass(frozen=True)
class WhisperCppBinary:
    """Metadata for a platform-specific whisper.cpp binary."""

    platform: str       # "windows-x64", "darwin-arm64", "darwin-x64"
    variant: str        # "cpu", "blas", "cuda-11.8", "cuda-12.4"
    url: str
    size_mb: int
    sha256: str | None = None


# Curated binary catalog from official GitHub Releases.
BINARIES: tuple[WhisperCppBinary, ...] = (
    WhisperCppBinary(
        platform="windows-x64",
        variant="cpu",
        url=f"{GITHUB_RELEASE_BASE}/whisper-bin-x64.zip",
        size_mb=4,
    ),
    WhisperCppBinary(
        platform="windows-x64",
        variant="blas",
        url=f"{GITHUB_RELEASE_BASE}/whisper-blas-bin-x64.zip",
        size_mb=16,
    ),
    WhisperCppBinary(
        platform="windows-x64",
        variant="cuda-11.8",
        url=f"{GITHUB_RELEASE_BASE}/whisper-cublas-11.8.0-bin-x64.zip",
        size_mb=57,
    ),
    WhisperCppBinary(
        platform="darwin-arm64",
        variant="cpu",
        url=f"{GITHUB_RELEASE_BASE}/whisper-v{WHISPER_CPP_VERSION}-xcframework.zip",
        size_mb=45,
    ),
    WhisperCppBinary(
        platform="darwin-x64",
        variant="cpu",
        url=f"{GITHUB_RELEASE_BASE}/whisper-v{WHISPER_CPP_VERSION}-xcframework.zip",
        size_mb=45,
    ),
)


def _current_platform() -> str:
    """Return the platform identifier string."""
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "windows-x64"
    if system == "Darwin":
        if machine in ("arm64", "aarch64"):
            return "darwin-arm64"
        return "darwin-x64"
    return f"{system.lower()}-{machine}"


def get_available_binaries() -> list[WhisperCppBinary]:
    """Return binaries available for the current platform."""
    current = _current_platform()
    return [b for b in BINARIES if b.platform == current]


def get_default_binary() -> WhisperCppBinary | None:
    """Return the recommended binary for the current platform.

    Prefers BLAS (CPU-optimized) on all platforms, or plain CPU if BLAS
    is not available.
    """
    available = get_available_binaries()
    if not available:
        return None

    # Prefer BLAS over plain CPU.
    blas = [b for b in available if b.variant == "blas"]
    if blas:
        return blas[0]

    return available[0]


def get_install_dir(data_dir: str | Path) -> Path:
    """Return the directory where whisper.cpp binary should be installed."""
    base = Path(data_dir) / "whisper.cpp"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _find_binary_in_dir(directory: Path) -> Path | None:
    """Search for a whisper executable in a directory."""
    candidates = ["whisper-cli.exe", "main.exe"] if sys.platform == "win32" else ["whisper-cli", "main"]
    for name in candidates:
        path = directory / name
        if path.exists():
            return path
    return None


def get_binary_path(data_dir: str | Path) -> Path:
    """Return the expected path to the whisper-cli executable."""
    install_dir = get_install_dir(data_dir)

    # Windows: check app-managed dir, then system PATH.
    if sys.platform == "win32":
        found = _find_binary_in_dir(install_dir)
        if found:
            return found
        system_binary = shutil.which("whisper-cli")
        if system_binary:
            return Path(system_binary)

    # macOS / Linux: homebrew, system PATH, xcframework, app-managed dir.
    found = get_macos_binary_path(data_dir)
    if found and found.exists():
        return found

    # Fallback.
    if sys.platform == "win32":
        return install_dir / "whisper-cli.exe"
    return install_dir / "whisper-cli"


def get_macos_binary_path(data_dir: str | Path) -> Path | None:
    """Return the macOS binary path, or None if not found.

    Priority:
    1. Homebrew (explicit paths, since .app bundles have limited PATH)
    2. System PATH (covers other package managers)
    3. App-managed xcframework directory
    4. Direct binary in install dir
    """
    # 1. Check Homebrew paths explicitly (app bundles may not have /opt/homebrew/bin on PATH).
    machine = platform.machine().lower()
    homebrew_prefix = "/opt/homebrew" if machine in ("arm64", "aarch64") else "/usr/local"
    homebrew_bin = Path(homebrew_prefix) / "bin" / "whisper-cli"
    if homebrew_bin.exists():
        return homebrew_bin

    # 2. Check system PATH.
    system_binary = shutil.which("whisper-cli")
    if system_binary:
        return Path(system_binary)

    # 3. Try inside xcframework structure.
    install_dir = get_install_dir(data_dir)
    if machine in ("arm64", "aarch64"):
        sub = "macos-arm64"
    else:
        sub = "macos-x86_64"
    xcframework = install_dir / "whisper.xcframework" / sub / "whisper-cli"
    if xcframework.exists():
        return xcframework

    # 4. Fallback: direct binary in install dir.
    found = _find_binary_in_dir(install_dir)
    return found


def is_installed(data_dir: str | Path) -> bool:
    """Check if whisper.cpp binary is installed and executable.

    Verification is based on the binary being runnable (no OSError /
    DLL-not-found crash). Exit code is not checked because whisper.cpp
    CLI may return non-zero for --help depending on the version.
    """
    path = get_binary_path(data_dir)
    if not path or not path.exists():
        return False

    # Set cwd to the binary directory so Windows can find DLLs
    # (whisper.dll, ggml.dll, etc.) at runtime.
    try:
        subprocess.run(
            [str(path), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(path.parent),
        )
        return True
    except OSError as exc:
        logger.warning("whisper.cpp verification OSError: %s", exc)
        return False
    except subprocess.TimeoutExpired:
        # Didn't crash -- binary exists and loads, just slow to respond.
        return True


def install_binary(
    data_dir: str | Path,
    variant: str | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    proxy_mode: str = "none",
    proxy_url: str | None = None,
) -> dict[str, Any]:
    """Download and install whisper.cpp binary for the current platform.

    Args:
        data_dir: Application data directory.
        variant: Binary variant to install ("cpu", "blas", etc.).
            If None, uses the default for the platform.
        on_progress: Callback(downloaded_bytes, total_bytes).
        proxy_mode: "none", "system", or "custom".
        proxy_url: Proxy URL when mode is "custom".

    Returns:
        Dict with "success", "path", "variant", "version".
    """
    current = _current_platform()

    if variant:
        binary = next(
            (b for b in BINARIES if b.platform == current and b.variant == variant),
            None,
        )
    else:
        binary = get_default_binary()

    if binary is None:
        return {
            "success": False,
            "error": f"No whisper.cpp binary available for platform: {current}",
        }

    install_dir = get_install_dir(data_dir)
    install_dir.mkdir(parents=True, exist_ok=True)

    # macOS: check if already installed via Homebrew.
    if _IS_MACOS:
        homebrew_path = get_macos_binary_path(data_dir)
        if homebrew_path:
            return {
                "success": True,
                "variant": "homebrew",
                "version": WHISPER_CPP_VERSION,
                "source": "homebrew",
            }

    # macOS: no pre-built CLI in the official release — guide user to Homebrew.
    if _IS_MACOS:
        return {
            "success": False,
            "error": (
                "macOS 没有预编译的 whisper-cli 二进制文件。"
                "请通过 Homebrew 安装：brew install whisper-cpp"
            ),
            "suggest_brew": True,
        }

    # Download (Windows only).
    tmp_path = install_dir / "_download.tmp"
    try:
        _download_file(
            binary.url, tmp_path,
            on_progress=on_progress,
            proxy_mode=proxy_mode,
            proxy_url=proxy_url,
        )

        # Extract.
        _extract_binary(tmp_path, install_dir, current)

        # Verify.
        if not is_installed(data_dir):
            return {
                "success": False,
                "error": "Binary installed but verification failed",
            }

        return {
            "success": True,
            "variant": binary.variant,
            "version": WHISPER_CPP_VERSION,
        }
    except Exception as exc:
        logger.exception("Failed to install whisper.cpp binary")
        return {"success": False, "error": str(exc)}
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _download_file(
    url: str,
    dest: Path,
    on_progress: Callable[[int, int], None] | None = None,
    proxy_mode: str = "none",
    proxy_url: str | None = None,
) -> None:
    """Download a file with progress reporting."""
    opener = urllib.request.build_opener()

    if proxy_mode == "custom" and proxy_url:
        proxy_handler = urllib.request.ProxyHandler({
            "http": proxy_url,
            "https": proxy_url,
        })
        opener = urllib.request.build_opener(proxy_handler)
    elif proxy_mode == "system":
        opener = urllib.request.build_opener()

    req = urllib.request.Request(url)
    resp = opener.open(req, timeout=60)
    total = int(resp.headers.get("Content-Length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        while True:
            chunk = resp.read(8192)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if on_progress and total > 0:
                on_progress(downloaded, total)


def _extract_binary(archive: Path, dest: Path, platform_id: str) -> None:
    """Extract whisper-cli binary and all dependencies from a zip archive.

    For Windows: extracts main.exe + required DLLs (whisper.dll, ggml.dll, etc.)
    into a flat directory structure.

    For macOS / Linux: extracts the xcframework directory preserving structure,
    or falls back to extracting individual binary files.
    """
    if not archive.exists():
        raise FileNotFoundError(f"Archive not found: {archive}")

    with zipfile.ZipFile(archive, "r") as zf:
        if platform_id == "windows-x64":
            # Extract all files, flattening any subdirectory structure.
            # This ensures DLLs (whisper.dll, ggml.dll, etc.) are present
            # alongside main.exe.
            extracted_names: list[str] = []
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                basename = name.rsplit("/", 1)[-1]
                # Skip subdirectory entries that create nested dirs.
                if "/" in name:
                    target = dest / basename
                else:
                    target = dest / basename
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                extracted_names.append(basename)

            # Verify main.exe was extracted.
            if not any(n.lower() == "main.exe" for n in extracted_names):
                raise FileNotFoundError(
                    f"main.exe not found in archive. Contents: {extracted_names[:10]}"
                )
            logger.info("Extracted %d files to %s", len(extracted_names), dest)
        else:
            # macOS / Linux: preserve xcframework directory structure.
            has_xcframework = any("xcframework" in n for n in zf.namelist())
            if has_xcframework:
                zf.extractall(dest)
                logger.info("Extracted xcframework to %s", dest)
            else:
                # Fallback: extract individual binary + libraries.
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    basename = name.rsplit("/", 1)[-1]
                    target = dest / basename
                    with zf.open(name) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    if not basename.endswith((".txt", ".md", ".plist")):
                        target.chmod(0o755)
                    logger.info("Extracted %s to %s", basename, target)


def uninstall_binary(data_dir: str | Path) -> bool:
    """Remove the whisper.cpp installation directory."""
    install_dir = get_install_dir(data_dir)
    if not install_dir.exists():
        return False
    shutil.rmtree(install_dir)
    return True


def get_status(data_dir: str | Path) -> dict[str, Any]:
    """Return the current installation status."""
    installed = is_installed(data_dir)
    available = get_available_binaries()

    # Detect installation source.
    source = None
    if installed and _IS_MACOS:
        system_binary = get_macos_binary_path(data_dir)
        if system_binary and "homebrew" in str(system_binary):
            source = "homebrew"

    return {
        "installed": installed,
        "version": WHISPER_CPP_VERSION if installed else None,
        "platform": _current_platform(),
        "available_variants": [b.variant for b in available],
        "default_variant": get_default_binary().variant if available else None,
        "source": source,
    }
