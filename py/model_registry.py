"""Curated catalog of available sherpa-onnx ASR models.

Each ModelEntry contains metadata needed for download, validation,
and display in the UI. The catalog is a static list of frozen dataclasses
-- update this file when new models become available.

Download URL pattern:
    {base_url}/{archive_name}

Where base_url defaults to:
    https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/
"""

from __future__ import annotations

from dataclasses import dataclass

GITHUB_BASE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
)


@dataclass(frozen=True)
class ModelEntry:
    """Metadata for a single downloadable model."""

    model_id: str
    display_name: str
    model_type: str  # "streaming" | "offline" | "vad"
    languages: tuple[str, ...]
    size_mb: int
    archive_name: str
    description: str
    required_files: tuple[str, ...]


# ------------------------------------------------------------------ #
#  Model catalog                                                       #
# ------------------------------------------------------------------ #

MODELS: tuple[ModelEntry, ...] = (
    # -- Streaming models --
    ModelEntry(
        model_id="sherpa-onnx-streaming-paraformer-bilingual-zh-en",
        display_name="Streaming Paraformer (Zh-En Bilingual)",
        model_type="streaming",
        languages=("zh", "en"),
        size_mb=999,
        archive_name="sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2",
        description="Streaming bilingual model for real-time recognition. Supports Chinese and English.",
        required_files=("tokens.txt", "encoder.int8.onnx", "decoder.int8.onnx"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en",
        display_name="Streaming Paraformer (Zh-Cantonese-En Trilingual)",
        model_type="streaming",
        languages=("zh", "cantonese", "en"),
        size_mb=999,
        archive_name="sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en.tar.bz2",
        description="Streaming trilingual model for real-time recognition. Supports Chinese, Cantonese, and English.",
        required_files=("tokens.txt", "encoder.int8.onnx", "decoder.int8.onnx"),
    ),
    # -- Offline models --
    ModelEntry(
        model_id="sherpa-onnx-paraformer-zh-small-2024-03-09",
        display_name="Paraformer-Zh Small",
        model_type="offline",
        languages=("zh",),
        size_mb=74,
        archive_name="sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2",
        description="Compact offline model for Chinese. Fast and lightweight.",
        required_files=("tokens.txt", "model.int8.onnx"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-paraformer-zh-2024-03-09",
        display_name="Paraformer-Zh",
        model_type="offline",
        languages=("zh",),
        size_mb=950,
        archive_name="sherpa-onnx-paraformer-zh-2024-03-09.tar.bz2",
        description="Full offline model for Chinese. Higher accuracy than small variant.",
        required_files=("tokens.txt", "model.int8.onnx"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-paraformer-zh-2023-09-14",
        display_name="Paraformer-Zh (With Timestamps)",
        model_type="offline",
        languages=("zh",),
        size_mb=223,
        archive_name="sherpa-onnx-paraformer-zh-2023-09-14.tar.bz2",
        description="Offline model for Chinese with timestamp support.",
        required_files=("tokens.txt", "model.int8.onnx"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-paraformer-zh-int8-2025-10-07",
        display_name="Paraformer-Zh Int8 (Sichuanese)",
        model_type="offline",
        languages=("zh",),
        size_mb=218,
        archive_name="sherpa-onnx-paraformer-zh-int8-2025-10-07.tar.bz2",
        description="Offline int8 model for Chinese including Sichuan dialect support.",
        required_files=("tokens.txt", "model.int8.onnx"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-paraformer-trilingual-zh-cantonese-en",
        display_name="Paraformer Trilingual (Zh-Cantonese-En)",
        model_type="offline",
        languages=("zh", "cantonese", "en"),
        size_mb=1010,
        archive_name="sherpa-onnx-paraformer-trilingual-zh-cantonese-en.tar.bz2",
        description="Full offline trilingual model. Supports Chinese, Cantonese, and English.",
        required_files=("tokens.txt", "model.int8.onnx"),
    ),
    # -- VAD model --
    ModelEntry(
        model_id="silero_vad",
        display_name="Silero VAD",
        model_type="vad",
        languages=(),
        size_mb=1,
        archive_name="silero_vad.onnx",
        description="Voice Activity Detection model. Required for file transcription. Auto-downloaded with first ASR model.",
        required_files=("silero_vad.onnx",),
    ),
)

# Index by model_id for fast lookup.
_MODEL_INDEX: dict[str, ModelEntry] = {m.model_id: m for m in MODELS}


# ------------------------------------------------------------------ #
#  Public API                                                          #
# ------------------------------------------------------------------ #


def get_model(model_id: str) -> ModelEntry | None:
    """Look up a model by its unique ID."""
    return _MODEL_INDEX.get(model_id)


def list_models(model_type: str | None = None) -> list[ModelEntry]:
    """Return all models, optionally filtered by type.

    Args:
        model_type: "streaming", "offline", or "vad". None returns all.
    """
    if model_type is None:
        return list(MODELS)
    return [m for m in MODELS if m.model_type == model_type]


def get_download_url(model: ModelEntry, mirror_url: str | None = None) -> str:
    """Construct the full download URL for a model.

    Args:
        model: The model entry.
        mirror_url: Optional custom mirror base URL. Falls back to GitHub.
    """
    base = mirror_url if mirror_url else GITHUB_BASE_URL
    return f"{base}{model.archive_name}"
