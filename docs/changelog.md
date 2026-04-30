# Changelog

> Version history for the project. Updated with each release.

## Format

Each entry follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

---

## [Unreleased]

---

## [2.1.0] - 2026-04-30

### Added
- feat(ocr): Multi-backend document extraction system with intelligent decision tree
- feat(ocr): markitdown integration for text-layer PDF and Office document (DOCX/PPTX/XLSX) extraction
- feat(ocr): PDF text layer detection using pdfplumber (first 3 pages, >50 chars threshold)
- feat(ocr): Unified ExtractedDocument output model for all extraction backends
- feat(ocr): Office file type support in OcrView (DOC badge, file picker filter)
- feat(ocr): Adapter pattern for document extraction backends (ppocr_adapter, markitdown_adapter)
- feat(plugins): Plugin runtime architecture with bundled Python + uv subprocess execution
- feat(plugins): Plugin management settings UI (DocumentSettingsPanel) with engine switching, backend management, and environment configuration
- feat(plugins): usePlugin composable for plugin install/uninstall lifecycle management
- feat(plugins): bridge.ts and Pinia store extended with plugin/document config support
- feat(ui): Fullscreen drag-and-drop layout for OCR page with auto PDF text layer detection in file list
- feat(plugins): Docling default OCR backend configured to use RapidOCR
- feat(settings): OCR/Document settings panel with PDF mode selection, backend management, and Java environment auto-detection
- feat(settings): PyPI and HuggingFace mirror source configuration for plugin installation and model downloads
- feat(plugins): Model pre-download for Docling with configurable model directory
- feat(plugins): Destroy plugin virtual environment with confirmation dialog
- feat(ocr): Upload file format validation with user-friendly error messages
- feat(ocr): Engine fallback warning when configured engine is unavailable
- feat(ui): Auto-save for plugin and document configuration changes
- feat(core): AI processing support for 30+ audio and video file formats via FFmpeg

### Changed
- refactor(ocr): Replace PyMuPDF (AGPL) with pypdfium2 (BSD) for PDF-to-image rendering
- refactor(ocr): Refactor ocr_process to use DocumentExtractor decision tree instead of direct OcrEngine calls
- refactor(ocr): New module structure: document_extractor.py, text_detector.py, adapters/, outputs/
- refactor(ui): Settings changes auto-save with full Chinese localization
- refactor(ocr): Scanned PDFs automatically skip opendataloader, use OCR directly
- perf(storage): Optimized list queries with reduced redundant queries for faster loading
- refactor(plugins): Auto-cleanup of opendataloader-pdf temp files after processing

### Fixed
- fix(ocr): Fix engine selection cache not invalidating on switch
- fix(plugins): Fix install operation with no log output
- fix(plugins): Fix uninstall -y flag error
- fix(plugins): Fix Java path not passed through execution chain
- fix(ocr): Fix engine fallback with no frontend notification
- fix(plugins): Fix Docling v2 API compatibility
- fix(plugins): Fix opendata runner output format
- fix(ocr): Fix temp file cleanup in opendata runner
- fix(ocr): PDF engine switch not taking effect after change
- fix(plugins): Installation progress unresponsive during package download
- fix(ocr): opendataloader-pdf producing empty output after processing
- fix(settings): Environment configuration text overflow in container
- fix(ocr): OCR page engine selection not syncing with saved config on startup
- fix(plugins): Engine options still showing as uninstalled after installation
- fix(backup): Export backup defaulting to select app configuration
- fix(ocr): Drag-and-drop upload area not covering full screen
- fix(core): Home page stuck on loading animation after packaging
- fix(ui): AI processing status indicator occasionally missing in record list
- fix(core): Model call failure due to whitespace in model name
- fix(core): Model directory configuration issue preventing local model discovery
- fix(ocr): pypdfium2 segfault when importing PDFs on macOS
- fix(settings): Java detection result display issue in document settings panel

### Decision Tree
```
Image -> PP-OCR (RapidOCR)
Office (DOCX/PPTX/XLSX) -> markitdown
PDF -> text layer detection -> markitdown (has text) / PP-OCR (no text)
PDF (scanned, with docling) -> docling with RapidOCR backend
Fallback: markitdown failure on text PDF -> PP-OCR
```

---

## [2.0.1] - 2026-04-22

### Added
- feat(ocr): OCR record naming convention - auto-prefix with "OCR-" for single files, PDFs, and batch processing

### Fixed
- fix(ocr): Fix OCR add button click not responding
- fix(asr): Fix model directory change requiring page re-entry to take effect in ASR settings

---

## [2.0.0] - 2026-04-20

### Added
- feat(ocr): New OCR image recognition feature - support images, multi-image, and PDF text extraction
- feat(ocr): Dedicated OCR view with drag-and-drop file upload and real-time progress display
- feat(ocr): OCR settings page with model version (v4/v5) and type (mobile/server) selection
- feat(ocr): Two processing modes - batch (one record per image) and sequential (merged into single record)

