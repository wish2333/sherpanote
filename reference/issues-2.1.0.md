我希望升级OCR功能，添加https://github.com/microsoft/markitdown和https://github.com/opendataloader-project/opendatalo
ader-pdf这两个项目，组成具有默认决策树+可选处理方式的一个更完善的系统

1. 图片文件仍然使用PPocr
2. PDF文件首先用pdftotext --first是否超过10 chars来判断是否有文本层

  - 有文本层，默认用opendataloader-pdf，可选markitdown和PPocr
  - 无文本层，只能使用PPocr

3. 支持微软文档：markitdown
   有这样几个问题需要思考：
4. 这些项目都是以一个很小的启动包作为uv add之后安装的包吧，初始化时才下载模型？
5. 如果是这样，我们当前的OCR模型管理是否可部分复用
6. 如果是后下载模型，还希望加入docling：https://pypi.org/project/docling/作为有文本层PDF的一个可选方案

# v2.1.0 - OCR System Upgrade

> Upgrade OCR to a multi-backend document extraction system with decision tree.

## Goal

Replace the single PP-OCR-only approach with a smart multi-backend system:
- Images: PP-OCR (unchanged)
- PDFs: Decision tree based on text layer detection
- Office docs: New capability via markitdown

## Research Results

### markitdown (Microsoft)

| Item | Detail |
|------|--------|
| PyPI | `markitdown` |
| Install | `uv add 'markitdown[all]'` |
| Size | ~63MB with all deps |
| Model download | **None** - pure rule-based extraction |
| Dependencies | beautifulsoup4, pdfminer-six, pdfplumber, mammoth, python-pptx, openpyxl, pandas |
| Supported formats | PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, XML, ZIP, EPUB |
| PDF handling | pdfminer-six + pdfplumber (pure Python, basic quality) |
| Office handling | Native DOCX (mammoth), PPTX (python-pptx), XLSX (openpyxl) |
| API | `MarkItDown().convert("file.pdf")` -> `result.markdown` |

### opendataloader-pdf

| Item | Detail |
|------|--------|
| PyPI | `opendataloader-pdf` |
| Install | `uv add opendataloader-pdf` |
| Size | ~22.5MB wheel |
| Model download | **None** - Java-based rule extraction |
| Dependencies | **Java 11+ runtime required** (bundles JAR, calls via subprocess) |
| Supported formats | PDF only |
| PDF quality | Benchmark #1 overall (0.907), excellent table extraction (0.928) |
| How it works | XY-Cut++ reading order, bounding boxes, AI safety filters |
| API | `opendataloader_pdf.convert(input_path=[...], output_dir="...", format="markdown,json")` |

### docling

| Item | Detail |
|------|--------|
| PyPI | `docling` |
| Install | `uv add docling` |
| Size | Medium package |
| Model download | **YES** - ~1-2GB on first use to `$HOME/.cache/docling/models/` |
| Dependencies | Deep learning models (layout, tableformer, picture classifier) |
| Supported formats | PDF, DOCX, PPTX, HTML, images |
| GPU | CUDA support available |
| OCR backends | EasyOCR, Tesseract, **RapidOCR** (native!), macOS Vision |
| Model prefetch | `docling-tools models download` or `download_models()` |
| Offline | Supported via `artifacts_path` parameter |
| API | `DocumentConverter().convert("file.pdf")` -> `result.document.export_to_markdown()` |

---

## Decision Tree

```
[Input File]
    |
    +-- Image (PNG/JPG/BMP/TIFF/WebP) --> PP-OCR (RapidOCR) [unchanged]
    |
    +-- PDF
    |     |
    |     +-- Detect text layer: pdftotext or PyMuPDF, check > 10 chars
    |           |
    |           +-- NO text layer (scanned/image PDF)
    |           |     --> PP-OCR only (PDF -> images -> OCR)
    |           |
    |           +-- HAS text layer
    |                 |
    |                 +-- Default: markitdown (lightweight, pure Python)
    |                 +-- Optional: opendataloader-pdf (best quality, needs Java 11+)
    |                 +-- Optional: docling (advanced layout/tables, downloads ~1-2GB models)
    |                 +-- Fallback: PP-OCR (always available)
    |
    +-- Office (DOCX/PPTX/XLSX)
          --> markitdown (native support)
```

---

## Decisions

### D1: Default PDF text-layer method = markitdown

**Chosen**: markitdown
**Rationale**:
- Zero ML model downloads (pure Python)
- No external runtime dependency (no Java required)
- Good enough quality for most text-layer PDFs
- Small install footprint (~63MB with all deps)
- Also handles DOCX/PPTX/XLSX natively

**Rejected alternatives**:
- opendataloader-pdf: Java 11+ hard dependency problematic for PyInstaller packaging. Would need to bundle JRE (~150MB) or require user to install Java.
- docling: Too heavy for default (~1-2GB model download). Better as optional advanced mode.

### D2: opendataloader-pdf = Optional, with Java check

**Decision**: Include as optional method, but:
- Auto-detect Java availability at runtime
- If Java not found, hide this option from PDF method selector
- Show clear message: "Install Java 11+ to use this method"
- Not bundled in PyInstaller package (user must have Java)

**Rationale**: Best PDF extraction quality, but Java dependency makes it unsuitable as default for a packaged desktop app. Worth offering as power-user option.

### D3: docling = Optional advanced mode

**Decision**: Include as optional method for text-layer PDFs:
- First use triggers model download (~1-2GB)
- Show download size warning before first activation
- Support offline use via `artifacts_path` pointing to bundled models
- Can leverage existing RapidOCR as OCR backend (synergy)
- GPU acceleration available for users with CUDA

**Rationale**: Provides layout analysis and table recognition that markitdown cannot. Heavy but powerful. The RapidOCR backend support means we can reuse existing PP-OCR models for the OCR portion.

### D4: Text layer detection method

**Decision**: Use PyMuPDF (fitz) instead of pdftotext CLI tool.

**Rationale**:
- PyMuPDF is already a dependency (used for PDF-to-image in current OCR)
- Pure Python, no external binary needed
- `fitz.open(pdf).page_text(page_num)` returns text, check length > 10
- Cross-platform without installing poppler-utils
- More reliable than calling external CLI

### D5: Model management reuse

**Decision**:
- markitdown / opendataloader-pdf: No model management needed (rule-based)
- docling: Use docling's built-in model management. Do NOT integrate into our existing RapidOCR model manager. Docling manages its own models via `docling-tools models download` and `artifacts_path`.
- PP-OCR models: Keep existing `py/ocr.py` model management unchanged

### D6: Office document support

**Decision**: Use markitdown for DOCX/PPTX/XLSX.

**Rationale**: markitdown natively supports these formats with lightweight dependencies. No need for a separate extraction path. Office files bypass the PDF decision tree entirely.

---

## Implementation Scope

### Phase 1: Core Refactor
- Refactor `py/ocr.py` -> `py/document_extractor.py` (new name, broader scope)
- Add text layer detection via PyMuPDF
- Implement decision tree logic
- Keep existing PP-OCR (RapidOCR) path unchanged for images and scanned PDFs
- Add markitdown integration for text-layer PDFs and Office docs
- Update `OcrConfig` to include PDF method selection

### Phase 2: Optional Backends
- Add opendataloader-pdf integration (with Java detection)
- Add docling integration (with model download warning)
- Update Settings UI with PDF method selector
- Update OcrView with format-aware UI

### Out of Scope
- Audio/OCR via LLM (markitdown plugin, requires external AI)
- Azure Document Intelligence (cloud service)
- Bundling JRE for opendataloader-pdf

---

## New Dependencies (planned)

```toml
# pyproject.toml additions
markitdown = { version = ">=0.1.0", extras = ["all"] }
# opendataloader-pdf = ">=0.1.0"  # optional, needs Java 11+
# docling = ">=2.0.0"              # optional, heavy model download
```

**Removed dependency opportunity**: If opendataloader-pdf and docling are added, PyMuPDF remains for PDF-to-image (scanned PDFs). If we later remove PP-OCR dependency for text-layer PDFs, pdfplumber (markitdown dep) could replace some PyMuPDF usage.

---

## Optional Backend Runtime Installation

opendataloader-pdf and docling are NOT bundled in PyInstaller. They are installed on-demand via a bundled uv standalone binary into a sidecar plugin venv.

### Directory Layout

```
app_dir/
  sherpanote.exe              # PyInstaller main app (no optional packages)
  _internal/                  # PyInstaller frozen env (markitdown + PP-OCR)
  data/
    plugins/
      .venv/                  # Created on-demand at runtime
        bin/python            # Python matching app's version
        lib/site-packages/
          docling/            # Installed on demand
          opendataloader-pdf/ # Installed on demand
    audio/
  uv.exe                      # Bundled uv standalone binary (~20MB)
```

### uv Binary Path Resolution

```python
def get_uv_path() -> Path:
    """Return path to the bundled uv binary."""
    if getattr(sys, "frozen", False):
        # PyInstaller onedir: uv.exe next to the executable
        return Path(sys.executable).parent / "uv.exe"
    # Development: use system uv
    return Path(shutil.which("uv") or "uv")
```

### Plugin Venv Management

All subprocess calls MUST use `get_uv_path()`, never bare `uv`:

```python
def _uv(*args: str) -> subprocess.CompletedProcess:
    """Run a uv command using the bundled uv binary."""
    uv_bin = str(get_uv_path())
    return subprocess.run(
        [uv_bin, *args],
        capture_output=True, text=True, check=True,
    )

def _ensure_plugin_venv() -> Path:
    """Create plugin venv if not exists, matching app's Python version."""
    venv_dir = Path(get_app_data_dir()) / "plugins" / ".venv"
    if not venv_dir.exists():
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        _uv("venv", "--python", py_ver, str(venv_dir))
    return venv_dir

def _install_plugin(package: str, pip_args: list[str] | None = None) -> Path:
    """Install a plugin package into the plugin venv. Returns site-packages path."""
    venv_dir = _ensure_plugin_venv()
    python_bin = venv_dir / "bin" / "python"
    args = ["pip", "install", "--python", str(python_bin), package]
    if pip_args:
        args.extend(pip_args)
    _uv(*args)
    # Return site-packages for sys.path injection
    return venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

def _is_plugin_installed(package: str) -> bool:
    """Check if a plugin is already installed in the plugin venv."""
    venv_dir = Path(get_app_data_dir()) / "plugins" / ".venv"
    if not venv_dir.exists():
        return False
    result = subprocess.run(
        [str(get_uv_path()), "pip", "list", "--python", str(venv_dir / "bin" / "python")],
        capture_output=True, text=True,
    )
    return package.lower() in result.stdout.lower()

def _uninstall_plugin(package: str) -> None:
    """Remove a plugin from the plugin venv."""
    venv_dir = Path(get_app_data_dir()) / "plugins" / ".venv"
    if not venv_dir.exists():
        return
    python_bin = venv_dir / "bin" / "python"
    _uv("pip", "uninstall", "--python", str(python_bin), "-y", package)

def _inject_plugin_site_packages() -> None:
    """Add plugin venv site-packages to sys.path (call before importing plugin)."""
    venv_dir = Path(get_app_data_dir()) / "plugins" / ".venv"
    if not venv_dir.exists():
        return
    site_packages = venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if site_packages.exists() and str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))
```

