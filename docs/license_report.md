# License Compliance Report

**Date**: 2026-04-30
**Version**: sherpanote v2.1.0

## Summary

**Status**: PASS (with notes)

All direct Python dependencies use permissive open-source licenses (MIT, Apache 2.0, BSD, Unlicense). PyMuPDF (AGPL) has been fully removed. The only GPL dependency is PyInstaller (dev-only), which has a special exception allowing commercial distribution. Plugin dependencies (docling, opendataloader-pdf) are user-installed on demand and not bundled with the main application.

---

## Direct Dependencies

| Package | Version | License | Bundled | Notes |
|---------|---------|---------|---------|-------|
| audioread | 3.1.0 | MIT | Yes | Audio decoding |
| huggingface_hub | 1.9.2 | Apache 2.0 | Yes | Model download client |
| onnxruntime | 1.24.4 | MIT | Yes | ML inference runtime |
| openai | 2.30.0 | Apache 2.0 | Yes | OpenAI API client |
| markitdown[pdf,docx,pptx,xlsx] | 0.1.5 | MIT | Yes | Microsoft document-to-markdown converter |
| pypdfium2 | 5.7.1 | BSD-3-Clause / Apache 2.0 | Yes | PDF rendering (replaces PyMuPDF) |
| python-docx | 1.2.0 | MIT | Yes | DOCX reader/writer |
| pywebview | 6.1 | BSD-3-Clause | Yes | Native desktop window |
| rapidocr | 3.8.1 | Apache 2.0 | Yes | OCR engine (PP-OCRv4/v5) |
| sherpa-onnx | 1.12.35 | Apache 2.0 | Yes | Speech recognition core |
| sherpa-onnx-bin | 1.12.35 | Apache 2.0 | Yes | Binary model files for sherpa-onnx |
| soundfile | 0.13.1 | BSD-3-Clause | Yes | Audio file I/O (libsndfile wrapper) |
| static-ffmpeg | 3.0 | MIT | Yes | Cross-platform ffmpeg binary downloader |
| yt-dlp | 2026.3.17 | Unlicense | Yes | Audio/video downloader |

## Dev Dependencies

| Package | Version | License | Bundled | Notes |
|---------|---------|---------|---------|-------|
| pyinstaller | 6.19.0 | GPLv2-or-later with special exception | No (build only) | Special exception allows commercial distribution of programs built with PyInstaller |

---

## Transitive Dependencies

### markitdown transitive deps

markitdown core dependencies:
- beautifulsoup4 (4.14.3) - **MIT**
- charset-normalizer (3.4.7) - **MIT**
- defusedxml (0.7.1) - **PSFL** (Python Software Foundation License)
- magika (0.6.2) - **Apache 2.0**
- markdownify (1.2.2) - **MIT**
- requests (2.33.1) - **Apache 2.0**

markitdown[pdf] extra:
- pdfminer.six (20251230) - **MIT** (PDF parser)
- pdfplumber (0.11.9) - **MIT** (PDF table/text extraction) -- depends on pdfminer.six, Pillow, pypdfium2

markitdown[docx] extra:
- lxml (6.0.2) - **BSD-3-Clause** (XML processing, wraps libxml2/libxslt)
- mammoth (1.11.0) - **BSD-2-Clause** (DOCX-to-HTML conversion)

markitdown[pptx] extra:
- python-pptx (1.0.2) - **MIT**

markitdown[xlsx] extra:
- openpyxl (3.1.5) - **MIT**
- et-xmlfile (2.0.0) - **MIT** (transitive dep of openpyxl)

### rapidocr transitive deps

- colorlog (6.10.1) - **MIT**
- numpy (2.4.4) - **BSD-3-Clause** (multi-license: BSD-3-Clause, 0BSD, MIT, Zlib, CC0-1.0)
- omegaconf (2.3.0) - **BSD-3-Clause**
- opencv-python (4.13.0.92) - **Apache 2.0**
- pillow (12.2.0) - **MIT-CMU** (historically MIT-like, compatible)
- pyclipper (1.4.0) - **MIT**
- pyyaml (6.0.3) - **MIT**
- shapely (2.1.2) - **BSD-3-Clause**
- six (1.17.0) - **MIT**
- tqdm (4.67.3) - **MPL-2.0 AND MIT** (dual-licensed)

omegaconf transitive dep:
- antlr4-python3-runtime (4.9.3) - **BSD**

### Other notable transitive deps

