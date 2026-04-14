"""Whisper.cpp ASR backend using CLI subprocess.

Provides file transcription via the whisper.cpp CLI binary,
with output parsed into the same segment format as SherpaASR.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WhisperCppConfig:
    """Configuration for the whisper.cpp ASR backend."""

    binary_path: str
    model_path: str
    language: str = "auto"
    threads: int = 4
    translate: bool = False


class WhisperCppASR:
    """ASR backend that delegates to the whisper.cpp CLI.

    This backend does NOT support real-time streaming.
    Only file-based transcription is available.
    """

    def __init__(self, config: WhisperCppConfig) -> None:
        self._config = config
        self._binary = Path(config.binary_path)

    def transcribe_file(
        self,
        path: str,
        on_progress: Callable[[int, dict[str, Any] | None], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Transcribe an audio file via whisper.cpp CLI.

        Args:
            path: Path to the audio file.
            on_progress: Callback(percent, info) for progress reporting.

        Returns:
            List of segment dicts matching SherpaASR format:
            {index, text, start_time, end_time, speaker, is_final}
        """
        if not self._binary.exists():
            raise FileNotFoundError(
                f"whisper.cpp binary not found: {self._binary}. "
                "Please install it from Settings."
            )

        model_path = Path(self._config.model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Whisper model not found: {model_path}. "
                "Please download a GGML model from Settings."
            )

        # Build command.
        cmd: list[str] = [
            str(self._binary),
            "-m", str(model_path),
            "-f", str(path),
            "--output-json",
        ]

        if self._config.language and self._config.language != "auto":
            cmd.extend(["-l", self._config.language])

        if self._config.threads > 0:
            cmd.extend(["-t", str(self._config.threads)])

        logger.info("Running whisper.cpp: %s", " ".join(cmd))

        if on_progress:
            on_progress(5, None)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max
                encoding="utf-8",
                errors="replace",
                cwd=str(self._binary.parent),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "whisper.cpp transcription timed out (>1 hour). "
                "Try a shorter file or a smaller model."
            )
        except OSError as exc:
            raise RuntimeError(
                f"Failed to run whisper.cpp: {exc}"
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout_tail = result.stdout[-500:].strip() if result.stdout else ""
            raise RuntimeError(
                f"whisper.cpp exited with code {result.returncode}: "
                f"{stderr or stdout_tail}"
            )

        if on_progress:
            on_progress(90, None)

        # Parse JSON output from stdout.
        segments = self._parse_output(result.stdout)

        if on_progress:
            total = max(len(segments), 1)
            on_progress(100, {"current": total, "total": total})

        logger.info("whisper.cpp produced %d segments", len(segments))
        return segments

    @staticmethod
    def _parse_output(stdout: str) -> list[dict[str, Any]]:
        """Parse whisper.cpp JSON output into segment dicts.

        The JSON output contains an array of segments, each with:
          - "text": transcribed text
          - "t0": start time in tokens/units
          - "t1": end time in tokens/units

        whisper.cpp outputs timing in milliseconds.
        """
        segments: list[dict[str, Any]] = []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("Failed to parse whisper.cpp JSON output. Raw output:\n%s", stdout[:500])
            # Try to extract text from raw output as fallback.
            text = stdout.strip()
            if text:
                segments.append({
                    "index": 0,
                    "text": text,
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "speaker": None,
                    "is_final": True,
                })
            return segments

        # The output may be wrapped in an object or be a direct array.
        items = data if isinstance(data, list) else data.get("transcription", [])

        # If there's a single full-text result.
        if isinstance(items, str):
            return [{
                "index": 0,
                "text": items.strip(),
                "start_time": 0.0,
                "end_time": 0.0,
                "speaker": None,
                "is_final": True,
            }]

        for i, item in enumerate(items):
            # whisper.cpp JSON segment format may vary.
            text = item.get("text", "").strip()
            if not text:
                continue

            # Timing can be in "timestamps" or "t0"/"t1" fields.
            start_time = 0.0
            end_time = 0.0

            if "timestamps" in item:
                ts = item["timestamps"]
                if isinstance(ts, (list, tuple)) and len(ts) >= 2:
                    # whisper.cpp sometimes outputs token-level timestamps.
                    # Use first and last token timestamps.
                    first_ts = ts[0] if ts else [0]
                    last_ts = ts[-1] if ts else [0]
                    start_time = float(first_ts[1]) / 1000.0 if isinstance(first_ts, list) else 0.0
                    end_time = float(last_ts[1]) / 1000.0 if isinstance(last_ts, list) else 0.0
            elif "t0" in item and "t1" in item:
                # Token-based timing (needs conversion).
                # This is a rough estimate; exact conversion depends on model.
                start_time = float(item["t0"]) * 0.02  # ~20ms per token at 16kHz
                end_time = float(item["t1"]) * 0.02
            elif "start" in item and "end" in item:
                start_time = float(item["start"])
                end_time = float(item["end"])

            segments.append({
                "index": i,
                "text": text,
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "speaker": None,
                "is_final": True,
            })

        return segments

    @staticmethod
    def is_binary_available(binary_path: str) -> bool:
        """Check if the whisper.cpp binary exists and is executable."""
        path = Path(binary_path)
        if not path.exists():
            return False
        try:
            result = subprocess.run(
                [str(path), "--help"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(path.parent),
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