### Runtime Flow (per backend)

```
[User selects optional backend in Settings]
    |
    v
1. _is_plugin_installed("docling")
    |        |
    |   NO   v
    |   Show dialog: "docling needs ~1-2GB download. Continue?"
    |        |
    |    YES  v
    |   site_packages = _install_plugin("docling")
    |   (runs: {bundled_uv} pip install --python .../bin/python docling)
    |        |
    v
2. _inject_plugin_site_packages()
3. import docling  # works normally
4. docling downloads its own models to ~/.cache/docling/models/ on first use
```

### Prerequisite Checks

| Backend | Check | Method |
|---------|-------|--------|
| opendataloader-pdf | Java 11+ available | `subprocess.run(["java", "-version"], ...)` |
| docling | Disk space for models | `shutil.disk_usage()` |
| Both | Internet connectivity | Attempt HEAD request to PyPI |

### Build Integration

```python
# build.py additions
def download_uv_standalone():
    """Download uv standalone binary for bundling."""
    import urllib.request
    import platform
    suffix = ".exe" if platform.system() == "Windows" else ""
    url = f"https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc{suffix}"
    dest = dist_dir / f"uv{suffix}"
    urllib.request.urlretrieve(url, dest)
    # Also download uv.exe for Windows ARM if needed
```

### Cleanup

```python
def uninstall_all_plugins():
    """Remove entire plugin venv directory."""
    plugins_dir = Path(get_app_data_dir()) / "plugins"
    if plugins_dir.exists():
        shutil.rmtree(plugins_dir)
```

### Package Size Summary

| Component | Bundled | Runtime Download |
|-----------|---------|-----------------|
| PP-OCR (RapidOCR) | ~200MB | - |
| markitdown | ~63MB | - |
| uv standalone binary | ~20MB | - |
| opendataloader-pdf | - | ~22.5MB + requires Java 11+ |
| docling | - | ~500MB (pip) + ~1-2GB (models) |

Base package: ~283MB. Optional backends downloaded on demand.

# Phase1

- docs\PRD-2.1.0.md
-   Phase 1 共 10 个任务，按依赖顺序：
    1. 更新依赖 (PyMuPDF -> pypdfium2 + markitdown)
    2. 创建统一输出数据模型 ExtractedDocument
    3. 创建文本层检测器 text_detector.py
    4. 替换 ocr.py 中的 PyMuPDF
        5-6. 创建 PP-OCR 和 markitdown 适配器
    5. 创建决策树入口 document_extractor.py
    6. 重构 main.py OCR 处理流程
    7. 前端支持 Office 文件类型
    8. 更新构建配置
- sherpanote\reference\cc-plan\2.1.0-phase1-effervescent-doodling-otter.md

```
[sherpanote] recent context, 2026-04-29 9:05pm GMT+8
────────────────────────────────────────────────────────────

Legend: session-request | 🔴 bugfix | 🟣 feature | 🔄 refactor | ✅ change | 🔵 discovery | ⚖️ decision

Column Key
  Read: Tokens to read this observation (cost to learn it now)
  Work: Tokens spent on work that produced this record ( research, building, deciding)

Context Index: This semantic index (titles, types, files, tokens) is usually sufficient to understand past work.

When you need implementation details, rationale, or debugging context:
  - Fetch by ID: get_observations([IDs]) for observations visible in this index
  - Search history: Use the mem-search skill for past decisions, bugs, and deeper research
  - Trust this index over re-reading code for past decisions and learnings

Context Economics
  Loading: 120 observations (37,637 tokens to read)
  Work investment: 0 tokens spent on research, building, and decisions

Apr 29, 2026

docs/design/data_models/records.csv
  #4116  4:00 PM  ✅  Complete SQLite database schema documented with 3 tables  
docs/procedures/workflow_index.md
  #4117  4:01 PM  ✅  Workflow index established with 7 core business processes  
docs/procedures/recording_transcription.md
  #4118  4:04 PM  ✅  Created comprehensive workflow documentation suite  
docs/business_rules.md
  #4119  4:07 PM  ✅  Populated business rules documentation with comprehensive domain rules  
General
  #4120  6:24 PM  🔵  OCR software architecture investigation initiated  
frontend/src/views/OcrView.vue
  #4121           🔵  OCR functionality spans 7 frontend files  
py/ocr.py
  #4122           🔵  OCR backend implemented in Python with RapidOCR  
  #4123           🔵  Complete OCR backend architecture documented  
main.py
  #4124           🔵  OCR orchestration and configuration layer documented  
General
  #4125  7:14 PM  🔵  Researched opendataloader-pdf capabilities and architecture  
  #4126           🔵  Researched Microsoft markitdown package capabilities  
  #4127           🔵  Discovered opendataloader-pdf Python package structure  
  #4128           🔵  Analyzed markitdown package architecture and capabilities  
  #4129           🔵  Examined opendataloader-pdf Python package structure and build system  
  #4130           🔵  Discovered multiple markitdown implementations via Context7  
  #4131  7:15 PM  🔵  Researched markitdown installation patterns and dependency structure  
  #4132           🔵  Learned markitdown Python API usage and plugin system  
  #4133           🔵  Analyzed opendataloader-pdf Python package dependencies and build configuration  
  #4134  7:16 PM  🔵  Confirmed markitdown architecture and model management via agent research  
  #4135           🔵  Examined opendataloader-pdf Python wrapper API implementation  
  #4136           🔵  Analyzed opendataloader-pdf convert() function implementation details  
  #4137  7:22 PM  ⚖️  Designed OCR upgrade architecture with opendataloader-pdf and markitdown integration strategy  
  #4138           🔵  Examined opendataloader-pdf JAR execution mechanism and PyPI package details  
  #4139           🔵  Discovered docling ecosystem packages via Context7  
  #4140  7:23 PM  🔵  Completed comprehensive opendataloader-pdf research via Explore agent  
  #4141           🔵  Examined recent git commit history for OCR system context  
  #4142           🔵  Examined project documentation structure and development framework  
  #4143           🔵  Explored project documentation directory structure  
  #4144           🔵  Discovered existing OCR documentation structure in project  
  #4145  7:24 PM  🔵  Reviewed workflow index showing OCR Processing workflow WF-006  
  #4146           🔵  Discovered .claude/rules directory with development governance rules  
  #4147  7:25 PM  🔵  Located OCR implementation files in project structure  
  #4148           🔵  Located OCR UI component in frontend structure  
  #4149           🔵  Analyzed current OCR implementation architecture via code search  
  #4150           🔵  Analyzed current OCR configuration and engine implementation  
  #4151  7:26 PM  🔵  Examined project dependencies and configuration in pyproject.toml  
  #4152           🔵  Completed comprehensive OCR business flow and implementation analysis via Explore agent  
  #4153           🔵  Researched docling library ecosystem via Context7  
  #4154           🔵  Researched docling installation, model management, and GPU support via Context7  
  #4155  7:27 PM  ⚖️  Analyzed library trade-offs and designed decision tree for OCR upgrade  
..\..\Git\GiteaManager\sherpanote\reference\issues-2.1.0.md
  #4156  7:28 PM  ✅  Documented OCR upgrade architecture decisions in reference/issues-2.1.0.md  
General
  #4157  7:48 PM  🔵  Explored optional packaging for opendataloader-pdf/docling dependency  
  #4158  7:49 PM  ⚖️  Chose sidecar venv approach for optional dependencies in PyInstaller app  
docs/dev_guide.md
  #4159  8:08 PM  🔵  Version 2.1.0 development preparation initiated  
py/ocr.py
  #4160  8:09 PM  🔵  OCR module architecture identified  
General
  #4161           🔵  Frontend architecture mapped for sherpanote project  
docs/PRD-2.1.0.md
  #4162           🔵  Project documentation structure catalogued  
pyproject.toml
  #4163  8:10 PM  🔵  Project dependencies and version identified  
docs/procedures/ocr_processing.md
  #4164           🔵  OCR processing procedure documented  
docs/design/system_design.md
  #4165           🔵  Historical OCR architecture context loaded for 2.1.0 development  
docs/changelog.md
  #4166           🔵  Project evolution history mapped from v1.0.0 to v2.0.1  
reference/issues-2.1.0.md
  #4167           🔵  Version 2.1.0 OCR enhancement requirements identified  
General
  #4168           🔵  Backend Python architecture catalogued  
  #4169           🔵  Recent commit history shows OCR feature completion and refinement  
  #4170           🔵  Development workflow uses version-specific branches  
docs/PRD-2.1.0.md
  #4171  8:11 PM  🔵  Version 2.1.0 PRD confirmed as OCR system upgrade  
General
  #4172           🔵  Backend module complexity quantified by file size  
main.py
  #4173           🔵  Historical OCR orchestration architecture loaded for 2.1.0 context  
frontend/src/views/OcrView.vue
  #4174           🔵  Current OCR frontend architecture loaded with removal requirements identified  
reference/Changelog.md
  #4175           🔵  Complete version evolution catalogued from v1.0.0 to v2.0.1  
frontend/src/views/SettingsView.vue
  #4176           🔵  Current OCR settings UI implementation revealed in SettingsView.vue  
build.py
  #4177  8:12 PM  🔵  OCR model bundling implemented in build system  
app.spec
  #4178           🔵  OCR packaging configuration and API exports catalogued  
main.py
  #4179           🔵  OCR process API implementation located in main.py  
  #4180           🔵  Complete OCR architecture documented with API, types, and database schema  
frontend/src/stores/appStore.ts
  #4181           🔵  dev-2.1.0 branch contains 4 commits ahead of main  
  #4182  8:13 PM  🔵  Git history reveals merge pattern across version branches  
  #4183           🔵  Complete OCR state initialization and recent commit history documented  
frontend/src/views/OcrView.vue
  #4184           🔵  OcrView.vue implementation architecture revealed  
py/ocr.py
  #4185  8:14 PM  🔵  Comprehensive OCR architecture exploration completed by Explore agent  
pyproject.toml
  #4186           🔵  Comprehensive project structure and documentation analysis completed  
frontend/src/views/OcrView.vue
  #4187           🔵  Comprehensive frontend OCR architecture documented by Explore agent  
main.py
  #4188  8:15 PM  🔵  Complete OCR architecture cross-referenced across codebase  
py/ocr.py
  #4189           🔵  OCR model management structure revealed in py/ocr.py  
  #4190  8:16 PM  🔵  Complete OCR backend implementation revealed through file analysis  
build.py
  #4191           🔵  Build system OCR model bundling implementation documented  
py/ocr.py
  #4192  8:17 PM  🔵  Complete py/ocr.py implementation documented  
py/config.py
  #4193  8:18 PM  🔵  Complete configuration management system documented  
docs/dev_guide.md
  #4194  8:33 PM  ⚖️  SherpaNote v2.1.0 Phase 1 Implementation Plan Approved  
General
  #4195  8:34 PM  🟣  SherpaNote v2.1.0 Development Tasks Initiated  
  #4196           🟣  SherpaNote v2.1.0 Implementation Task Suite Created  
pyproject.toml
  #4197           🟣  Dependencies Updated for OCR System Upgrade  
uv.lock
  #4198  8:36 PM  🟣  Dependency Lock File Updated Successfully  
General
  #4199  8:38 PM  🟣  Dependencies Synchronized Successfully  
  #4200           🟣  Dependency Import Verification Successful  
  #4201           🟣  Task 1 Completed: Dependency Updates  
  #4202  8:39 PM  🟣  Parallel Development Tasks Initiated  
  #4203           🔵  Current py/ Directory Structure Confirmed  
  #4204           🟣  Package Directories Created for Modular Architecture  
py/outputs/__init__.py
  #4205  8:40 PM  🟣  py/outputs Package Initialized  
py/adapters/__init__.py
  #4206           🟣  py/adapters Package Initialized  
py/outputs/unified_document.py
  #4207           🟣  Unified Document Output Model Implemented  
py/text_detector.py
  #4208           🟣  File Type Detection and PDF Text Layer Detection Implemented  
py/adapters/ppocr_adapter.py
  #4209           🟣  Backend Adapters Implemented  
py/ocr.py
  #4210  8:42 PM  🔵  Existing PyMuPDF PDF-to-Image Implementation Reviewed  
  #4211           🟣  PyMuPDF Replaced with pypdfium2 in PDF-to-Image Conversion  
  #4212           🟣  File Picker Extended with Office File Types  
  #4213           🟣  PyMuPDF Completely Removed from Codebase  
General
  #4214           🟣  Decision Tree Orchestrator Development Started  
py/document_extractor.py
  #4215  8:43 PM  🟣  Document Extraction Decision Tree Orchestrator Implemented  
General
  #4216           🟣  Core Module Development Complete, Integration Phase Started  
main.py
  #4217  8:44 PM  🔵  main.py OCR Engine Initialization Pattern Reviewed  
  #4218           🔵  Current OCR Engine Lazy Initialization Pattern Reviewed  
  #4219           🟣  DocumentExtractor Instance Variable Added to main.py  
  #4220           🟣  DocumentExtractor Lazy Initialization Method Added  
  #4221           🔵  Current ocr_process Implementation Reviewed  
  #4222  8:45 PM  🟣  OCR Pipeline Refactored to Use DocumentExtractor  
  #4223           🔵  _annotate_record Function Location Identified  
  #4224  8:46 PM  🔵  Build Segments Helper Function Location Identified  
  #4225  8:57 PM  🔴  OCR processing fails with undefined function error  
  #4226           🔵  _build_segments function exists but out of scope at call site  
  #4227           🔵  Error occurs in OCR document processing workflow  
  #4228           🔴  Fixed _build_segments scope issue in OCR processing  
  #4229           🔵  Second _build_segments scope issue found in batch mode  
  #4230  8:58 PM  🔴  Fixed second _build_segments scope issue in batch mode OCR  
py/text_detector.py
  #4231           🔵  PDF text layer detection uses pdfplumber for smart routing  
  #4232           🔴  Suppressed verbose pdfminer debug logging during PDF text detection  
py/adapters/markitdown_adapter.py
  #4233           🔵  MarkitdownAdapter wraps markitdown library for text-based document conversion  
  #4234           🔴  Suppressed pdfminer debug logging in markitdown adapter  
main.py
  #4235           🔵  Verified _build_segments static method accessibility after fix
```

