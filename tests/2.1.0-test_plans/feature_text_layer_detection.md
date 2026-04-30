# Test Plan: Text Layer Detection

## Scope
`py/text_detector.py` -- `has_text_layer()`, `classify_file()`

## Prerequisites
- Test PDF files prepared: text PDF, scanned PDF, blank PDF, encrypted PDF, mixed PDF, short-text PDF, corrupted PDF
- `OcrConfig` with default detection settings (`detect_pages=3`, `detect_threshold=50`)

---

## Test Cases

### TC-001: Multi-page text PDF (P0)
- **Steps**:
  1. Prepare a 10-page PDF with text on every page (e.g., exported from Word)
  2. Call `has_text_layer(pdf_path)`
- **Expected**: Returns `True`. Accumulated non-whitespace chars across first 3 pages > 50.
- **Priority**: P0

### TC-002: Single-page text PDF (P0)
- **Steps**:
  1. Prepare a 1-page text PDF (e.g., a letter)
  2. Call `has_text_layer(pdf_path)`
- **Expected**: Returns `True` if page has > 50 non-whitespace chars.
- **Priority**: P0

### TC-003: Blank PDF (no text, no images) (P0)
- **Steps**:
  1. Create or use a blank PDF with 0 text content
  2. Call `has_text_layer(pdf_path)`
- **Expected**: Returns `False`. 0 accumulated chars < threshold of 50.
- **Priority**: P0

### TC-004: Encrypted PDF (password-protected) (P1)
- **Steps**:
  1. Prepare a password-encrypted PDF
  2. Call `has_text_layer(pdf_path)` without providing a password
- **Expected**: Returns `False` gracefully. No crash. Warning logged about unable to open PDF.
- **Priority**: P1

### TC-005: Scanned PDF (image-only, no text layer) (P0)
- **Steps**:
  1. Prepare a scanned PDF (e.g., scanner output, each page is an image)
  2. Call `has_text_layer(pdf_path)`
- **Expected**: Returns `False`. pdfplumber extracts 0 or very few characters from image-only pages.
- **Priority**: P0

### TC-006: Mixed PDF (text pages + scanned pages) (P0)
- **Steps**:
  1. Prepare a PDF where first 3 pages have text, remaining pages are scanned images
  2. Call `has_text_layer(pdf_path)` with default `max_pages=3`
- **Expected**: Returns `True`. Text pages contribute enough chars (>50).
- **Priority**: P0

### TC-007: Very short text PDF (P1)
- **Steps**:
  1. Prepare a PDF with < 50 total non-whitespace characters across all pages (e.g., a single-page PDF with only a title like "Hello World")
  2. Call `has_text_layer(pdf_path)` with default `threshold=50`
- **Expected**: Returns `False`. Accumulated chars < threshold.
- **Priority**: P1

### TC-008: Configurable threshold (P1)
- **Steps**:
  1. Prepare a PDF with ~20 non-whitespace chars
  2. Set `detect_threshold=10` in OcrConfig
  3. Call `has_text_layer(pdf_path)`
- **Expected**: Returns `True` (20 > 10).
  4. Set `detect_threshold=100`
  5. Call again
- **Expected**: Returns `False` (20 < 100).
- **Priority**: P1

### TC-009: Configurable max_pages (P1)
- **Steps**:
  1. Prepare a 5-page PDF where page 1 is blank, pages 2-5 have text
  2. Set `detect_pages=1` in OcrConfig
  3. Call `has_text_layer(pdf_path)`
- **Expected**: Returns `False` (page 1 has no text).
  4. Set `detect_pages=3`
  5. Call again
- **Expected**: Returns `True` (pages 1-3 combined exceed threshold).
- **Priority**: P1

### TC-010: Corrupted PDF (P2)
- **Steps**:
  1. Create or obtain a corrupted/truncated PDF file
  2. Call `has_text_layer(pdf_path)`
- **Expected**: Returns `False` without crashing. Warning/error logged.
- **Priority**: P2

### TC-011: File classification -- image (P0)
- **Steps**:
  1. Call `classify_file("test.png")`
- **Expected**: Returns `FileTypeInfo(category="image", mime_type="image/png")`.
- **Priority**: P0

### TC-012: File classification -- office doc (P0)
- **Steps**:
  1. Call `classify_file("test.docx")`
  2. Call `classify_file("test.pptx")`
  3. Call `classify_file("test.xlsx")`
- **Expected**: All return `category="office"`.
- **Priority**: P0

### TC-013: File classification -- unsupported (P1)
- **Steps**:
  1. Call `classify_file("test.xyz")` (unknown extension)
- **Expected**: Returns `category="unknown"`.
- **Priority**: P1

---

## Regression Check
- [ ] `has_text_layer()` does not import or reference PyMuPDF/fitz
- [ ] pdfplumber is used exclusively for text extraction
- [ ] Threshold and max_pages are read from config, not hardcoded
