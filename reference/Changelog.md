# Changelog

All notable changes to SherpaNote will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [2.0.1] - 2026-04-22

### New

- OCR recognition records now automatically add an “OCR-” prefix, standardizing the naming rules for single files, PDFs, and batch processing for easy differentiation and retrieval (custom title functionality remains unchanged)

### Fixed

- Fixed the issue where the add button in the OCR interface was unresponsive
- Fixed the issue where changing the model directory via the browse button in ASR settings required re-entering the page to take effect

## [2.0.0] - 2026-04-20

### New
- Brand-new OCR image recognition feature: Supports text recognition for images, multiple images, and PDF files
- New OCR dedicated view interface for drag-and-drop file uploads and real-time processing progress display
- OCR settings page with flexible selection of different model versions (v4/v5) and types (Mobile/Server)
- Support for two processing modes: Batch processing (generates a separate record for each image) and Sequential processing (merges into a single record)

### Fixes
- Fixed OCR model selection and result parsing errors
- Resolved model download and management issues
- Fixed the issue of incomplete display in the front-end settings interface

### Optimizations
- Refactored the OCR model management system to use RapidOCR's built-in automatic download and management
- Packaging optimization: Added an option for pre-downloading OCR models to enhance the offline user experience
- Streamlined OCR settings by removing unnecessary parameter configurations

## [1.3.2] - 2026-04-16

### New

- Added data backup feature: Allows backing up application settings, presets, transcription history, and audio files in settings
- Supports selective backup, allowing flexible choice of data types to back up
- Automatic compatibility with different operating systems after import, enabling cross-platform data transfer

### Fixes

- Fixed the issue where a new window was unexpectedly opened when downloading models on Mac
- Resolved the problem where leaving the recording interface during AI processing caused results to be lost
- Fixed incorrect display of Markdown headings and tables
- Solved timeout and 404 errors that occurred when downloading models from hf-mirror

### Optimizations

- Improved the persistence mechanism for AI processing results to ensure a seamless user experience
- Enhanced stability and speed of model downloads, reducing failures caused by network issues

## [1.3.1] - 2026-04-15

### New
- Whisper.cpp CUDA Support: Windows users can now enable GPU acceleration for a significant transcription speed boost
- Whisper.cpp Model Selection: Support for multiple model versions, allowing you to choose size and precision based on your needs
- LLM Prompt Management: Built-in prompts can be edited via the settings interface, with one-click reset to defaults available

### Fixes
- Fixed static FFmpeg button visibility issue when an existing installation is detected
- Fixed yt-dlp Cookie description text overflow display issue

### Optimizations
- Whispercpp now supports multiple versions co-existing, no need to re-download when installing or switching versions
- AI processing built-in mode prompts can now be customized via the settings interface

## [1.3.0] - 2026-04-15

### Added

- Real-time progress display showing segment counts, e.g. "42% (15/30)"
- GPU acceleration: automatic NVIDIA CUDA device detection via `py/gpu_detect.py`, significantly faster transcription for large models (Qwen3-ASR, Whisper)
- CUDA build system in `build.py`: isolated `_cuda_build_venv` keeps dev environment clean, supports `--cuda` and `--cuda-variant` flags (CUDA 11.8 / CUDA 12+cuDNN 9)
- Whisper.cpp integration (`py/whispercpp.py`): optional ASR backend via whisper-cli.exe with binary distribution management
- Whisper.cpp model registry (`py/whispercpp_registry.py`): supports cpu/blas/cuda variants
- Auto-save download source configuration after switching
- Engine switching in recording/transcription views with dynamic model selector filtering
- Independent Whisper model selector, separate from ONNX models
- Audio metadata management: display video titles or original filenames
- Smart file detection: auto-skip duplicate copies during import
- Video download support for transcription (`py/video_downloader.py`)
- Audio format optimization: WAV to MP3 conversion, 90%+ file size reduction
- Added a complete yt-dlp/ffmpeg dependency management interface for direct in-app installation
- Added support for cookie file configuration to download authenticated videos
- Enhanced Whisper.cpp support to prioritize using Homebrew-installed binaries

### Fixed

- Progress bar not showing segment counts (whisper.cpp backend real-time progress coming in final release)
- Whisper.cpp installation failure: all dependency files (libggml etc.) now correctly extracted
- Whisper.cpp model download errors: temporary file extension compatibility resolved
- Whisper.exe deprecation warning: now correctly uses whisper-cli.exe
- Whisper transcription timestamp display issues: output format parsing corrected
- Unnecessary ModelScope Qwen3 models removed from model management UI
- Recording view engine switching experience optimized
- Missing audio player in video download transcription records
- Audio duration display error (hardcoded 0 -> actual calculation)
- ASR initialization errors, improved transcription stability
- `sherpa-onnx` CUDA variant `+cuda` suffix detection instead of broken `import onnxruntime`
- `uv run` re-syncing `.venv` and undoing CUDA package installs
- Fixed the issue on macOS where whisper-cli executable file was missing after Whisper.cpp installation
- Resolved download failure errors caused by “ffmpeg not found”

### Changed

