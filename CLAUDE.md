# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SherpaNote is an AI-powered voice learning assistant -- a desktop app built on PyWebVue (pywebview + Vue 3 bridge). It combines local speech recognition (sherpa-onnx), LLM text processing (OpenAI-compatible API), OCR (RapidOCR), and document extraction (markitdown, docling, opendataloader-pdf) with versioned note management.

## Development Commands

### Full Dev Environment (Vite + Python)
```bash
uv run dev.py              # Sync deps, start Vite dev server on :5173, launch pywebview
uv run dev.py --no-vite    # Preview using built frontend_dist/
uv run dev.py --setup      # Install dependencies only
```

### Frontend Only
```bash
cd frontend
bun install                # Install frontend deps
bun dev                    # Vite dev server on :5173
bun run build              # Type-check (vue-tsc) + build to frontend_dist/
```

### Build Desktop App
```bash
uv run build.py                                    # onedir build (recommended)
uv run build.py --onefile                           # Single executable
uv run build.py --with-models sherpa-onnx-streaming-whee  # Bundle ASR model
uv run build.py --with-ocr-models                   # Bundle PP-OCRv5 models
uv run build.py --with-plugins                      # Bundle plugin runtime (Python + uv)
uv run build.py --cuda                              # CUDA GPU build
uv run build.py --cuda --cuda-variant cuda12.cudnn9 # CUDA 12.8 + cuDNN 9
uv run build.py --clean                             # Remove build artifacts
```

### Plugin Management
```bash
uv run dev.py plugin status              # Show plugin/backend status
uv run dev.py plugin install docling     # Install docling backend
uv run dev.py plugin install opendataloader  # Install opendataloader backend
uv run dev.py plugin uninstall docling   # Uninstall a backend
uv run dev.py plugin destroy             # Destroy plugin venv
uv run dev.py plugin detect-java         # Detect Java 11+ runtime
uv run dev.py plugin test FILE           # Test document extraction on a file
```

## Architecture

### Communication Pattern: PyWebVue Bridge (NOT REST/WebSocket)

The frontend and backend communicate through pywebview's native JS-Python bridge, not HTTP:

- **Frontend -> Backend**: `bridge.ts` calls `window.pywebview.api.<method>(...args)` which invokes Python methods decorated with `@expose` in the `Bridge` subclass. Returns `ApiResponse<T>` with `{success, data?, error?}`.
- **Backend -> Frontend**: Python calls `self._emit(event, data)` to queue events. A JS timer (50ms) polls `flush_events()` and dispatches `CustomEvent` objects named `pywebvue:{event}`. Frontend listens via `onEvent(event, handler)`.
- **Thread safety**: Background Python threads cannot call `evaluate_js` directly (Windows COM/WebView2 restriction). Events and tasks are queued and drained by JS timers on the main thread.

### Entry Point Flow

`main.py` bottom:
1. Pre-imports `sherpa_onnx` and loads ONNX Runtime DLLs **before** pywebview initializes WebView2 (critical: avoids Windows DLL conflicts)
2. Creates `SherpaNoteAPI(Bridge)` instance
3. Creates `App(api, title="SherpaNote", frontend_dir="frontend_dist")`
4. Registers `_shutdown_cleanup` via `atexit`
5. Calls `app.run()`

### Backend Layout (`py/`)

| Module | Role |
|--------|------|
| `config.py` | Immutable frozen dataclasses (`AppConfig`, `AsrConfig`, `OcrConfig`, `AiConfig`, `PluginConfig`, `DocumentConfig`) persisted as JSON in SQLite |
| `storage.py` | SQLite WAL mode -- Record/Version CRUD, FTS5 full-text search, multi-format export |
| `asr.py` | Streaming (OnlineRecognizer) and file-based (OfflineRecognizer) transcription via sherpa-onnx |
| `llm.py` | OpenAI-compatible API with streaming, 4 modes: polish/note/mindmap/brainstorm |
| `ocr.py` | RapidOCR wrapper (PP-OCRv4/v5), PDF-to-image conversion |
| `document_extractor.py` | Decision tree: Images->PP-OCR, Office->markitdown, PDF->text layer detection->engine selection |
| `model_manager.py` | Model download from 5 sources (GitHub, HuggingFace, HF-Mirror, GitHub Proxy, ModelScope) |
| `adapters/` | Backend wrappers producing unified `ExtractedDocument` output (ppocr, markitdown, docling, opendata) |
| `plugins/` | Subprocess-isolated runtime for optional heavy backends (docling, opendataloader-pdf) |

### Plugin System (Runtime Isolation)

Optional document extraction backends (docling, opendataloader-pdf) run in a dedicated Python subprocess using bundled `python-build-standalone` + `uv`:

- `plugins/manager.py` -- PluginManager: venv lifecycle, package install/uninstall via `uv pip`
- `plugins/runner.py` -- Subprocess execution: base64-encoded JSON args via CLI, JSON stdout for results, JSON lines on stderr for progress events
- `plugins/paths.py` -- Path resolution for frozen (PyInstaller) vs dev mode
- `plugins/runners/` -- CLI entry points executed inside the plugin venv

