"""AI provider preset management.

Stores multiple AI provider configurations (presets) in SQLite
so users can quickly switch between different providers/models.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from py.config import _DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)


class AiPresetStore:
    """SQLite-backed storage for AI provider presets.

    Each preset is a complete AiConfig snapshot (provider, model,
    api_key, base_url, temperature, max_tokens) with a user-friendly
    name. Exactly one preset is marked as active at any time.
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = str(Path(_DEFAULT_DATA_DIR) / "data.db")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_table(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_presets (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                provider    TEXT NOT NULL DEFAULT 'openai',
                model       TEXT NOT NULL,
                api_key     TEXT,
                base_url    TEXT,
                temperature REAL NOT NULL DEFAULT 0.7,
                max_tokens  INTEGER NOT NULL DEFAULT 4096,
                is_active   INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.commit()

    def list(self) -> list[dict[str, Any]]:
        """List all presets, active one first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM ai_presets ORDER BY is_active DESC, created_at ASC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, preset_id: str) -> dict[str, Any] | None:
        """Get a single preset by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ai_presets WHERE id = ?", (preset_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_active(self) -> dict[str, Any] | None:
        """Get the currently active preset."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ai_presets WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new preset. If is_active, deactivate others first."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        preset_id = data.get("id") or str(uuid.uuid4())

        if data.get("is_active"):
            conn.execute("UPDATE ai_presets SET is_active = 0")

        conn.execute(
            """INSERT INTO ai_presets (id, name, provider, model, api_key,
               base_url, temperature, max_tokens, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                preset_id,
                data.get("name", "Untitled"),
                data.get("provider", "openai"),
                data.get("model", ""),
                data.get("api_key"),
                data.get("base_url"),
                data.get("temperature", 0.7),
                data.get("max_tokens", 4096),
                1 if data.get("is_active") else 0,
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(preset_id)  # type: ignore[return-value]

    def update(self, preset_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update an existing preset."""
        conn = self._get_conn()
        existing = self.get(preset_id)
        if not existing:
            return None

        now = datetime.now(timezone.utc).isoformat()

        if data.get("is_active"):
            conn.execute("UPDATE ai_presets SET is_active = 0 WHERE id != ?", (preset_id,))

        merged = dict(existing)
        merged.update(data)
        merged["updated_at"] = now
        # is_active must be int for SQLite
        merged["is_active"] = 1 if merged.get("is_active") else 0

        conn.execute(
            """UPDATE ai_presets SET name=?, provider=?, model=?, api_key=?,
               base_url=?, temperature=?, max_tokens=?, is_active=?, updated_at=?
               WHERE id=?""",
            (
                merged["name"],
                merged["provider"],
                merged["model"],
                merged["api_key"],
                merged["base_url"],
                merged["temperature"],
                merged["max_tokens"],
                merged["is_active"],
                now,
                preset_id,
            ),
        )
        conn.commit()
        return self.get(preset_id)

    def delete(self, preset_id: str) -> bool:
        """Delete a preset. If it was active, activate the first remaining."""
        conn = self._get_conn()
        existing = self.get(preset_id)
        if not existing:
            return False

        was_active = existing.get("is_active", False)
        conn.execute("DELETE FROM ai_presets WHERE id = ?", (preset_id,))

        if was_active:
            # Activate the first remaining preset
            first = conn.execute(
                "SELECT id FROM ai_presets ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if first:
                conn.execute("UPDATE ai_presets SET is_active = 1 WHERE id = ?", (first["id"],))

        conn.commit()
        return True

    def set_active(self, preset_id: str) -> dict[str, Any] | None:
        """Set a preset as the active one."""
        conn = self._get_conn()
        existing = self.get(preset_id)
        if not existing:
            return None

        conn.execute("UPDATE ai_presets SET is_active = 0")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE ai_presets SET is_active = 1, updated_at = ? WHERE id = ?",
            (now, preset_id),
        )
        conn.commit()
        return self.get(preset_id)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["is_active"] = bool(d.get("is_active", 0))
        return d

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
