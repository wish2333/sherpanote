"""Unified document output model.

All document extraction backends (PP-OCR, markitdown, etc.)
produce an ExtractedDocument instance. Downstream code
(record creation, frontend display) only consumes this type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py.ocr import OcrResult


@dataclass(frozen=True)
class ImageRef:
    """Reference to an embedded image extracted from a document."""

    index: int
    alt_text: str
    mime_type: str  # "image/png", "image/jpeg", etc.


@dataclass(frozen=True)
class TableInfo:
    """Structured table data extracted from a document."""

    markdown: str  # Table content in markdown format


@dataclass(frozen=True)
class ExtractedDocument:
    """Unified output from any document extraction backend.

    Downstream code (main.py record creation, frontend) only
    consumes this type, never raw backend output.
    """

    markdown: str  # Primary text content in GFM
    metadata: dict[str, str]  # page_count, title, author, etc.
    tables: tuple[TableInfo, ...] = ()  # Structured table data
    images: tuple[ImageRef, ...] = ()  # Embedded image references
    raw_format: str = ""  # Original format identifier
    backend: str = ""  # Backend name: "ppocr", "markitdown"
    source_path: str = ""  # Original file path


def ocr_results_to_document(
    results: list[OcrResult],
    source_path: str,
    page_count: int = 1,
) -> ExtractedDocument:
    """Convert a list of OcrResult into ExtractedDocument.

    Bridges the existing OcrResult type to the new unified type.
    """
    text_blocks = [r.text for r in results if r.text.strip()]
    markdown = "\n".join(text_blocks)
    return ExtractedDocument(
        markdown=markdown,
        metadata={
            "page_count": str(page_count),
            "block_count": str(len(text_blocks)),
        },
        tables=(),
        images=(),
        raw_format="ppocr",
        backend="ppocr",
        source_path=source_path,
    )
