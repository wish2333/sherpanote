"""Document extraction decision tree.

Routes input files to the appropriate backend based on file type,
content analysis (text layer detection for PDFs), and user preferences.

Decision tree:
    Image -> PpocrAdapter
    Office (DOCX/PPTX/XLSX) -> MarkitdownAdapter
    PDF:
        has_text_layer?
            Yes -> configured text_pdf_engine (markitdown/opendataloader/docling/ppocr)
            No  -> configured scan_pdf_engine (ppocr/docling)
        Fallback: markitdown -> PP-OCR
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from py.outputs.unified_document import ExtractedDocument
from py.text_detector import FileTypeInfo, classify_file, has_text_layer

if TYPE_CHECKING:
    from py.config import DocumentConfig, PluginConfig
    from py.ocr import OcrEngine
    from py.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class DocumentExtractor:
    """Main entry point for document extraction.

    Usage:
        extractor = DocumentExtractor(ocr_engine=engine)
        doc = extractor.extract("report.pdf")
        print(doc.markdown)

    Optional plugin backends:
        extractor = DocumentExtractor(
            ocr_engine=engine,
            plugin_manager=manager,
            doc_config=config.document,
        )
    """

    def __init__(
        self,
        ocr_engine: OcrEngine,
        plugin_manager: PluginManager | None = None,
        doc_config: DocumentConfig | None = None,
        plugin_config: PluginConfig | None = None,
    ) -> None:
        self._ocr_engine = ocr_engine
        self._plugin_manager = plugin_manager
        self._doc_config = doc_config
        self._plugin_config = plugin_config

        # Built-in adapters (always available)
        self._ppocr_adapter = None
        self._markitdown_adapter = None

        # Plugin adapters (lazy init, may be unavailable)
        self._docling_adapter = None
        self._opendata_adapter = None

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

    def _get_docling_adapter(self):
        from py.adapters.docling_adapter import DoclingAdapter
        if self._docling_adapter is None and self._plugin_manager is not None:
            artifacts = "data/docling"
            if self._plugin_config and self._plugin_config.docling_artifacts_path:
                artifacts = self._plugin_config.docling_artifacts_path
            self._docling_adapter = DoclingAdapter(self._plugin_manager, artifacts_path=artifacts)
        return self._docling_adapter

    def _get_opendata_adapter(self):
        from py.adapters.opendata_adapter import OpendataAdapter
        if self._opendata_adapter is None and self._plugin_manager is not None:
            java_path = self._plugin_config.manual_java_path if self._plugin_config else None
            self._opendata_adapter = OpendataAdapter(self._plugin_manager, manual_java_path=java_path)
        return self._opendata_adapter

    def classify(self, file_path: str) -> FileTypeInfo:
        """Classify a file without processing it."""
        return classify_file(file_path)

    def get_available_backends(self) -> dict[str, bool]:
        """Return availability status of all backends.

        Returns:
            {"ppocr": True, "markitdown": True, "docling": bool, "opendataloader": bool}
        """
        result = {
            "ppocr": True,
            "markitdown": True,
            "docling": False,
            "opendataloader": False,
        }

        docling = self._get_docling_adapter()
        if docling is not None:
            result["docling"] = docling.is_available()

        opendata = self._get_opendata_adapter()
        if opendata is not None:
            result["opendataloader"] = opendata.is_available()

        return result

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

    def _get_text_pdf_engine(self) -> str:
        """Get configured text-layer PDF engine name."""
        if self._doc_config is not None:
            return self._doc_config.text_pdf_engine
        return "markitdown"

    def _get_scan_pdf_engine(self) -> str:
        """Get configured scanned PDF engine name."""
        if self._doc_config is not None:
            return self._doc_config.scan_pdf_engine
        return "ppocr"

    def _extract_pdf(
        self,
        pdf_path: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ExtractedDocument:
        """Extract text from a PDF with text layer detection."""
        logger.info("PDF detected: %s, checking text layer...", pdf_path)
        has_text = has_text_layer(pdf_path)

        if has_text:
            return self._extract_text_pdf(pdf_path)
        else:
            return self._extract_scan_pdf(pdf_path, on_progress)

    def _extract_text_pdf(self, pdf_path: str) -> ExtractedDocument:
        """Extract from a text-layer PDF using configured engine."""
        engine = self._get_text_pdf_engine()

        if engine == "docling":
            doc = self._try_docling_text(pdf_path)
            if doc is not None:
                return doc
            logger.warning("docling unavailable/failed for %s, falling back", pdf_path)

        if engine == "opendataloader":
            doc = self._try_opendata(pdf_path)
            if doc is not None:
                return doc
            logger.warning("opendataloader unavailable/failed for %s, falling back", pdf_path)

        if engine == "ppocr":
            return self._get_ppocr_adapter().extract_pdf_as_images(pdf_path)

        # Default: markitdown
        logger.info("Text layer found: %s -> markitdown", pdf_path)
        try:
            return self._get_markitdown_adapter().convert(pdf_path)
        except Exception as exc:
            logger.warning(
                "markitdown failed for %s, falling back to PP-OCR: %s",
                pdf_path, exc,
            )
        return self._get_ppocr_adapter().extract_pdf_as_images(pdf_path)

    def _extract_scan_pdf(
        self,
        pdf_path: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ExtractedDocument:
        """Extract from a scanned PDF using configured engine."""
        engine = self._get_scan_pdf_engine()

        if engine == "docling":
            doc = self._try_docling_ocr(pdf_path)
            if doc is not None:
                return doc
            logger.warning("docling OCR unavailable/failed for %s, falling back to PP-OCR", pdf_path)

        # Default: PP-OCR
        logger.info("No text layer (or fallback): %s -> PP-OCR", pdf_path)
        return self._get_ppocr_adapter().extract_pdf_as_images(
            pdf_path, on_progress=on_progress,
        )

    def _try_docling_text(self, pdf_path: str) -> ExtractedDocument | None:
        """Try docling for text-layer PDF. Returns None if unavailable."""
        adapter = self._get_docling_adapter()
        if adapter is None or not adapter.is_available():
            return None
        try:
            logger.info("Text layer PDF: %s -> docling (text mode)", pdf_path)
            return adapter.extract_text_pdf(pdf_path)
        except Exception as exc:
            logger.warning("docling text extraction failed: %s", exc)
            return None

    def _try_docling_ocr(self, pdf_path: str) -> ExtractedDocument | None:
        """Try docling for scanned PDF. Returns None if unavailable."""
        adapter = self._get_docling_adapter()
        if adapter is None or not adapter.is_available():
            return None
        try:
            logger.info("Scan PDF: %s -> docling (OCR mode)", pdf_path)
            return adapter.extract_ocr_pdf(pdf_path)
        except Exception as exc:
            logger.warning("docling OCR extraction failed: %s", exc)
            return None

    def _try_opendata(self, pdf_path: str) -> ExtractedDocument | None:
        """Try opendataloader-pdf for text-layer PDF. Returns None if unavailable."""
        adapter = self._get_opendata_adapter()
        if adapter is None or not adapter.is_available():
            return None
        try:
            logger.info("Text layer PDF: %s -> opendataloader-pdf", pdf_path)
            return adapter.extract_text_pdf(pdf_path)
        except Exception as exc:
            logger.warning("opendataloader-pdf extraction failed: %s", exc)
            return None

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