### Fixed
- fix(ocr): Fix OCR model selection and result parsing errors
- fix(ocr): Fix model download and management issues
- fix(ocr): Fix frontend settings display incomplete

### Changed
- refactor(ocr): Refactor OCR model management to use RapidOCR built-in download and management
- perf(build): Add pre-download OCR models option for offline usage
- refactor(ocr): Simplify OCR settings, remove unnecessary parameter configuration

---

## [1.3.2] - 2026-04-16

### Added
- feat(backup): New data backup feature - backup app config, presets, records, and audio files
- feat(backup): Selective backup with flexible data type selection
- feat(backup): Cross-platform data restore with automatic path compatibility

### Fixed
- fix(macos): Fix new window opening during model download on macOS
- fix(editor): Fix AI results lost when navigating away from record during processing
- fix(ui): Fix Markdown heading and table display issues
- fix(models): Fix hf-mirror download timeout and 404 errors

### Changed
- feat(editor): Improved AI result persistence mechanism for continuous user experience
- perf(models): Improved model download stability and speed

---

## [1.3.1] - 2026-04-15

### Added
- feat(whisper): CUDA support for whisper.cpp on Windows
- feat(whisper): Whisper.cpp model selection with multiple versions
- feat(ai): Unified prompt management - editable built-in prompts with one-click reset

### Fixed
- fix(deps): Fix static FFmpeg button not visible when already installed
- fix(ui): Fix yt-dlp cookie description text overflow

### Changed
- feat(whisper): Whisper.cpp multi-version coexistence - install/switch without re-download
- feat(ai): Built-in AI mode prompts now customizable via settings

---

## [1.3.0] - 2026-04-15

### Added
- feat(asr): Real-time progress display with segment count (e.g., "42% (15/30)")
- feat(gpu): GPU acceleration - auto-detect NVIDIA CUDA via `py/gpu_detect.py`
- feat(build): CUDA build system in `build.py` with `--cuda` and `--cuda-variant` flags
- feat(whisper): whisper.cpp integration via `py/whispercpp.py` for optional ASR backend
- feat(whisper): Whisper.cpp model registry (`py/whispercpp_registry.py`) with cpu/blas/cuda variants
- feat(config): Auto-save download source after switching
- feat(asr): Engine switching in recording/transcription views with dynamic model filtering
- feat(whisper): Independent Whisper model selector, separate from ONNX models
- feat(audio): Audio metadata management - display video title or original filename
- feat(io): Smart file detection - auto-skip duplicate files on import
- feat(video): Video download and transcription via `py/video_downloader.py`
- feat(audio): Audio format optimization - WAV to MP3, 90%+ file size reduction
- feat(deps): Complete yt-dlp/ffmpeg dependency management with in-app installation
- feat(video): Cookie file configuration for authenticated video downloads
- feat(whisper): Enhanced whisper.cpp with Homebrew binary preference on macOS

### Fixed
- fix(ui): Progress bar not showing segment count
- fix(whisper): whisper.cpp installation failure - missing dependency files
- fix(whisper): Model download temp file extension compatibility issue
- fix(whisper): Deprecated whisper.exe - now uses whisper-cli.exe
- fix(whisper): Whisper transcription timestamp display parsing
- fix(models): Removed unnecessary ModelScope Qwen3 models from UI
- fix(asr): Improved engine switching experience in recording view
- fix(audio): Missing audio player in video download transcription records
- fix(audio): Incorrect audio duration display (hardcoded 0 -> actual calculation)
- fix(asr): ASR initialization error, improved transcription stability
- fix(build): sherpa-onnx CUDA variant detection (no longer uses wrong `import onnxruntime`)
- fix(build): `uv run` re-sync issue with CUDA packages
- fix(macos): Missing whisper-cli executable after whisper.cpp install
- fix(deps): "ffmpeg not found" causing download failures
- fix(audio): Audio file playback not loading correctly
- fix(audio): Deleting audio file incorrectly deleting entire record
- fix(audio): Re-transcribe button not responding
- fix(audio): Lost title and audio link after re-transcription
- fix(ui): Progress bar not disappearing after transcription complete
- fix(asr): Trilingual Paraformer model crash
- fix(ui): Prevent page switching during recording

### Changed
- perf(asr): Significantly improved GPU transcription performance for long audio
- feat(install): Improved installation flow with auto system detection and GPU guidance
- feat(ui): Enhanced error messages with detailed troubleshooting info
- feat(whisper): Improved whisper engine integration with existing architecture
- feat(config): Optimized download source and model config save logic
- feat(ui): Simplified model selection interface
- feat(ui): Audio manager shows user-friendly title/filename first
- feat(build): Correct `--cuda` parameter support with venv isolation
- feat(build): app.spec collects sherpa-onnx lib/ DLL files including CUDA providers
- feat(cross): Cross-platform tool detection with priority-based path lookup
- feat(deps): Real-time dependency status with clear installation guidance
- feat(ui): Optimized settings layout with intuitive dependency management