### 📝 Commit Message

```
feat(ocr): 重构文档提取架构并支持Office文件

- 替换 PyMuPDF 为 pypdfium2，引入 markitdown 处理文本类文档
- 新增 ExtractedDocument 统一输出数据模型
- 实现文本层检测器，支持按 PDF 特征智能路由提取策略
- 创建 PP-OCR 与 markitdown 适配器，解耦具体实现
- 新增 DocumentExtractor 决策树入口，统筹文档提取流程
- 重构 main.py OCR 管线对接新架构
- 前端文件选择器扩展 Office 文件类型
- 修复批量模式下 _build_segments 作用域错误
- 抑制 pdfminer 冗余调试日志
```

### 🚀 Release Notes

```
## 2.1.0 - 文档提取系统全面升级

### ✨ 新增
- 支持 Office 文件直接导入：Word、Excel、PowerPoint 等格式无需预先转 PDF 即可处理
- 智能提取策略：系统自动识别文档类型及 PDF 文本层特征，选择最优提取路径

### 🐛 修复
- 修复批量 OCR 处理时偶发的提取失败问题

### ⚡ 优化
- PDF 解析引擎更换，提升图片型 PDF 的渲染质量与兼容性
- 文本型 PDF 提取效率提升，不再走不必要的 OCR 流程
- 处理过程日志更简洁，减少无关调试信息干扰
```

# Phase2

```
● Phase 2 实现计划：插件运行时架构 + docling/opendataloader-pdf 适配器

  架构概览

  py/plugins/              # 新增插件子系统
    paths.py               # 路径解析（frozen vs dev）
    manager.py             # venv 生命周期管理
    runner.py              # 子进程 JSON 通信协议
    java_detect.py         # Java 11+ 多策略检测
    runners/               # 子进程入口脚本
      docling_runner.py
      opendata_runner.py
  py/adapters/             # 新增两个适配器
    docling_adapter.py     # 通过子进程调用 docling
    opendata_adapter.py    # 通过子进程调用 opendataloader-pdf

  实施阶段（10个任务）

  ┌──────┬─────────────────┬───────┬────────┬─────────────────────────────────┐
  │ 阶段 │      任务       │ 新/改 │ 复杂性 │              描述               │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ A1   │ 插件路径解析    │ 新建  │ 小     │ frozen/dev 模式路径解析         │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ A2   │ 插件管理器      │ 新建  │ 中     │ venv 创建、安装、检测、卸载     │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ A3   │ 子进程运行器    │ 新建  │ 中     │ JSON stdin/stdout 通信协议      │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ B1   │ docling runner  │ 新建  │ 中     │ docling 子进程入口脚本          │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ B2   │ opendata runner │ 新建  │ 小     │ opendataloader-pdf 子进程入口   │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ C1   │ docling 适配器  │ 新建  │ 小     │ 通过 runner 调用 docling        │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ C2   │ opendata 适配器 │ 新建  │ 小     │ 通过 runner 调用 opendataloader │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ D1   │ Java 检测       │ 新建  │ 中     │ 多策略 Java 11+ 检测            │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ E1   │ 配置扩展        │ 修改  │ 小     │ PluginConfig + DocumentConfig   │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ F1   │ 决策树集成      │ 修改  │ 中     │ DocumentExtractor 支持可选后端  │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ F2   │ main.py 集成    │ 修改  │ 中     │ 暴露插件管理 API                │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ G1   │ 构建脚本        │ 修改  │ 中大   │ 下载捆绑 Python + uv            │
  ├──────┼─────────────────┼───────┼────────┼─────────────────────────────────┤
  │ G2   │ app.spec        │ 修改  │ 小     │ PyInstaller 包含捆绑资源        │
  └──────┴─────────────────┴───────┴────────┴─────────────────────────────────┘

  关键路径

  A1 -> A2 + A3 -> B1 + B2 -> C1 + C2 -> F1 -> F2
                  D1 ──────────────────> C2
                  E1 ──────────────────> F1

  主要风险

  - 高: 子进程 stdout/stderr 缓冲区死锁（用 communicate() 缓解）
  - 中: 捆绑 Python 版本与主应用不匹配（固定同版本）
  - 中: docling API 不稳定（固定版本范围）

  预计新增代码: ~1300-1500 行 | 新文件: 10 | 修改文件: 6
```

### Phase 2 Complete

