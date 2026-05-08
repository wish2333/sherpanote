"""AI processing API mixin.

Provides AI text processing (polish/note/mindmap/brainstorm),
streaming, punctuation restoration, and preset management.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from pywebvue import expose
from py.api.base import ApiBase
from py.config import AiConfig, AppConfig
from py.llm import AIProcessor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AiMixin(ApiBase):
    """AI-related @expose methods."""

    # ---- Internal helpers ----

    def _get_ai(self) -> AIProcessor:
        """Lazy-initialize AI processor."""
        if self._api._ai is None:
            self._api._ai = AIProcessor(
                self._api._config.ai,
                max_tokens_mode=self._api._config.max_tokens_mode,
            )
        return self._api._ai

    def _persist_ai_result(self, record_id: str, mode: str, result: str) -> dict | None:
        """Persist an AI processing result to a record in the database.

        Returns the annotated saved record, or None on failure.
        Thread-safe: called from background threads.
        """
        try:
            record = self._api._storage.get(record_id)
            if record is None:
                logger.warning("Cannot persist AI result: record %s not found", record_id)
                return None
            ai_results = dict(record.get("ai_results", {}) or {})
            ai_results[mode] = result
            saved = self._api._storage.save({**record, "ai_results": ai_results})
            return self._api._annotate_record(saved)
        except Exception as exc:
            logger.warning("Failed to persist AI result for record %s: %s", record_id, exc)
            return None

    def _auto_process_record(self, record: dict) -> dict:
        """Run configured auto AI processing modes on a record.

        Processes each mode non-streamingly in sequence, saves results
        to the record, and emits progress events.
        """
        text = record.get("transcript", "")
        if not text.strip():
            return record

        ai_results = dict(record.get("ai_results", {}) or {})

        for mode in self._api._config.auto_ai_modes:
            try:
                self._emit("auto_ai_progress", {
                    "record_id": record["id"],
                    "mode": mode,
                    "status": "processing",
                })
                result, _ = self._get_ai().process(text, mode)
                ai_results[mode] = result
                self._emit("auto_ai_progress", {
                    "record_id": record["id"],
                    "mode": mode,
                    "status": "done",
                })
            except Exception as exc:
                logger.warning("Auto AI processing mode=%s failed: %s", mode, exc)
                self._emit("auto_ai_progress", {
                    "record_id": record["id"],
                    "mode": mode,
                    "status": "error",
                    "error": str(exc),
                })

        if ai_results:
            record = self._api._storage.save({
                **record,
                "ai_results": ai_results,
            })
            record = self._api._annotate_record(record)

        self._emit("auto_ai_complete", {
            "record_id": record["id"],
            "modes": list(ai_results.keys()),
        })
        return record

    # ---- Exposed methods ----

    @expose
    def test_ai_connection(self) -> dict:
        """Test the AI configuration by sending a minimal request."""
        try:
            result, _ = self._get_ai().process("Hello", "polish")
            return {"success": True, "data": {"response": result[:200]}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def test_ai_preset_connection(self, config: dict) -> dict:
        """Test an AI connection using an inline config dict.

        config must contain: provider, model. Optional: api_key, base_url.
        """
        test_config = AiConfig(
            provider=config.get("provider", "openai"),
            model=config.get("model", ""),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 8192),
        )

        try:
            proc = AIProcessor(test_config)
            result, _ = proc.process("Hello", "polish")
            return {"success": True, "data": {"response": result[:200]}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def process_text(self, text: str, mode: str, custom_prompt: str = None) -> dict:
        """Process text with AI. Mode: polish / note / mindmap / brainstorm."""
        try:
            result, truncated = self._get_ai().process(text, mode, custom_prompt=custom_prompt)
            return {"success": True, "data": {"result": result, "truncated": truncated}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def process_text_stream(self, text: str, mode: str, custom_prompt: str = None, record_id: str = None) -> dict:
        """Stream AI results. Tokens pushed via _emit('ai_token')."""
        def _work() -> None:
            try:
                def on_token(chunk: str) -> None:
                    self._emit("ai_token", {"text": chunk})

                result, truncated = self._get_ai().process_stream(
                    text, mode, on_token=on_token, custom_prompt=custom_prompt
                )
                if self._get_ai()._cancel_event.is_set():
                    self._emit("ai_error", {"error": "Cancelled"})
                    return

                saved_record = None
                if record_id:
                    saved_record = self._persist_ai_result(record_id, mode, result)

                self._emit("ai_complete", {
                    "result": result,
                    "truncated": truncated,
                    "record": saved_record,
                })
            except Exception as e:
                self._emit("ai_error", {"error": str(e)})

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"status": "streaming"}}

    @expose
    def cancel_ai(self) -> dict:
        """Cancel the current AI streaming request."""
        if self._api._ai is not None:
            self._api._ai.cancel()
            return {"success": True, "data": {"status": "cancelled"}}
        return {"success": False, "error": "No active AI session"}

    @expose
    def continue_text_stream(self, previous_output: str, mode: str, custom_prompt: str = None, record_id: str = None) -> dict:
        """Continue AI output from where it was truncated."""
        def _work() -> None:
            try:
                def on_token(chunk: str) -> None:
                    self._emit("ai_token", {"text": chunk})

                result, truncated = self._get_ai().continue_stream(
                    previous_output, mode, on_token=on_token, custom_prompt=custom_prompt
                )
                if self._get_ai()._cancel_event.is_set():
                    self._emit("ai_error", {"error": "Cancelled"})
                    return

                saved_record = None
                if record_id:
                    saved_record = self._persist_ai_result(record_id, mode, result)

                self._emit("ai_continue_complete", {
                    "result": result,
                    "truncated": truncated,
                    "record": saved_record,
                })
            except Exception as e:
                self._emit("ai_error", {"error": str(e)})

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"status": "streaming"}}

    # ---- AI Provider Presets ----

    @expose
    def list_ai_presets(self) -> dict:
        """List all AI provider presets."""
        presets = self._api._preset_store.list()
        return {"success": True, "data": presets}

    @expose
    def create_ai_preset(self, data: dict) -> dict:
        """Create a new AI provider preset."""
        preset = self._api._preset_store.create(data)
        return {"success": True, "data": preset}

    @expose
    def update_ai_preset(self, preset_id: str, data: dict) -> dict:
        """Update an AI provider preset."""
        preset = self._api._preset_store.update(preset_id, data)
        if preset is None:
            return {"success": False, "error": f"Preset not found: {preset_id}"}
        return {"success": True, "data": preset}

    @expose
    def delete_ai_preset(self, preset_id: str) -> dict:
        """Delete an AI provider preset."""
        success = self._api._preset_store.delete(preset_id)
        return {"success": success, "data": {"preset_id": preset_id}}

    @expose
    def set_active_ai_preset(self, preset_id: str) -> dict:
        """Set a preset as active and update the app's AI config."""
        preset = self._api._preset_store.set_active(preset_id)
        if preset is None:
            return {"success": False, "error": f"Preset not found: {preset_id}"}
        # Sync the active preset into the app's AiConfig.
        self._api._config = AppConfig(
            data_dir=self._api._config.data_dir,
            asr=self._api._config.asr,
            ai=AiConfig(
                provider=preset["provider"],
                model=preset["model"],
                api_key=preset.get("api_key"),
                base_url=preset.get("base_url"),
                temperature=preset.get("temperature", 0.7),
                max_tokens=preset.get("max_tokens", 8192),
            ),
            max_versions=self._api._config.max_versions,
        )
        self._api._config_store.save(self._api._config)
        self._api._ai = None  # Reset AI processor to pick up new config.
        return {"success": True, "data": preset}

    # ---- AI Processing Presets ----

    @expose
    def list_processing_presets(self) -> dict:
        """List all AI processing presets."""
        presets = self._api._processing_preset_store.list()
        return {"success": True, "data": presets}

    @expose
    def create_processing_preset(self, data: dict) -> dict:
        """Create a new AI processing preset."""
        preset = self._api._processing_preset_store.create(data)
        return {"success": True, "data": preset}

    @expose
    def update_processing_preset(self, preset_id: str, data: dict) -> dict:
        """Update an AI processing preset."""
        preset = self._api._processing_preset_store.update(preset_id, data)
        if preset is None:
            return {"success": False, "error": f"Preset not found: {preset_id}"}
        return {"success": True, "data": preset}

    @expose
    def delete_processing_preset(self, preset_id: str) -> dict:
        """Delete a custom AI processing preset."""
        success = self._api._processing_preset_store.delete(preset_id)
        if not success:
            return {"success": False, "error": "Cannot delete built-in presets"}
        return {"success": True, "data": {"preset_id": preset_id}}

    @expose
    def reset_builtin_presets(self) -> dict:
        """Reset all built-in processing presets to their default prompts."""
        presets = self._api._processing_preset_store.reset_builtins()
        return {"success": True, "data": presets}
