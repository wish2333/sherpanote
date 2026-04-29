# System Design

> Architecture, module design, and technical decisions for SherpaNote.
> AI reads this after PRD.md to understand HOW to build.

---

## Version Change Index

| Version | Changed Module | Description |
|---------|---------------|-------------|
| v2.0.0 | OCR, Model Management | Added OCR engine, refactored model management |
| v1.3.0 | ASR, Whisper, CUDA | Added whisper.cpp, GPU detection, video download |
| v1.2.0 | Model Manager | Multi-source model download, new ASR models |
| v1.1.0 | AI Processing | Multi-preset, version history, streaming |
| v1.0.0 | Initial | Core recording, transcription, record management |

---

## Architecture Overview

### System Context

```
[User] --> [pywebview Desktop Window]
                |
                v
         [Vue.js Frontend]  <--bridge.js-->  [Python Backend]
                |                                    |
                |                              +-----+------+
                |                              |            |
                v                              v            v
         [Pinia Stores]              [sherpa-onnx]   [RapidOCR]
                                        |            |
                                        v            v
                                  [ASR Models]  [OCR Models]
                                        |
                                        v
                                  [SQLite (WAL)]
                                        |
                                        v
                                  [Local Files]
                                  (audio, exports)
```

### Layer Responsibilities

| Layer | Responsibility | Technology |
|-------|---------------|------------|
| Presentation | UI rendering, user interaction, routing | Vue 3 + TypeScript + Tailwind CSS 4 + DaisyUI 5 |
| Bridge | Bidirectional JS-Python communication | pywebvue (pywebview + JS bridge) |
| Application | Business logic, orchestration, model management | Python 3.11+ |
| Data | Persistence, file storage | SQLite (WAL mode) + local filesystem |
| AI/ML | Speech recognition, OCR, text generation | sherpa-onnx, whisper.cpp, RapidOCR, OpenAI API |

---

## Module Design

### Module: Backend API (`main.py`)

**Purpose**: Main API class exposing all backend functionality to frontend via pywebvue Bridge.

**Dependencies**: py, pywebvue

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| `SherpaNoteAPI(Bridge)` | Exposes all `@expose` methods as callable JS API |
| `dispatch_task()` | Runs tasks in background thread, queues events to frontend |
| `handle_exception()` | Global exception handler, shows error dialog |

**Data Flow**:

```
Frontend JS call --> bridge.call('method', args) --> @expose method in SherpaNoteAPI
                                                            |
                                                     dispatch_task() [background thread]
                                                            |
                                                     bridge.emit('event', data) --> Frontend event listener
```

### Module: Storage (`py/storage.py`)

**Purpose**: SQLite database access with WAL mode, record CRUD, versioning, and export.

**Dependencies**: sqlite3

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| `Storage` | Main storage class, connection pooling via `_get_conn()` |
| `save()` | Insert or update record |
| `get()` | Fetch single record by ID |
| `list()` | List with optional filter (category) |
| `delete()` | Remove record by ID |
| `create_version()` | Snapshot current record state, prune old versions |
| `restore_version()` | Replace record content with version snapshot |
| `export()` | Export to md/txt/srt/docx |

### Module: ASR (`py/asr.py`)

**Purpose**: Automatic Speech Recognition with multiple engine support.

**Dependencies**: sherpa-onnx, py/whispercpp.py

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| ASR engine classes | sherpa-onnx and whisper.cpp backends |
| Streaming recognition | Real-time audio chunk processing |
| File transcription | Offline transcription with progress callback |
| VAD integration | Voice Activity Detection for simulated streaming |

### Module: OCR (`py/ocr.py`)

**Purpose**: Optical Character Recognition using RapidOCR.

**Dependencies**: rapidocr-onnxruntime

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| `OcrEngine` | OCR processing wrapper |
| Batch processing | Multi-file/image processing |
| Model management | Download, scan, delete OCR models |

### Module: LLM (`py/llm.py`)

**Purpose**: AI text processing via OpenAI-compatible API.

