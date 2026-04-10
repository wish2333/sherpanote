"""sherpa-onnx speech recognition engine wrapper.

Provides both streaming (OnlineRecognizer) and file-based
(OfflineRecognizer) transcription. Models are lazy-loaded
on first use to keep startup fast.

Audio data from the frontend arrives as Base64-encoded float32 PCM.
The decoder runs in a background thread and pushes results
via callbacks (which the Bridge layer turns into _emit events).

Model management:
  - Streaming: sherpa-onnx-streaming-zipformer (en) or
    sherpa-onnx-streaming-paraformer-bilingual-zh-en
  - Offline: sherpa-onnx-paraformer-zh (zh) or
    sherpa-onnx-whisper (multilingual)
  - Models are stored in ~/sherpanote/models/
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np

from py.config import AsrConfig
from py.io import read_audio_as_mono_16k, base64_to_float32, float32_to_int16, _resample, PcmRecorder

logger = logging.getLogger(__name__)


class SherpaASR:
    """Wrapper around sherpa-onnx OnlineRecognizer / OfflineRecognizer.

    Usage:
        asr = SherpaASR(AsrConfig())
        asr.start_streaming()
        asr.feed_audio(base64_chunk)
        asr.stop_streaming()

        # or for file transcription:
        segments = asr.transcribe_file("lecture.mp3", on_progress=callback)
    """

    def __init__(self, config: AsrConfig) -> None:
        self._config = config
        self._online_recognizer: Any = None
        self._online_stream: Any = None
        self._offline_recognizer: Any = None
        self._lock = threading.Lock()
        self._is_streaming = False
        self._is_simulated_streaming = False
        self._final_segments: list[dict[str, Any]] = []
        self._partial_text = ""
        self._segment_index = 0
        self._stream_start_time = 0.0
        self._pcm_recorder: PcmRecorder | None = None
        # Simulated streaming (VAD + offline recognizer) state.
        self._simulated_vad: Any = None
        self._simulated_offline_recognizer: Any = None
        self._simulated_audio_buffer: np.ndarray | None = None

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    @staticmethod
    def _is_simulated_streaming_model(model_dir: Path) -> bool:
        """Check if a model supports simulated streaming (VAD + offline recognition).

        SenseVoice and Qwen3-ASR models are offline-only but can be used for
        near-real-time speech recognition by combining VAD with the offline recognizer.
        """
        dir_name = model_dir.name.lower()
        if "sense-voice" in dir_name or "sensevoice" in dir_name:
            return True
        if "qwen3-asr" in dir_name or "qwen3_asr" in dir_name:
            return True
        # Fallback: detect by characteristic file.
        if (model_dir / "conv_frontend.onnx").exists():
            return True
        return False

    @staticmethod
    def _is_sense_voice_dir(model_dir: Path) -> bool:
        """Check if a model directory is a SenseVoice model (used for offline detection)."""
        dir_name = model_dir.name.lower()
        return "sense-voice" in dir_name or "sensevoice" in dir_name

    # ---- Model file helpers ----

    @staticmethod
    def _find_file(model_dir: Path, *candidates: str) -> Path | None:
        """Find the first matching model file in model_dir (recursive).

        Each candidate is tried as:
        1. Exact filename
        2. Prefixed variant (e.g. "distil-large-v3.5-tokens.txt" matches "tokens.txt")
        3. Quantized variant (e.g. "encoder.int8.onnx" matches "encoder.onnx")
        4. Prefixed + quantized (e.g. "distil-large-v3.5-encoder.int8.onnx" matches "encoder.onnx")

        Searches model_dir and one level of subdirectories.
        """
        search_dirs = [model_dir]
        for sub in model_dir.iterdir():
            if sub.is_dir() and not sub.name.startswith("."):
                search_dirs.append(sub)

        for search_dir in search_dirs:
            for name in candidates:
                exact = search_dir / name
                if exact.exists():
                    return exact
                for f in search_dir.iterdir():
                    if f.is_file() and f.name != name and SherpaASR._match_model_file(f.name, name):
                        logger.debug("Found variant: %s -> %s", name, f.name)
                        return f
        return None

    @staticmethod
    def _match_model_file(actual_name: str, candidate: str) -> bool:
        """Check if actual_name matches candidate for model file lookup.

        Handles prefixed variants (e.g. "distil-large-v3.5-tokens.txt")
        and quantization suffixes (e.g. "encoder.int8.onnx" vs "encoder.onnx").

        Matching rules:
        - Extensions must match (e.g. .onnx, .txt)
        - If candidate specifies quantization (e.g. encoder.int8.onnx),
          actual must have the same quantization
        - Core name must appear at end of actual core name (allows prefix)
        """
        _QUANT = ('int8', 'int4', 'fp16', 'fp32')

        cand_parts = candidate.split('.')
        if len(cand_parts) < 2:
            return False
        cand_ext = cand_parts[-1]
        if len(cand_parts) == 2:
            cand_core, cand_quant = cand_parts[0], None
        elif len(cand_parts) == 3 and cand_parts[1] in _QUANT:
            cand_core, cand_quant = cand_parts[0], cand_parts[1]
        else:
            return actual_name.endswith(candidate)

        act_parts = actual_name.split('.')
        if len(act_parts) < 2 or act_parts[-1] != cand_ext:
            return False
        act_rest = act_parts[:-1]  # Everything before extension
        if len(act_rest) >= 2 and act_rest[-1] in _QUANT:
            act_quant = act_rest[-1]
            act_core = '.'.join(act_rest[:-1])
        else:
            act_core = '.'.join(act_rest)
            act_quant = None

        if cand_quant is not None and act_quant != cand_quant:
            return False
        # Match both suffix patterns (e.g. "encoder-epoch-99-avg-1")
        # and prefix patterns (e.g. "distil-large-v3.5-encoder").
        return (
            act_core == cand_core
            or act_core.startswith(cand_core + "-")
            or act_core.startswith(cand_core + "_")
            or act_core.endswith("-" + cand_core)
            or act_core.endswith("_" + cand_core)
        )

    @staticmethod
    def _find_tokenizer_dir(model_dir: Path) -> Path | None:
        """Find a tokenizer directory (containing vocab.json) in model_dir.

        Searches model_dir and one level of subdirectories.
        Used by Qwen3-ASR and FunASR Nano models.
        """
        # Check model_dir itself.
        if (model_dir / "vocab.json").exists():
            return model_dir
        # Check subdirectories.
        for sub in model_dir.iterdir():
            if sub.is_dir() and not sub.name.startswith(".") and (sub / "vocab.json").exists():
                return sub
        return None

    @staticmethod
    def _has_model_files(model_dir: Path) -> bool:
        """Check if a directory looks like it contains a sherpa-onnx model.

        Searches model_dir and one level of subdirectories.
        """
        if SherpaASR._find_file(model_dir, "tokens.txt"):
            return True
        # Check for any .onnx file in model_dir or subdirs.
        if any((model_dir / f).is_file() and f.endswith(".onnx")
               for f in model_dir.iterdir() if f.is_file()):
            return True
        for sub in model_dir.iterdir():
            if sub.is_dir():
                if any((sub / f).is_file() and f.endswith(".onnx")
                       for f in sub.iterdir() if f.is_file()):
                    return True
        return False

    @staticmethod
    def _classify_model_dir(model_dir: Path) -> str | None:
        """Classify a model directory as 'streaming', 'offline', or None.

        Uses file presence heuristics:
        - joiner.onnx present -> Transducer/Zipformer (always streaming)
        - model.onnx present -> Offline (Paraformer/SenseVoice)
        - conv_frontend.onnx present -> Offline (Qwen3-ASR)
        - encoder_adaptor.onnx or llm.onnx -> Offline (FunASR Nano)
        - encoder + decoder only (no joiner, no model) -> Ambiguous:
          dir name with "whisper" -> offline
          dir name with "streaming"/"online"/"zipformer" -> streaming
          default -> offline
        """
        has_joiner = SherpaASR._find_file(model_dir, "joiner.onnx") is not None
        has_model = SherpaASR._find_file(model_dir, "model.onnx", "model.int8.onnx") is not None
        has_encoder = SherpaASR._find_file(model_dir, "encoder.onnx", "encoder.int8.onnx") is not None
        has_decoder = SherpaASR._find_file(model_dir, "decoder.onnx", "decoder.int8.onnx") is not None
        has_conv_frontend = SherpaASR._find_file(model_dir, "conv_frontend.onnx") is not None
        has_encoder_adaptor = SherpaASR._find_file(model_dir, "encoder_adaptor.onnx", "encoder_adaptor.int8.onnx") is not None
        has_llm = SherpaASR._find_file(model_dir, "llm.onnx", "llm.int8.onnx") is not None

        if has_joiner:
            return "streaming"
        if has_model:
            return "offline"
        if has_conv_frontend:
            return "offline"
        if has_encoder_adaptor or has_llm:
            return "offline"
        if has_encoder and has_decoder:
            dir_name = model_dir.name.lower()
            if "whisper" in dir_name:
                return "offline"
            if any(kw in dir_name for kw in ("streaming", "online", "zipformer")):
                return "streaming"
            return "offline"
        return None

    # ---- Model paths ----

    def _model_dir(self) -> Path:
        """Resolve the model directory.

        Uses config.model_dir if set, otherwise falls back to
        <project_root>/models/. Also checks bundled models directory
        for PyInstaller onedir builds.
        """
        if self._config.model_dir:
            return Path(self._config.model_dir)
        from py.config import _DEFAULT_MODELS_DIR
        return Path(_DEFAULT_MODELS_DIR)

    def _bundled_models_dir(self) -> Path | None:
        """Check for bundled models in PyInstaller onedir builds."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            bundled = Path(sys._MEIPASS) / "models"
            if bundled.is_dir():
                return bundled
        return None

    def _all_model_dirs(self) -> list[Path]:
        """Return all model directories to search (user + bundled)."""
        dirs = [self._model_dir()]
        bundled = self._bundled_models_dir()
        if bundled:
            dirs.append(bundled)
        return dirs

    def _find_streaming_model(self) -> Path | None:
        """Find a streaming model directory. Returns None if not found."""
        # 1. Check actively configured model first.
        if self._config.active_streaming_model:
            for base in self._all_model_dirs():
                candidate = base / self._config.active_streaming_model
                if candidate.is_dir():
                    return candidate

        # 2. Check bundled models.
        bundled = self._bundled_models_dir()
        if bundled:
            for name in (
                "sherpa-onnx-streaming-paraformer-bilingual-zh-en",
                "sherpa-onnx-streaming-zipformer-en",
                "sherpa-onnx-streaming-zipformer-zh",
            ):
                candidate = bundled / name
                if candidate.is_dir():
                    return candidate

        # 3. Scan user models directory for streaming-classified models.
        base = self._model_dir()
        if base.is_dir():
            for entry in sorted(base.iterdir()):
                if entry.is_dir() and SherpaASR._classify_model_dir(entry) == "streaming":
                    return entry

        return None

    def _find_offline_model(self) -> Path | None:
        """Find an offline model directory. Returns None if not found."""
        # 1. Check actively configured model first.
        if self._config.active_offline_model:
            for base in self._all_model_dirs():
                candidate = base / self._config.active_offline_model
                if candidate.is_dir():
                    return candidate

        # 2. Check bundled models.
        bundled = self._bundled_models_dir()
        if bundled:
            for name in (
                "sherpa-onnx-paraformer-zh",
                "sherpa-onnx-whisper-small",
                "sherpa-onnx-whisper-base",
                "sherpa-onnx-sense-voice-zh-en",
            ):
                candidate = bundled / name
                if candidate.is_dir():
                    return candidate

        # 3. Scan user models directory for offline-classified models.
        base = self._model_dir()
        if base.is_dir():
            for entry in sorted(base.iterdir()):
                if entry.is_dir() and SherpaASR._classify_model_dir(entry) == "offline":
                    return entry

        return None

    # ---- Streaming (OnlineRecognizer) ----

    def start_streaming(self) -> dict[str, Any]:
        """Initialize streaming session.

        Supports two modes:
        - True streaming: uses OnlineRecognizer (Paraformer, Zipformer)
        - Simulated streaming: uses VAD + OfflineRecognizer (SenseVoice)

        The recognizer must have been created on the main thread before calling.

        Returns:
            dict with 'status' and 'language'.
        """
        if not self._is_simulated_streaming and self._online_recognizer is None:
            raise RuntimeError("Online recognizer not initialized. Must be created on main thread first.")
        if self._is_simulated_streaming and self._simulated_offline_recognizer is None:
            raise RuntimeError("Simulated streaming recognizer not initialized. Must be created on main thread first.")

        with self._lock:
            self._final_segments = []
            self._partial_text = ""
            self._segment_index = 0
            self._stream_start_time = 0.0
            self._is_streaming = True

            # Start recording PCM audio for later playback.
            from py.config import _DEFAULT_DATA_DIR
            audio_dir = str(Path(_DEFAULT_DATA_DIR) / "audio")
            self._pcm_recorder = PcmRecorder(sample_rate=self._config.sample_rate, output_dir=audio_dir)

            if self._is_simulated_streaming:
                # Reset VAD state for new session.
                if self._simulated_vad is not None:
                    try:
                        self._simulated_vad.clear()
                    except AttributeError:
                        logger.debug("VAD clear() not available (older sherpa-onnx version)")
                self._simulated_audio_buffer = None
                logger.info("Simulated streaming session initialized (VAD + offline)")
            else:
                self._online_stream = self._online_recognizer.create_stream()
                logger.info("Streaming session initialized")

        return {"status": "streaming", "language": self._config.language}

    def _create_online_recognizer(self, sherpa_onnx: Any, model_dir: Path) -> Any:
        """Create an OnlineRecognizer from the model directory.

        Detects model type (paraformer vs zipformer) based on
        which files are present. Supports prefixed filenames
        (e.g. distil-large-v3.5-encoder.int8.onnx).
        """
        import sys
        import traceback

        logger.info("_create_online_recognizer called with model_dir: %s", model_dir)
        logger.info("Python version: %s", sys.version)
        logger.info("Platform: %s", sys.platform)

        # Determine model type: check for joiner.onnx first (Zipformer/Transducer)
        # to avoid misclassifying Zipformer models as Paraformer.
        joiner = self._find_file(model_dir, "joiner.onnx")

        tokens = self._find_file(model_dir, "tokens.txt")
        if not tokens:
            raise FileNotFoundError(f"tokens.txt not found in {model_dir}")

        num_threads = 2
        provider = "cpu"
        if self._config.use_gpu:
            # sherpa-onnx uses "cuda" for GPU inference.
            provider = "cuda"

        try:
            if joiner and joiner.exists():
                # Transducer (zipformer) streaming model.
                encoder = self._find_file(model_dir, "encoder.onnx")
                decoder = self._find_file(model_dir, "decoder.onnx")
                if not all(f and f.exists() for f in (encoder, decoder)):
                    raise FileNotFoundError(
                        f"Model files not found in {model_dir}. "
                        "Expected encoder.onnx, decoder.onnx, joiner.onnx"
                    )
                logger.info("Using streaming Zipformer (transducer) model")
                recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                    tokens=str(tokens),
                    encoder=str(encoder),
                    decoder=str(decoder),
                    joiner=str(joiner),
                    num_threads=num_threads,
                    sample_rate=self._config.sample_rate,
                    feature_dim=80,
                    enable_endpoint_detection=True,
                    rule1_min_trailing_silence=2.4,
                    rule2_min_trailing_silence=1.0,
                    rule3_min_utterance_length=20.0,
                    provider=provider,
                )
                logger.info("OnlineRecognizer created successfully (Zipformer)")
                return recognizer
            else:
                # Paraformer streaming model (no joiner.onnx).
                paraformer_encoder = self._find_file(model_dir, "encoder.int8.onnx", "encoder.onnx")
                if not paraformer_encoder or not paraformer_encoder.exists():
                    raise FileNotFoundError(
                        f"Model files not found in {model_dir}. "
                        "Expected encoder.onnx and decoder.onnx"
                    )
                decoder = self._find_file(model_dir, "decoder.int8.onnx", "decoder.onnx")
                logger.info("Using streaming Paraformer model")
                logger.info("Creating OnlineRecognizer.from_paraformer with:")
                logger.info("  tokens: %s", tokens)
                logger.info("  encoder: %s", paraformer_encoder)
                logger.info("  decoder: %s", decoder)
                logger.info("  provider: %s", provider)

                recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
                    tokens=str(tokens),
                    encoder=str(paraformer_encoder),
                    decoder=str(decoder),
                    num_threads=num_threads,
                    sample_rate=self._config.sample_rate,
                    feature_dim=80,
                    provider=provider,
                )
                logger.info("OnlineRecognizer created successfully (Paraformer)")
                return recognizer
        except Exception as e:
            logger.error("Failed to create online recognizer: %s", e)
            logger.debug("Traceback: %s", traceback.format_exc())
            raise

    def feed_audio(self, base64_data: str) -> dict[str, Any]:
        """Decode a chunk of Base64-encoded float32 PCM audio.

        Routes to true streaming or simulated streaming based on model type.

        Returns:
            dict with 'partial' (in-progress text) and
            'final' (list of finalized segments).
        """
        if not self._is_streaming:
            return {"partial": "", "final": []}

        samples = base64_to_float32(base64_data)

        # Record PCM for later playback.
        if self._pcm_recorder is not None:
            self._pcm_recorder.write_chunk(samples)

        if self._is_simulated_streaming:
            return self._feed_audio_simulated(samples)

        if self._online_stream is None:
            return {"partial": "", "final": []}

        return self._feed_audio_online(samples)

    def _feed_audio_online(self, samples: np.ndarray) -> dict[str, Any]:
        """Feed audio chunk to OnlineRecognizer (true streaming)."""
        sample_rate = self._config.sample_rate

        with self._lock:
            self._online_stream.accept_waveform(sample_rate, samples)

            while self._online_recognizer.is_ready(self._online_stream):
                self._online_recognizer.decode_stream(self._online_stream)

            result = self._online_recognizer.get_result(self._online_stream)
            self._partial_text = result.strip()

            if self._online_recognizer.is_endpoint(self._online_stream):
                if self._partial_text:
                    self._final_segments.append(
                        {
                            "index": self._segment_index,
                            "text": self._partial_text,
                            "start_time": 0.0,
                            "end_time": 0.0,
                            "speaker": None,
                            "is_final": True,
                        }
                    )
                    self._segment_index += 1
                self._partial_text = ""
                self._online_recognizer.reset(self._online_stream)

        return {
            "partial": self._partial_text,
            "final": list(self._final_segments),
        }

    def _feed_audio_simulated(self, samples: np.ndarray) -> dict[str, Any]:
        """Feed audio chunk to VAD + OfflineRecognizer (simulated streaming).

        Audio is buffered through VAD in window-sized chunks. When VAD
        detects a completed speech segment, it is transcribed immediately.
        """
        with self._lock:
            vad = self._simulated_vad
            if vad is None or self._simulated_offline_recognizer is None:
                return {"partial": "", "final": []}

            # Prepend any leftover samples from the previous call.
            if self._simulated_audio_buffer is not None:
                samples = np.concatenate([self._simulated_audio_buffer, samples])
                self._simulated_audio_buffer = None

            window_size = vad.config.silero_vad.window_size

            # Feed full window-sized chunks to VAD.
            offset = 0
            while offset + window_size <= len(samples):
                vad.accept_waveform(samples[offset : offset + window_size])
                offset += window_size

            # Keep remainder for the next call.
            if offset < len(samples):
                self._simulated_audio_buffer = samples[offset:]

            # Process any completed speech segments.
            self._process_vad_segments()

        return {"partial": "", "final": list(self._final_segments)}

    def _pad_segment(self, samples, start_sample: int, total_samples: int = 0) -> tuple:
        """Add silence padding around a VAD segment for better recognition.

        Args:
            samples: speech segment samples (list or ndarray).
            start_sample: sample index where the segment starts.
            total_samples: total audio length (0 if unknown).

        Returns (padded_samples, adjusted_start_sample).
        """
        padding = int(self._config.vad_padding * 16000)
        if padding <= 0:
            return samples, start_sample
        pad_before = min(padding, start_sample)
        pad_after = padding
        if total_samples > 0:
            pad_after = min(padding, total_samples - start_sample - len(samples))
        arr = np.array(samples, dtype=np.float32) if not isinstance(samples, np.ndarray) else samples
        padded = np.zeros(len(arr) + pad_before + pad_after, dtype=np.float32)
        padded[pad_before:pad_before + len(arr)] = arr
        return padded, start_sample - pad_before

    def _process_vad_segments(self) -> None:
        """Transcribe all completed VAD speech segments.

        Must be called while holding self._lock.
        """
        vad = self._simulated_vad
        recognizer = self._simulated_offline_recognizer

        while not vad.empty():
            speech = vad.front
            speech_samples = speech.samples
            speech_start = speech.start
            vad.pop()

            if len(speech_samples) < 160:
                continue

            speech_samples, speech_start = self._pad_segment(speech_samples, speech_start)

            try:
                stream = recognizer.create_stream()
                stream.accept_waveform(16000, speech_samples)
                recognizer.decode_stream(stream)
                text = stream.result.text.strip()
            except Exception as exc:
                logger.warning("Failed to transcribe VAD segment: %s", exc)
                continue

            if text:
                self._final_segments.append(
                    {
                        "index": self._segment_index,
                        "text": text,
                        "start_time": round(speech_start / 16000, 2),
                        "end_time": round((speech_start + len(speech_samples)) / 16000, 2),
                        "speaker": None,
                        "is_final": True,
                    }
                )
                self._segment_index += 1

    def stop_streaming(self) -> dict[str, Any]:
        """Finalize streaming and return the complete transcript.

        Returns:
            dict with 'text' (full transcript), 'segments' (list),
            and 'audio_path' (path to saved WAV file, if any).
        """
        if self._is_simulated_streaming:
            return self._stop_streaming_simulated()

        with self._lock:
            if self._online_stream is None:
                self._is_streaming = False
                return {"text": "", "segments": [], "audio_path": None}

            # Signal end of input (method depends on recognizer type).
            # Zipformer (transducer) requires input_finished(), Paraformer does not.
            if hasattr(self._online_recognizer, 'input_finished'):
                self._online_recognizer.input_finished(self._online_stream)

            # Decode any remaining audio.
            while self._online_recognizer.is_ready(self._online_stream):
                self._online_recognizer.decode_stream(self._online_stream)

            final_text = self._online_recognizer.get_result(self._online_stream).strip()

            # Add any remaining partial as the last segment.
            if final_text:
                self._final_segments.append(
                    {
                        "index": self._segment_index,
                        "text": final_text,
                        "start_time": 0.0,
                        "end_time": 0.0,
                        "speaker": None,
                        "is_final": True,
                    }
                )

            self._is_streaming = False
            full_text = " ".join(s["text"] for s in self._final_segments)

            # Save recorded audio to WAV file.
            audio_path = None
            if self._pcm_recorder is not None:
                audio_path = self._pcm_recorder.close()
                self._pcm_recorder = None

        return {
            "text": full_text,
            "segments": self._final_segments,
            "audio_path": audio_path,
        }

    def _stop_streaming_simulated(self) -> dict[str, Any]:
        """Finalize simulated streaming: flush VAD and transcribe remaining audio."""
        with self._lock:
            if self._simulated_vad is None:
                self._is_streaming = False
                return {"text": "", "segments": [], "audio_path": None}

            # Feed any remaining buffered audio to VAD.
            if self._simulated_audio_buffer is not None and len(self._simulated_audio_buffer) > 0:
                vad = self._simulated_vad
                window_size = vad.config.silero_vad.window_size
                buf = self._simulated_audio_buffer
                self._simulated_audio_buffer = None
                # Feed all buffered audio in window-sized chunks.
                offset = 0
                while offset < len(buf):
                    chunk = buf[offset : offset + window_size]
                    if len(chunk) < window_size:
                        padded = np.zeros(window_size, dtype=np.float32)
                        padded[: len(chunk)] = chunk
                        chunk = padded
                    vad.accept_waveform(chunk)
                    offset += window_size

            # Flush VAD to force detection of the final segment.
            try:
                self._simulated_vad.flush()
            except AttributeError:
                logger.debug("VAD flush() not available (older sherpa-onnx version)")

            # Process any remaining segments.
            self._process_vad_segments()

            self._is_streaming = False
            full_text = " ".join(s["text"] for s in self._final_segments)

            # Save recorded audio to WAV file.
            audio_path = None
            if self._pcm_recorder is not None:
                audio_path = self._pcm_recorder.close()
                self._pcm_recorder = None

        return {
            "text": full_text,
            "segments": self._final_segments,
            "audio_path": audio_path,
        }

    # ---- File transcription (OfflineRecognizer) ----

    def transcribe_file(
        self,
        path: str,
        on_progress: Callable[[int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Transcribe an audio file using the offline recognizer.

        The offline recognizer must have been created on the main thread
        via _create_offline_recognizer before calling this method.

        Uses VAD (Voice Activity Detection) to split the audio
        into speech segments, then transcribes each segment.
        Progress is reported via the on_progress callback.

        Args:
            path: Path to the audio file (mp3, wav, m4a, flac).
            on_progress: Callback invoked with percent (0-100).

        Returns:
            List of segment dicts with 'text', 'start_time', 'end_time'.
        """
        import sherpa_onnx

        # Ensure recognizer exists (should be created on main thread)
        if self._offline_recognizer is None:
            raise RuntimeError("Offline recognizer not initialized. Must be created on main thread first.")

        # Read and convert audio to 16kHz mono float32.
        samples, sr = read_audio_as_mono_16k(path)
        total_duration = len(samples) / sr

        if not self._config.offline_use_vad:
            logger.info("offline_use_vad=False, transcribing entire audio without VAD segmentation")
            # Transcribe entire audio without VAD segmentation.
            if on_progress:
                on_progress(20)
            stream = self._offline_recognizer.create_stream()
            stream.accept_waveform(16000, samples)
            self._offline_recognizer.decode_stream(stream)
            text = stream.result.text.strip()
            if on_progress:
                on_progress(100)
            if text:
                return [
                    {
                        "index": 0,
                        "text": text,
                        "start_time": 0.0,
                        "end_time": round(total_duration, 2),
                        "speaker": None,
                        "is_final": True,
                    }
                ]
            return []

        # Use VAD to segment speech regions.
        # Buffer must exceed audio duration to avoid 0-sample segments.
        vad_buffer = int(total_duration) + 60
        vad = self._create_vad(sherpa_onnx, buffer_seconds=vad_buffer)
        window_size = vad.config.silero_vad.window_size

        # Feed audio to VAD in window-sized chunks.
        for i in range(0, len(samples), window_size):
            chunk = samples[i : i + window_size]
            if len(chunk) == window_size:
                vad.accept_waveform(chunk)

        if on_progress:
            on_progress(20)

        # Transcribe each speech segment.
        segments: list[dict[str, Any]] = []
        segment_idx = 0

        while not vad.empty():
            speech = vad.front

            # Extract data BEFORE pop() -- pop() invalidates the
            # underlying C++ object, making speech.samples empty.
            speech_samples = speech.samples
            speech_start = speech.start
            vad.pop()

            if len(speech_samples) < 160:  # Skip very short segments (< 10ms).
                continue

            speech_samples, speech_start = self._pad_segment(speech_samples, speech_start, total_samples=len(samples))

            stream = self._offline_recognizer.create_stream()
            stream.accept_waveform(16000, speech_samples)
            self._offline_recognizer.decode_stream(stream)

            text = stream.result.text.strip()
            if text:
                start_time = speech_start / 16000
                end_time = start_time + len(speech_samples) / 16000
                segments.append(
                    {
                        "index": segment_idx,
                        "text": text,
                        "start_time": round(start_time, 2),
                        "end_time": round(end_time, 2),
                        "speaker": None,
                        "is_final": True,
                    }
                )

            segment_idx += 1

            # Report progress (20-90 range for transcription phase).
            if on_progress and segment_idx % 3 == 0:
                progress = 20 + int(70 * min(segment_idx / max(segment_idx + 5, 1), 1.0))
                on_progress(min(progress, 90))

        if on_progress:
            on_progress(100)

        return segments

    def _create_offline_recognizer(self, sherpa_onnx: Any, model_dir: Path) -> Any:
        """Create an OfflineRecognizer from the model directory.

        Model detection priority:
        1. Qwen3-ASR (conv_frontend.onnx + encoder + decoder + tokenizer dir)
        2. FunASR Nano (encoder_adaptor + llm + embedding + tokenizer dir)
        3. Paraformer (model.int8.onnx or model.onnx, but not SenseVoice)
        4. SenseVoice (model.onnx when model dir name contains "sense-voice")
        5. Whisper (encoder.onnx + decoder.onnx)

        Supports prefixed filenames (e.g. distil-large-v3.5-tokens.txt).
        """
        num_threads = 4
        provider = "cpu"
        if self._config.use_gpu:
            provider = "cuda"

        # --- Qwen3-ASR (conv_frontend.onnx) ---
        conv_frontend = self._find_file(model_dir, "conv_frontend.onnx")
        if conv_frontend:
            encoder = self._find_file(model_dir, "encoder.int8.onnx", "encoder.onnx")
            decoder = self._find_file(model_dir, "decoder.int8.onnx", "decoder.onnx")
            tokenizer_dir = self._find_tokenizer_dir(model_dir)
            if encoder and decoder and tokenizer_dir:
                logger.info("Using Qwen3-ASR offline model (dir: %s)", model_dir.name)
                # Patch: from_qwen3_asr passes 'hotwords' to OfflineQwen3ASRModelConfig
                # which doesn't accept it. Strip it before calling.
                _Qwen3Config = sherpa_onnx.OfflineQwen3ASRModelConfig
                _orig_qwen3_init = _Qwen3Config.__init__
                _Qwen3Config.__init__ = lambda self, **kw: _orig_qwen3_init(self, **{k: v for k, v in kw.items() if k != "hotwords"})
                try:
                    return sherpa_onnx.OfflineRecognizer.from_qwen3_asr(
                        conv_frontend=str(conv_frontend),
                        encoder=str(encoder),
                        decoder=str(decoder),
                        tokenizer=str(tokenizer_dir),
                        num_threads=num_threads,
                        provider=provider,
                        max_total_len=512,
                        max_new_tokens=128,
                    )
                finally:
                    _Qwen3Config.__init__ = _orig_qwen3_init

        # --- FunASR Nano (encoder_adaptor.onnx or llm.onnx) ---
        encoder_adaptor = self._find_file(model_dir, "encoder_adaptor.int8.onnx", "encoder_adaptor.onnx")
        llm = self._find_file(model_dir, "llm.int8.onnx", "llm.onnx")
        if encoder_adaptor or llm:
            if not encoder_adaptor:
                encoder_adaptor = self._find_file(model_dir, "encoder_adaptor.int8.onnx", "encoder_adaptor.onnx")
            if not llm:
                llm = self._find_file(model_dir, "llm.int8.onnx", "llm.onnx")
            embedding = self._find_file(model_dir, "embedding.int8.onnx", "embedding.onnx")
            tokenizer_dir = self._find_tokenizer_dir(model_dir)
            if encoder_adaptor and llm and embedding and tokenizer_dir:
                funasr_lang = self._config.language if self._config.language != "auto" else ""
                logger.info("Using FunASR Nano offline model (dir: %s, lang: %s)", model_dir.name, funasr_lang or "auto-detect")
                return sherpa_onnx.OfflineRecognizer.from_funasr_nano(
                    encoder_adaptor=str(encoder_adaptor),
                    llm=str(llm),
                    embedding=str(embedding),
                    tokenizer=str(tokenizer_dir),
                    num_threads=num_threads,
                    language=funasr_lang,
                    provider=provider,
                )

        # --- Paraformer / SenseVoice / Whisper (require tokens.txt) ---
        tokens = self._find_file(model_dir, "tokens.txt")
        if not tokens:
            raise FileNotFoundError(f"tokens.txt not found in {model_dir}")

        # Check for SenseVoice by directory name.
        is_sense_voice = self._is_sense_voice_dir(model_dir)

        # Try Paraformer model (model.int8.onnx takes priority).
        # Skip if this is a SenseVoice model directory — SenseVoice also uses model.int8.onnx.
        paraformer_model = None if is_sense_voice else self._find_file(model_dir, "model.int8.onnx")
        if not paraformer_model:
            # model.onnx could be Paraformer or SenseVoice -- use dir name to decide.
            if not is_sense_voice:
                paraformer_model = self._find_file(model_dir, "model.onnx")
        if paraformer_model:
            logger.info("Using Paraformer offline model (dir: %s)", model_dir.name)
            return sherpa_onnx.OfflineRecognizer.from_paraformer(
                tokens=str(tokens),
                paraformer=str(paraformer_model),
                num_threads=num_threads,
                provider=provider,
            )

        # Try SenseVoice model (only if directory name indicates SenseVoice).
        sense_voice_model = self._find_file(model_dir, "model.onnx", "model.int8.onnx")
        if is_sense_voice and sense_voice_model:
            sv_lang = self._config.language if self._config.language != "auto" else ""
            logger.info("Using SenseVoice offline model (lang: %s)", sv_lang or "auto-detect")
            return sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(sense_voice_model),
                tokens=str(tokens),
                num_threads=num_threads,
                language=sv_lang,
                use_itn=True,
                provider=provider,
            )

        # Try Cohere Transcribe model (cohere-transcribe in dir name, encoder + decoder + tokens).
        dir_name = model_dir.name.lower()
        if "cohere-transcribe" in dir_name or "cohere_transcribe" in dir_name:
            cohere_encoder = self._find_file(model_dir, "encoder.int8.onnx", "encoder.onnx")
            cohere_decoder = self._find_file(model_dir, "decoder.int8.onnx", "decoder.onnx")
            if cohere_encoder and cohere_decoder:
                # Map config language to cohere-transcribe language code.
                _COHERE_LANG_MAP = {
                    "zh": "zh", "en": "en", "ja": "ja", "ko": "ko",
                    "de": "de", "fr": "fr", "es": "es", "it": "it",
                    "pt": "pt", "ar": "ar", "nl": "nl", "pl": "pl",
                    "el": "el", "vi": "vi",
                }
                cohere_lang = _COHERE_LANG_MAP.get(self._config.language, "en")
                logger.info("Using Cohere Transcribe offline model (dir: %s, lang: %s)", model_dir.name, cohere_lang)
                return sherpa_onnx.OfflineRecognizer.from_cohere_transcribe(
                    encoder=str(cohere_encoder),
                    decoder=str(cohere_decoder),
                    tokens=str(tokens),
                    num_threads=num_threads,
                    language=cohere_lang,
                    provider=provider,
                )

        # Fallback: try Whisper model.
        whisper_encoder = self._find_file(model_dir, "encoder.onnx")
        whisper_decoder = self._find_file(model_dir, "decoder.onnx")
        if whisper_encoder and whisper_decoder:
            # Pass user-configured language so Whisper transcribes in the
            # correct language instead of defaulting to English.
            whisper_lang = self._config.language if self._config.language != "auto" else ""
            logger.info("Using Whisper offline model (lang: %s)", whisper_lang or "auto-detect")
            return sherpa_onnx.OfflineRecognizer.from_whisper(
                tokens=str(tokens),
                encoder=str(whisper_encoder),
                decoder=str(whisper_decoder),
                num_threads=num_threads,
                language=whisper_lang,
                task="transcribe",
                provider=provider,
            )

        raise FileNotFoundError(
            f"No recognized offline model files in {model_dir}. "
            "Expected model.onnx (SenseVoice/Paraformer) or "
            "encoder.onnx + decoder.onnx (Whisper)."
        )

    def _create_vad(self, sherpa_onnx: Any, buffer_seconds: int = 600, *, streaming: bool = False) -> Any:
        """Create a Voice Activity Detector for speech segmentation.

        Args:
            buffer_seconds: Must exceed the audio duration, otherwise
                the VAD discards sample data and produces 0-sample segments.
            streaming: If True, use longer min_silence_duration to avoid
                splitting sentences mid-utterance during real-time recognition.
        """
        # Look for the configured VAD model in the model directory.
        # Auto-detect: prefer v5, fall back to v4.
        models_dir = self._model_dir()
        if self._config.active_vad_model and self._config.active_vad_model != "auto":
            candidates = [self._config.active_vad_model + ".onnx"]
        else:
            candidates = ["silero_vad_v5.onnx", "silero_vad.onnx"]
        vad_model = None
        for filename in candidates:
            candidate = models_dir / filename
            if candidate.exists():
                vad_model = candidate
                break
        if vad_model is None:
            # Fall back to sherpa-onnx built-in VAD asset path.
            try:
                vad_model = Path(sherpa_onnx.__file__).parent / candidates[0]
            except Exception:
                pass

        config = sherpa_onnx.VadModelConfig()
        if vad_model is not None and vad_model.exists():
            config.silero_vad.model = str(vad_model)
        # For streaming: use a multiplier on the user's setting to allow
        # longer pauses without cutting sentences mid-phrase.
        config.silero_vad.min_silence_duration = (
            self._config.vad_min_silence_duration * 1.6 if streaming
            else self._config.vad_min_silence_duration
        )
        config.silero_vad.min_speech_duration = self._config.vad_min_speech_duration
        config.silero_vad.max_speech_duration = self._config.vad_max_speech_duration
        config.silero_vad.threshold = self._config.vad_threshold
        logger.info(
            "VAD config: threshold=%.2f, min_silence=%.2fs, min_speech=%.2fs, "
            "max_speech=%.1fs, model=%s, streaming=%s",
            config.silero_vad.threshold, config.silero_vad.min_silence_duration,
            config.silero_vad.min_speech_duration, config.silero_vad.max_speech_duration,
            vad_model.name if vad_model and vad_model.exists() else "builtin/default",
            streaming,
        )
        config.sample_rate = 16000

        return sherpa_onnx.VoiceActivityDetector(
            config, buffer_size_in_seconds=buffer_seconds
        )

    # ---- Cleanup ----

    def cleanup(self) -> None:
        """Release model resources to free memory."""
        self._online_recognizer = None
        self._online_stream = None
        self._offline_recognizer = None
        self._simulated_vad = None
        self._simulated_offline_recognizer = None
        self._is_streaming = False
        self._is_simulated_streaming = False
        self._simulated_audio_buffer = None
        self._pcm_recorder = None
        logger.info("ASR models released")