```
  New Files (10)

  ┌───────────────────────────────────────┬─────────────────────────────────────────────────────────────────┐
  │                 File                  │                             Purpose                             │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/__init__.py                │ Package marker                                                  │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/paths.py                   │ Frozen/dev path resolution for Python, uv, venv                 │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/manager.py                 │ PluginManager: venv lifecycle, install/uninstall packages       │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/runner.py                  │ SubprocessRunner: JSON stdin/stdout protocol, timeout, progress │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/java_detect.py             │ Multi-strategy Java 11+ detection                               │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/runners/__init__.py        │ Package marker                                                  │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/runners/docling_runner.py  │ docling CLI wrapper (text_layer + OCR mode)                     │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/plugins/runners/opendata_runner.py │ opendataloader-pdf CLI wrapper                                  │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/adapters/docling_adapter.py        │ DoclingAdapter via subprocess                                   │
  ├───────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ py/adapters/opendata_adapter.py       │ OpendataAdapter via subprocess                                  │
  └───────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘

  Modified Files (6)

  ┌─────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────┐
  │            File             │                                      Changes                                       │
  ├─────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ py/config.py                │ Added PluginConfig, DocumentConfig dataclasses, updated to_dict/from_dict          │
  ├─────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ py/document_extractor.py    │ Added plugin backend routing (docling, opendataloader) with fallback chain         │
  ├─────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ main.py                     │ Added _plugin_manager, _get_plugin_manager(), updated _get_document_extractor(), 6 │
  │                             │  new @expose API methods                                                           │
  ├─────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ frontend/src/types/index.ts │ Added PluginConfig, DocumentConfig, PluginPackageStatus, JavaDetectionResult types │
  ├─────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ app.spec                    │ Added plugin hidden imports + bundled Python/uv binary collection                  │
  ├─────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ build.py                    │ Added --with-plugins flag + _download_plugin_runtime() for Python+uv bundling      │
  └─────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────┘

  New API Methods (main.py)

  - get_plugin_status() - installation status of all plugin backends
  - install_plugin(package_name) - background install with progress events
  - uninstall_plugin(package_name) - remove from plugin venv
  - detect_java() - Java 11+ runtime detection
  - get_available_backends() - availability of all extraction backends
  
● 开发环境完全支持插件系统。新增的 dev.py plugin 子命令：

  ┌─────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────┐
  │                命令                 │                                   功能                                    │
  ├─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ uv run dev.py plugin status         │ 查看插件系统状态：运行模式、Python/uv 路径、venv 状态、已安装后端、Java   │
  │                                     │ 检测、决策树配置                                                          │
  ├─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ uv run dev.py plugin install        │ 安装 docling 到插件 venv                                                  │
  │ docling                             │                                                                           │
  ├─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ uv run dev.py plugin install        │ 安装 opendataloader-pdf                                                   │
  │ opendataloader                      │                                                                           │
  ├─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ uv run dev.py plugin uninstall      │ 卸载插件                                                                  │
  │ docling                             │                                                                           │
  ├─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ uv run dev.py plugin destroy        │ 销毁整个插件 venv                                                         │
  ├─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ uv run dev.py plugin detect-java    │ 检测 Java 11+                                                             │
  ├─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ uv run dev.py plugin test FILE      │ 用当前配置测试文件提取                                                    │
  └─────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────┘

  开发模式下插件系统使用系统 Python 和 uv 创建独立的 .plugin_dev/.venv，不会污染项目 .venv。切换后端只需
  install/uninstall 对应插件，决策树会根据 DocumentConfig 中配置的引擎自动路由，不可用时自动回退到默认引擎。
```

### CC-Mem

```
Legend: session-request | 🔴 bugfix | 🟣 feature | 🔄 refactor | ✅ change | 🔵 discovery | ⚖️ decision
Apr 30, 2026

CLAUDE.md
  #4243  12:50 AM  ✅  Updated project documentation with PDF processing dependencies  
..\..\Git\GiteaManager\sherpanote\README.md
  #4244            ✅  README.md updated with multi-backend OCR feature documentation  
  #4245            ✅  Technology Stack section updated with new OCR backend dependencies  
  #4246  12:51 AM  ✅  Project Structure section updated with new OCR backend architecture files  
  #4247            ✅  Acknowledgments section updated with markitdown attribution  
..\..\Git\GiteaManager\sherpanote\README_zh.md
  #4248            ✅  Chinese README (README_zh.md) updated with multi-backend OCR feature documentation  
  #4249            ✅  Chinese README Technology Stack section updated with new OCR backend dependencies  
General
  #4250  12:56 AM  🔵  Phase 1 document extraction system completed, Phase 2 planning initiated  
  #4251            🔵  OCR integration partially implemented in main.py with API endpoints  
  #4252            🔵  Phase 1 OCR integration complete with full UI and configuration system  
  #4253            🔵  OcrConfig fully implemented with frozen dataclass pattern  
  #4254  1:03 AM  ⚖️  Plugin path resolver architecture for SherpaNote  
  #4255           ⚖️  Subprocess communication protocol for plugins  
  #4256           ⚖️  Plugin manager architecture for SherpaNote  
  #4257           ⚖️  Java runtime detection strategy for plugins  
  #4258           ⚖️  Configuration schema extension for plugin system  
  #4259           ⚖️  Plugin runner scripts for document processing backends  
  #4260           ⚖️  Backend adapter architecture for document processing  
  #4261           ⚖️  Decision tree routing and main API integration  
py/adapters/__init__.py
  #4262  1:04 AM  ⚖️  Build system enhancement for bundled Python runtime  
py/document_extractor.py
  #4263           🔵  MCP smart_outline tool doesn't support Python files  
  #4264           🔵  DocumentExtractor decision tree architecture  
py/outputs/unified_document.py
  #4265           🔵  Unified document output model architecture  
py/adapters/markitdown_adapter.py
  #4266           🔵  Adapter pattern for document processing backends  
py/config.py
  #4267           🔵  Configuration system architecture with SQLite persistence  
main.py
  #4268           🔵  Main API integration points for document extraction  
frontend/src/types/index.ts
  #4269           🔵  TypeScript type definitions mirror Python config dataclasses  
py/plugins/__init__.py
  #4270           🟣  Plugin path resolver with frozen/dev mode support  
py/plugins/runner.py
  #4271           🟣  Subprocess runner with JSON protocol and progress streaming  
py/plugins/manager.py
  #4272  1:05 AM  🟣  Plugin manager with virtual environment lifecycle management  
  #4273           🟣  Plugin manager with venv lifecycle and package operations  
py/plugins/java_detect.py
  #4274           🟣  Java runtime detection with multi-strategy fallback  
  #4275           🟣  Java runtime detection with multi-strategy fallback  
py/config.py
  #4276           🟣  Configuration extension with PluginConfig and DocumentConfig  
  #4277           🟣  AppConfig integration of plugin and document configurations  
  #4278  1:06 AM  🟣  Config serialization updates for plugin and document configs  
  #4279           🟣  Configuration system extension completed with full serialization support  
frontend/src/types/index.ts
  #4280           🟣  TypeScript type definitions for plugin system added to frontend  
py/plugins/runners/__init__.py
  #4281           🟣  Docling runner wrapper script for subprocess execution  
py/plugins/runners/opendata_runner.py
  #4282           🟣  Opendata runner wrapper script for subprocess execution  
py/adapters/docling_adapter.py
  #4283           🟣  Docling adapter for subprocess-based document extraction  
py/adapters/opendata_adapter.py
  #4284  1:07 AM  🟣  Opendata adapter for Java-based document extraction  
py/document_extractor.py
  #4285           🟣  DocumentExtractor integration with plugin backends  
main.py
  #4286  1:08 AM  🟣  Plugin manager integration into main API  
General
  #4287  1:12 AM  🔵  Located dev.py file for plugin support implementation  
  #4288           🔵  Read existing dev.py structure for plugin implementation  
  #4289  1:13 AM  🟣  Implemented plugin management CLI in dev.py  
  #4290           🔵  Plugin status command verified operational  
  #4291  1:15 AM  🔵  Frontend lacks plugin configuration interface  
frontend/src/views/SettingsView.vue
  #4292           🔵  Frontend lacks plugin configuration interface in SettingsView  
  #4293           🔵  SettingsView tab structure lacks plugins configuration section
```

### 📝 Commit Message

```
feat(plugins): 实现插件运行时架构与后端适配器

- 新增插件子系统：路径解析、venv 生命周期、子进程 JSON 通信
- 新增 docling 与 opendataloader-pdf 适配器，通过隔离 venv 调用
- 实现多策略 Java 11+ 运行时检测
- DocumentExtractor 支持可选后端路由与自动回退链
- 暴露 5 个插件管理 API 及 dev.py plugin CLI
- 构建脚本支持 --with-plugins 捆绑独立 Python 运行时
```

### 🚀 Release Notes

```
## 2026-04-30 - 插件化文档提取引擎

### ✨ 新增
- 引入插件系统，支持按需安装扩展文档提取后端
- 新增 docling 后端：支持文本层提取与 OCR 模式
- 新增 opendataloader-pdf 后端：基于 Java 的 PDF 解析
- 后端决策树路由：根据配置自动选择引擎，不可用时自动回退
- 新增插件管理 API：查询状态、安装/卸载后端、检测 Java 环境
- 新增开发工具链：`dev.py plugin` 子命令集，支持本地调试与测试

### ⚡ 优化
- 插件运行在独立虚拟环境中，不污染项目主依赖
- 构建时可捆绑独立 Python 运行时，支持无系统 Python 环境部署
```

# Phase3

