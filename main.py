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
from typing import Any, Callable

from pywebvue import App, Bridge, expose
from py.config import AppConfig, AiConfig, AsrConfig, ConfigStore, _DEFAULT_MODELS_DIR
from py.storage import Storage
from py.asr import SherpaASR
from py.llm import AIProcessor
from py.io import ensure_data_dir, convert_to_mono_16k_wav
from py.presets import AiPresetStore
from py.processing_presets import ProcessingPresetStore
from py import model_manager as _mm
from py import model_registry as _mr
from py.video_downloader import VideoDownloadConfig, download_audio

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
        self._whisper_asr: "WhisperCppASR | None" = None
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
        # Track how many final segments have been emitted to the frontend
        # during the current streaming session (used for both true and simulated streaming).
        self._last_emitted_final_count: int = 0
        # Audio file display-name metadata (filename -> display_name).
        self._audio_meta: dict[str, str] = self._load_audio_meta()

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
            if self._asr._is_simulated_streaming:
                logger.info("Simulated streaming recognizer already exists, skipping")
                return True
            model_dir = self._asr._find_streaming_model()
            if model_dir is None:
                raise FileNotFoundError(
                    "No streaming ASR model found. "
                    f"Please download a model and place it in {self._asr._model_dir()}"
                )
            # Detect simulated streaming (SenseVoice) before creating recognizer.
            if self._asr._is_simulated_streaming_model(model_dir):
                logger.info("Detected simulated streaming model: %s", model_dir.name)
                self._asr._is_simulated_streaming = True
                self._asr._simulated_vad = self._asr._create_vad(sherpa_onnx, buffer_seconds=600, streaming=True)
                offline_rec = self._asr._create_offline_recognizer(sherpa_onnx, model_dir)
                self._asr._simulated_offline_recognizer = offline_rec
                logger.info("Simulated streaming setup complete (VAD + offline recognizer)")
            else:
                recognizer = self._asr._create_online_recognizer(sherpa_onnx, model_dir)
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

    def _make_asr_config(self, language: str | None = None) -> AsrConfig:
        """Build an AsrConfig from the current persisted config."""
        if language is None:
            language = self._config.asr.language or "auto"
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
            vad_min_silence_duration=self._config.asr.vad_min_silence_duration,
            vad_min_speech_duration=self._config.asr.vad_min_speech_duration,
            vad_max_speech_duration=self._config.asr.vad_max_speech_duration,
            vad_threshold=self._config.asr.vad_threshold,
            offline_use_vad=self._config.asr.offline_use_vad,
            vad_padding=self._config.asr.vad_padding,
            active_vad_model=self._config.asr.active_vad_model,
        )

    @expose
    def detect_gpu(self) -> dict:
        """Detect NVIDIA GPU and CUDA availability for sherpa-onnx.

        Runs detection in a background thread to avoid blocking the UI.
        Result is emitted via 'gpu_detect_complete' event.
        """
        def _work() -> None:
            try:
                from py.gpu_detect import detect_gpu
                status = detect_gpu()
                self._emit("gpu_detect_complete", {
                    "available": status.available,
                    "gpu_name": status.gpu_name,
                    "cuda_version": status.cuda_version,
                    "reason": status.reason,
                    "onnx_provider": status.onnx_provider,
                })
            except Exception as exc:
                logger.error("GPU detection failed: %s", exc)
                self._emit("gpu_detect_complete", {
                    "available": False,
                    "gpu_name": "",
                    "cuda_version": "",
                    "reason": str(exc),
                    "onnx_provider": "cpu",
                })

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"status": "detecting"}}

    @expose
    def init_model(self, language: str | None = None) -> dict:
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
                # Ensure recognizer is created on main thread
                needs_creation = (
                    self._asr._online_recognizer is None
                    and not self._asr._is_simulated_streaming
                ) or (
                    self._asr._is_simulated_streaming
                    and self._asr._simulated_offline_recognizer is None
                )
                if needs_creation:
                    logger.info("Recognizer not yet created, will create on main thread")
                    self.run_on_main_thread("create_online_recognizer", timeout=60.0)
                    logger.info("Recognizer creation completed")
                else:
                    logger.info("Recognizer already exists, skipping creation")

                # Now create the stream and start recording (safe on background thread)
                result = self._asr.start_streaming()
                self._last_emitted_final_count = 0
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
            # Emit newly finalized segments using a tracked count.
            # This works for both true streaming and simulated streaming (VAD + offline).
            current_count = len(self._asr._final_segments)
            for i in range(self._last_emitted_final_count, current_count):
                seg = self._asr._final_segments[i]
                self._emit("final_result", {"text": seg["text"], "timestamp": []})
            self._last_emitted_final_count = current_count
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

        use_whisper = self._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        def on_progress(percent: int, info: dict | None = None) -> None:
            payload: dict = {"percent": percent}
            if info:
                payload["segments"] = info
            self._emit("transcribe_progress", payload)

        def _work() -> None:
            import traceback
            logger.info("transcribe_file background thread started")
            try:
                if use_whisper:
                    # whisper.cpp backend (no main-thread recognizer needed).
                    whisper = self._get_whisper_asr()
                    if whisper is None:
                        raise RuntimeError("whisper.cpp ASR not available")
                    logger.info("Starting whisper.cpp transcribe_file for: %s", file_path)
                    segments = whisper.transcribe_file(file_path, on_progress=on_progress)
                else:
                    # sherpa-onnx backend.
                    if self._asr is None:
                        raise RuntimeError("sherpa-onnx ASR not initialized")
                    if self._asr._offline_recognizer is None:
                        logger.info("Scheduling offline recognizer creation on main thread")
                        self.run_on_main_thread("create_offline_recognizer", timeout=60.0)
                        logger.info("Offline recognizer creation completed")
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
        # Annotate with current version number from versions table.
        if "version" not in record or not record.get("version"):
            record["version"] = self._storage._get_current_version(record["id"])
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

        use_whisper = self._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        logger.info("retranscribe_record: starting transcription of %s", audio_path)

        def on_progress(percent: int, info: dict | None = None) -> None:
            payload: dict = {"percent": percent}
            if info:
                payload["segments"] = info
            self._emit("transcribe_progress", payload)

        def _work() -> None:
            try:
                if use_whisper:
                    whisper = self._get_whisper_asr()
                    if whisper is None:
                        raise RuntimeError("whisper.cpp ASR not available")
                    logger.info("retranscribe_record: transcribing with whisper.cpp: %s", audio_path)
                    segments = whisper.transcribe_file(audio_path, on_progress=on_progress)
                else:
                    if self._asr is None:
                        raise RuntimeError("sherpa-onnx ASR not initialized")
                    logger.info("retranscribe_record: creating offline recognizer...")
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

    def _audio_meta_path(self) -> Path:
        """Path to the audio display-name metadata JSON file."""
        return Path(self._config.data_dir) / "audio_meta.json"

    def _load_audio_meta(self) -> dict[str, str]:
        """Load audio metadata mapping from disk."""
        try:
            import json
            text = self._audio_meta_path().read_text(encoding="utf-8")
            return json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_audio_meta(self) -> None:
        """Persist audio metadata mapping to disk."""
        import json
        self._audio_meta_path().write_text(
            json.dumps(self._audio_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _copy_file_to_audio_dir(self, src_path: str, display_name: str | None = None) -> str:
        """Copy a file into data/audio/ with a safe timestamped filename.

        Args:
            src_path: Source file path.
            display_name: Human-readable name to show in the audio manager
                (e.g. video title or original filename).

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

        # Save display name metadata so the audio manager can show it.
        if display_name:
            self._audio_meta[dest.name] = display_name
            self._save_audio_meta()

        return str(dest)

    @expose
    def import_and_transcribe(self, file_path: str, title: str | None = None) -> dict:
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

        if title is None:
            title = src.stem

        # If the file is already in the managed audio directory, use it directly.
        # Otherwise, copy it into the managed directory.
        audio_dir = Path(self._config.data_dir) / "audio"
        resolved_src = src.resolve()
        resolved_audio_dir = audio_dir.resolve()
        if str(resolved_src).startswith(str(resolved_audio_dir)):
            dest_path = file_path
        else:
            try:
                dest_path = self._copy_file_to_audio_dir(file_path, display_name=title)
            except Exception as exc:
                logger.error("Failed to copy file: %s", exc, exc_info=True)
                return {"success": False, "error": f"Failed to copy file: {exc}"}

        use_whisper = self._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        def on_progress(percent: int, info: dict | None = None) -> None:
            payload: dict = {"percent": percent}
            if info:
                payload["segments"] = info
            self._emit("transcribe_progress", payload)

        def _work(dest: str, rec_title: str) -> None:
            self._transcribe_and_save_record(dest, rec_title, on_progress)

        threading.Thread(target=_work, args=(dest_path, title), daemon=True).start()
        return {"success": True, "data": {"status": "importing", "audio_path": dest_path}}

    def _transcribe_and_save_record(self, audio_path: str, title: str, on_progress: Callable) -> None:
        """Internal helper to transcribe an audio file and save it as a record.

        This method is intended to be run in a background thread.
        """
        from py.io import get_audio_metadata

        try:
            use_whisper = self._config.asr.asr_backend == "whisper-cpp"
            if use_whisper:
                whisper = self._get_whisper_asr()
                if whisper is None:
                    raise RuntimeError("whisper.cpp ASR not available")
                logger.info("Transcribing with whisper.cpp: %s", audio_path)
                segments = whisper.transcribe_file(audio_path, on_progress=on_progress)
            else:
                if self._asr is None:
                    raise RuntimeError("sherpa-onnx ASR not initialized")
                if self._asr._offline_recognizer is None:
                    self.run_on_main_thread("create_offline_recognizer", timeout=60.0)
                logger.info("Transcribing with sherpa-onnx: %s", audio_path)
                segments = self._asr.transcribe_file(audio_path, on_progress=on_progress)
            
            full_text = " ".join(s["text"] for s in segments)
            full_text = self._apply_punctuation(full_text)
            logger.info("Saving record for %s", title)
            # Calculate actual duration from audio metadata.
            meta = get_audio_metadata(audio_path)
            duration_seconds = meta.get("duration", 0) or 0
            record = self._storage.save({
                "title": title,
                "transcript": full_text,
                "segments": segments,
                "audio_path": audio_path,
                "duration_seconds": duration_seconds,
            })
            record = self._annotate_record(record)
            
            # Auto AI processing after transcription.
            if self._config.auto_ai_modes and self._config.ai.api_key:
                record = self._auto_process_record(record)
            
            self._emit("import_transcribe_complete", {
                "record_id": record["id"],
                "record": record,
                "audio_path": audio_path,
            })
            logger.info("Transcription and save complete, record_id=%s", record["id"])
        except Exception as exc:
            logger.error("Transcription failed: %s", exc, exc_info=True)
            self._emit("transcribe_error", {"error": f"Transcription failed: {exc}"})

    @expose
    def download_and_transcribe(self, url: str) -> dict:
        """Download audio from a URL and then transcribe it.

        Progress is emitted via 'download_progress' and 'transcribe_progress'.
        Completion is reported via 'import_transcribe_complete'.
        """
        logger.info("download_and_transcribe called for URL: %s", url)

        # 1. Setup download config
        # Use data/temp for initial download
        temp_dir = str(Path(self._config.data_dir) / "temp")
        config = VideoDownloadConfig(
            output_dir=temp_dir,
            proxy=self._config.asr.proxy_url if self._config.asr.proxy_mode == "manual" else ""
        )

        def on_download_progress(progress: float) -> None:
            self._emit("download_progress", {"percent": int(progress * 100)})

        def _work(downloaded_path: str, title: str) -> None:
            try:
                # 2. Move to managed audio directory (save video title as display name)
                dest_path = self._copy_file_to_audio_dir(downloaded_path, display_name=title)

                # 3. Transcribe and save
                def on_transcribe_progress(percent: int, info: dict | None = None) -> None:
                    payload: dict = {"percent": percent}
                    if info:
                        payload["segments"] = info
                    self._emit("transcribe_progress", payload)

                self._transcribe_and_save_record(dest_path, title, on_transcribe_progress)

            except Exception as exc:
                logger.error("download_and_transcribe failed: %s", exc, exc_info=True)
                self._emit("transcribe_error", {"error": f"Download/Transcription failed: {exc}"})

        # Pre-initialize ASR (same as import_and_transcribe).
        use_whisper = self._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        def _download_then_work() -> None:
            try:
                logger.info("Starting download for URL: %s", url)
                downloaded_path, title = download_audio(url, config, on_download_progress)
                _work(downloaded_path, title)
            except Exception as exc:
                logger.error("download_and_transcribe failed: %s", exc, exc_info=True)
                self._emit("transcribe_error", {"error": f"Download/Transcription failed: {exc}"})

        threading.Thread(target=_download_then_work, daemon=True).start()
        return {"success": True, "data": {"status": "downloading"}}

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

    # ------------------------------------------------------------------ #
    #  whisper.cpp binary management                                       #
    # ------------------------------------------------------------------ #

    @expose
    def get_whisper_binary_status(self) -> dict:
        """Check whisper.cpp binary installation status."""
        from py.whispercpp_registry import get_status

        data_dir = self._config.data_dir or str(Path(__file__).parent / "data")
        status = get_status(data_dir)
        return {"success": True, "data": status}

    @expose
    def install_whisper_binary(self, variant: str | None = None) -> dict:
        """Download and install whisper.cpp binary for the current platform."""
        from py.whispercpp_registry import install_binary

        data_dir = self._config.data_dir or str(Path(__file__).parent / "data")

        def _on_progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = int(100 * downloaded / total)
                self._emit("model_download_progress", {
                    "model_id": "whisper-cpp-binary",
                    "phase": "download",
                    "percent": pct,
                    "downloaded_mb": round(downloaded / (1024 * 1024), 1),
                    "total_mb": round(total / (1024 * 1024), 1),
                })

        result = install_binary(
            data_dir,
            variant=variant,
            on_progress=_on_progress,
            proxy_mode=self._config.asr.proxy_mode,
            proxy_url=self._config.asr.proxy_url,
        )
        return result

    @expose
    def uninstall_whisper_binary(self) -> dict:
        """Remove the installed whisper.cpp binary."""
        from py.whispercpp_registry import uninstall_binary

        data_dir = self._config.data_dir or str(Path(__file__).parent / "data")
        removed = uninstall_binary(data_dir)
        return {"success": True, "data": {"removed": removed}}

    def _get_whisper_asr(self) -> "WhisperCppASR | None":
        """Lazily initialize and return the WhisperCppASR instance."""
        if self._whisper_asr is None:
            from py.whispercpp import WhisperCppASR, WhisperCppConfig
            from py.whispercpp_registry import get_binary_path

            data_dir = self._config.data_dir or str(Path(__file__).parent / "data")
            binary_path = get_binary_path(data_dir)

            # Use the active whisper.cpp model.
            model_dir = Path(self._config.asr.model_dir or _DEFAULT_MODELS_DIR)
            model_id = self._config.asr.active_whisper_model or self._config.asr.active_offline_model
            model_path = ""
            if model_id and model_id.startswith("whisper-ggml-"):
                model_path = str(model_dir / model_id / f"ggml-{model_id.replace('whisper-ggml-', '')}.bin")

            if not model_path or not Path(model_path).exists():
                # Try to find any installed whisper.cpp model.
                for child in model_dir.iterdir():
                    if child.is_dir() and child.name.startswith("whisper-ggml-"):
                        bin_file = next(child.glob("ggml-*.bin"), None)
                        if bin_file:
                            model_path = str(bin_file)
                            break

            if not model_path:
                return None

            config = WhisperCppConfig(
                binary_path=str(binary_path),
                model_path=model_path,
                language=self._config.asr.language,
                threads=4,
            )
            self._whisper_asr = WhisperCppASR(config)

        return self._whisper_asr

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
                "display_name": self._audio_meta.get(entry.name, ""),
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
            # Clean up display-name metadata.
            self._audio_meta.pop(p.name, None)
            self._save_audio_meta()
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
            
            # Cleanup temporary files
            try:
                temp_dir = Path(api._config.data_dir) / "temp"
                if temp_dir.exists() and temp_dir.is_dir():
                    shutil.rmtree(temp_dir)
                    logger.info("Cleaned up temporary directory: %s", temp_dir)
            except Exception as e:
                logger.warning("Failed to cleanup temporary directory: %s", e)

        import atexit
        atexit.register(_shutdown_cleanup)

        app.run()
    except Exception as e:
        logging.critical("Failed to start app: %s", e, exc_info=True)
        raise
