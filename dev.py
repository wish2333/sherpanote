# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PyWebVue one-click development startup script.

Cross-platform (Windows / macOS / Linux).

============================================================
Usage
============================================================

    uv run dev.py              Start Vite dev server + app (default)
    uv run dev.py --no-vite    Load frontend_dist/ from disk (no Vite)
    uv run dev.py --setup      Only install dependencies

    uv run dev.py plugin status          Show plugin & backend status
    uv run dev.py plugin install docling Install a plugin backend
    uv run dev.py plugin uninstall docling Uninstall a plugin backend
    uv run dev.py plugin destroy         Destroy the entire plugin venv
    uv run dev.py plugin detect-java     Detect Java 11+ runtime
    uv run dev.py plugin test FILE       Test document extraction

============================================================
How it works
============================================================

    1. uv sync                        Install Python dependencies
    2. npm/bun install                 Install frontend dependencies
    3. Start Vite dev server           Background process at :5173
    4. Start main.py                   Launch the pywebview window
    5. On exit (Ctrl+C or window close): stop all background processes

============================================================
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
_bg_procs: list[subprocess.Popen] = []

DEFAULT_FRONTEND_DIR = PROJECT_ROOT / "frontend"


# ================================================================
# Helpers
# ================================================================

def _info(msg: str) -> None:
    print(f"[INFO] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


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


def _spawn_bg(cmd: list[str], cwd: Path | None = None) -> None:
    """Start a background process (registered for cleanup on exit)."""
    _info(f"  $ {' '.join(cmd)}  [background]")
    kw: dict = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(cmd, cwd=cwd, **kw)
    _bg_procs.append(proc)


def _kill_bg() -> None:
    """Terminate all background processes."""
    for proc in _bg_procs:
        if proc.poll() is not None:
            continue
        try:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
            proc.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
            proc.kill()
    _bg_procs.clear()


# ================================================================
# Setup
# ================================================================

def _setup_python() -> None:
    """Install Python dependencies via uv."""
    uv = _find_cmd("uv")
    if uv is None:
        _error("uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/")
    _info("[1] Installing Python dependencies...")
    _run([uv, "sync"], cwd=PROJECT_ROOT)


def _setup_frontend(frontend_dir: Path) -> str:
    """Install frontend dependencies. Returns the package manager name."""
    pm = _find_cmd("bun", "npm", "yarn")
    if pm is None:
        _error("No package manager found. Install bun/npm/yarn first.")
    _info("[2] Installing frontend dependencies...")
    _run([pm, "install"], cwd=frontend_dir)
    return pm


# ================================================================
# Start
# ================================================================

def _start_vite(frontend_dir: Path, pm: str) -> None:
    """Start Vite dev server in background and wait for it to be ready."""
    _info(f"[3] Starting Vite dev server ({pm})...")
    _spawn_bg([pm, "run", "dev"], cwd=frontend_dir)
    import time
    time.sleep(2)
    _info("    Vite should be running at http://localhost:5173")


def _start_app(env_extra: dict[str, str] | None = None) -> None:
    """Start main.py via uv run to use the project .venv."""
    uv = _find_cmd("uv")
    if uv is None:
        _error("uv not found.")

    main_py = PROJECT_ROOT / "main.py"
    if not main_py.exists():
        _error(f"Entry script not found: {main_py}")

    env = {**os.environ}
    if env_extra:
        env.update(env_extra)

    cmd = [uv, "run", str(main_py)]
    _info(f"Starting app: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
    except KeyboardInterrupt:
        pass


# ================================================================
# Plugin management
# ================================================================

def _cmd_plugin_status(_args: argparse.Namespace) -> None:
    """Show plugin system status and backend availability."""
    from py.plugins.paths import (
        get_bundled_python,
        get_bundled_uv,
        get_plugin_venv_dir,
        get_plugin_venv_python,
    )
    from py.plugins.manager import PluginManager

    print("=" * 50)
    print("  Plugin System Status")
    print("=" * 50)

    # Runtime environment
    is_frozen = getattr(sys, "frozen", False)
    mode = "PyInstaller bundle" if is_frozen else "Development"
    print(f"\n  Mode:             {mode}")
    print(f"  Python:           {sys.executable} ({sys.version.split()[0]})")

    python = get_bundled_python()
    print(f"  Bundled Python:   {python}")
    try:
        uv = get_bundled_uv()
        print(f"  Bundled uv:       {uv}")
    except FileNotFoundError as e:
        print(f"  Bundled uv:       NOT FOUND ({e})")

    venv_dir = get_plugin_venv_dir()
    venv_python = get_plugin_venv_python()
    print(f"  Plugin venv dir:  {venv_dir}")
    print(f"  Plugin venv py:   {venv_python}")
    print(f"  Venv exists:      {venv_python.exists()}")

    # Package status
    pm = PluginManager()
    print()
    statuses = pm.get_all_status()
    for name, status in statuses.items():
        if status.installed:
            print(f"  {name:20s} INSTALLED (v{status.version})")
        else:
            print(f"  {name:20s} not installed")

    # Venv size
    if pm.is_venv_ready():
        size_mb = pm.get_venv_size_mb()
        print(f"\n  Venv size:        {size_mb:.1f} MB")

    # Java detection
    print()
    from py.plugins.java_detect import detect_java
    java = detect_java()
    if java.found:
        print(f"  Java:             FOUND ({java.version}) at {java.path}")
    else:
        print(f"  Java:             NOT FOUND")
        print(f"                    {java.error}")

    # Decision tree summary
    print()
    print("-" * 50)
    print("  Decision tree (current config):")
    from py.config import ConfigStore
    try:
        config = ConfigStore().load()
        print(f"    text_pdf_engine:   {config.document.text_pdf_engine}")
        print(f"    scan_pdf_engine:   {config.document.scan_pdf_engine}")
    except Exception as exc:
        print(f"    (config load failed: {exc})")
    print("=" * 50)


def _cmd_plugin_install(args: argparse.Namespace) -> None:
    """Install a plugin backend into the plugin venv."""
    from py.plugins.manager import PluginManager, PACKAGE_NAMES

    name = args.package
    pip_name = PACKAGE_NAMES.get(name, name)

    print(f"Installing {name} (pip: {pip_name})...")
    pm = PluginManager()

    def on_output(line: str) -> None:
        print(f"  {line}")

    result = pm.install_package(pip_name, on_output=on_output)

    if result["success"]:
        print(f"Done. Version: {result.get('version', '?')}")
    else:
        _error(f"Install failed: {result.get('error')}")


def _cmd_plugin_uninstall(args: argparse.Namespace) -> None:
    """Uninstall a plugin backend from the plugin venv."""
    from py.plugins.manager import PluginManager, PACKAGE_NAMES

    name = args.package
    pip_name = PACKAGE_NAMES.get(name, name)

    print(f"Uninstalling {name} (pip: {pip_name})...")
    pm = PluginManager()
    result = pm.uninstall_package(pip_name)

    if result["success"]:
        print("Done.")
    else:
        _error(f"Uninstall failed: {result.get('error')}")


def _cmd_plugin_destroy(_args: argparse.Namespace) -> None:
    """Destroy the entire plugin venv."""
    from py.plugins.manager import PluginManager

    pm = PluginManager()
    if pm.is_venv_ready():
        size_mb = pm.get_venv_size_mb()
        print(f"Destroying plugin venv ({size_mb:.1f} MB)...")
    else:
        print("No plugin venv to destroy.")
        return

    result = pm.destroy_venv()
    if result["success"]:
        print("Done.")
    else:
        _error(f"Destroy failed: {result.get('error')}")


def _cmd_plugin_detect_java(_args: argparse.Namespace) -> None:
    """Detect Java 11+ runtime."""
    from py.plugins.java_detect import detect_java

    print("Detecting Java 11+...")
    result = detect_java()
    if result.found:
        print(f"  Found: Java {result.version} at {result.path}")
    else:
        print(f"  Not found: {result.error}")


def _cmd_plugin_test(args: argparse.Namespace) -> None:
    """Test document extraction on a file."""
    file_path = args.file
    if not Path(file_path).exists():
        _error(f"File not found: {file_path}")

    from py.text_detector import classify_file
    from py.plugins.manager import PluginManager

    info = classify_file(file_path)
    print(f"  File:     {file_path}")
    print(f"  Type:     {info.category}")
    print(f"  Size:     {Path(file_path).stat().st_size / 1024:.1f} KB")

    # Show available backends
    pm = PluginManager()
    statuses = pm.get_all_status()
    available = {n: s.installed for n, s in statuses.items() if s.installed}
    print(f"  Backends: ppocr, markitdown", end="")
    if available:
        print(f", {', '.join(available)}", end="")
    print()

    # Build extractor
    from py.ocr import OcrEngine
    from py.document_extractor import DocumentExtractor
    from py.config import ConfigStore

    engine = OcrEngine()
    doc_config = None
    try:
        config = ConfigStore().load()
        doc_config = config.document
    except Exception:
        pass

    extractor = DocumentExtractor(
        ocr_engine=engine,
        plugin_manager=pm,
        doc_config=doc_config,
    )

    print(f"\n  Extracting with engine: {doc_config.text_pdf_engine if doc_config else 'default'}")
    print("  ---")

    try:
        doc = extractor.extract(file_path)
        lines = doc.markdown.splitlines()
        preview = "\n  ".join(lines[:20])
        if len(lines) > 20:
            preview += "\n  ..."
        print(f"  Backend:  {doc.backend}")
        print(f"  Pages:    {doc.metadata.get('page_count', '?')}")
        print(f"  Chars:    {len(doc.markdown)}")
        print(f"  Preview:\n  {preview}")
    except Exception as exc:
        _error(f"Extraction failed: {exc}")


# ================================================================
# Signal handling
# ================================================================

def _on_signal(signum: int, _frame) -> None:
    _info("\nShutting down...")
    _kill_bg()
    sys.exit(0)


# ================================================================
# Main
# ================================================================

def main() -> None:
    ap = argparse.ArgumentParser(
        description="PyWebVue one-click dev startup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  uv run dev.py                           Start Vite + app (default)
  uv run dev.py --no-vite                  Load from disk (production preview)
  uv run dev.py --frontend-dir ./my-app    Custom Vue project path
  uv run dev.py --setup                    Only install dependencies
  uv run dev.py plugin status              Show plugin system status
  uv run dev.py plugin install docling     Install docling plugin
  uv run dev.py plugin test report.pdf     Test extraction on a file
""",
    )
    ap.add_argument("--no-vite", action="store_true",
                    help="Skip Vite, load frontend from disk")
    ap.add_argument("--setup", action="store_true",
                    help="Only install dependencies, then exit")
    ap.add_argument("--frontend-dir", type=str, default=None,
                    help="Vue project root with package.json (default: ./frontend)")

    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    # plugin subcommand
    plugin_ap = sub.add_parser("plugin", help="Plugin system management")
    plugin_sub = plugin_ap.add_subparsers(dest="plugin_cmd", metavar="ACTION")

    plugin_sub.add_parser("status", help="Show plugin system status")
    plugin_sub.add_parser("destroy", help="Destroy the plugin venv")
    plugin_sub.add_parser("detect-java", help="Detect Java 11+ runtime")

    p_install = plugin_sub.add_parser("install", help="Install a plugin backend")
    p_install.add_argument("package", choices=["docling", "opendataloader"],
                           help="Plugin backend to install")

    p_uninstall = plugin_sub.add_parser("uninstall", help="Uninstall a plugin backend")
    p_uninstall.add_argument("package", choices=["docling", "opendataloader"],
                             help="Plugin backend to uninstall")

    p_test = plugin_sub.add_parser("test", help="Test document extraction")
    p_test.add_argument("file", help="Path to a file to extract")

    args = ap.parse_args()

    # Plugin subcommand: skip normal startup flow
    if args.command == "plugin":
        if args.plugin_cmd == "status":
            _cmd_plugin_status(args)
        elif args.plugin_cmd == "install":
            _cmd_plugin_install(args)
        elif args.plugin_cmd == "uninstall":
            _cmd_plugin_uninstall(args)
        elif args.plugin_cmd == "destroy":
            _cmd_plugin_destroy(args)
        elif args.plugin_cmd == "detect-java":
            _cmd_plugin_detect_java(args)
        elif args.plugin_cmd == "test":
            _cmd_plugin_test(args)
        else:
            plugin_ap.print_help()
        return

    # Graceful shutdown on Ctrl+C
    signal.signal(signal.SIGINT, _on_signal)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _on_signal)

    # --- Step 1: Python deps ---
    _setup_python()

    # --- Step 2: Frontend deps ---
    frontend_dir = (
        Path(args.frontend_dir) if args.frontend_dir
        else DEFAULT_FRONTEND_DIR
    )
    pm: str | None = None
    if not args.no_vite:
        if not (frontend_dir / "package.json").exists():
            _error(f"No package.json in {frontend_dir}. "
                   f"Use --frontend-dir to point to your Vue project.")
        pm = _setup_frontend(frontend_dir)

    if args.setup:
        _info("Setup complete.")
        return

    # --- Step 3: Vite dev server (background) ---
    if not args.no_vite and pm:
        _start_vite(frontend_dir, pm)

    # --- Step 4: Start the app ---
    try:
        _start_app()
    finally:
        _kill_bg()


if __name__ == "__main__":
    main()
