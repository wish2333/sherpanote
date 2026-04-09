"""Curated catalog of available sherpa-onnx ASR models.

Each ModelEntry contains metadata needed for download, validation,
and display in the UI. The catalog is a static list of frozen dataclasses
-- update this file when new models become available.

Download URL construction depends on the selected source:
    - github:    GitHub releases
    - huggingface / hf_mirror: HuggingFace / hf-mirror.com
    - ghproxy:   User-provided GitHub proxy domain
    - modelscope: ModelScope (Alibaba ecosystem, limited models)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GITHUB_BASE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
)

# HuggingFace author/org for sherpa-onnx models.
# Each model has its own repo: csukuangfj/{model_id}.
# The hf_repo_id field on ModelEntry can override this per model.
HF_REPO_AUTHOR = "csukuangfj"

# ModelScope repo for sherpa-onnx ASR models (Alibaba ecosystem).
MODELSCOPE_REPO_ID = "zhaochaoqun/sherpa-onnx-asr-models"


@dataclass(frozen=True)
class ModelEntry:
    """Metadata for a single downloadable model."""

    model_id: str
    display_name: str
    model_type: str  # "streaming" | "offline" | "vad" | "tool"
    languages: tuple[str, ...]
    size_mb: int
    archive_name: str
    description: str
    required_files: tuple[str, ...]
    sha256: str | None = None
    sources: tuple[str, ...] = ("github", "huggingface")
    hf_filename: str | None = None  # filename in HF repo, defaults to archive_name
    modelscope_file_path: str | None = None  # path within ModelScope repo
    hf_repo_id: str | None = None  # HuggingFace repo ID (e.g. "csukuangfj/vad"), defaults to "csukuangfj/{model_id}"
    manual_download_links: tuple[dict[str, str], ...] = ()


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
        sources=("github", "huggingface", "hf_mirror", "ghproxy"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
        display_name="Streaming Zipformer (Zh-En Bilingual)",
        model_type="streaming",
        languages=("zh", "en"),
        size_mb=850,
        archive_name="sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2",
        description="Streaming bilingual model using Zipformer transducer architecture.",
        required_files=("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"),
        sources=("github", "huggingface", "hf_mirror", "ghproxy"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-streaming-zipformer-small-ru-vosk-2025-08-16",
        display_name="Streaming Zipformer Small (Ru)",
        model_type="streaming",
        languages=("ru",),
        size_mb=45,
        archive_name="sherpa-onnx-streaming-zipformer-small-ru-vosk-2025-08-16.tar.bz2",
        description="Compact Russian streaming model. Based on Vosk data. Lightweight and fast.",
        required_files=("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"),
        sha256="cc2e99ed0c67cae8801170e7b7539b4cac00b716076af86f974bf5b888d9370c",
        sources=("github", "huggingface", "hf_mirror", "ghproxy"),
    ),
    # -- Offline models --
    ModelEntry(
        model_id="sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25",
        display_name="Qwen3-ASR 0.6B Int8",
        model_type="offline",
        languages=("zh", "en", "ja", "ko"),
        size_mb=390,
        archive_name="sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25.tar.bz2",
        description="Qwen3 ASR model with multilingual support (zh/en/ja/ko).",
        required_files=("conv_frontend.onnx", "encoder.int8.onnx", "decoder.int8.onnx"),
        sha256="393f8a14e2f5fb96746aaab342997a40641001fbd5bf9592a080a8329178ee96",
        sources=("github", "huggingface", "hf_mirror", "ghproxy"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-qwen3-asr-0.6B",
        display_name="Qwen3-ASR 0.6B (ModelScope)",
        model_type="offline",
        languages=("zh", "en", "ja", "ko"),
        size_mb=390,
        archive_name="Qwen3-ASR-0.6B.tar.bz2",
        description="Qwen3 ASR model from ModelScope. Multilingual support (zh/en/ja/ko).",
        required_files=("conv_frontend.onnx", "encoder.int8.onnx", "decoder.int8.onnx"),
        sources=("modelscope",),
        modelscope_file_path="Qwen3-ASR-0.6B.tar.bz2",
    ),
    ModelEntry(
        model_id="sherpa-onnx-qwen3-asr-1.7B",
        display_name="Qwen3-ASR 1.7B (ModelScope)",
        model_type="offline",
        languages=("zh", "en", "ja", "ko"),
        size_mb=1000,
        archive_name="Qwen3-ASR-1.7B.tar.bz2",
        description="Qwen3 ASR 1.7B model from ModelScope. Multilingual support (zh/en/ja/ko).",
        required_files=("conv_frontend.onnx", "encoder.int8.onnx", "decoder.int8.onnx"),
        sources=("modelscope",),
        modelscope_file_path="Qwen3-ASR-1.7B.tar.bz2",
    ),
    ModelEntry(
        model_id="sherpa-onnx-funasr-nano-int8-2025-12-30",
        display_name="FunASR Nano Int8",
        model_type="offline",
        languages=("zh", "en", "ja", "ko", "yue"),
        size_mb=240,
        archive_name="sherpa-onnx-funasr-nano-int8-2025-12-30.tar.bz2",
        description="FunASR Nano model with low-latency transcription. Multilingual (zh/en/ja/ko/yue).",
        required_files=("encoder_adaptor.int8.onnx", "llm.int8.onnx", "embedding.int8.onnx"),
        sources=("github", "huggingface", "hf_mirror", "ghproxy"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-sense-voice-funasr-nano-2025-12-17",
        display_name="SenseVoice FunASR Nano",
        model_type="offline",
        languages=("zh", "en", "ja", "ko", "yue"),
        size_mb=240,
        archive_name="sherpa-onnx-sense-voice-funasr-nano-2025-12-17.tar.bz2",
        description="Compact SenseVoice model with multilingual support (zh/en/ja/ko/yue). Fast and accurate.",
        required_files=("tokens.txt", "model.onnx"),
        sha256="426db3bf7d2cc0d083089e57054033682726041a9de0cf51aaf98723b9908681",
        sources=("github", "huggingface", "hf_mirror", "modelscope"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-whisper-distil-large-v3.5",
        display_name="Whisper Distil Large v3.5",
        model_type="offline",
        languages=("zh", "en", "ja", "ko", "de", "fr", "es", "it", "pt", "ru"),
        size_mb=780,
        archive_name="sherpa-onnx-whisper-distil-large-v3.5.tar.bz2",
        description="Distilled Whisper Large v3.5 with excellent multilingual accuracy.",
        required_files=("tokens.txt", "encoder.onnx", "decoder.onnx"),
        sha256="ec874c7346d24ef8063e05430ede616d66d80a410360283099d0bdf659187b1d",
        sources=("github", "huggingface", "hf_mirror", "ghproxy"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-whisper-distil-large-v3",
        display_name="Whisper Distil Large v3",
        model_type="offline",
        languages=("zh", "en", "ja", "ko", "de", "fr", "es", "it", "pt", "ru"),
        size_mb=780,
        archive_name="sherpa-onnx-whisper-distil-large-v3.tar.bz2",
        description="Distilled Whisper Large v3. Good multilingual accuracy with smaller size.",
        required_files=("tokens.txt", "encoder.onnx", "decoder.onnx"),
        sha256="3c13a06664e66708180baf98d17a35a7bc59b3f0f926c0e300445ce0789b5a73",
        sources=("github", "huggingface", "hf_mirror", "ghproxy"),
    ),
    ModelEntry(
        model_id="sherpa-onnx-paraformer-zh-small-2024-03-09",
        display_name="Paraformer-Zh Small",
        model_type="offline",
        languages=("zh",),
        size_mb=74,
        archive_name="sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2",
        description="Compact offline model for Chinese. Fast and lightweight.",
        required_files=("tokens.txt", "model.int8.onnx"),
        sources=("github", "huggingface", "hf_mirror", "modelscope"),
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
        sha256="9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6",
        sources=("github", "huggingface", "hf_mirror", "modelscope"),
        hf_repo_id="csukuangfj/vad",
    ),
    # -- Tools (manual download only, no in-app download) --
    ModelEntry(
        model_id="tool-generate-subtitles-sense-voice",
        display_name="Generate Subtitles (SenseVoice)",
        model_type="tool",
        languages=("zh", "en", "ko", "ja", "yue"),
        size_mb=0,
        archive_name="",
        description="Pre-built tool for generating subtitles using SenseVoice. Download and run separately.",
        required_files=(),
        manual_download_links=(
            {
                "label": "GitHub",
                "url": "https://k2-fsa.github.io/sherpa/onnx/lazarus/download-generated-subtitles-cn.html",
            },
        ),
        sources=(),
    ),
    ModelEntry(
        model_id="tool-generate-subtitles-paraformer",
        display_name="Generate Subtitles (Paraformer)",
        model_type="tool",
        languages=("zh", "en"),
        size_mb=0,
        archive_name="",
        description="Pre-built tool for generating subtitles using Paraformer. Download and run separately.",
        required_files=(),
        manual_download_links=(
            {
                "label": "GitHub",
                "url": "https://k2-fsa.github.io/sherpa/onnx/lazarus/download-generated-subtitles-cn.html",
            },
        ),
        sources=(),
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
        model_type: "streaming", "offline", "vad", "tool", or None for all.
    """
    if model_type is None:
        return list(MODELS)
    return [m for m in MODELS if m.model_type == model_type]


