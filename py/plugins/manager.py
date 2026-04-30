"""Plugin virtual environment lifecycle management.

Creates and manages a shared plugin venv using the bundled Python.
Uses bundled uv for package installation/removal within the venv.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from py.plugins.paths import (
    get_bundled_python,
    get_bundled_uv,
    get_plugin_venv_dir,
    get_plugin_venv_python,
)

logger = logging.getLogger(__name__)

# Packages managed by the plugin system (version-pinned)
DOCLING_PACKAGE = "docling==2.92.0"
OPENDATA_PACKAGE = "opendataloader-pdf==2.4.0"

# Map display names to install names
PACKAGE_NAMES: dict[str, str] = {
    "docling": DOCLING_PACKAGE,
    "opendataloader": OPENDATA_PACKAGE,
}


@dataclass(frozen=True)
class PackageStatus:
    """Status of an optional plugin package."""

    name: str
    installed: bool
    version: str | None = None


class PluginManager:
    """Manages the plugin virtual environment and optional backend packages.

    All operations use the bundled Python and uv binaries.
    In development mode, falls back to system Python and uv.
    """

    def __init__(self) -> None:
        self._uv_path: str | None = None
        self._python_path: str | None = None

    @property
    def uv_path(self) -> str:
        """Cached path to uv binary."""
        if self._uv_path is None:
            self._uv_path = str(get_bundled_uv())
        return self._uv_path

    @property
    def python_path(self) -> str:
        """Cached path to bundled Python."""
        if self._python_path is None:
            self._python_path = str(get_bundled_python())
        return self._python_path

    def ensure_venv(self) -> str:
        """Ensure the plugin venv exists, creating it if necessary.

        Returns:
            Path to the venv Python executable.
        """
        venv_python = str(get_plugin_venv_python())
        venv_dir = get_plugin_venv_dir()

        # Check marker file to verify venv is valid
        marker = venv_dir / ".venv_valid"
        if marker.exists():
            return venv_python

        # Create venv
        logger.info("Creating plugin venv at %s", venv_dir)
        venv_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                [self.python_path, "-m", "venv", str(venv_dir)],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timed out creating plugin venv")
        except Exception as exc:
            raise RuntimeError(f"Failed to create plugin venv: {exc}")

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create plugin venv: {result.stderr.strip()}"
            )

        # Write marker file
        marker.touch()

        # Install uv into the venv for faster pip operations
        logger.info("Installing uv into plugin venv")
        try:
            subprocess.run(
                [venv_python, "-m", "ensurepip", "--upgrade"],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            subprocess.run(
                [venv_python, "-m", "pip", "install", "uv", "--quiet"],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            logger.warning("Could not install uv in plugin venv: %s", exc)

        logger.info("Plugin venv created: %s", venv_python)
        return venv_python

    def is_venv_ready(self) -> bool:
        """Check if the plugin venv exists and is valid."""
        venv_python = get_plugin_venv_python()
        marker = get_plugin_venv_dir() / ".venv_valid"
        return venv_python.exists() and marker.exists()

    def is_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed in the plugin venv.

        Args:
            package_name: Pip package name (e.g. "docling").
        """
        if not self.is_venv_ready():
            return False
        return self.get_installed_version(package_name) is not None

    def get_installed_version(self, package_name: str) -> str | None:
        """Get installed version of a package, or None if not installed.

        Uses uv pip show for fast version lookup.
        """
        if not self.is_venv_ready():
            return None

        try:
            result = subprocess.run(
                [self.uv_path, "pip", "show", package_name,
                 "--python", str(get_plugin_venv_python())],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                return None
            # Parse "Version: x.y.z" from pip show output
            for line in result.stdout.splitlines():
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
            return None
        except Exception as exc:
            logger.debug("Could not check package version: %s: %s", package_name, exc)
            return None

    def install_package(
        self,
        package_name: str,
        on_output: Callable[[str], None] | None = None,
        timeout: int = 600,
    ) -> dict[str, Any]:
        """Install a package into the plugin venv using uv.

        Args:
            package_name: Pip package name.
            on_output: Optional callback receiving output lines.
            timeout: Maximum seconds for installation.

        Returns:
            {"success": True} or {"success": False, "error": str}.
        """
        venv_python = str(self.ensure_venv())

        cmd = [
            self.uv_path,
            "pip", "install", package_name,
            "--python", venv_python,
        ]

        logger.info("Installing plugin package: %s", package_name)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            # Stream output line by line for real-time progress
            stdout_lines: list[str] = []
            for line in proc.stdout:
                line = line.rstrip()
                stdout_lines.append(line)
                if on_output and line.strip():
                    on_output(line.strip())

            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            error_msg = f"Installation timed out after {timeout}s"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as exc:
            error_msg = f"Failed to install {package_name}: {exc}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        if proc.returncode != 0:
            error_msg = f"Installation failed (exit code {proc.returncode}): {''.join(stdout_lines[-10:])}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        version = self.get_installed_version(package_name)
        logger.info("Installed %s version %s", package_name, version)
        return {"success": True, "version": version}

    def uninstall_package(self, package_name: str) -> dict[str, Any]:
        """Uninstall a package from the plugin venv.

        Returns:
            {"success": True} or {"success": False, "error": str}.
        """
        if not self.is_venv_ready():
            return {"success": True, "message": "Not installed (no venv)"}

        cmd = [
            self.uv_path, "pip", "uninstall", package_name,
            "--python", str(get_plugin_venv_python()),
        ]

        logger.info("Uninstalling plugin package: %s", package_name)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip()}

        return {"success": True}

    def destroy_venv(self) -> dict[str, Any]:
        """Remove the entire plugin venv directory.

        Returns:
            {"success": True} or {"success": False, "error": str}.
        """
        venv_dir = get_plugin_venv_dir()
        if not venv_dir.exists():
            return {"success": True, "message": "No venv to remove"}

        try:
            import shutil
            shutil.rmtree(venv_dir)
            logger.info("Plugin venv destroyed: %s", venv_dir)
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get_venv_size_mb(self) -> float:
        """Calculate total size of the plugin venv in MB."""
        venv_dir = get_plugin_venv_dir()
        if not venv_dir.exists():
            return 0.0
        total = 0
        for root, _dirs, files in os.walk(venv_dir):
            for f in files:
                path = root + os.sep + f
                try:
                    total += os.path.getsize(path)
                except OSError:
                    pass
        return total / (1024 * 1024)

    def get_all_status(self) -> dict[str, PackageStatus]:
        """Return installation status for all known plugin packages."""
        statuses: dict[str, PackageStatus] = {}
        for display_name, pip_name in PACKAGE_NAMES.items():
            version = self.get_installed_version(pip_name)
            statuses[display_name] = PackageStatus(
                name=display_name,
                installed=version is not None,
                version=version,
            )
        return statuses
