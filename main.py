"""SherpaNote - AI-powered voice learning assistant.

Entry point for the PyWebVue desktop application.
Defines SherpaNoteAPI which bridges the Python backend
(ASR, AI, Storage) with the Vue 3 frontend via PyWebVue.
"""

import logging
import os
import subprocess
import sys
import threading
from typing import Any

from pywebvue import App, Bridge, expose
from py.config import AppConfig, AiConfig, AsrConfig, ConfigStore, _DEFAULT_MODELS_DIR
from py.storage import Storage
from py.asr import SherpaASR
from py.llm import AIProcessor
from py.io import ensure_data_dir
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
        self._model_installer = _mm.ModelInstaller(
            self._config.asr.model_dir or _DEFAULT_MODELS_DIR,
            mirror_url=self._config.asr.mirror_url,
        )

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
            mirror_url=self._config.asr.mirror_url,
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
                logger.info("transcribe_file completed, emitting event")
                self._emit("transcribe_complete", {
                    "segments": segments,
                    "text": " ".join(s["text"] for s in segments),
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
            self._ai = AIProcessor(self._config.ai)
        return self._ai

    @expose
    def test_ai_connection(self) -> dict:
        """Test the AI configuration by sending a minimal request."""
        try:
            result = self._get_ai().process("Hello", "polish")
            return {"success": True, "data": {"response": result[:200]}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def process_text(self, text: str, mode: str) -> dict:
        """Process text with AI. Mode: polish / note / mindmap / brainstorm."""
        try:
            result = self._get_ai().process(text, mode)
            return {"success": True, "data": {"result": result}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def process_text_stream(self, text: str, mode: str) -> dict:
        """Stream AI results. Tokens pushed via _emit('ai_token')."""
        try:
            def on_token(chunk: str) -> None:
                self._emit("ai_token", {"text": chunk})

            result = self._get_ai().process_stream(text, mode, on_token=on_token)
            if self._get_ai()._cancel_event.is_set():
                self._emit("ai_error", {"error": "Cancelled"})
                return {"success": False, "error": "Cancelled"}
            self._emit("ai_complete", {"result": result})
            return {"success": True, "data": {"result": result}}
        except Exception as e:
            self._emit("ai_error", {"error": str(e)})
            return {"success": False, "error": str(e)}

    @expose
    def cancel_ai(self) -> dict:
        """Cancel the current AI streaming request."""
        if self._ai is not None:
            self._ai.cancel()
            return {"success": True, "data": {"status": "cancelled"}}
        return {"success": False, "error": "No active AI session"}

    # ---- Data Persistence ----

    @expose
    def save_record(self, data: dict) -> dict:
        """Create or update a record."""
        record = self._storage.save(data)
        return {"success": True, "data": record}

    @expose
    def get_record(self, record_id: str) -> dict:
        """Fetch a single record by ID."""
        record = self._storage.get(record_id)
        if record is None:
            return {"success": False, "error": f"Record not found: {record_id}"}
        return {"success": True, "data": record}

    @expose
    def list_records(self, filter: dict = None) -> dict:
        """List records with optional filtering."""
        records = self._storage.list(filter)
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
    def retranscribe_record(self, record_id: str) -> dict:
        """Re-transcribe the audio file associated with a record.

        Runs in a background thread. Progress is emitted via
        'transcribe_progress' events; completion via 'retranscribe_complete'.
        """
        from pathlib import Path as P

        record = self._storage.get(record_id)
        if record is None:
            return {"success": False, "error": f"Record not found: {record_id}"}

        audio_path = record.get("audio_path")
        if not audio_path:
            return {"success": False, "error": "This record has no associated audio file"}

        if not P(audio_path).exists():
            return {"success": False, "error": f"Audio file not found: {audio_path}"}

        if self._asr is None:
            self._asr = SherpaASR(self._make_asr_config())

        def on_progress(percent: int) -> None:
            self._emit("transcribe_progress", {"percent": percent})

        def _work() -> None:
            try:
                segments = self._asr.transcribe_file(audio_path, on_progress=on_progress)
                full_text = " ".join(s["text"] for s in segments)
                updated = self._storage.save({
                    "id": record_id,
                    "transcript": full_text,
                    "segments": segments,
                })
                self._emit("retranscribe_complete", {
                    "record_id": record_id,
                    "record": updated,
                })
            except FileNotFoundError as e:
                self._emit("transcribe_error", {"error": str(e)})
            except Exception as e:
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
    def restore_version(self, record_id: str, version: int) -> dict:
        """Restore a record to a specific version."""
        record = self._storage.restore_version(record_id, version)
        if record is None:
            return {"success": False, "error": "Version not found."}
        return {"success": True, "data": record}

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

    # ---- Model Management ----

    @expose
    def list_available_models(self, model_type: str = None) -> dict:
        """List models from the registry catalog."""
        models = _mr.list_models(model_type)
        data = [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "model_type": m.model_type,
                "languages": list(m.languages),
                "size_mb": m.size_mb,
                "description": m.description,
            }
            for m in models
        ]
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
            models_dir, mirror_url=self._config.asr.mirror_url,
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

    # ---- Config ----

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
        app.run()
    except Exception as e:
        logging.critical("Failed to start app: %s", e, exc_info=True)
        raise
