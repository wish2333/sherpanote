"""Application configuration management.

Uses SQLite key-value store (app_config table) for persistence.
All config objects are immutable dataclasses --
updates return new instances rather than mutating in place.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_KEY = "app_config"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent  # py/config.py -> project root
_DEFAULT_DATA_DIR = str(_PROJECT_ROOT / "data")
_DEFAULT_MODELS_DIR = str(_PROJECT_ROOT / "models")


@dataclass(frozen=True)
class AsrConfig:
    """sherpa-onnx ASR engine configuration."""

    model_dir: str = ""
    language: str = "auto"
    sample_rate: int = 16000
    use_gpu: bool = False
    asr_backend: str = "sherpa-onnx"  # "sherpa-onnx" | "whisper-cpp"
    active_streaming_model: str = ""
    active_offline_model: str = ""
    auto_punctuate: bool = False
    download_source: str = "github"
    custom_ghproxy_domain: str | None = None
    proxy_mode: str = "none"
    proxy_url: str | None = None
    vad_min_silence_duration: float = 0.7
    vad_min_speech_duration: float = 0.25
    vad_max_speech_duration: float = 8.0
    vad_threshold: float = 0.05
    offline_use_vad: bool = True
    vad_padding: float = 0.8
    active_vad_model: str = "auto"


@dataclass(frozen=True)
class AiConfig:
    """LLM backend configuration."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 8192


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    data_dir: str = ""
    asr: AsrConfig = AsrConfig()
    ai: AiConfig = AiConfig()
    max_versions: int = 20
    auto_ai_modes: tuple[str, ...] = ()  # e.g. ("polish", "note")
    max_tokens_mode: str = "auto"  # "auto" | "custom" | "default"

    @staticmethod
    def default() -> AppConfig:
        """Create default config with project-relative data directory."""
        return AppConfig(
            data_dir=_DEFAULT_DATA_DIR,
            asr=AsrConfig(model_dir=_DEFAULT_MODELS_DIR),
            ai=AiConfig(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "data_dir": self.data_dir,
            "asr": {
                "model_dir": self.asr.model_dir,
                "language": self.asr.language,
                "sample_rate": self.asr.sample_rate,
                "use_gpu": self.asr.use_gpu,
                "asr_backend": self.asr.asr_backend,
                "active_streaming_model": self.asr.active_streaming_model,
                "active_offline_model": self.asr.active_offline_model,
                "auto_punctuate": self.asr.auto_punctuate,
                "download_source": self.asr.download_source,
                "custom_ghproxy_domain": self.asr.custom_ghproxy_domain,
                "proxy_mode": self.asr.proxy_mode,
                "proxy_url": self.asr.proxy_url,
                "vad_min_silence_duration": self.asr.vad_min_silence_duration,
                "vad_min_speech_duration": self.asr.vad_min_speech_duration,
                "vad_max_speech_duration": self.asr.vad_max_speech_duration,
                "vad_threshold": self.asr.vad_threshold,
                "offline_use_vad": self.asr.offline_use_vad,
                "vad_padding": self.asr.vad_padding,
                "active_vad_model": self.asr.active_vad_model,
            },
            "ai": {
                "provider": self.ai.provider,
                "model": self.ai.model,
                "api_key": self.ai.api_key,
                "base_url": self.ai.base_url,
                "temperature": self.ai.temperature,
                "max_tokens": self.ai.max_tokens,
            },
            "max_versions": self.max_versions,
            "auto_ai_modes": list(self.auto_ai_modes),
            "max_tokens_mode": self.max_tokens_mode,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AppConfig:
        """Deserialize from dict. Missing keys fall back to defaults."""
        asr_d = data.get("asr", {})
        ai_d = data.get("ai", {})
        # Migrate old mirror_url to new download_source.
        download_source = asr_d.get("download_source", "github")
        custom_ghproxy_domain = asr_d.get("custom_ghproxy_domain")
        if download_source == "github" and asr_d.get("mirror_url"):
            old_url = asr_d["mirror_url"]
            if "hf-mirror" in old_url:
                download_source = "hf_mirror"
            elif old_url != "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/":
                download_source = "github"
                custom_ghproxy_domain = old_url
            logger.info("Migrated old mirror_url to download_source=%s", download_source)
        return AppConfig(
            data_dir=data.get("data_dir", _DEFAULT_DATA_DIR),
            asr=AsrConfig(
                model_dir=asr_d.get("model_dir", _DEFAULT_MODELS_DIR),
                language=asr_d.get("language", "auto"),
                sample_rate=asr_d.get("sample_rate", 16000),
                use_gpu=asr_d.get("use_gpu", False),
                asr_backend=asr_d.get("asr_backend", "sherpa-onnx"),
                active_streaming_model=asr_d.get("active_streaming_model", ""),
                active_offline_model=asr_d.get("active_offline_model", ""),
                auto_punctuate=asr_d.get("auto_punctuate", False),
                download_source=download_source,
                custom_ghproxy_domain=custom_ghproxy_domain,
                proxy_mode=asr_d.get("proxy_mode", "none"),
                proxy_url=asr_d.get("proxy_url"),
                vad_min_silence_duration=asr_d.get("vad_min_silence_duration", 0.7),
                vad_min_speech_duration=asr_d.get("vad_min_speech_duration", 0.25),
                vad_max_speech_duration=asr_d.get("vad_max_speech_duration", 8.0),
                vad_threshold=asr_d.get("vad_threshold", 0.05),
                offline_use_vad=asr_d.get("offline_use_vad", True),
                vad_padding=asr_d.get("vad_padding", 0.8),
                active_vad_model=asr_d.get("active_vad_model", "auto"),
            ),
            ai=AiConfig(
                provider=ai_d.get("provider", "openai"),
                model=ai_d.get("model", "gpt-4o-mini"),
                api_key=ai_d.get("api_key"),
                base_url=ai_d.get("base_url"),
                temperature=ai_d.get("temperature", 0.7),
                max_tokens=ai_d.get("max_tokens", 4096),
            ),
            max_versions=data.get("max_versions", 20),
            auto_ai_modes=tuple(data.get("auto_ai_modes", [])),
            max_tokens_mode=data.get("max_tokens_mode", "auto"),
        )


class ConfigStore:
    """Persists AppConfig to a SQLite key-value table.

    Reuses the same app_config table created by Storage.
    Each call to save() replaces the entire config blob.
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
        return self._conn

    def _ensure_table(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS app_config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )"""
        )
        conn.commit()

    def load(self) -> AppConfig:
        """Load config from the database. Returns defaults if not found."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM app_config WHERE key = ?", (_CONFIG_KEY,)
        ).fetchone()
        if row is None:
            logger.info("No saved config found, using defaults")
            return AppConfig.default()
        try:
            data = json.loads(row[0])
            return AppConfig.from_dict(data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse saved config: %s, using defaults", exc)
            return AppConfig.default()

    def save(self, config: AppConfig) -> AppConfig:
        """Persist config to the database. Returns the saved config."""
        conn = self._get_conn()
        data = json.dumps(config.to_dict(), ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)",
            (_CONFIG_KEY, data),
        )
        conn.commit()
        logger.info("Config saved")
        return config

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
