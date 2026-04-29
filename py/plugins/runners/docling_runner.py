"""CLI wrapper for docling document extraction.

Run via: python -m py.plugins.runners.docling_runner --json-input <base64>

Input JSON:
    {"file_path": "...", "method": "text_layer" | "ocr"}

Output JSON (stdout):
    {"success": true, "result": {ExtractedDocument fields}}
    {"success": false, "error": "...", "traceback": "..."}

Progress (stderr):
    {"type": "progress", "percent": 50, "message": "..."}
"""

from __future__ import annotations

import base64
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_docling(file_path: str, method: str) -> dict:
    """Call docling to extract document content.

    Args:
        file_path: Path to the input document.
        method: "text_layer" for text PDFs, "ocr" for scanned PDFs.

    Returns:
        Dict matching ExtractedDocument fields.
    """
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.backend.pdf_backend import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat

    # Configure pipeline based on method
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = (method == "ocr")

    if method == "ocr":
        pipeline_options.ocr_engine = "rapidocr_onnx"

    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
    }

    converter = DocumentConverter(format_options=format_options)

    # Log progress to stderr
    _emit_progress(0, f"Converting {file_path} with docling ({method})")

    result = converter.convert(file_path)

    _emit_progress(80, "Building output")

    # Extract content
    markdown = result.document.export_to_markdown()

    # Build metadata
    metadata: dict[str, str] = {
        "page_count": "1",
    }
    if result.document and hasattr(result.document, "name"):
        metadata["title"] = result.document.name
    if result.pages:
        metadata["page_count"] = str(len(result.pages))

    # Extract tables if available
    tables = []
    if result.document and hasattr(result.document, "tables"):
        for table in result.document.tables:
            tables.append({
                "markdown": getattr(table, "export_to_markdown", lambda: str(table.data))(),
            })

    # Extract images if available
    images = []
    img_idx = 0
    if result.document and hasattr(result.document, "pictures"):
        for pic in result.document.pictures:
            images.append({
                "index": img_idx,
                "alt_text": getattr(pic, "caption", ""),
                "mime_type": "image/png",
            })
            img_idx += 1

    _emit_progress(100, "Done")

    return {
        "markdown": markdown,
        "metadata": metadata,
        "tables": tables,
        "images": images,
        "raw_format": "docling",
        "backend": "docling",
        "source_path": str(file_path),
    }


def _emit_progress(percent: int, message: str) -> None:
    """Emit progress event to stderr as JSON line."""
    event = json.dumps({"type": "progress", "percent": percent, "message": message})
    print(event, file=sys.stderr, flush=True)


def main() -> None:
    """CLI entry point."""
    if "--json-input" not in sys.argv:
        _fail("Usage: docling_runner --json-input <base64_json>")
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
    method = args.get("method", "text_layer")

    if not file_path:
        _fail("Missing 'file_path' in input")
        return

    if not Path(file_path).exists():
        _fail(f"File not found: {file_path}")
        return

    try:
        result = _run_docling(file_path, method)
        json.dump({"success": True, "result": result}, sys.stdout)
        print()  # trailing newline
    except Exception as exc:
        import traceback
        _fail(str(exc), traceback.format_exc())


def _fail(message: str, tb: str = "") -> None:
    """Write failure JSON to stdout."""
    json.dump({"success": False, "error": message, "traceback": tb}, sys.stdout)
    print()


if __name__ == "__main__":
    main()
