# SherpaNote - AI-Powered Voice Learning Assistant

![SherpaNote Screenshot](reference/preview.png)

[README_zh](README_zh.md)

SherpaNote is an intelligent voice learning assistant that combines real-time speech recognition with AI-powered text processing. Record your thoughts, lectures, or conversations, and let SherpaNote automatically transcribe and enhance your content with AI polishing, note organization, mind mapping, and brainstorming capabilities.

Built on the **PyWebVue** framework, SherpaNote provides a seamless desktop experience with native performance across Windows and macOS, while leveraging the power of modern web technologies for the user interface.

## Features

### Speech Recognition
- **Real-time streaming transcription** with live partial results (Zipformer/Paraformer online models)
- **Offline audio file transcription** with VAD-based segmentation and progress tracking
- **Simulated streaming** - VAD + offline model pipeline enabling real-time display for offline-only models (SenseVoice, Qwen3-ASR, Cohere Transcribe)
- **GPU acceleration** - automatic NVIDIA CUDA detection, significantly speeds up transcription for large models (Qwen3-ASR, Whisper)
- **Whisper.cpp integration** - optional ASR backend with broader model support and hardware compatibility
- **Multi-language support** - 14 languages including Chinese, English, Japanese, Korean, Cantonese, and more
- **10+ ASR models** from multiple providers (Paraformer, SenseVoice, Whisper, Qwen3-ASR, FunASR Nano, Cohere Transcribe)
- **Automatic model type detection** - streaming/offline/simulated-streaming classification based on file heuristics, supporting user-downloaded models
- **Configurable VAD** - tunable voice activity detection parameters (threshold, silence/speech duration, max speech duration)
- **macOS audio compatibility** - AudioContext resampling, silence detection with user warnings, and retry logic

### AI Processing
- **Text polishing**: Refine and improve your transcribed text
- **Smart notes**: Convert raw transcripts into organized notes
- **Mind mapping**: Generate visual mind maps (Markmap/Mermaid) from your content
- **Brainstorming**: Expand on ideas with AI-generated suggestions
- **Streaming responses**: Real-time AI token streaming with truncation detection and "Continue" recovery
- **Custom AI presets**: User-defined processing templates with custom prompts
- **Multi-provider API management**: Configure multiple AI providers (OpenAI-compatible, OpenRouter) with connection testing
- **Auto AI processing**: Automatically run selected AI modes after transcription completes

### Data Management
- **Persistent storage**: All records saved locally with SQLite database (WAL mode)
- **Version history**: Manual version snapshots with restore, content-diff dirty detection, and configurable retention limits
- **Audio management**: Dedicated audio file management view, re-transcription, flexible recording/import workflows
- **Search functionality**: Find records by keywords in title or transcript
- **Import/Export**: Support for Markdown, TXT, DOCX, and SRT formats

### Model Management
- **Multi-source download**: GitHub, HuggingFace, HF-Mirror, GitHub Proxy, and ModelScope
- **Proxy support**: None / System proxy / Custom proxy with configurable settings
- **Model catalog**: 10+ curated ASR models with size, language, and source availability badges
- **One-click installation**: Download, install, validate models directly from the app
- **Custom model support**: Any sherpa-onnx compatible model placed in the models directory is auto-detected
- **Related links**: Quick access to model sources, subtitle generation tools, and documentation

### User Experience
- **Notion-inspired design**: Clean, modern interface built with Vue 3 and DaisyUI 5 + Tailwind CSS 4
- **Dark/light mode**: Automatic theme switching with system preference detection
- **Chinese UI localization**: Full Chinese interface
- **Collapsible panels**: Transcript and audio player sections can be collapsed for more workspace
- **Native file dialogs**: Platform-native file and folder pickers via pywebview

## Technology Stack

