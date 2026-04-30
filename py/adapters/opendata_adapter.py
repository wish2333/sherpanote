"""Adapter for opendataloader-pdf: converts text-layer PDF to ExtractedDocument.

opendataloader-pdf provides high-quality PDF text extraction using Java.
Requires Java 11+ and runs in plugin venv subprocess.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from py.outputs.unified_document import ExtractedDocument

if TYPE_CHECKING:
    from py.plugins.manager import PluginManager
    from py.plugins.runner import RunResult

logger = logging.getLogger(__name__)

_RUNNER_MODULE = "py.plugins.runners.opendata_runner"


class OpendataAdapter:
    """Wraps opendataloader-pdf backend via subprocess to produce ExtractedDocument."""

    def __init__(
        self,
        plugin_manager: PluginManager,
        manual_java_path: str | None = None,
    ) -> None:
        self._manager = plugin_manager
        self._manual_java_path = manual_java_path

    @property
    def java_path(self) -> str | None:
        """Get the resolved Java path (manual override or auto-detected)."""
        return self._get_java_path()

    def is_available(self) -> bool:
        """Check if opendataloader-pdf is installed and Java is available."""
        if not self._manager.is_package_installed("opendataloader-pdf"):
            return False
        from py.plugins.java_detect import validate_java_version
        java_path = self._get_java_path()
        if java_path is None:
            return False
        valid, _, _ = validate_java_version(java_path)
        return valid

    def extract_text_pdf(self, file_path: str) -> ExtractedDocument:
        """Extract text from a text-layer PDF using opendataloader-pdf.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ExtractedDocument with extracted content.

        Raises:
            PluginError: If subprocess fails.
            RuntimeError: If Java is not available.
        """
        java_path = self._get_java_path()
        if java_path is None:
            raise RuntimeError(
                "Java 11+ required for opendataloader-pdf. "
                "Install from https://adoptium.net/ or set path in settings."
            )

        from py.plugins.runner import run

        logger.info("opendataloader-pdf extraction (Java: %s): %s", java_path, file_path)

        result = run(
            plugin_module=_RUNNER_MODULE,
            args={"file_path": file_path, "java_path": java_path},
            timeout=300,
        )

        return _parse_result(result)

    def _get_java_path(self) -> str | None:
        """Get the Java path: manual override first, then auto-detect."""
        from py.plugins.java_detect import detect_java
        detection = detect_java(manual_path=self._manual_java_path)
        if detection.found:
            return detection.path
        return None


def _parse_result(result: "RunResult") -> ExtractedDocument:
    """Convert RunResult data dict to ExtractedDocument."""
    data = result.data
    if data is None:
        return ExtractedDocument(
            markdown="",
            metadata={"error": "No data returned"},
            raw_format="opendataloader",
            backend="opendataloader",
        )

    return ExtractedDocument(
        markdown=data.get("markdown") or "",
        metadata=data.get("metadata", {}),
        tables=(),
        images=(),
        raw_format=data.get("raw_format", "opendataloader"),
        backend=data.get("backend", "opendataloader"),
        source_path=data.get("source_path", ""),
    )