**Dependencies**: openai

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| `AIProcessor` | OpenAI client with streaming support |
| Processing modes | polish, note, mindmap, brainstorm |
| Multi-preset | Multiple API configurations |

### Module: Config (`py/config.py`)

**Purpose**: Application configuration management.

**Dependencies**: py/storage.py (app_config table)

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| `AppConfig` | Centralized config with get/update |
| Default values | Sensible defaults for all settings |

### Module: Model Manager (`py/model_manager.py`, `py/model_registry.py`)

**Purpose**: ASR model discovery, download, and lifecycle management.

**Dependencies**: huggingface_hub, py/config.py

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| `ModelRegistry` | Defines all available ASR models with metadata |
| `ModelManager` | Install, list, delete, validate models |
| Multi-source download | HuggingFace, GitHub Proxy, ModelScope |

### Module: Whisper.cpp (`py/whispercpp.py`, `py/whispercpp_registry.py`)

**Purpose**: whisper.cpp binary integration for alternative ASR backend.

**Dependencies**: whisper-cli binary, py/gpu_detect.py

**Key Components**:

| Component | Responsibility |
|-----------|---------------|
| `WhisperCppASR` | Whisper.cpp transcription wrapper |
| `WhisperCppRegistry` | Model definitions for whisper.cpp |
| Binary management | Download/install/uninstall whisper-cli |

### Module: Video Downloader (`py/video_downloader.py`)

**Purpose**: Download video/audio from URLs using yt-dlp.

**Dependencies**: yt-dlp, ffmpeg

### Module: Backup (`py/backup.py`)

**Purpose**: Data backup and restore functionality.

**Dependencies**: py/storage.py, shutil

---

## Frontend Architecture

### Route Structure

| Route | View | Purpose |
|-------|------|---------|
| `/` | `HomeView.vue` | Record list with search and filter |
| `/record` | `RecordView.vue` | Audio recording with real-time transcription |
| `/editor/:id` | `EditorView.vue` | Record editor with transcript and AI processing |
| `/settings` | `SettingsView.vue` | Configuration (ASR, AI, OCR, general) |
| `/audio-manage` | `AudioManageView.vue` | Audio file management |
| `/ocr` | `OcrView.vue` | OCR image/PDF processing |

### State Management (Pinia)

| Store | Purpose |
|-------|---------|
| `appStore` | Global app state, records list, config, dirty tracking |

### Key Components

| Component | Purpose |
|-----------|---------|
| `AudioRecorder.vue` | Microphone recording with Web Audio API |
| `AiProcessor.vue` | AI processing UI with mode selection and streaming display |
| `TranscriptPanel.vue` | Transcript display with timestamp segments |
| `MarkdownRenderer.vue` | Markdown rendering with syntax highlighting |
| `MindMapPreview.vue` | Mind map visualization from AI output |
| `RecordCard.vue` | Record item card in list view |
| `SearchBar.vue` | Global search input |
| `ExportMenu.vue` | Export format selection |

---

## Data Architecture

### Data Flow Diagram

```
Recording:
  [Mic] --> [Web Audio API] --> [PCM chunks] --> [base64] --> [feed_audio()] --> [ASR Engine] --> [transcript]
                                                                                                  |
                                                                                                  v
                                                                    [save_record()] --> [SQLite records table]

File Import:
  [File/URL] --> [download/import] --> [local audio file] --> [transcribe_file()] --> [ASR Engine] --> [transcript]
                                                                                                        |
                                                                                                        v
                                                                                          [save_record()] --> [SQLite]

AI Processing:
  [Record transcript] --> [process_text_stream()] --> [OpenAI API] --> [streaming tokens] --> [AI result]
                                                                                                  |
                                                                                                  v
                                                                                    [_persist_ai_result()] --> [SQLite]

OCR:
  [Image/PDF] --> [ocr_process()] --> [RapidOCR] --> [extracted text] --> [save_record()] --> [SQLite]
```

### Storage Strategy