- Significantly improved transcription performance under GPU, especially for long audio files
- Improved installation flow with automatic system detection and GPU version guidance
- Enhanced error messages with more detailed troubleshooting information
- Whisper engine integration refined with existing architecture
- Download source and model configuration save logic optimized
- Model selection UI simplified
- Frontend display: audio manager prioritizes user-friendly titles/filenames
- CUDA build method: now correctly supports `--cuda` flag with isolated venv approach
- `app.spec` collects sherpa-onnx lib/ DLLs (including `onnxruntime_providers_cuda.dll`)
- Optimized cross-platform tool detection to search for installation paths by priority
- Real-time dependency status detection with clear installation guidance
- Optimized settings interface layout with more intuitive dependency management instructions

---

## [1.2.4] - 2026-04-10

[update-1.2.4](https://github.com/wish2333/sherpanote/releases/tag/update-1.2.4)

### Added

- Simulated streaming recognition: SenseVoice and Qwen3-ASR models support pseudo-real-time transcription via VAD pipeline
- Configurable VAD parameters: threshold, silence duration, speech duration, max speech duration
- ASR settings UI split into Model Settings and Model Management tabs
- macOS audio enhancement: automatic resampling to 16kHz, silence detection warnings
- Full Chinese localization of the interface

### Fixed

- macOS microphone recording intermittently silent
- Simulated streaming results not displaying in real-time
- SenseVoice int8 model loading failure
- Retranscribe version save missing Timestamped Segments

### Changed

- VAD default silence duration adjusted to 0.8s for better accuracy
- Improved audio buffer management and error handling
- Enhanced model management for multi-source downloads

---

## [1.2.3] - 2026-04-10

[update-1.2.3](https://github.com/wish2333/sherpanote/releases/tag/update-1.2.3)

### Added

- Support for Cohere Transcribe model with improved accuracy
- Quick settings bar in recording view for instant model/language switching

### Fixed

- Chinese speech incorrectly transcribed to English
- Model language configuration not taking effect
- Auto-detect language option not working with some models

### Changed

- VAD model management accessible directly from model list
- Recording settings auto-hide during active recording

---

## [1.2.2] - 2026-04-10

[update-1.2.2](https://github.com/wish2333/sherpanote/releases/tag/update-1.2.2)

### Added

- Three new ASR models: multilingual zh/cantonese/en, Whisper Large v3, Whisper Large v2

### Fixed

- macOS microphone recording completely broken
- Media device access not exposed in packaged macOS app (Info.plist NSMicrophoneUsageDescription)

### Changed

- Improved permission prompt messaging for microphone access

---

## [1.2.0] - 2026-04-09

[update-1.2.0](https://github.com/wish2333/sherpanote/releases/tag/update-1.2.0)

### Added

- Multi-source model downloads: GitHub, HuggingFace, HF-Mirror, GitHub Proxy, ModelScope
- Six new ASR models: Qwen3-ASR (0.6B/1.7B), FunASR Nano, SenseVoice, Whisper distil-large-v3/v3.5, trilingual Paraformer
- Smart model detection: automatic streaming/offline classification based on file heuristics, supports user-downloaded models
- Proxy settings: None / System proxy / Custom proxy
- Language selection: 12 languages + custom option

### Fixed

- Model recognition failures for downloaded models
- Whisper model filename prefix incompatibility
- GitHub Proxy switch causing model list gray-out
- Audio Files delete operation error

### Changed

- Improved model list display with streaming/offline categorization
- Consolidated Related Links section
- Language selection dropdown functionality

---

## [1.1.0] - 2026-04-08

[update-1.1.0](https://github.com/wish2333/sherpanote/releases/tag/update-1.1.0)

### Added

- Multi-API preset management: save and switch between multiple AI providers and model configs
- AI processing preset management: personalized templates with custom prompts
- Auto AI processing after transcription
- AI result auto-save to prevent data loss
- Version history: record edit history with restore and delete
- "Continue" button for truncated AI output recovery

### Fixed

- Page navigation causing transcription record loss
- Missing punctuation in transcribed text
- AI result naming display incorrect
- Spurious version creation when no changes exist
- "Current version" indicator not updating in version history
- Long text streaming interruption
- AI results lost after frontend refresh

### Changed

- Editor layout: 1:2 ratio between control panel and content area
- Collapsible transcript panel
- Streaming performance optimization
- Smart max_tokens estimation based on input length
- Version creation only on actual content changes

---

## [1.0.0] - 2026-04-08

### Added

- Audio player with volume control (slider + mute toggle)
- One-click transcript copy
- Dedicated audio file management view
- Import & transcribe workflow with drag-and-drop support
- Editable transcript text before AI processing
- Transcription progress bar with page-switch protection

### Fixed

- Audio file playback loading failure
- Delete audio file incorrectly deleting entire record
- Retranscribe button not responding
- Title loss and audio link breakage after retranscription
- Progress bar not disappearing after transcription completion
- Tri-lingual Paraformer model crash (protobuf parsing)
- Accidental page navigation during recording

### Changed

- Retranscribe button only visible for microphone recordings
- Uploaded audio files fully managed by the system
- Enhanced logging system
