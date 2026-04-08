# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "sherpa-onnx>=1.10.0",
#     "numpy>=1.24.0",
#     "soundfile>=0.12.0",
#     "audioread>=3.0.0",
# ]
# ///
"""sherpa-onnx diagnostic tool.

Standalone script to verify sherpa-onnx ASR functionality
independently from the main SherpaNote application.

Usage:
    uv run scripts/test_sherpa.py --script              # Scan models only
    uv run scripts/test_sherpa.py --script --file X.mp3 # Transcribe a file
    uv run scripts/test_sherpa.py --script --streaming  # Test streaming model
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sherpa-diag")


# ---- Model scanning ----

def find_models_dir() -> Path:
    """Resolve the default models directory."""
    # Check project root first (relative to this script).
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / "models",
        Path.home() / "sherpanote" / "models",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


STREAMING_MODEL_NAMES = [
    "sherpa-onnx-streaming-paraformer-bilingual-zh-en",
    "sherpa-onnx-streaming-zipformer-en",
    "sherpa-onnx-streaming-zipformer-zh",
    "streaming",
]

OFFLINE_MODEL_NAMES = [
    "sherpa-onnx-paraformer-zh",
    "sherpa-onnx-whisper-small",
    "sherpa-onnx-whisper-base",
    "sherpa-onnx-sense-voice-zh-en",
    "offline",
]


def scan_models(base: Path) -> dict[str, list[Path]]:
    """Scan for streaming and offline model directories."""
    streaming = []
    offline = []
    if not base.is_dir():
        log.warning("Models directory does not exist: %s", base)
        return {"streaming": streaming, "offline": offline}

    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name in STREAMING_MODEL_NAMES or (entry / "encoder.onnx").exists():
            streaming.append(entry)
        if name in OFFLINE_MODEL_NAMES or (entry / "model.onnx").exists() or (entry / "model.int8.onnx").exists():
            offline.append(entry)

    # Also check if base itself is a flat model dir.
    if (base / "tokens.txt").exists():
        if base not in streaming and base not in offline:
            if (base / "encoder.onnx").exists():
                streaming.append(base)
            if (base / "model.onnx").exists() or (base / "model.int8.onnx").exists():
                offline.append(base)

    return {"streaming": streaming, "offline": offline}


# ---- Audio reading (mirrors py/io.py) ----

def read_audio_as_mono_16k(path: str) -> tuple:
    """Read audio using soundfile + audioread fallback. Returns (samples, sr)."""
    import numpy as np

    # Try soundfile first.
    try:
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        if data.shape[1] > 1:
            data = data.mean(axis=1)
        else:
            data = data[:, 0]
        if sr != 16000:
            data = _resample(data, sr, 16000)
            sr = 16000
        log.info(
            "Read via soundfile: %s (%d samples, %dHz)",
            path, len(data), sr,
        )
        return data, sr
    except Exception as sf_exc:
        log.info("soundfile failed (%s), trying audioread...", sf_exc)

    # Fallback to audioread.
    try:
        import audioread
        with audioread.audio_open(path) as f:
            sr = f.samplerate
            channels = f.channels
            duration = f.duration
            buf = bytearray()
            for chunk in f:
                buf.extend(chunk)
        raw = np.frombuffer(bytes(buf), dtype=np.int16)
        if channels > 1:
            raw = raw.reshape(-1, channels).mean(axis=1)
        else:
            raw = raw.reshape(-1)
        data = raw.astype(np.float32) / 32767.0
        if sr != 16000:
            data = _resample(data, sr, 16000)
            sr = 16000
        log.info(
            "Read via audioread: %s (%.1fs, %dHz, %dch, %d samples)",
            path, duration, sr, channels, len(data),
        )
        return data, sr
    except Exception as ar_exc:
        log.error("audioread also failed: %s", ar_exc)
        raise ValueError(
            f"Cannot read audio: {path}.\n"
            f"  soundfile error: {sf_exc}\n"
            f"  audioread error: {ar_exc}\n"
            f"Suggestion: Install ffmpeg and ensure it is on your PATH.\n"
            f"  Windows: winget install ffmpeg | macOS: brew install ffmpeg"
        ) from sf_exc


def _resample(samples, orig_sr, target_sr):
    """Linear interpolation resample (mirrors py/io.py)."""
    import numpy as np
    if orig_sr == target_sr:
        return samples
    duration = len(samples) / orig_sr
    target_len = int(round(duration * target_sr))
    x_orig = np.linspace(0, 1, len(samples))
    x_target = np.linspace(0, 1, target_len)
    return np.interp(x_target, x_orig, samples).astype(np.float32)


# ---- Offline transcription test ----

def test_offline(model_dir: Path, audio_path: str) -> None:
    """Load offline model and transcribe an audio file."""
    import sherpa_onnx

    tokens = model_dir / "tokens.txt"
    if not tokens.exists():
        log.error("tokens.txt not found in %s", model_dir)
        sys.exit(1)

    # Create recognizer based on available model files.
    log.info("Creating offline recognizer from %s ...", model_dir)
    t0 = time.monotonic()

    sense_voice = model_dir / "model.onnx"
    paraformer = model_dir / "model.int8.onnx" if (model_dir / "model.int8.onnx").exists() else model_dir / "model.onnx"
    whisper_enc = model_dir / "encoder.onnx"
    whisper_dec = model_dir / "decoder.onnx"

    if sense_voice.exists() and not whisper_enc.exists():
        log.info("Detected SenseVoice model")
        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(sense_voice), tokens=str(tokens),
            num_threads=4, use_itn=True,
        )
    elif paraformer.exists():
        log.info("Detected Paraformer model")
        recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
            tokens=str(tokens), paraformer=str(paraformer),
            num_threads=4,
        )
    elif whisper_enc.exists() and whisper_dec.exists():
        log.info("Detected Whisper model")
        recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            tokens=str(tokens), encoder=str(whisper_enc), decoder=str(whisper_dec),
            num_threads=4,
        )
    else:
        log.error("No recognized model files in %s", model_dir)
        sys.exit(1)

    load_time = time.monotonic() - t0
    log.info("Model loaded in %.2fs", load_time)

    # Read audio.
    log.info("Reading audio file: %s", audio_path)
    t1 = time.monotonic()
    samples, sr = read_audio_as_mono_16k(audio_path)
    read_time = time.monotonic() - t1
    log.info(
        "Audio read in %.2fs: %d samples, %.1fs duration",
        read_time, len(samples), len(samples) / sr,
    )

    # Create VAD and segment.
    vad_model_path = find_models_dir() / "silero_vad.onnx"
    vad_config = sherpa_onnx.VadModelConfig()
    if vad_model_path.exists():
        vad_config.silero_vad.model = str(vad_model_path)
        log.info("Using VAD model: %s", vad_model_path)
    vad_config.silero_vad.min_silence_duration = 0.25
    vad_config.sample_rate = 16000

    # Buffer must be larger than the audio duration, otherwise the VAD
    # discards sample data while still tracking segment boundaries (0-sample segments).
    audio_duration = len(samples) / 16000
    buffer_seconds = int(audio_duration) + 60
    log.info("VAD buffer_size: %ds (audio: %.1fs)", buffer_seconds, audio_duration)

    vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=buffer_seconds)
    window_size = vad.config.silero_vad.window_size

    for i in range(0, len(samples), window_size):
        chunk = samples[i : i + window_size]
        if len(chunk) == window_size:
            vad.accept_waveform(chunk)

    num_speech_segments = 0
    while not vad.empty():
        speech = vad.front
        vad.pop()
        num_speech_segments += 1

    log.info("VAD detected %d speech segments", num_speech_segments)

    # Now transcribe.
    log.info("Starting transcription...")
    t2 = time.monotonic()

    # Re-create VAD for actual transcription.
    vad2 = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=buffer_seconds)
    for i in range(0, len(samples), window_size):
        chunk = samples[i : i + window_size]
        if len(chunk) == window_size:
            vad2.accept_waveform(chunk)

    segments = []
    seg_idx = 0
    empty_count = 0
    error_count = 0
    while not vad2.empty():
        speech = vad2.front

        # CRITICAL: Extract data BEFORE pop(). The pop() call invalidates
        # the underlying C++ object, making speech.samples become empty.
        speech_start = speech.start
        speech_samples = speech.samples

        # Inspect the speech object on first iteration.
        if seg_idx == 0:
            log.info("  speech object type: %s", type(speech))
            log.info("  speech attributes: %s", [a for a in dir(speech) if not a.startswith('_')])
            log.info("  speech.start = %s", speech_start)
            log.info("  speech.samples type: %s", type(speech_samples))
            log.info("  speech.samples len: %s", len(speech_samples))

        vad2.pop()

        if speech_samples is None or len(speech_samples) < 160:
            if seg_idx < 5:
                log.info("  [%d] skipped (samples=%s)", seg_idx,
                         len(speech_samples) if speech_samples is not None else 'None')
            seg_idx += 1
            continue

        try:
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, speech_samples)
            recognizer.decode_stream(stream)

            result = stream.result
            # Log result object for first segment.
            if seg_idx == 0:
                log.info("  [0] result type: %s", type(result))
                log.info("  [0] result dir: %s", [a for a in dir(result) if not a.startswith('_')])
                log.info("  [0] result repr: %s", repr(result))

            text = str(result.text).strip() if hasattr(result, 'text') else str(result).strip()
            if text:
                start_time = getattr(speech, 'start', 0)
                if isinstance(start_time, (int, float)):
                    start = start_time / 16000
                else:
                    try:
                        start = speech[0] / 16000
                    except Exception:
                        start = 0
                end = start + len(speech_samples) / 16000
                segments.append((seg_idx, start, end, text))
                if seg_idx < 10:
                    log.info("  [%d] %.2f-%.2f: %s", seg_idx, start, end, text)
            else:
                empty_count += 1
                if seg_idx < 3:
                    log.info("  [%d] empty text after decode", seg_idx)
        except Exception as e:
            error_count += 1
            log.error("  [%d] decode error: %s", seg_idx, e)

        seg_idx += 1

    infer_time = time.monotonic() - t2
    full_text = " ".join(s[3] for s in segments)

    log.info("--- Transcription Results ---")
    log.info("Total segments processed: %d", seg_idx)
    log.info("  With text: %d", len(segments))
    log.info("  Empty text: %d", empty_count)
    log.info("  Errors: %d", error_count)
    log.info("Total inference time: %.2fs", infer_time)
    log.info("Full text: %s", full_text if full_text else "(empty - no speech detected)")
    log.info("--- End Results ---")


# ---- Streaming test ----

def test_streaming(model_dir: Path) -> None:
    """Load streaming model and test with simulated audio chunks."""
    import sherpa_onnx
    import numpy as np

    tokens = model_dir / "tokens.txt"
    if not tokens.exists():
        log.error("tokens.txt not found in %s", model_dir)
        sys.exit(1)

    log.info("Creating streaming recognizer from %s ...", model_dir)
    t0 = time.monotonic()

    paraformer_enc = model_dir / "encoder.int8.onnx" if (model_dir / "encoder.int8.onnx").exists() else model_dir / "encoder.onnx"

    if paraformer_enc.exists():
        log.info("Detected streaming Paraformer model")
        decoder = model_dir / "decoder.int8.onnx" if (model_dir / "decoder.int8.onnx").exists() else model_dir / "decoder.onnx"
        recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
            tokens=str(tokens), encoder=str(paraformer_enc), decoder=str(decoder),
            num_threads=2, sample_rate=16000, feature_dim=80,
        )
    else:
        log.info("Detected streaming Zipformer (transducer) model")
        encoder = model_dir / "encoder.onnx"
        decoder = model_dir / "decoder.onnx"
        joiner = model_dir / "joiner.onnx"
        if not all(f.exists() for f in (encoder, decoder, joiner)):
            log.error("Missing model files in %s", model_dir)
            sys.exit(1)
        recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(tokens), encoder=str(encoder), decoder=str(decoder), joiner=str(joiner),
            num_threads=2, sample_rate=16000, feature_dim=80,
            enable_endpoint_detection=True,
        )

    load_time = time.monotonic() - t0
    log.info("Streaming model loaded in %.2fs", load_time)

    # Simulate feeding 2 seconds of silence (should not crash).
    log.info("Simulating audio input (2s of silence)...")
    stream = recognizer.create_stream()
    chunk_size = 4096
    total_samples = 16000 * 2  # 2 seconds at 16kHz
    chunks_fed = 0

    t1 = time.monotonic()
    for i in range(0, total_samples, chunk_size):
        chunk = np.zeros(min(chunk_size, total_samples - i), dtype=np.float32)
        stream.accept_waveform(16000, chunk)
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)
        chunks_fed += 1

    result = recognizer.get_result(stream).strip()
    total_time = time.monotonic() - t1
    log.info("Fed %d chunks in %.2fs", chunks_fed, total_time)
    log.info("Result text: '%s'", result if result else "(empty - expected for silence)")

    # Test endpoint detection.
    if recognizer.is_endpoint(stream):
        log.info("Endpoint detected after silence (expected)")
    else:
        log.info("No endpoint after 2s silence (may depend on model config)")

    log.info("--- Streaming test passed ---")


# ---- Main ----

def main() -> None:
    # Strip --script if passed by "uv run script.py --script" convention.
    if "--script" in sys.argv:
        sys.argv.remove("--script")

    parser = argparse.ArgumentParser(description="sherpa-onnx diagnostic tool")
    parser.add_argument("--file", type=str, help="Audio file to transcribe (offline)")
    parser.add_argument("--streaming", action="store_true", help="Test streaming model")
    parser.add_argument("--models-dir", type=str, default=None, help="Override models directory")
    args = parser.parse_args()

    # Check sherpa_onnx import.
    log.info("=== sherpa-onnx Diagnostic Tool ===")
    try:
        import sherpa_onnx
        log.info("sherpa_onnx version: %s", getattr(sherpa_onnx, "__version__", "unknown"))
        log.info("sherpa_onnx path: %s", sherpa_onnx.__file__)
    except ImportError as e:
        log.error("sherpa_onnx is not installed: %s", e)
        log.error("Install with: pip install sherpa-onnx")
        sys.exit(1)

    # Scan models.
    models_dir = Path(args.models_dir) if args.models_dir else find_models_dir()
    log.info("Models directory: %s", models_dir)
    found = scan_models(models_dir)

    log.info("Streaming models found: %d", len(found["streaming"]))
    for p in found["streaming"]:
        log.info("  - %s", p)

    log.info("Offline models found: %d", len(found["offline"]))
    for p in found["offline"]:
        log.info("  - %s", p)

    if args.file:
        if not found["offline"]:
            log.error("No offline model found. Cannot transcribe file.")
            log.error("Download a model and place it in: %s", models_dir)
            sys.exit(1)
        if not Path(args.file).exists():
            log.error("Audio file not found: %s", args.file)
            sys.exit(1)
        test_offline(found["offline"][0], args.file)

    if args.streaming:
        if not found["streaming"]:
            log.error("No streaming model found.")
            log.error("Download a model and place it in: %s", models_dir)
            sys.exit(1)
        test_streaming(found["streaming"][0])

    if not args.file and not args.streaming:
        log.info("(No --file or --streaming flag given. Only model scan performed.)")
        log.info("Usage examples:")
        log.info("  uv run scripts/test_sherpa.py --script --file lecture.mp3")
        log.info("  uv run scripts/test_sherpa.py --script --streaming")


if __name__ == "__main__":
    main()
