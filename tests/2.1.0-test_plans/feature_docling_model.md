# Test Plan: Docling Model Download and Management

## Scope
`py/adapters/docling_adapter.py`, `py/plugins/runners/docling_runner.py`, `py/plugins/manager.py`

## Prerequisites
- Plugin venv created and docling package installed
- Network connection for online tests
- ~1.5GB free disk space for model download
- Offline artifacts directory (pre-downloaded models) for offline test

---

## Test Cases

### TC-001: First-time model download (P1)
- **Steps**:
  1. Ensure no cached docling models exist (clean `~/.cache/docling/` or custom artifacts_path)
  2. Process a PDF through docling_adapter
- **Expected**: Model download begins automatically. Progress is reported (if adapter exposes progress). Download completes successfully (~1.5GB). Extraction proceeds after download.
- **Priority**: P1

### TC-002: Cancel during download (P2)
- **Steps**:
  1. Start a docling extraction that triggers model download
  2. Cancel the operation mid-download (via UI cancel button or interrupt)
- **Expected**: Download stops cleanly. No corrupted partial files left in model cache. App remains responsive.
- **Priority**: P2

### TC-003: Offline use with artifacts_path (P0)
- **Steps**:
  1. Pre-download docling models to a known directory (e.g., `D:\docling_models\`)
  2. Set `docling_artifacts_path = "D:\docling_models"` in PluginConfig
  3. Disconnect from network
  4. Process a PDF through docling_adapter
- **Expected**: No network request is made. Model loads from artifacts_path directory. Extraction succeeds.
- **Priority**: P0

### TC-004: Resume interrupted download (P2)
- **Steps**:
  1. Partially download docling models (e.g., interrupt during download)
  2. Restart the extraction
- **Expected**: Download resumes from where it left off (huggingface_hub handles this). If not resumable, clean restart with fresh download.
- **Priority**: P2

### TC-005: Network error during download (P1)
- **Steps**:
  1. Start docling extraction that triggers model download
  2. Disconnect from network midway through download
- **Expected**: Download fails with clear network error message. No crash. User is informed to check network or use offline artifacts_path.
- **Priority**: P1

### TC-006: Custom artifacts_path with existing models (P1)
- **Steps**:
  1. Pre-populate `D:\docling_models\` with docling model files (from another machine or backup)
  2. Set `docling_artifacts_path = "D:\docling_models\"`
  3. Process a PDF
- **Expected**: Models are used from custom path. No download needed. Extraction works correctly.
- **Priority**: P1

### TC-007: Switch between online and offline modes (P2)
- **Steps**:
  1. First extraction: use online mode (no artifacts_path). Let models download.
  2. Second extraction: set artifacts_path to a new empty directory, go offline
  3. Third extraction: clear artifacts_path, go online
- **Expected**: Each mode works correctly. Mode switching does not corrupt model cache.
- **Priority**: P2

### TC-008: Docling with scan PDF (OCR mode) (P1)
- **Steps**:
  1. Configure `scan_pdf_engine = "docling"`
  2. Process a scanned (image-only) PDF through docling_adapter
- **Expected**: Docling uses its OCR backend (RapidOCR or EasyOCR). Extracted text is returned. Works without additional model downloads beyond docling's own dependencies.
- **Priority**: P1

### TC-009: Disk space warning before download (P1)
- **Steps**:
  1. Check available disk space before triggering docling model download
  2. If space < 3GB, show warning to user
- **Expected**: User is warned before download begins if disk space is low. Option to cancel or proceed anyway.
- **Priority**: P1

---

## Regression Check
- [ ] Docling model download does not interfere with other backends (markitdown, PP-OCR)
- [ ] Model cache directory is configurable and respected
- [ ] Offline mode works without any network requests
