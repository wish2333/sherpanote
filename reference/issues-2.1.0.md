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

# 审计更新

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
