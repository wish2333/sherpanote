"""RapidOCR engine wrapper and PDF-to-image converter.

Provides OcrEngine for image/PDF OCR processing using
RapidOCR with onnxruntime. Models are auto-downloaded
by RapidOCR on first use.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Mapping from (version, role, model_type) -> expected filename.
_MODEL_FILENAMES: dict[tuple[str, str, str], str] = {
    ("v4", "det", "mobile"): "ch_PP-OCRv4_det_mobile.onnx",
    ("v4", "det", "server"): "ch_PP-OCRv4_det_server.onnx",
    ("v4", "rec", "mobile"): "ch_PP-OCRv4_rec_mobile.onnx",
    ("v4", "rec", "server"): "ch_PP-OCRv4_rec_server.onnx",
    ("v4", "cls", "mobile"): "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    ("v5", "det", "mobile"): "ch_PP-OCRv5_det_mobile.onnx",
    ("v5", "det", "server"): "ch_PP-OCRv5_det_server.onnx",
    ("v5", "rec", "mobile"): "ch_PP-OCRv5_rec_mobile.onnx",
    ("v5", "rec", "server"): "ch_PP-OCRv5_rec_server.onnx",
    ("v5", "cls", "mobile"): "ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx",
    ("v5", "cls", "server"): "ch_PP-LCNet_x1_0_textline_ori_cls_server.onnx",
}

# v4 cls has no server variant.
_MODEL_CONSTRAINTS: dict[str, dict[str, list[str]]] = {
    "v4": {"det": ["mobile", "server"], "rec": ["mobile", "server"], "cls": ["mobile"]},
    "v5": {"det": ["mobile", "server"], "rec": ["mobile", "server"], "cls": ["mobile", "server"]},
}


@dataclass(frozen=True)
class OcrResult:
    """A single OCR text block with bounding box and confidence."""

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)


def get_model_root_dir() -> Path:
    """Return the directory where RapidOCR stores downloaded models.

    Dev: rapidocr/models/ inside the installed package.
    Packaged (PyInstaller): {exe_dir}/_internal/rapidocr/models/ (onedir)
                             or {exe_dir}/rapidocr/models/ (if bundled at root)
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        # PyInstaller onedir: data files go into _internal/
        internal_dir = exe_dir / "_internal"
        if internal_dir.exists():
            return internal_dir / "rapidocr" / "models"
        return exe_dir / "rapidocr" / "models"
    from rapidocr.main import root_dir as _rapidocr_root
    return _rapidocr_root / "models"


def scan_downloaded_models() -> list[dict[str, Any]]:
    """Scan the model directory and report which model files are present."""
    model_dir = get_model_root_dir()
    result: list[dict[str, Any]] = []

    for ver, roles in _MODEL_CONSTRAINTS.items():
        for role, types in roles.items():
            for mtype in types:
                key = (ver, role, mtype)
                filename = _MODEL_FILENAMES.get(key, "")
                filepath = model_dir / filename
                size_mb = 0.0
                if filepath.exists() and filepath.is_file():
                    size_mb = round(filepath.stat().st_size / (1024 * 1024), 1)
                result.append({
                    "version": ver,
                    "role": role,
                    "model_type": mtype,
                    "filename": filename,
                    "size_mb": size_mb,
                    "downloaded": filepath.exists() and filepath.is_file() and filepath.stat().st_size > 0,
                })

    return result


def delete_model_file(version: str, role: str, model_type: str) -> dict[str, Any]:
    """Delete a specific model file."""
    key = (version, role, model_type)
    filename = _MODEL_FILENAMES.get(key)
    if filename is None:
        return {"success": False, "error": f"Unknown model: {version}/{role}/{model_type}"}
    filepath = get_model_root_dir() / filename
    if not filepath.exists():
        return {"success": False, "error": f"Model file not found: {filename}"}
    filepath.unlink()
    logger.info("Deleted OCR model: %s", filename)
    return {"success": True, "version": version, "role": role, "model_type": model_type}


