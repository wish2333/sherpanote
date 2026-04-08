## Why

SherpaNote relies on sherpa-onnx for local speech recognition, but users must manually download model files (~70-230MB each), place them in the correct directory structure, and configure the path in settings. This is error-prone and creates a poor first-run experience. Additionally, the build system has no option to bundle models at packaging time, making distribution harder for users who don't want to manage model files separately.

## What Changes

- Add a Python model manager module (`py/model_manager.py`) that can:
  - List available sherpa-onnx ASR models from a curated model registry
  - Download models (with progress reporting) from GitHub releases
  - Verify model integrity after download
  - List installed models and their status
  - Delete installed models
- Add model management API methods to the SherpaNoteAPI bridge (`main.py`)
- Add model download/management UI to the Settings page ASR tab:
  - Model catalog with available models (name, size, language support)
  - Download button with progress bar
  - Installed model list with delete option
  - Model selection for active ASR model
- Add optional model bundling support to the build system:
  - `--with-models` flag in `build.py` to download and bundle models at build time
  - `--models` flag to specify which models to include
  - Configurable model output directory in `app.spec`

## Capabilities

### New Capabilities

- `model-registry`: Curated list of available sherpa-onnx ASR models with metadata (name, size, language, download URL, required files)
- `model-download`: Model download, verification, and installation with progress reporting
- `model-management-ui`: Frontend UI for browsing, downloading, and managing ASR models in Settings
- `build-model-bundling`: Optional model bundling during PyInstaller build process

### Modified Capabilities

(none - no existing specs)

## Impact

- **Python backend**: New `py/model_manager.py` module; new `@expose` methods in `main.py`
- **Frontend**: New components in SettingsView.vue or a separate ModelManager section
- **Build system**: Modified `build.py` and `app.spec` for optional model bundling
- **Configuration**: `AsrConfig` may need a new field for active model selection (replacing manual `model_dir` path)
- **Dependencies**: `requests` or `urllib` for HTTP downloads (likely already available); `tarfile` (stdlib) for extraction; `hashlib` (stdlib) for verification
- **Network**: Downloads from GitHub releases (~70-230MB per model); should support Chinese mirror URLs
