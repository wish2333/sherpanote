"""Model download, extraction, validation, and lifecycle management.

Supports multiple download sources:
  - GitHub releases (default)
  - HuggingFace / HF-Mirror (via huggingface_hub library)
  - GitHub proxy (user-provided domain)
  - ModelScope (Alibaba ecosystem)

All I/O runs in a background thread so the UI stays responsive.
Progress is reported via callbacks.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import sys
import tarfile
import threading
import urllib.request
from pathlib import Path
from typing import Any, Callable

from py.model_registry import ModelEntry, get_model, get_download_url

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536  # 64 KB


# ------------------------------------------------------------------ #
#  Proxy helper                                                        #
# ------------------------------------------------------------------ #


def _build_opener(proxy_mode: str, proxy_url: str | None) -> urllib.request.OpenerDirector:
    """Build a urllib opener based on proxy settings.

    Args:
        proxy_mode: "none", "system", or "custom".
        proxy_url: Proxy URL when mode is "custom".
    """
    if proxy_mode == "none":
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    if proxy_mode == "custom" and proxy_url:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    # "system" -- default opener (uses env vars / system settings)
    return urllib.request.build_opener()


# ------------------------------------------------------------------ #
#  Download (HTTP)                                                     #
# ------------------------------------------------------------------ #


def download_archive(
    url: str,
    dest_path: Path,
    on_progress: Callable[[int, int], None] | None = None,
    cancel_event: threading.Event | None = None,
    proxy_mode: str = "none",
    proxy_url: str | None = None,
) -> Path:
    """Download a file with optional resume, progress, and proxy support.

    Args:
        url: Remote URL to download from.
        dest_path: Local file path to write to.
        on_progress: Callback(bytes_downloaded, total_bytes).
        cancel_event: If set, abort the download.
        proxy_mode: "none", "system", or "custom".
        proxy_url: Proxy URL when mode is "custom".

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

    opener = _build_opener(proxy_mode, proxy_url)
    try:
        resp = opener.open(req, timeout=30)
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
#  Download (HuggingFace)                                              #
# ------------------------------------------------------------------ #


def download_from_huggingface(
    model: ModelEntry,
    endpoint: str,
    dest_path: Path,
    on_progress: Callable[[int, int], None] | None = None,
    cancel_event: threading.Event | None = None,
    proxy_url: str | None = None,
) -> Path:
    """Download a model file using huggingface_hub.

    Args:
        model: The model entry (must have archive_name or hf_filename).
        endpoint: HF API endpoint ("https://huggingface.co" or "https://hf-mirror.com").
        dest_path: Local file path to write to.
        on_progress: Callback(bytes_downloaded, total_bytes).
        cancel_event: If set, abort the download.
        proxy_url: Optional proxy URL for HTTP requests.
    """
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import tqdm as hf_tqdm

    repo_id = model.hf_repo_id or f"csukuangfj/{model.model_id}"
    filename = model.hf_filename or model.archive_name

    # HF library downloads to a cache; we copy to dest_path after.
    _cancel_flag = False

    def _on_progress_wrapper(progress) -> None:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download cancelled")
        if on_progress:
            on_progress(progress.n, progress.total)

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Set proxy via environment for huggingface_hub.
    old_http_proxy = os.environ.get("HTTP_PROXY")
    old_https_proxy = os.environ.get("HTTPS_PROXY")
    old_no_proxy = os.environ.get("NO_PROXY")
    if proxy_url:
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url

    try:
        cached_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            endpoint=endpoint,
            local_dir=None,
        )
        shutil.copy2(cached_path, dest_path)
    finally:
        # Restore proxy env vars.
        if proxy_url:
            if old_http_proxy is not None:
                os.environ["HTTP_PROXY"] = old_http_proxy
            else:
                os.environ.pop("HTTP_PROXY", None)
            if old_https_proxy is not None:
                os.environ["HTTPS_PROXY"] = old_https_proxy
            else:
                os.environ.pop("HTTPS_PROXY", None)

    return dest_path


# ------------------------------------------------------------------ #
#  Unified download dispatcher                                         #
# ------------------------------------------------------------------ #