| Data Type | Storage | Retention | Location |
|-----------|---------|-----------|----------|
| Records | SQLite | Permanent | `data/data.db` |
| Audio files | Filesystem | Permanent | `data/audio/` |
| OCR results | SQLite | Permanent | `data/data.db` |
| App config | SQLite | Permanent | `data/data.db` (app_config) |
| ASR models | Filesystem | Permanent | `models/` |
| OCR models | Filesystem | Permanent | `data/rapid_ocr_models/` |
| Whisper binary | Filesystem | Permanent | `tools/whisper/` |
| Audio metadata | JSON file | Permanent | `data/audio_meta.json` |
| Export files | Filesystem | Until user deletes | OS temp / user-chosen |

---

## API Design

### Conventions

- **Call pattern**: `bridge.call('method_name', arg1, arg2, ...)` returns `Promise<dict>`
- **Event pattern**: Backend emits events via `bridge.emit('event_name', payload)`, frontend listens with `bridge.on('event_name', handler)`
- **Response envelope**: All `@expose` methods return `dict` with `success: bool` and `data`/`error`
- **Error format**: `{ success: false, error: { code: str, message: str } }`

### Backend API Reference (Python)

#### ASR & Audio

| Method | Description |
|--------|-------------|
| `detect_gpu()` | Detect NVIDIA GPU availability |
| `init_model(language)` | Initialize ASR model for recording |
| `start_streaming()` | Start streaming recognition |
| `feed_audio(base64_data)` | Feed audio chunk for streaming |
| `stop_streaming()` | Stop streaming, get final transcript |
| `transcribe_file(file_path)` | Transcribe audio file |
| `retranscribe_record(record_id)` | Re-transcribe existing record |
| `import_and_transcribe(file_path, title)` | Import file and transcribe |
| `download_and_transcribe(url)` | Download URL and transcribe |
| `get_audio_base64(file_path)` | Get audio as base64 for playback |

#### AI Processing

| Method | Description |
|--------|-------------|
| `test_ai_connection()` | Test current AI preset connection |
| `test_ai_preset_connection(config)` | Test specific preset connection |
| `process_text(text, mode, custom_prompt)` | Non-streaming AI process |
| `process_text_stream(text, mode, custom_prompt, record_id)` | Streaming AI process |
| `cancel_ai()` | Cancel ongoing AI processing |
| `continue_text_stream(previous_output, mode, custom_prompt, record_id)` | Continue truncated output |

#### Record Management

| Method | Description |
|--------|-------------|
| `save_record(data)` | Create or update record |
| `get_record(record_id)` | Fetch single record |
| `list_records(filter)` | List records with optional category filter |
| `delete_record(record_id)` | Delete record |
| `search_records(keyword)` | Search records by keyword |

#### Version Control

| Method | Description |
|--------|-------------|
| `get_version_history(record_id)` | Get all versions |
| `save_version(record_id)` | Create version snapshot |
| `mark_dirty(record_id)` | Mark as unsaved |
| `mark_clean(record_id)` | Mark as saved |
| `restore_version(record_id, version)` | Restore to version |
| `delete_version(record_id, version)` | Delete version |

#### OCR

| Method | Description |
|--------|-------------|
| `ocr_process(files, mode, title)` | Run OCR on files (single/batch) |
| `cancel_ocr()` | Cancel OCR processing |
| `scan_ocr_models()` | Scan installed OCR models |
| `download_ocr_models(det_version, det_type, cls_version)` | Download OCR models |
| `delete_ocr_model(version, role, type)` | Delete OCR model |
| `get_image_preview(file_path)` | Get image thumbnail as base64 |

#### Model Management

| Method | Description |
|--------|-------------|
| `list_available_models(model_type)` | List downloadable models |
| `list_installed_models()` | List installed models |
| `install_model(model_id)` | Download and install model |
| `cancel_model_install()` | Cancel model download |
| `delete_model(model_id)` | Delete installed model |
| `validate_model(model_id)` | Validate model integrity |
| `get_download_links(model_id)` | Get download URLs |

#### Export & Import

