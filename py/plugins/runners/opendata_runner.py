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
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_opendataloader(file_path: str, java_path: str | None = None) -> dict:
    """Call opendataloader-pdf to extract document content.

    Args:
        file_path: Path to the input PDF.

    Returns:
        Dict matching ExtractedDocument fields.
    """
    import os as _os
    import tempfile as _tempfile
    from pathlib import Path as _Path

    from opendataloader_pdf import run_jar

    _emit_progress(0, f"Converting {file_path} with opendataloader-pdf")

    # Use system temp dir — relative paths like "data/temp" resolve
    # unpredictably in packaged apps (macOS Finder sets cwd to /).
    tmpdir = str(_Path(_tempfile.gettempdir()) / "sherpanote_opendata")
    _os.makedirs(tmpdir, exist_ok=True)

    # Clean up previous output with same stem name
    stem = _Path(file_path).stem
    for old in _Path(tmpdir).glob(f"{stem}.*"):
        try:
            old.unlink()
        except OSError:
            pass

    args = [file_path, "--output-dir", tmpdir, "--format", "markdown", "--quiet"]
    try:
        run_jar(args, quiet=True)
    except FileNotFoundError:
        raise RuntimeError(
            "Java not found. opendataloader-pdf requires Java 11+. "
            "Install from https://adoptium.net/ or set java.exe path in settings."
        )
    except Exception as exc:
        msg = str(exc)
        if "UnsupportedClassVersionError" in msg:
            raise RuntimeError(
                "opendataloader-pdf requires Java 11 or newer. "
                "Your Java version is too old. Please install Java 11+ from https://adoptium.net/"
            ) from exc
        raise RuntimeError(msg) from exc

    # Read the generated markdown file
    output_files: list[_Path] = []
    md_files = sorted(_Path(tmpdir).glob(f"{stem}*.md"))
    if md_files:
        markdown = md_files[0].read_text(encoding="utf-8")
        output_files.append(md_files[0])
    else:
        # Fallback: try JSON
        json_files = sorted(_Path(tmpdir).glob(f"{stem}*.json"))
        if json_files:
            import json as _json
            data = _json.loads(json_files[0].read_text(encoding="utf-8"))
            kids = data.get("kids", [])
            markdown = "\n".join(k.get("content", "") for k in kids if k.get("content"))
            output_files.append(json_files[0])
        else:
            raise RuntimeError("opendataloader-pdf produced no output files")

    # Clean up temp files after reading
    for f in output_files:
        try:
            f.unlink()
        except OSError:
            pass

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
    java_path = args.get("java_path")

    if not file_path:
        _fail("Missing 'file_path' in input")
        return

    if not Path(file_path).exists():
        _fail(f"File not found: {file_path}")
        return

    # Set JAVA_HOME if a specific Java path was provided
    if java_path:
        import os as _os
        java_bin = str(Path(java_path).parent)
        _os.environ["JAVA_HOME"] = str(Path(java_bin).parent)
        _os.environ["PATH"] = java_bin + _os.pathsep + _os.environ.get("PATH", "")

    try:
        result = _run_opendataloader(file_path, java_path)
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
