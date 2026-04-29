"""Adapter for docling: converts PDF to ExtractedDocument via plugin subprocess.

docling provides advanced PDF parsing with layout recognition and
optional OCR for scanned documents. Runs in plugin venv subprocess.
"""

from __future__ import annotations

import logging
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
    ) -> None:
        self._manager = plugin_manager

    def is_available(self) -> bool:
        """Check if docling is installed in the plugin venv."""
        return self._manager.is_package_installed("docling")

    def extract_text_pdf(self, file_path: str) -> ExtractedDocument:
        """Extract text from a text-layer PDF using docling.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ExtractedDocument with extracted content.

        Raises:
            PluginError: If docling subprocess fails.
        """
        return self._run_extract(file_path, method="text_layer")

    def extract_ocr_pdf(self, file_path: str) -> ExtractedDocument:
        """Extract text from a scanned PDF using docling OCR mode.

        Args:
            file_path: Path to the scanned PDF file.

        Returns:
            ExtractedDocument with OCR-extracted content.

        Raises:
            PluginError: If docling subprocess fails.
        """
        return self._run_extract(file_path, method="ocr")

    def _run_extract(self, file_path: str, method: str) -> ExtractedDocument:
        """Execute docling runner subprocess and parse result."""
        from py.plugins.runner import run

        logger.info("Docling extraction (%s): %s", method, file_path)

        result = run(
            plugin_module=_RUNNER_MODULE,
            args={"file_path": file_path, "method": method},
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
        markdown=data.get("markdown", ""),
        metadata=data.get("metadata", {}),
        tables=tables,
        images=images,
        raw_format=data.get("raw_format", "docling"),
        backend=data.get("backend", "docling"),
        source_path=data.get("source_path", ""),
    )
