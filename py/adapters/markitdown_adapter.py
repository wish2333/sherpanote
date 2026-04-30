"""Adapter for markitdown: converts PDF/Office docs to ExtractedDocument.

markitdown handles:
- Text-layer PDFs (via pdfplumber/pdfminer)
- DOCX (via mammoth)
- PPTX (via python-pptx)
- XLSX (via openpyxl)
"""

from __future__ import annotations

import logging
from pathlib import Path

from py.outputs.unified_document import ExtractedDocument

logger = logging.getLogger(__name__)


class MarkitdownAdapter:
    """Wraps markitdown to produce ExtractedDocument output."""

    def __init__(self) -> None:
        self._md = None  # Lazy init

    def _get_markitdown(self):
        """Lazy import and instantiation of MarkItDown."""
        if self._md is None:
            from markitdown import MarkItDown
            self._md = MarkItDown()
        return self._md

    def convert(self, file_path: str) -> ExtractedDocument:
        """Convert a file (PDF, DOCX, PPTX, XLSX) to ExtractedDocument."""
        md = self._get_markitdown()
        logger.info("Converting with markitdown: %s", file_path)

        # Suppress verbose pdfminer debug logging for PDF processing
        logging.getLogger("pdfminer").setLevel(logging.WARNING)

        result = md.convert(file_path)

        # Determine page count for PDFs
        page_count = "1"
        if Path(file_path).suffix.lower() == ".pdf":
            page_count = self._count_pdf_pages(file_path)

        metadata: dict[str, str] = {
            "page_count": page_count,
        }
        if hasattr(result, "title") and result.title:
            metadata["title"] = result.title

        return ExtractedDocument(
            markdown=result.markdown,
            metadata=metadata,
            tables=(),
            images=(),
            raw_format="markdown",
            backend="markitdown",
            source_path=file_path,
        )

    @staticmethod
    def _count_pdf_pages(pdf_path: str) -> str:
        """Count pages in a PDF using pdfplumber. Returns "1" on failure."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                return str(len(pdf.pages))
        except Exception as exc:
            logger.debug("Could not count PDF pages: %s: %s", pdf_path, exc)
            return "1"
