# OCR Processing

## Metadata

- **ID**: WF-006
- **Version**: 2.0.0
- **Owner**: Document Extraction Module (py/document_extractor.py, py/ocr.py, main.py)
- **Trigger**: User uploads images/PDFs/Office docs on OcrView and starts processing
- **Last Updated**: 2026-04-29

---

## Overview

Extract text from images, PDFs, and Office documents using an intelligent decision tree that routes each file to the optimal extraction backend. Supports batch mode (one record per file) and single/sequential mode (merge all into one record). OCR records are auto-prefixed with "OCR-" for easy identification.

### Decision Tree

```
[Input File]
  |-- Image (PNG/JPG/BMP/TIFF/WebP) --> PP-OCR (RapidOCR)
  |-- Office (DOCX/PPTX/XLSX) --> markitdown
  |-- PDF
        |-- has_text_layer? (pdfplumber, first 3 pages, >50 chars)
        |     |-- Yes --> markitdown
        |     +-- No  --> PP-OCR (pypdfium2 PDF->image -> OCR)
        +-- Fallback: markitdown failure -> PP-OCR
```

### Backend Architecture

| Module | Purpose |
|--------|---------|
| `py/document_extractor.py` | Decision tree orchestrator, routes files to adapters |
| `py/text_detector.py` | File type classification + PDF text layer detection |
| `py/adapters/ppocr_adapter.py` | PP-OCR (RapidOCR) -> ExtractedDocument |
| `py/adapters/markitdown_adapter.py` | markitdown -> ExtractedDocument |
| `py/outputs/unified_document.py` | ExtractedDocument unified data model |
| `py/ocr.py` | OcrEngine (RapidOCR) for image OCR + PDF-to-image conversion |

---

## Pre-conditions

- [ ] OCR models are installed for image/scan processing (det/rec/cls in RapidOCR model dir)
- [ ] Input files are valid: images (PNG, JPG, BMP, TIFF, WebP), PDFs, or Office docs (DOCX, PPTX, XLSX)
- [ ] No document processing is currently running

---

## Flow

### Step 1: File Upload

**Actor**: User
**Action**: Drag-and-drop files onto OcrView or click add button to use `pick_image_files()` (multi-select)
**Validation**: File types classified as image/pdf/office
**On Failure**: "Unsupported file format"

### Step 2: Configure Processing

**Actor**: User
**Action**: Select processing mode:
  - **Single mode**: All files merged into one record
  - **Batch mode**: Each file becomes a separate record
**Validation**: Mode is valid
**On Failure**: Default to batch mode

### Step 3: Start Processing

**Actor**: User
**Action**: Click start button, `ocr_process(files, mode, title)` called in background thread
**Validation**: Files readable, backends available
**On Failure**: "Processing failed" with error details

### Step 3.1: Decision Tree Execution (System)

**Actor**: DocumentExtractor
**Action**:
  1. Classify file type via `classify_file()` (image/pdf/office)
  2. If image: route to PpocrAdapter.extract_image()
  3. If office: route to MarkitdownAdapter.convert()
  4. If PDF: run text layer detection via `has_text_layer()` (pdfplumber)
     - Has text layer: MarkitdownAdapter.convert() (fallback to PP-OCR on failure)
     - No text layer: PpocrAdapter.extract_pdf_as_images() (pypdfium2 -> image -> OCR)
**Output**: ExtractedDocument with markdown content, metadata, and backend info

### Step 4: Progress Display

**Actor**: System
**Action**: Emit progress events per file `{ current, total }`; per-page progress for PDF OCR
**Validation**: Progress updates for each file
**On Failure**: Show "Processing..." without detailed progress

### Step 5: Create Records

**Actor**: System
**Action**:
  - **Batch**: Create one record per file with "OCR-" prefix + filename as title
  - **Single/Sequential**: Create one record with merged markdown from all files, user-provided or auto title
**Validation**: Extracted text is non-empty
**On Failure**: Skip empty results, show warning

### Step 6: Cancel (optional)

**Actor**: User
**Action**: Click cancel, `cancel_ocr()` aborts processing
**Validation**: Processing thread responds to cancel flag
**On Failure**: Force terminate thread

---

## Post-conditions

- [ ] Records created with extracted text (markdown format)
- [ ] Titles prefixed with "OCR-" (batch mode) or user-provided title (single mode)
- [ ] Records visible in HomeView list
- [ ] Backend info recorded in record metadata (ppocr/markitdown)

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| No OCR models | scan_ocr_models() empty | Link to model settings | "Install OCR models first" |
| Unreadable image | PIL/image error | Skip file | "Cannot read image" |
| Empty extraction result | markdown length = 0 | Skip file | "No text detected" |
| PDF encrypted | pdfplumber/pypdfium2 error | Fallback to PP-OCR or skip | "PDF processing error" |
| markitdown failure | Exception in adapter | Fallback to PP-OCR for PDFs | Automatic, logged |
| Unsupported file type | classify_file() = unknown | Skip file | "Unsupported file format" |
| Processing crash | Exception in thread | Cancel remaining | "Processing error" |

---

## Related

- **Business Rules**: BR-OCR-001 (naming convention), BR-OCR-002 (processing modes)
- **API Endpoints**: ocr_process, cancel_ocr, scan_ocr_models, download_ocr_models
- **State Machine**: OCR Processing State Machine
- **Data Models**: records.csv
- **PRD**: docs/PRD-2.1.0.md (OCR System Upgrade)
