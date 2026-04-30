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


def _setup_hf_home(artifacts_path: str | None, hf_endpoint: str | None = None) -> str:
    """Set HF_HOME to redirect model cache to artifacts_path."""
    import os as _os
    target = str(Path(artifacts_path or "data/docling").resolve())
    _os.makedirs(target, exist_ok=True)
    _os.environ["HF_HOME"] = target
    if hf_endpoint:
        _os.environ["HF_ENDPOINT"] = hf_endpoint
    return target


def _run_docling(file_path: str, method: str, artifacts_path: str | None = None, hf_endpoint: str | None = None) -> dict:
    """Call docling to extract document content.

    Args:
        file_path: Path to the input document.
        method: "text_layer" for text PDFs, "ocr" for scanned PDFs.
        artifacts_path: Optional model cache root (sets HF_HOME).
        hf_endpoint: Optional HuggingFace mirror endpoint.

    Returns:
        Dict matching ExtractedDocument fields.
    """
    _setup_hf_home(artifacts_path, hf_endpoint)

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = (method == "ocr")

    if method == "ocr":
        from docling.datamodel.pipeline_options import RapidOcrOptions
        pipeline_options.ocr_options = RapidOcrOptions(
            lang=["english", "chinese"],
        )

    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
    }

    converter = DocumentConverter(format_options=format_options)

    # Log progress to stderr
    _emit_progress(0, f"Converting {file_path} with docling ({method})")

    result = converter.convert(file_path)

    _emit_progress(80, "Building output")

    # Extract markdown content
    doc = result.document
    markdown = doc.export_to_markdown() if doc else ""

    # Build metadata
    page_count = "1"
    if doc and doc.num_pages:
        page_count = str(doc.num_pages)

    metadata: dict[str, str] = {"page_count": page_count}

    # Extract title from document name if available
    if doc and hasattr(doc, "name") and doc.name:
        metadata["title"] = doc.name

    _emit_progress(100, "Done")

    return {
        "markdown": markdown,
        "metadata": metadata,
        "tables": [],
        "images": [],
        "raw_format": "docling",
        "backend": "docling",
        "source_path": str(file_path),
    }


def _pre_download_models(artifacts_path: str | None = None, hf_endpoint: str | None = None) -> dict:
    """Pre-download docling models by triggering a conversion.

    HF_HOME is redirected to artifacts_path, so docling downloads
    models there via huggingface_hub on first use.
    """
    import tempfile as _tf
    import os as _os

    target = _setup_hf_home(artifacts_path, hf_endpoint)
    _emit_progress(0, f"Model directory: {target}")

    minimal_pdf = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )
    tmp_path = None
    try:
        fd, tmp_path = _tf.mkstemp(suffix=".pdf")
        _os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(minimal_pdf)
        _emit_progress(10, "Downloading docling models...")
        _run_docling(tmp_path, "text_layer", artifacts_path, hf_endpoint)
        _emit_progress(100, f"Models ready in {target}")
    finally:
        if tmp_path:
            try: _os.unlink(tmp_path)
            except OSError: pass

    return {"message": f"Models downloaded to {target}"}


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

    command = args.get("command", "extract")
    artifacts_path = args.get("artifacts_path")
    hf_endpoint = args.get("hf_endpoint")

    # Route to command handler
    if command == "pre_download":
        try:
            result = _pre_download_models(artifacts_path, hf_endpoint)
            json.dump({"success": True, "result": result}, sys.stdout)
            print()
        except Exception as exc:
            import traceback
            _fail(str(exc), traceback.format_exc())
        return

    # Default: extract
    file_path = args.get("file_path", "")
    method = args.get("method", "text_layer")

    if not file_path:
        _fail("Missing 'file_path' in input")
        return

    if not Path(file_path).exists():
        _fail(f"File not found: {file_path}")
        return

    try:
        result = _run_docling(file_path, method, artifacts_path, hf_endpoint)
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
