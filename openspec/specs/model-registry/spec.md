## ADDED Requirements

### Requirement: Model registry provides curated catalog of ASR models
The system SHALL maintain a curated catalog of available sherpa-onnx ASR models as frozen dataclasses in `py/model_registry.py`. Each model entry SHALL include: `model_id` (unique string, matching directory name), `display_name` (human-readable), `model_type` (streaming/offline), `languages` (list of supported language codes), `size_mb` (approximate download size in MB), `archive_url` (relative path under the download base URL), `sha256` (expected checksum of the archive), `required_files` (list of files that MUST exist after extraction for model validation), and `description` (brief description of the model).

#### Scenario: Registry contains bilingual streaming paraformer
- **WHEN** the model registry is loaded
- **THEN** it SHALL contain an entry for `sherpa-onnx-streaming-paraformer-bilingual-zh-en` with `model_type` = "streaming", `languages` = ["zh", "en"], and a valid `archive_url`

#### Scenario: Registry contains offline paraformer models
- **WHEN** the model registry is loaded
- **THEN** it SHALL contain entries for at minimum: `sherpa-onnx-paraformer-zh-2024-03-09` (offline, zh), `sherpa-onnx-paraformer-zh-small-2024-03-09` (offline, zh, small), and `sherpa-onnx-paraformer-zh-en-2023-09-14` (offline, zh+en, with timestamps)

#### Scenario: Registry contains VAD model entry
- **WHEN** the model registry is loaded
- **THEN** it SHALL contain a special entry for `silero_vad` with `model_type` = "vad", `size_mb` approximately 2, and a valid `archive_url`

### Requirement: Registry provides model lookup by ID
The system SHALL provide a function `get_model(model_id: str) -> ModelEntry | None` that returns the model entry matching the given ID, or None if not found.

#### Scenario: Lookup existing model
- **WHEN** `get_model("sherpa-onnx-paraformer-zh-2024-03-09")` is called
- **THEN** the matching ModelEntry SHALL be returned

#### Scenario: Lookup nonexistent model
- **WHEN** `get_model("nonexistent-model")` is called
- **THEN** None SHALL be returned

### Requirement: Registry supports filtering by model type
The system SHALL provide a function `list_models(model_type: str | None = None) -> list[ModelEntry]` that returns all models, optionally filtered by type ("streaming", "offline", "vad").

#### Scenario: List all models
- **WHEN** `list_models()` is called with no arguments
- **THEN** all model entries SHALL be returned

#### Scenario: List only streaming models
- **WHEN** `list_models(model_type="streaming")` is called
- **THEN** only models with `model_type` = "streaming" SHALL be returned

### Requirement: Download base URL is configurable
The system SHALL support two download sources: "github" (default, `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/`) and a user-configurable mirror URL stored in `AsrConfig.mirror_url`.

#### Scenario: Default download source is GitHub
- **WHEN** no mirror URL is configured
- **THEN** download URLs SHALL be constructed using the GitHub releases base URL

#### Scenario: Custom mirror URL overrides default
- **WHEN** `AsrConfig.mirror_url` is set to `"https://example.com/models/"`
- **THEN** download URLs SHALL be constructed using the mirror base URL + the model's `archive_url` path
