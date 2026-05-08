"""Storage API mixin.

Provides record CRUD, version history, export/import,
audio file management, and import-and-transcribe workflows.
"""

from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from pywebvue import expose
from py.api.base import ApiBase

logger = logging.getLogger(__name__)


class StorageMixin(ApiBase):
    """Storage-related @expose methods."""

    # ---- Record CRUD ----

    @expose
    def save_record(self, data: dict) -> dict:
        """Create or update a record."""
        record = self._api._storage.save(data)
        record = self._annotate_record(record)
        return {"success": True, "data": record}

    def _annotate_record(self, record: dict) -> dict:
        """Add computed fields to a record for the frontend."""
        audio_path = record.get("audio_path", "")
        if audio_path:
            try:
                resolved = str(Path(audio_path).resolve())
                audio_dir = str(Path(self._api._config.data_dir).resolve() / "audio")
                record["can_retranscribe"] = resolved.startswith(audio_dir)
            except (OSError, ValueError):
                record["can_retranscribe"] = False
        else:
            record["can_retranscribe"] = False
        if "version" not in record or not record.get("version"):
            record["version"] = self._api._storage._get_current_version(record["id"])
        return record

    def _annotate_records(self, records: list[dict]) -> list[dict]:
        """Batch-annotate records with computed fields."""
        if not records:
            return records
        audio_dir = str(Path(self._api._config.data_dir).resolve() / "audio")
        record_ids = [r["id"] for r in records]
        id_list = ",".join("?" * len(record_ids))
        conn = self._api._storage._get_conn()
        version_rows = conn.execute(
            f"SELECT record_id, MAX(version) AS v FROM versions WHERE record_id IN ({id_list}) GROUP BY record_id",
            record_ids,
        ).fetchall()
        version_map = {row["record_id"]: row["v"] for row in version_rows}
        for r in records:
            audio_path = r.get("audio_path", "")
            if audio_path:
                try:
                    resolved = str(Path(audio_path).resolve())
                    r["can_retranscribe"] = resolved.startswith(audio_dir)
                except (OSError, ValueError):
                    r["can_retranscribe"] = False
            else:
                r["can_retranscribe"] = False
            r["version"] = version_map.get(r["id"], 0)
        return records

    @expose
    def get_record(self, record_id: str) -> dict:
        """Fetch a single record by ID."""
        record = self._api._storage.get(record_id)
        if record is None:
            return {"success": False, "error": f"Record not found: {record_id}"}
        record = self._annotate_record(record)
        return {"success": True, "data": record}

    @expose
    def list_records(self, filter: dict = None) -> dict:
        """List records with optional filtering."""
        records = self._api._storage.list(filter)
        records = self._annotate_records(records)
        return {"success": True, "data": records}

    @expose
    def delete_record(self, record_id: str) -> dict:
        """Delete a record and its version history."""
        success = self._api._storage.delete(record_id)
        return {"success": success, "data": {"record_id": record_id}}

    @expose
    def search_records(self, keyword: str) -> dict:
        """Search records by keyword (title + transcript)."""
        records = self._api._storage.list({"keyword": keyword})
        return {"success": True, "data": records}

    @expose
    def get_audio_base64(self, file_path: str) -> dict:
        """Read an audio file and return base64-encoded content with MIME type."""
        p = Path(file_path).resolve()
        allowed_base = Path(self._api._config.data_dir).resolve()
        if not str(p).startswith(str(allowed_base)):
            return {"success": False, "error": "Access denied: path outside data directory"}
        if not p.exists():
            return {"success": False, "error": f"Audio file not found: {file_path}"}

        max_size = 100 * 1024 * 1024  # 100 MB
        if p.stat().st_size > max_size:
            return {"success": False, "error": "Audio file too large for browser playback"}

        import mimetypes
        mime, _ = mimetypes.guess_type(str(p))
        if mime is None:
            mime = "audio/wav"

        try:
            import base64
            data = p.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            return {"success": True, "data": {"base64": b64, "mime": mime}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- Version History ----

    @expose
    def get_version_history(self, record_id: str) -> dict:
        """Get version history for a record."""
        versions = self._api._storage.get_versions(record_id)
        return {"success": True, "data": versions}

    @expose
    def save_version(self, record_id: str) -> dict:
        """Create an explicit version snapshot for a record."""
        try:
            version = self._api._storage.create_version(
                record_id, max_versions=self._api._config.max_versions
            )
            self._api._dirty_record_ids.discard(record_id)
            logger.info("Saved version %d for record %s", version, record_id)
            return {"success": True, "data": {"version": version}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def mark_dirty(self, record_id: str) -> dict:
        """Mark a record as having unsaved changes."""
        self._api._dirty_record_ids.add(record_id)
        return {"success": True, "data": None}

    @expose
    def mark_clean(self, record_id: str) -> dict:
        """Mark a record as clean (no unsaved changes)."""
        self._api._dirty_record_ids.discard(record_id)
        return {"success": True, "data": None}

    @expose
    def restore_version(self, record_id: str, version: int) -> dict:
        """Restore a record to a specific version."""
        record = self._api._storage.restore_version(record_id, version)
        if record is None:
            return {"success": False, "error": "Version not found."}
        new_ver = self._api._storage.create_version(
            record_id, max_versions=self._api._config.max_versions
        )
        record["version"] = new_ver
        return {"success": True, "data": record}

    @expose
    def delete_version(self, record_id: str, version: int) -> dict:
        """Delete a single version from a record's version history."""
        success = self._api._storage.delete_version(record_id, version)
        if not success:
            return {"success": False, "error": "Version not found."}
        return {"success": True, "data": {"version": version}}

    # ---- Export / Import ----

    @expose
    def export_record(self, record_id: str, fmt: str, include_ai: bool = True) -> dict:
        """Export a record. Format: md / txt / docx / srt."""
        try:
            path = self._api._storage.export(record_id, fmt, include_ai=include_ai)
            return {"success": True, "data": {"file_path": path}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def import_record(self, file_path: str) -> dict:
        """Import a .md or .txt file as a new record."""
        try:
            p = Path(file_path)
            if not p.exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            suffix = p.suffix.lower()
            if suffix not in (".md", ".txt"):
                return {"success": False, "error": f"Unsupported format: {suffix}. Use .md or .txt"}

            text = p.read_text(encoding="utf-8")
            title = p.stem

            record = self._api._storage.save({
                "title": title,
                "transcript": text,
                "audio_path": None,
                "segments": [],
                "ai_results": {},
                "category": "",
                "tags": [],
                "duration_seconds": 0,
            })
            return {"success": True, "data": record}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- Audio File Management ----

    def _audio_meta_path(self) -> Path:
        """Path to the audio display-name metadata JSON file."""
        return Path(self._api._config.data_dir) / "audio_meta.json"

    def _load_audio_meta(self) -> dict[str, str]:
        """Load audio metadata mapping from disk."""
        try:
            import json
            text = self._audio_meta_path().read_text(encoding="utf-8")
            return json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_audio_meta(self) -> None:
        """Persist audio metadata mapping to disk."""
        import json
        self._audio_meta_path().write_text(
            json.dumps(self._api._audio_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _copy_file_to_audio_dir(self, src_path: str, display_name: str | None = None) -> str:
        """Copy a file into data/audio/ with a safe timestamped filename."""
        audio_dir = Path(self._api._config.data_dir) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        src = Path(src_path)
        ext = src.suffix.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"import_{timestamp}"

        dest = audio_dir / f"{base_name}{ext}"
        if dest.exists():
            counter = 1
            while (audio_dir / f"{base_name}_{counter}{ext}").exists():
                counter += 1
            dest = audio_dir / f"{base_name}_{counter}{ext}"

        shutil.copy2(str(src), str(dest))
        logger.info("Copied %s -> %s", src_path, dest)

        if display_name:
            self._api._audio_meta[dest.name] = display_name
            self._save_audio_meta()

        return str(dest)

    @expose
    def list_audio_files(self) -> dict:
        """List all audio files in the data/audio directory."""
        audio_dir = Path(self._api._config.data_dir) / "audio"
        if not audio_dir.is_dir():
            return {"success": True, "data": []}

        records = self._api._storage.list()
        path_to_records: dict[str, list[dict[str, str]]] = {}
        for rec in records:
            audio_path = rec.get("audio_path", "")
            if audio_path:
                normalized = str(Path(audio_path))
                path_to_records.setdefault(normalized, []).append({
                    "id": rec["id"],
                    "title": rec.get("title", ""),
                })

        files = []
        for entry in sorted(audio_dir.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True):
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext not in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma"):
                continue

            size_mb = entry.stat().st_size / (1024 * 1024)
            normalized = str(entry)
            linked = path_to_records.get(normalized, [])

            files.append({
                "file_path": str(entry),
                "file_name": entry.name,
                "display_name": self._api._audio_meta.get(entry.name, ""),
                "size_mb": round(size_mb, 2),
                "linked_records": linked,
            })

        return {"success": True, "data": files}

    @expose
    def delete_audio_file(self, file_path: str) -> dict:
        """Delete an audio file from disk and clear references in linked records."""
        p = Path(file_path).resolve()
        allowed_base = Path(self._api._config.data_dir).resolve()
        if not str(p).startswith(str(allowed_base)):
            return {"success": False, "error": "Access denied: path outside data directory"}
        if not p.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        try:
            p.unlink()
            self._api._audio_meta.pop(p.name, None)
            self._save_audio_meta()
            normalized = str(p)
            for rec in self._api._storage.list():
                rec_audio = rec.get("audio_path")
                if not rec_audio:
                    continue
                rec_path = str(Path(rec_audio).resolve())
                if rec_path == normalized:
                    updated = dict(rec)
                    updated["audio_path"] = None
                    self._api._storage.save(updated)
            return {"success": True, "data": {"file_path": str(p)}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @expose
    def open_audio_folder(self) -> dict:
        """Open the audio files directory in the system file explorer."""
        import os
        import sys
        import subprocess

        audio_dir = str(Path(self._api._config.data_dir) / "audio")
        Path(audio_dir).mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(audio_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", audio_dir])
            else:
                subprocess.Popen(["xdg-open", audio_dir])
            return {"success": True, "data": {"path": audio_dir}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- Import & Transcribe ----

    @expose
    def import_and_transcribe(self, file_path: str, title: str | None = None) -> dict:
        """Copy an audio file into data/audio/, then transcribe it."""
        logger.info("import_and_transcribe called for: %s", file_path)

        src = Path(file_path)
        if not src.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        audio_exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma"}
        if src.suffix.lower() not in audio_exts:
            return {"success": False, "error": f"Unsupported audio format: {src.suffix}"}

        if title is None:
            title = src.stem

        audio_dir = Path(self._api._config.data_dir) / "audio"
        resolved_src = src.resolve()
        resolved_audio_dir = audio_dir.resolve()
        if str(resolved_src).startswith(str(resolved_audio_dir)):
            dest_path = file_path
        else:
            try:
                dest_path = self._copy_file_to_audio_dir(file_path, display_name=title)
            except Exception as exc:
                logger.error("Failed to copy file: %s", exc, exc_info=True)
                return {"success": False, "error": f"Failed to copy file: {exc}"}

        use_whisper = self._api._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._api._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._api._asr is None:
            from py.asr import SherpaASR
            self._api._asr = SherpaASR(self._api._make_asr_config())

        def on_progress(percent: int, info: dict | None = None) -> None:
            payload: dict = {"percent": percent}
            if info:
                payload["segments"] = info
            self._emit("transcribe_progress", payload)

        def _work(dest: str, rec_title: str) -> None:
            self._transcribe_and_save_record(dest, rec_title, on_progress)

        threading.Thread(target=_work, args=(dest_path, title), daemon=True).start()
        return {"success": True, "data": {"status": "importing", "audio_path": dest_path}}

    def _transcribe_and_save_record(self, audio_path: str, title: str, on_progress: Callable) -> None:
        """Internal helper to transcribe an audio file and save it as a record."""
        from py.io import get_audio_metadata

        try:
            use_whisper = self._api._config.asr.asr_backend == "whisper-cpp"
            if use_whisper:
                whisper = self._api._get_whisper_asr()
                if whisper is None:
                    raise RuntimeError("whisper.cpp ASR not available")
                logger.info("Transcribing with whisper.cpp: %s", audio_path)
                segments = whisper.transcribe_file(audio_path, on_progress=on_progress)
            else:
                if self._api._asr is None:
                    raise RuntimeError("sherpa-onnx ASR not initialized")
                if self._api._asr._offline_recognizer is None:
                    self.run_on_main_thread("create_offline_recognizer", timeout=60.0)
                logger.info("Transcribing with sherpa-onnx: %s", audio_path)
                segments = self._api._asr.transcribe_file(audio_path, on_progress=on_progress)

            full_text = " ".join(s["text"] for s in segments)
            full_text = self._api._apply_punctuation(full_text)
            logger.info("Saving record for %s", title)
            meta = get_audio_metadata(audio_path)
            duration_seconds = meta.get("duration", 0) or 0
            record = self._api._storage.save({
                "title": title,
                "transcript": full_text,
                "segments": segments,
                "audio_path": audio_path,
                "duration_seconds": duration_seconds,
            })
            record = self._annotate_record(record)

            if self._api._config.auto_ai_modes and self._api._config.ai.api_key:
                record = self._api._auto_process_record(record)

            self._emit("import_transcribe_complete", {
                "record_id": record["id"],
                "record": record,
                "audio_path": audio_path,
            })
            logger.info("Transcription and save complete, record_id=%s", record["id"])
        except Exception as exc:
            logger.error("Transcription failed: %s", exc, exc_info=True)
            self._emit("transcribe_error", {"error": f"Transcription failed: {exc}"})

    @expose
    def download_and_transcribe(self, url: str) -> dict:
        """Download audio from a URL and then transcribe it."""
        from py.video_downloader import VideoDownloadConfig, download_audio

        logger.info("download_and_transcribe called for URL: %s", url)

        temp_dir = str(Path(self._api._config.data_dir) / "temp")
        config = VideoDownloadConfig(
            output_dir=temp_dir,
            proxy=self._api._config.asr.proxy_url if self._api._config.asr.proxy_mode == "manual" else "",
            cookie_file=self._api._config.asr.ytdlp_cookie_path or "",
            ffmpeg_path=self._api._config.asr.ffmpeg_path or "",
        )

        def on_download_progress(progress: float) -> None:
            self._emit("download_progress", {"percent": int(progress * 100)})

        def _work(downloaded_path: str, title: str) -> None:
            try:
                dest_path = self._copy_file_to_audio_dir(downloaded_path, display_name=title)

                def on_transcribe_progress(percent: int, info: dict | None = None) -> None:
                    payload: dict = {"percent": percent}
                    if info:
                        payload["segments"] = info
                    self._emit("transcribe_progress", payload)

                self._transcribe_and_save_record(dest_path, title, on_transcribe_progress)

            except Exception as exc:
                logger.error("download_and_transcribe failed: %s", exc, exc_info=True)
                self._emit("transcribe_error", {"error": f"Download/Transcription failed: {exc}"})

        use_whisper = self._api._config.asr.asr_backend == "whisper-cpp"
        if use_whisper and self._api._get_whisper_asr() is None:
            return {"success": False, "error": "whisper.cpp backend not configured. Please install binary and model."}
        if not use_whisper and self._api._asr is None:
            from py.asr import SherpaASR
            self._api._asr = SherpaASR(self._api._make_asr_config())

        def _download_then_work() -> None:
            try:
                logger.info("Starting download for URL: %s", url)
                downloaded_path, title = download_audio(url, config, on_download_progress)
                _work(downloaded_path, title)
            except Exception as exc:
                logger.error("download_and_transcribe failed: %s", exc, exc_info=True)
                self._emit("transcribe_error", {"error": f"Download/Transcription failed: {exc}"})

        threading.Thread(target=_download_then_work, daemon=True).start()
        return {"success": True, "data": {"status": "downloading"}}
