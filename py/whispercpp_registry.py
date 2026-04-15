"""Whisper.cpp binary registry and management.

Provides platform-specific binary metadata, download URLs,
and installation status checks for the whisper.cpp CLI tool.

Supports multi-variant coexistence: each variant (cpu, blas, cuda-11.8, etc.)
is stored in its own subdirectory under the install root. Switching between
variants only updates a pointer file -- no re-download required.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
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

# File that records which variant is currently active.
_ACTIVE_VARIANT_FILE = "_active_variant.txt"


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
    """Return the root directory for whisper.cpp installations."""
    base = Path(data_dir) / "whisper.cpp"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_variant_dir(data_dir: str | Path, variant: str) -> Path:
    """Return the subdirectory for a specific variant."""
    return get_install_dir(data_dir) / variant


def get_active_variant(data_dir: str | Path) -> str | None:
    """Return the currently active variant, or None."""
    variant_file = get_install_dir(data_dir) / _ACTIVE_VARIANT_FILE
    if variant_file.exists():
        text = variant_file.read_text(encoding="utf-8").strip()
        if text:
            return text
    return None


def set_active_variant(data_dir: str | Path, variant: str) -> None:
    """Set the active variant by writing the pointer file."""
    variant_file = get_install_dir(data_dir) / _ACTIVE_VARIANT_FILE
    variant_file.write_text(variant, encoding="utf-8")


def _find_binary_in_dir(directory: Path) -> Path | None:
    """Search for a whisper executable in a directory."""
    candidates = ["whisper-cli.exe", "main.exe"] if sys.platform == "win32" else ["whisper-cli", "main"]
    for name in candidates:
        path = directory / name
        if path.exists():
            return path
    return None


def _get_active_variant_dir(data_dir: str | Path) -> Path | None:
    """Return the directory of the currently active variant, or None."""
    active = get_active_variant(data_dir)
    if active:
        vdir = get_variant_dir(data_dir, active)
        if vdir.exists() and _find_binary_in_dir(vdir):
            return vdir
    # Backward compat: check flat install (pre-multi-variant layout).
    install_dir = get_install_dir(data_dir)
    if _find_binary_in_dir(install_dir):
        return install_dir
    return None


def get_binary_path(data_dir: str | Path) -> Path:
    """Return the path to the active whisper-cli executable."""
    install_dir = get_install_dir(data_dir)

    # Windows: check app-managed variant dirs, then system PATH.
    if sys.platform == "win32":
        active_dir = _get_active_variant_dir(data_dir)
        if active_dir:
            found = _find_binary_in_dir(active_dir)
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

    # 3. Try inside xcframework structure (legacy flat install or variant subdir).
    install_dir = get_install_dir(data_dir)
    active_dir = _get_active_variant_dir(data_dir)
    search_dirs = [active_dir, install_dir] if active_dir and active_dir != install_dir else [install_dir]
    for search_dir in search_dirs:
        if search_dir is None:
            continue
        if machine in ("arm64", "aarch64"):
            sub = "macos-arm64"
        else:
            sub = "macos-x86_64"
        xcframework = search_dir / "whisper.xcframework" / sub / "whisper-cli"
        if xcframework.exists():
            return xcframework

    # 4. Fallback: direct binary in install dir.
    for search_dir in search_dirs:
        if search_dir is None:
            continue
        found = _find_binary_in_dir(search_dir)
        if found:
            return found
    return None


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


def is_variant_installed(data_dir: str | Path, variant: str) -> bool:
    """Check if a specific variant has been downloaded."""
    vdir = get_variant_dir(data_dir, variant)
    return vdir.exists() and _find_binary_in_dir(vdir) is not None


def get_installed_variants(data_dir: str | Path) -> list[str]:
    """Return list of variants that have been downloaded."""
    install_dir = get_install_dir(data_dir)
    available = {b.variant for b in get_available_binaries()}
    installed = []
    for child in install_dir.iterdir():
        if child.is_dir() and child.name in available and _find_binary_in_dir(child):
            installed.append(child.name)
    return sorted(installed)


def install_binary(
    data_dir: str | Path,
    variant: str | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    proxy_mode: str = "none",
    proxy_url: str | None = None,
) -> dict[str, Any]:
    """Download and install whisper.cpp binary for the current platform.

    If the requested variant is already downloaded, this only switches the
    active pointer -- no re-download occurs.

    Args:
        data_dir: Application data directory.
        variant: Binary variant to install ("cpu", "blas", etc.).
            If None, uses the default for the platform.
        on_progress: Callback(downloaded_bytes, total_bytes).
        proxy_mode: "none", "system", or "custom".
        proxy_url: Proxy URL when mode is "custom".

    Returns:
        Dict with "success", "variant", "version".
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
                "switched": False,
            }

    # macOS: no pre-built CLI in the official release -- guide user to Homebrew.
    if _IS_MACOS:
        return {
            "success": False,
            "error": (
                "macOS 没有预编译的 whisper-cli 二进制文件。"
                "请通过 Homebrew 安装：brew install whisper-cpp"
            ),
            "suggest_brew": True,
        }

    # Check if this variant is already downloaded.
    already_downloaded = is_variant_installed(data_dir, binary.variant)

    if already_downloaded:
        # Just switch the active pointer.
        set_active_variant(data_dir, binary.variant)
        logger.info("Switched to existing variant: %s", binary.variant)
        return {
            "success": True,
            "variant": binary.variant,
            "version": WHISPER_CPP_VERSION,
            "switched": True,
        }

    # Download and extract to variant-specific subdirectory.
    variant_dir = get_variant_dir(data_dir, binary.variant)
    variant_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = install_dir / "_download.tmp"
    try:
        _download_file(
            binary.url, tmp_path,
            on_progress=on_progress,
            proxy_mode=proxy_mode,
            proxy_url=proxy_url,
        )

        # Extract to variant subdirectory.
        _extract_binary(tmp_path, variant_dir, current)

        # Verify the new variant.
        found = _find_binary_in_dir(variant_dir)
        if not found:
            return {
                "success": False,
                "error": "Binary installed but not found after extraction",
            }

        # Set as active.
        set_active_variant(data_dir, binary.variant)

        return {
            "success": True,
            "variant": binary.variant,
            "version": WHISPER_CPP_VERSION,
            "switched": False,
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
            extracted_names: list[str] = []
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                basename = name.rsplit("/", 1)[-1]
                target = dest / basename
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                extracted_names.append(basename)

            if not any(n.lower() == "main.exe" for n in extracted_names):
                raise FileNotFoundError(
                    f"main.exe not found in archive. Contents: {extracted_names[:10]}"
                )
            logger.info("Extracted %d files to %s", len(extracted_names), dest)
        else:
            has_xcframework = any("xcframework" in n for n in zf.namelist())
            if has_xcframework:
                zf.extractall(dest)
                logger.info("Extracted xcframework to %s", dest)
            else:
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


def uninstall_binary(data_dir: str | Path, variant: str | None = None) -> bool:
    """Remove whisper.cpp installation.

    Args:
        data_dir: Application data directory.
        variant: If specified, only remove this variant's subdirectory.
            If None, remove the entire whisper.cpp install directory.

    Returns:
        True if anything was removed.
    """
    if variant:
        vdir = get_variant_dir(data_dir, variant)
        if vdir.exists():
            shutil.rmtree(vdir)
            # If the removed variant was active, clear the pointer.
            if get_active_variant(data_dir) == variant:
                # Try to auto-switch to another installed variant.
                remaining = get_installed_variants(data_dir)
                if remaining:
                    set_active_variant(data_dir, remaining[0])
                else:
                    pointer = get_install_dir(data_dir) / _ACTIVE_VARIANT_FILE
                    pointer.unlink(missing_ok=True)
            return True
        return False

    # Remove everything.
    install_dir = get_install_dir(data_dir)
    if not install_dir.exists():
        return False
    shutil.rmtree(install_dir)
    return True


def get_status(data_dir: str | Path) -> dict[str, Any]:
    """Return the current installation status."""
    installed = is_installed(data_dir)
    available = get_available_binaries()

    current_variant = get_active_variant(data_dir)
    installed_variants = get_installed_variants(data_dir)

    # Migrate legacy flat install to variant-based layout.
    if installed and not current_variant and not installed_variants:
        install_dir = get_install_dir(data_dir)
        if _find_binary_in_dir(install_dir) and not _IS_MACOS:
            # Existing flat install detected. Treat it as the default variant.
            default = get_default_binary()
            if default:
                variant_dir = get_variant_dir(data_dir, default.variant)
                if not variant_dir.exists():
                    variant_dir.mkdir(parents=True, exist_ok=True)
                    # Move files from root to variant subdir.
                    for child in install_dir.iterdir():
                        if child.is_file() and child.name != _ACTIVE_VARIANT_FILE:
                            child.rename(variant_dir / child.name)
                    set_active_variant(data_dir, default.variant)
                    current_variant = default.variant
                    installed_variants = [default.variant]
                    logger.info("Migrated flat install to variant layout: %s", default.variant)

    # Detect installation source (macOS).
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
        "current_variant": current_variant,
        "installed_variants": installed_variants,
        "source": source,
    }
