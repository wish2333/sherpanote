"""CLI wrapper for opendataloader-pdf document extraction.

Run via: python -m py.plugins.runners.opendata_runner --json-input <base64>

Input JSON:
    {"file_path": "..."}

Output JSON (stdout):
    {"success": true, "result": {ExtractedDocument fields}}
    {"success": false, "error": "...", "traceback": "..."}
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_opendataloader(file_path: str) -> dict:
    """Call opendataloader-pdf to extract document content.

    Args:
        file_path: Path to the input PDF.

    Returns:
        Dict matching ExtractedDocument fields.
    """
    from opendataloader_pdf import convert

    _emit_progress(0, f"Converting {file_path} with opendataloader-pdf")

    # opendataloader-pdf returns markdown text
    markdown = convert(file_path)

    _emit_progress(80, "Building output")

    # Count pages using pdfplumber (available via markitdown deps)
    page_count = "1"
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            page_count = str(len(pdf.pages))
    except Exception:
        pass

    _emit_progress(100, "Done")

    return {
        "markdown": markdown,
        "metadata": {
            "page_count": page_count,
        },
        "tables": [],
        "images": [],
        "raw_format": "opendataloader",
        "backend": "opendataloader",
        "source_path": str(file_path),
    }


def _emit_progress(percent: int, message: str) -> None:
    """Emit progress event to stderr as JSON line."""
    event = json.dumps({"type": "progress", "percent": percent, "message": message})
    print(event, file=sys.stderr, flush=True)


def main() -> None:
    """CLI entry point."""
    if "--json-input" not in sys.argv:
        _fail("Usage: opendata_runner --json-input <base64_json>")
        return

    idx = sys.argv.index("--json-input")
    if idx + 1 >= len(sys.argv):
        _fail("Missing --json-input argument")
        return

    try:
        encoded = sys.argv[idx + 1]
        args = json.loads(base64.b64decode(encoded).decode())
    except Exception as exc:
        _fail(f"Invalid --json-input: {exc}")
        return

    file_path = args.get("file_path", "")

    if not file_path:
        _fail("Missing 'file_path' in input")
        return

    if not Path(file_path).exists():
        _fail(f"File not found: {file_path}")
        return

    try:
        result = _run_opendataloader(file_path)
        json.dump({"success": True, "result": result}, sys.stdout)
        print()
    except Exception as exc:
        import traceback
        _fail(str(exc), traceback.format_exc())


def _fail(message: str, tb: str = "") -> None:
    """Write failure JSON to stdout."""
    json.dump({"success": False, "error": message, "traceback": tb}, sys.stdout)
    print()


if __name__ == "__main__":
    main()
