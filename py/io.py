"""File I/O utilities for audio files.

Handles audio format detection, metadata extraction,
PCM format conversion, data directory management,
and PCM-to-WAV recording.
"""

from __future__ import annotations

import logging
import struct
import wave
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Supported audio extensions.
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"}


def is_audio_file(path: str) -> bool:
    """Check if a file path has a supported audio extension."""
    return Path(path).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def get_audio_metadata(path: str) -> dict[str, Any]:
    """Extract metadata from an audio file.

    Returns dict with 'duration', 'sample_rate', 'channels', 'format'.
    Falls back to empty values if soundfile cannot read the file.
    """
    try:
        import soundfile as sf

        info = sf.info(path)
        return {
            "duration": info.duration,
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "format": info.format,
            "subtype": info.subtype,
        }
    except Exception:
        return {"duration": 0, "sample_rate": 0, "channels": 0, "format": "", "subtype": ""}


def read_audio_as_mono_16k(path: str) -> tuple[np.ndarray, int]:
    """Read any audio file and convert to 16kHz mono float32 PCM.

    Tries soundfile first, falls back to audioread for formats
    like MP3 that soundfile may not support on some platforms.

    Args:
        path: Path to an audio file (wav, mp3, m4a, flac, ogg).

    Returns:
        Tuple of (samples, sample_rate) where samples is a 1-D float32
        numpy array at 16kHz.

    Raises:
        ValueError: If the file cannot be read by any decoder.
    """
    import soundfile as sf

    try:
        return _read_with_soundfile(path)
    except Exception as sf_exc:
        logger.info(
            "soundfile failed to read %s (%s), trying audioread fallback",
            path, sf_exc,
        )
        try:
            return _read_with_audioread(path)
        except Exception as ar_exc:
            logger.error(
                "Both decoders failed for %s. "
                "soundfile: %s | audioread: %s",
                path, sf_exc, ar_exc,
            )
            raise ValueError(
                f"Cannot read audio file: {path}. "
                f"Ensure ffmpeg is installed if the file is MP3/M4A. "
                f"soundfile error: {sf_exc} | audioread error: {ar_exc}"
            ) from sf_exc


def _read_with_soundfile(path: str) -> tuple[np.ndarray, int]:
    """Read audio using soundfile and convert to 16kHz mono float32."""
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=True)

    # Mix down to mono by averaging channels.
    if data.shape[1] > 1:
        data = data.mean(axis=1)
    else:
        data = data[:, 0]

    # Resample to 16kHz if needed.
    if sr != 16000:
        data = _resample(data, sr, 16000)
        sr = 16000

    return data, sr


def _read_with_audioread(path: str) -> tuple[np.ndarray, int]:
    """Read audio using audioread and convert to 16kHz mono float32.

    audioread delegates to system-level backends (ffmpeg, GStreamer,
    Media Foundation) and can handle formats that soundfile cannot
    (e.g., MP3 on Windows without MPG123).
    """
    import audioread

    with audioread.audio_open(path) as input_file:
        sr = input_file.samplerate
        channels = input_file.channels
        duration = input_file.duration

        # Read all frames as raw PCM bytes.
        buf = bytearray()
        for buf_in in input_file:
            buf.extend(buf_in)

    # Convert raw bytes to numpy array.
    # audioread outputs native PCM (int16 on most backends).
    raw = np.frombuffer(bytes(buf), dtype=np.int16)

    # Reshape to (frames, channels).
    if channels > 1:
        raw = raw.reshape(-1, channels).mean(axis=1)
    else:
        raw = raw.reshape(-1)

    # Convert int16 to float32 [-1, 1].
    data = raw.astype(np.float32) / 32767.0

    # Resample to 16kHz if needed.
    if sr != 16000:
        data = _resample(data, sr, 16000)
        sr = 16000

    logger.info(
        "Read audio via audioread: %s (%.1fs, %dHz, %dch)",
        path, duration, sr, channels,
    )
    return data, sr


def float32_to_int16(samples: np.ndarray) -> np.ndarray:
    """Convert float32 PCM (range [-1, 1]) to int16 PCM."""
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16)


def int16_to_float32(samples: np.ndarray) -> np.ndarray:
    """Convert int16 PCM to float32 PCM (range [-1, 1])."""
    return samples.astype(np.float32) / 32767.0


def base64_to_float32(base64_data: str) -> np.ndarray:
    """Decode Base64-encoded float32 PCM to numpy array.

    The frontend sends 16kHz mono float32 audio as Base64.
    """
    import base64

    raw = base64.b64decode(base64_data)
    return np.frombuffer(raw, dtype=np.float32).copy()


class PcmRecorder:
    """Accumulates float32 PCM chunks and writes a WAV file on close.

    Usage::

        rec = PcmRecorder(sample_rate=16000)
        rec.write_chunk(float32_array)
        audio_path = rec.close()  # writes WAV and returns path
    """

    def __init__(self, sample_rate: int = 16000, output_dir: str | None = None) -> None:
        self._sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._output_dir = output_dir

    def write_chunk(self, samples: np.ndarray) -> None:
        """Append a float32 PCM chunk (1-D array)."""
        self._chunks.append(samples.copy())

    def close(self) -> str | None:
        """Write all accumulated PCM data to a WAV file.

        Returns the file path, or None if no data was recorded.
        """
        if not self._chunks:
            return None

        all_samples = np.concatenate(self._chunks)
        self._chunks.clear()

        if self._output_dir is None:
            from py.config import _DEFAULT_DATA_DIR
            self._output_dir = str(Path(_DEFAULT_DATA_DIR) / "temp")

        Path(self._output_dir).mkdir(parents=True, exist_ok=True)

        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"
        path = str(Path(self._output_dir) / filename)

        # Convert float32 [-1, 1] to int16 PCM.
        int16_data = float32_to_int16(all_samples)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self._sample_rate)
            wf.writeframes(int16_data.tobytes())

        return path


def ensure_data_dir(data_dir: str) -> str:
    """Create data directory and subdirectories if they don't exist."""
    base = Path(data_dir)
    (base / "temp").mkdir(parents=True, exist_ok=True)
    (base / "audio").mkdir(parents=True, exist_ok=True)
    (base / "exports").mkdir(parents=True, exist_ok=True)
    return str(base)


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in file names."""
    for ch in ('/', '\\', ':', '*', '?', '"', '<', '>', '|'):
        name = name.replace(ch, "_")
    return name.strip(". ")


def convert_to_mono_16k_wav(input_path: str, output_path: str) -> str:
    """Convert any supported audio file to a 16kHz mono WAV file.

    Returns the path to the converted file.
    """
    samples, _ = read_audio_as_mono_16k(input_path)

    # Convert float32 [-1, 1] to int16 PCM.
    int16_data = float32_to_int16(samples)

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(16000)
        wf.writeframes(int16_data.tobytes())

    return output_path


# ---- internal helpers ----


def _resample(samples: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio using linear interpolation.

    This avoids requiring scipy or librosa as dependencies.
    For production quality, consider scipy.signal.resample instead.
    """
    if orig_sr == target_sr:
        return samples

    duration = len(samples) / orig_sr
    target_len = int(round(duration * target_sr))
    x_orig = np.linspace(0, 1, len(samples))
    x_target = np.linspace(0, 1, target_len)
    return np.interp(x_target, x_orig, samples).astype(np.float32)
