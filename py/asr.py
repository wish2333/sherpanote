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
from py.file_matcher import (
    classify_model_dir as _classify_model_dir,
)
from py.asr_recognizer import (
    create_online_recognizer as _create_online_recognizer_impl,
    create_offline_recognizer as _create_offline_recognizer_impl,
    create_vad as _create_vad_impl,
)
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

    # ---- Model detection helpers are in py.file_matcher ----

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
                if entry.is_dir() and _classify_model_dir(entry) == "streaming":
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
                if entry.is_dir() and _classify_model_dir(entry) == "offline":
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
        """Create an OnlineRecognizer from the model directory."""
        return _create_online_recognizer_impl(
            sherpa_onnx, model_dir,
            use_gpu=self._config.use_gpu,
            sample_rate=self._config.sample_rate,
        )

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
        on_progress: Callable[[int, dict[str, Any] | None], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Transcribe an audio file using the offline recognizer.

        The offline recognizer must have been created on the main thread
        via _create_offline_recognizer before calling this method.

        Uses VAD (Voice Activity Detection) to split the audio
        into speech segments, then transcribes each segment.
        Progress is reported via the on_progress callback.

        Args:
            path: Path to the audio file (mp3, wav, m4a, flac).
            on_progress: Callback(percent, info) where info is optional
                dict with 'current' and 'total' segment counts.

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
                on_progress(20, {"current": 0, "total": 1})
            stream = self._offline_recognizer.create_stream()
            stream.accept_waveform(16000, samples)
            self._offline_recognizer.decode_stream(stream)
            text = stream.result.text.strip()
            if on_progress:
                on_progress(100, {"current": 1, "total": 1})
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
            on_progress(20, None)

        # Pre-drain all VAD segments to get total count for accurate progress.
        vad_segments: list[tuple[Any, int]] = []
        while not vad.empty():
            speech = vad.front
            # Extract data BEFORE pop() -- pop() invalidates the
            # underlying C++ object, making speech.samples empty.
            speech_samples = speech.samples
            speech_start = speech.start
            vad.pop()
            if len(speech_samples) < 160:  # Skip very short segments (< 10ms).
                continue
            vad_segments.append((speech_samples, speech_start))

        total_segments = len(vad_segments)

        # Transcribe each speech segment.
        segments: list[dict[str, Any]] = []
        segment_idx = 0

        for speech_samples, speech_start in vad_segments:
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

            # Report progress with segment info (20-90 range for transcription phase).
            if on_progress and total_segments > 0:
                progress = 20 + int(70 * segment_idx / total_segments)
                on_progress(
                    min(progress, 90),
                    {"current": segment_idx, "total": total_segments},
                )

        if on_progress:
            on_progress(100, {"current": total_segments, "total": total_segments})

        return segments

    def _create_offline_recognizer(self, sherpa_onnx: Any, model_dir: Path) -> Any:
        """Create an OfflineRecognizer from the model directory."""
        return _create_offline_recognizer_impl(
            sherpa_onnx, model_dir,
            use_gpu=self._config.use_gpu,
            language=self._config.language,
        )

    def _create_vad(self, sherpa_onnx: Any, buffer_seconds: int = 600, *, streaming: bool = False) -> Any:
        """Create a Voice Activity Detector for speech segmentation."""
        return _create_vad_impl(
            sherpa_onnx, self._model_dir(),
            active_vad_model=self._config.active_vad_model,
            vad_threshold=self._config.vad_threshold,
            vad_min_silence_duration=self._config.vad_min_silence_duration,
            vad_min_speech_duration=self._config.vad_min_speech_duration,
            vad_max_speech_duration=self._config.vad_max_speech_duration,
            buffer_seconds=buffer_seconds,
            streaming=streaming,
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