```
 Phase 3: Settings UI, Plugin Management, Document Engine Selection

 Context

 SherpaNote v2.1.0 Phase 1 (core refactor + markitdown) and Phase 2 (plugin runtime + adapters) are complete. The
 backend is fully ready -- all bridge methods are exposed, config persistence works for PluginConfig and
 DocumentConfig. Phase 3 builds the entirely frontend user interface for plugin management and document engine
 selection, per PRD sections 6.1-6.3.

 Key Architecture Decisions

 1. Rename "OCR" tab to "OCR / Documents" -- add document/plugin sections within the existing tab rather than creating
 an 8th tab (PRD 6.1 says "In the OCR / Document Extraction settings panel")
 2. Extract DocumentSettingsPanel.vue sub-component -- SettingsView is already 2574 lines; new sections add ~450 lines
 that should be isolated
 3. Create usePlugin composable -- encapsulates install/uninstall event lifecycle (progress streaming, completion,
 error) away from UI
 4. Add pluginConfig + documentConfig to Pinia store -- follows existing pattern for aiConfig/asrConfig/ocrConfig

 Implementation Steps

 Step 1: Bridge Helpers (~25 lines)

 File: frontend/src/bridge.ts

 Add 5 typed helper functions following existing patterns:
 - getPluginStatus() -> calls get_plugin_status
 - installPlugin(packageName) -> calls install_plugin
 - uninstallPlugin(packageName) -> calls uninstall_plugin
 - detectJava() -> calls detect_java
 - getAvailableBackends() -> calls get_available_backends

 Step 2: Store Extension (~15 lines)

 File: frontend/src/stores/appStore.ts

 - Import PluginConfig, DocumentConfig from types
 - Add pluginConfig ref (default: { manual_java_path: null, docling_artifacts_path: null })
 - Add documentConfig ref (default: { text_pdf_engine: "markitdown", scan_pdf_engine: "ppocr" })
 - Export both in return object

 Step 3: usePlugin Composable (~150 lines, NEW)

 File: frontend/src/composables/usePlugin.ts

 Reactive state:
 - pluginStatuses, availableBackends, javaResult
 - installingPackage, installProgress, uninstallingPackage, isDetectingJava

 Functions:
 - loadStatuses() -- calls getPluginStatus() + getAvailableBackends()
 - installPackage(name) -- fire-and-forget call, backend emits events
 - uninstallPackage(name) -- calls uninstallPlugin(), refreshes statuses
 - runDetectJava() -- calls detectJava()
 - cleanup() -- removes all event listeners

 Event listeners (register on init, cleanup on unmount):
 - plugin_install_progress -> updates installProgress
 - plugin_install_complete -> clears installing, refreshes statuses, toast success
 - plugin_install_error -> clears installing, toast error with offline guidance

 Step 4: Config Integration (~35 lines)

 File: frontend/src/views/SettingsView.vue

 - Import PluginConfig/DocumentConfig types + store refs
 - Add local refs: pluginConfig = ref(store.pluginConfig), documentConfig = ref(store.documentConfig)
 - In loadConfig(): read res.data.plugin and res.data.document from backend
 - In saveConfig(): include plugin and document in the update_config payload
 - Import DocumentSettingsPanel component

 Step 5: DocumentSettingsPanel Component (~450 lines, NEW)

 File: frontend/src/components/settings/DocumentSettingsPanel.vue

 Props: pluginConfig, documentConfig (passed from parent)
 Emits: update:pluginConfig, update:documentConfig, save-requested

 Card 1 -- PDF Processing Mode:
 - Text-layer PDF engine dropdown: markitdown / opendataloader / docling / ppocr
   - Unavailable engines greyed out with "(not installed)" label
   - Each option shows environment requirement note
 - Scan PDF engine dropdown: ppocr / docling (greyed if not installed)
 - Warning alert when selected engine is unavailable

 Card 2 -- Backend Management:
 - Per-backend row (docling, opendataloader):
   - Name + description + version badge (installed/not-installed/installing)
   - Install button (shows confirm dialog with disk/network requirements)
   - Uninstall button (two-step confirm pattern)
   - Progress bar during installation
 - Venv disk size display

 Card 3 -- Environment Settings:
 - Java path: text input + Browse button (pickFile) + Detect button
   - Shows detection result badge or error guidance
 - Docling model directory: text input + Browse button (pickDirectory) + Reset button

 Step 6: SettingsView Integration (~15 lines)

 File: frontend/src/views/SettingsView.vue

 - Rename tab label: "OCR" -> "OCR / Documents"
 - Place <DocumentSettingsPanel> after existing OCR model cards in the tab
 - Pass pluginConfig/documentConfig as props, handle update events

 Step 7: OcrView Enhancements (~40 lines)

 File: frontend/src/views/OcrView.vue

 - Import documentConfig from store, getAvailableBackends from bridge
 - Show processing method hint below file list based on documentConfig
 - Enhance error handling with actionable guidance ("Try switching engine in Settings")

 Step 8: Manual Test Plan (~60 lines, NEW)

 File: tests/test_plans/feature_plugin_settings.md

 Test cases covering: tab display, backend status loading, install/uninstall flows, engine dropdown availability,
 config persistence, Java detection, custom paths, OcrView hints.

 Files Changed

 ┌────────────────────────────────────────────────────────────┬─────────────┬────────────┬────────┐
 │                            File                            │   Action    │ Est. Lines │  Risk  │
 ├────────────────────────────────────────────────────────────┼─────────────┼────────────┼────────┤
 │ frontend/src/bridge.ts                                     │ Add helpers │ +25        │ Low    │
 ├────────────────────────────────────────────────────────────┼─────────────┼────────────┼────────┤
 │ frontend/src/stores/appStore.ts                            │ Add refs    │ +15        │ Low    │
 ├────────────────────────────────────────────────────────────┼─────────────┼────────────┼────────┤
 │ frontend/src/composables/usePlugin.ts                      │ New         │ ~150       │ Medium │
 ├────────────────────────────────────────────────────────────┼─────────────┼────────────┼────────┤
 │ frontend/src/components/settings/DocumentSettingsPanel.vue │ New         │ ~450       │ High   │
 ├────────────────────────────────────────────────────────────┼─────────────┼────────────┼────────┤
 │ frontend/src/views/SettingsView.vue                        │ Modify      │ +50        │ Medium │
 ├────────────────────────────────────────────────────────────┼─────────────┼────────────┼────────┤
 │ frontend/src/views/OcrView.vue                             │ Modify      │ +40        │ Medium │
 ├────────────────────────────────────────────────────────────┼─────────────┼────────────┼────────┤
 │ tests/test_plans/feature_plugin_settings.md                │ New         │ ~60        │ Low    │
 └────────────────────────────────────────────────────────────┴─────────────┴────────────┴────────┘

 Verification

 1. cd frontend && bun run build -- zero errors
 2. uv run python main.py -- app launches, Settings > "OCR / Documents" tab shows 3 new card sections
 3. Backend management shows correct install status
 4. Install docling -> progress shown -> status updates to "Installed"
 5. Engine dropdowns reflect availability correctly
 6. Config persists across app restart
 7. Java detection works, custom paths save
 8. Existing OCR model config/delete/download unaffected
```



## 问题

- 新增界面应该显示中文

- 新增界面中的环境设置应该设置自动检测并显示状态

- PDF引擎切换不生效

- 插件的包安装未正确执行，控制台也没有打印，无法得知出问题在哪里，而且模型安装没有实现可操作和可检测吧。但是用dev.py的参数安装是可以的。卸载也会出错。

- Q:\Git\GiteaManager\sherpanote>uv run dev.py plugin uninstall opendataloader
  Uninstalling opendataloader (pip: opendataloader-pdf)...
  [ERROR] Uninstall failed: error: unexpected argument '-y' found

    tip: to pass '-y' as a value, use '-- -y'

  Usage: uv.exe pip uninstall [OPTIONS] <PACKAGE|--requirements <REQUIREMENTS>>

  For more information, try '--help'.

- 前端设置中没有Destroy venv的实现

- 而且Docling应该也是可以搭配RapidOCR执行的（不过现在这两个没安装在同一个环境会不会没法搭配），这个不知道能不能实现

- 插件虚拟环境中uv的作用在哪里，好像也没见你用uv来管理插件虚拟环境啊，如果没用的话就删掉吧

```
  Bug 修复总结

  1. PDF 引擎切换不生效 (Critical)

  根因: main.py:1592 update_config() 缓存了 _document_extractor 但切换引擎时没有将其置为 None 失效
  修复: 在 update_config() 中增加 self._document_extractor = None 和 self._plugin_manager = None

  2. uv pip uninstall -y 参数错误 (Critical)

  根因: py/plugins/manager.py:246 对 uv pip uninstall 传了 -y 标志，该命令不支持此参数
  修复: 移除 "-y" 参数

  3. 安装/卸载无日志输出

  修复: main.py install_plugin() 和 uninstall_plugin() 增加 logger.info/error 调用，可通过控制台查看执行状态

  4. 前端界面中文化

  DocumentSettingsPanel.vue 所有文字改为中文（引擎选择、后端管理、环境设置、安装对话框、按钮等）

  5. 环境设置自动检测

  onMounted 中自动调用 runDetectJava()，Java 检测结果显示"已检测到 Java xx"或"未检测到 Java 11+"

  6. 新增销毁虚拟环境功能

  - 后端 main.py: 新增 destroy_plugin_venv API
  - 前端 bridge.ts: 新增 destroyPluginVenv()
  - 前端 usePlugin.ts: 新增 doDestroyVenv()
  - 前端 DocumentSettingsPanel.vue: 环境设置卡片新增"销毁插件虚拟环境"按钮（含确认步骤）

  7. Docling + RapidOCR

  docling_runner.py:47 已配置 pipeline_options.ocr_engine = "rapidocr_onnx"。Docling 在插件 venv 中有自己的 RapidOCR
  依赖，无需与主应用共享模型。通过 docling_artifacts_path 可指定预下载模型路径以支持离线使用。

  8. UV 的作用

  UV 已被使用：用于创建 venv(manager.py:85-130)、安装包(uv pip install)、卸载包(uv pip uninstall)、版本查询(uv pip
  show)。不能删除。
```

- 插件引擎运行报错
- 插件安装时要限定成现在的版本以避免后期出错
- JAVA这个控制台打印的信息乱七八糟的，根本不知道究竟现在软件会用哪个路径的java执行，而且我在设置里面java路径好像也并没有用。
- 此外，插件引擎错误了前端没有显示报错就切换成markitdown跳到记录了，用户无法得知没有用原本的引擎。还有，这些设置改动了之后应该自动保存配置，不需要用户手动保存。
- 前端设置中的后端管理的安装虽然打印Plugin install requested: opendataloader-pdf但是网速完全没跑起来，跟后端dev实现的效果完全不同。
- Docling能够正确运行了，但是环境设置中其模型目录默认是什么不知道，也没有提示用户应该填哪个选项，而且现在我们只一套安装方式应该不会出问题（改了前端安装失败之后），应该也不太需要手动指定Docling目录吧，不过保留这个以托底也可以，但是至少应该显示默认文件夹在哪里
- 同理，`java路径`应该改为`java.exe路径`
- Docling 模型默认目录改为 data/docling + 添加模型预下载功能
- 现在插件引擎检测有问题了，明明已经安装但是无法选择（PDF处理模式处仍然显示未安装，其他地方都检测正确）
- PDF处理模式的选项添加到OCR页中，并同步两边的设置
- 04:20:14 [INFO] py.document_extractor: Text layer PDF: Q:\VerySync\CUHK-Learning\SOCI5601 Theory\Final\SOCI 5601 Take-Home Exam.pdf -> opendataloader-pdf
  04:20:14 [DEBUG] py.plugins.java_detect: Java detection: Checking manual path: C:\Program Files\Java\jdk-17.0.1\bin\java.exe
  04:20:14 [INFO] py.adapters.opendata_adapter: opendataloader-pdf extraction (Java: C:\Program Files\Java\jdk-17.0.1\bin\java.exe): Q:\VerySync\CUHK-Learning\SOCI5601 Theory\Final\SOCI 5601 Take-Home Exam.pdf
  04:20:14 [DEBUG] py.plugins.runner: Running plugin subprocess: Q:\Git\GiteaManager\sherpanote\.plugin_dev\.venv\Scripts\python.exe -m py.plugins.runners.opendata_runner --json-input eyJmaWxlX3BhdGgiOiAiUTpcXFZlcnlTeW5jXFxDVUhLLUxlYXJuaW5nXFxTT0NJNTYwMSBUaGVvcnlcXEZpbmFsXFxTT0NJIDU2MDEgVGFrZS1Ib21lIEV4YW0ucGRmIiwgImphdmFfcGF0aCI6ICJDOlxcUHJvZ3JhbSBGaWxlc1xcSmF2YVxcamRrLTE3LjAuMVxcYmluXFxqYXZhLmV4ZSJ9
  04:20:15 [WARNING] py.document_extractor: opendataloader-pdf extraction failed: Plugin output is not valid JSON: Extra data: line 1 column 2 (char 1)
  04:20:15 [WARNING] py.document_extractor: opendataloader unavailable/failed for Q:\VerySync\CUHK-Learning\SOCI5601 Theory\Final\SOCI 5601 Take-Home Exam.pdf, falling back
  04:20:15 [INFO] py.document_extractor: Text layer found: Q:\VerySync\CUHK-Learning\SOCI5601 Theory\Final\SOCI 5601 Take-Home Exam.pdf -> markitdown
  04:20:16 [INFO] py.adapters.markitdown_adapter: Converting with markitdown: Q:\VerySync\CUHK-Learning\SOCI5601 Theory\Final\SOCI 5601 Take-Home Exam.pdf

