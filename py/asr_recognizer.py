"""Sherpa-onnx recognizer factory functions.

Extracted from SherpaASR to keep the main class under 800 lines.
Each function creates a specific recognizer type from a model directory.
"""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from typing import Any

from py.file_matcher import find_file as _find_file, find_tokenizer_dir, is_sense_voice_dir

logger = logging.getLogger(__name__)

_STREAMING_NUM_THREADS = 2
_OFFLINE_NUM_THREADS = 4


def create_online_recognizer(
    sherpa_onnx: Any,
    model_dir: Path,
    *,
    use_gpu: bool = False,
    sample_rate: int = 16000,
) -> Any:
    """Create an OnlineRecognizer from *model_dir*.

    Detects model type (Paraformer vs Zipformer) based on which files
    are present.  Supports prefixed filenames
    (e.g. ``distil-large-v3.5-encoder.int8.onnx``).
    """
    logger.info("create_online_recognizer called with model_dir: %s", model_dir)
    logger.info("Python version: %s", sys.version)
    logger.info("Platform: %s", sys.platform)

    joiner = _find_file(model_dir, "joiner.onnx")
    tokens = _find_file(model_dir, "tokens.txt")
    if not tokens:
        raise FileNotFoundError(f"tokens.txt not found in {model_dir}")

    num_threads = _STREAMING_NUM_THREADS
    provider = "cuda" if use_gpu else "cpu"

    try:
        if joiner and joiner.exists():
            # Transducer (zipformer) streaming model.
            encoder = _find_file(model_dir, "encoder.onnx")
            decoder = _find_file(model_dir, "decoder.onnx")
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
                sample_rate=sample_rate,
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
            paraformer_encoder = _find_file(model_dir, "encoder.int8.onnx", "encoder.onnx")
            if not paraformer_encoder or not paraformer_encoder.exists():
                raise FileNotFoundError(
                    f"Model files not found in {model_dir}. "
                    "Expected encoder.onnx and decoder.onnx"
                )
            decoder = _find_file(model_dir, "decoder.int8.onnx", "decoder.onnx")
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
                sample_rate=sample_rate,
                feature_dim=80,
                provider=provider,
            )
            logger.info("OnlineRecognizer created successfully (Paraformer)")
            return recognizer
    except Exception as e:
        logger.error("Failed to create online recognizer: %s", e)
        logger.debug("Traceback: %s", traceback.format_exc())
        raise