def download_model(
    model: ModelEntry,
    source: str,
    dest_path: Path,
    ghproxy_domain: str | None = None,
    proxy_mode: str = "none",
    proxy_url: str | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Download a model from the specified source.

    Routes to the appropriate download function based on source type.
    """
    if source in ("huggingface", "hf_mirror"):
        endpoint = (
            "https://hf-mirror.com"
            if source == "hf_mirror"
            else "https://huggingface.co"
        )
        return download_from_huggingface(
            model, endpoint, dest_path,
            on_progress=on_progress,
            cancel_event=cancel_event,
            proxy_url=proxy_url if proxy_mode == "custom" else None,
        )

    # GitHub, ghproxy, modelscope all use HTTP download.
    url = get_download_url(model, source, ghproxy_domain)
    return download_archive(
        url, dest_path,
        on_progress=on_progress,
        cancel_event=cancel_event,
        proxy_mode=proxy_mode,
        proxy_url=proxy_url,
    )


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
        dest = models_dir / (model_id + ".onnx")
        shutil.copy2(archive_path, dest)
        logger.info("VAD model installed to %s", dest)
        return dest

    target_dir = models_dir / model_id
    if target_dir.exists():
        shutil.rmtree(target_dir)

    with tarfile.open(archive_path, "r:bz2") as tf:
        # Detect single top-level directory ("tarbomb") and strip it.
        names = tf.getnames()
        top_dirs = {n.split("/")[0] for n in names if "/" in n and not n.startswith(".")}
        top_dirs |= {n for n in names if n.count("/") == 0 and not n.startswith(".")}
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
    """Check that a model directory contains valid model files.

    For known models, checks required_files (with prefix support).
    For unknown models, checks that at least a tokens.txt and one .onnx file exist.

    Returns:
        {"valid": True} or {"valid": False, "missing": [...]}
    """
    entry = get_model(model_id)

    if entry is None or entry.model_type == "vad":
        if model_id in ("silero_vad", "silero_vad_v5"):
            vad_file = Path(models_dir) / (model_id + ".onnx")
            if vad_file.exists():
                return {"valid": True}
            return {"valid": False, "missing": [model_id + ".onnx"]}
        # Unknown model -- check if it has model files.
        model_dir = Path(models_dir) / model_id
        if model_dir.is_dir():
            has_tokens = _find_file(model_dir, "tokens.txt")
            has_onnx = any(f.suffix == ".onnx" for f in model_dir.iterdir() if f.is_file())
            return {"valid": bool(has_tokens and has_onnx), "missing": []}
        return {"valid": False, "missing": []}

    model_dir = Path(models_dir) / model_id
    # Check required_files with prefix support.
    missing = [
        fname for fname in entry.required_files
        if not _find_file(model_dir, fname)
    ]
    if missing:
        return {"valid": False, "missing": missing}
    return {"valid": True}


def _find_file(model_dir: Path, *candidates: str) -> Path | None:
    """Find the first matching file in model_dir (recursive).

    Each candidate is tried as:
    1. Exact filename
    2. Prefixed variant (e.g. "distil-large-v3.5-tokens.txt" matches "tokens.txt")
    3. Quantized variant (e.g. "encoder.int8.onnx" matches "encoder.onnx")
    4. Prefixed + quantized (e.g. "distil-large-v3.5-encoder.int8.onnx" matches "encoder.onnx")

    Searches model_dir and one level of subdirectories.
    """
    search_dirs = [model_dir]
    for sub in model_dir.iterdir():
        if sub.is_dir() and not sub.name.startswith("."):
            search_dirs.append(sub)
    for search_dir in search_dirs:
        for name in candidates:
            exact = search_dir / name
            if exact.exists():
                return exact
            for f in search_dir.iterdir():
                if f.is_file() and f.name != name and _match_model_file(f.name, name):
                    return f
    return None


def _match_model_file(actual_name: str, candidate: str) -> bool:
    """Check if actual_name matches candidate for model file lookup.

    Handles prefixed variants and quantization suffixes.
    See SherpaASR._match_model_file for detailed rules.
    """
    _QUANT = ('int8', 'int4', 'fp16', 'fp32')

    cand_parts = candidate.split('.')
    if len(cand_parts) < 2:
        return False
    cand_ext = cand_parts[-1]
    if len(cand_parts) == 2:
        cand_core, cand_quant = cand_parts[0], None
    elif len(cand_parts) == 3 and cand_parts[1] in _QUANT:
        cand_core, cand_quant = cand_parts[0], cand_parts[1]
    else:
        return actual_name.endswith(candidate)

    act_parts = actual_name.split('.')
    if len(act_parts) < 2 or act_parts[-1] != cand_ext:
        return False
    act_rest = act_parts[:-1]  # Everything before extension
    if len(act_rest) >= 2 and act_rest[-1] in _QUANT:
        act_quant = act_rest[-1]
        act_core = '.'.join(act_rest[:-1])
    else:
        act_core = '.'.join(act_rest)
        act_quant = None

    if cand_quant is not None and act_quant != cand_quant:
        return False
    # Match both suffix patterns (e.g. "encoder-epoch-99-avg-1")
    # and prefix patterns (e.g. "distil-large-v3.5-encoder").
    return (
        act_core == cand_core
        or act_core.startswith(cand_core + "-")
        or act_core.startswith(cand_core + "_")
        or act_core.endswith("-" + cand_core)
        or act_core.endswith("_" + cand_core)
    )


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

    # Collect known model IDs for lookup.
    known_ids = {m.model_id: m for m in MODELS}

    # Check for VAD models (v4 and v5).
    for vad_id in ("silero_vad", "silero_vad_v5"):
        vad_file = models_dir / (vad_id + ".onnx")
        if vad_file.exists():
            size = vad_file.stat().st_size / (1024 * 1024)
            result.append({
                "model_id": vad_id,
                "valid": True,
                "size_mb": round(size, 1),
                "model_type": "vad",
            })

    # Scan subdirectories for installed models.
    if models_dir.is_dir():
        for entry in sorted(models_dir.iterdir()):
            if not entry.is_dir():
                continue
            model_id = entry.name
            validation = validate_model(model_id, models_dir)
            total_size = sum(
                f.stat().st_size for f in entry.rglob("*") if f.is_file()
            )
            size_mb = round(total_size / (1024 * 1024), 1)
            known = known_ids.get(model_id)
            # Classify unknown models by file structure.
            if known:
                model_type = known.model_type
            else:
                from py.asr import SherpaASR
                model_type = SherpaASR._classify_model_dir(entry) or "unknown"
            result.append({
                "model_id": model_id,
                "valid": validation["valid"],
                "size_mb": size_mb,
                "display_name": known.display_name if known else model_id,
                "model_type": model_type,
            })

    return result


def delete_model(model_id: str, models_dir: Path) -> dict[str, Any]:
    """Delete an installed model directory or VAD file."""
    models_dir = Path(models_dir)

    if model_id in ("silero_vad", "silero_vad_v5"):
        vad_file = models_dir / (model_id + ".onnx")
        if not vad_file.exists():
            return {"success": False, "error": "VAD model not found"}
        vad_file.unlink()
        logger.info("VAD model deleted: %s", model_id)
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
        installer = ModelInstaller(models_dir, download_source="github")
        installer.start("model-id", on_progress=callback)
        # ... later:
        installer.cancel()
        result = installer.result  # dict
    """

    def __init__(
        self,
        models_dir: str | Path,
        download_source: str = "github",
        custom_ghproxy_domain: str | None = None,
        proxy_mode: str = "none",
        proxy_url: str | None = None,
    ) -> None:
        self._models_dir = Path(models_dir)
        self._download_source = download_source
        self._custom_ghproxy_domain = custom_ghproxy_domain
        self._proxy_mode = proxy_mode
        self._proxy_url = proxy_url
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

        if entry.model_type == "tool":
            return {"success": False, "error": "Tool models cannot be installed in-app. Please download manually."}

        if self._download_source not in entry.sources:
            return {
                "success": False,
                "error": (
                    f"Source '{self._download_source}' is not available for this model. "
                    f"Available: {', '.join(entry.sources)}"
                ),
            }

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

        download_model(
            entry, self._download_source, tmp_archive,
            ghproxy_domain=self._custom_ghproxy_domain,
            proxy_mode=self._proxy_mode,
            proxy_url=self._proxy_url,
            on_progress=on_dl,
            cancel_event=self._cancel,
        )
        self._emit_progress("download", 85)

        try:
            # 2. Verify (85-90%).
            self._emit_progress("verify", 85)
            verify_checksum(tmp_archive, entry.sha256)
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
                vad_id = "silero_vad_v5"
                vad_path = models_dir / (vad_id + ".onnx")
                if not vad_path.exists():
                    vad_entry = get_model(vad_id)
                    if vad_entry and self._download_source in vad_entry.sources:
                        vad_tmp = models_dir / "_silero_vad_download.tmp"
                        self._emit_progress("download", 100, sub_phase="vad")
                        download_model(
                            vad_entry, self._download_source, vad_tmp,
                            ghproxy_domain=self._custom_ghproxy_domain,
                            proxy_mode=self._proxy_mode,
                            proxy_url=self._proxy_url,
                            cancel_event=self._cancel,
                        )
                        extract_archive(vad_tmp, vad_id, models_dir, is_vad=True)
                        if vad_tmp.exists():
                            vad_tmp.unlink()

            return {"success": True, "model_id": model_id}

        finally:
            # Clean up temp archive.
            if tmp_archive.exists():
                tmp_archive.unlink()
