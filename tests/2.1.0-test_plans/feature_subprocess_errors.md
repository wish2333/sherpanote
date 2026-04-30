# Test Plan: Subprocess Error Recovery

## Scope
`py/plugins/runner.py` (`run_with_json`, `run_with_progress`), `py/document_extractor.py`

## Prerequisites
- Plugin venv exists with at least one backend installed
- Test scripts/fixtures that simulate various failure modes
- Alternatively: mock the subprocess to avoid needing actual plugin backends

---

## Test Cases

### TC-001: Subprocess timeout (P0)
- **Steps**:
  1. Create a test runner script that sleeps for 300 seconds
  2. Call `Runner.run_with_json(..., timeout=2)` (2 second timeout)
- **Expected**: Raises `PluginError` with "timed out" or "timeout" in message. Subprocess is killed. No zombie process.
- **Priority**: P0

### TC-002: Process crash (non-zero exit) (P0)
- **Steps**:
  1. Create a test runner that calls `sys.exit(1)`
  2. Call `Runner.run_with_json(...)`
- **Expected**: Raises `PluginError` with non-zero return code information. Error message includes the exit code.
- **Priority**: P0

### TC-003: Invalid JSON output (P0)
- **Steps**:
  1. Create a test runner that prints `"not json"` to stdout
  2. Call `Runner.run_with_json(...)`
- **Expected**: Raises `PluginError` with "not valid JSON" or "JSON decode" in message. The invalid output text is logged for debugging.
- **Priority**: P0

### TC-004: Empty output (no stdout) (P0)
- **Steps**:
  1. Create a test runner that exits immediately without writing to stdout
  2. Call `Runner.run_with_json(...)`
- **Expected**: Raises `PluginError` with "no output" or "empty" in message.
- **Priority**: P0

### TC-005: Error result JSON (P0)
- **Steps**:
  1. Create a test runner that outputs `{"success": false, "error": "simulated failure", "traceback": "..."}`
  2. Call `Runner.run_with_json(...)`
- **Expected**: Raises `PluginError` with message "simulated failure". The traceback is logged if present.
- **Priority**: P0

### TC-006: Missing venv Python (P1)
- **Steps**:
  1. Delete or rename the venv Python executable
  2. Call `Runner.run_with_json(venv_python=".../nonexistent/python", ...)`
- **Expected**: Raises `FileNotFoundError` or `PluginError` with clear message about missing Python. No crash.
- **Priority**: P1

### TC-007: Progress streaming during error (P1)
- **Steps**:
  1. Create a test runner that emits progress lines then an error result
  2. Call `Runner.run_with_progress(...)`
- **Expected**: Progress callback receives the emitted lines. Final result is `PluginError` for the error.
- **Priority**: P1

### TC-008: Binary/stderr garbled data (P2)
- **Steps**:
  1. Create a test runner that outputs binary data (e.g., raw bytes, BOM characters) on stdout or stderr
  2. Call `Runner.run_with_json(...)`
- **Expected**: Handled gracefully with `errors="replace"` encoding. No UnicodeDecodeError crash.
- **Priority**: P2

### TC-009: Recovery chain -- fallback after crash (P0)
- **Steps**:
  1. Configure `DocumentConfig.text_pdf_engine = "docling"`
  2. Mock docling runner to always crash
  3. Call `DocumentExtractor.extract("sample_text.pdf")`
- **Expected**: Extraction falls back to markitdown -> PP-OCR chain. Produces a valid `ExtractedDocument`. Warning logged about docling failure.
- **Priority**: P0

### TC-010: Concurrent subprocess calls (P2)
- **Steps**:
  1. Start two subprocess calls simultaneously (e.g., two docling extractions)
- **Expected**: Both complete successfully without interfering. No shared state corruption.
- **Priority**: P2

### TC-011: Large output handling (P2)
- **Steps**:
  1. Process a PDF that produces >10MB of extraction output
  2. Verify the JSON is fully received and parsed
- **Expected**: Full output is captured. No truncation. `ExtractedDocument` contains complete content.
- **Priority**: P2

---

## Regression Check
- [ ] Subprocess is always killed/cleaned up, no zombie processes
- [ ] Timeout mechanism works (not infinite hang)
- [ ] All error paths produce user-friendly messages in main.py `@expose` methods
- [ ] stderr from subprocess is captured and logged