### Backend (Python)
- **Python 3.10+**: Core application logic
- **sherpa-onnx**: Local-first speech recognition engine (Paraformer, SenseVoice, Whisper, Qwen3-ASR, FunASR Nano, Cohere Transcribe)
- **OpenAI-compatible API**: AI text processing and generation (supports OpenRouter and custom endpoints)
- **pywebview**: Native desktop window management (via PyWebVue framework)
- **SQLite (WAL mode)**: Local data persistence with atomic transactions
- **uv**: Fast Python package management and execution

### Frontend (Vue.js)
- **Vue 3**: Reactive user interface framework
- **TypeScript**: Type-safe JavaScript development
- **Vite**: Blazing fast development server and build tool
- **Tailwind CSS 4**: Utility-first CSS framework
- **DaisyUI 5**: Beautiful component library with built-in theming
- **Pinia**: State management for Vue applications
- **Web Audio API**: Browser-based audio capture with PCM streaming to backend

### Build & Deployment
- **PyInstaller**: Desktop application packaging (onedir/onefile)
- **Cross-platform**: Single codebase for Windows and macOS
- **CUDA builds**: Optional GPU-accelerated builds with `--cuda` flag
- **bun**: Frontend package management

## Quick Start

### Prerequisites
- **Python 3.10 or higher**
- **uv** package manager: [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **bun** for frontend dependencies

### Installation
```bash
# Clone the repository
git clone https://github.com/wish2333/sherpanote.git
cd sherpanote

# Install dependencies and start development server
uv run dev.py
```

### Development Commands
```bash
# Start development environment (Vite + Python app)
uv run dev.py

# Only install dependencies (no app startup)
uv run dev.py --setup

# Load from built frontend (production preview)
uv run dev.py --no-vite
```

## Building & Packaging

### Desktop Applications
```bash
# Build directory-based application (recommended)
uv run build.py

# Build single executable file
uv run build.py --onefile

# Build with bundled ASR models (directory mode only)
uv run build.py --with-models sherpa-onnx-paraformer-zh-small-2024-03-09

# Build with CUDA GPU acceleration (NVIDIA, requires CUDA toolkit + cuDNN)
uv run build.py --cuda
uv run build.py --cuda --cuda-variant cuda12.cudnn9  # CUDA 12.x + cuDNN 9

# Clean build artifacts
uv run build.py --clean
```

## Usage Guide

### Recording Audio
1. Click the **Record** button in the main interface
2. Speak naturally - you'll see live transcription updates
3. Click **Stop** when finished
4. Your recording is automatically saved with audio file and transcript

### Processing with AI
1. Select any record from your list
2. Choose an AI mode: **Polish**, **Note**, **Mindmap**, or **Brainstorm**
3. Click **Process** to enhance your content
4. View results in real-time as AI tokens stream in

### Managing Models
1. Go to **Settings** > **Model Settings** for active model selection and VAD parameters
2. Go to **Settings** > **Model Management** to browse, download, and install models
3. Models are automatically classified as streaming/offline and appear in the correct dropdowns

### Importing & Exporting
- **Import**: Drag and drop audio files, or use the import button to copy files into the managed audio directory
- **Export**: Use the export menu in the editor view (MD, TXT, DOCX, SRT formats)

## Project Structure

```
sherpanote/
├── frontend/           # Vue.js frontend application
│   ├── src/
│   │   ├── components/ # Reusable UI components
│   │   │   ├── AiProcessor.vue       # AI processing control panel
│   │   │   ├── AudioRecorder.vue     # Microphone recording with silence detection
│   │   │   ├── ExportMenu.vue        # Multi-format export dropdown
│   │   │   ├── RecordCard.vue        # Record list item
│   │   │   ├── SearchBar.vue         # Keyword search and filter
│   │   │   ├── TranscriptPanel.vue   # Transcript display and editing
│   │   │   ├── VersionHistory.vue    # Version list with restore/delete
│   │   │   ├── MindMapPreview.vue    # Mermaid mind map renderer
│   │   │   ├── MarkdownRenderer.vue  # Markdown content renderer
│   │   │   └── ThemeToggle.vue       # Dark/light mode switch
│   │   ├── views/
│   │   │   ├── HomeView.vue          # Record list with search/filter
│   │   │   ├── RecordView.vue        # Recording and file transcription
│   │   │   ├── EditorView.vue        # Transcript editing + AI processing
│   │   │   ├── SettingsView.vue      # Full settings (General, Model, AI, ASR tabs)
│   │   │   └── AudioManageView.vue   # Audio file management
│   │   ├── composables/
│   │   │   ├── useRecording.ts       # Audio capture, resampling, silence detection
│   │   │   ├── useTranscript.ts      # Transcription event handling
│   │   │   ├── useAiProcess.ts       # AI streaming and result management
│   │   │   └── useStorage.ts         # CRUD operations and version control
│   │   ├── stores/
│   │   │   └── appStore.ts           # Global state (config, models, settings)
│   │   ├── bridge.ts                 # PyWebVue bridge: call(), onEvent()
│   │   └── types.ts                  # TypeScript type definitions
│   └── index.html
├── py/                 # Python backend modules
│   ├── asr.py                 # ASR engine (streaming/offline/simulated streaming)
│   ├── llm.py                 # AI text processing with streaming
│   ├── config.py              # App configuration management
│   ├── storage.py             # SQLite persistence + version control
│   ├── model_manager.py       # Model download, install, validate (5 sources)
│   ├── model_registry.py      # Model catalog (10+ models)
│   ├── presets.py             # AI API preset management
│   ├── processing_presets.py  # AI processing template management
│   ├── gpu_detect.py          # NVIDIA CUDA detection and verification
│   ├── whispercpp.py          # Whisper.cpp ASR backend integration
│   ├── video_downloader.py    # Video download for transcription
│   └── io.py                  # Audio I/O utilities
├── pywebvue/           # PyWebVue framework core
├── main.py             # Application entry point + Bridge API
├── dev.py              # Development startup script
├── build.py            # Build and packaging script
└── app.spec            # PyInstaller configuration
```

## Configuration

SherpaNote uses a persistent configuration system stored in SQLite. Key configuration options include:

- **General**: Data directory, max version history, auto punctuation, auto AI processing
- **Model Settings**: Active streaming/offline model, language, GPU toggle, VAD parameters (threshold, silence/speech duration)
- **AI Settings**: API presets (name, base URL, key, model), processing presets (name, mode, prompt template), temperature, max tokens, auto max tokens
- **Model Management**: Download source, proxy settings, model directory

Configuration can be modified through the **Settings** interface.

## Changelog

See [reference/Changelog.md](reference/Changelog.md) for the full changelog.

### [Unreleased]

- GPU acceleration with CUDA build support
- Whisper.cpp integration as optional ASR backend
- Real-time transcription progress with segment counts
- Video download for transcription
- Audio format optimization (WAV to MP3)

## Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a pull request

### Development Guidelines
- Follow the existing code style and patterns
- Write meaningful commit messages (conventional commits format)
- Ensure cross-platform compatibility (Windows + macOS)
- Update documentation for new features

### Reporting Issues
When reporting bugs or requesting features, please include:
- Your operating system and version
- Python version
- Steps to reproduce the issue
- Expected vs actual behavior
- Any error messages or logs

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)**: Next-generation speech recognition toolkit
- **[pywebview](https://github.com/r0x0r/pywebview)**: Cross-platform native GUI library
- **[PyWebVue](https://github.com/nicepkg/pywebvue)**: Vue + pywebview desktop framework
- **[Vue.js](https://vuejs.org/)**: Progressive JavaScript framework
- **[Tailwind CSS](https://tailwindcss.com/)**: Utility-first CSS framework
- **[DaisyUI](https://daisyui.com/)**: Component library for Tailwind CSS
- **[Hugging Face](https://huggingface.co/)**: Open-source model hosting platform
- **[ModelScope](https://www.modelscope.cn/)**: Model community by Alibaba