```
  后端修复 (4项)

  ┌─────┬───────────────────┬───────────────────────────────────────────┬───────────────────────────────────────────┐
  │  #  │       问题        │                   根因                    │                   修复                    │
  ├─────┼───────────────────┼───────────────────────────────────────────┼───────────────────────────────────────────┤
  │ 1   │ PDF引擎切换不生效 │ update_config() 未失效缓存的              │ 添加 self._document_extractor = None 和   │
  │     │                   │ _document_extractor                       │ self._plugin_manager = None               │
  ├─────┼───────────────────┼───────────────────────────────────────────┼───────────────────────────────────────────┤
  │ 2   │ 卸载报错 -y       │ uv pip uninstall 不支持 -y 参数           │ 移除 -y 标志                              │
  ├─────┼───────────────────┼───────────────────────────────────────────┼───────────────────────────────────────────┤
  │ 3   │ 安装/卸载无日志   │ 缺少 logger 调用                          │ install_plugin()/uninstall_plugin() 添加  │
  │     │                   │                                           │ logger.info/error                         │
  ├─────┼───────────────────┼───────────────────────────────────────────┼───────────────────────────────────────────┤
  │ 4   │ Docling import    │ PdfPipelineOptions 在 v2 中路径变为       │ 修正 import 路径，移除不存在的 ocr_engine │
  │     │ 错误              │ docling.datamodel.pipeline_options        │  属性                                     │
  └─────┴───────────────────┴───────────────────────────────────────────┴───────────────────────────────────────────┘

  Runner 修复 (2项)

  ┌─────┬─────────────────────┬─────────────────────────────────────────────────────────────────────────────────────┐
  │  #  │        问题         │                                        修复                                         │
  ├─────┼─────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ 5   │ Opendata runner     │ 重写 _run_opendataloader() 捕获 Java stderr，检测 UnsupportedClassVersionError      │
  │     │ 错误不透明          │ 等常见错误并给出中文友好提示                                                        │
  ├─────┼─────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ 6   │ Docling runner API  │ 修正为 v2 API（pipeline_options.ocr_options.lang，doc.num_pages）                   │
  │     │ 不兼容 v2           │                                                                                     │
  └─────┴─────────────────────┴─────────────────────────────────────────────────────────────────────────────────────┘

  前端修复 (6项)

  ┌─────┬─────────────────────────┬───────────────────────────────────────────────────────────┐
  │  #  │          问题           │                           修复                            │
  ├─────┼─────────────────────────┼───────────────────────────────────────────────────────────┤
  │ 7   │ 界面英文                │ DocumentSettingsPanel 全面中文化                          │
  ├─────┼─────────────────────────┼───────────────────────────────────────────────────────────┤
  │ 8   │ 环境未自动检测          │ onMounted 自动调用 runDetectJava()                        │
  ├─────┼─────────────────────────┼───────────────────────────────────────────────────────────┤
  │ 9   │ 缺少销毁 venv           │ 新增后端 destroy_plugin_venv API + 前端按钮（含确认步骤） │
  ├─────┼─────────────────────────┼───────────────────────────────────────────────────────────┤
  │ 10  │ 插件状态不显示          │ 模板已使用解构变量替换 .value                             │
  ├─────┼─────────────────────────┼───────────────────────────────────────────────────────────┤
  │ 11  │ bridge 缺少 destroy     │ 添加 destroyPluginVenv()                                  │
  ├─────┼─────────────────────────┼───────────────────────────────────────────────────────────┤
  │ 12  │ composable 缺少 destroy │ 添加 doDestroyVenv()                                      │
  └─────┴─────────────────────────┴───────────────────────────────────────────────────────────┘

● 修复总结

  1. Java 路径传递链路打通

  之前 manual_java_path 只用于检测显示，实际执行 opendataloader 时从未使用。

  修复了完整链路：

  PluginConfig.manual_java_path
    → main.py _get_document_extractor() 传 plugin_config
      → DocumentExtractor._get_opendata_adapter() 传 java_path
        → OpendataAdapter(manual_java_path=)
          → detect_java(manual_path=) 优先使用手动路径
          → runner 接收 java_path，设置 JAVA_HOME 环境变量
            → opendataloader-pdf 使用正确的 Java 执行

  关键改动：
  - opendata_adapter.py: 构造函数接受 manual_java_path，extract_text_pdf() 传递 java_path 到 runner
  - opendata_runner.py: 接受 java_path 参数，设置 JAVA_HOME + PATH
  - document_extractor.py: 新增 plugin_config 参数，传递给 Adapter
  - main.py: 传递 self._config.plugin 到 DocumentExtractor

  2. 引擎回退前端提示

  当用户选择了 docling/opendataloader 但实际使用了其他引擎时，前端弹出警告：

  ▎ "注意：所选引擎 Docling 不可用，已使用 markitdown"

  实现：
  - main.py ocr_complete 事件携带 backend_used 字段
  - OcrView.vue 比较所使用的引擎与配置的引擎，不匹配时显示 warning toast

  3. 设置自动保存

  Document/Plugin 配置修改后 500ms 自动保存，无需手动点击 Save。实现：SettingsView.vue 对 pluginConfig/documentConfig
  添加 watch(deep: true) 带 setTimeout 防抖。
  
  ● 总结

  1. 默认模型目录改为 data\docling

  链路: PluginConfig.docling_artifacts_path -> DocumentExtractor -> DoclingAdapter -> runner ->
  PdfPipelineOptions.artifacts_path

  当用户未手动指定时，自动使用 软件目录\data\docling 作为模型存储位置。UI 提示也已更新：

  ▎ 留空则使用默认位置 (软件目录\data\docling)

  2. 模型下载时机 + 手动预下载

  时机: Docling 模型在 首次运行时 下载（调用 converter.convert() 时从 HuggingFace 拉取），不是在 pip install 时。

  新增"下载模型"按钮: Docling 已安装后，在后端管理卡片中出现"下载模型"按钮。点击后：
  1. 创建一个最小 PDF
  2. 触发 docling 转换，从而自动下载约 1.5GB 模型文件到 data/docling
  3. 显示下载进度
  4. 完成后自动清理临时 PDF

  3. 前端安装 bug 修复

  根因: install_plugin 用了 self.dispatch_task("install_plugin", {}) 但 dispatch_task 是主线程命令分发器，_work()
  函数从未被传入也不执行。

  修复: 改为 threading.Thread(target=_work, daemon=True).start() + Popen 逐行流式读取输出推送进度。
  
    根因: 安装/卸载完成后 _plugin_manager 和 _document_extractor 缓存未失效。前端 loadStatuses() 调用
  getAvailableBackends() 时返回的是旧缓存结果（docling: False），导致引擎选择项灰显。

  修复: 在 install_plugin 的 _work() 完成路径和异常路径，以及 uninstall_plugin 中，都添加：
  self._plugin_manager = None
  self._document_extractor = None

  （destroy_plugin_venv 和 update_config 已有此逻辑）
  
  ● 修复: PDF处理模式的引擎可用性判断现在同时检查两个数据源：

  - availableBackends (来自 getAvailableBackends API)
  - pluginStatuses (来自 getPluginStatus API — 与后端管理处使用相同来源)

  const isDoclingAvailable = computed(
    () => availableBackends.value.docling === true
       || pluginStatuses.value.docling?.installed === true,
  );

  这样即使某一数据源异常，只要后端管理卡片显示已安装，引擎下拉选项就会同步显示可用。
  ● 两个问题同一个根因：

  py/document_extractor.py 缺少 from pathlib import Path，导致 _get_docling_adapter() 中 Path("data") / "docling" 抛出
  NameError → get_available_backends() 异常被 try/except 吞掉返回 {success: false} → 前端 availableBackends 始终为空 {}
  → 引擎下拉永远显示"未安装"。

  加上 import 后，getAvailableBackends() 恢复正常，下拉选项也会同步更新。之前添加的双数据源检查（pluginStatuses
  兜底）作为保险仍然保留。
  
  - _setup_hf_home()：把相对路径 data/docling 转为绝对路径，mkdir -p 确保存在，设置 os.environ["HF_HOME"]
  - _run_docling()：调用前先 _setup_hf_home(artifacts_path)，PdfPipelineOptions.artifacts_path 不设置，让 docling 走 HF
  hub 自然查找/下载
  - _pre_download_models()：同样设 HF_HOME，跑一次空 PDF 转换触发下载，模型落在 data/docling/hub/ 下
  - 默认路径：data/docling，用户可在设置中覆盖
  
    1. 空白内容：默认 --format json 生成的 JSON 键是 kids[].content，没有 markdown。改为 --format markdown 直接生成 .md
  文件，读取即得文本内容。JSON 格式作为 fallback（从 kids 提取 content 拼接）。
  2. 临时目录：改为 data/temp，不自动清理，旧文件处理前先删除以防混淆。
```



# 其他问题

- opendata_runner生成的temp文件没有清理
- 没有持久化新功能对应的设置
- 全屏拖拽输入替换区域拖拽输入以节省排版空间 @reference\filedrop
- 导出备份默认不勾选应用配置，检查导出备份是否完全涵盖新功能对应的设置
- opendata_runner不知道支不支持扫描件，效果怎么样，可以测试一下

  1. opendata_runner 临时文件清理 -- _run_opendataloader 读取完生成文件后立即删除它们
  2. 导出备份默认不勾选应用配置 -- include_config 默认值改为 false。备份本身已涵盖 plugin/document 配置（通过
      config.json 导出完整 AppConfig），无需额外修改
  3. OcrView 全屏拖拽 -- 移除了专用的上传区域卡片，替换为全屏拖拽覆盖层 + 紧凑工具栏（标题输入 +
      选择文件按钮）。拖拽支持多文件
  4. opendata_runner 扫描件测试 -- 不支持。扫描 PDF 只能输出页码和图片引用，没有实际文本。扫描件路由应继续走 ppocr

