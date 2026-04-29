# OCR Processing

## Metadata

- **ID**: WF-006
- **Version**: 1.0.0
- **Owner**: OCR Module (py/ocr.py, main.py)
- **Trigger**: User uploads images/PDFs on OcrView and starts processing
- **Last Updated**: 2026-04-29

---

## Overview

Extract text from images and PDF files using RapidOCR. Supports batch mode (one record per file) and single mode (merge all into one record). OCR records are auto-prefixed with "OCR-" for easy identification.

---

## Pre-conditions

- [ ] OCR models are installed (det/rec/cls models in `data/rapid_ocr_models/`)
- [ ] Input files are valid images (PNG, JPG, BMP) or PDFs
- [ ] No OCR processing is currently running

---

## Flow

### Step 1: File Upload

**Actor**: User
**Action**: Drag-and-drop files onto OcrView or click add button to use `pick_image_files()` (multi-select)
**Validation**: File types are supported (image/*, .pdf)
**On Failure**: "Unsupported file format"

### Step 2: Configure Processing

**Actor**: User
**Action**: Select processing mode:
  - **Single mode**: All files merged into one record
  - **Batch mode**: Each file/page becomes a separate record
**Validation**: Mode is valid
**On Failure**: Default to batch mode

### Step 3: Start OCR

**Actor**: User
**Action**: Click start button, `ocr_process(files, mode, title)` called in background thread
**Validation**: OCR models available, files readable
**On Failure**: "OCR models not installed" with link to settings

### Step 4: Progress Display

**Actor**: System
**Action**: Emit progress events `{ current, total }` showing processing progress
**Validation**: Progress updates for each file
**On Failure**: Show "Processing..." without detailed progress

### Step 5: Create Records

**Actor**: System
**Action**:
  - **Batch**: Create one record per file with "OCR-" prefix + filename as title
  - **Single**: Create one record with merged text from all files, user-provided or auto title
**Validation**: OCR text is non-empty
**On Failure**: Skip empty results, show warning

### Step 6: Cancel (optional)

**Actor**: User
**Action**: Click cancel, `cancel_ocr()` aborts processing
**Validation**: Processing thread responds to cancel flag
**On Failure**: Force terminate thread

---

## Post-conditions

- [ ] Records created with OCR-extracted text
- [ ] Titles prefixed with "OCR-" (batch mode) or user-provided title (single mode)
- [ ] Records visible in HomeView list

---

## Error Handling

| Error Scenario | Detection | Recovery | User Feedback |
|---------------|-----------|----------|---------------|
| No OCR models | scan_ocr_models() empty | Link to model settings | "Install OCR models first" |
| Unreadable image | PIL/image error | Skip file | "Cannot read image" |
| Empty OCR result | Text length = 0 | Skip file | "No text detected in image" |
| PDF encrypted | PyMuPDF error | Skip file | "PDF is encrypted" |
| Processing crash | Exception in thread | Cancel remaining | "OCR processing error" |

---

## Related

- **Business Rules**: BR-OCR-001 (naming convention), BR-OCR-002 (processing modes)
- **API Endpoints**: ocr_process, cancel_ocr, scan_ocr_models, download_ocr_models
- **State Machine**: OCR Processing State Machine
- **Data Models**: records.csv
