"""Model management API mixin.

Provides model listing, installation, deletion, validation,
and download link retrieval for ASR models.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from pywebvue import expose
from py.api.base import ApiBase
from py import model_manager as _mm
from py import model_registry as _mr
from py.config import _DEFAULT_MODELS_DIR

logger = logging.getLogger(__name__)


class ModelsMixin(ApiBase):
    """Model management @expose methods."""

    @expose
    def list_available_models(self, model_type: str = None) -> dict:
        """List models from the registry catalog."""
        models = _mr.list_models(model_type)
        data = [_mr.model_to_dict(m) for m in models]
        return {"success": True, "data": data}

    @expose
    def list_installed_models(self) -> dict:
        """List models installed on disk."""
        models_dir = (
            self._api._config.asr.model_dir
            or str(Path.home() / "sherpanote" / "models")
        )
        installed = _mm.list_installed_models(models_dir)
        return {"success": True, "data": installed}

    @expose
    def install_model(self, model_id: str) -> dict:
        """Start downloading and installing a model."""
        if self._api._model_installer.is_active:
            return {"success": False, "error": "A model installation is already in progress"}

        models_dir = (
            self._api._config.asr.model_dir
            or str(Path.home() / "sherpanote" / "models")
        )
        self._api._model_installer = _mm.ModelInstaller(
            models_dir,
            download_source=self._api._config.asr.download_source,
            custom_ghproxy_domain=self._api._config.asr.custom_ghproxy_domain,
            proxy_mode=self._api._config.asr.proxy_mode,
            proxy_url=self._api._config.asr.proxy_url,
        )

        def on_progress(info: dict) -> None:
            self._emit("model_download_progress", info)

        def on_complete() -> None:
            result = self._api._model_installer.result
            if result and result.get("success"):
                self._emit("model_install_complete", result)
            elif result:
                self._emit("model_install_error", result)

        self._api._model_installer.start(model_id, on_progress=on_progress)

        def _wait() -> None:
            if self._api._model_installer._thread:
                self._api._model_installer._thread.join()
            on_complete()

        threading.Thread(target=_wait, daemon=True).start()

        return {"success": True, "data": {"model_id": model_id, "status": "downloading"}}

    @expose
    def cancel_model_install(self) -> dict:
        """Cancel the current model installation."""
        if not self._api._model_installer.is_active:
            return {"success": False, "error": "No installation in progress"}
        self._api._model_installer.cancel()
        return {"success": True, "data": {"status": "cancelling"}}

    @expose
    def delete_model(self, model_id: str) -> dict:
        """Delete an installed model."""
        models_dir = (
            self._api._config.asr.model_dir
            or str(Path.home() / "sherpanote" / "models")
        )
        result = _mm.delete_model(model_id, models_dir)
        return result

    @expose
    def validate_model(self, model_id: str) -> dict:
        """Validate an installed model's files."""
        models_dir = (
            self._api._config.asr.model_dir
            or str(Path.home() / "sherpanote" / "models")
        )
        result = _mm.validate_model(model_id, models_dir)
        return {"success": True, "data": result}

    @expose
    def get_download_links(self, model_id: str) -> dict:
        """Get manual download links for a model."""
        entry = _mr.get_model(model_id)
        if entry is None:
            return {"success": False, "error": f"Model not found: {model_id}"}
        return {"success": True, "data": list(entry.manual_download_links)}
