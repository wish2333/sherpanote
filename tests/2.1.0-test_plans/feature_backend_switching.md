# Test Plan: Backend Switching and Output Standardization

## Scope
`py/document_extractor.py`, `py/adapters/*.py`, `py/outputs/unified_document.py`

## Prerequisites
- Test files: text PDF, scanned PDF, DOCX, PPTX, XLSX, PNG image
- PP-OCR models installed (required for all image paths)
- Optional: docling and opendataloader-pdf installed (for plugin backend tests)

---

## Test Cases

### TC-001: Text PDF -- markitdown (P0)
- **Steps**:
  1. Configure `text_pdf_engine = "markitdown"`
  2. Call `DocumentExtractor.extract("sample_text.pdf")`
- **Expected**: Returns `ExtractedDocument` with non-empty `markdown` field. `raw_format = "markitdown"`. `backend = "markitdown"`. No error.
- **Priority**: P0

### TC-002: Text PDF -- PP-OCR fallback (P0)
- **Steps**:
  1. Configure `text_pdf_engine = "markitdown"`, `scan_pdf_engine = "ppocr"`
  2. Process a text PDF where markitdown somehow fails (or test the fallback chain directly)
- **Expected**: Falls back to PP-OCR. `ExtractedDocument` produced with `backend = "ppocr"`.
- **Priority**: P0

### TC-003: Scanned PDF -- PP-OCR (P0)
- **Steps**:
  1. Configure `scan_pdf_engine = "ppocr"`
  2. Call `DocumentExtractor.extract("sample_scanned.pdf")`
- **Expected**: Text layer detection returns `False`. PP-OCR is used. `ExtractedDocument` with `backend = "ppocr"`.
- **Priority**: P0

### TC-004: Office DOCX -- markitdown (P0)
- **Steps**:
  1. Call `DocumentExtractor.extract("sample.docx")`
- **Expected**: Returns `ExtractedDocument` with non-empty `markdown`. `raw_format` indicates DOCX source. No error.
- **Priority**: P0

### TC-005: Office PPTX -- markitdown (P1)
- **Steps**:
  1. Call `DocumentExtractor.extract("sample.pptx")`
- **Expected**: Returns `ExtractedDocument` with slide content in `markdown`. `raw_format` indicates PPTX source.
- **Priority**: P1

### TC-006: Office XLSX -- markitdown (P1)
- **Steps**:
  1. Call `DocumentExtractor.extract("sample.xlsx")`
- **Expected**: Returns `ExtractedDocument` with table data in `markdown`. `raw_format` indicates XLSX source.
- **Priority**: P1

### TC-007: Image -- PP-OCR (P0)
- **Steps**:
  1. Call `DocumentExtractor.extract("sample.png")`
- **Expected**: Returns `ExtractedDocument` with OCR result in `markdown`. `backend = "ppocr"`. `raw_format` indicates image type.
- **Priority**: P0

### TC-008: Output structure verification (P0)
- **Steps**:
  1. Extract any document
  2. Inspect the returned `ExtractedDocument`
- **Expected**: All required fields present:
  - `markdown`: str (non-empty after successful extraction)
  - `metadata`: dict
  - `tables`: list (may be empty)
  - `images`: list (may be empty)
  - `raw_format`: str (identifies the source format)
  - `backend`: str (identifies which backend was used)
  - `source_path`: str (path to the original file)
- **Priority**: P0

### TC-009: Dynamic engine switching -- text PDF (P0)
- **Steps**:
  1. Process a text PDF with `text_pdf_engine = "markitdown"` -- record result
  2. Change config to `text_pdf_engine = "ppocr"`
  3. Process the same PDF again
- **Expected**: First result uses markitdown. Second result uses PP-OCR. Both produce valid `ExtractedDocument`. Content may differ but both are non-empty.
- **Priority**: P0

### TC-010: Dynamic engine switching -- scanned PDF (P1)
- **Steps**:
  1. Process a scanned PDF with `scan_pdf_engine = "ppocr"` -- record result
  2. If docling is installed, change `scan_pdf_engine = "docling"` and process again
- **Expected**: Both produce valid output. Docling output may have better layout/table extraction.
- **Priority**: P1

### TC-011: Unsupported file format (P1)
- **Steps**:
  1. Call `DocumentExtractor.extract("sample.xyz")` (unknown extension)
- **Expected**: `classify_file()` returns `category="unknown"`. Extractor raises `ValueError` with message about unsupported format. No crash.
- **Priority**: P1

### TC-012: Batch extraction (P1)
- **Steps**:
  1. Prepare 3 files: text PDF, DOCX, PNG
  2. Call `DocumentExtractor.extract_batch([...])`
- **Expected**: All 3 files processed. Results returned in same order. Each result is a valid `ExtractedDocument`.
- **Priority**: P1

### TC-013: get_available_backends (P0)
- **Steps**:
  1. With no plugins installed, call `DocumentExtractor.get_available_backends()`
- **Expected**: Returns `{"ppocr": True, "markitdown": True, "docling": False, "opendataloader": False}`.
  2. Install docling plugin, call again
- **Expected**: `docling` becomes `True`.
- **Priority**: P0

---

## Regression Check
- [ ] All backends produce `ExtractedDocument` with consistent structure
- [ ] `raw_format` field correctly identifies which backend was used
- [ ] Decision tree correctly routes file types (image / office / pdf-text / pdf-scan)
- [ ] Fallback chain works when preferred backend fails or is unavailable
