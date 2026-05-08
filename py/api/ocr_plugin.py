"""OCR and plugin management API mixin.

Provides OCR processing, document extraction, plugin lifecycle
(backend install/uninstall), OCR model management, and image preview.
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from pywebvue import expose
from py.api.base import ApiBase

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OcrPluginMixin(ApiBase):
    """OCR and plugin-related @expose methods."""

    # ---- Internal helpers ----

    def _get_ocr(self):
        """Lazy-initialize the OCR engine."""
        if self._api._ocr_engine is None:
            from py.ocr import OcrEngine

            ocr_config = self._api._config.ocr
            self._api._ocr_engine = OcrEngine(
                det_model_version=ocr_config.det_model_version,
                det_model_type=ocr_config.det_model_type,
                rec_model_version=ocr_config.rec_model_version,
                rec_model_type=ocr_config.rec_model_type,
                cls_model_version=ocr_config.cls_model_version,
                cls_model_type=ocr_config.cls_model_type,
            )
        return self._api._ocr_engine

    def _get_plugin_manager(self):
        """Lazy-initialize the plugin manager."""
        if self._api._plugin_manager is None:
            from py.plugins.manager import PluginManager
            self._api._plugin_manager = PluginManager()
        return self._api._plugin_manager

    def _get_document_extractor(self):
        """Lazy-initialize the document extractor with optional plugin support."""
        if self._api._document_extractor is None:
            from py.document_extractor import DocumentExtractor
            try:
                pm = self._get_plugin_manager()
                doc_config = self._api._config.document
            except Exception:
                pm = None
                doc_config = None
            self._api._document_extractor = DocumentExtractor(
                ocr_engine=self._get_ocr(),
                plugin_manager=pm,
                doc_config=doc_config,
                plugin_config=self._api._config.plugin if self._api._config else None,
            )
        return self._api._document_extractor

    @staticmethod
    def _build_segments(text: str) -> list[dict]:
        """Build segment list from extracted text."""
        blocks = [line for line in text.split("\n")
                   if line.strip() and line.strip() != "---"]
        return [
            {
                "index": i,
                "text": block,
                "start_time": 0.0,
                "end_time": 0.0,
                "speaker": None,
                "is_final": True,
            }
            for i, block in enumerate(blocks)
        ]

    # ---- Exposed methods ----

    @expose
    def detect_pdf_text_layer(self, file_path: str) -> dict:
        """Detect whether a PDF has a text layer."""
        from py.text_detector import has_text_layer

        if not Path(file_path).exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        if not file_path.lower().endswith(".pdf"):
            return {"success": False, "error": "Not a PDF file"}

        try:
            has_text = has_text_layer(file_path)
            return {"success": True, "data": {"has_text": has_text}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def ocr_process(self, files: list[str], mode: str = "single", title: str | None = None) -> dict:
        """Run document extraction on image/PDF/Office files and create record(s)."""
        if not files:
            return {"success": False, "error": "No files provided"}

        self._api._ocr_cancel_event.clear()
        logger.info("OCR process started: %d files, mode=%s", len(files), mode)

        def _work() -> None:
            try:
                extractor = self._get_document_extractor()
                total = len(files)

                def on_file_progress(current: int, file_total: int) -> None:
                    self._emit("ocr_progress", {
                        "status": "processing",
                        "current": current,
                        "total": file_total,
                        "percent": int(100 * current / file_total) if file_total > 0 else 0,
                    })

                if mode == "batch":
                    created_records: list[dict] = []
                    for i, f in enumerate(files):
                        if self._api._ocr_cancel_event.is_set():
                            self._emit("ocr_complete", {"status": "cancelled", "records": []})
                            return

                        self._emit("ocr_progress", {
                            "status": "processing",
                            "current": i,
                            "total": total,
                            "percent": int(100 * i / total),
                        })

                        doc = extractor.extract(f, on_progress=on_file_progress)
                        text = doc.markdown or ""
                        segments = self._build_segments(text)
                        source_name = Path(f).stem
                        record_title = title or f"OCR-{source_name}"
                        backend_used = doc.backend

                        record = self._api._storage.save({
                            "title": record_title,
                            "audio_path": None,
                            "transcript": text,
                            "segments": segments,
                        })
                        record = self._api._annotate_record(record)
                        record["_backend_used"] = backend_used
                        created_records.append(record)

                    self._emit("ocr_progress", {
                        "status": "processing",
                        "current": total,
                        "total": total,
                        "percent": 100,
                    })
                    self._emit("ocr_complete", {
                        "status": "done",
                        "records": created_records,
                        "backend_used": created_records[-1].get("_backend_used", "") if created_records else "",
                    })

                else:
                    all_docs: list = []
                    for i, f in enumerate(files):
                        if self._api._ocr_cancel_event.is_set():
                            self._emit("ocr_complete", {"status": "cancelled", "records": []})
                            return

                        self._emit("ocr_progress", {
                            "status": "processing",
                            "current": i,
                            "total": total,
                            "percent": int(100 * i / total),
                        })

                        doc = extractor.extract(f, on_progress=on_file_progress)
                        all_docs.append(doc)

                    self._emit("ocr_progress", {
                        "status": "processing",
                        "current": total,
                        "total": total,
                        "percent": 100,
                    })

                    parts = [d.markdown for d in all_docs if d.markdown and d.markdown.strip()]
                    text = "\n\n---\n\n".join(parts)
                    segments = self._build_segments(text)
                    first_source = Path(files[0]).stem if files else "OCR"
                    record = self._api._storage.save({
                        "title": title or f"OCR-{first_source}",
                        "audio_path": None,
                        "transcript": text,
                        "segments": segments,
                    })
                    record = self._api._annotate_record(record)
                    record = self._api._auto_process_record(record)
                    backend_used = all_docs[0].backend if all_docs else ""
                    self._emit("ocr_complete", {
                        "status": "done",
                        "records": [record],
                        "backend_used": backend_used,
                    })

            except Exception as exc:
                logger.exception("OCR processing failed")
                self._emit("ocr_complete", {"status": "error", "error": str(exc)})

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()
        return {"success": True, "data": {"status": "started"}}

    @expose
    def cancel_ocr(self) -> dict:
        """Cancel the current OCR processing."""
        self._api._ocr_cancel_event.set()
        return {"success": True, "data": {"status": "cancelled"}}

    @expose
    def get_plugin_status(self) -> dict:
        """Get installation status of all plugin backends."""
        try:
            pm = self._get_plugin_manager()
            statuses = pm.get_all_status()
            return {
                "success": True,
                "data": {
                    name: {"installed": s.installed, "version": s.version}
                    for name, s in statuses.items()
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def install_plugin(self, package_name: str) -> dict:
        """Install a plugin package into the plugin venv."""
        logger.info("Plugin install requested: %s", package_name)

        def _work() -> None:
            try:
                pm = self._get_plugin_manager()

                def on_output(line: str) -> None:
                    logger.debug("  pip: %s", line)
                    self._emit("plugin_install_progress", {"message": line})

                logger.info("Starting pip install for %s...", package_name)
                index_url = self._api._config.plugin.pip_index_url if self._api._config else None
                result = pm.install_package(package_name, on_output=on_output, index_url=index_url)
                self._api._plugin_manager = None
                self._api._document_extractor = None
                if result["success"]:
                    logger.info("Plugin installed: %s v%s", package_name, result.get("version"))
                    self._emit("plugin_install_complete", {
                        "package": package_name,
                        "version": result.get("version"),
                    })
                else:
                    logger.error("Plugin install failed: %s", result.get("error"))
                    self._emit("plugin_install_error", {
                        "package": package_name,
                        "error": result.get("error", "Unknown error"),
                    })
            except Exception as e:
                logger.exception("Plugin install exception: %s", package_name)
                self._api._plugin_manager = None
                self._api._document_extractor = None
                self._emit("plugin_install_error", {
                    "package": package_name,
                    "error": str(e),
                })

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()
        return {"success": True}

    @expose
    def uninstall_plugin(self, package_name: str) -> dict:
        """Uninstall a plugin package from the plugin venv."""
        logger.info("Plugin uninstall requested: %s", package_name)
        try:
            pm = self._get_plugin_manager()
            from py.plugins.manager import PACKAGE_NAMES
            pip_name = PACKAGE_NAMES.get(package_name, package_name)
            logger.info("Uninstalling pip package: %s", pip_name)
            result = pm.uninstall_package(pip_name)
            self._api._plugin_manager = None
            self._api._document_extractor = None
            if result["success"]:
                logger.info("Plugin uninstalled: %s", package_name)
            else:
                logger.error("Plugin uninstall failed: %s", result.get("error"))
            return {"success": result["success"], "data": result}
        except Exception as e:
            logger.exception("Plugin uninstall exception: %s", package_name)
            return {"success": False, "error": str(e)}

    @expose
    def detect_java(self) -> dict:
        """Detect Java 11+ runtime on the system."""
        try:
            from py.plugins.java_detect import detect_java
            manual_path = self._api._config.plugin.manual_java_path
            result = detect_java(manual_path=manual_path)
            return {
                "success": True,
                "data": {
                    "found": result.found,
                    "path": result.path,
                    "version": result.version,
                    "error": result.error,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def pre_download_docling(self) -> dict:
        """Pre-download docling AI models to the configured directory."""
        logger.info("Docling model pre-download requested")

        def _work() -> None:
            try:
                extractor = self._get_document_extractor()
                adapter = extractor._get_docling_adapter()
                if adapter is None or not adapter.is_available():
                    self._emit("plugin_install_error", {
                        "package": "docling",
                        "error": "Docling is not installed. Please install it first.",
                    })
                    return

                self._emit("plugin_install_progress", {"message": "正在下载 Docling AI 模型..."})
                result = adapter.pre_download_models()

                if result["success"]:
                    self._emit("plugin_install_complete", {
                        "package": "docling-models",
                        "version": result.get("message", "Done"),
                    })
                else:
                    self._emit("plugin_install_error", {
                        "package": "docling-models",
                        "error": result.get("error", "Unknown error"),
                    })
            except Exception as e:
                logger.exception("Docling model pre-download failed")
                self._emit("plugin_install_error", {
                    "package": "docling-models",
                    "error": str(e),
                })

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()
        return {"success": True}

    @expose
    def get_available_backends(self) -> dict:
        """Get availability status of all document extraction backends."""
        try:
            extractor = self._get_document_extractor()
            backends = extractor.get_available_backends()
            return {"success": True, "data": backends}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def destroy_plugin_venv(self) -> dict:
        """Destroy the entire plugin virtual environment."""
        try:
            pm = self._get_plugin_manager()
            result = pm.destroy_venv()
            self._api._plugin_manager = None
            self._api._document_extractor = None
            return {"success": result["success"], "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def pick_image_files(self) -> dict:
        """Open a native file picker for image/PDF files."""
        try:
            import webview
            from py.ocr import OcrEngine as _OcrEngine

            file_types = _OcrEngine.supported_image_extensions()
            try:
                dialog_type = webview.FileDialog.OPEN
            except AttributeError:
                dialog_type = webview.OPEN_DIALOG
            try:
                result = self._window.create_file_dialog(
                    dialog_type=dialog_type,
                    file_types=file_types,
                    allows_multiple_selection=True,
                )
            except TypeError:
                result = self._window.create_file_dialog(
                    dialog_type=dialog_type,
                    file_types=file_types,
                )
            if result:
                return {"success": True, "data": result}
            return {"success": False, "error": "No file selected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def scan_ocr_models(self) -> dict:
        """Scan and report which OCR model files are downloaded."""
        from py.ocr import scan_downloaded_models

        models = scan_downloaded_models()
        return {"success": True, "data": models}

    @expose
    def download_ocr_models(
        self,
        det_model_version: str = "v5",
        det_model_type: str = "mobile",
        rec_model_version: str = "v5",
        rec_model_type: str = "mobile",
        cls_model_version: str = "v5",
        cls_model_type: str = "server",
    ) -> dict:
        """Trigger RapidOCR auto-download for specified model variants."""
        def _work() -> None:
            from py.ocr import download_ocr_models as _download

            result = _download(
                det_model_version=det_model_version,
                det_model_type=det_model_type,
                rec_model_version=rec_model_version,
                rec_model_type=rec_model_type,
                cls_model_version=cls_model_version,
                cls_model_type=cls_model_type,
            )
            if result.get("success"):
                self._emit("ocr_model_download_complete", result)
            else:
                self._emit("ocr_model_download_error", result)

        threading.Thread(target=_work, daemon=True).start()
        return {"success": True, "data": {"status": "downloading"}}

    @expose
    def delete_ocr_model(self, version: str, role: str, model_type: str) -> dict:
        """Delete a specific OCR model file."""
        from py.ocr import delete_model_file

        return delete_model_file(version, role, model_type)

    @expose
    def get_image_preview(self, file_path: str) -> dict:
        """Read an image file and return base64-encoded content with MIME type."""
        from py.ocr import OcrEngine as _OcrEngine

        p = Path(file_path).resolve()
        if not p.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        max_size = 20 * 1024 * 1024  # 20 MB
        if p.stat().st_size > max_size:
            return {"success": False, "error": "File too large for preview"}

        import base64 as _base64
        import mimetypes

        if _OcrEngine.is_pdf(str(p)):
            try:
                pages = _OcrEngine.pdf_to_images(str(p), dpi=72)
                if not pages:
                    return {"success": False, "error": "PDF has no pages"}
                preview_path = Path(pages[0])
                data = preview_path.read_bytes()
                shutil.rmtree(str(preview_path.parent), ignore_errors=True)
                return {"success": True, "data": {"base64": _base64.b64encode(data).decode("ascii"), "mime": "image/png"}}
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        mime, _ = mimetypes.guess_type(str(p))
        if mime is None:
            mime = "image/png"

        try:
            data = p.read_bytes()
            b64 = _base64.b64encode(data).decode("ascii")
            return {"success": True, "data": {"base64": b64, "mime": mime}}
        except Exception as e:
            return {"success": False, "error": str(e)}
