"""Resolve paths for bundled Python, uv, and plugin virtual environment.

Handles two modes:
- Frozen (PyInstaller): paths relative to the executable directory.
- Development: falls back to system Python and uv.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_base_dir() -> Path:
    """Return the application base directory.

    In frozen mode this is the directory containing the executable.
    In development this is the project root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_bundled_python() -> Path:
    """Return path to the bundled Python executable.

    In frozen mode: {base_dir}/python/python.exe (Windows) or python (Unix).
    In development: sys.executable (system Python).
    """
    base = _get_base_dir()
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            python = base / "python" / "python.exe"
        else:
            python = base / "python" / "bin" / "python3"
        if python.exists():
            return python
        logger.warning("Bundled Python not found at %s, falling back to sys.executable", python)
    return Path(sys.executable).resolve()


def get_bundled_uv() -> Path:
    """Return path to the bundled uv binary.

    In frozen mode: {base_dir}/uv.exe (Windows) or uv (Unix).
    In development: uses shutil.which to find system uv.
    """
    base = _get_base_dir()
    if getattr(sys, "frozen", False):
        ext = ".exe" if sys.platform == "win32" else ""
        uv = base / f"uv{ext}"
        if uv.exists():
            return uv
        logger.warning("Bundled uv not found at %s, falling back to system uv", uv)
    system_uv = shutil.which("uv")
    if system_uv:
        return Path(system_uv).resolve()
    raise FileNotFoundError("uv not found. Install uv or run from bundled application.")


def get_plugin_base_dir() -> Path:
    """Return the plugin data directory.

    In frozen mode: {base_dir}/data/plugins/
    In development: {project_root}/.plugin_dev/
    """
    base = _get_base_dir()
    if getattr(sys, "frozen", False):
        return base / "data" / "plugins"
    return base / ".plugin_dev"


def get_plugin_venv_dir() -> Path:
    """Return the plugin virtual environment directory."""
    return get_plugin_base_dir() / ".venv"


def get_plugin_venv_python() -> Path:
    """Return the Python executable inside the plugin venv.

    The venv may not exist yet -- callers should check before using.
    """
    venv_dir = get_plugin_venv_dir()
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"
