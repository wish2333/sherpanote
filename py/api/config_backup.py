"""Config and backup API mixin.

Provides configuration management, backup/restore,
file picker dialogs, and system utility methods.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from pywebvue import expose
from py.api.base import ApiBase
from py.config import AppConfig
from py import backup as _backup

logger = logging.getLogger(__name__)


class ConfigBackupMixin(ApiBase):
    """Config, backup, and utility @expose methods."""

    # ---- Config ----

    @expose
    def get_config(self) -> dict:
        """Get current application configuration."""
        return {"success": True, "data": self._api._config.to_dict()}

    @expose
    def update_config(self, config: dict) -> dict:
        """Update and persist application configuration."""
        self._api._config = AppConfig.from_dict(config)
        self._api._config_store.save(self._api._config)
        # Re-create AI processor with new config.
        self._api._ai = None
        # Re-create ASR if model_dir changed.
        self._api._asr = None
        # Re-create OCR engine if config changed.
        self._api._ocr_engine = None
        self._api._document_extractor = None
        self._api._plugin_manager = None
        return {"success": True, "data": self._api._config.to_dict()}

    # ---- Backup / Restore ----

    @expose
    def export_backup(self, path: str, options: dict) -> dict:
        """Export application data to a ZIP backup file."""
        try:
            output = _backup.export_backup(
                path,
                include_config=options.get("include_config", True),
                include_presets=options.get("include_presets", True),
                include_records=options.get("include_records", True),
                include_versions=options.get("include_versions", True),
                include_audio=options.get("include_audio", False),
            )
            return {"success": True, "data": {"path": output}}
        except Exception as e:
            logger.exception("export_backup failed")
            return {"success": False, "error": str(e)}

    @expose
    def import_backup(self, path: str) -> dict:
        """Import data from a ZIP backup file. Replaces existing data."""
        try:
            summary = _backup.import_backup(path)
            # Reload config to pick up imported settings.
            self._api._config = self._api._config_store.load()
            self._api._ai = None
            self._api._asr = None
            return {"success": True, "data": summary}
        except Exception as e:
            logger.exception("import_backup failed")
            return {"success": False, "error": str(e)}

    # ---- File Pickers ----

    @expose
    def pick_directory(self) -> dict:
        """Open a folder picker dialog and return the selected path."""
        try:
            import webview
            try:
                dialog_type = webview.FileDialog.FOLDER
            except AttributeError:
                dialog_type = webview.FOLDER_DIALOG
            result = self._window.create_file_dialog(dialog_type=dialog_type)
            if result:
                return {"success": True, "data": {"path": result[0]}}
            return {"success": False, "error": "No folder selected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def pick_audio_file(self) -> dict:
        """Open a native file picker for audio files and return the full path."""
        try:
            import webview
            audio_extensions = ("MP3 Audio (*.mp3)", "WAV Audio (*.wav)",
                                "M4A Audio (*.m4a)", "FLAC Audio (*.flac)",
                                "OGG Audio (*.ogg)", "All Files (*.*)")
            try:
                dialog_type = webview.FileDialog.OPEN
            except AttributeError:
                dialog_type = webview.OPEN_DIALOG
            result = self._window.create_file_dialog(
                dialog_type=dialog_type,
                file_types=audio_extensions,
            )
            if result:
                return {"success": True, "data": result}
            return {"success": False, "error": "No file selected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def pick_file(self, file_types: tuple[str, ...] = ("All Files (*.*)",)) -> dict:
        """Open a native file picker dialog and return the selected path."""
        try:
            import webview
            try:
                dialog_type = webview.FileDialog.OPEN
            except AttributeError:
                dialog_type = webview.OPEN_DIALOG
            result = self._window.create_file_dialog(
                dialog_type=dialog_type,
                file_types=file_types,
            )
            if result:
                return {"success": True, "data": {"path": result[0]}}
            return {"success": False, "error": "No file selected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- Utilities ----

    @expose
    def open_file(self, file_path: str) -> dict:
        """Open a file with the system default application."""
        try:
            p = Path(file_path).resolve()
            allowed_base = Path(self._api._config.data_dir).resolve()
            if not str(p).startswith(str(allowed_base)):
                return {"success": False, "error": "Access denied: path outside data directory"}
            if sys.platform == "win32":
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return {"success": True, "data": {"file_path": str(p)}}
        except Exception as e:
            logger.exception("open_file failed")
            return {"success": False, "error": "Failed to open file"}

    @expose
    def open_folder(self, folder_path: str) -> dict:
        """Open a folder in the system file explorer."""
        try:
            p = Path(folder_path).resolve()
            allowed_base = Path(self._api._config.data_dir).resolve()
            if not str(p).startswith(str(allowed_base)):
                return {"success": False, "error": "Access denied: path outside data directory"}
            if sys.platform == "win32":
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return {"success": True, "data": {"folder_path": str(p)}}
        except Exception as e:
            logger.exception("open_folder failed")
            return {"success": False, "error": "Failed to open folder"}
