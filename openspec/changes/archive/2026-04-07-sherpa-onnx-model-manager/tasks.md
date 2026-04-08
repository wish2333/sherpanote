## 1. Configuration Updates

- [x] 1.1 Add `active_streaming_model`, `active_offline_model`, and `mirror_url` fields to `AsrConfig` dataclass in `py/config.py`
- [x] 1.2 Update `AsrConfig.to_dict()` and `AsrConfig.from_dict()` to serialize/deserialize the new fields with backward-compatible defaults
- [x] 1.3 Update `SettingsView.vue` AsrConfig type in `frontend/src/types` to include the new fields

## 2. Model Registry

- [x] 2.1 Create `py/model_registry.py` with `ModelEntry` frozen dataclass (model_id, display_name, model_type, languages, size_mb, archive_url, sha256, required_files, description)
- [x] 2.2 Populate registry with streaming models: `sherpa-onnx-streaming-paraformer-bilingual-zh-en`, `sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en`
- [x] 2.3 Populate registry with offline models: `sherpa-onnx-paraformer-zh-2024-03-09`, `sherpa-onnx-paraformer-zh-small-2024-03-09`, `sherpa-onnx-paraformer-zh-en-2023-09-14`, `sherpa-onnx-paraformer-trilingual-zh-cantonese-en`
- [x] 2.4 Add VAD model entry (`silero_vad`) with model_type "vad"
- [x] 2.5 Implement `get_model(model_id) -> ModelEntry | None` lookup function
- [x] 2.6 Implement `list_models(model_type=None) -> list[ModelEntry]` filter function
- [x] 2.7 Implement `get_download_url(model_entry, mirror_url=None) -> str` URL construction function

## 3. Model Manager (Download, Extract, Validate)

- [x] 3.1 Create `py/model_manager.py` with `download_archive(url, dest_path, on_progress) -> Path` using urllib.request with 64KB chunked reads
- [x] 3.2 Implement download resume support (HTTP Range header, partial file detection)
- [x] 3.3 Implement `verify_checksum(archive_path, expected_sha256) -> bool`
- [x] 3.4 Implement `extract_archive(archive_path, model_id, models_dir, is_vad=False) -> Path` for .tar.bz2 extraction
- [x] 3.5 Implement `validate_model(model_id, models_dir) -> dict` checking required_files
- [x] 3.6 Implement `install_model(model_id, models_dir, mirror_url=None, on_progress=None) -> dict` combining download+verify+extract+validate
- [x] 3.7 Implement `delete_model(model_id, models_dir) -> dict`
- [x] 3.8 Implement `list_installed_models(models_dir) -> list[dict]`
- [x] 3.9 Add VAD auto-download logic in `install_model` (download silero_vad if not already installed)
- [x] 3.10 Add cancellation support via threading Event for aborting downloads

## 4. Backend API (main.py)

- [x] 4.1 Add `@expose list_available_models(model_type=None) -> dict` API method
- [x] 4.2 Add `@expose list_installed_models() -> dict` API method
- [x] 4.3 Add `@expose install_model(model_id) -> dict` API method with progress events (`model_download_progress`, `model_install_complete`)
- [x] 4.4 Add `@expose delete_model(model_id) -> dict` API method
- [x] 4.5 Add `@expose cancel_model_install() -> dict` API method
- [x] 4.6 Add `@expose validate_model(model_id) -> dict` API method
- [x] 4.7 Update `app.spec` hiddenimports to include `py.model_manager` and `py.model_registry`

## 5. ASR Engine Integration

- [x] 5.1 Update `SherpaASR._find_streaming_model()` to check `config.active_streaming_model` first before candidate search
- [x] 5.2 Update `SherpaASR._find_offline_model()` to check `config.active_offline_model` first before candidate search
- [x] 5.3 Add bundled models directory check (for PyInstaller `sys._MEIPASS` / `models/`) to model resolution

## 6. Frontend - Settings UI

- [x] 6.1 Add model management types to `frontend/src/types` (ModelEntry, InstalledModel, DownloadProgress)
- [x] 6.2 Add bridge API functions: `listAvailableModels`, `listInstalledModels`, `installModel`, `deleteModel`, `cancelModelInstall`, `validateModel`
- [x] 6.3 Add "Download Source" selector (GitHub / Custom Mirror) to ASR config section in SettingsView.vue
- [x] 6.4 Add "Streaming Model" and "Offline Model" dropdown selects to ASR config section
- [x] 6.5 Add "Available Models" catalog section with model cards (name, type badge, languages, size, download button)
- [x] 6.6 Add "Installed Models" section with model cards (name, type, validation status, size, active badge, delete button)
- [x] 6.7 Implement download progress bar with cancel button
- [x] 6.8 Add model deletion confirmation dialog
- [x] 6.9 Wire up model install/delete events (listen for `model_download_progress`, `model_install_complete`)

## 7. Build System

- [x] 7.1 Add `--with-models` argument to `build.py` argparse
- [x] 7.2 Implement `_download_build_models(model_ids, models_dir)` function in `build.py`
- [x] 7.3 Add onefile+models validation (reject `--with-models` when `--onefile` is set)
- [x] 7.4 Implement dynamic datas injection: add downloaded model directories to `app.spec` datas list before PyInstaller runs
- [x] 7.5 Add console progress output for build-time model downloads

## 8. Manual Testing Checklist

- [ ] 8.1 Verify model catalog loads correctly in Settings ASR tab
- [ ] 8.2 Verify streaming model download with progress bar works end-to-end
- [ ] 8.3 Verify offline model download works end-to-end
- [ ] 8.4 Verify VAD auto-download triggers with first ASR model install
- [ ] 8.5 Verify model deletion with confirmation dialog
- [ ] 8.6 Verify active model dropdown selection and persistence
- [ ] 8.7 Verify custom mirror URL configuration works
- [ ] 8.8 Verify cancel download works mid-download
- [ ] 8.9 Verify ASR engine uses actively selected model for streaming recognition
- [ ] 8.10 Verify ASR engine uses actively selected model for file transcription
- [ ] 8.11 Verify `uv run build.py --with-models model-id` downloads and bundles model
- [ ] 8.12 Verify `uv run build.py --onefile --with-models model-id` is rejected with clear error
- [ ] 8.13 Verify bundled app finds and uses bundled models at runtime
- [ ] 8.14 Verify backward compatibility: existing manual model directories still work
