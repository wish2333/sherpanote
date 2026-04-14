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
) -> None:
    """Build desktop app as a directory (uses app.spec directly).

    Args:
        bundled_model_dirs: Optional model datas to inject into app.spec.
    """
    uv = _find_cmd("uv")
    if uv is None:
        _error("uv not found.")

    spec = PROJECT_ROOT / "app.spec"
    if not spec.exists():
        _error(
            f"Spec file not found: {spec}\n"
            "Make sure app.spec exists in the project root."
        )

    # If models are being bundled, generate a temporary spec with extra datas.
    if bundled_model_dirs:
        _info(f"Bundling {len(bundled_model_dirs)} model(s) into onedir build")
        spec = _inject_model_datas(spec, bundled_model_dirs)

    cmd = [uv, "run", "--", "pyinstaller", "--clean", "--noconfirm", str(spec)]
    _info(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    # Clean up temp spec if generated.
    if bundled_model_dirs and spec.name.startswith("_build_"):
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

    # Find the datas = [...] block and append model entries.
    model_lines = "\n".join(
        f'    (r"{path}", "{dest}"),'
        for path, dest in model_dirs
    )

    # Insert before the closing bracket of datas = [...]
    import re
    content = re.sub(
        r"(datas\s*=\s*\[)",
        f"\\1\n{model_lines}",
        content,
        count=1,
    )

    tmp_spec = PROJECT_ROOT / "_build_onedir_with_models.spec"
    tmp_spec.write_text(content, encoding="utf-8")
    return tmp_spec


# ========== desktop: onefile ==========

def _build_onefile() -> None:
    """Build desktop app as a single executable.

    Generates a temporary onefile spec based on app.spec config,
    then runs PyInstaller. The temp spec is deleted after build.
    """
    uv = _find_cmd("uv")
    if uv is None:
        _error("uv not found.")

    spec_content = _generate_onefile_spec()
    tmp_spec = PROJECT_ROOT / "_build_onefile.spec"
    tmp_spec.write_text(spec_content, encoding="utf-8")

    cmd = [uv, "run", "--", "pyinstaller", "--clean", "--noconfirm", str(tmp_spec)]
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

    _build_frontend()

    # Download models if requested.
    bundled_model_dirs: list[tuple[str, str]] = []
    if args.with_models:
        model_ids = [m.strip() for m in args.with_models.split(",")]
        bundled_model_dirs = _download_build_models(model_ids)

    _build_desktop(onefile=args.onefile, bundled_model_dirs=bundled_model_dirs, cuda=args.cuda)


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
) -> None:
    if cuda:
        _info("=== CUDA GPU build (NVIDIA) ===")
        _info("Note: This build requires the sherpa-onnx +cuda wheel variant.")
        _info("      The resulting app will be larger (~200MB+ vs ~50MB CPU-only).")
        _info("      Users must have an NVIDIA GPU with CUDA Toolkit installed.")
    if onefile:
        _build_onefile()
    else:
        _build_onedir(bundled_model_dirs=bundled_model_dirs)


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