- 设置页中持久化了但是OCR页中PDF引擎选择没有持久化，每次打开都是显示默认的设置，打开设置页之后才更新
- 设置页中环境设置有戳出容器的小字（检测到的Java路径、docling说明）
- OCR页上传了文件之后的文件列表给每个PDF文件添加一个检测PDF是否有文字层的功能

● 完成。PDF 文件添加到列表后会自动检测文字层：

  - 检测中: 显示小 spinner badge
  - 有文字层: 绿色 text badge
  - 无文字层（扫描件）: 红色 scan badge
  - 非 PDF 文件不检测

## 补充功能

测试docling默认没有ocr扫描件的功能，我看他不是能搭配rapidocr吗，能够实现吗

可以。Docling 自带 RapidOcrOptions，不需要额外装 rapidocr-onnxruntime（docling 的依赖里已包含）。

  改动总结：docling_runner.py 的 OCR 模式从 EasyOCR（默认）切换为 RapidOcrOptions(lang=["english",
  "chinese"])，支持中英文扫描件识别。RapidOCR 相比 EasyOCR 更轻量，且 SherpaNote 本身已使用 RapidOCR 生态。

## CC-Mem

```
Apr 30, 2026

..\..\Git\GiteaManager\sherpanote\py\plugins\paths.py
  #4294  1:19 AM  🔵  Phase 3 Development Initiated  
  #4295           🔵  SherpaNote Architecture Explored for Phase 3  
..\..\Git\GiteaManager\sherpanote\py\plugins\__init__.py
  #4297           🔵  Plugin Runner Implementations and Frontend Composables Identified  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4298           🔵  SettingsView Configuration Architecture Documented  
..\..\Git\GiteaManager\sherpanote\py\plugins\manager.py
  #4299           🔵  SherpaNote Core Architecture Analyzed  
..\..\Git\GiteaManager\sherpanote\py\plugins\runners\docling_runner.py
  #4300  1:20 AM  🔵  Frontend Composables and Plugin Runners Implementation Patterns Documented  
..\..\Git\GiteaManager\sherpanote\main.py
  #4301           🔵  API Architecture and Plugin Integration Points Mapped  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4302           🔵  SettingsView Model and Dependency Management Implementation Detailed  
..\..\Git\GiteaManager\sherpanote\main.py
  #4303  1:21 AM  🔵  Plugin Manager and Document Extractor Integration Architecture  
  #4304           🔵  Plugin and OCR Management API Surface Documented  
..\..\Git\GiteaManager\sherpanote\py\plugins\java_detect.py
  #4305           🔵  Supporting Plugin Files and Settings Tab Structure Confirmed  
..\..\Git\GiteaManager\sherpanote\py\document_extractor.py
  #4306           🔵  Document Extraction Decision Tree and Java Detection Architecture  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4307  1:22 AM  🔵  Phase 3 Planning Reveals Complete Backend Plugin System with Frontend Integration Gaps  
  #4308           🔵  Config Save Patterns and OCR Tab Implementation Confirmed  
..\..\Git\GiteaManager\sherpanote\frontend\src\stores\appStore.ts
  #4309           🔵  App Store State Architecture Confirmed Missing Plugin and Document Config Sections  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4310           🔵  SettingsView Imports and State Initialization Confirm Missing Plugin Configuration  
  #4311  1:23 AM  🔵  saveConfig Function Excludes Plugin and Document Config Sections  
docs/PRD-2.1.0.md
  #4312  1:37 AM  ⚖️  SherpaNote Phase 3 implementation plan approved  
General
  #4313           ⚖️  Phase 3 implementation broken into 9 discrete tasks  
  #4314           ⚖️  Phase 3 task dependencies established with two-track parallel execution  
frontend/src/bridge.ts
  #4315  1:38 AM  🟣  Plugin backend bridge helpers added to bridge.ts  
frontend/src/stores/appStore.ts
  #4316           🟣  Plugin and Document config refs added to Pinia store  
  #4317           🟣  Store export updated with pluginConfig and documentConfig  
frontend/src/composables/usePlugin.ts
  #4318           🟣  usePlugin composable created for plugin lifecycle management  
  #4319           🔄  usePlugin composable refactored with automatic cleanup and simplified error handling  
frontend/src/components/settings/DocumentSettingsPanel.vue
  #4320  1:39 AM  🟣  DocumentSettingsPanel component created with PDF engine selection, plugin management, and environment configuration  
frontend/src/views/SettingsView.vue
  #4321  1:42 AM  🟣  PluginConfig and DocumentConfig types added to SettingsView imports  
  #4322           🟣  pluginConfig and documentConfig refs added to SettingsView  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4323  1:43 AM  🟣  Added Document Settings Panel component to SettingsView  
General
  #4324           🟣  Phase 3 development tasks progressing for document processing features  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\OcrView.vue
  #4325           🔵  OcrView.vue component implements comprehensive OCR processing interface  
  #4326           🟣  Added intelligent engine detection and user guidance to OcrView  
  #4327           🟣  Engine detection now displays visual hint in OCR file list UI  
..\..\Git\GiteaManager\sherpanote\frontend\src\components\settings\DocumentSettingsPanel.vue
  #4328           🔵  DocumentSettingsPanel.vue template structure reveals plugin management UI  
  #4330  1:44 AM  🔄  Added template helper functions to DocumentSettingsPanel component  
  #4332           🔄  DocumentSettingsPanel refactored to destructure usePlugin composable  
  #4333           🔄  DocumentSettingsPanel watch statements updated to use destructured plugin state  
General
  #4334  11:38 AM  ✅  Task list identified for session work  
..\..\Git\GiteaManager\sherpanote\py\plugins\runners\opendata_runner.py
  #4335  11:42 AM  🔵  OpenData Runner Temp File Management  
..\..\Git\GiteaManager\sherpanote\main.py
  #4336            🔵  Export Backup Configuration  
..\..\Git\GiteaManager\sherpanote\py\adapters\opendata_adapter.py
  #4337  11:43 AM  🔵  OpenDataLoader Document Processing  
..\..\Git\GiteaManager\sherpanote\main.py
  #4338            🔵  Configuration Persistence Mechanism  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4339            🔵  Backup Configuration Default  
  #4340            🔵  Backup Configuration Coverage  
..\..\Git\GiteaManager\sherpanote\main.py
  #4341            🔵  Backup System Architecture  
..\..\Git\GiteaManager\sherpanote\py\backup.py
  #4342            🔵  Backup System Configuration Handling  
..\..\Git\GiteaManager\sherpanote\py\config.py
  #4343            🔵  Configuration Data Model Structure  
  #4344            🔵  Configuration Serialization Support  
..\..\Git\GiteaManager\sherpanote\py\plugins\runners\opendata_runner.py
  #4345  11:44 AM  🔴  OpenData Runner Temp File Cleanup  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\OcrView.vue
  #4346            🟣  Fullscreen Drag and Drop Implementation  
..\..\Git\GiteaManager\sherpanote\py\plugins\runners\opendata_runner.py
  #4347            ✅  Temp File Cleanup Task Status Updated  
  #4348  11:48 AM  🔴  OpenData Runner Temp File Cleanup Implemented  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4349            🔴  Backup Default Configuration Changed  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\OcrView.vue
  #4350  11:49 AM  🔄  OcrView Drag-Drop System Refactored  
  #4351            🟣  Fullscreen Multi-File Drag-Drop Implemented  
  #4352  11:50 AM  🟣  OcrView UI Streamlined with Fullscreen Drag-Drop  
  #4353            ✅  Task Progress: Fullscreen Drag-Drop Completed  
..\..\Git\GiteaManager\sherpanote\py\plugins\runners\opendata_runner.py
  #4354            🔵  OpenData Runner Text-Only Processing Confirmed  
  #4355  11:51 AM  🔵  OpenDataLoader PDF Not Installed  
..\..\Git\GiteaManager\sherpanote\test\Lectures Extract[1-2].pdf
  #4356  11:58 AM  🔵  Test PDF is scanned document requiring OCR  
..\..\Git\GiteaManager\sherpanote\.plugin_dev\.venv\Lib\site-packages\opendataloader_pdf\runner.py
  #4357  12:02 PM  🔵  opendataloader-pdf uses embedded JAR with dual output modes  
..\..\Git\GiteaManager\sherpanote\test\Lectures Extract[1-2].pdf
  #4358  12:03 PM  🔵  opendataloader-pdf extracts images from scanned PDFs without OCR  
General
  #4359  12:07 PM  🔵  Drag-and-drop file handling uses Tauri backend command  
  #4360            🔵  OCR completion handling routes to editor view  
  #4361  12:08 PM  🔵  Drag overlay uses pointer-events-none causing drop target issue  
  #4362            🔴  Added window-level drag event handlers to prevent default file opening  
  #4363            🔴  Added cleanup for window drag event listeners in onUnmounted  
  #4364  12:09 PM  🔵  Located onMounted lifecycle hook for event listener registration  
  #4365            🔵  Identified onMounted hook structure for window event registration  
  #4366  12:10 PM  🔴  PDF engine selection persistence issue identified  
  #4367            🔴  Settings page UI text overflow issue identified  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\OcrView.vue
  #4368            🔵  OcrView engine selection uses reactive computed properties from store  
  #4369  12:11 PM  🔵  OcrView onMounted hook only loads backends, not configuration  
..\..\Git\GiteaManager\sherpanote\frontend\src\bridge.ts
  #4370            🔵  Configuration loading not found in bridge.ts  
  #4371  12:12 PM  🔵  Bridge API lacks get_config function for loading persisted settings  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
  #4372            🔵  SettingsView loads and populates store with document configuration  
  #4373            🔵  SettingsView loadConfig function uses call("get_config") API  
  #4374            🔵  loadConfig called at three locations in SettingsView  
  #4375            🔵  SettingsView onMounted calls loadConfig to initialize store  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\OcrView.vue
  #4376            🔴  Fixed OCR page PDF engine selection not persisting on load  
..\..\Git\GiteaManager\sherpanote\frontend\src\components\settings\DocumentSettingsPanel.vue
  #4377            🔵  Settings page text overflow sources identified in DocumentSettingsPanel  
  #4378  12:13 PM  🔴  Fixed Java path text overflow in settings environment section  
frontend/src/views/OcrView.vue
  #4379  12:17 PM  🟣  Adding PDF text layer detection to OCR file list  
  #4380            🔵  OcrView file list and PDF engine selector structure  
  #4381            🔵  File entry rendering structure in OcrView  
frontend/src/bridge.ts
  #4382            🔵  Backend has_text_layer function already exists  
py/text_detector.py
  #4383  12:18 PM  🔵  has_text_layer function implementation details  
main.py
  #4384            🔵  OCR engine and document extractor initialization in main.py  
  #4385            🔵  ocr_process method already uses PDF text layer detection  
  #4386  12:19 PM  🔵  Planned API insertion point identified in main.py  
  #4387            🟣  Added detect_pdf_text_layer API method to main.py  
frontend/src/bridge.ts
  #4388  12:20 PM  🟣  Added detectPdfTextLayer bridge function to frontend  
frontend/src/views/OcrView.vue
  #4389            🟣  Added detectPdfTextLayer import to OcrView.vue  
  #4390            🟣  Added PDF text layer detection state and function to OcrView  
  #4391  12:22 PM  🟣  Triggered PDF text layer detection on file upload  
  #4392            🟣  Added PDF text layer status indicator to file list UI  
..\..\Git\GiteaManager\sherpanote\frontend\src\views\OcrView.vue
  #4393  12:24 PM  🔵  Fullscreen drag drop zone investigation  
  #4394  12:25 PM  🔵  Drop handler implementation uses backend IPC call  
  #4395  12:26 PM  🔵  Window-level drop listener registered in onMounted  
  #4396            🔵  Window event listeners cleaned up in onUnmounted  
  #4397            🔵  Root cause identified: Container width limitation  
  #4398            🔴  Window-level drop handler now processes files  
  #4399  12:27 PM  🔴  Removed duplicate element-level onDrop handler  
  #4400            🔴  Registered window-level dragenter and dragleave listeners  
  #4401            🔴  Added cleanup for window dragenter and dragleave listeners  
General
  #4402  12:29 PM  🔵  Docling already has built-in OCR support  
  #4403            🔵  Context7 identifies multiple Docling documentation sources  
  #4404            🔵  Docling supports multiple OCR backends including RapidOCR  
  #4405            🟣  Implemented RapidOCR backend for docling OCR processing  
  #4407  12:32 PM  🔵  EasyOCR not installed in project virtual environment  
  #4408  12:33 PM  🔵  Docling model cache occupies 506MB of storage  
  #4409            🔵  Docling does not depend on EasyOCR or RapidOCR  
  #4410            🔵  EasyOCR never installed in project dependency tree  
  #4411            🔵  Docling-slim depends on standard Python packages, no OCR engines  
  #4412  12:35 PM  🔵  Docling OCR model dependency investigation  
  #4413            🔵  Docling OCR models downloaded on first use, not bundled  
  #4415            🔵  RapidOcrOptions exposes configurable model paths  
  #4416            🔵  RapidOcrOptions model paths default to None  
  #4417  12:36 PM  🔵  rapidocr package installed but rapidocr_onnxruntime missing  
  #4418  12:37 PM  🔵  rapidocr package includes bundled ONNX models
```

