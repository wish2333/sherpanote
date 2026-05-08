"""Model file matching and classification utilities.

Shared by asr.py and model_manager.py for finding model files
with prefixed or quantized variants, and for classifying model
directories by type (streaming / offline).
"""

from __future__ import annotations

from pathlib import Path

_QUANT = ("int8", "int4", "fp16", "fp32")


def match_model_file(actual_name: str, candidate: str) -> bool:
    """Check if *actual_name* matches *candidate* for model file lookup.

    Handles prefixed variants (e.g. ``"distil-large-v3.5-tokens.txt"``)
    and quantization suffixes (e.g. ``"encoder.int8.onnx"`` vs ``"encoder.onnx"``).

    Matching rules:

    * Extensions must match (e.g. ``.onnx``, ``.txt``).
    * If *candidate* specifies quantization (e.g. ``encoder.int8.onnx``),
      *actual* must have the same quantization.
    * Core name must appear at end of actual core name (allows prefix).
    """
    cand_parts = candidate.split(".")
    if len(cand_parts) < 2:
        return False
    cand_ext = cand_parts[-1]
    if len(cand_parts) == 2:
        cand_core, cand_quant = cand_parts[0], None
    elif len(cand_parts) == 3 and cand_parts[1] in _QUANT:
        cand_core, cand_quant = cand_parts[0], cand_parts[1]
    else:
        return actual_name.endswith(candidate)

    act_parts = actual_name.split(".")
    if len(act_parts) < 2 or act_parts[-1] != cand_ext:
        return False
    act_rest = act_parts[:-1]  # Everything before extension
    if len(act_rest) >= 2 and act_rest[-1] in _QUANT:
        act_quant = act_rest[-1]
        act_core = ".".join(act_rest[:-1])
    else:
        act_core = ".".join(act_rest)
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


def find_file(model_dir: Path, *candidates: str) -> Path | None:
    """Find the first matching model file in *model_dir* (recursive).

    Each candidate is tried as:

    1. Exact filename
    2. Prefixed variant (e.g. ``"distil-large-v3.5-tokens.txt"`` matches ``"tokens.txt"``)
    3. Quantized variant (e.g. ``"encoder.int8.onnx"`` matches ``"encoder.onnx"``)
    4. Prefixed + quantized (e.g. ``"distil-large-v3.5-encoder.int8.onnx"`` matches ``"encoder.onnx"``)

    Searches *model_dir* and one level of subdirectories.
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
                if f.is_file() and f.name != name and match_model_file(f.name, name):
                    return f
    return None


# ------------------------------------------------------------------ #
#  Model directory classification helpers                              #
# ------------------------------------------------------------------ #


def is_simulated_streaming_model(model_dir: Path) -> bool:
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


def is_sense_voice_dir(model_dir: Path) -> bool:
    """Check if a model directory is a SenseVoice model."""
    dir_name = model_dir.name.lower()
    return "sense-voice" in dir_name or "sensevoice" in dir_name


def find_tokenizer_dir(model_dir: Path) -> Path | None:
    """Find a tokenizer directory (containing vocab.json) in *model_dir*.

    Searches *model_dir* and one level of subdirectories.
    Used by Qwen3-ASR and FunASR Nano models.
    """
    if (model_dir / "vocab.json").exists():
        return model_dir
    for sub in model_dir.iterdir():
        if sub.is_dir() and not sub.name.startswith(".") and (sub / "vocab.json").exists():
            return sub
    return None


def has_model_files(model_dir: Path) -> bool:
    """Check if a directory looks like it contains a sherpa-onnx model.

    Searches *model_dir* and one level of subdirectories.
    """
    if find_file(model_dir, "tokens.txt"):
        return True
    if any(
        f.suffix == ".onnx"
        for f in model_dir.iterdir()
        if f.is_file()
    ):
        return True
    for sub in model_dir.iterdir():
        if sub.is_dir():
            if any(
                f.suffix == ".onnx"
                for f in sub.iterdir()
                if f.is_file()
            ):
                return True
    return False


def classify_model_dir(model_dir: Path) -> str | None:
    """Classify a model directory as ``'streaming'``, ``'offline'``, or ``None``.

    Uses file presence heuristics:

    * ``joiner.onnx`` present -> Transducer/Zipformer (always streaming)
    * ``model.onnx`` present -> Offline (Paraformer/SenseVoice)
    * ``conv_frontend.onnx`` present -> Offline (Qwen3-ASR)
    * ``encoder_adaptor.onnx`` or ``llm.onnx`` -> Offline (FunASR Nano)
    * encoder + decoder only (no joiner, no model) -> Ambiguous:
      dir name with ``"whisper"`` -> offline;
      dir name with ``"streaming"``/``"online"``/``"zipformer"`` -> streaming;
      default -> offline
    """
    has_joiner = find_file(model_dir, "joiner.onnx") is not None
    has_model = find_file(model_dir, "model.onnx", "model.int8.onnx") is not None
    has_encoder = find_file(model_dir, "encoder.onnx", "encoder.int8.onnx") is not None
    has_decoder = find_file(model_dir, "decoder.onnx", "decoder.int8.onnx") is not None
    has_conv_frontend = find_file(model_dir, "conv_frontend.onnx") is not None
    has_encoder_adaptor = find_file(model_dir, "encoder_adaptor.onnx", "encoder_adaptor.int8.onnx") is not None
    has_llm = find_file(model_dir, "llm.onnx", "llm.int8.onnx") is not None

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
