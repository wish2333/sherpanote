"""AI processing preset management.

Stores custom AI processing prompt presets in SQLite
so users can define, save, and switch between different
prompt templates for text processing.

Default prompts are sourced from py.llm._PROMPTS (single source of truth).
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from py.config import _DEFAULT_DATA_DIR
from py.llm import _PROMPTS

logger = logging.getLogger(__name__)

# Display labels for each built-in mode.
_BUILTIN_META: list[dict[str, Any]] = [
    {"id": "builtin_polish", "name": "Polish", "mode": "polish", "sort_order": 0},
    {"id": "builtin_note", "name": "Notes", "mode": "note", "sort_order": 1},
    {"id": "builtin_mindmap", "name": "Mind Map", "mode": "mindmap", "sort_order": 2},
    {"id": "builtin_brainstorm", "name": "Brainstorm", "mode": "brainstorm", "sort_order": 3},
]


def _get_builtin_defaults() -> list[dict[str, Any]]:
    """Build builtin preset list from _PROMPTS (single source of truth)."""
    presets = []
    for meta in _BUILTIN_META:
        prompt = _PROMPTS.get(meta["mode"], "")
        presets.append({
            **meta,
            "prompt": prompt,
            "is_default": True,
        })
    return presets


class ProcessingPresetStore:
    """SQLite-backed storage for AI processing presets."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = str(Path(_DEFAULT_DATA_DIR) / "data.db")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._ensure_table()
        self._seed_builtins()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_table(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_processing_presets (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                mode        TEXT NOT NULL DEFAULT 'custom',
                prompt      TEXT NOT NULL,
                is_default  INTEGER NOT NULL DEFAULT 0,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.commit()

    def _seed_builtins(self) -> None:
        """Insert built-in presets if they don't exist."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        for preset in _get_builtin_defaults():
            existing = conn.execute(
                "SELECT id FROM ai_processing_presets WHERE id = ?",
                (preset["id"],),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """INSERT INTO ai_processing_presets
                       (id, name, mode, prompt, is_default, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        preset["id"],
                        preset["name"],
                        preset["mode"],
                        preset["prompt"],
                        1 if preset.get("is_default") else 0,
                        preset.get("sort_order", 0),
                        now,
                        now,
                    ),
                )
        conn.commit()

    def reset_builtins(self) -> list[dict[str, Any]]:
        """Reset all built-in presets to their default prompts from _PROMPTS."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        updated = []
        for preset in _get_builtin_defaults():
            conn.execute(
                """UPDATE ai_processing_presets
                   SET prompt=?, updated_at=?
                   WHERE id=?""",
                (preset["prompt"], now, preset["id"]),
            )
            updated.append(self.get(preset["id"]))
        conn.commit()
        return [p for p in updated if p]

    def list(self) -> list[dict[str, Any]]:
        """List all presets sorted by sort_order."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM ai_processing_presets ORDER BY sort_order ASC, created_at ASC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, preset_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ai_processing_presets WHERE id = ?", (preset_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        preset_id = data.get("id") or str(uuid.uuid4())

        # Get next sort_order
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM ai_processing_presets"
        ).fetchone()[0]
        sort_order = data.get("sort_order", max_order + 1)

        conn.execute(
            """INSERT INTO ai_processing_presets
               (id, name, mode, prompt, is_default, sort_order, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                preset_id,
                data.get("name", "Custom"),
                data.get("mode", "custom"),
                data.get("prompt", ""),
                1 if data.get("is_default") else 0,
                sort_order,
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(preset_id)  # type: ignore[return-value]

    def update(self, preset_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self._get_conn()
        existing = self.get(preset_id)
        if not existing:
            return None

        now = datetime.now(timezone.utc).isoformat()
        merged = dict(existing)
        merged.update(data)
        merged["updated_at"] = now
        merged["is_default"] = 1 if merged.get("is_default") else 0

        conn.execute(
            """UPDATE ai_processing_presets
               SET name=?, mode=?, prompt=?, is_default=?, sort_order=?, updated_at=?
               WHERE id=?""",
            (
                merged["name"],
                merged["mode"],
                merged["prompt"],
                merged["is_default"],
                merged.get("sort_order", 0),
                now,
                preset_id,
            ),
        )
        conn.commit()
        return self.get(preset_id)

    def delete(self, preset_id: str) -> bool:
        """Delete a preset. Built-in presets cannot be deleted."""
        if preset_id.startswith("builtin_"):
            return False
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM ai_processing_presets WHERE id = ?", (preset_id,))
        conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["is_default"] = bool(d.get("is_default", 0))
        return d

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