def get_download_url(
    model: ModelEntry,
    source: str = "github",
    ghproxy_domain: str | None = None,
) -> str:
    """Construct the download URL for a model based on the selected source.

    Args:
        model: The model entry.
        source: "github", "huggingface", "hf_mirror", "ghproxy", or "modelscope".
        ghproxy_domain: Required when source is "ghproxy", e.g. "https://ghproxy.link/abc123".

    Returns:
        The full download URL.

    Raises:
        ValueError: If the source is not supported by this model.
    """
    if source not in model.sources:
        raise ValueError(
            f"Source '{source}' is not available for model '{model.model_id}'. "
            f"Available sources: {', '.join(model.sources)}"
        )

    if source == "github":
        return f"{GITHUB_BASE_URL}{model.archive_name}"

    if source == "huggingface":
        filename = model.hf_filename or model.archive_name
        repo_id = model.hf_repo_id or f"{HF_REPO_AUTHOR}/{model.model_id}"
        return f"https://huggingface.co/{repo_id}/resolve/main/{filename}"

    if source == "hf_mirror":
        filename = model.hf_filename or model.archive_name
        repo_id = model.hf_repo_id or f"{HF_REPO_AUTHOR}/{model.model_id}"
        return f"https://hf-mirror.com/{repo_id}/resolve/main/{filename}"

    if source == "ghproxy":
        if not ghproxy_domain:
            raise ValueError("ghproxy_domain is required when source is 'ghproxy'")
        domain = ghproxy_domain.rstrip("/")
        return f"{domain}/https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{model.archive_name}"

    if source == "modelscope":
        if not model.modelscope_file_path:
            raise ValueError(
                f"Model '{model.model_id}' does not have a ModelScope file path configured"
            )
        return (
            f"https://modelscope.cn/api/v1/models/{MODELSCOPE_REPO_ID}"
            f"/repo?Revision=master&FilePath={model.modelscope_file_path}"
        )

    raise ValueError(f"Unknown download source: '{source}'")


def model_to_dict(model: ModelEntry) -> dict[str, Any]:
    """Serialize a ModelEntry for the frontend."""
    return {
        "model_id": model.model_id,
        "display_name": model.display_name,
        "model_type": model.model_type,
        "languages": list(model.languages),
        "size_mb": model.size_mb,
        "description": model.description,
        "sources": list(model.sources),
        "manual_download_links": list(model.manual_download_links),
    }
