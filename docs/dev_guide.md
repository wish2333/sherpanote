# Development Guide

> Technical conventions, patterns, and development workflow for SherpaNote.
> AI reads this to understand HOW to write code for this project.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend Language | Python | 3.11+ |
| Backend Framework | pywebvue (pywebview) | latest |
| ASR Engine | sherpa-onnx | latest |
| ASR Alternative | whisper.cpp | latest binary |
| OCR Engine | RapidOCR (rapidocr-onnxruntime) | latest |
| PDF Rendering | pypdfium2 | latest |
| PDF Text Detection | pdfplumber (via markitdown) | latest |
| Document Extraction | markitdown | latest |
| Plugin: docling | docling (with RapidOCR OCR backend) | latest |
| Plugin: opendataloader | opendataloader-pdf (requires Java 17+) | latest |
| AI Integration | openai (Python SDK) | latest |
| Frontend Framework | Vue 3 | 3.5+ |
| Frontend Language | TypeScript | 5.x |
| UI Library | DaisyUI 5 + Tailwind CSS 4 | 4.0+ / 5.x |
| State Management | Pinia | 2.3+ |
| Routing | Vue Router | 4.5+ |
| Build Tool (frontend) | Vite | 6.0+ |
| Build Tool (desktop) | PyInstaller | latest |
| Package Manager (Python) | uv | latest |
| Package Manager (Node) | bun | latest |
| Database | SQLite (WAL mode) | built-in |

---

## Project Structure

```
sherpanote/
  main.py                     # Application entry point, SherpaNoteAPI class
  py/                         # Core Python modules
    __init__.py
    config.py                 # Application configuration
    storage.py                # SQLite database layer
    asr.py                    # ASR engine (sherpa-onnx)
    ocr.py                    # OCR engine (RapidOCR)
    document_extractor.py      # Document extraction decision tree
    text_detector.py           # File classification + PDF text layer detection
    adapters/
      ppocr_adapter.py         # PP-OCR -> ExtractedDocument adapter
      markitdown_adapter.py    # markitdown -> ExtractedDocument adapter
    outputs/
      unified_document.py      # ExtractedDocument unified data model
    plugins/                   # Plugin system
      runners/
        docling_runner.py      # docling adapter with RapidOCR backend
        opendata_runner.py     # opendataloader-pdf adapter (requires Java)
    llm.py                    # AI text processing (OpenAI API)
    model_manager.py          # ASR model download and management
    model_registry.py         # ASR model definitions
    whispercpp.py             # Whisper.cpp integration
    whispercpp_registry.py    # Whisper model definitions
    video_downloader.py       # yt-dlp video download
    gpu_detect.py             # NVIDIA GPU detection
    presets.py                # AI processing preset definitions
    processing_presets.py     # Extended preset management
    io.py                     # File I/O utilities
    backup.py                 # Data backup/restore
  pywebvue/                   # PyWebVue framework
    ...                       # (vendored, do not modify)
  frontend/                   # Vue.js frontend
    src/
      App.vue                 # Root component
      main.ts                 # Entry point
      bridge.ts               # Python bridge interface
      components/             # Reusable Vue components
      views/                  # Page views (Home, Record, Editor, Settings, OCR, AudioManage)
      components/settings/    # Settings sub-components (DocumentSettingsPanel, etc.)
      stores/                 # Pinia stores (appStore.ts)
      composables/            # Vue composables (useRecording, useTranscript, useAiProcess, usePlugin, etc.)
      types/                  # TypeScript type definitions
      styles/                 # Global styles
      router/                 # Vue Router configuration
    index.html                # HTML entry
    package.json              # Frontend dependencies
    vite.config.ts            # Vite configuration
    tailwind.config.ts        # Tailwind configuration (if present)
  models/                     # ASR model files directory
  data/                       # Runtime data
    data.db                   # SQLite database
    audio/                    # Audio files
    rapid_ocr_models/         # OCR model files
    audio_meta.json           # Audio metadata (filename -> record mapping)
  tools/                      # External tools
    whisper/                  # whisper.cpp binary and models
  build.py                    # PyInstaller build script
  app.spec                    # PyInstaller spec file
  pyproject.toml              # Python project config
  reference/                  # Design references and documentation
  docs/                       # Documentation (this directory)
  .claude/                    # AI configuration
```

---

## Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Files (frontend) | kebab-case or PascalCase (components) | `use-recording.ts`, `AudioRecorder.vue` |
| Files (backend) | snake_case | `model_manager.py` |
| Components | PascalCase | `AudioRecorder.vue`, `TranscriptPanel.vue` |
| Functions (Python) | snake_case | `save_record()`, `process_text_stream()` |
| Functions (TypeScript) | camelCase | `fetchRecords()`, `handleExport()` |
| Constants | UPPER_SNAKE_CASE | `MAX_VERSIONS`, `DEFAULT_SAMPLE_RATE` |
| CSS Classes | Tailwind utilities + kebab-case custom | `task-card`, `bg-primary` |
| Database columns | snake_case | `created_at`, `duration_seconds` |
| API methods | snake_case | `list_records()`, `export_backup()` |
| Events (bridge) | snake_case | `stream_token`, `progress_update` |
| Composables | camelCase with `use` prefix | `useRecording`, `useAiProcess` |
| Stores | camelCase with `Store` suffix | `appStore` |