- certifi (2026.2.25) - **MPL-2.0** (CA certificate bundle)
- cryptography (46.0.7) - **Apache-2.0 OR BSD-3-Clause** (dual-licensed)
- protobuf (7.34.1) - **BSD-3-Clause** (Google protocol buffers; onnxruntime dep)
- flatbuffers (25.12.19) - **Apache 2.0** (onnxruntime dep)
- sympy (1.14.0) - **BSD** (onnxruntime dep)
- mpmath (1.3.0) - **BSD** (sympy dep)
- cffi (2.0.0) - **MIT** (C foreign function interface)
- pydantic (2.12.5) - **MIT** (openai dep)
- click (8.3.2) - **BSD-3-Clause** (openai/sherpa-onnx dep)
- httpx (0.28.1) - **BSD-3-Clause** (openai dep)
- httpcore (1.0.9) - **BSD-3-Clause** (httpx dep)
- filelock (3.25.2) - **MIT** (huggingface_hub/static-ffmpeg dep)
- colorama (0.4.6) - **BSD-3-Clause**
- pygments (2.20.0) - **BSD-2-Clause**
- importlib_metadata (9.0.0) - **Apache 2.0**
- zipp (3.23.1) - **MIT**
- more_itertools (11.0.2) - **MIT**
- bottle (0.13.4) - **MIT** (pywebview internal HTTP server)
- pythonnet (3.0.5) - **MIT** (pywebview .NET interop)
- clr_loader (0.2.10) - **MIT** (pywebview .NET runtime loader)

---

## Plugin Dependencies (Optional, user-installed)

These packages are NOT bundled with the main application. They are installed on-demand by the user into a separate plugin virtual environment.

| Package | License | Notes |
|---------|---------|-------|
| docling | Apache 2.0 | IBM's deep-learning PDF parser. User must `pip install docling` into plugin venv |
| opendataloader-pdf | Apache 2.0 (wraps Apache PDFBox) | Java-based PDF text extraction. Requires Java 11+. User must `pip install opendataloader-pdf` into plugin venv |

**Risk note**: Opendataloader-pdf requires Java 11+ runtime, which is a separate system dependency not distributed with sherpanote. Java is governed by the GPLv2+CE (Classpath Exception) for OpenJDK distributions such as Eclipse Temurin, or the Oracle No-Fee Terms and Conditions (NFTC) for Oracle OpenJDK. Sherpanote does not bundle or distribute any Java runtime.

---

## Bundled Binaries (via `--with-plugins` build flag)

These binaries are optionally bundled into the PyInstaller distribution when `--with-plugins` is specified at build time. They enable the plugin subsystem to work in frozen (packaged) mode.

| Binary | Version | License | Notes |
|--------|---------|---------|-------|
| python-build-standalone | 3.11.11 (build 20241016) | Python Software Foundation License (PSF) + MIT for build scripts | From indygreg/python-build-standalone. Provides a relocatable Python for the plugin venv. |
| uv | 0.6.6 | Apache 2.0 / MIT | From astral-sh/uv. Used for fast package installation in the plugin venv. |

---

## AGPL Risk Verification

- **PyMuPDF (AGPL) removed?** **YES**

  Evidence:
  - No `import fitz` or `from fitz` statement exists in any `.py` file under `py/`
  - The `py/ocr.py` `pdf_to_images()` method uses `import pypdfium2 as pdfium` (line 301) instead of PyMuPDF
  - `pyproject.toml` does not list PyMuPDF as a dependency
  - Historical references to PyMuPDF remain ONLY in archived reference documents (`reference/`, `docs/PRD-2.1.0.md`, `docs/changelog.md`) which are documentation-only

- **Any other AGPL dependencies?** **NO**

  An exhaustive scan of all installed package METADATA files found zero packages using AGPL or GPL (except PyInstaller which uses GPLv2 with a commercial exception).

---

## Copyleft License Summary

The following copyleft or weak-copyleft licenses were found:

| Package | License | Type | Risk | Notes |
|---------|---------|------|------|-------|
| pyinstaller (dev only) | GPLv2+ with special exception | Strong copyleft | LOW | The PyInstaller GPL exception explicitly allows distribution of programs built with PyInstaller under any license, including commercial. See https://pyinstaller.org/en/stable/license.html |
| certifi | MPL-2.0 | Weak copyleft | LOW | MPL-2.0 is a file-level copyleft. When used as a Python package (imported as a library), it does not require the overall application to be MPL-licensed. |
| tqdm | MPL-2.0 AND MIT | Weak copyleft (dual-licensed) | NONE | Users can choose the MIT license, which is fully permissive. |
| python-build-standalone (optional bundled binary) | PSF + MIT | Permissive | NONE | Same license as Python itself; fully permissive. |

**No AGPL, LGPL, or strong copyleft licenses found among the distributed application dependencies.**

---

## Recommendations

1. **No action required** -- All direct dependencies use permissive licenses (MIT, Apache 2.0, BSD, Unlicense). The application complies with all license requirements.

2. **PyInstaller license notice**: If distributing the PyInstaller-built binary, include the PyInstaller license (COPYING.txt) in the distribution's documentation/credits. PyInstaller's special exception permits this.

3. **MPL-2.0 compliance for certifi**: Since certifi (MPL-2.0) is imported as a Python library, no source disclosure obligation applies. Consider adding a brief note in the application credits about certifi licensing.

4. **MySQL Connector / GPL dependency check**: If the project were to add a MySQL connector (e.g., `mysql-connector-python`) in the future, verify it is the LGPL-licensed "Connector/Python" and not the GPL-licensed one.

5. **Plugin dependency liability**: docling (Apache 2.0) and opendataloader-pdf (Apache 2.0 wrapping Apache PDFBox) are user-installed, not bundled. If they are ever bundled directly in the future, verify their transitive dependency trees for copyleft licenses, particularly docling which pulls in deep learning frameworks that may have their own licensing.
