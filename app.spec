# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# PyInstaller spec for PyWebVue desktop applications
# ============================================================
#
# Usage:
#   pyinstaller --clean app.spec       onedir build (folder + exe)
#   uv run build.py                    onedir build (same as above)
#   uv run build.py --onefile          onefile build (single exe)
#
# ---------- USER CONFIGURATION ----------
# The sections marked [MODIFY] are where you should customize
# for your own project. Everything else usually works as-is.
# =============================================


import sys
from pathlib import Path

project_root = Path(SPECPATH)


# ========== [MODIFY] Entry point ==========
# Change this to your main Python script path.
# Default: main.py (at project root)
ENTRY_SCRIPT = str(project_root / "main.py")


# ========== [MODIFY] Output name ==========
# The name of the generated executable (without extension).
APP_NAME = "SherpaNote"


# ========== [MODIFY] Frontend assets ==========
# How to bundle your frontend:
#
#   Standard: bundle the Vite build output directory
#     datas = [(str(project_root / "frontend_dist"), "frontend_dist")]
#
#   Custom: bundle your own directory
#     datas = [(str(project_root / "my_dist"), "my_dist")]
#
# Build frontend first:  cd frontend && npm run build
# Output goes to:        frontend_dist/
_frontend_dist = project_root / "frontend_dist"
_py_package = project_root / "py"
datas = [
    (str(_frontend_dist), "frontend_dist"),
    (str(_py_package), "py"),
]


# ========== [MODIFY] Icon ==========
# Path to your .ico (Windows) or .icns (macOS) icon file.
# Set to None to use the default icon.
ICON = None  # Example: str(project_root / "assets" / "icon.ico")


# ========== [MODIFY] Hidden imports ==========
# If you import additional Python packages in your code,
# add them here so PyInstaller can find them.
hiddenimports = [
    "pywebvue",
    "pywebvue.app",
    "pywebvue.bridge",
    "openai",
    "docx",
    "sherpa_onnx",
    "py",
    "py.config",
    "py.storage",
    "py.asr",
    "py.llm",
    "py.io",
    "py.model_manager",
    "py.model_registry",
    "py.gpu_detect",
    "py.ocr",
    # rapidocr - lazy imported by py/ocr.py, PyInstaller can't detect them
    "rapidocr",
    "rapidocr.main",
    "rapidocr.config",
    "rapidocr.inference_engine",
    "rapidocr.inference_engine.main",
    "rapidocr.inference_engine.onnxruntime",
    "rapidocr.utils",
    "rapidocr.utils.download_models",
    "rapidocr.utils.load_image",
    "rapidocr.ch_ppocr_det",
    "rapidocr.ch_ppocr_rec",
    "rapidocr.ch_ppocr_cls",
    "rapidocr.cal_rec_boxes",
    # rapidocr transitive deps
    "onnxruntime",
    "shapely",
    # rapidocr brings in cv2 (opencv-python-headless)
    "cv2",
    # document extraction backends
    "markitdown",
    "pdfplumber",
    "pypdfium2",
    "PIL",
    # plugin subsystem
    "py.plugins",
    "py.plugins.paths",
    "py.plugins.manager",
    "py.plugins.runner",
    "py.plugins.java_detect",
    "py.plugins.runners",
    "py.plugins.runners.docling_runner",
    "py.plugins.runners.opendata_runner",
]


# ========== [MODIFY] GUI framework excludes ==========
# pywebview auto-selects the best engine per platform:
#   Windows  -> EdgeWebView2 (or CEF if no Edge)
#   macOS    -> Cocoa WebKit
#   Linux    -> GTK WebKit
#
# Exclude GUI frameworks you are NOT using to reduce bundle size.
# Only modify this if you know what you are doing.
EXCLUDES_WIN32 = ["PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter"]
EXCLUDES_LINUX = ["PyQt5", "PyQt6", "PySide2", "PySide6"]
EXCLUDES_DARWIN = ["PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter"]


# ========== Usually no need to modify below ==========

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# sherpa-onnx bundles CUDA provider DLLs in its lib/ directory.
# These are loaded dynamically by onnxruntime at runtime, so
# PyInstaller cannot detect them automatically. Force collection.
# Target: sherpa_onnx/lib so they sit next to onnxruntime.dll.
import sherpa_onnx as _so  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_lib = _Path(_so.__file__).parent.joinpath("lib")
_dlls = list(_lib.glob("*.dll"))
print(f"[DEBUG] sherpa_onnx lib={_lib}, DLLs={[f.name for f in _dlls]}")
for _f in _dlls:
    a.binaries.append((str(_Path("sherpa_onnx") / "lib" / _f.name), str(_f), "BINARY"))

# rapidocr: collect config YAML and default model files.
# These are data files that PyInstaller doesn't auto-detect.
import rapidocr as _ro  # noqa: E402
_ro_pkg = _Path(_ro.__file__).parent
# config.yaml and default_models.yaml are needed for model resolution
for _cfg_name in ("config.yaml", "default_models.yaml"):
    _cfg_path = _ro_pkg / _cfg_name
    if _cfg_path.exists():
        a.datas.append((str(_Path("rapidocr") / _cfg_name), str(_cfg_path), "DATA"))

# cv2 data files (haarcascades, etc.) are collected automatically
# by PyInstaller through hiddenimports -- no manual collection needed.

# Plugin system: collect bundled Python and uv if available.
# These are downloaded by build.py --with-plugins and placed in build/plugins_support/.
_plugins_support = project_root / "build" / "plugins_support"
_bundled_python_dir = _plugins_support / "python"
_bundled_uv = _plugins_support / ("uv.exe" if sys.platform == "win32" else "uv")
if _bundled_python_dir.exists():
    # Collect the entire bundled Python directory tree
    # Use a.datas (not a.binaries) so files go to dist root, not _internal/
    for _item in _bundled_python_dir.rglob("*"):
        if _item.is_file():
            _rel = _item.relative_to(_bundled_python_dir)
            a.datas.append((str(_Path("python") / _rel), str(_item), "DATA"))
    print(f"[DEBUG] Bundled Python: {_bundled_python_dir}")
if _bundled_uv.exists():
    a.datas.append((str(_Path(_bundled_uv.name)), str(_bundled_uv), "DATA"))
    print(f"[DEBUG] Bundled uv: {_bundled_uv}")

if sys.platform == "win32":
    a.excludes += EXCLUDES_WIN32
elif sys.platform == "linux":
    a.excludes += EXCLUDES_LINUX
elif sys.platform == "darwin":
    a.excludes += EXCLUDES_DARWIN

pyz = PYZ(a.pure)

# macOS: add microphone permission so WKWebView exposes navigator.mediaDevices
_DARWIN_INFO_PLIST = {
    "NSMicrophoneUsageDescription": "SherpaNote needs microphone access for speech recognition.",
    "LSMultipleInstancesProhibited": True,
}

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

# On macOS, wrap the collect output in a .app bundle so that Info.plist
# (including NSMicrophoneUsageDescription) is picked up by WKWebView.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        info_plist=_DARWIN_INFO_PLIST,
        icon=ICON,
    )
