"""SherpaNote - AI-powered voice learning assistant.

Entry point for the PyWebVue desktop application.
Defines SherpaNoteAPI which bridges the Python backend
(ASR, AI, Storage) with the Vue 3 frontend via PyWebVue.
"""

import logging
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from pywebvue import App, Bridge, expose
from py.config import AppConfig, AiConfig, AsrConfig, ConfigStore, _DEFAULT_MODELS_DIR
from py.storage import Storage
from py.asr import SherpaASR
from py.llm import AIProcessor
from py.io import ensure_data_dir
from py.presets import AiPresetStore
from py.processing_presets import ProcessingPresetStore
from py import model_manager as _mm
from py import model_registry as _mr

logger = logging.getLogger(__name__)


class SherpaNoteAPI(Bridge):
    """Main API bridging Python backend to Vue frontend.

    All public methods are decorated with @expose and return
    {"success": True, "data": ...} on success or
    {"success": False, "error": "..."} on failure (auto-handled).

    Backend-to-frontend events use self._emit(event, data).

    Lifecycle:
        __init__() loads persisted config from SQLite,
        falling back to AppConfig.default() on first run.
        Config changes are saved immediately via ConfigStore.
    """

    def __init__(self):
        super().__init__()
        # Load persisted config (or defaults on first run).
        self._config_store = ConfigStore()
        self._config = self._config_store.load()
        ensure_data_dir(self._config.data_dir)
        self._storage = Storage()
        self._asr: SherpaASR | None = None
        self._ai: AIProcessor | None = None
        self._preset_store = AiPresetStore()
        self._processing_preset_store = ProcessingPresetStore()
        self._model_installer = _mm.ModelInstaller(
            self._config.asr.model_dir or _DEFAULT_MODELS_DIR,
            download_source=self._config.asr.download_source,
            custom_ghproxy_domain=self._config.asr.custom_ghproxy_domain,
            proxy_mode=self._config.asr.proxy_mode,
            proxy_url=self._config.asr.proxy_url,
        )
        # Track record IDs with unsaved changes for exit-time versioning.
        self._dirty_record_ids: set[str] = set()

    def dispatch_task(self, command: str, args: Any) -> Any:
        """Dispatch commands for run_on_main_thread.

        Registered commands:
          - "create_online_recognizer": args = None
          - "create_offline_recognizer": args = None
        """
        import sherpa_onnx

        if command == "create_online_recognizer":
            if self._asr is None:
                raise RuntimeError("ASR not initialized")
            if self._asr._online_recognizer is not None:
                logger.info("Online recognizer already exists, skipping")
                return True
            model_dir = self._asr._find_streaming_model()
            if model_dir is None:
                raise FileNotFoundError(
                    "No streaming ASR model found. "
                    f"Please download a model and place it in {self._asr._model_dir()}"
                )
            recognizer = self._asr._create_online_recognizer(sherpa_onnx, model_dir)
            # CRITICAL: Assign the recognizer to the ASR instance
            self._asr._online_recognizer = recognizer
            logger.info("Online recognizer created on main thread and assigned")
            return True

        elif command == "create_offline_recognizer":
            if self._asr is None:
                raise RuntimeError("ASR not initialized")
            if self._asr._offline_recognizer is not None:
                logger.info("Offline recognizer already exists, skipping")
                return True
            import sherpa_onnx as _sherpa
            model_dir = self._asr._find_offline_model()
            if model_dir is None:
                raise FileNotFoundError(
                    "No offline ASR model found. "
                    f"Please download a model and place it in {self._asr._model_dir()}"
                )
            recognizer = self._asr._create_offline_recognizer(_sherpa, model_dir)
            # CRITICAL: Assign the recognizer to the ASR instance
            self._asr._offline_recognizer = recognizer
            logger.info("Offline recognizer created on main thread and assigned")
            return True

        else:
            return super().dispatch_task(command, args)

    # ---- ASR (Speech Recognition) ----

    def _make_asr_config(self, language: str = "auto") -> AsrConfig:
        """Build an AsrConfig from the current persisted config."""
        return AsrConfig(
            model_dir=self._config.asr.model_dir,
            language=language,
            sample_rate=self._config.asr.sample_rate,
            use_gpu=self._config.asr.use_gpu,
            active_streaming_model=self._config.asr.active_streaming_model,
            active_offline_model=self._config.asr.active_offline_model,
            auto_punctuate=self._config.asr.auto_punctuate,
            download_source=self._config.asr.download_source,
            custom_ghproxy_domain=self._config.asr.custom_ghproxy_domain,
            proxy_mode=self._config.asr.proxy_mode,
            proxy_url=self._config.asr.proxy_url,
        )

    @expose
    def init_model(self, language: str = "auto") -> dict:
        """Initialize sherpa-onnx ASR model. Language: zh / en / auto.

        Runs model loading in a background thread. The frontend should
        listen for 'streaming_ready' or 'streaming_error' events.
        """
        asr_config = self._make_asr_config(language)
        self._asr = SherpaASR(asr_config)

        def _work() -> None:
            try:
                result = self._asr.start_streaming()
                self._emit("streaming_ready", result)
            except Exception as exc:
                self._emit("streaming_error", {"error": str(exc)})

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"language": language, "status": "loading"}}

    @expose
    def start_streaming(self) -> dict:
        """Start a streaming recognition session.

        Model loading (sherpa-onnx from_paraformer) runs on the main thread
        via run_on_main_thread to avoid Windows COM/ONNX conflicts.
        Completion is signalled via 'streaming_ready' event.
        """
        logger.info("start_streaming API called")
        if self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        def _work() -> None:
            import traceback
            logger.info("Background thread started for start_streaming")
            logger.info("_asr: %s, _online_recognizer: %s", self._asr, getattr(self._asr, '_online_recognizer', 'N/A'))
            try:
                # Ensure online recognizer is created on main thread
                if self._asr._online_recognizer is None:
                    logger.info("_online_recognizer is None, will create on main thread")
                    # This blocks until the main thread executes the task
                    self.run_on_main_thread("create_online_recognizer", timeout=60.0)
                    logger.info("Online recognizer creation completed")
                else:
                    logger.info("_online_recognizer already exists, skipping creation")

                # Now create the stream and start recording (safe on background thread)
                result = self._asr.start_streaming()
                logger.info("start_streaming completed, emitting streaming_ready: %s", result)
                self._emit("streaming_ready", result)
            except Exception as exc:
                logger.error("start_streaming failed: %s", exc, exc_info=True)
                self._emit("streaming_error", {"error": str(exc)})

        threading.Thread(target=_work, name="StartStreamingThread", daemon=True).start()
        logger.info("start_streaming returning 'loading' status")
        return {"success": True, "data": {"status": "loading"}}

    @expose
    def feed_audio(self, base64_data: str) -> dict:
        """Feed a Base64-encoded audio chunk. Results pushed via _emit."""
        if self._asr is None:
            logger.warning("feed_audio called but ASR not initialized")
            return {"success": False, "error": "ASR not initialized. Call start_streaming() first."}
        try:
            result = self._asr.feed_audio(base64_data)
            # Emit partial (in-progress) text.
            if result.get("partial"):
                self._emit("partial_result", {"text": result["partial"]})
            # Emit newly finalized segments (when endpoint detected).
            prev_count = len(self._asr._final_segments) - (1 if result.get("partial") else 0)
            for seg in result.get("final", []):
                if seg.get("index", 0) >= prev_count:
                    self._emit("final_result", {"text": seg["text"], "timestamp": []})
            return {"success": True, "data": {"length": len(base64_data)}}
        except Exception as e:
            import traceback
            logger.error("feed_audio exception: %s", e)
            logger.debug("feed_audio traceback: %s", traceback.format_exc())
            return {"success": False, "error": str(e)}

    @expose
    def stop_streaming(self) -> dict:
        """End streaming recognition. Returns final transcript."""
        if self._asr is None:
            return {"success": False, "error": "No active streaming session."}
        result = self._asr.stop_streaming()
        return {"success": True, "data": result}

    @expose
    def transcribe_file(self, file_path: str) -> dict:
        """Transcribe an audio file. Progress pushed via _emit.

        Model creation runs on the main thread via run_on_main_thread
        to avoid Windows COM/ONNX conflicts. The actual transcription
        runs in a background thread.
        Completion is reported via 'transcribe_complete' event.
        """
        logger.info("transcribe_file called for: %s", file_path)
        if self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        def on_progress(percent: int) -> None:
            self._emit("transcribe_progress", {"percent": percent})

        def _work() -> None:
            import traceback
            logger.info("transcribe_file background thread started")
            try:
                # Ensure offline recognizer is created on main thread
                if self._asr._offline_recognizer is None:
                    logger.info("Scheduling offline recognizer creation on main thread")
                    self.run_on_main_thread("create_offline_recognizer", timeout=60.0)
                    logger.info("Offline recognizer creation completed")

                # Now transcribe the file (safe on background thread)
                logger.info("Starting transcribe_file for: %s", file_path)
                segments = self._asr.transcribe_file(file_path, on_progress=on_progress)
                full_text = " ".join(s["text"] for s in segments)
                full_text = self._apply_punctuation(full_text)
                logger.info("transcribe_file completed, emitting event")
                self._emit("transcribe_complete", {
                    "segments": segments,
                    "text": full_text,
                    "audio_path": file_path,
                })
            except Exception as exc:
                logger.error("transcribe_file failed: %s", exc, exc_info=True)
                self._emit("transcribe_error", {"error": str(exc)})

        threading.Thread(target=_work, daemon=True).start()
        logger.info("transcribe_file returning 'transcribing' status")
        return {"success": True, "data": {"status": "transcribing"}}

    # ---- AI Processing ----

    def _get_ai(self) -> AIProcessor:
        """Lazy-initialize AI processor."""
        if self._ai is None:
            self._ai = AIProcessor(self._config.ai, max_tokens_mode=self._config.max_tokens_mode)
        return self._ai

    def _apply_punctuation(self, text: str) -> str:
        """Apply AI-based punctuation restoration if enabled and AI is configured.

        Returns the original text if punctuation is disabled or AI is unavailable.
        """
        if not self._config.asr.auto_punctuate:
            return text
        if not self._config.ai.api_key and not self._config.ai.base_url:
            logger.warning("Auto-punctuate enabled but no AI configured, skipping")
            return text
        try:
            return self._get_ai().restore_punctuation(text)
        except Exception as exc:
            logger.warning("Punctuation restoration failed: %s, using raw text", exc)
            return text

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
        Sends a minimal request and returns success/failure.
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
        """Process text with AI. Mode: polish / note / mindmap / brainstorm.
        custom_prompt: optional prompt template with {text} placeholder."""
        try:
            result, truncated = self._get_ai().process(text, mode, custom_prompt=custom_prompt)
            return {"success": True, "data": {"result": result, "truncated": truncated}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def process_text_stream(self, text: str, mode: str, custom_prompt: str = None) -> dict:
        """Stream AI results. Tokens pushed via _emit('ai_token').
        custom_prompt: optional prompt template with {text} placeholder.
        Streaming runs in a background thread to avoid blocking the main thread."""
        def _work() -> None:
            try:
                def on_token(chunk: str) -> None:
                    self._emit("ai_token", {"text": chunk})

                result, truncated = self._get_ai().process_stream(text, mode, on_token=on_token, custom_prompt=custom_prompt)
                if self._get_ai()._cancel_event.is_set():
                    self._emit("ai_error", {"error": "Cancelled"})
                    return
                self._emit("ai_complete", {"result": result, "truncated": truncated})
            except Exception as e:
                self._emit("ai_error", {"error": str(e)})

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"status": "streaming"}}

    @expose
    def cancel_ai(self) -> dict:
        """Cancel the current AI streaming request."""
        if self._ai is not None:
            self._ai.cancel()
            return {"success": True, "data": {"status": "cancelled"}}
        return {"success": False, "error": "No active AI session"}

    @expose
    def continue_text_stream(self, previous_output: str, mode: str, custom_prompt: str = None) -> dict:
        """Continue AI output from where it was truncated.

        Takes the previous output and asks the AI to continue from the last point.
        Streams continuation tokens via _emit('ai_token').
        Runs in a background thread to avoid blocking the main thread.
        """
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
                self._emit("ai_continue_complete", {"result": result, "truncated": truncated})
            except Exception as e:
                self._emit("ai_error", {"error": str(e)})

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"status": "streaming"}}

    def _auto_process_record(self, record: dict) -> dict:
        """Run configured auto AI processing modes on a record.

        Processes each mode non-streamingly in sequence, saves results
        to the record, and emits progress events.
        """
        text = record.get("transcript", "")
        if not text.strip():
            return record

        ai_results = dict(record.get("ai_results", {}) or {})

        for mode in self._config.auto_ai_modes:
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
            record = self._storage.save({
                **record,
                "ai_results": ai_results,
            })
            record = self._annotate_record(record)

        self._emit("auto_ai_complete", {
            "record_id": record["id"],
            "modes": list(ai_results.keys()),
        })
        return record

    # ---- Data Persistence ----

    @expose
    def save_record(self, data: dict) -> dict:
        """Create or update a record."""
        record = self._storage.save(data)
        record = self._annotate_record(record)
        return {"success": True, "data": record}

    def _annotate_record(self, record: dict) -> dict:
        """Add computed fields to a record for the frontend."""
        audio_path = record.get("audio_path", "")
        if audio_path:
            try:
                resolved = str(Path(audio_path).resolve())
                audio_dir = str(Path(self._config.data_dir).resolve() / "audio")
                record["can_retranscribe"] = resolved.startswith(audio_dir)
            except (OSError, ValueError):
                record["can_retranscribe"] = False
        else:
            record["can_retranscribe"] = False
        return record

    @expose
    def get_record(self, record_id: str) -> dict:
        """Fetch a single record by ID."""
        record = self._storage.get(record_id)
        if record is None:
            return {"success": False, "error": f"Record not found: {record_id}"}
        record = self._annotate_record(record)
        return {"success": True, "data": record}

    @expose
    def list_records(self, filter: dict = None) -> dict:
        """List records with optional filtering."""
        records = self._storage.list(filter)
        records = [self._annotate_record(r) for r in records]
        return {"success": True, "data": records}

    @expose
    def delete_record(self, record_id: str) -> dict:
        """Delete a record and its version history."""
        success = self._storage.delete(record_id)
        return {"success": success, "data": {"record_id": record_id}}

    @expose
    def search_records(self, keyword: str) -> dict:
        """Search records by keyword (title + transcript)."""
        records = self._storage.list({"keyword": keyword})
        return {"success": True, "data": records}

    @expose
    def get_audio_base64(self, file_path: str) -> dict:
        """Read an audio file and return base64-encoded content with MIME type."""
        p = Path(file_path).resolve()
        allowed_base = Path(self._config.data_dir).resolve()
        if not str(p).startswith(str(allowed_base)):
            return {"success": False, "error": "Access denied: path outside data directory"}
        if not p.exists():
            return {"success": False, "error": f"Audio file not found: {file_path}"}

        # Guard against excessively large files (base64 adds ~33% overhead).
        max_size = 100 * 1024 * 1024  # 100 MB
        if p.stat().st_size > max_size:
            return {"success": False, "error": "Audio file too large for browser playback"}

        import mimetypes
        mime, _ = mimetypes.guess_type(str(p))
        if mime is None:
            mime = "audio/wav"

        try:
            import base64
            data = p.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            return {"success": True, "data": {"base64": b64, "mime": mime}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def retranscribe_record(self, record_id: str) -> dict:
        """Re-transcribe the audio file associated with a record.

        Runs in a background thread. Progress is emitted via
        'transcribe_progress' events; completion via 'retranscribe_complete'.
        """
        logger.info("retranscribe_record: record_id=%s", record_id)

        record = self._storage.get(record_id)
        if record is None:
            logger.warning("retranscribe_record: record not found: %s", record_id)
            return {"success": False, "error": f"Record not found: {record_id}"}

        audio_path = record.get("audio_path")
        if not audio_path:
            logger.warning("retranscribe_record: no audio_path for record %s", record_id)
            return {"success": False, "error": "This record has no associated audio file"}

        if not Path(audio_path).exists():
            logger.warning("retranscribe_record: audio file not found: %s", audio_path)
            return {"success": False, "error": f"Audio file not found: {audio_path}"}

        if self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        logger.info("retranscribe_record: starting transcription of %s", audio_path)

        def on_progress(percent: int) -> None:
            self._emit("transcribe_progress", {"percent": percent})

        def _work() -> None:
            try:
                logger.info("retranscribe_record: creating offline recognizer...")
                # Ensure offline recognizer is created on main thread
                if self._asr._offline_recognizer is None:
                    self.run_on_main_thread("create_offline_recognizer", timeout=60.0)

                logger.info("retranscribe_record: transcribing file %s", audio_path)
                segments = self._asr.transcribe_file(audio_path, on_progress=on_progress)
                full_text = " ".join(s["text"] for s in segments)
                full_text = self._apply_punctuation(full_text)
                logger.info("retranscribe_record: transcription done, %d segments, saving...", len(segments))
                updated = self._storage.save({
                    "id": record_id,
                    "transcript": full_text,
                    "segments": segments,
                })
                self._emit("retranscribe_complete", {
                    "record_id": record_id,
                    "record": updated,
                })
                logger.info("retranscribe_record: complete for record %s", record_id)
            except FileNotFoundError as e:
                logger.error("retranscribe_record: file not found: %s", e)
                self._emit("transcribe_error", {"error": str(e)})
            except Exception as e:
                logger.error("retranscribe_record: failed: %s", e, exc_info=True)
                self._emit("transcribe_error", {"error": f"Transcription failed: {e}"})

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"status": "transcribing", "record_id": record_id}}

    # ---- Version History ----

    @expose
    def get_version_history(self, record_id: str) -> dict:
        """Get version history for a record."""
        versions = self._storage.get_versions(record_id)
        return {"success": True, "data": versions}

    @expose
    def save_version(self, record_id: str) -> dict:
        """Create an explicit version snapshot for a record.

        Call this from the "Save Version" button or on navigation-away.
        Also marks the record as clean (not dirty).
        """
        try:
            version = self._storage.create_version(
                record_id, max_versions=self._config.max_versions
            )
            self._dirty_record_ids.discard(record_id)
            logger.info("Saved version %d for record %s", version, record_id)
            return {"success": True, "data": {"version": version}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def mark_dirty(self, record_id: str) -> dict:
        """Mark a record as having unsaved changes (for exit-time versioning)."""
        self._dirty_record_ids.add(record_id)
        return {"success": True, "data": None}

    @expose
    def mark_clean(self, record_id: str) -> dict:
        """Mark a record as clean (no unsaved changes)."""
        self._dirty_record_ids.discard(record_id)
        return {"success": True, "data": None}

    @expose
    def restore_version(self, record_id: str, version: int) -> dict:
        """Restore a record to a specific version.

        Creates a new version snapshot of the restored content so
        the user can see which version is "current" and revert if needed.
        """
        record = self._storage.restore_version(record_id, version)
        if record is None:
            return {"success": False, "error": "Version not found."}
        # Create a version snapshot of the restored state
        new_ver = self._storage.create_version(
            record_id, max_versions=self._config.max_versions
        )
        record["version"] = new_ver
        return {"success": True, "data": record}

    @expose
    def delete_version(self, record_id: str, version: int) -> dict:
        """Delete a single version from a record's version history."""
        success = self._storage.delete_version(record_id, version)
        if not success:
            return {"success": False, "error": "Version not found."}
        return {"success": True, "data": {"version": version}}

    # ---- Export ----

    @expose
    def export_record(self, record_id: str, fmt: str, include_ai: bool = True) -> dict:
        """Export a record. Format: md / txt / docx / srt. include_ai controls whether AI results are included."""
        try:
            path = self._storage.export(record_id, fmt, include_ai=include_ai)
            return {"success": True, "data": {"file_path": path}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- Import ----

    @expose
    def import_record(self, file_path: str) -> dict:
        """Import a .md or .txt file as a new record."""
        try:
            from pathlib import Path as P

            p = P(file_path)
            if not p.exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            suffix = p.suffix.lower()
            if suffix not in (".md", ".txt"):
                return {"success": False, "error": f"Unsupported format: {suffix}. Use .md or .txt"}

            text = p.read_text(encoding="utf-8")
            title = p.stem  # filename without extension

            record = self._storage.save({
                "title": title,
                "transcript": text,
                "audio_path": None,
                "segments": [],
                "ai_results": {},
                "category": "",
                "tags": [],
                "duration_seconds": 0,
            })
            return {"success": True, "data": record}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- Import & Transcribe ----

    def _copy_file_to_audio_dir(self, src_path: str) -> str:
        """Copy a file into data/audio/ with a safe timestamped filename.

        Returns the destination path as a string.
        Appends a numeric suffix if a file with the same name exists.
        """
        audio_dir = Path(self._config.data_dir) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        src = Path(src_path)
        ext = src.suffix.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"import_{timestamp}"

        dest = audio_dir / f"{base_name}{ext}"
        if dest.exists():
            counter = 1
            while (audio_dir / f"{base_name}_{counter}{ext}").exists():
                counter += 1
            dest = audio_dir / f"{base_name}_{counter}{ext}"

        shutil.copy2(str(src), str(dest))
        logger.info("Copied %s -> %s", src_path, dest)
        return str(dest)

    @expose
    def import_and_transcribe(self, file_path: str) -> dict:
        """Copy an audio file into data/audio/, then transcribe it.

        Unlike transcribe_file, this manages the audio file inside the
        app's data directory so the resulting record supports re-transcription.

        Progress is emitted via 'transcribe_progress'; completion via
        'import_transcribe_complete' with {record_id, record, audio_path}.
        """
        logger.info("import_and_transcribe called for: %s", file_path)

        src = Path(file_path)
        if not src.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        audio_exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma"}
        if src.suffix.lower() not in audio_exts:
            return {"success": False, "error": f"Unsupported audio format: {src.suffix}"}

        # Copy file into managed directory.
        try:
            dest_path = self._copy_file_to_audio_dir(file_path)
        except Exception as exc:
            logger.error("Failed to copy file: %s", exc, exc_info=True)
            return {"success": False, "error": f"Failed to copy file: {exc}"}

        title = src.stem

        if self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        def on_progress(percent: int) -> None:
            self._emit("transcribe_progress", {"percent": percent})

        def _work(dest: str, rec_title: str) -> None:
            try:
                if self._asr._offline_recognizer is None:
                    self.run_on_main_thread("create_offline_recognizer", timeout=60.0)

                logger.info("import_and_transcribe: transcribing %s", dest)
                segments = self._asr.transcribe_file(dest, on_progress=on_progress)
                full_text = " ".join(s["text"] for s in segments)
                full_text = self._apply_punctuation(full_text)
                logger.info("import_and_transcribe: saving record")
                record = self._storage.save({
                    "title": rec_title,
                    "transcript": full_text,
                    "segments": segments,
                    "audio_path": dest,
                    "duration_seconds": 0,
                })
                record = self._annotate_record(record)

                # Auto AI processing after transcription.
                if self._config.auto_ai_modes and self._config.ai.api_key:
                    record = self._auto_process_record(record)

                self._emit("import_transcribe_complete", {
                    "record_id": record["id"],
                    "record": record,
                    "audio_path": dest,
                })
                logger.info("import_and_transcribe: complete, record_id=%s", record["id"])
            except Exception as exc:
                logger.error("import_and_transcribe: failed: %s", exc, exc_info=True)
                self._emit("transcribe_error", {"error": f"Transcription failed: {exc}"})

        threading.Thread(target=_work, args=(dest_path, title), daemon=True).start()
        return {"success": True, "data": {"status": "importing", "audio_path": dest_path}}

    # ---- Model Management ----

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
            self._config.asr.model_dir
            or str(__import__("pathlib").Path.home() / "sherpanote" / "models")
        )
        installed = _mm.list_installed_models(models_dir)
        return {"success": True, "data": installed}

    @expose
    def install_model(self, model_id: str) -> dict:
        """Start downloading and installing a model.

        Progress is reported via 'model_download_progress' events.
        Completion is reported via 'model_install_complete' event.
        """
        if self._model_installer.is_active:
            return {"success": False, "error": "A model installation is already in progress"}

        models_dir = (
            self._config.asr.model_dir
            or str(__import__("pathlib").Path.home() / "sherpanote" / "models")
        )
        self._model_installer = _mm.ModelInstaller(
            models_dir,
            download_source=self._config.asr.download_source,
            custom_ghproxy_domain=self._config.asr.custom_ghproxy_domain,
            proxy_mode=self._config.asr.proxy_mode,
            proxy_url=self._config.asr.proxy_url,
        )

        def on_progress(info: dict) -> None:
            self._emit("model_download_progress", info)

        def on_complete() -> None:
            result = self._model_installer.result
            if result and result.get("success"):
                self._emit("model_install_complete", result)
            elif result:
                self._emit("model_install_error", result)

        # Track completion via polling (installer runs in thread).
        self._model_installer.start(model_id, on_progress=on_progress)

        def _wait() -> None:
            if self._model_installer._thread:
                self._model_installer._thread.join()
            on_complete()

        threading.Thread(target=_wait, daemon=True).start()

        return {"success": True, "data": {"model_id": model_id, "status": "downloading"}}

    @expose
    def cancel_model_install(self) -> dict:
        """Cancel the current model installation."""
        if not self._model_installer.is_active:
            return {"success": False, "error": "No installation in progress"}
        self._model_installer.cancel()
        return {"success": True, "data": {"status": "cancelling"}}

    @expose
    def delete_model(self, model_id: str) -> dict:
        """Delete an installed model."""
        models_dir = (
            self._config.asr.model_dir
            or str(__import__("pathlib").Path.home() / "sherpanote" / "models")
        )
        result = _mm.delete_model(model_id, models_dir)
        return result

    @expose
    def validate_model(self, model_id: str) -> dict:
        """Validate an installed model's files."""
        models_dir = (
            self._config.asr.model_dir
            or str(__import__("pathlib").Path.home() / "sherpanote" / "models")
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

    @expose
    def pick_directory(self) -> dict:
        """Open a folder picker dialog and return the selected path."""
        try:
            import webview
            try:
                dialog_type = webview.FileDialog.FOLDER
            except AttributeError:
                dialog_type = webview.FOLDER_DIALOG  # fallback for older versions
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
                dialog_type = webview.OPEN_DIALOG  # fallback for older versions
            result = self._window.create_file_dialog(
                dialog_type=dialog_type,
                file_types=audio_extensions,
            )
            if result:
                return {"success": True, "data": result}
            return {"success": False, "error": "No file selected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- AI Provider Presets ----

    @expose
    def list_ai_presets(self) -> dict:
        """List all AI provider presets."""
        presets = self._preset_store.list()
        return {"success": True, "data": presets}

    @expose
    def create_ai_preset(self, data: dict) -> dict:
        """Create a new AI provider preset."""
        preset = self._preset_store.create(data)
        return {"success": True, "data": preset}

    @expose
    def update_ai_preset(self, preset_id: str, data: dict) -> dict:
        """Update an AI provider preset."""
        preset = self._preset_store.update(preset_id, data)
        if preset is None:
            return {"success": False, "error": f"Preset not found: {preset_id}"}
        return {"success": True, "data": preset}

    @expose
    def delete_ai_preset(self, preset_id: str) -> dict:
        """Delete an AI provider preset."""
        success = self._preset_store.delete(preset_id)
        return {"success": success, "data": {"preset_id": preset_id}}

    @expose
    def set_active_ai_preset(self, preset_id: str) -> dict:
        """Set a preset as active and update the app's AI config."""
        preset = self._preset_store.set_active(preset_id)
        if preset is None:
            return {"success": False, "error": f"Preset not found: {preset_id}"}
        # Sync the active preset into the app's AiConfig.
        self._config = AppConfig(
            data_dir=self._config.data_dir,
            asr=self._config.asr,
            ai=AiConfig(
                provider=preset["provider"],
                model=preset["model"],
                api_key=preset.get("api_key"),
                base_url=preset.get("base_url"),
                temperature=preset.get("temperature", 0.7),
                max_tokens=preset.get("max_tokens", 8192),
            ),
            max_versions=self._config.max_versions,
        )
        self._config_store.save(self._config)
        self._ai = None  # Reset AI processor to pick up new config.
        return {"success": True, "data": preset}

    # ---- AI Processing Presets ----

    @expose
    def list_processing_presets(self) -> dict:
        """List all AI processing presets."""
        presets = self._processing_preset_store.list()
        return {"success": True, "data": presets}

    @expose
    def create_processing_preset(self, data: dict) -> dict:
        """Create a new AI processing preset."""
        preset = self._processing_preset_store.create(data)
        return {"success": True, "data": preset}

    @expose
    def update_processing_preset(self, preset_id: str, data: dict) -> dict:
        """Update an AI processing preset."""
        preset = self._processing_preset_store.update(preset_id, data)
        if preset is None:
            return {"success": False, "error": f"Preset not found: {preset_id}"}
        return {"success": True, "data": preset}

    @expose
    def delete_processing_preset(self, preset_id: str) -> dict:
        """Delete a custom AI processing preset."""
        success = self._processing_preset_store.delete(preset_id)
        if not success:
            return {"success": False, "error": "Cannot delete built-in presets"}
        return {"success": True, "data": {"preset_id": preset_id}}

    # ---- Config ----

    @expose
    def list_audio_files(self) -> dict:
        """List all audio files in the data/audio directory.

        Returns each file with its size and linked records.
        """
        audio_dir = Path(self._config.data_dir) / "audio"
        if not audio_dir.is_dir():
            return {"success": True, "data": []}

        # Build a map from audio_path to records that reference it.
        records = self._storage.list()
        path_to_records: dict[str, list[dict[str, str]]] = {}
        for rec in records:
            audio_path = rec.get("audio_path", "")
            if audio_path:
                # Normalize path for cross-platform matching.
                normalized = str(Path(audio_path))
                path_to_records.setdefault(normalized, []).append({
                    "id": rec["id"],
                    "title": rec.get("title", ""),
                })

        files = []
        for entry in sorted(audio_dir.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True):
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext not in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma"):
                continue

            size_mb = entry.stat().st_size / (1024 * 1024)
            normalized = str(entry)
            linked = path_to_records.get(normalized, [])

            files.append({
                "file_path": str(entry),
                "file_name": entry.name,
                "size_mb": round(size_mb, 2),
                "linked_records": linked,
            })

        return {"success": True, "data": files}

    @expose
    def delete_audio_file(self, file_path: str) -> dict:
        """Delete an audio file from disk and clear references in linked records."""
        p = Path(file_path).resolve()
        allowed_base = Path(self._config.data_dir).resolve()
        if not str(p).startswith(str(allowed_base)):
            return {"success": False, "error": "Access denied: path outside data directory"}
        if not p.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        try:
            p.unlink()
            # Clear audio_path from records that reference this file.
            # Must pass the full record data to avoid overwriting other fields.
            normalized = str(p)
            for rec in self._storage.list():
                rec_audio = rec.get("audio_path")
                if not rec_audio:
                    continue
                rec_path = str(Path(rec_audio).resolve())
                if rec_path == normalized:
                    updated = dict(rec)
                    updated["audio_path"] = None
                    self._storage.save(updated)
            return {"success": True, "data": {"file_path": str(p)}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def open_audio_folder(self) -> dict:
        """Open the audio files directory in the system file explorer."""
        audio_dir = str(Path(self._config.data_dir) / "audio")
        Path(audio_dir).mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(audio_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", audio_dir])
            else:
                subprocess.Popen(["xdg-open", audio_dir])
            return {"success": True, "data": {"path": audio_dir}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def get_config(self) -> dict:
        """Get current application configuration."""
        return {"success": True, "data": self._config.to_dict()}

    @expose
    def update_config(self, config: dict) -> dict:
        """Update and persist application configuration."""
        self._config = AppConfig.from_dict(config)
        self._config_store.save(self._config)
        # Re-create AI processor with new config.
        self._ai = None
        # Re-create ASR if model_dir changed.
        self._asr = None
        return {"success": True, "data": self._config.to_dict()}

    # ---- Utilities ----

    @expose
    def open_file(self, file_path: str) -> dict:
        """Open a file with the system default application."""
        try:
            if sys.platform == "win32":
                os.startfile(file_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
            return {"success": True, "data": {"file_path": file_path}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def open_folder(self, folder_path: str) -> dict:
        """Open a folder in the system file explorer."""
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
            return {"success": True, "data": {"folder_path": folder_path}}
        except Exception as e:
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import faulthandler
    import logging
    import sys
    import traceback
    from pathlib import Path

    # Enable faulthandler to catch segfaults and other fatal errors
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fault_log = log_dir / "faults.log"
    faulthandler.enable(file=open(fault_log, "a", encoding="utf-8"))
    # Also log to stderr for immediate visibility
    faulthandler.enable()

    # Configure logging to file + console
    log_file = log_dir / "sherpanote.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Global exception handler to log crashes
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))
        # Also write to a crash file for easy access
        crash_file = log_dir / "last_crash.txt"
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        logging.info("Crash report written to %s", crash_file)

    sys.excepthook = handle_exception

    logging.info("=" * 60)
    logging.info("SherpaNote starting")
    logging.info("Log file: %s", log_file)
    logging.info("Fault log: %s", fault_log)
    logging.info("=" * 60)

    # Pre-import sherpa-onnx and pre-load ONNX Runtime DLLs BEFORE pywebview initializes WebView2.
    # On Windows, ONNX Runtime and Chromium/WebView2 share some system DLLs (MSVC runtime).
    # Loading sherpa-onnx's C++ DLLs before WebView2 avoids DLL version conflicts that would crash the process.
    try:
        import sherpa_onnx
        from pathlib import Path as P
        import sys

        logging.getLogger(__name__).info(
            "sherpa_onnx %s pre-loaded (before pywebview)",
            getattr(sherpa_onnx, "__version__", "unknown"),
        )
        logging.getLogger(__name__).info("Python executable: %s", sys.executable)
        logging.getLogger(__name__).info("Python version: %s", sys.version)

        # Try multiple strategies to safely pre-load ONNX Runtime
        models_dir = P("models")

        # Strategy 1: Try to pre-load using OfflineRecognizer (may be more stable)
        offline_model = models_dir / "sherpa-onnx-paraformer-zh-small-2024-03-09"
        if offline_model.exists() and (offline_model / "model.int8.onnx").exists():
            try:
                logging.info("Pre-loading ONNX Runtime via OfflineRecognizer (Paraformer)...")
                temp_recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
                    tokens=str(offline_model / "tokens.txt"),
                    paraformer=str(offline_model / "model.int8.onnx"),
                    num_threads=1,
                    sample_rate=16000,
                    feature_dim=80,
                    provider="cpu",
                )
                del temp_recognizer
                logging.info("ONNX Runtime DLLs pre-loaded via OfflineRecognizer successfully")
            except Exception as e:
                logging.warning("OfflineRecognizer pre-load failed: %s", e, exc_info=True)

        # Strategy 2: Even if above fails, try a minimal import-only approach
        # The key is to import before WebView2, even if we don't create recognizer yet
        logging.info("sherpa_onnx modules loaded: %s", dir(sherpa_onnx)[:10])
    except ImportError as exc:
        logging.getLogger(__name__).warning(
            "sherpa_onnx import failed: %s (ASR will not be available)", exc
        )

    try:
        api = SherpaNoteAPI()
        app = App(api, title="SherpaNote", frontend_dir="frontend_dist")

        def _shutdown_cleanup() -> None:
            """Save versions for any dirty records before process exit."""
            for rid in list(api._dirty_record_ids):
                try:
                    ver = api._storage.create_version(
                        rid, max_versions=api._config.max_versions
                    )
                    logger.info("Auto-saved version %d for record %s on exit", ver, rid)
                except Exception as exc:
                    logger.warning("Failed to auto-save version for %s: %s", rid, exc)
            api._storage.close()

        import atexit
        atexit.register(_shutdown_cleanup)

        app.run()
    except Exception as e:
        logging.critical("Failed to start app: %s", e, exc_info=True)
        raise
