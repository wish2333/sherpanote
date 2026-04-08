"""Model download, extraction, validation, and lifecycle management.

Handles downloading model archives from GitHub releases (or a
user-configured mirror), verifying integrity, extracting to the
models directory, and managing installed models.

All I/O runs in a background thread so the UI stays responsive.
Progress is reported via callbacks.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import shutil
import tarfile
import threading
import urllib.request
from pathlib import Path
from typing import Any, Callable

from py.model_registry import ModelEntry, get_model, get_download_url

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536  # 64 KB


# ------------------------------------------------------------------ #
#  Download                                                            #
# ------------------------------------------------------------------ #


def download_archive(
    url: str,
    dest_path: Path,
    on_progress: Callable[[int, int], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Download a file with optional resume and progress reporting.

    Args:
        url: Remote URL to download from.
        dest_path: Local file path to write to.
        on_progress: Callback(bytes_downloaded, total_bytes).
        cancel_event: If set, abort the download.

    Returns:
        Path to the downloaded file.

    Raises:
        RuntimeError: On network errors, HTTP errors, or cancellation.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Resume support: check partial file size.
    initial_size = 0
    if dest_path.exists():
        initial_size = dest_path.stat().st_size

    req = urllib.request.Request(url)
    if initial_size > 0:
        req.add_header("Range", f"bytes={initial_size}-")

    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except Exception as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc

    # Check response status.
    status = resp.status
    if status == 416:
        # Range not satisfiable -- file is already fully downloaded.
        return dest_path
    if status not in (200, 206):
        resp.close()
        raise RuntimeError(f"HTTP error {status} downloading {url}")

    # Determine total size.
    content_range = resp.headers.get("Content-Range", "")
    if status == 206 and content_range:
        total = int(content_range.split("/")[-1])
    else:
        content_length = resp.headers.get("Content-Length")
        total = int(content_length) if content_length else 0

    mode = "ab" if initial_size > 0 and status == 206 else "wb"
    downloaded = initial_size

    try:
        with open(dest_path, mode) as f:
            while True:
                if cancel_event and cancel_event.is_set():
                    resp.close()
                    raise RuntimeError("Download cancelled")

                chunk = resp.read(_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress and total > 0:
                    on_progress(downloaded, total)
    finally:
        resp.close()

    return dest_path


# ------------------------------------------------------------------ #
#  Verification                                                        #
# ------------------------------------------------------------------ #


def verify_checksum(archive_path: Path, expected_sha256: str | None) -> bool:
    """Verify SHA256 of a file. Returns True if expected_sha256 is None."""
    if expected_sha256 is None:
        return True

    sha = hashlib.sha256()
    with open(archive_path, "rb") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)

    actual = sha.hexdigest()
    if actual != expected_sha256:
        logger.warning("Checksum mismatch for %s", archive_path)
        return False
    return True


# ------------------------------------------------------------------ #
#  Extraction                                                          #
# ------------------------------------------------------------------ #


def extract_archive(
    archive_path: Path,
    model_id: str,
    models_dir: Path,
    is_vad: bool = False,
) -> Path:
    """Extract a .tar.bz2 archive (or copy a single .onnx file) into models_dir.

    For VAD models, the .onnx file is placed directly in models_dir.
    For other models, the archive is extracted to {models_dir}/{model_id}/.

    Returns:
        Path to the installed model directory (or file for VAD).
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if is_vad:
        dest = models_dir / "silero_vad.onnx"
        shutil.copy2(archive_path, dest)
        logger.info("VAD model installed to %s", dest)
        return dest

    target_dir = models_dir / model_id
    if target_dir.exists():
        shutil.rmtree(target_dir)

    with tarfile.open(archive_path, "r:bz2") as tf:
        # Detect single top-level directory ("tarbomb") and strip it.
        # Most sherpa-onnx archives contain one root folder matching
        # the archive name, e.g. sherpa-onnx-paraformer-zh/tokens.txt.
        names = tf.getnames()
        # Collect top-level dirs (skip '.' entries).
        top_dirs = {n.split("/")[0] for n in names if "/" in n and not n.startswith(".")}
        # Also include bare entries that are directories.
        top_dirs |= {n for n in names if n.count("/") == 0 and not n.startswith(".")}
        # If there's exactly one top-level entry and it's a directory,
        # strip it by adjusting member paths.
        strip_prefix = ""
        if len(top_dirs) == 1:
            prefix = next(iter(top_dirs)) + "/"
            if all(n.startswith(prefix) or n == next(iter(top_dirs)) for n in names):
                strip_prefix = prefix

        extract_kwargs: dict[str, Any] = {}
        if sys.version_info >= (3, 12):
            extract_kwargs["filter"] = "data"

        for member in tf.getmembers():
            if strip_prefix and member.name.startswith(strip_prefix):
                member.name = member.name[len(strip_prefix):]
            if not member.name:
                continue
            tf.extract(member, target_dir, **extract_kwargs)

    logger.info("Model extracted to %s", target_dir)
    return target_dir


