"""ASR (Speech Recognition) API mixin.

Provides streaming recognition, file transcription, whisper.cpp
binary management, and dependency status methods.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from pywebvue import expose
from py.api.base import ApiBase
from py.config import AsrConfig
from py.asr import SherpaASR
from py import model_manager as _mm
from py import model_registry as _mr
from py.config import _DEFAULT_MODELS_DIR

if TYPE_CHECKING:
    from py.whispercpp import WhisperCppASR

logger = logging.getLogger(__name__)


class AsrMixin(ApiBase):
    """ASR-related @expose methods."""

    # ---- Internal helpers ----

    def _make_asr_config(self, language: str | None = None) -> AsrConfig:
        """Build an AsrConfig from the current persisted config."""
        cfg = self._api._config
        if language is None:
            language = cfg.asr.language or "auto"
        return AsrConfig(
            model_dir=cfg.asr.model_dir,
            language=language,
            sample_rate=cfg.asr.sample_rate,
            use_gpu=cfg.asr.use_gpu,
            active_streaming_model=cfg.asr.active_streaming_model,
            active_offline_model=cfg.asr.active_offline_model,
            auto_punctuate=cfg.asr.auto_punctuate,
            download_source=cfg.asr.download_source,
            custom_ghproxy_domain=cfg.asr.custom_ghproxy_domain,
            proxy_mode=cfg.asr.proxy_mode,
            proxy_url=cfg.asr.proxy_url,
            vad_min_silence_duration=cfg.asr.vad_min_silence_duration,
            vad_min_speech_duration=cfg.asr.vad_min_speech_duration,
            vad_max_speech_duration=cfg.asr.vad_max_speech_duration,
            vad_threshold=cfg.asr.vad_threshold,
            offline_use_vad=cfg.asr.offline_use_vad,
            vad_padding=cfg.asr.vad_padding,
            active_vad_model=cfg.asr.active_vad_model,
        )

    def _get_whisper_asr(self) -> WhisperCppASR | None:
        """Lazily initialize and return the WhisperCppASR instance."""
        if self._api._whisper_asr is None:
            from py.whispercpp import WhisperCppASR, WhisperCppConfig
            from py.whispercpp_registry import get_binary_path

            cfg = self._api._config
            data_dir = cfg.data_dir or str(Path(__file__).resolve().parents[2] / "data")
            binary_path = get_binary_path(data_dir)

            model_dir = Path(cfg.asr.model_dir or _DEFAULT_MODELS_DIR)
            model_id = cfg.asr.active_whisper_model or cfg.asr.active_offline_model
            model_path = ""
            if model_id and model_id.startswith("whisper-ggml-"):
                model_path = str(model_dir / model_id / f"ggml-{model_id.replace('whisper-ggml-', '')}.bin")

            if not model_path or not Path(model_path).exists():
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
                language=cfg.asr.language,
                threads=4,
            )
            self._api._whisper_asr = WhisperCppASR(config)

        return self._api._whisper_asr

    def _apply_punctuation(self, text: str) -> str:
        """Apply AI-based punctuation restoration if enabled."""
        cfg = self._api._config
        if not cfg.asr.auto_punctuate:
            return text
        if not cfg.ai.api_key and not cfg.ai.base_url:
            logger.warning("Auto-punctuate enabled but no AI configured, skipping")
            return text
        try:
            return self._api._get_ai().restore_punctuation(text)
        except Exception as exc:
            logger.warning("Punctuation restoration failed: %s, using raw text", exc)
            return text

    # ---- Exposed methods ----

    @expose
    def detect_gpu(self) -> dict:
        """Detect NVIDIA GPU and CUDA availability for sherpa-onnx."""
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
        """Initialize sherpa-onnx ASR model. Language: zh / en / auto."""
        asr_config = self._make_asr_config(language)
        self._api._asr = SherpaASR(asr_config)

        def _work() -> None:
            try:
                result = self._api._asr.start_streaming()
                self._emit("streaming_ready", result)
            except Exception as exc:
                self._emit("streaming_error", {"error": str(exc)})

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"language": language, "status": "loading"}}

    @expose
    def start_streaming(self) -> dict:
        """Start a streaming recognition session."""
        logger.info("start_streaming API called")
        if self._api._asr is None:
            self._api._asr = SherpaASR(self._make_asr_config())

        def _work() -> None:
            import traceback
            logger.info("Background thread started for start_streaming")
            logger.info("_asr: %s, _online_recognizer: %s", self._api._asr, getattr(self._api._asr, '_online_recognizer', 'N/A'))
            try:
                needs_creation = (
                    self._api._asr._online_recognizer is None
                    and not self._api._asr._is_simulated_streaming
                ) or (
                    self._api._asr._is_simulated_streaming
                    and self._api._asr._simulated_offline_recognizer is None
                )
                if needs_creation:
                    logger.info("Recognizer not yet created, will create on main thread")
                    self.run_on_main_thread("create_online_recognizer", timeout=60.0)
                    logger.info("Recognizer creation completed")
                else:
                    logger.info("Recognizer already exists, skipping creation")

                result = self._api._asr.start_streaming()
                self._api._last_emitted_final_count = 0
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
        if self._api._asr is None:
            logger.warning("feed_audio called but ASR not initialized")
            return {"success": False, "error": "ASR not initialized. Call start_streaming() first."}
        try:
            result = self._api._asr.feed_audio(base64_data)
            if result.get("partial"):
                self._emit("partial_result", {"text": result["partial"]})
            current_count = len(self._api._asr._final_segments)
            for i in range(self._api._last_emitted_final_count, current_count):
                seg = self._api._asr._final_segments[i]
                self._emit("final_result", {"text": seg["text"], "timestamp": []})
            self._api._last_emitted_final_count = current_count
            return {"success": True, "data": {"length": len(base64_data)}}
        except Exception as e:
            import traceback
            logger.error("feed_audio exception: %s", e)
            logger.debug("feed_audio traceback: %s", traceback.format_exc())
            return {"success": False, "error": str(e)}

    @expose
    def stop_streaming(self) -> dict:
        """End streaming recognition. Returns final transcript."""
        if self._api._asr is None:
            return {"success": False, "error": "No active streaming session."}
        result = self._api._asr.stop_streaming()
        return {"success": True, "data": result}

    @expose
    def transcribe_file(self, file_path: str) -> dict:
        """Transcribe an audio file. Progress pushed via _emit."""
        logger.info("transcribe_file called for: %s", file_path)

        use_whisper = self._api._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._api._asr is None:
            self._api._asr = SherpaASR(self._make_asr_config())

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
                    whisper = self._get_whisper_asr()
                    if whisper is None:
                        raise RuntimeError("whisper.cpp ASR not available")
                    logger.info("Starting whisper.cpp transcribe_file for: %s", file_path)
                    segments = whisper.transcribe_file(file_path, on_progress=on_progress)
                else:
                    if self._api._asr is None:
                        raise RuntimeError("sherpa-onnx ASR not initialized")
                    if self._api._asr._offline_recognizer is None:
                        logger.info("Scheduling offline recognizer creation on main thread")
                        self.run_on_main_thread("create_offline_recognizer", timeout=60.0)
                        logger.info("Offline recognizer creation completed")
                    logger.info("Starting transcribe_file for: %s", file_path)
                    segments = self._api._asr.transcribe_file(file_path, on_progress=on_progress)

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

    @expose
    def retranscribe_record(self, record_id: str) -> dict:
        """Re-transcribe the audio file associated with a record."""
        logger.info("retranscribe_record: record_id=%s", record_id)

        record = self._api._storage.get(record_id)
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

        use_whisper = self._api._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._api._asr is None:
            self._api._asr = SherpaASR(self._make_asr_config())

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
                    if self._api._asr is None:
                        raise RuntimeError("sherpa-onnx ASR not initialized")
                    logger.info("retranscribe_record: creating offline recognizer...")
                    if self._api._asr._offline_recognizer is None:
                        self.run_on_main_thread("create_offline_recognizer", timeout=60.0)
                    logger.info("retranscribe_record: transcribing file %s", audio_path)
                    segments = self._api._asr.transcribe_file(audio_path, on_progress=on_progress)
                full_text = " ".join(s["text"] for s in segments)
                full_text = self._apply_punctuation(full_text)
                logger.info("retranscribe_record: transcription done, %d segments, saving...", len(segments))
                updated = self._api._storage.save({
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

    # ---- whisper.cpp binary management ----

    @expose
    def get_whisper_binary_status(self) -> dict:
        """Check whisper.cpp binary installation status."""
        from py.whispercpp_registry import get_status

        data_dir = self._api._config.data_dir or str(Path(__file__).resolve().parents[2] / "data")
        status = get_status(data_dir)
        return {"success": True, "data": status}

    @expose
    def install_whisper_binary(self, variant: str | None = None) -> dict:
        """Download and install whisper.cpp binary for the current platform."""
        from py.whispercpp_registry import install_binary

        data_dir = self._api._config.data_dir or str(Path(__file__).resolve().parents[2] / "data")

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
            proxy_mode=self._api._config.asr.proxy_mode,
            proxy_url=self._api._config.asr.proxy_url,
        )
        if result.get("success"):
            return {"success": True, "data": result}
        return {"success": False, "error": result.get("error", "Unknown error")}

    @expose
    def uninstall_whisper_binary(self) -> dict:
        """Remove the installed whisper.cpp binary."""
        from py.whispercpp_registry import uninstall_binary

        data_dir = self._api._config.data_dir or str(Path(__file__).resolve().parents[2] / "data")
        removed = uninstall_binary(data_dir)
        return {"success": True, "data": {"removed": removed}}

    # ---- Dependency Management ----

    @expose
    def get_dependency_status(self) -> dict:
        """Check status of external dependencies (ffmpeg, yt-dlp)."""
        import os
        import shutil
        import platform as _platform
        import sys

        cfg = self._api._config
        ffmpeg_status: dict = {"installed": False, "source": "", "path": ""}

        user_ffmpeg = cfg.asr.ffmpeg_path if cfg.asr.ffmpeg_path else ""
        if user_ffmpeg:
            candidate = user_ffmpeg.strip()
            if os.path.isdir(candidate):
                exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
                candidate = os.path.join(candidate, exe)
            if os.path.isfile(candidate):
                ffmpeg_status = {"installed": True, "source": "custom", "path": candidate}

        machine = _platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            brew_paths = ["/opt/homebrew/bin/ffmpeg"]
        elif sys.platform == "darwin":
            brew_paths = ["/usr/local/bin/ffmpeg"]
        else:
            brew_paths = []
        for bp in brew_paths:
            if os.path.isfile(bp):
                ffmpeg_status = {"installed": True, "source": "homebrew", "path": bp}
                break

        if not ffmpeg_status["installed"]:
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                ffmpeg_status = {"installed": True, "source": "system", "path": ffmpeg_path}

        if not ffmpeg_status["installed"]:
            try:
                import static_ffmpeg
                pkg_dir = os.path.dirname(static_ffmpeg.__file__)
                if sys.platform == "darwin":
                    if machine in ("arm64", "aarch64"):
                        platform_key = "darwin_arm64"
                    else:
                        platform_key = "darwin_x86_64"
                elif sys.platform == "win32":
                    platform_key = "windows_x64"
                else:
                    platform_key = f"linux_{machine}"
                static_bin = os.path.join(pkg_dir, "bin", platform_key, "ffmpeg")
                if os.path.isfile(static_bin):
                    ffmpeg_status = {"installed": True, "source": "static-ffmpeg", "path": static_bin}
            except Exception:
                pass

        ytdlp_status: dict = {"installed": False, "version": ""}
        try:
            import yt_dlp
            ytdlp_status = {"installed": True, "version": yt_dlp.version.__version__}
        except Exception:
            pass

        return {
            "success": True,
            "data": {
                "ffmpeg": ffmpeg_status,
                "ytdlp": ytdlp_status,
            },
        }

    @expose
    def install_static_ffmpeg(self) -> dict:
        """Download static ffmpeg binaries via static_ffmpeg package."""
        try:
            import os
            import sys
            import shutil as _shutil
            import platform as _platform
            import static_ffmpeg
            static_ffmpeg.add_paths()

            ffmpeg_path = _shutil.which("ffmpeg")
            if not ffmpeg_path:
                pkg_dir = os.path.dirname(static_ffmpeg.__file__)
                machine = _platform.machine().lower()
                if sys.platform == "darwin":
                    platform_key = "darwin_arm64" if machine in ("arm64", "aarch64") else "darwin_x86_64"
                elif sys.platform == "win32":
                    platform_key = "windows_x64"
                else:
                    platform_key = f"linux_{machine}"
                candidate = os.path.join(pkg_dir, "bin", platform_key, "ffmpeg")
                if os.path.isfile(candidate):
                    ffmpeg_path = candidate

            if ffmpeg_path:
                return {"success": True, "data": {"path": ffmpeg_path, "source": "static-ffmpeg"}}
            return {"success": False, "error": "static_ffmpeg add_paths() succeeded but ffmpeg not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