def create_offline_recognizer(
    sherpa_onnx: Any,
    model_dir: Path,
    *,
    use_gpu: bool = False,
    language: str = "auto",
) -> Any:
    """Create an OfflineRecognizer from *model_dir*.

    Model detection priority:

    1. Qwen3-ASR (``conv_frontend.onnx`` + encoder + decoder + tokenizer dir)
    2. FunASR Nano (``encoder_adaptor`` + llm + embedding + tokenizer dir)
    3. Paraformer (``model.int8.onnx`` or ``model.onnx``, but not SenseVoice)
    4. SenseVoice (``model.onnx`` when dir name contains ``"sense-voice"``)
    5. Whisper (``encoder.onnx`` + ``decoder.onnx``)

    Supports prefixed filenames (e.g. ``distil-large-v3.5-tokens.txt``).
    """
    num_threads = _OFFLINE_NUM_THREADS
    provider = "cuda" if use_gpu else "cpu"

    # --- Qwen3-ASR (conv_frontend.onnx) ---
    conv_frontend = _find_file(model_dir, "conv_frontend.onnx")
    if conv_frontend:
        encoder = _find_file(model_dir, "encoder.int8.onnx", "encoder.onnx")
        decoder = _find_file(model_dir, "decoder.int8.onnx", "decoder.onnx")
        tokenizer_dir = find_tokenizer_dir(model_dir)
        if encoder and decoder and tokenizer_dir:
            logger.info("Using Qwen3-ASR offline model (dir: %s)", model_dir.name)
            _Qwen3Config = sherpa_onnx.OfflineQwen3ASRModelConfig
            _orig_qwen3_init = _Qwen3Config.__init__
            _Qwen3Config.__init__ = lambda self, **kw: _orig_qwen3_init(
                self, **{k: v for k, v in kw.items() if k != "hotwords"}
            )
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
    encoder_adaptor = _find_file(model_dir, "encoder_adaptor.int8.onnx", "encoder_adaptor.onnx")
    llm = _find_file(model_dir, "llm.int8.onnx", "llm.onnx")
    if encoder_adaptor or llm:
        if not encoder_adaptor:
            encoder_adaptor = _find_file(model_dir, "encoder_adaptor.int8.onnx", "encoder_adaptor.onnx")
        if not llm:
            llm = _find_file(model_dir, "llm.int8.onnx", "llm.onnx")
        embedding = _find_file(model_dir, "embedding.int8.onnx", "embedding.onnx")
        tokenizer_dir = find_tokenizer_dir(model_dir)
        if encoder_adaptor and llm and embedding and tokenizer_dir:
            funasr_lang = language if language != "auto" else ""
            logger.info(
                "Using FunASR Nano offline model (dir: %s, lang: %s)",
                model_dir.name, funasr_lang or "auto-detect",
            )
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
    tokens = _find_file(model_dir, "tokens.txt")
    if not tokens:
        raise FileNotFoundError(f"tokens.txt not found in {model_dir}")

    is_sv = is_sense_voice_dir(model_dir)

    # Try Paraformer model (model.int8.onnx takes priority).
    # Skip if this is a SenseVoice model directory.
    paraformer_model = None if is_sv else _find_file(model_dir, "model.int8.onnx")
    if not paraformer_model and not is_sv:
        paraformer_model = _find_file(model_dir, "model.onnx")
    if paraformer_model:
        logger.info("Using Paraformer offline model (dir: %s)", model_dir.name)
        return sherpa_onnx.OfflineRecognizer.from_paraformer(
            tokens=str(tokens),
            paraformer=str(paraformer_model),
            num_threads=num_threads,
            provider=provider,
        )

    # Try SenseVoice model.
    sense_voice_model = _find_file(model_dir, "model.onnx", "model.int8.onnx")
    if is_sv and sense_voice_model:
        sv_lang = language if language != "auto" else ""
        logger.info("Using SenseVoice offline model (lang: %s)", sv_lang or "auto-detect")
        return sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(sense_voice_model),
            tokens=str(tokens),
            num_threads=num_threads,
            language=sv_lang,
            use_itn=True,
            provider=provider,
        )

    # Try Cohere Transcribe model.
    dir_name = model_dir.name.lower()
    if "cohere-transcribe" in dir_name or "cohere_transcribe" in dir_name:
        cohere_encoder = _find_file(model_dir, "encoder.int8.onnx", "encoder.onnx")
        cohere_decoder = _find_file(model_dir, "decoder.int8.onnx", "decoder.onnx")
        if cohere_encoder and cohere_decoder:
            _COHERE_LANG_MAP = {
                "zh": "zh", "en": "en", "ja": "ja", "ko": "ko",
                "de": "de", "fr": "fr", "es": "es", "it": "it",
                "pt": "pt", "ar": "ar", "nl": "nl", "pl": "pl",
                "el": "el", "vi": "vi",
            }
            cohere_lang = _COHERE_LANG_MAP.get(language, "en")
            logger.info(
                "Using Cohere Transcribe offline model (dir: %s, lang: %s)",
                model_dir.name, cohere_lang,
            )
            return sherpa_onnx.OfflineRecognizer.from_cohere_transcribe(
                encoder=str(cohere_encoder),
                decoder=str(cohere_decoder),
                tokens=str(tokens),
                num_threads=num_threads,
                language=cohere_lang,
                provider=provider,
            )

    # Fallback: try Whisper model.
    whisper_encoder = _find_file(model_dir, "encoder.onnx")
    whisper_decoder = _find_file(model_dir, "decoder.onnx")
    if whisper_encoder and whisper_decoder:
        whisper_lang = language if language != "auto" else ""
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


def create_vad(
    sherpa_onnx: Any,
    models_dir: Path,
    *,
    active_vad_model: str | None = None,
    vad_threshold: float = 0.5,
    vad_min_silence_duration: float = 0.5,
    vad_min_speech_duration: float = 0.25,
    vad_max_speech_duration: float = 60.0,
    buffer_seconds: int = 600,
    streaming: bool = False,
) -> Any:
    """Create a Voice Activity Detector for speech segmentation.

    Args:
        buffer_seconds: Must exceed the audio duration, otherwise
            the VAD discards sample data and produces 0-sample segments.
        streaming: If True, use longer min_silence_duration to avoid
            splitting sentences mid-utterance during real-time recognition.
    """
    if active_vad_model and active_vad_model != "auto":
        candidates = [active_vad_model + ".onnx"]
    else:
        candidates = ["silero_vad_v5.onnx", "silero_vad.onnx"]
    vad_model = None
    for filename in candidates:
        candidate = models_dir / filename
        if candidate.exists():
            vad_model = candidate
            break
    if vad_model is None:
        try:
            vad_model = Path(sherpa_onnx.__file__).parent / candidates[0]
        except Exception:
            pass

    config = sherpa_onnx.VadModelConfig()
    if vad_model is not None and vad_model.exists():
        config.silero_vad.model = str(vad_model)
    config.silero_vad.min_silence_duration = (
        vad_min_silence_duration * 1.6 if streaming
        else vad_min_silence_duration
    )
    config.silero_vad.min_speech_duration = vad_min_speech_duration
    config.silero_vad.max_speech_duration = vad_max_speech_duration
    config.silero_vad.threshold = vad_threshold
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
