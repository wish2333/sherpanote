## ADDED Requirements

### Requirement: build.py supports --with-models flag for onedir builds
The build script SHALL accept a `--with-models <model-id>[,<model-id>]` flag. When specified in onedir mode, the build script SHALL download the specified models (using the model manager's download logic) before running PyInstaller. The models SHALL be placed in `frontend_dist/models/` or a dedicated `bundled_models/` directory.

#### Scenario: Build with single model
- **WHEN** `uv run build.py --with-models sherpa-onnx-paraformer-zh-2024-03-09` is executed
- **THEN** the specified model SHALL be downloaded
- **AND** the model SHALL be included in the PyInstaller datas

#### Scenario: Build with multiple models
- **WHEN** `uv run build.py --with-models model-a,model-b` is executed
- **THEN** both models SHALL be downloaded and included

#### Scenario: Build with --onefile rejects --with-models
- **WHEN** `uv run build.py --onefile --with-models model-a` is executed
- **THEN** the build SHALL fail with an error message indicating model bundling is not supported in onefile mode

#### Scenario: Build with nonexistent model ID
- **WHEN** `uv run build.py --with-models nonexistent-model` is executed
- **THEN** the build SHALL fail with an error listing valid model IDs

### Requirement: app.spec includes bundled models in datas
When `--with-models` is used, the build script SHALL dynamically add the downloaded model directories to the `datas` list in `app.spec`. The models SHALL be bundled under a `models/` prefix so the ASR engine can find them at runtime relative to the application directory.

#### Scenario: Models added to PyInstaller datas
- **WHEN** models are downloaded via `--with-models`
- **THEN** each model directory SHALL be added to `app.spec` datas as `(model_path, "models")`

#### Scenario: Runtime model path resolution in bundled app
- **WHEN** the bundled app runs and `AsrConfig.model_dir` is empty
- **THEN** the ASR engine SHALL search for models in the application's `models/` directory (alongside `~/sherpanote/models/`)

### Requirement: Build script shows model download progress
During a `--with-models` build, the build script SHALL display download progress for each model being downloaded.

#### Scenario: Progress shown during build
- **WHEN** `uv run build.py --with-models model-a` is executing
- **THEN** download progress (percentage and MB) SHALL be printed to the console for each model