Built-in backends (PP-OCR, markitdown) run in-process directly.

### Frontend Layout (`frontend/src/`)

- `bridge.ts` -- All Python communication goes through `call<T>(method, ...args)` and `onEvent(event, handler)`
- `stores/appStore.ts` -- Single Pinia store for global state (config, models, theme, processing states)
- `composables/` -- Domain logic: useRecording, useTranscript, useAiProcess, usePlugin, useStorage, useDragDrop
- `views/` -- 6 routes: Home(`/`), Record(`/record`), Editor(`/editor/:id`), Settings(`/settings`), AudioManage(`/audio`), OCR(`/ocr`)
- `types/index.ts` -- TypeScript interfaces mirroring Python dataclasses

### PyWebVue Framework (`pywebvue/`)

Custom framework layer:
- `bridge.py` -- `Bridge` base class with `@expose` decorator, thread-safe `_emit()`, `run_on_main_thread()`
- `app.py` -- `App` class wrapping pywebview, handles PyInstaller frozen path resolution, dev/prod URL switching

## Key Technical Decisions

- **sherpa-onnx must be imported before pywebview**: On Windows, ONNX Runtime DLLs conflict with WebView2 if loaded after pywebview initialization. The pre-import in `main.py` is intentional.
- **Immutable configs**: All config objects are frozen dataclasses. Updates create new instances, persisted as JSON in SQLite.
- **Plugin subprocess protocol**: Args are base64-encoded JSON passed via `--json-input` CLI flag. Results come on stdout as JSON. Progress events come on stderr as JSON lines (`{"type": "progress", "percent": N, "message": "..."}`).
- **PDF text layer detection**: `text_detector.py` uses pdfplumber to check if a PDF has a text layer before routing to the appropriate engine.
- **Hash-based frontend routing**: `createWebHashHistory` is used because pywebview serves local files (no server-side routing).
- **DaisyUI themes**: Two custom themes (`sherpanote-dark`, `sherpanote-light`) with localStorage persistence.

## Naming Conventions

- **Backend methods**: snake_case, exposed to frontend via `@expose`
- **Frontend composables**: `use<Domain>` (e.g., `useRecording`, `useStorage`)
- **Config dataclasses**: `<Name>Config` (e.g., `AsrConfig`, `AiConfig`)
- **Events**: `pywebvue:<domain>_<action>` (e.g., `pywebvue:transcribe_progress`)
- **Files**: Python snake_case, Vue PascalCase components, TypeScript camelCase composables

## Data Directory

- **Frozen (packaged)**: `{executable_dir}/data/`
- **Dev mode**: `{project_root}/data/`

Contains: SQLite database, ASR models, OCR models, plugin venv, logs, audio files, temp files.

### Release Flow

Releases are performed **manually by the user**. After the user commits or releases:

1. User provides commit message and/or release version info
2. AI invokes `/doc-sync` to update all documentation accordingly

## Prohibited Actions

- NEVER skip reading docs before coding
- NEVER modify code without understanding the corresponding business rule
- NEVER stop a task without code review and doc sync
- NEVER reuse context from a previous sub-agent task
- NEVER make more than one unverified change at a time
- NEVER ignore feedback from `feedback/index.md`

## Development Environment

- **OS**: Windows 11
- **Runtime**: Python 3.11+ / Node 20+
- **Package Manager (frontend)**: bun
- **Package Manager (backend)**: uv
- **Build Check (frontend)**: cd frontend && bun run build

## AI Behavior Rules

### Core Principles

1. **Document-first**: Always read relevant docs before coding. Docs > Code.
2. **No guessing**: When uncertain, ask the user. Never make assumptions.
3. **One change at a time**: Modify one thing, verify it works, then proceed.
4. **Evidence over intuition**: Gather evidence before forming conclusions.
5. **Sub-agent isolation**: Each sub-task gets a fresh instance, no inherited context.

### Document Priority

When conflicting information exists, follow this priority:

1. `docs/PRD-x.x.x.md` - Product requirements (highest)
2. `docs/design/*.md` - System design and architecture
3. `docs/procedures/*.md` - Business and system workflows
4. `docs/business_rules.md` - Domain-specific rules
5. `.claude/rules/*.md` - Coding standards
6. Source code (lowest)

### Mandatory Before Coding

Before writing any code, the AI MUST:

1. Read `docs/PRD-x.x.x.md` to understand the requirement
2. Read relevant design documents in `docs/design/`
3. Check `docs/business_rules.md` for domain constraints
4. Review `feedback/index.md` for known pitfalls and user preferences
5. Re-read all of the above at the start of each new phase (prevent requirement drift)

### Mandatory Before Stopping

Before ending a task, the AI MUST:

1. Run code review (via `ecc:code-review` skill)
2. Sync documentation (via `/doc-sync` skill if user provides commit/release info)
3. Record any new user feedback to `feedback/`