# ------------------------------------------------------------------ #
#  Validation                                                          #
# ------------------------------------------------------------------ #


def validate_model(model_id: str, models_dir: Path) -> dict[str, Any]:
    """Check that all required_files exist in the model directory.

    Returns:
        {"valid": True} or {"valid": False, "missing": [...]}
    """
    entry = get_model(model_id)
    if entry is None:
        return {"valid": False, "missing": [], "error": f"Unknown model: {model_id}"}

    if entry.model_type == "vad":
        vad_file = Path(models_dir) / "silero_vad.onnx"
        if vad_file.exists():
            return {"valid": True}
        return {"valid": False, "missing": ["silero_vad.onnx"]}

    model_dir = Path(models_dir) / model_id
    missing = [
        fname for fname in entry.required_files if not (model_dir / fname).exists()
    ]
    if missing:
        return {"valid": False, "missing": missing}
    return {"valid": True}


# ------------------------------------------------------------------ #
#  List / Delete installed models                                      #
# ------------------------------------------------------------------ #


def list_installed_models(models_dir: Path) -> list[dict[str, Any]]:
    """Scan models_dir and return info about installed models."""
    models_dir = Path(models_dir)
    result: list[dict[str, Any]] = []

    if not models_dir.is_dir():
        return result

    from py.model_registry import MODELS

    for entry in MODELS:
        if entry.model_type == "vad":
            vad_file = models_dir / "silero_vad.onnx"
            if vad_file.exists():
                size = vad_file.stat().st_size / (1024 * 1024)
                result.append({
                    "model_id": "silero_vad",
                    "valid": True,
                    "size_mb": round(size, 1),
                })
            continue

        model_dir = models_dir / entry.model_id
        if not model_dir.is_dir():
            continue

        # Calculate total directory size.
        total_size = sum(
            f.stat().st_size for f in model_dir.rglob("*") if f.is_file()
        )
        size_mb = round(total_size / (1024 * 1024), 1)

        validation = validate_model(entry.model_id, models_dir)
        result.append({
            "model_id": entry.model_id,
            "valid": validation["valid"],
            "size_mb": size_mb,
        })

    return result


def delete_model(model_id: str, models_dir: Path) -> dict[str, Any]:
    """Delete an installed model directory or VAD file."""
    models_dir = Path(models_dir)

    if model_id == "silero_vad":
        vad_file = models_dir / "silero_vad.onnx"
        if not vad_file.exists():
            return {"success": False, "error": "VAD model not found"}
        vad_file.unlink()
        logger.info("VAD model deleted")
        return {"success": True, "model_id": model_id}

    model_dir = models_dir / model_id
    if not model_dir.is_dir():
        return {"success": False, "error": f"Model directory not found: {model_id}"}

    shutil.rmtree(model_dir)
    logger.info("Model deleted: %s", model_id)
    return {"success": True, "model_id": model_id}


# ------------------------------------------------------------------ #
#  Combined install (download + verify + extract + validate)           #
# ------------------------------------------------------------------ #