● 需求/问题: 录音页拖拽上传改为全屏拖拽，分左右两半
  根源: 原来是元素级拖拽，区域小
  实现方案: 窗口级 dragenter/leave/over/drop 监听 + Teleport 挂载 body + flex-1 左右各半
  结果: 左侧直接转写，右侧导入并转写，鼠标跟随高亮
  ────────────────────────────────────────
  需求/问题: 拖拽覆盖层没有全屏
  根源: 两个半区缺少 flex-1，默认 flex:0 1 auto 按内容收缩
  实现方案: 给左右半区加 flex-1
  结果: 各占视口 50%
  ────────────────────────────────────────
  需求/问题: 上传错误格式文件导致页面错误且无提示
  根源: 无前端文件格式校验
  实现方案: 拖拽放下时检查扩展名，不匹配则 showToast 报错
  结果: 支持常见音视频格式 + m4s
  ────────────────────────────────────────
  需求/问题: 打包后首页转录记录无限转圈
  根源: pywebview API 未就绪时 call() 抛异常，isLoading 永不重置
  实现方案: bridge.ts call() 兜底返回 error + useStorage 用 try-finally 包裹
  结果: 桥接竞态不再卡死
  ────────────────────────────────────────
  需求/问题: 记录多了首页加载慢
  根源: list() SELECT * 返回完整 transcript + ai_results_json，且逐条查 version (N+1)
  实现方案: 只查摘要列 + SUBSTR preview + 批量查 version 单条 SQL
  结果: 列表加载大幅减少数据传输
  ────────────────────────────────────────
  需求/问题: 优化列表后 AI 处理标记消失
  根源: 摘要查询不再返回 ai_results_json
  实现方案: SQL 加 CASE WHEN ai_results_json != '{}' THEN 1 返回 has_ai 字段
  结果: RecordCard 适配两种模式
  ────────────────────────────────────────
  需求/问题: TS 编译错误：PluginConfig 未导入
  根源: OcrView.vue 使用了类型但 import 遗漏
  实现方案: 补充 import
  结果: 已修复
  ────────────────────────────────────────
  需求/问题: TS 编译错误：string | null 赋给 title
  根源: javaResult.path 为 null 但 title 属性要求 string | undefined
  实现方案: 加 ?? undefined
  结果: 已修复
  ────────────────────────────────────────
  需求/问题: DeepSeek API 报 model name 无效
  根源: 数据库中模型名前有空格  deepseek-v4-flash
  实现方案: config.py from_dict 加 _str helper 对 model 做 strip() + 修复数据库脏数据
  结果: 已修复并加防护
  ────────────────────────────────────────
  需求/问题: 设置里模型目录为空
  根源: 旧配置 model_dir 存空字符串，.get() 取到空值不触发默认值
  实现方案: 改用 or 运算符，空字符串也回退默认值
  结果: 默认指向 project_root/models

- Mac导入PDF崩溃
- 当前插件的 pip 安装（uv pip install）没有指定任何镜像源，默认走 PyPI 官方源。在国内环境下会非常慢甚至超时。Docling模型下载的的HF源同理。

# 📝 Commit Message

```
feat(ui): 插件管理设置界面与引擎选择

- 新增 DocumentSettingsPanel 组件：引擎切换、后端管理、环境配置
- 新增 usePlugin composable 封装安装/卸载事件生命周期
- bridge 与 Pinia store 扩展插件/文档配置支持
- OCR 页改为全屏拖拽布局，文件列表自动检测 PDF 文字层
- 修复引擎切换不生效（缓存未失效）、安装无日志、卸载 -y 报错
- 修复 Java 路径未传递至执行链路、引擎回退无前端提示
- 修复 Docling v2 API 兼容性、opendata runner 输出格式
- 设置变更自动保存、界面全面中文化、临时文件清理
- Docling默认使用RapidOCR进行OCR识别

fix(core): 修复多项异常并优化列表加载性能
- 修复拖拽覆盖层未全屏的问题
- 新增上传文件格式前端校验与错误提示
- 修复桥接未就绪导致首页无限转圈的问题
- 优化列表查询，消除冗余查询以提升加载速度
- 补充列表摘要查询缺失的 AI 处理标记
- 修复多处 TS 类型编译错误
- 修复模型名空格及空目录配置导致的运行异常

fix(ocr): 修复导入PDF时pypdfium2导致的段错误

  PdfDocument.__exit__ 在关闭时通过weakref终结器与显式close竞争，
  在macOS ARM64上触发double-free段错误。将with语句替换为显式
  try/finally并在循环中主动释放页面资源，避免竞态条件。
  
feat(settings): 添加 PyPI 和 HuggingFace 镜像源配置选项

- 添加 PyPI 镜像源选择功能，支持官方源和常用国内镜像源
  （清华大学 TUNA、阿里云、腾讯云）以及自定义选项
- 添加 HuggingFace 镜像源选择功能，支持官方源和 HF-Mirror
  以及自定义选项
- 在插件安装时使用配置的 PyPI 镜像源地址
- 在 Docling 模型下载时使用配置的 HuggingFace 镜像端点
- 更新相关类型定义和配置结构以支持新的镜像源配置项
```

# 🚀 Release Notes

```
## 2026-04-30 - 插件管理与文档引擎设置界面

### ✨ 新增
- 设置页新增"OCR / 文档"面板，包含三大功能区块：
  - PDF 处理模式：可选择文本层引擎与扫描件引擎，不可用引擎自动置灰
  - 后端管理：可视化安装/卸载 docling 与 opendataloader-pdf，含进度展示
  - 环境设置：自动检测 Java 环境，可自定义 Java 路径与 Docling 模型目录
- Docling 支持手动预下载模型，默认存储于软件目录下的 data/docling
- 新增销毁插件虚拟环境功能（含二次确认）
- OCR 页升级为全屏拖拽布局，上传文件后自动检测是否为扫描件
- 引擎回退时弹出警告提示，告知用户实际使用的引擎
- 上传文件时自动校验格式，不支持的格式会弹出明确提示
- 添加 PyPI 和 HuggingFace 镜像源配置选项

### 🐛 修复
- 修复切换 PDF 引擎后不生效的问题
- 修复插件安装/卸载时无日志输出、安装进度无响应的问题
- 修复自定义 Java 路径未实际生效的问题
- 修复 opendataloader-pdf 处理后输出空白内容的问题
- 修复设置页环境配置文字溢出容器的问题
- 修复 OCR 页引擎选择未在启动时同步已保存配置的问题
- 修复插件安装完成后引擎选项仍显示未安装的问题
- 修复导出备份默认勾选应用配置的问题
- 修复拖拽上传区域无法铺满全屏的问题
- 修复打包后打开首页可能一直显示加载动画的问题
- 修复历史记录列表中 AI 处理状态标记偶尔消失的问题
- 修复部分情况下模型调用失败的问题
- 修复设置中模型目录配置异常导致找不到本地模型的问题
- 修复MAC端导入PDF时pypdfium2导致的段错误

### ⚡ 优化
- 插件与文档配置修改后自动保存，无需手动点击保存
- opendataloader-pdf 临时文件处理完毕后自动清理
- 扫描件 PDF 自动跳过 opendataloader，直接使用 OCR 引擎
- 大幅提升历史记录列表的加载速度，记录越多提速越明显
```
