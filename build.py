# /// script
# requires-python = ">=3.10"
# dependencies = ["pyinstaller>=6.19.0"]
# ///
"""
PyWebVue build script - auto-detect platform and build accordingly.

============================================================
Usage
============================================================

    uv run build.py                              Desktop build (onedir)
    uv run build.py --onefile                    Desktop build (single executable)
    uv run build.py --with-models model-a[,model-b]  Desktop build with bundled models
    uv run build.py --android                    Android APK build (macOS / Linux)
    uv run build.py --clean                      Remove all build artifacts

============================================================
Desktop build details
============================================================

    onedir mode (default):
    Produces dist/app/ folder containing the executable + all
    dependencies. Faster startup than onefile.

    onefile mode (--onefile):
    Produces a single dist/app.exe file. Convenient to
    distribute but slower startup (must extract to temp dir).

    Both modes read app.spec for configuration.
    Edit app.spec to change: entry script, frontend assets,
    app name, icon, etc. See app.spec header for details.

    --with-models (onedir only):
    Downloads specified ASR models and bundles them in the
    dist folder. Comma-separated model IDs from the registry.
    Not compatible with --onefile.

============================================================
Android build details
============================================================

    Requires macOS or Linux (not supported on Windows).
    Uses Buildozer to produce an Android APK.

    First run generates buildozer.spec automatically.
    Edit buildozer.spec to change: app title, package name,
    permissions, Android API level, etc.

    Note: Android does NOT support multi-window. Your app
    must use a single window.

============================================================
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


# ========== venv helpers ==========


def _venv_python() -> Path:
    """Return the path to the project .venv Python executable."""
    if sys.platform == "win32":
        return PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    return PROJECT_ROOT / ".venv" / "bin" / "python"


def _ensure_pyinstaller_in_venv() -> None:
    """Install PyInstaller into the project .venv if not already present."""
    py = _venv_python()
    if not py.exists():
        _error("Project .venv not found. Run 'uv sync' first.")

    result = subprocess.run(
        [str(py), "-c", "import PyInstaller; print(PyInstaller.__version__)"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        _info(f"PyInstaller {result.stdout.strip()} in .venv")
        return

    _info("Installing PyInstaller into .venv ...")
    uv = _find_cmd("uv")
    if uv is None:
        _error("uv not found.")
    r = subprocess.run(
        [uv, "pip", "install", "--python", str(py), "pyinstaller>=6.19.0"],
    )
    if r.returncode != 0:
        _error("Failed to install PyInstaller into .venv")


# ========== helpers ==========

def _info(msg: str) -> None:
    print(f"[INFO] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def _check_command(name: str, install_hint: str) -> None:
    """Check if a CLI tool is installed."""
    try:
        subprocess.run([name, "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        _error(f"{name} not found. {install_hint}")


def _find_cmd(*names: str) -> str | None:
    """Return the first available command, or None."""
    for name in names:
        if shutil.which(name) is not None:
            return name
    return None


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command, exit on failure."""
    _info(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        _error(f"Command failed (exit {r.returncode}): {' '.join(cmd)}")


# ========== clean ==========

def _clean() -> None:
    """Remove build artifacts (build/, dist/, temp spec files)."""
    for name in ("build", "dist"):
        p = PROJECT_ROOT / name
        if p.exists():
            shutil.rmtree(p)
            _info(f"Removed {name}/")

    for spec in PROJECT_ROOT.glob("_build_*.spec"):
        spec.unlink()
        _info(f"Removed {spec.name}")

    _info("Clean complete")


# ========== desktop: onedir ==========

def _build_onedir(
    bundled_model_dirs: list[tuple[str, str]] | None = None,
    cuda_venv_python: Path | None = None,
    ocr_model_datas: list[tuple[str, str]] | None = None,
) -> None:
    """Build desktop app as a directory (uses app.spec directly)."""
    spec = PROJECT_ROOT / "app.spec"
    if not spec.exists():
        _error(
            f"Spec file not found: {spec}\n"
            "Make sure app.spec exists in the project root."
        )

    # Collect all extra datas that need injection into the spec.
    extra_datas: list[tuple[str, str]] = []
    if bundled_model_dirs:
        _info(f"Bundling {len(bundled_model_dirs)} model(s) into onedir build")
        extra_datas.extend(bundled_model_dirs)
    if ocr_model_datas:
        _info(f"Bundling {len(ocr_model_datas)} OCR model file(s) into onedir build")
        extra_datas.extend(ocr_model_datas)

    if extra_datas:
        spec = _inject_model_datas(spec, extra_datas)

    # For CUDA builds, use the isolated CUDA venv.
    # For normal builds, use the project .venv.
    if cuda_venv_python is not None:
        py = cuda_venv_python
    else:
        _ensure_pyinstaller_in_venv()
        py = _venv_python()

    cmd = [str(py), "-m", "PyInstaller", "--clean", "--noconfirm", str(spec)]
    _info(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    # Clean up temp spec if generated.
    if spec.name.startswith("_build_"):
        spec.unlink(missing_ok=True)

    if result.returncode != 0:
        _error("PyInstaller build failed")

    _info(f"Build complete -> {PROJECT_ROOT / 'dist' / 'SherpaNote'}")


def _inject_model_datas(
    original_spec: Path,
    model_dirs: list[tuple[str, str]],
) -> Path:
    """Create a temporary app.spec with additional model datas injected."""
    content = original_spec.read_text(encoding="utf-8")

    # Build the extra data lines to insert.
    model_lines = "\n".join(
        f'    (r"{path}", "{dest}"),'
        for path, dest in model_dirs
    )

    # Insert model entries after "datas = [" — use string find, not regex,
    # to avoid backslash escaping issues with Windows paths.
    # Match only the uncommented line (not inside # comment blocks).
    marker = "\ndatas = ["
    idx = content.find(marker)
    if idx == -1:
        _error("Could not find 'datas = [' in spec file")
    idx += 1  # skip the leading \n
    insert_pos = idx + len(marker)
    content = content[:insert_pos] + "\n" + model_lines + content[insert_pos:]

    tmp_spec = PROJECT_ROOT / "_build_onedir_with_models.spec"
    tmp_spec.write_text(content, encoding="utf-8")
    return tmp_spec


# ========== CUDA support ==========

# sherpa-onnx CUDA wheel configuration
# Reference: https://k2-fsa.github.io/sherpa/onnx/cuda.html
# Available variants:
#   "cuda"          -> CUDA 11.8
#   "cuda12.cudnn9" -> CUDA 12.8 + cuDNN 9
_SHERPA_CUDA_VERSION = "1.12.38"
_SHERPA_CUDA_INDEX_URL = "https://k2-fsa.github.io/sherpa/onnx/cuda.html"
_CUDA_BUILD_VENV = PROJECT_ROOT / "_cuda_build_venv"


def _setup_cuda_env(cuda_variant: str = "cuda") -> Path:
    """Create an isolated temporary venv with the CUDA variant of sherpa-onnx.

    This keeps the project's .venv untouched so dev mode is not affected.
    The temp venv is deleted after the build.

    Returns:
        Path to the temp venv's Python executable.
    """
    uv = _find_cmd("uv")
    if uv is None:
        _error("uv not found.")

    venv_dir = _CUDA_BUILD_VENV
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    # Clean up any previous temp venv.
    if venv_dir.exists():
        shutil.rmtree(venv_dir)

    # 1. Create temp venv.
    _info("Creating isolated CUDA build environment...")
    subprocess.run([uv, "venv", str(venv_dir)], check=True)

    # 2. Install project dependencies.
    _info("Installing project dependencies into CUDA venv...")
    subprocess.run(
        [uv, "pip", "install", "--python", str(venv_python), str(PROJECT_ROOT)],
        check=True,
    )

    # 3. Uninstall CPU-only sherpa-onnx-bin.
    _info("Removing CPU-only sherpa-onnx-bin...")
    subprocess.run(
        [uv, "pip", "uninstall", "--python", str(venv_python), "-y", "sherpa-onnx-bin"],
        capture_output=True,
    )

    # 4. Install CUDA variant from official wheel index.
    version_spec = f"{_SHERPA_CUDA_VERSION}+{cuda_variant}"
    _info(f"Installing sherpa-onnx=={version_spec} ...")
    _info(f"  Index: {_SHERPA_CUDA_INDEX_URL}")
    result = subprocess.run(
        [uv, "pip", "install", "--python", str(venv_python),
         f"sherpa-onnx=={version_spec}",
         "--no-index", "-f", _SHERPA_CUDA_INDEX_URL],
    )
    if result.returncode != 0:
        _error(
            f"Failed to install sherpa-onnx {version_spec}.\n"
            "  Check available versions at: https://k2-fsa.github.io/sherpa/onnx/cuda.html\n"
            "  Ensure your NVIDIA GPU and CUDA toolkit meet the requirements."
        )

    # 5. Install PyInstaller.
    _info("Installing PyInstaller into CUDA venv...")
    subprocess.run(
        [uv, "pip", "install", "--python", str(venv_python), "pyinstaller>=6.19.0"],
        check=True,
    )

    # Verify.
    result = subprocess.run(
        [str(venv_python), "-c",
         "import sherpa_onnx; print(sherpa_onnx.__version__)"],
        capture_output=True, text=True,
    )
    installed_version = result.stdout.strip()
    _info(f"  sherpa-onnx {installed_version} in CUDA venv")

    return venv_python


def _cleanup_cuda_venv() -> None:
    """Remove the temporary CUDA build venv."""
    if _CUDA_BUILD_VENV.exists():
        shutil.rmtree(_CUDA_BUILD_VENV)
        _info("Cleaned up temporary CUDA build environment")


# ========== desktop: onefile ==========

def _build_onefile(
    cuda_venv_python: Path | None = None,
) -> None:
    """Build desktop app as a single executable.

    Generates a temporary onefile spec based on app.spec config,
    then runs PyInstaller. The temp spec is deleted after build.
    """
    if cuda_venv_python is not None:
        py = cuda_venv_python
    else:
        _ensure_pyinstaller_in_venv()
        py = _venv_python()

    spec_content = _generate_onefile_spec()
    tmp_spec = PROJECT_ROOT / "_build_onefile.spec"
    tmp_spec.write_text(spec_content, encoding="utf-8")

    cmd = [str(py), "-m", "PyInstaller", "--clean", "--noconfirm", str(tmp_spec)]
    _info(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    tmp_spec.unlink(missing_ok=True)

    if result.returncode != 0:
        _error("PyInstaller build failed")

    exe_name = "SherpaNote.exe" if sys.platform == "win32" else "SherpaNote"
    exe_path = PROJECT_ROOT / "dist" / exe_name
    if exe_path.exists():
        _info(f"Build complete -> {exe_path}")
    else:
        _warn(f"Output not found at {exe_path}")
        _info("Check dist/ directory for results")


def _generate_onefile_spec() -> str:
    """Generate PyInstaller spec content for onefile mode.

    Reads configuration from app.spec's user-configurable sections.
    Modify app.spec to customize: entry script, app name, icon, etc.
    """
    # --- Read user config from app.spec ---
    entry_script = "main.py"       # [MODIFY] same as app.spec ENTRY_SCRIPT
    app_name = "SherpaNote"         # [MODIFY] same as app.spec APP_NAME
    icon = None                    # [MODIFY] same as app.spec ICON

    project_root = Path(__file__).parent

    # Frontend assets (same logic as app.spec)
    frontend_dist = project_root / "frontend_dist"
    if frontend_dist.is_dir():
        _path = str(frontend_dist)
        datas_line = f'        (r"{_path}", "frontend_dist"),'
    else:
        _path = str(project_root / "index.html")
        datas_line = f'        (r"{_path}", "."),'

    icon_line = f'    icon=r"{icon}",' if icon else "    icon=None,"

    return f"""\
# -*- mode: python ; coding: utf-8 -*-
# Auto-generated by: uv run build.py --onefile
# To customize: edit the [MODIFY] markers below, or edit app.spec and
#               regenerate by running this command again.
import sys
from pathlib import Path

project_root = Path(SPECPATH)

# [MODIFY] Your main script path
ENTRY_SCRIPT = str(project_root / "{entry_script}")

# [MODIFY] Output executable name
APP_NAME = "{app_name}"

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
{datas_line}
    ],
    hiddenimports=["pywebvue", "pywebvue.app", "pywebvue.bridge"],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Collect sherpa-onnx DLLs (CUDA provider DLLs are loaded dynamically
# by onnxruntime at runtime and PyInstaller cannot detect them).
a.binaries += [
    (f.name, str(f), "BINARY")
    for f in _pathlib.Path(__import__("sherpa_onnx").__file__).parent.joinpath("lib").glob("*.dll")
]

# Exclude unused GUI frameworks to reduce size
if sys.platform == "win32":
    a.excludes += ["PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter"]
elif sys.platform == "linux":
    a.excludes += ["PyQt5", "PyQt6", "PySide2", "PySide6"]
elif sys.platform == "darwin":
    a.excludes += ["PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter"]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,   # onefile: bundle binaries into the exe
    a.datas,      # onefile: bundle datas into the exe
    [],
    name=APP_NAME,
{icon_line}
    debug=False,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""


# ========== android ==========

def _build_android() -> None:
    """Build Android APK using Buildozer.

    Requirements:
        - Linux (WSL, Docker, or native Linux)
        - buildozer installed: pip install buildozer
        - Android SDK/NDK (buildozer downloads automatically on first run)

    On first run, generates buildozer.spec. Edit it to customize:
        - [app] title, package.name, package.domain, version
        - [app] requirements (add your Python dependencies here)
        - [app:android] android.api, android.minapi, permissions, etc.
    """
    if sys.platform == "win32":
        _error(
            "Android builds are not supported on Windows.\n"
            "Options: macOS (native), Linux (native), WSL, or Docker."
        )

    _check_command("buildozer", "Install with: pip install buildozer")

    _generate_buildozer_spec()

    _info("Starting Android build (first build downloads SDK, may take long)...")
    result = subprocess.run(
        ["buildozer", "android", "debug"],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        _error("Android build failed")

    _info("Build complete. APK location: bin/")


def _generate_buildozer_spec() -> None:
    """Generate buildozer.spec for Android builds.

    Only generates if buildozer.spec does not already exist.
    If it exists, the existing file is used as-is (user may have
    customized it). Delete buildozer.spec to regenerate.
    """
    spec_path = PROJECT_ROOT / "buildozer.spec"
    if spec_path.exists():
        _info(f"Using existing {spec_path.name} (delete to regenerate)")
        return

    # Resolve pywebview Android JAR path
    jar_path = ""
    try:
        from webview import util  # type: ignore[import-untyped]
        jar_path = str(util.android_jar_path())
    except Exception:
        _warn(
            "Could not resolve pywebview Android JAR path.\n"
            "  Run: python -c \"from webview import util; print(util.android_jar_path())\"\n"
            "  Then update android.add_jars in buildozer.spec manually."
        )

    content = f"""\
# ============================================================
# Buildozer spec for PyWebVue Android builds
# ============================================================
# Generated by: uv run build.py --android
#
# [MODIFY] Customize the values below for your project:
#   - title:            Display name of your app
#   - package.name:     APK package name (lowercase, no spaces)
#   - package.domain:   Reverse domain (e.g. com.yourcompany)
#   - version:          App version string
#   - requirements:     Python packages your app needs
#   - android.api:      Target Android API level
#   - android.minapi:   Minimum Android API level
#   - android.permissions: Permissions your app needs
# ============================================================

[app]
title = PyWebVue App
package.name = pywebvue
package.domain = org.pywebvue
source.dir = .
source.include_exts = py,html,css,js
version = 0.1

# pywebview 6.x uses Kivyless Android (kivy still needed for bootstrap)
# [MODIFY] Add your own Python dependencies here, comma-separated
requirements = python3,kivy,pywebview
android.add_jars = {jar_path}

# [MODIFY] portrait / landscape / sensor
orientation = portrait
fullscreen = 1

[app:android]
# [MODIFY] Add permissions as needed: INTERNET, CAMERA, READ_EXTERNAL_STORAGE, etc.
android.permissions = INTERNET
# [MODIFY] Target API level (33 = Android 13)
android.api = 33
# [MODIFY] Minimum API level (24 = Android 7.0)
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
"""

    spec_path.write_text(content, encoding="utf-8")
    _info(f"Generated {spec_path.name} - review and customize before building")


# ========== main ==========

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PyWebVue build script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
    uv run build.py                                    Desktop build (onedir)
    uv run build.py --onefile                          Desktop build (single exe)
    uv run build.py --with-models model-a,model-b      Bundle models with onedir
    uv run build.py --cuda                             CUDA GPU build (CUDA 11.8)
    uv run build.py --cuda --cuda-variant cuda12.cudnn9  CUDA 12.8 + cuDNN 9
    uv run build.py --with-ocr-models                  Bundle default OCR models (onedir)
    uv run build.py --with-plugins                    Bundle plugin runtime (Python + uv)
    uv run build.py --android                          Android APK (macOS / Linux)
    uv run build.py --clean                            Remove build artifacts

configuration:
    Desktop: edit app.spec
    Android: edit buildozer.spec (generated on first --android run)
""",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--onefile", action="store_true",
                        help="Build single executable instead of folder")
    group.add_argument("--android", action="store_true",
                        help="Build Android APK (requires macOS or Linux)")
    parser.add_argument("--clean", action="store_true",
                        help="Remove build/ and dist/ artifacts")
    parser.add_argument("--with-models", type=str, default=None,
                        metavar="MODEL_IDS",
                        help="Comma-separated model IDs to bundle (onedir only)")
    parser.add_argument("--cuda", action="store_true",
                        help="Build with CUDA GPU support (NVIDIA only, Windows)")
    parser.add_argument("--cuda-variant", type=str, default="cuda",
                        choices=["cuda", "cuda12.cudnn9"],
                        metavar="VARIANT",
                        help="CUDA variant: 'cuda' (CUDA 11.8, default) or "
                             "'cuda12.cudnn9' (CUDA 12.8 + cuDNN 9)")
    parser.add_argument("--with-ocr-models", action="store_true",
                        help="Bundle default OCR models (onedir only). "
                             "Downloads v5/mobile det, v5/mobile rec, "
                             "v5/server cls into the package.")
    parser.add_argument("--with-plugins", action="store_true",
                        help="Bundle plugin runtime (python-build-standalone + uv). "
                             "Enables optional backends (docling, opendataloader-pdf).")
    args = parser.parse_args()

    if args.clean:
        _clean()
        return

    _info(f"Platform: {sys.platform}")

    if args.android:
        _build_android()
        return

    if args.with_models and args.onefile:
        _error("--with-models is not compatible with --onefile mode. "
               "Models are too large for single-exe distribution.")

    if args.with_ocr_models and args.onefile:
        _error("--with-ocr-models is not compatible with --onefile mode. "
               "OCR models are too large for single-exe distribution.")

    if args.with_plugins and args.onefile:
        _error("--with-plugins is not compatible with --onefile mode. "
               "Plugin runtime is too large for single-exe distribution.")

    _build_frontend()

    # Download models if requested.
    bundled_model_dirs: list[tuple[str, str]] = []
    if args.with_models:
        model_ids = [m.strip() for m in args.with_models.split(",")]
        bundled_model_dirs = _download_build_models(model_ids)

    # Download OCR models if requested.
    ocr_model_datas: list[tuple[str, str]] = []
    if args.with_ocr_models:
        ocr_model_datas = _download_ocr_models()

    # Download plugin runtime if requested.
    if args.with_plugins:
        _download_plugin_runtime()

    _build_desktop(
        onefile=args.onefile,
        bundled_model_dirs=bundled_model_dirs,
        cuda=args.cuda,
        cuda_variant=args.cuda_variant,
        ocr_model_datas=ocr_model_datas,
    )


# ========== frontend build ==========

def _build_frontend() -> None:
    """Build the Vue frontend to frontend_dist/."""
    frontend_dir = PROJECT_ROOT / "frontend"
    dist_dir = PROJECT_ROOT / "frontend_dist"

    if not (frontend_dir / "package.json").exists():
        _error(f"No package.json in {frontend_dir}.")

    pm = _find_cmd("bun", "npm", "yarn")
    if pm is None:
        _error("No package manager found. Install bun/npm/yarn first.")

    # Ensure deps installed
    _info("[0] Installing frontend dependencies...")
    _run([pm, "install"], cwd=frontend_dir)

    # Build
    _info("[0.5] Building Vue app...")
    _run([pm, "run", "build"], cwd=frontend_dir)

    if not dist_dir.exists():
        _error(f"Frontend build failed: {dist_dir} not found.")
    _info(f"    Frontend built -> {dist_dir}")


# ========== desktop ==========

def _build_desktop(
    onefile: bool = False,
    bundled_model_dirs: list[tuple[str, str]] | None = None,
    cuda: bool = False,
    cuda_variant: str = "cuda",
    ocr_model_datas: list[tuple[str, str]] | None = None,
) -> None:
    cuda_venv_python = None
    if cuda:
        _info("=== CUDA GPU build (NVIDIA) ===")
        cuda_venv_python = _setup_cuda_env(cuda_variant)
    try:
        if onefile:
            _build_onefile(cuda_venv_python=cuda_venv_python)
        else:
            _build_onedir(
                bundled_model_dirs=bundled_model_dirs,
                cuda_venv_python=cuda_venv_python,
                ocr_model_datas=ocr_model_datas,
            )
    finally:
        if cuda_venv_python is not None:
            _info(f"CUDA build venv kept at: {_CUDA_BUILD_VENV}")
            _info(f"(delete manually with: rmdir /s /q {_CUDA_BUILD_VENV})")


# ========== plugin runtime bundling ==========

# python-build-standalone: install_only Python for creating plugin venvs
# Matches the major.minor version used in pyproject.toml
_PBS_VERSION = "3.11.11"
_PBS_BUILD = "20241016"
_PBS_PLATFORM = {
    "win32": "x86_64-pc-windows-msvc-shared-install_only.tar.gz",
    "darwin": "aarch64-apple-darwin-install_only.tar.gz",
    "linux": "x86_64-unknown-linux-gnu-install_only.tar.gz",
}
_PBS_URL_TEMPLATE = (
    "https://github.com/indygreg/python-build-standalone/releases/download/"
    "{version}/cpython-{version}+{build}-{platform}"
)

# uv standalone binary
_UV_VERSION = "0.6.6"


def _download_plugin_runtime() -> None:
    """Download python-build-standalone and uv binary for plugin venv support.

    Places files in build/plugins_support/python/ and build/plugins_support/uv(.exe).
    These are collected by app.spec during PyInstaller build.
    """
    import urllib.request

    support_dir = PROJECT_ROOT / "build" / "plugins_support"
    support_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download python-build-standalone
    platform_key = sys.platform
    if platform_key not in _PBS_PLATFORM:
        _error(f"Plugin runtime not supported on platform: {sys.platform}")

    pbs_filename = f"cpython-{_PBS_VERSION}+{_PBS_BUILD}-{_PBS_PLATFORM[platform_key]}"
    pbs_url = _PBS_URL_TEMPLATE.format(
        version=_PBS_VERSION,
        build=_PBS_BUILD,
        platform=_PBS_PLATFORM[platform_key],
    )
    pbs_archive = support_dir / pbs_filename
    pbs_target = support_dir / "python"

    if pbs_target.exists():
        _info("[plugins] Using existing bundled Python")
    else:
        _info(f"[plugins] Downloading python-build-standalone {_PBS_VERSION}...")
        _info(f"  URL: {pbs_url}")
        _download_file(pbs_url, pbs_archive)

        _info("[plugins] Extracting Python...")
        import tarfile
        with tarfile.open(pbs_archive, "r:gz") as tf:
            # Extract to a temp dir first, then move the python/ subdir
            tmp_extract = support_dir / "_tmp_extract"
            if tmp_extract.exists():
                shutil.rmtree(tmp_extract)
            tmp_extract.mkdir()
            tf.extractall(tmp_extract)

            # Find the python install directory inside the archive
            extracted_python = None
            for item in tmp_extract.iterdir():
                if item.name.startswith("python"):
                    extracted_python = item
                    break
            if extracted_python is None:
                _error("Could not find python directory in python-build-standalone archive")

            if pbs_target.exists():
                shutil.rmtree(pbs_target)
            shutil.move(str(extracted_python), str(pbs_target))
            shutil.rmtree(tmp_extract)

        # Clean up archive
        pbs_archive.unlink(missing_ok=True)

        # Verify
        py_exe = pbs_target / ("python.exe" if sys.platform == "win32" else "bin" / "python3")
        if py_exe.exists():
            _info(f"[plugins] Bundled Python: {py_exe}")
        else:
            _warn(f"[plugins] Python executable not found at {py_exe}")

    # 2. Download uv
    uv_ext = ".exe" if sys.platform == "win32" else ""
    uv_target = support_dir / f"uv{uv_ext}"

    if uv_target.exists():
        _info("[plugins] Using existing bundled uv")
    else:
        _info(f"[plugins] Downloading uv {_UV_VERSION}...")

        if sys.platform == "win32":
            uv_url = f"https://github.com/astral-sh/uv/releases/download/{_UV_VERSION}/uv-x86_64-pc-windows-msvc.zip"
            uv_archive = support_dir / "uv.zip"
            _download_file(uv_url, uv_archive)
            import zipfile
            with zipfile.ZipFile(uv_archive, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("uv.exe"):
                        with zf.open(name) as src, open(uv_target, "wb") as dst:
                            dst.write(src.read())
                        break
            uv_archive.unlink(missing_ok=True)
        elif sys.platform == "darwin":
            uv_url = f"https://github.com/astral-sh/uv/releases/download/{_UV_VERSION}/uv-aarch64-apple-darwin.tar.gz"
            _download_and_extract_uv_tar(uv_url, uv_target, support_dir)
        else:
            uv_url = f"https://github.com/astral-sh/uv/releases/download/{_UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz"
            _download_and_extract_uv_tar(uv_url, uv_target, support_dir)

        _info(f"[plugins] Bundled uv: {uv_target}")

    # Size summary
    total_size = 0
    for f in support_dir.rglob("*"):
        if f.is_file():
            total_size += f.stat().st_size
    _info(f"[plugins] Plugin runtime total: {total_size / (1024 * 1024):.1f} MB")


def _download_file(url: str, dest: Path) -> None:
    """Download a file with progress display."""
    import urllib.request

    def _on_progress(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            downloaded = block_num * block_size
            pct = min(int(100 * downloaded / total_size), 100)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  {pct}% ({mb:.0f}/{total_mb:.0f} MB)")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, dest, _on_progress)
        print()  # newline after progress
    except Exception as e:
        _error(f"Download failed: {e}\n  URL: {url}")


def _download_and_extract_uv_tar(url: str, uv_target: Path, support_dir: Path) -> None:
    """Download and extract uv from a tar.gz archive."""
    import tarfile

    uv_archive = support_dir / "uv.tar.gz"
    _download_file(url, uv_archive)

    with tarfile.open(uv_archive, "r:gz") as tf:
        for member in tf.getmembers():
            if member.name.endswith("/uv") and not member.isdir():
                # Extract just the uv binary
                with tf.extractfile(member) as src, open(uv_target, "wb") as dst:
                    dst.write(src.read())
                break
    uv_archive.unlink(missing_ok=True)

    # Make executable on Unix
    uv_target.chmod(uv_target.stat().st_mode | 0o755)


# ========== OCR model bundling ==========

def _download_ocr_models() -> list[tuple[str, str]]:
    """Download default OCR models and return datas list for PyInstaller.

    Downloads the same default set as OcrConfig:
      - det: v5/mobile  (ch_PP-OCRv5_det_mobile.onnx)
      - rec: v5/mobile  (ch_PP-OCRv5_rec_mobile.onnx)
      - cls: v5/server  (ch_PP-LCNet_x1_0_textline_ori_cls_server.onnx)

    Also bundles dict files (ppocr_keys_v1.txt, ppocrv5_dict.txt) so
    RapidOCR can find character mappings at runtime.

    Returns:
        List of (model_file_path, "rapidocr/models") tuples for PyInstaller datas.
    """
    _info("[ocr-models] Downloading default OCR models via RapidOCR...")
    _ensure_pyinstaller_in_venv()
    py = _venv_python()

    # Use a small script to trigger RapidOCR auto-download.
    download_script = PROJECT_ROOT / "_tmp_download_ocr.py"
    download_script.write_text(
        "from rapidocr import ModelType, OCRVersion, RapidOCR\n"
        "from rapidocr.main import root_dir\n"
        "import json\n"
        "model_dir = root_dir / 'models'\n"
        "RapidOCR(params={\n"
        "    'Global.model_root_dir': str(model_dir),\n"
        "    'Det.ocr_version': OCRVersion.PPOCRV5,\n"
        "    'Det.model_type': ModelType.MOBILE,\n"
        "    'Rec.ocr_version': OCRVersion.PPOCRV5,\n"
        "    'Rec.model_type': ModelType.MOBILE,\n"
        "    'Cls.ocr_version': OCRVersion.PPOCRV5,\n"
        "    'Cls.model_type': ModelType.SERVER,\n"
        "})\n"
        "# Collect all files in the models directory\n"
        "files = sorted(str(f) for f in model_dir.iterdir() if f.is_file())\n"
        "print(json.dumps(files))\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(py), str(download_script)],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    download_script.unlink(missing_ok=True)

    if result.returncode != 0:
        _error(f"OCR model download failed:\n{result.stderr}")

    import json
    model_files = json.loads(result.stdout.strip().split("\n")[-1])

    # Filter to the specific default model files we want.
    target_files = {
        "ch_PP-OCRv5_det_mobile.onnx",
        "ch_PP-OCRv5_rec_mobile.onnx",
        "ch_PP-LCNet_x1_0_textline_ori_cls_server.onnx",
        "ppocr_keys_v1.txt",
        "ppocrv5_dict.txt",
    }

    datas: list[tuple[str, str]] = []
    for fpath in model_files:
        fname = Path(fpath).name
        if fname in target_files:
            size_mb = Path(fpath).stat().st_size / (1024 * 1024)
            _info(f"  [ocr-models] {fname} ({size_mb:.1f} MB)")
            datas.append((fpath, "rapidocr/models"))

    _info(f"[ocr-models] {len(datas)} file(s) ready for bundling")
    return datas


# ========== model bundling ==========

def _download_build_models(
    model_ids: list[str],
) -> list[tuple[str, str]]:
    """Download models for build-time bundling.

    Args:
        model_ids: List of model IDs from the registry.

    Returns:
        List of (model_dir_path, "models") tuples for PyInstaller datas.
    """
    from py.model_registry import get_model, get_download_url
    from py.model_manager import download_archive, extract_archive, validate_model

    models_dir = PROJECT_ROOT / "_bundled_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    result: list[tuple[str, str]] = []

    for model_id in model_ids:
        entry = get_model(model_id)
        if entry is None:
            from py.model_registry import MODELS
            _error(
                f"Unknown model ID: {model_id}\n"
                "Available models:\n" + "\n".join(
                    f"  {m.model_id}" for m in MODELS
                )
            )
            continue  # unreachable due to _error exit

        url = get_download_url(entry)
        is_vad = entry.model_type == "vad"

        _info(f"[models] Downloading {entry.display_name} ({entry.size_mb}MB)...")

        tmp_archive = models_dir / f"_{model_id}.tmp"

        def _on_progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = int(100 * downloaded / total)
                mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                sys.stdout.write(f"\r  {pct}% ({mb:.0f}/{total_mb:.0f} MB)")
                sys.stdout.flush()

        download_archive(url, tmp_archive, on_progress=_on_progress)
        print()  # newline after progress

        _info(f"[models] Extracting {model_id}...")
        extract_archive(tmp_archive, model_id, models_dir, is_vad=is_vad)
        tmp_archive.unlink(missing_ok=True)

        validation = validate_model(model_id, models_dir)
        if not validation["valid"]:
            _error(f"Model validation failed for {model_id}: {validation.get('missing')}")

        if is_vad:
            result.append((str(models_dir / "silero_vad.onnx"), "models"))
        else:
            result.append((str(models_dir / model_id), f"models/{model_id}"))

        _info(f"[models] Ready: {model_id}")

    return result


if __name__ == "__main__":
    main()
