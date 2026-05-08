"""SherpaNote - AI-powered voice learning assistant.

Entry point for the PyWebVue desktop application.
Defines SherpaNoteAPI which bridges the Python backend
(ASR, AI, Storage) with the Vue 3 frontend via PyWebVue.
"""

import logging
import shutil
import sys
import threading
from pathlib import Path
from typing import Any

from pywebvue import App, Bridge
from py.config import ConfigStore, _DEFAULT_MODELS_DIR
from py.storage import Storage
from py.asr import SherpaASR
from py.llm import AIProcessor
from py.io import ensure_data_dir
from py.presets import AiPresetStore
from py.processing_presets import ProcessingPresetStore
from py import model_manager as _mm

from py.api import (
    AsrMixin,
    AiMixin,
    StorageMixin,
    ModelsMixin,
    OcrPluginMixin,
    ConfigBackupMixin,
)

logger = logging.getLogger(__name__)


class SherpaNoteAPI(
    AsrMixin,
    AiMixin,
    StorageMixin,
    ModelsMixin,
    OcrPluginMixin,
    ConfigBackupMixin,
    Bridge,
):
    """Main API bridging Python backend to Vue frontend.

    All public methods are decorated with @expose and return
    {"success": True, "data": ...} on success or
    {"success": False, "error": "..."} on failure (auto-handled).

    Backend-to-frontend events use self._emit(event, data).

    Domain logic is split across mixin classes:
      - AsrMixin: speech recognition, whisper.cpp, dependencies
      - AiMixin: AI processing, presets
      - StorageMixin: record CRUD, versions, audio files, import/export
      - ModelsMixin: ASR model management
      - OcrPluginMixin: OCR, plugin backends, document extraction
      - ConfigBackupMixin: config, backup/restore, file pickers
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
        self._ocr_engine: "OcrEngine | None" = None
        self._document_extractor = None
        self._plugin_manager = None
        self._ocr_cancel_event = threading.Event()
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
                raise RuntimeError("No streaming model found")
            self._asr._online_recognizer = self._asr._create_online_recognizer(sherpa_onnx, model_dir)
            logger.info("Online recognizer created successfully on main thread")
            return True

        elif command == "create_offline_recognizer":
            if self._asr is None:
                raise RuntimeError("ASR not initialized")
            if self._asr._offline_recognizer is not None:
                logger.info("Offline recognizer already exists, skipping")
                return True

            model_dir = self._asr._find_offline_model()
            if model_dir is None:
                raise RuntimeError("No offline model found")
            self._asr._offline_recognizer = self._asr._create_offline_recognizer(sherpa_onnx, model_dir)
            logger.info("Offline recognizer created successfully on main thread")
            return True

        logger.warning("Unknown dispatch command: %s", command)
        return None


if __name__ == "__main__":
    import faulthandler
    import logging
    import sys
    import traceback
    from pathlib import Path

    # Enable faulthandler to catch segfaults and other fatal errors
    if getattr(sys, "frozen", False):
        log_dir = Path(sys.executable).resolve().parent / "data" / "logs"
    else:
        log_dir = Path(__file__).parent / "data" / "logs"
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
    except Exception as exc:
        logging.critical("Application failed to start:", exc_info=True)
        raise