def download_ocr_models(
    det_model_version: str = "v5",
    det_model_type: str = "mobile",
    rec_model_version: str = "v5",
    rec_model_type: str = "mobile",
    cls_model_version: str = "v5",
    cls_model_type: str = "server",
) -> dict[str, Any]:
    """Trigger RapidOCR auto-download by instantiating with given params.

    RapidOCR will download any missing models to its model_root_dir.
    """
    from rapidocr import ModelType, OCRVersion, RapidOCR

    ver_map = {"v4": OCRVersion.PPOCRV4, "v5": OCRVersion.PPOCRV5}
    type_map = {"mobile": ModelType.MOBILE, "server": ModelType.SERVER}

    model_dir = get_model_root_dir()
    model_dir.mkdir(parents=True, exist_ok=True)

    params: dict[str, Any] = {
        "Global.model_root_dir": str(model_dir),
        "Det.ocr_version": ver_map[det_model_version],
        "Det.model_type": type_map[det_model_type],
        "Rec.ocr_version": ver_map[rec_model_version],
        "Rec.model_type": type_map[rec_model_type],
        "Cls.ocr_version": ver_map[cls_model_version],
        "Cls.model_type": type_map[cls_model_type],
    }

    try:
        logger.info(
            "Downloading OCR models: det=%s/%s rec=%s/%s cls=%s/%s",
            det_model_version, det_model_type, rec_model_version, rec_model_type,
            cls_model_version, cls_model_type,
        )
        RapidOCR(params=params)
        logger.info("OCR models ready")
        return {"success": True}
    except Exception as exc:
        logger.exception("OCR model download failed")
        return {"success": False, "error": str(exc)}


