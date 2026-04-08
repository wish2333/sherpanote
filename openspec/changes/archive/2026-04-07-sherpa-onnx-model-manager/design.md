## Context

SherpaNote uses sherpa-onnx for local speech recognition. Currently, users must manually download ASR models from GitHub releases, extract them to `~/sherpanote/models/`, and configure the path in settings. The build system (PyInstaller) has no model bundling option.

Current state:
- `py/asr.py` has hardcoded candidate directory names for model discovery
- `py/config.py` has `AsrConfig.model_dir` (a raw path string)
- `frontend/src/views/SettingsView.vue` has a text input for the model directory path
- `build.py` and `app.spec` have no model-related configuration
- Models are hosted at `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/`

Constraints:
- Models are 70-230MB each (int8 quantized); users should choose which to download
- GitHub releases can be slow in China; Chinese mirrors should be supported
- PyInstaller onedir mode can bundle models; onefile mode should NOT (too large)
- sherpa-onnx expects specific directory structures per model type (Paraformer, Zipformer, SenseVoice, Whisper)

## Goals / Non-Goals

**Goals:**
- Provide an in-app model catalog with available ASR models (name, size, language, type)
- Enable one-click model download with progress reporting and verification
- Allow users to switch active ASR models without manual path editing
- Support optional model bundling during onedir build (`--with-models` flag)
- Support both GitHub and Chinese mirror download sources
- Verify model integrity after download (SHA256 checksum)

**Non-Goals:**
- Automatic model selection based on language detection
- Model fine-tuning or custom model support
- Cloud-based model hosting or CDN
- onefile build model bundling (models are too large for single-exe distribution)
- GPU-specific model variants (int8 models work on both CPU and GPU)

## Decisions

### D1: Model registry as a Python data file (not API)

**Decision**: Define the model catalog as a frozen dataclass list in `py/model_registry.py`.

**Alternatives**:
- Fetch from a remote API: Adds dependency on external service availability. Overkill for a small, slowly-changing catalog.
- JSON/YAML file: Extra file to manage; Python dataclass is more type-safe and co-located with the download logic.

**Rationale**: The catalog changes infrequently (new sherpa-onnx releases). A Python module with frozen dataclasses is simple, type-safe, and requires no network call to load the catalog.

### D2: Download using urllib (stdlib) instead of requests

**Decision**: Use `urllib.request` from the standard library for downloads.

**Alternatives**:
- `requests` library: More ergonomic but adds a dependency. The app currently has no `requests` dependency.
- `httpx`: Async support but unnecessary overhead for sequential model downloads.

**Rationale**: Avoid adding a new dependency. `urllib.request` supports chunked reads (needed for progress), custom headers, and redirect following. Progress reporting is done via a callback invoked per chunk.

### D3: Download source selection (GitHub vs mirror)

**Decision**: Default to GitHub releases. Provide a configurable mirror URL in config. The UI shows a dropdown for download source.

**Rationale**: GitHub is the canonical source. Chinese users can switch to a mirror (e.g., hf-mirror.com or a self-hosted URL) via settings. The mirror URL is stored in `AsrConfig`.

### D4: Model directory structure

**Decision**: Each model extracts into `~/sherpanote/models/<model-id>/` (e.g., `~/sherpanote/models/sherpa-onnx-streaming-paraformer-bilingual-zh-en/`). The VAD model (`silero_vad.onnx`) stays in `~/sherpanote/models/` (root level, not in a subdirectory).

**Rationale**: This matches the existing `_find_streaming_model()` and `_find_offline_model()` candidate paths in `py/asr.py`. No changes to model discovery logic needed.

### D5: Build-time bundling (onedir only)

**Decision**: Add `--with-models <model-id>[,<model-id>]` flag to `build.py`. When specified, the build script downloads selected models before PyInstaller runs and adds them to `app.spec` datas. Only supported in onedir mode.

**Rationale**: onefile bundles everything into a single exe which would make the file 500MB+ with models. onedir keeps models as separate files in the dist folder, which is more practical. The flag is optional so default builds remain small.

### D6: AsrConfig change - add active_model_id field

**Decision**: Add `active_streaming_model: str` and `active_offline_model: str` fields to `AsrConfig`. When set, the ASR engine uses these to find models instead of the candidate search. The existing `model_dir` field remains as the base models directory.

**Rationale**: This lets users explicitly select which model to use instead of relying on directory name discovery. Backward-compatible: if the new fields are empty, the existing candidate search is used.

### D7: Model integrity verification via SHA256

**Decision**: Each model registry entry includes an expected SHA256 hash. After download and extraction, verify the hash of the archive file.

**Rationale**: Models are large; corruption during download is possible. SHA256 catches this. The hash is checked against the `.tar.bz2` archive before extraction.

## Risks / Trade-offs

- **[Large downloads]** 70-230MB models may fail on slow/unstable connections -> Implement resume/partial download detection; show clear error on failure; allow retry
- **[GitHub rate limits]** Unauthenticated GitHub API has rate limits -> We download release assets directly (not via API), which has much higher limits. No API calls needed.
- **[Disk space]** Users may not have space for multiple models -> Show installed model sizes; warn before download if space is low
- **[Model compatibility]** sherpa-onnx version updates may break older models -> Pin to known-compatible model versions in the registry; note the sherpa-onnx version requirement per model
- **[Mirror reliability]** User-configured mirrors may go down -> Catch download errors and suggest switching back to GitHub source

## Migration Plan

- **Config migration**: `AsrConfig.from_dict()` already handles missing keys with defaults. The new `active_streaming_model` and `active_offline_model` fields default to empty string, so existing configs work without migration.
- **Model discovery**: Existing model directories continue to work. The new `active_model_id` fields are optional; when empty, the existing candidate search in `py/asr.py` is used.
- **Build system**: The `--with-models` flag is optional. Existing build commands work unchanged.

## Open Questions

- Should we include the VAD model (silero_vad.onnx, ~2MB) as an automatic download when any ASR model is downloaded? Currently it's searched for separately. -> **Yes**, auto-download VAD model with first ASR model download.
- Should the model registry support auto-update (fetch latest models from a remote source)? -> **Not in v1**. Manual registry updates via code changes. Can be added later.
