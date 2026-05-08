# Development Guide

> Quick reference for SherpaNote contributors. Covers setup, architecture, conventions, and common workflows.

---

## 1. Environment Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- uv (Python package manager)
- bun (Node package manager)
- Git

### Initial Setup

```bash
git clone <repo-url> && cd sherpanote
uv run dev.py --setup
cd frontend && bun install
```

### Running in Development Mode

```bash
# Full dev environment: Vite dev server on :5173 + pywebview window
uv run dev.py

# Preview using pre-built frontend
uv run dev.py --no-vite
```

---

## 2. Project Architecture

### Communication: PyWebVue Bridge (NOT REST/WebSocket)

```
Frontend (Vue 3)  <-->  pywebview JS-Python Bridge  <-->  Backend (Python)
     |                        |                              |
  bridge.ts              window.pywebview.api          @expose methods
  call<T>(method)                                       returns ApiResponse<T>
  onEvent(event)     <--   self._emit(event, data)  <--   background threads
```

- **Frontend -> Backend**: `bridge.ts` calls `window.pywebview.api.<method>(...args)` which invokes Python `@expose`-decorated methods. Returns `ApiResponse<T>` with `{success, data?, error?}`.
- **Backend -> Frontend**: Python calls `self._emit(event, data)`. A JS timer (50ms) polls `flush_events()` and dispatches `CustomEvent` named `pywebvue:{event}`.
- **Thread safety**: Background threads cannot call `evaluate_js` directly (Windows COM restriction). Events and tasks are queued and drained by JS timers on the main thread.

### Entry Point Flow

`main.py`:
1. Pre-imports `sherpa_onnx` before pywebview (avoids Windows DLL conflicts with WebView2)
2. Creates `SherpaNoteAPI(Bridge)` instance
3. Creates `App(api, title="SherpaNote", frontend_dir="frontend_dist")`
4. Registers `_shutdown_cleanup` via `atexit`
5. Calls `app.run()`

---

## 3. Backend Layout (`py/`)

| Module | Role |
|--------|------|
| `config.py` | Immutable frozen dataclasses (`AppConfig`, `AsrConfig`, etc.) persisted as JSON in SQLite |
| `storage.py` | SQLite WAL mode, Record/Version CRUD, FTS5 full-text search, multi-format export |
| `asr.py` | Streaming (OnlineRecognizer) and file-based (OfflineRecognizer) transcription via sherpa-onnx |
| `asr_recognizer.py` | ASR engine abstraction layer |
| `llm.py` | OpenAI-compatible API with streaming, 4 modes: polish/note/mindmap/brainstorm |
| `ocr.py` | RapidOCR wrapper (PP-OCRv4/v5), PDF-to-image conversion |
| `document_extractor.py` | Decision tree: Images->PP-OCR, Office->markitdown, PDF->text layer detection->engine |
| `text_detector.py` | PDF text layer detection using pdfplumber |
| `model_manager.py` | Model download from 5 sources (GitHub, HuggingFace, HF-Mirror, GitHub Proxy, ModelScope) |
| `model_registry.py` | ASR model definitions and registry |
| `whispercpp.py` | Optional whisper.cpp CLI backend |
| `whispercpp_registry.py` | Whisper.cpp model registry (cpu/blas/cuda variants) |
| `gpu_detect.py` | NVIDIA GPU and CUDA version auto-detection |
| `io.py` | Audio I/O utilities |
| `backup.py` | Data backup and restore |
| `video_downloader.py` | yt-dlp wrapper for video download |
| `presets.py` | AI API preset management |
| `processing_presets.py` | AI processing preset templates |
| `file_matcher.py` | File type detection and matching |
| `adapters/` | Backend wrappers producing unified `ExtractedDocument` (ppocr, markitdown, docling, opendata) |
| `plugins/` | Subprocess-isolated runtime for optional heavy backends |
| `api/` | Bridge-exposed API methods organized by domain |

### Plugin System

Optional backends (docling, opendataloader-pdf) run in a dedicated subprocess:

- `plugins/manager.py` -- venv lifecycle, package install/uninstall via `uv pip`
- `plugins/runner.py` -- subprocess execution: base64 JSON args via CLI, JSON stdout, JSON lines stderr
- `plugins/paths.py` -- path resolution for frozen (PyInstaller) vs dev mode
- `plugins/runners/` -- CLI entry points executed inside plugin venv
- `plugins/java_detect.py` -- Java 11+ runtime detection for opendataloader-pdf

Built-in backends (PP-OCR, markitdown) run in-process directly.

---

## 4. Frontend Layout (`frontend/src/`)

| Path | Role |
|------|------|
| `bridge.ts` | All Python communication: `call<T>(method, ...args)` and `onEvent(event, handler)` |
| `stores/appStore.ts` | Single Pinia store for global state (config, models, theme, processing states) |
| `composables/` | Domain logic hooks |
| `views/` | 6 route views |
| `components/` | Reusable UI components |
| `types/index.ts` | TypeScript interfaces mirroring Python dataclasses |
| `router/` | Hash-based routing (`createWebHashHistory`) |

