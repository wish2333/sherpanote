"""File type classification and PDF text layer detection.

Provides centralized file type classification for the document
extraction decision tree, and text layer detection for PDFs
using pdfplumber.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
})

_OFFICE_EXTENSIONS: frozenset[str] = frozenset({
    ".docx", ".pptx", ".xlsx",
})


@dataclass(frozen=True)
class FileTypeInfo:
    """Classified file type information."""

    category: str  # "image", "pdf", "office", "unknown"
    extension: str


def classify_file(file_path: str) -> FileTypeInfo:
    """Classify a file into image/pdf/office based on extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return FileTypeInfo(category="pdf", extension=ext)
    if ext in _OFFICE_EXTENSIONS:
        return FileTypeInfo(category="office", extension=ext)
    if ext in _IMAGE_EXTENSIONS:
        return FileTypeInfo(category="image", extension=ext)
    return FileTypeInfo(category="unknown", extension=ext)


def has_text_layer(
    pdf_path: str,
    max_pages: int = 3,
    char_threshold: int = 50,
) -> bool:
    """Detect whether a PDF has a text layer using pdfplumber.

    Opens the first ``max_pages`` pages, extracts text from each,
    and accumulates non-whitespace character count. Returns True if
    the total exceeds ``char_threshold``.

    Falls back to False (no text layer) if pdfplumber fails to open.
    """
    import pdfplumber

    # Suppress verbose pdfminer debug logging
    logging.getLogger("pdfminer").setLevel(logging.WARNING)

    total_chars = 0
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_check = min(max_pages, len(pdf.pages))
            for i in range(pages_to_check):
                page = pdf.pages[i]
                text = page.extract_text() or ""
                # Count non-whitespace characters
                clean = re.sub(r"\s", "", text)
                total_chars += len(clean)
                logger.debug(
                    "Text layer check page %d/%d: %d chars (total: %d)",
                    i + 1, pages_to_check, len(clean), total_chars,
                )
    except Exception as exc:
        logger.warning("pdfplumber failed to open %s: %s", pdf_path, exc)
        return False

    has_text = total_chars > char_threshold
    logger.info(
        "Text layer detection for %s: %d chars across %d pages -> %s",
        pdf_path, total_chars, min(max_pages, 3),
        "has text" if has_text else "no text",
    )
    return has_text
