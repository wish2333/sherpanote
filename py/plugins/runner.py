"""Subprocess runner for plugin backends.

Executes plugin runner scripts in the plugin venv Python via subprocess,
communicating through JSON over stdin/stdout. Progress events are sent
over stderr as JSON lines.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

from py.plugins.paths import get_plugin_venv_python, get_py_package_parent

logger = logging.getLogger(__name__)

# Windows: prevent subprocess calls from flashing a console window.
_SUBPROCESS_FLAGS = 0
if sys.platform == "win32":
    _SUBPROCESS_FLAGS = 0x08000000  # CREATE_NO_WINDOW


class PluginError(Exception):
    """Raised when a plugin subprocess fails."""

    def __init__(
        self,
        message: str,
        traceback: str = "",
        returncode: int = -1,
    ) -> None:
        self.message = message
        self.traceback = traceback
        self.returncode = returncode
        super().__init__(message)


@dataclass(frozen=True)
class RunResult:
    """Result from a plugin subprocess run."""

    success: bool
    data: dict[str, Any] | None = None
    error: str = ""
    traceback: str = ""


def _encode_args(args: dict[str, Any]) -> str:
    """Encode args dict as base64 JSON string for CLI passing."""
    return base64.b64encode(json.dumps(args).encode()).decode()


def _decode_args(encoded: str) -> dict[str, Any]:
    """Decode base64 JSON string back to dict."""
    return json.loads(base64.b64decode(encoded).decode())


def _build_subprocess_env() -> dict[str, str]:
    """Build environment dict for plugin subprocesses.

    Ensures ``PYTHONPATH`` includes the parent of the ``py`` package so
    that ``python -m py.plugins.runners.xxx`` works in the plugin venv.

    On Windows, also disables HuggingFace symlink creation to avoid
    ``WinError 1314`` (privilege required) in packaged apps.
    """
    env = os.environ.copy()
    py_parent = str(get_py_package_parent())
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = py_parent + os.pathsep + existing if existing else py_parent

    if sys.platform == "win32":
        env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    return env


def run(
    plugin_module: str,
    args: dict[str, Any],
    timeout: int = 300,
) -> RunResult:
    """Execute a plugin module in the plugin venv subprocess.

    Args:
        plugin_module: Dotted module path, e.g. "py.plugins.runners.docling_runner".
        args: Keyword arguments passed to the runner script via --json-input.
        timeout: Maximum seconds to wait for completion.

    Returns:
        RunResult with success/data or error/traceback.

    Raises:
        PluginError: On subprocess crash or timeout.
        FileNotFoundError: If plugin venv Python not found.
    """
    venv_python = get_plugin_venv_python()
    if not venv_python.exists():
        raise FileNotFoundError(
            f"Plugin venv not found: {venv_python}. "
            "Install a plugin first via PluginManager.install_package()."
        )

    encoded = _encode_args(args)
    cmd = [
        str(venv_python),
        "-m", plugin_module,
        "--json-input", encoded,
    ]

    logger.debug("Running plugin subprocess: %s", " ".join(cmd))

    env = _build_subprocess_env()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            # Use bytes for stderr to avoid encoding issues on Windows
            encoding="utf-8",
            errors="replace",
            creationflags=_SUBPROCESS_FLAGS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise PluginError(
            message=f"Plugin timed out after {timeout}s",
            traceback="",
            returncode=-1,
        )
    except Exception as exc:
        raise PluginError(
            message=f"Failed to start plugin subprocess: {exc}",
            traceback=str(exc),
            returncode=-1,
        )

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        logger.error("Plugin exited with code %d: %s", proc.returncode, stderr)
        raise PluginError(
            message=f"Plugin exited with code {proc.returncode}",
            traceback=stderr,
            returncode=proc.returncode,
        )

    # Parse stdout as JSON
    stdout = proc.stdout.strip()
    if not stdout:
        raise PluginError(
            message="Plugin produced no output",
            traceback=proc.stderr.strip(),
            returncode=proc.returncode,
        )

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise PluginError(
            message=f"Plugin output is not valid JSON: {exc}",
            traceback=stdout[:500],
            returncode=proc.returncode,
        )

    if not result.get("success", False):
        raise PluginError(
            message=result.get("error", "Unknown plugin error"),
            traceback=result.get("traceback", ""),
            returncode=proc.returncode,
        )

    return RunResult(
        success=True,
        data=result.get("result"),
    )


def run_with_progress(
    plugin_module: str,
    args: dict[str, Any],
    on_progress: Callable[[str], None],
    timeout: int = 600,
) -> RunResult:
    """Execute a plugin module with progress event streaming.

    Progress events arrive on stderr as JSON lines:
    {"type": "progress", "percent": 50, "message": "converting page 3/10"}

    Args:
        plugin_module: Dotted module path.
        args: Keyword arguments for the runner script.
        on_progress: Callback receiving progress message strings.
        timeout: Maximum seconds to wait for completion.

    Returns:
        RunResult with success/data or error/traceback.
    """
    venv_python = get_plugin_venv_python()
    if not venv_python.exists():
        raise FileNotFoundError(
            f"Plugin venv not found: {venv_python}. "
            "Install a plugin first via PluginManager.install_package()."
        )

    encoded = _encode_args(args)
    cmd = [
        str(venv_python),
        "-m", plugin_module,
        "--json-input", encoded,
    ]

    logger.debug("Running plugin subprocess (with progress): %s", " ".join(cmd))

    env = _build_subprocess_env()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_SUBPROCESS_FLAGS,
            env=env,
        )
    except Exception as exc:
        raise PluginError(
            message=f"Failed to start plugin subprocess: {exc}",
            traceback=str(exc),
            returncode=-1,
        )

    # Read stderr lines for progress while waiting for stdout
    stderr_lines: list[str] = []
    try:
        # communicate() reads all stdout/stderr without deadlock
        stdout_data, stderr_data = proc.communicate(timeout=timeout)
        stderr_lines = stderr_data.splitlines()
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise PluginError(
            message=f"Plugin timed out after {timeout}s",
            traceback="",
            returncode=-1,
        )

    if proc.returncode != 0:
        stderr_combined = "\n".join(stderr_lines)
        logger.error("Plugin exited with code %d: %s", proc.returncode, stderr_combined)
        raise PluginError(
            message=f"Plugin exited with code {proc.returncode}",
            traceback=stderr_combined,
            returncode=proc.returncode,
        )

    # Parse progress events from stderr
    for line in stderr_lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "progress":
                msg = event.get("message", f"{event.get('percent', 0)}%")
                on_progress(msg)
        except json.JSONDecodeError:
            # Non-JSON stderr lines are informational, forward as progress
            on_progress(line)

    # Parse stdout as JSON
    stdout = stdout_data.strip()
    if not stdout:
        raise PluginError(
            message="Plugin produced no output",
            traceback="\n".join(stderr_lines),
            returncode=proc.returncode,
        )

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise PluginError(
            message=f"Plugin output is not valid JSON: {exc}",
            traceback=stdout[:500],
            returncode=proc.returncode,
        )

    if not result.get("success", False):
        raise PluginError(
            message=result.get("error", "Unknown plugin error"),
            traceback=result.get("traceback", ""),
            returncode=proc.returncode,
        )

    return RunResult(
        success=True,
        data=result.get("result"),
    )