### Views

| View | Route | Purpose |
|------|-------|---------|
| `HomeView` | `/` | Record list, search, drag-drop import |
| `RecordView` | `/record` | Audio recording with real-time transcription |
| `EditorView` | `/editor/:id` | Transcript editing, AI processing, version history |
| `SettingsView` | `/settings` | ASR/AI/OCR/Plugin/GPU configuration |
| `AudioManageView` | `/audio` | Audio file management |
| `OcrView` | `/ocr` | Image/PDF OCR processing |

### Composables

| Composable | Purpose |
|------------|---------|
| `useRecording` | Microphone access, audio capture, recording state |
| `useTranscript` | Transcription display, segment management |
| `useAiProcess` | AI text processing with streaming |
| `useStorage` | Record CRUD, search, export |
| `usePlugin` | Plugin management operations |
| `useDragDrop` | File drag-and-drop handling |

---

## 5. Key Technical Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| sherpa-onnx import order | Must import before pywebview | Windows ONNX Runtime DLLs conflict with WebView2 |
| Config objects | Frozen dataclasses | Immutable updates prevent hidden side effects |
| Plugin subprocess protocol | Base64 JSON via CLI | Safe arg passing, structured progress reporting |
| PDF text layer detection | pdfplumber | Determine routing before choosing extraction engine |
| Frontend routing | Hash-based | pywebview serves local files, no server-side routing |
| GPU build isolation | Separate temporary venv | Avoid CUDA packages polluting dev environment |
| Simulated streaming | VAD + OfflineRecognizer | Enable real-time UX with offline-only models |

---

## 6. Data Directory

| Mode | Path |
|------|------|
| Frozen (packaged) | `{executable_dir}/data/` |
| Dev mode | `{project_root}/data/` |

Contents: SQLite database, ASR models, OCR models, plugin venv, logs, audio files, temp files.

---

## 7. Conventions

### Naming

- Backend methods: `snake_case`, exposed via `@expose`
- Frontend composables: `use<Domain>` (e.g., `useRecording`, `useStorage`)
- Config dataclasses: `<Name>Config` (e.g., `AsrConfig`, `AiConfig`)
- Events: `pywebvue:<domain>_<action>` (e.g., `pywebvue:transcribe_progress`)
- Files: Python `snake_case`, Vue `PascalCase`, TypeScript `camelCase`

### Frontend Style

- Tailwind utility classes as primary styling
- DaisyUI 5 components with custom themes (`sherpanote-dark`, `sherpanote-light`)
- Composition API with `<script setup>` syntax
- Scoped `<style>` blocks for component-specific overrides

### Backend Style

- Type hints on all public functions
- Error handling at every system boundary
- No global mutable state
- Immutable config pattern (frozen dataclasses)

---

## 8. Building

```bash
uv run build.py                                    # onedir build (recommended)
uv run build.py --onefile                           # Single executable
uv run build.py --with-models sherpa-onnx-streaming-whee  # Bundle ASR model
uv run build.py --with-ocr-models                   # Bundle PP-OCRv5 models
uv run build.py --with-plugins                      # Bundle plugin runtime (Python + uv)
uv run build.py --cuda                              # CUDA GPU build
uv run build.py --cuda --cuda-variant cuda12.cudnn9 # CUDA 12 + cuDNN 9
uv run build.py --clean                             # Remove build artifacts
```

### Frontend Build

```bash
cd frontend
bun run build          # Type-check (vue-tsc) + build to frontend_dist/
```

---

## 9. Plugin Development

```bash
# Check plugin status
uv run dev.py plugin status

# Install a backend
uv run dev.py plugin install docling
uv run dev.py plugin install opendataloader

# Test document extraction
uv run dev.py plugin test <file-path>

# Uninstall a backend
uv run dev.py plugin uninstall docling

# Detect Java runtime (for opendataloader)
uv run dev.py plugin detect-java
```

### Adding a New Backend Adapter

1. Create adapter in `py/adapters/<name>_adapter.py` implementing the unified interface
2. Register in `py/document_extractor.py` decision tree
3. If heavy deps, add runner in `py/plugins/runners/`
4. Add UI controls in `frontend/src/components/settings/DocumentSettingsPanel.vue`

---

## 10. Debugging

- **Logs**: Check `data/logs/` directory for application logs
- **Bridge issues**: Verify `@expose` decorator on Python methods, check `bridge.ts` method names match exactly
- **Thread issues**: Remember Windows COM restriction -- use `_emit()` + `run_on_main_thread()` from background threads
- **DLL conflicts**: Ensure `sherpa_onnx` is imported before `pywebview` in `main.py`
- **Plugin failures**: Check plugin venv at `data/plugins/venv/`, review subprocess stderr in logs
