"""Document extraction decision tree.

Routes input files to the appropriate backend based on file type
and content analysis (text layer detection for PDFs).

Decision tree:
    Image -> PpocrAdapter
    Office (DOCX/PPTX/XLSX) -> MarkitdownAdapter
    PDF:
        has_text_layer?
            Yes -> MarkitdownAdapter (fallback to PP-OCR on failure)
            No  -> PpocrAdapter (PDF->image->OCR)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from py.outputs.unified_document import ExtractedDocument
from py.text_detector import FileTypeInfo, classify_file, has_text_layer

if TYPE_CHECKING:
    from py.ocr import OcrEngine

logger = logging.getLogger(__name__)


class DocumentExtractor:
    """Main entry point for document extraction.

    Usage:
        extractor = DocumentExtractor(ocr_engine=engine)
        doc = extractor.extract("report.pdf")
        print(doc.markdown)
    """

    def __init__(self, ocr_engine: OcrEngine) -> None:
        self._ocr_engine = ocr_engine
        self._ppocr_adapter = None
        self._markitdown_adapter = None

    def _get_ppocr_adapter(self):
        from py.adapters.ppocr_adapter import PpocrAdapter
        if self._ppocr_adapter is None:
            self._ppocr_adapter = PpocrAdapter(self._ocr_engine)
        return self._ppocr_adapter

    def _get_markitdown_adapter(self):
        from py.adapters.markitdown_adapter import MarkitdownAdapter
        if self._markitdown_adapter is None:
            self._markitdown_adapter = MarkitdownAdapter()
        return self._markitdown_adapter

    def classify(self, file_path: str) -> FileTypeInfo:
        """Classify a file without processing it."""
        return classify_file(file_path)

    def extract(
        self,
        file_path: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ExtractedDocument:
        """Extract text from a file using the decision tree.

        Args:
            file_path: Path to the input file.
            on_progress: Optional callback(current, total).

        Returns:
            ExtractedDocument with the extracted content.
        """
        info = classify_file(file_path)

        if info.category == "image":
            logger.info("Image detected: %s -> PP-OCR", file_path)
            return self._get_ppocr_adapter().extract_image(file_path)

        if info.category == "office":
            logger.info("Office doc detected: %s -> markitdown", file_path)
            return self._get_markitdown_adapter().convert(file_path)

        if info.category == "pdf":
            return self._extract_pdf(file_path, on_progress)

        raise ValueError(f"Unsupported file type: {file_path}")

    def _extract_pdf(
        self,
        pdf_path: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ExtractedDocument:
        """Extract text from a PDF with text layer detection."""
        logger.info("PDF detected: %s, checking text layer...", pdf_path)

        if has_text_layer(pdf_path):
            logger.info("Text layer found: %s -> markitdown", pdf_path)
            try:
                return self._get_markitdown_adapter().convert(pdf_path)
            except Exception as exc:
                logger.warning(
                    "markitdown failed for %s, falling back to PP-OCR: %s",
                    pdf_path, exc,
                )

        logger.info("No text layer (or markitdown failed): %s -> PP-OCR", pdf_path)
        return self._get_ppocr_adapter().extract_pdf_as_images(
            pdf_path, on_progress=on_progress,
        )

    def extract_batch(
        self,
        file_paths: list[str],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[ExtractedDocument]:
        """Extract from multiple files, each producing one document."""
        results: list[ExtractedDocument] = []
        total = len(file_paths)
        for i, path in enumerate(file_paths):
            if on_progress:
                on_progress(i, total)
            try:
                doc = self.extract(path)
                results.append(doc)
            except Exception as exc:
                logger.warning("Extraction failed for %s: %s", path, exc)
                results.append(ExtractedDocument(
                    markdown="",
                    metadata={"error": str(exc)},
                    tables=(), images=(),
                    raw_format="error", backend="none",
                    source_path=path,
                ))
        if on_progress:
            on_progress(total, total)
        return results
