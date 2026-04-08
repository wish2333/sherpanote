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
        self._final_segments: list[dict[str, Any]] = []
        self._partial_text = ""
        self._segment_index = 0
        self._stream_start_time = 0.0
        self._pcm_recorder: PcmRecorder | None = None

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

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

        # 3. Search user models directory.
        base = self._model_dir()
        candidates = [
            base / "sherpa-onnx-streaming-paraformer-bilingual-zh-en",
            base / "sherpa-onnx-streaming-zipformer-en",
            base / "sherpa-onnx-streaming-zipformer-zh",
            base / "streaming",
        ]
        for c in candidates:
            if c.is_dir():
                return c
        # Also check if base itself contains a tokens.txt (flat layout).
        if (base / "tokens.txt").exists():
            return base
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

        # 3. Search user models directory.
        base = self._model_dir()
        candidates = [
            base / "sherpa-onnx-paraformer-zh",
            base / "sherpa-onnx-whisper-small",
            base / "sherpa-onnx-whisper-base",
            base / "sherpa-onnx-sense-voice-zh-en",
            base / "offline",
        ]
        for c in candidates:
            if c.is_dir():
                return c

        # 4. Scan for any subdirectory that contains a model file.
        if base.is_dir():
            for entry in sorted(base.iterdir()):
                if entry.is_dir() and entry not in candidates:
                    if (
                        (entry / "model.onnx").exists()
                        or (entry / "model.int8.onnx").exists()
                        or (entry / "encoder.onnx").exists()
                    ):
                        return entry

        if (base / "tokens.txt").exists():
            return base
        return None

    # ---- Streaming (OnlineRecognizer) ----

    def start_streaming(self) -> dict[str, Any]:
        """Initialize streaming session. Assumes recognizer already created.

        The online recognizer must have been created on the main thread
        via _create_online_recognizer before calling this method.

        Returns:
            dict with 'status' and 'language'.
        """
        # The recognizer should already exist (created on main thread)
        if self._online_recognizer is None:
            raise RuntimeError("Online recognizer not initialized. Must be created on main thread first.")

        # Use lock to protect state modifications (stream creation, flags, recorder)
        with self._lock:
            # Create a fresh stream for each recording session.
            self._online_stream = self._online_recognizer.create_stream()
            self._is_streaming = True
            self._final_segments = []
            self._partial_text = ""
            self._segment_index = 0
            self._stream_start_time = 0.0

            # Start recording PCM audio for later playback.
            from py.config import _DEFAULT_DATA_DIR
            audio_dir = str(Path(_DEFAULT_DATA_DIR) / "audio")
            self._pcm_recorder = PcmRecorder(sample_rate=self._config.sample_rate, output_dir=audio_dir)
            logger.info("Streaming session initialized")

        return {"status": "streaming", "language": self._config.language}

    def _create_online_recognizer(self, sherpa_onnx: Any, model_dir: Path) -> Any:
        """Create an OnlineRecognizer from the model directory.

        Detects model type (paraformer vs zipformer) based on
        which files are present.
        """
        import sys
        import traceback

        logger.info("_create_online_recognizer called with model_dir: %s", model_dir)
        logger.info("Python version: %s", sys.version)
        logger.info("Platform: %s", sys.platform)

        # Check for paraformer model files.
        paraformer_encoder = model_dir / "encoder.int8.onnx"
        if not paraformer_encoder.exists():
            paraformer_encoder = model_dir / "encoder.onnx"

        tokens = model_dir / "tokens.txt"
        if not tokens.exists():
            raise FileNotFoundError(f"tokens.txt not found in {model_dir}")

        num_threads = 2
        provider = "cpu"
        if self._config.use_gpu:
            # sherpa-onnx uses "cuda" for GPU inference.
            provider = "cuda"

        try:
            if paraformer_encoder.exists():
                # Paraformer streaming model.
                decoder = model_dir / "decoder.int8.onnx"
                if not decoder.exists():
                    decoder = model_dir / "decoder.onnx"
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
            else:
                # Transducer (zipformer) streaming model.
                encoder = model_dir / "encoder.onnx"
                decoder = model_dir / "decoder.onnx"
                joiner = model_dir / "joiner.onnx"
                if not all(f.exists() for f in (encoder, decoder, joiner)):
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
        except Exception as e:
            logger.error("Failed to create online recognizer: %s", e)
            logger.debug("Traceback: %s", traceback.format_exc())
            raise

    def feed_audio(self, base64_data: str) -> dict[str, Any]:
        """Decode a chunk of Base64-encoded float32 PCM audio.

        The frontend sends audio as 16kHz mono float32 PCM encoded
        in Base64. This method decodes it, feeds it to the recognizer,
        and returns the current partial/final results.

        Returns:
            dict with 'partial' (in-progress text) and
            'final' (list of finalized segments).
        """
        if not self._is_streaming or self._online_stream is None:
            return {"partial": "", "final": []}

        samples = base64_to_float32(base64_data)
        sample_rate = self._config.sample_rate

        # Record PCM for later playback.
        if self._pcm_recorder is not None:
            self._pcm_recorder.write_chunk(samples)

        # Feed audio into the stream.
        # Use lock to avoid concurrent modification with stop_streaming.
        with self._lock:
            self._online_stream.accept_waveform(sample_rate, samples)

            # Decode until the recognizer needs more input.
            while self._online_recognizer.is_ready(self._online_stream):
                self._online_recognizer.decode_stream(self._online_stream)

            # Get the current partial result.
            result = self._online_recognizer.get_result(self._online_stream)
            self._partial_text = result.strip()

            # Check if an endpoint was detected (sentence boundary).
            # When endpoint fires, the finalized text becomes a segment.
            if self._online_recognizer.is_endpoint(self._online_stream):
                if self._partial_text:
                    self._final_segments.append(
                        {
                            "index": self._segment_index,
                            "text": self._partial_text,
                            "start_time": 0.0,  # Approximate; precise timing needs timestamp model
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

    def stop_streaming(self) -> dict[str, Any]:
        """Finalize streaming and return the complete transcript.

        Returns:
            dict with 'text' (full transcript), 'segments' (list),
            and 'audio_path' (path to saved WAV file, if any).
        """
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
        1. Paraformer (model.int8.onnx or model.onnx, but not SenseVoice)
        2. SenseVoice (model.onnx when model dir name contains "sense-voice")
        3. Whisper (encoder.onnx + decoder.onnx)
        """
        tokens = model_dir / "tokens.txt"
        if not tokens.exists():
            raise FileNotFoundError(f"tokens.txt not found in {model_dir}")

        num_threads = 4
        provider = "cpu"
        if self._config.use_gpu:
            provider = "cuda"

        # Check for SenseVoice by directory name.
        dir_name = model_dir.name.lower()
        is_sense_voice = "sense-voice" in dir_name or "sensevoice" in dir_name

        # Try Paraformer model (model.int8.onnx takes priority).
        paraformer_model = model_dir / "model.int8.onnx"
        if not paraformer_model.exists():
            # model.onnx could be Paraformer or SenseVoice -- use dir name to decide.
            if not is_sense_voice:
                paraformer_model = model_dir / "model.onnx"
        if paraformer_model.exists():
            logger.info("Using Paraformer offline model (dir: %s)", model_dir.name)
            return sherpa_onnx.OfflineRecognizer.from_paraformer(
                tokens=str(tokens),
                paraformer=str(paraformer_model),
                num_threads=num_threads,
                provider=provider,
            )

        # Try SenseVoice model (only if directory name indicates SenseVoice).
        sense_voice_model = model_dir / "model.onnx"
        if is_sense_voice and sense_voice_model.exists():
            logger.info("Using SenseVoice offline model")
            return sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(sense_voice_model),
                tokens=str(tokens),
                num_threads=num_threads,
                use_itn=True,
                provider=provider,
            )

        # Fallback: try Whisper model.
        whisper_encoder = model_dir / "encoder.onnx"
        whisper_decoder = model_dir / "decoder.onnx"
        if whisper_encoder.exists() and whisper_decoder.exists():
            logger.info("Using Whisper offline model")
            return sherpa_onnx.OfflineRecognizer.from_whisper(
                tokens=str(tokens),
                encoder=str(whisper_encoder),
                decoder=str(whisper_decoder),
                num_threads=num_threads,
                provider=provider,
            )

        raise FileNotFoundError(
            f"No recognized offline model files in {model_dir}. "
            "Expected model.onnx (SenseVoice/Paraformer) or "
            "encoder.onnx + decoder.onnx (Whisper)."
        )

    def _create_vad(self, sherpa_onnx: Any, buffer_seconds: int = 600) -> Any:
        """Create a Voice Activity Detector for speech segmentation.

        Args:
            buffer_seconds: Must exceed the audio duration, otherwise
                the VAD discards sample data and produces 0-sample segments.
        """
        # Look for silero_vad.onnx in the model directory.
        vad_model = self._model_dir() / "silero_vad.onnx"
        if not vad_model.exists():
            # Fall back to sherpa-onnx built-in VAD asset path.
            # If not available, create a simple VAD with default config.
            try:
                vad_model = Path(sherpa_onnx.__file__).parent / "silero_vad.onnx"
            except Exception:
                pass

        config = sherpa_onnx.VadModelConfig()
        if vad_model.exists():
            config.silero_vad.model = str(vad_model)
        config.silero_vad.min_silence_duration = 0.25
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
        self._is_streaming = False
        self._pcm_recorder = None
        logger.info("ASR models released")
