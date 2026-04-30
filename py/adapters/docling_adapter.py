"""Adapter for docling: converts PDF to ExtractedDocument via plugin subprocess.

docling provides advanced PDF parsing with layout recognition and
optional OCR for scanned documents. Runs in plugin venv subprocess.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from py.outputs.unified_document import (
    ExtractedDocument,
    ImageRef,
    TableInfo,
)

if TYPE_CHECKING:
    from py.plugins.manager import PluginManager
    from py.plugins.runner import RunResult

logger = logging.getLogger(__name__)

_RUNNER_MODULE = "py.plugins.runners.docling_runner"


class DoclingAdapter:
    """Wraps docling backend via subprocess to produce ExtractedDocument."""

    def __init__(
        self,
        plugin_manager: PluginManager,
        artifacts_path: str | None = None,
    ) -> None:
        self._manager = plugin_manager
        self._artifacts_path = artifacts_path

    def is_available(self) -> bool:
        """Check if docling is installed in the plugin venv."""
        return self._manager.is_package_installed("docling")

    def extract_text_pdf(self, file_path: str) -> ExtractedDocument:
        """Extract text from a text-layer PDF using docling."""
        return self._run_extract(file_path, method="text_layer")

    def extract_ocr_pdf(self, file_path: str) -> ExtractedDocument:
        """Extract text from a scanned PDF using docling OCR mode."""
        return self._run_extract(file_path, method="ocr")

    def pre_download_models(self) -> dict:
        """Trigger docling model pre-download via subprocess.

        Models are downloaded to artifacts_path if configured and exists,
        otherwise to the default HuggingFace cache.

        Returns:
            {"success": True, "message": str} or {"success": False, "error": str}
        """
        from py.plugins.runner import run

        logger.info("Docling model pre-download requested")

        result = run(
            plugin_module=_RUNNER_MODULE,
            args={
                "command": "pre_download",
                "artifacts_path": self._artifacts_path,
            },
            timeout=1800,
        )

        return {"success": True, "message": result.data.get("message", "Done")}

    def _run_extract(self, file_path: str, method: str) -> ExtractedDocument:
        """Execute docling runner subprocess and parse result."""
        from py.plugins.runner import run

        logger.info("Docling extraction (%s): %s", method, file_path)

        result = run(
            plugin_module=_RUNNER_MODULE,
            args={
                "file_path": file_path,
                "method": method,
                "artifacts_path": self._artifacts_path,
            },
            timeout=600,
        )

        return _parse_result(result)


def _parse_result(result: "RunResult") -> ExtractedDocument:
    """Convert RunResult data dict to ExtractedDocument."""
    data = result.data
    if data is None:
        return ExtractedDocument(
            markdown="",
            metadata={"error": "No data returned"},
            raw_format="docling",
            backend="docling",
        )

    # Parse tables
    tables = tuple(
        TableInfo(markdown=t.get("markdown", ""))
        for t in data.get("tables", [])
    )

    # Parse images
    images = tuple(
        ImageRef(
            index=img.get("index", 0),
            alt_text=img.get("alt_text", ""),
            mime_type=img.get("mime_type", "image/png"),
        )
        for img in data.get("images", [])
    )

    return ExtractedDocument(
        markdown=data.get("markdown") or "",
        metadata=data.get("metadata", {}),
        tables=tables,
        images=images,
        raw_format=data.get("raw_format", "docling"),
        backend=data.get("backend", "docling"),
        source_path=data.get("source_path", ""),
    )
