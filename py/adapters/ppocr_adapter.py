"""Adapter that wraps OcrEngine (RapidOCR/PP-OCR) into the ExtractedDocument interface."""

from __future__ import annotations

import logging
import tempfile
from typing import TYPE_CHECKING, Callable

from py.outputs.unified_document import ExtractedDocument, ocr_results_to_document

if TYPE_CHECKING:
    from py.ocr import OcrEngine

logger = logging.getLogger(__name__)


class PpocrAdapter:
    """Wraps OcrEngine to produce ExtractedDocument output."""

    def __init__(self, engine: OcrEngine) -> None:
        self._engine = engine

    def extract_image(self, image_path: str) -> ExtractedDocument:
        """OCR a single image file."""
        results = self._engine.process_image(image_path)
        return ocr_results_to_document(results, image_path, page_count=1)

    def extract_pdf_as_images(
        self,
        pdf_path: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ExtractedDocument:
        """Convert PDF to images and OCR all pages, returning combined document."""
        self._engine.initialize()
        with tempfile.TemporaryDirectory(prefix="sherpanote_ocr_") as tmp:
            pages = self._engine.pdf_to_images(pdf_path, output_dir=tmp)
            results = self._engine.process_images_sequential(
                pages, on_progress=on_progress,
            )
        return ocr_results_to_document(results, pdf_path, page_count=len(pages))

    def extract_images_batch(
        self,
        image_paths: list[str],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[ExtractedDocument]:
        """Process multiple images, each producing a separate document."""
        all_results = self._engine.process_images_batch(
            image_paths, on_progress=on_progress,
        )
        return [
            ocr_results_to_document(r, p, page_count=1)
            for r, p in zip(all_results, image_paths)
        ]
