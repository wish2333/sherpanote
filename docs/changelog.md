# Changelog

All notable changes to SherpaNote are documented here.

---

## [2.1.1] - 2026-05-08

### Security

- Path traversal protection in `open_file`/`open_folder` -- `Path.resolve()` + data directory whitelist validation
- ZipSlip vulnerability fix in backup import -- validate extracted paths stay within target directory
- XSS protection in MarkdownRenderer -- HTML escaping for all regex captures, protocol whitelist for links (http/https/mailto only)

### Reliability

- `@expose` decorator now logs unhandled exceptions instead of silently swallowing them
- `restore_punctuation` logs warnings on failure instead of silently returning original text
- Database migration catches `sqlite3.OperationalError` precisely (only ignores "duplicate column")
- AiProcessor event listeners cleaned up on component unmount to prevent memory leaks
- `os.environ` modifications in model downloads protected with `threading.Lock` for thread safety
- Timer cleanup on unmount for SearchBar and SettingsView debounce/autosave timers
- VersionHistory `isLoading` state protected with `try/finally` against stuck loading

### Changed

- **Architecture refactor**: `main.py` SherpaNoteAPI (2343 lines) split into 6 domain mixins under `py/api/`:
  - `AsrMixin` (ASR, whisper.cpp, dependency management)
  - `AiMixin` (AI processing, preset management)
  - `StorageMixin` (record CRUD, version history, audio management, import/export)
  - `ModelsMixin` (ASR model management)
  - `OcrPluginMixin` (OCR, plugin backends, document extraction)
  - `ConfigBackupMixin` (configuration, backup/restore, file picker)
- **File size reduction**: Extracted `py/file_matcher.py` (shared model file matching), `py/asr_recognizer.py` (recognizer factory), reducing `py/asr.py` from 1077 to 651 lines
- **Frontend composable extraction**: 5 new composables from oversized views:
  - `useAiPresets.ts`, `useProcessingPresets.ts`, `useBackup.ts` (from SettingsView)
  - `useAudioPlayback.ts`, `useVersionManagement.ts` (from EditorView)
- **Code quality**: 10+ magic numbers replaced with named constants across 6 files
- **Code quality**: Hardcoded HuggingFace/Mirror/ModelScope URLs consolidated into `model_registry.py` constants
- **Type safety**: Added `isApiResponse<T>` type guard in `bridge.ts`, removed `any` casts in `OcrView.vue`
- **Type safety**: Added return type annotations to 4 adapter getter methods in `document_extractor.py`
- **Security**: Error messages in `open_file`/`open_folder` no longer leak system paths
- **Reliability**: `processText` checks API response success and resets `isProcessing` on failure
- **Reliability**: `copyResult` handles clipboard API failures with user-facing error messages
- **Reliability**: OCR engine lazy initialization protected with `threading.Lock`
- Removed debug `print` statement in `pywebvue/app.py` (replaced with `logger.debug`)
- Frontend `bun.lock` now tracked in git for reproducible builds

---

## [2.1.0] - 2026-05-01

### Added

- Plugin runtime system with subprocess-isolated execution for optional heavy backends (docling, opendataloader-pdf)
- Multi-backend document extraction architecture with unified `ExtractedDocument` output
- Decision tree routing: Images->PP-OCR, Office->markitdown, PDF->text layer detection->engine selection
- Plugin management UI in settings with install/uninstall/status controls
- Mirror source configuration for PyPI and HuggingFace (China-friendly defaults)
- Backend adapter layer (`py/adapters/`) for ppocr, markitdown, docling, opendata
- Plugin subprocess protocol: base64 JSON args via CLI, JSON stdout results, JSON lines stderr progress

### Fixed

- Windows symlink permission error during HuggingFace model download (fallback to file copy)
- PDF import segmentation fault caused by pypdfium2 (replaced with PyMuPDF)
- Bridge-not-ready causing infinite loading spinner on home page
- Drag overlay not covering full screen
- Missing file format validation and error messages on upload
- Missing AI processing flag in list summary queries
- Multiple TypeScript compilation errors
- Java binary PATH discovery for opendataloader-pdf on packaged apps
- Data directory path resolution for packaged applications
- Windows HuggingFace symlink creation permission errors

### Changed

- Refactored document extraction to support multiple backends via adapter pattern
- Updated data directory structure for packaged applications
- Improved list query performance by eliminating redundant queries

---

## [2.0.0] - 2026-04-20

### Added

- OCR image recognition system based on RapidOCR (PP-OCRv4/v5)
- Per-component model configuration (detection, recognition, classification)
- Built-in model lifecycle management with download and version tracking
- Support for single image, batch images, and PDF input
- Batch processing mode (multiple records) and sequential mode (one combined record)
- File list preview before processing
- OCR settings panel in settings view
- OCR view with drag-and-drop file upload

### Fixed