| Method | Description |
|--------|-------------|
| `export_record(record_id, fmt, include_ai)` | Export to md/txt/srt/docx |
| `import_record(file_path)` | Import file as record |
| `export_backup(path, options)` | Full data backup |
| `import_backup(path)` | Restore from backup |

#### Configuration

| Method | Description |
|--------|-------------|
| `get_config()` | Get all app configuration |
| `update_config(config)` | Update configuration |
| `list_ai_presets()` | List AI API presets |
| `create_ai_preset(data)` | Create AI preset |
| `update_ai_preset(preset_id, data)` | Update AI preset |
| `delete_ai_preset(preset_id)` | Delete AI preset |
| `set_active_ai_preset(preset_id)` | Set active preset |
| `list_processing_presets()` | List processing presets |
| `create_processing_preset(data)` | Create processing preset |

#### Utility

| Method | Description |
|--------|-------------|
| `pick_directory()` | Open directory picker dialog |
| `pick_audio_file()` | Open audio file picker |
| `pick_file(file_types)` | Open generic file picker |
| `pick_image_files()` | Open image file picker (multi) |
| `list_audio_files()` | List all audio files with metadata |
| `delete_audio_file(file_path)` | Delete audio file |
| `open_file(file_path)` | Open file with system app |
| `open_folder(folder_path)` | Open folder in file explorer |
| `get_dependency_status()` | Check ffmpeg/yt-dlp status |
| `install_static_ffmpeg()` | Install static ffmpeg |

---

## Technology Decisions

### Decision Log

| Decision | Choice | Rationale | Alternatives Considered |
|----------|--------|-----------|------------------------|
| Desktop framework | pywebview (via pywebvue) | Lightweight, native OS window, no bundled Chromium | Electron (too heavy), Tauri (Rust learning curve) |
| ASR engine | sherpa-onnx | Best local ASR quality, multiple model support, streaming | Vosk (lower quality), Whisper ONNX (no streaming) |
| Alternative ASR | whisper.cpp | GPU acceleration, high accuracy, separate from onnx runtime | OpenAI Whisper API (cloud only) |
| OCR engine | RapidOCR | PP-OCRv4/v5 support, easy model management | PaddleOCR (complex setup), Tesseract (lower CJK quality) |
| State management | Pinia | Official Vue 3 recommendation, TypeScript friendly | Vuex 4 (legacy API) |
| UI framework | DaisyUI 5 + Tailwind CSS 4 | Rapid development, built-in theming, dark mode | Headless UI (more manual), Element Plus (opinionated) |
| Build tool | Vite 6 | Fast HMR, native ESM, Vue plugin | Webpack (slower), Rollup (less integrated) |
| Database | SQLite (WAL) | Zero-config, embedded, good for desktop apps | PostgreSQL (overkill), IndexedDB (limited) |
| Audio format | MP3 | 90% size reduction vs WAV, universal compatibility | WAV (large), OGG (less compatible) |
| Package manager | uv (Python) / bun (Node) | uv: fast, reliable. bun: fast, compatible | pip/npm (slower) |

---

## Cross-Cutting Concerns

### Threading Model

- All long-running operations run in background threads via `dispatch_task()`
- Frontend communicates via event queue (thread-safe)
- Main thread handles UI and database writes
- Background threads handle ASR, OCR, AI, downloads

### Error Handling

- Global exception handler: `handle_exception()` catches unhandled exceptions
- All `@expose` methods return `{ success: bool, data?, error? }` envelope
- Frontend shows error dialogs for failed API calls
- Network errors during downloads are retried with user notification

### Configuration

- Config stored in `app_config` SQLite table (key-value)
- Config loaded at startup, cached in memory
- Frontend syncs config via `get_config()` / `update_config()`
- Model paths resolved relative to app root directory
- PyInstaller environment detection: `sys._MEIPASS` vs development mode

### Platform Compatibility

- Windows: primary development platform
- macOS: secondary, handles microphone permissions, Homebrew paths
- File paths: `pathlib.Path` for cross-platform compatibility
- Audio: `soundfile` + `audioread` for cross-platform audio I/O
- GPU: CUDA detection via `py/gpu_detect.py` (Windows only)
