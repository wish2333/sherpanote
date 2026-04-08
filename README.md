# SherpaNote - AI-powered Voice Learning Assistant

![SherpaNote Screenshot](reference/preview.png)

[README_zh](README_zh.md)

SherpaNote is an intelligent voice learning assistant that combines real-time speech recognition with AI-powered text processing. Record your thoughts, lectures, or conversations, and let SherpaNote automatically transcribe and enhance your content with AI polishing, note organization, mind mapping, and brainstorming capabilities.

Built on the **PyWebVue** framework, SherpaNote provides a seamless desktop experience with native performance across Windows, macOS, and Linux, while leveraging the power of modern web technologies for the user interface.

## 🌟 Features

### 🎙️ Speech Recognition
- **Real-time streaming transcription** with live partial results
- **Offline audio file transcription** with progress tracking
- **Multi-language support** (Chinese, English, and auto-detection)
- **GPU acceleration** support for faster processing
- **Multiple ASR models** including Paraformer and Whisper variants

### 🤖 AI Processing
- **Text polishing**: Refine and improve your transcribed text
- **Smart notes**: Convert raw transcripts into organized notes
- **Mind mapping**: Generate visual mind maps from your content
- **Brainstorming**: Expand on ideas with AI-generated suggestions
- **Streaming responses**: Real-time AI token streaming for immediate feedback

### 💾 Data Management
- **Persistent storage**: All records saved locally with SQLite database
- **Version history**: Track changes and restore previous versions
- **Audio persistence**: Recorded audio files stored in organized directory structure
- **Search functionality**: Find records by keywords in title or transcript
- **Import/Export**: Support for Markdown, TXT, DOCX, and SRT formats

### 🔧 Model Management
- **Model registry**: Browse available ASR models with detailed information
- **One-click installation**: Download and install models directly from the app
- **Custom mirrors**: Configure custom download sources for faster access
- **Model validation**: Verify model integrity after installation
- **Active model selection**: Choose which models to use for streaming/offline recognition

### 🎨 User Experience
- **Responsive design**: Beautiful, modern interface built with Vue 3 and Tailwind CSS
- **Dark/light mode**: Automatic theme switching with system preference detection
- **Native file dialogs**: Platform-native file and folder pickers
- **Drag & drop**: Easy audio file import via drag and drop
- **Keyboard shortcuts**: Efficient workflow with keyboard navigation

## 🛠️ Technology Stack

### Backend (Python)
- **Python 3.10+**: Core application logic
- **sherpa-onnx**: Offline speech recognition engine
- **OpenAI API**: AI text processing and generation
- **pywebview**: Native desktop window management
- **SQLite**: Local data persistence
- **uv**: Fast Python package management and execution

### Frontend (Vue.js)
- **Vue 3**: Reactive user interface framework
- **TypeScript**: Type-safe JavaScript development
- **Vite**: Blazing fast development server and build tool
- **Tailwind CSS**: Utility-first CSS framework
- **DaisyUI**: Beautiful component library with built-in theming
- **Pinia**: State management for Vue applications

### Build & Deployment
- **PyInstaller**: Desktop application packaging
- **Buildozer**: Android APK generation (macOS/Linux only)
- **Cross-platform**: Single codebase for Windows, macOS, Linux, and Android

## 🚀 Quick Start

### Prerequisites
- **Python 3.10 or higher**
- **uv** package manager: [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **bun**, **npm**, or **yarn** for frontend dependencies

### Installation
```bash
# Clone the repository
git clone https://github.com/your-username/sherpanote.git
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

## 📦 Building & Packaging

### Desktop Applications
```bash
# Build directory-based application (recommended)
uv run build.py

# Build single executable file
uv run build.py --onefile

# Build with bundled ASR models (directory mode only)
uv run build.py --with-models sherpa-onnx-paraformer-zh-small-2024-03-09

# Clean build artifacts
uv run build.py --clean
```

### Android APK (macOS/Linux only)
```bash
# Build Android APK
uv run build.py --android
```

> **Note**: Android builds require macOS or Linux. Windows users can use WSL or Docker.

## 🎯 Usage Guide

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
1. Go to **Settings** → **ASR Engine**
2. Browse available models in the **Model Management** section
3. Click **Download** to install models
4. Use dropdowns to set active streaming and offline models

### Importing & Exporting
- **Import**: Drag and drop `.md` or `.txt` files, or use the import button
- **Export**: Right-click any record and choose export format (MD, TXT, DOCX, SRT)

## 📁 Project Structure

```
sherpanote/
├── frontend/           # Vue.js frontend application
│   ├── src/            # Source code
│   │   ├── components/ # Vue components
│   │   ├── views/      # Page views
│   │   ├── composables/# Vue composables
│   │   └── stores/     # Pinia stores
├── py/                 # Python backend modules
│   ├── asr.py          # Speech recognition logic
│   ├── llm.py          # AI processing logic
│   ├── storage.py      # Data persistence
│   └── model_manager.py # Model management
├── pywebvue/           # PyWebVue framework core
├── main.py             # Application entry point
├── dev.py              # Development startup script
├── build.py            # Build and packaging script
└── app.spec            # PyInstaller configuration
```

## ⚙️ Configuration

SherpaNote uses a persistent configuration system stored in SQLite. Key configuration options include:

- **Data Directory**: Where audio files and database are stored
- **ASR Settings**: Model directory, sample rate, GPU usage, mirror URL
- **AI Settings**: OpenAI API key, model selection, temperature
- **UI Preferences**: Theme, language, default view

Configuration can be modified through the **Settings** interface or programmatically via the API.

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a pull request

### Development Guidelines
- Follow the existing code style and patterns
- Write meaningful commit messages
- Include tests for new functionality when possible
- Update documentation for new features
- Ensure cross-platform compatibility

### Reporting Issues
When reporting bugs or requesting features, please include:
- Your operating system and version
- Python version
- Steps to reproduce the issue
- Expected vs actual behavior
- Any error messages or logs

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)**: Offline speech recognition toolkit
- **[pywebview](https://github.com/r0x0r/pywebview)**: Cross-platform native GUI library
- **[Vue.js](https://vuejs.org/)**: Progressive JavaScript framework
- **[Tailwind CSS](https://tailwindcss.com/)**: Utility-first CSS framework
- **[DaisyUI](https://daisyui.com/)**: Component library for Tailwind CSS

---

Made with ❤️ by the SherpaNote team. Happy learning!