---

## Code Patterns

### Pattern: Bridge API Call (Frontend)

**When to use**: Calling any backend method from Vue component

```typescript
// In a Vue component or composable
import { bridge } from '../bridge'

// Simple call
const result = await bridge.call('method_name', arg1, arg2)
if (result.success) {
  // use result.data
} else {
  // handle result.error
}

// Event listener
bridge.on('event_name', (payload) => {
  // handle event
})
```

### Pattern: Expose API Method (Backend)

**When to use**: Adding a new backend API method

```python
@expose
def my_method(self, param: str) -> dict:
    """Description of what this method does."""
    def _work() -> None:
        # Long-running work here
        bridge.emit('progress', {'percent': 50})
        # ...
        bridge.emit('result', {'data': ...})

    self.dispatch_task('my_method', {})
    return {'success': True}
```

### Pattern: Background Task with Progress

**When to use**: Any long-running operation (ASR, OCR, AI, download)

```python
@expose
def my_long_task(self, input_data: str) -> dict:
    def _work() -> None:
        for i in range(total):
            # Do chunk of work
            bridge.emit('progress_update', {
                'percent': int((i + 1) / total * 100),
                'info': {'current': i + 1, 'total': total}
            })
        bridge.emit('task_complete', {'result': final_data})

    self.dispatch_task('my_long_task', {})
    return {'success': True}
```

### Pattern: Error Handling (Backend)

**When to use**: All @expose methods

```python
try:
    # operation
    return {'success': True, 'data': result}
except SpecificError as e:
    return {'success': False, 'error': {'code': 'SPECIFIC_ERROR', 'message': str(e)}}
except Exception as e:
    return {'success': False, 'error': {'code': 'UNKNOWN', 'message': 'Operation failed'}}
```

### Pattern: Pinia Store (Frontend)

**When to use**: Managing shared application state

```typescript
// stores/appStore.ts
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    records: [] as Record[],
    config: {} as AppConfig,
    dirty: new Set<string>(),
  }),
  actions: {
    async fetchRecords(filter?: RecordFilter) {
      const result = await bridge.call('list_records', filter ?? {})
      if (result.success) this.records = result.data
    },
  },
})
```

---

## API Communication

### Request Pattern

```typescript
// Frontend -> Backend
const result = await bridge.call('method_name', ...args)
```

### Response Format

```json
{
  "success": true,
  "data": {}
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "User-friendly message"
  }
}
```

---

## Build & Run

### Development

```bash
# Backend (runs pywebview window)
cd sherpanote && uv run python main.py

# Frontend dev server (for UI development only)
cd sherpanote/frontend && bun run dev

# Frontend build (required before desktop run)
cd sherpanote/frontend && bun run build
```

### Build Desktop App

```bash
# Standard build
cd sherpanote && uv run python build.py

# CUDA build (Windows only)
cd sherpanote && uv run python build.py --cuda

# CUDA build with specific variant
cd sherpanote && uv run python build.py --cuda --cuda-variant 12

# Build with OCR models
cd sherpanote && uv run python build.py --with-ocr-models
```

### Frontend Build

```bash
cd sherpanote/frontend && bun run build
# Output: ../frontend_dist/
```

---

## Important Notes

### PyInstaller Environment Detection

```python
import sys
import os

# Detect if running in PyInstaller bundle
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
```

### Threading Model

- All `@expose` methods return immediately
- Long-running work runs in `dispatch_task()` background threads
- Communicate results via `bridge.emit()` events
- Never call bridge methods from background threads directly

### Platform Differences

- **Windows**: Primary platform, CUDA GPU support
- **macOS**: Microphone permissions required (Info.plist), Homebrew paths for whisper.cpp
- Use `pathlib.Path` for all file path operations
- Audio: `soundfile` + `audioread` for cross-platform

---

## Common Pitfalls

| Pitfall | Symptom | Solution |
|---------|---------|----------|
| Frontend not updating | Changes not visible in app | Run `bun run build` in frontend/ |
| Model not found | "Model not installed" error | Check models/ directory, run install |
| Bridge call hangs | UI freezes | Ensure method uses `dispatch_task()` for long work |
| Audio not recording | No sound in recording | Check mic permissions (macOS: system prefs) |
| GPU not detected | Always using CPU | Verify NVIDIA driver, run `detect_gpu()` |
| Whisper binary missing | "whisper-cli not found" | Run `install_whisper_binary()` |
| ffmpeg not found | "ffmpeg not found" during video download | Run `install_static_ffmpeg()` |
| SQLite locked | "database is locked" error | Ensure WAL mode enabled, check for unclosed connections |
| Duplicate record on import | Same file imported twice | Check `audio_meta.json` before importing |