- OCR add button click not responding
- OCR record naming now uses "OCR" prefix

---

## [1.3.0] - 2026-04-15

### Added

- GPU acceleration support with auto-detection (NVIDIA GPU, CUDA version, sherpa-onnx CUDA build)
- CUDA build workflow with isolated temporary venv (avoids polluting dev environment)
- Whisper.cpp integration as optional ASR backend with model registry (cpu/blas/cuda variants)
- Binary distribution management: download, install, dependency auto-extraction
- Engine switcher on recording/transcription UI with dynamic model filtering
- Audio metadata management: display video title or original filename
- Smart file detection: avoid duplicate copy when importing audio
- Audio format optimization: WAV to MP3 conversion, 90%+ size reduction
- yt-dlp/ffmpeg dependency management for video download
- Thread-safe event queuing and task execution system in pywebvue

### Fixed

- `uv run` re-syncing `.venv` and replacing CUDA packages (solved with isolated venv)
- PyInstaller failing to auto-collect `onnxruntime_providers_cuda.dll` (manual collection in app.spec)
- `import onnxruntime` failure when sherpa-onnx bundles it (check `__version__` `+cuda` suffix)
- Deprecated whisper.exe replaced with whisper-cli.exe

---

## [1.2.0] - 2026-04-13

### Added

- Whisper model series (distil-large-v3/v3.5/turbo/medium, int8 and full versions)
- `hf_files` field for multi-file HuggingFace downloads (loose files instead of tar.bz2)
- Whisper engine integration with independent model selector
- Download source auto-save: configuration persists after switching

### Fixed

- Removed low-quality ONNX-Whisper models from manager (execution code preserved for manual downloads)
- Reduced redundant DEBUG log output when switching recording/transcription views

---

## [1.1.0] - 2026-04-10

### Added

- Simulated streaming recognition: VAD segmentation + OfflineRecognizer pipeline
- Streaming VAD `min_silence_duration` auto x1.6 for better segmentation
- Segment deduplication detection (skip identical content)
- Frontend streaming dropdown shows offline models that support simulated streaming
- macOS audio enhancements: sample rate resampling, AudioContext suspended retry (3 attempts), silence detection (3s RMS < 0.01)
- Configurable VAD parameters exposed in settings UI with range sliders
- Multilingual support enhancements

### Fixed

- SenseVoice int8 model using `model.int8.onnx` instead of `model.onnx` (extended file matching)
- No record created when recording contains no speech (toast notification instead)
- macOS AudioContext sample rate mismatch (44100/48000 -> 16000 resampling)

---

## [1.0.0] - 2026-04-09

### Added

- Core framework: PyWebVue (pywebview + Vue 3 bridge) with `@expose` + `_emit` event-driven communication
- Streaming ASR via sherpa-onnx (OnlineRecognizer) and file-based transcription (OfflineRecognizer)
- SQLite WAL mode storage with FTS5 full-text search
- OpenAI-compatible API integration with streaming, 4 modes: polish/note/mindmap/brainstorm
- AI preset system: multi-provider API presets (OpenAI-compatible, OpenRouter), processing presets with custom templates
- Auto AI processing after transcription (configurable pipeline)
- Version history system: manual save, content-diff dirty detection, restore, configurable max retention
- Multi-source model management: GitHub Releases, HuggingFace, HF-Mirror, GitHub Proxy, ModelScope
- Model auto-classification via file heuristic rules (Transducer/Paraformer/SenseVoice/Whisper/Qwen3-ASR/FunASR Nano)
- 6 new ASR models: Qwen3-ASR 0.6B/1.7B, FunASR Nano, Whisper distil-large-v3/v3.5, streaming Paraformer tri-lingual
- Editor layout: vertical stack (Transcript + AI Result) with collapsible transcript
- Output truncation prevention: dynamic `max_tokens` estimation, finish_reason detection, "Continue" button
- 5 views: Home, Record, Editor, Settings, AudioManage
- DaisyUI 5 custom themes (sherpanote-dark, sherpanote-light) with localStorage persistence
- Hash-based frontend routing for pywebview local file serving
- Data backup and export functionality

### Fixed

- Re-transcribe button not bound (implemented handleRetranscribe)
- Audio playback `file://` protocol failure (switched to base64 data URL)
- Paraformer vs SenseVoice runtime differences (improved model type detection)
- Recording state loss on page navigation (added navigation guards)
- Tri-lingual Paraformer model crash (protobuf parsing failed, fixed model type judgment)
- File upload transcription missing progress bar (added progress event push)
- PyWebVue bridge not supporting `None` as optional parameter (changed to single config dict)
- AI results not persisting (auto-save after ai_complete event)
- Version History current flag error (content-diff dirty detection replaces boolean flag)
- macOS microphone permission: added NSMicrophoneUsageDescription to Info.plist in app.bundle