class ModelInstaller:
    """Stateful installer that runs in a background thread.

    Usage:
        installer = ModelInstaller(models_dir, mirror_url)
        installer.start("model-id", on_progress=callback)
        # ... later:
        installer.cancel()
        result = installer.result  # dict
    """

    def __init__(
        self,
        models_dir: str | Path,
        mirror_url: str | None = None,
    ) -> None:
        self._models_dir = Path(models_dir)
        self._mirror_url = mirror_url
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._result: dict[str, Any] | None = None
        self._on_progress: Callable[[dict[str, Any]], None] | None = None
        self._model_id: str = ""

    @property
    def result(self) -> dict[str, Any] | None:
        return self._result

    @property
    def is_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        model_id: str,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Start model installation in a background thread."""
        if self.is_active:
            raise RuntimeError("An installation is already in progress")

        self._model_id = model_id
        self._on_progress = on_progress
        self._cancel.clear()
        self._result = None

        self._thread = threading.Thread(
            target=self._run, daemon=True, name="model-installer"
        )
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation of the current installation."""
        self._cancel.set()

    def _emit_progress(self, phase: str, percent: int, **extra: Any) -> None:
        if self._on_progress:
            self._on_progress({
                "model_id": self._model_id,
                "phase": phase,
                "percent": percent,
                **extra,
            })

    def _run(self) -> None:
        """Worker thread entry point."""
        model_id = self._model_id
        models_dir = self._models_dir
        try:
            self._result = self._install(model_id, models_dir)
        except Exception as exc:
            logger.exception("Model install failed: %s", model_id)
            self._result = {"success": False, "error": str(exc), "model_id": model_id}

    def _install(self, model_id: str, models_dir: Path) -> dict[str, Any]:
        entry = get_model(model_id)
        if entry is None:
            return {"success": False, "error": f"Unknown model: {model_id}"}

        url = get_download_url(entry, self._mirror_url)
        is_vad = entry.model_type == "vad"

        # 1. Download (0-85%).
        self._emit_progress("download", 0)
        tmp_archive = models_dir / f"_{model_id}_download.tmp"

        def on_dl(downloaded: int, total: int) -> None:
            if total > 0:
                pct = int(85 * downloaded / total)
                self._emit_progress(
                    "download", pct,
                    bytes_downloaded=downloaded, total_bytes=total,
                )

        download_archive(url, tmp_archive, on_progress=on_dl, cancel_event=self._cancel)
        self._emit_progress("download", 85)

        try:
            # 2. Verify (85-90%).
            self._emit_progress("verify", 85)
            verify_checksum(tmp_archive, None)  # No SHA256 stored for now.
            self._emit_progress("verify", 90)

            # 3. Extract (90-97%).
            self._emit_progress("extract", 90)
            extract_archive(tmp_archive, model_id, models_dir, is_vad=is_vad)
            self._emit_progress("extract", 97)

            # 4. Validate (97-100%).
            self._emit_progress("validate", 97)
            validation = validate_model(model_id, models_dir)
            self._emit_progress("validate", 100)

            if not validation["valid"]:
                return {
                    "success": False,
                    "error": f"Validation failed. Missing: {validation.get('missing')}",
                    "model_id": model_id,
                }

            # 5. Auto-download VAD if this is the first ASR model install.
            if not is_vad:
                vad_path = models_dir / "silero_vad.onnx"
                if not vad_path.exists():
                    vad_entry = get_model("silero_vad")
                    if vad_entry:
                        vad_url = get_download_url(vad_entry, self._mirror_url)
                        vad_tmp = models_dir / "_silero_vad_download.tmp"
                        self._emit_progress("download", 100, sub_phase="vad")
                        download_archive(
                            vad_url, vad_tmp,
                            cancel_event=self._cancel,
                        )
                        extract_archive(vad_tmp, "silero_vad", models_dir, is_vad=True)
                        if vad_tmp.exists():
                            vad_tmp.unlink()

            return {"success": True, "model_id": model_id}

        finally:
            # Clean up temp archive.
            if tmp_archive.exists():
                tmp_archive.unlink()