class OcrEngine:
    """Wrapper around RapidOCR with local PP-OCR models.

    Usage:
        engine = OcrEngine(model_version="v5", det_model_type="mobile")
        results = engine.process_image("photo.png")
        for r in results:
            print(r.text)
    """

    def __init__(
        self,
        det_model_version: str = "v5",
        det_model_type: str = "mobile",
        rec_model_version: str = "v5",
        rec_model_type: str = "mobile",
        cls_model_version: str = "v5",
        cls_model_type: str = "server",
    ) -> None:
        self._det_model_version = det_model_version
        self._det_model_type = det_model_type
        self._rec_model_version = rec_model_version
        self._rec_model_type = rec_model_type
        self._cls_model_version = cls_model_version
        self._cls_model_type = cls_model_type
        self._engine: Any = None

    def initialize(self) -> None:
        """Lazily create the RapidOCR instance."""
        if self._engine is not None:
            return

        from rapidocr import ModelType, OCRVersion, RapidOCR

        ver_map = {"v4": OCRVersion.PPOCRV4, "v5": OCRVersion.PPOCRV5}
        type_map = {"mobile": ModelType.MOBILE, "server": ModelType.SERVER}

        model_dir = get_model_root_dir()
        model_dir.mkdir(parents=True, exist_ok=True)

        params: dict[str, Any] = {
            "Global.model_root_dir": str(model_dir),
            "Det.ocr_version": ver_map[self._det_model_version],
            "Det.model_type": type_map[self._det_model_type],
            "Rec.ocr_version": ver_map[self._rec_model_version],
            "Rec.model_type": type_map[self._rec_model_type],
            "Cls.ocr_version": ver_map[self._cls_model_version],
            "Cls.model_type": type_map[self._cls_model_type],
        }

        logger.info(
            "Initializing RapidOCR: det=%s/%s rec=%s/%s cls=%s/%s",
            self._det_model_version, self._det_model_type,
            self._rec_model_version, self._rec_model_type,
            self._cls_model_version, self._cls_model_type,
        )

        self._engine = RapidOCR(params=params)
        logger.info("RapidOCR initialized successfully")

    def process_image(self, image_path: str) -> list[OcrResult]:
        """OCR a single image file.

        Returns a list of OcrResult with text, confidence, and bounding box.
        """
        self.initialize()
        output = self._engine(image_path)  # type: ignore[operator]
        if not output or not output.txts:
            return []
        return [
            OcrResult(
                text=text,
                confidence=float(score),
                bbox=(
                    int(box[0][0]),
                    int(box[0][1]),
                    int(box[2][0]),
                    int(box[2][1]),
                ),
            )
            for box, text, score in zip(output.boxes, output.txts, output.scores)
        ]

    def process_images_batch(
        self,
        image_paths: list[str],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[list[OcrResult]]:
        """Process multiple images independently.

        Returns a list of results per image (same order as input).
        """
        all_results: list[list[OcrResult]] = []
        total = len(image_paths)
        for i, path in enumerate(image_paths):
            if on_progress:
                on_progress(i, total)
            try:
                results = self.process_image(path)
                all_results.append(results)
            except Exception as exc:
                logger.warning("OCR failed for %s: %s", path, exc)
                all_results.append([])
        if on_progress:
            on_progress(total, total)
        return all_results

    def process_images_sequential(
        self,
        image_paths: list[str],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[OcrResult]:
        """Process multiple images and return combined results.

        All text blocks from all images are concatenated in order.
        """
        all_results: list[OcrResult] = []
        total = len(image_paths)
        for i, path in enumerate(image_paths):
            if on_progress:
                on_progress(i, total)
            try:
                results = self.process_image(path)
                all_results.extend(results)
            except Exception as exc:
                logger.warning("OCR failed for %s: %s", path, exc)
        if on_progress:
            on_progress(total, total)
        return all_results

    @staticmethod
    def is_pdf(file_path: str) -> bool:
        """Check if a file is a PDF based on extension."""
        return Path(file_path).suffix.lower() == ".pdf"

    @staticmethod
    def pdf_to_images(
        pdf_path: str,
        output_dir: str | None = None,
        dpi: int = 200,
    ) -> list[str]:
        """Convert each page of a PDF to a PNG image.

        Uses pypdfium2 for rendering. If output_dir is not provided,
        a temporary directory is created.

        Returns a list of paths to the generated PNG images.
        """
        import pypdfium2 as pdfium
        from PIL import Image

        doc = pdfium.PdfDocument(pdf_path)
        try:
            page_count = len(doc)
            logger.info("Converting PDF to images: %d pages, dpi=%d", page_count, dpi)

            if output_dir is None:
                tmp = tempfile.mkdtemp(prefix="sherpanote_ocr_")
                output_dir = tmp

            Path(output_dir).mkdir(parents=True, exist_ok=True)
            scale = dpi / 72  # PDFium renders at 72 dpi base
            image_paths: list[str] = []

            for page_idx in range(page_count):
                page = doc[page_idx]
                try:
                    bitmap = page.render(scale=scale)
                    pil_image = bitmap.to_pil()
                finally:
                    # Explicitly close page to avoid double-free in PdfDocument finalizer
                    page.close()
                img_path = str(Path(output_dir) / f"page_{page_idx + 1:04d}.png")
                pil_image.save(img_path, "PNG")
                image_paths.append(img_path)
        finally:
            doc.close()

        logger.info("PDF converted: %d images generated in %s", len(image_paths), output_dir)
        return image_paths

    @staticmethod
    def supported_image_extensions() -> tuple[str, ...]:
        """Return supported file extensions for file picker."""
        return (
            "PNG Image (*.png)",
            "JPEG Image (*.jpg;*.jpeg)",
            "BMP Image (*.bmp)",
            "TIFF Image (*.tiff;*.tif)",
            "WebP Image (*.webp)",
            "PDF Document (*.pdf)",
            "Word Document (*.docx)",
            "PowerPoint (*.pptx)",
            "Excel Workbook (*.xlsx)",
            "All Files (*.*)",
        )

    def cleanup(self) -> None:
        """Release the OCR engine to free memory."""
        self._engine = None
        logger.info("OCR engine released")