---

## [1.2.4] - 2026-04-10

### Added
- feat(asr): Simulated streaming recognition for SenseVoice and Qwen3-ASR via VAD
- feat(asr): Configurable VAD parameters (threshold, silence duration, speech duration)
- feat(ui): ASR settings split into model settings and model management
- feat(macos): macOS audio enhancement - auto resample to 16kHz, silence detection reminder
- feat(ui): Frontend Chinese localization

### Fixed
- fix(macos): Fix macOS microphone recording intermittent silence issue
- fix(asr): Fix simulated streaming mode results not displaying in real-time
- fix(asr): Fix SenseVoice int8 model load failure
- fix(versions): Fix incomplete version save after re-transcription (missing timestamped segments)

### Changed
- feat(asr): Improved VAD detection accuracy - default silence duration to 0.8s
- feat(asr): Optimized audio processing flow - improved buffer management and exception handling
- feat(models): Enhanced model management with multi-source download support

---

## [1.2.3] - 2026-04-10

### Added
- feat(asr): Support for Cohere transcription model
- feat(ui): Quick settings bar in recording view for instant model/language switching

### Fixed
- fix(asr): Fix Chinese speech incorrectly translated to English
- fix(asr): Fix model language configuration not taking effect
- fix(asr): Fix some models not working in auto-detect language mode

### Changed
- feat(models): Convenient VAD model management with direct download/delete in model list
- feat(ui): Auto-hide recording settings for cleaner interface

---

## [1.2.2] - 2026-04-10

### Added
- feat(asr): Three new ASR models - trilingual zh/yue/en, Whisper Large v3, Whisper Large v2

### Fixed
- fix(macos): Fix macOS microphone recording not working
- fix(macos): Fix microphone permission prompt and guidance
- fix(macos): Fix media device access not properly exposed in packaged app

---

## [1.2.0] - 2026-04-09

### Added
- feat(models): Multiple download sources - GitHub, HuggingFace (with mirror), ModelScope
- feat(models): Six new ASR models - Qwen3-ASR, FunASR Nano, SenseVoice and more
- feat(models): Smart model recognition - auto-classify manually downloaded models (streaming/offline)
- feat(models): Proxy settings - system proxy and custom proxy options

### Fixed
- fix(models): Fix model recognition issues - all downloaded models correctly identified
- fix(models): Fix Whisper model filename prefix incompatibility
- fix(models): Fix GitHub Proxy grayed-out model list after switching
- fix(audio): Fix error in Audio Files delete operation

### Changed
- feat(ui): Language selection dropdown with 12 languages + custom option
- feat(ui): Improved installed model display - streaming and offline models clearly separated
- feat(ui): Consolidated related links into "Related Links" section

---

## [1.1.0] - 2026-04-08

### Added
- feat(ai): Multiple API presets support - save and switch between providers/models
- feat(ai): AI processing preset management with custom prompts
- feat(ai): Auto AI processing after transcription when preset configured
- feat(ai): AI results auto-save - prevent data loss
- feat(versions): Version history feature with restore and delete
- feat(ai): "Continue output" for truncated AI responses

### Fixed
- fix(editor): Fix record not saving when switching views
- fix(asr): Fix missing punctuation in transcription
- fix(ai): Fix incorrect AI result naming display
- fix(versions): Fix auto version creation when no changes exist
- fix(versions): Fix "current version" indicator not updating in history
- fix(ai): Fix streaming interruption for long text processing
- fix(editor): Fix AI results lost after frontend refresh

### Changed
- feat(ui): Optimized layout - left panel and content area 1:2 ratio
- feat(ui): Collapsible transcript display with preview
- perf(ai): Improved streaming performance and token allocation
- feat(ai): Smart max_tokens management based on input length
- feat(versions): Version management optimization - create version only on actual content change

---

## [1.0.0] - 2026-04-08

### Added
- feat(audio): Audio player volume control with mute toggle
- feat(editor): One-click transcript copy to clipboard
- feat(audio): Full audio file management system - view, delete, open folder
- feat(audio): Import and transcribe with drag-drop support
- feat(editor): Editable transcript text before AI processing
- feat(ui): Transcription progress display with page switch warning

### Fixed
- fix(audio): Fix audio file playback not loading
- fix(audio): Fix delete operation incorrectly removing entire record
- fix(audio): Fix re-transcribe button not responding
- fix(audio): Fix lost title and audio link after re-transcription
- fix(ui): Fix progress bar not disappearing after completion
- fix(asr): Fix trilingual Paraformer model crash
- fix(ui): Prevent page switching during recording

### Changed
- feat(asr): Re-transcribe only shown for mic recordings
- feat(audio): Imported files fully managed with re-transcribe support
- feat(log): Enhanced logging system for troubleshooting
