"""Backup and restore functionality for SherpaNote.

Exports configuration, presets, transcription records, and optionally
audio files into a portable ZIP archive. Supports cross-platform
(Windows <-> macOS) migration by stripping platform-specific fields.
"""

from __future__ import annotations

import json
import logging
import platform
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from py.config import _DEFAULT_DATA_DIR, AppConfig, ConfigStore

logger = logging.getLogger(__name__)

_BACKUP_VERSION = 1

# Fields to strip from config for cross-platform portability.
# Paths and platform-specific model selections are excluded.
_STRIP_CONFIG_KEYS = {
    "data_dir",
}

_STRIP_ASR_KEYS = {
    "model_dir",
    "active_streaming_model",
    "active_offline_model",
    "active_whisper_model",
    "ytdlp_cookie_path",
    "ffmpeg_path",
}


def export_backup(
    output_path: str,
    *,
    include_config: bool = True,
    include_presets: bool = True,
    include_records: bool = True,
    include_versions: bool = True,
    include_audio: bool = False,
) -> str:
    """Export application data to a ZIP backup file.

    Returns the path to the created backup file.
    """
    db_path = str(Path(_DEFAULT_DATA_DIR) / "data.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    audio_dir = Path(_DEFAULT_DATA_DIR) / "audio"

    counts: dict[str, int] = {}
    audio_files_count = 0

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        now = datetime.now(timezone.utc).isoformat()

        # --- manifest.json ---
        manifest: dict[str, Any] = {
            "version": _BACKUP_VERSION,
            "created_at": now,
            "platform": platform.system().lower(),
            "includes": {
                "config": include_config,
                "ai_presets": include_presets,
                "processing_presets": include_presets,
                "records": include_records,
                "versions": include_versions,
                "audio": include_audio,
            },
            "counts": {},
        }

        # --- config.json ---
        if include_config:
            row = conn.execute(
                "SELECT value FROM app_config WHERE key = 'app_config'"
            ).fetchone()
            if row:
                config_data = json.loads(row["value"])
                config_data = _strip_platform_fields(config_data)
                zf.writestr("config.json", json.dumps(config_data, ensure_ascii=False, indent=2))

        # --- ai_presets.json ---
        if include_presets:
            rows = conn.execute("SELECT * FROM ai_presets ORDER BY created_at ASC").fetchall()
            presets = [_preset_row_to_dict(r) for r in rows]
            zf.writestr("ai_presets.json", json.dumps(presets, ensure_ascii=False, indent=2))
            counts["ai_presets"] = len(presets)

        # --- processing_presets.json ---
        if include_presets:
            rows = conn.execute(
                "SELECT * FROM ai_processing_presets ORDER BY sort_order ASC, created_at ASC"
            ).fetchall()
            ppresets = [_processing_preset_row_to_dict(r) for r in rows]
            zf.writestr(
                "processing_presets.json", json.dumps(ppresets, ensure_ascii=False, indent=2)
            )
            counts["processing_presets"] = len(ppresets)

        # --- records.json ---
        records_map: dict[str, str] = {}  # record_id -> original audio filename
        if include_records:
            rows = conn.execute("SELECT * FROM records ORDER BY created_at ASC").fetchall()
            records = []
            for r in rows:
                d = _record_row_to_dict(r)
                # Track audio file for optional inclusion
                audio_path = d.get("audio_path")
                if audio_path:
                    audio_file = Path(audio_path)
                    if audio_file.exists() and audio_file.is_file():
                        records_map[d["id"]] = str(audio_file)
                        # Store relative path in backup
                        d["audio_path"] = f"audio/{audio_file.name}"
                    else:
                        d["audio_path"] = None
                records.append(d)
            zf.writestr("records.json", json.dumps(records, ensure_ascii=False, indent=2))
            counts["records"] = len(records)

        # --- versions.json ---
        if include_versions:
            rows = conn.execute("SELECT * FROM versions ORDER BY record_id ASC, version ASC").fetchall()
            versions = [_version_row_to_dict(r) for r in rows]
            zf.writestr("versions.json", json.dumps(versions, ensure_ascii=False, indent=2))
            counts["versions"] = len(versions)

        # --- audio files ---
        if include_audio and records_map:
            for record_id, audio_file in records_map.items():
                if Path(audio_file).exists():
                    arcname = f"audio/{Path(audio_file).name}"
                    # Handle duplicate filenames by appending record_id prefix
                    if any(info.filename == arcname for info in zf.infolist()):
                        arcname = f"audio/{record_id}_{Path(audio_file).name}"
                    zf.write(audio_file, arcname)
                    audio_files_count += 1
                    # Update the record's audio_path if we renamed
                    if arcname != f"audio/{Path(audio_file).name}":
                        records_data = json.loads(zf.read("records.json"))
                        for rec in records_data:
                            if rec["id"] == record_id:
                                rec["audio_path"] = arcname
                                break
                        zf.writestr(
                            "records.json", json.dumps(records_data, ensure_ascii=False, indent=2)
                        )

        counts["audio_files"] = audio_files_count
        manifest["counts"] = counts

        # Write manifest last so counts are accurate
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    conn.close()
    logger.info("Backup exported to %s (%d records, %d audio files)", output_path, counts.get("records", 0), audio_files_count)
    return output_path


def import_backup(zip_path: str) -> dict[str, Any]:
    """Import data from a ZIP backup file.

    Returns a summary dict of what was imported.
    Replaces existing data according to the backup merge policy.
    """
    db_path = str(Path(_DEFAULT_DATA_DIR) / "data.db")
    audio_dir = Path(_DEFAULT_DATA_DIR) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # --- Validate manifest ---
        manifest = _read_json_entry(zf, "manifest.json")
        if manifest is None:
            raise ValueError("Invalid backup file: missing manifest.json")
        backup_version = manifest.get("version", 0)
        if backup_version > _BACKUP_VERSION:
            raise ValueError(
                f"Backup version {backup_version} is newer than supported version {_BACKUP_VERSION}"
            )

        summary: dict[str, Any] = {
            "backup_version": backup_version,
            "source_platform": manifest.get("platform", "unknown"),
            "created_at": manifest.get("created_at", ""),
        }

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        try:
            # --- Config ---
            config_data = _read_json_entry(zf, "config.json")
            if config_data is not None:
                # Let from_dict fill in platform-specific defaults
                config = AppConfig.from_dict(config_data)
                config_json = json.dumps(config.to_dict(), ensure_ascii=False)
                conn.execute(
                    "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)",
                    ("app_config", config_json),
                )
                conn.commit()
                summary["config"] = True

            # --- AI Presets ---
            presets_data = _read_json_entry(zf, "ai_presets.json")
            if presets_data is not None:
                # Delete all existing presets
                conn.execute("DELETE FROM ai_presets")
                conn.commit()
                # Insert from backup
                imported_presets = 0
                for p in presets_data:
                    conn.execute(
                        """INSERT OR REPLACE INTO ai_presets
                           (id, name, provider, model, api_key, base_url,
                            temperature, max_tokens, is_active, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            p["id"],
                            p.get("name", ""),
                            p.get("provider", "openai"),
                            p.get("model", ""),
                            p.get("api_key"),
                            p.get("base_url"),
                            p.get("temperature", 0.7),
                            p.get("max_tokens", 4096),
                            1 if p.get("is_active") else 0,
                            p.get("created_at", ""),
                            p.get("updated_at", ""),
                        ),
                    )
                    imported_presets += 1
                conn.commit()
                summary["ai_presets"] = imported_presets

            # --- Processing Presets ---
            ppresets_data = _read_json_entry(zf, "processing_presets.json")
            if ppresets_data is not None:
                # Delete non-builtin presets only, keep builtins
                conn.execute("DELETE FROM ai_processing_presets WHERE id NOT LIKE 'builtin_%'")
                conn.commit()
                imported_ppresets = 0
                for p in ppresets_data:
                    conn.execute(
                        """INSERT OR REPLACE INTO ai_processing_presets
                           (id, name, mode, prompt, is_default, sort_order, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            p["id"],
                            p.get("name", ""),
                            p.get("mode", "custom"),
                            p.get("prompt", ""),
                            1 if p.get("is_default") else 0,
                            p.get("sort_order", 0),
                            p.get("created_at", ""),
                            p.get("updated_at", ""),
                        ),
                    )
                    imported_ppresets += 1
                conn.commit()
                summary["processing_presets"] = imported_ppresets

            # --- Records ---
            records_data = _read_json_entry(zf, "records.json")
            if records_data is not None:
                # Delete all existing records and versions
                conn.execute("DELETE FROM versions")
                conn.execute("DELETE FROM records")
                conn.commit()

                imported_records = 0
                audio_remap: dict[str, str] = {}  # old relative path -> new absolute path
                for r in records_data:
                    # Remap audio path: backup relative -> local absolute
                    old_audio = r.get("audio_path")
                    new_audio = None
                    if old_audio and old_audio.startswith("audio/"):
                        filename = old_audio[len("audio/"):]
                        new_audio = str(audio_dir / filename)
                        r["audio_path"] = new_audio
                    else:
                        r["audio_path"] = None

                    segments_json = json.dumps(r.get("segments", []), ensure_ascii=False)
                    ai_json = json.dumps(r.get("ai_results", {}), ensure_ascii=False)
                    tags_json = json.dumps(r.get("tags", []), ensure_ascii=False)

                    conn.execute(
                        """INSERT OR REPLACE INTO records
                           (id, title, audio_path, transcript, segments_json,
                            ai_results_json, category, tags_json, duration_seconds, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            r.get("id", ""),
                            r.get("title", ""),
                            r.get("audio_path"),
                            r.get("transcript", ""),
                            segments_json,
                            ai_json,
                            r.get("category", ""),
                            tags_json,
                            r.get("duration_seconds", 0.0),
                            r.get("created_at", ""),
                            r.get("updated_at", ""),
                        ),
                    )
                    imported_records += 1
                conn.commit()
                summary["records"] = imported_records

            # --- Versions ---
            versions_data = _read_json_entry(zf, "versions.json")
            if versions_data is not None:
                imported_versions = 0
                for v in versions_data:
                    conn.execute(
                        """INSERT OR REPLACE INTO versions
                           (record_id, version, transcript, segments_json, ai_results_json, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            v.get("record_id", ""),
                            v.get("version", 0),
                            v.get("transcript", ""),
                            v.get("segments_json", "[]"),
                            v.get("ai_results_json", "{}"),
                            v.get("created_at", ""),
                        ),
                    )
                    imported_versions += 1
                conn.commit()
                summary["versions"] = imported_versions

            # --- Audio files ---
            audio_count = 0
            for info in zf.infolist():
                if info.filename.startswith("audio/") and not info.is_dir():
                    filename = info.filename[len("audio/"):]
                    dest = audio_dir / filename
                    # Extract audio file
                    with zf.open(info) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    audio_count += 1
            summary["audio_files"] = audio_count

        finally:
            conn.close()

    logger.info("Backup imported from %s: %s", zip_path, summary)
    return summary


# ---- Internal Helpers ----


def _strip_platform_fields(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Remove platform-specific fields from config for cross-platform portability."""
    result = dict(config_dict)
    for key in _STRIP_CONFIG_KEYS:
        result.pop(key, None)
    if "asr" in result:
        asr = dict(result["asr"])
        for key in _STRIP_ASR_KEYS:
            asr.pop(key, None)
        result["asr"] = asr
    return result


def _read_json_entry(zf: zipfile.ZipFile, name: str) -> Any:
    """Read and parse a JSON file from a ZIP archive. Returns None if not found."""
    try:
        return json.loads(zf.read(name).decode("utf-8"))
    except KeyError:
        return None


def _preset_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert an ai_presets row to a plain dict."""
    d = dict(row)
    d["is_active"] = bool(d.get("is_active", 0))
    return d


def _processing_preset_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert an ai_processing_presets row to a plain dict."""
    d = dict(row)
    d["is_default"] = bool(d.get("is_default", 0))
    return d


def _record_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a records row to a plain dict with parsed JSON fields."""
    d = dict(row)
    for json_field, default in [
        ("segments_json", []),
        ("ai_results_json", {}),
        ("tags_json", []),
    ]:
        if json_field in d:
            try:
                d[json_field.replace("_json", "")] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError):
                d[json_field.replace("_json", "")] = default
    return d


def _version_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a versions row to a plain dict."""
    d = dict(row)
    d.setdefault("segments_json", "[]")
    return d
