"""Video downloader utility using yt-dlp.

This module provides functionality to download audio from video URLs
(e.g., Bilibili, YouTube) and extract it as an MP3 file.
"""

from __future__ import annotations

import logging
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yt_dlp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoDownloadConfig:
    """Configuration for video downloading.

    Args:
        output_dir: Directory where the downloaded audio will be saved.
        proxy: Proxy URL if needed for downloading.
        format: yt-dlp format selection string.
        cookie_file: Path to cookie file for authenticated downloads.
    """
    output_dir: str
    proxy: str = ""
    format: str = "bestaudio/best"
    cookie_file: str = ""
    ffmpeg_path: str = ""


def ensure_ffmpeg(ffmpeg_path_override: str = "") -> str | None:
    """Ensure ffmpeg is available, returning its path or None.

    Priority:
    1. User-specified path (from config)
    2. Platform-specific known paths (Homebrew, etc.)
    3. System PATH
    4. static_ffmpeg (may download on first call)
    """
    import os
    import platform as _platform

    # 1. User-specified path.
    if ffmpeg_path_override:
        candidate = ffmpeg_path_override.strip()
        # If pointing to a directory, look for ffmpeg inside it.
        if os.path.isdir(candidate):
            exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
            candidate = os.path.join(candidate, exe)
        if os.path.isfile(candidate):
            return candidate

    # 2. Platform-specific known paths (app bundles may have limited PATH).
    known_paths: list[str] = []
    machine = _platform.machine().lower()
    if sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            known_paths = ["/opt/homebrew/bin/ffmpeg"]
        else:
            known_paths = ["/usr/local/bin/ffmpeg"]
    for kp in known_paths:
        if os.path.isfile(kp):
            return kp

    # 3. System PATH.
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # 4. static_ffmpeg (may download on first call).
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        return shutil.which("ffmpeg")
    except Exception as exc:
        logger.warning("static_ffmpeg unavailable: %s", exc)
        return None


def download_audio(url: str, config: VideoDownloadConfig, on_progress: Callable[[float], None]) -> tuple[str, str]:
    """Downloads audio from a video URL and extracts it as a WAV file.

    Args:
        url: The video URL to download from.
        config: Download configuration.
        on_progress: Callback function that receives progress as a float (0.0 to 1.0).

    Returns:
        Tuple of (absolute_path_to_audio, video_title).

    Raises:
        Exception: If the download or extraction fails.
    """
    # Ensure output directory exists
    out_path = Path(config.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Ensure ffmpeg is available for post-processing.
    ffmpeg_path = ensure_ffmpeg(getattr(config, "ffmpeg_path", ""))
    if not ffmpeg_path:
        if sys.platform == "darwin":
            hint = "请通过 Homebrew 安装 (brew install ffmpeg) 或在设置中点击安装 static-ffmpeg"
        elif sys.platform == "win32":
            hint = "请通过 winget/scoop/choco 安装 ffmpeg 或在设置中点击安装 static-ffmpeg"
        else:
            hint = "请安装 ffmpeg 或在设置中点击安装 static-ffmpeg"
        raise RuntimeError(f"ffmpeg not found. {hint}")

    # Use a unique ID for the filename to avoid collisions and issues with special characters
    unique_id = str(uuid.uuid4())
    output_template = str(out_path / f"{unique_id}.%(ext)s")

    # yt-dlp options
    ydl_opts = {
        "format": config.format,
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": str(Path(ffmpeg_path).parent),
    }

    if config.proxy:
        ydl_opts["proxy"] = config.proxy

    if config.cookie_file:
        ydl_opts["cookiefile"] = config.cookie_file

    def progress_hook(d: dict) -> None:
        if d["status"] == "downloading":
            p_str = d.get("_percent_str")
            if p_str:
                try:
                    # Remove '%' and convert to float (e.g., " 45.2%" -> 0.452)
                    progress = float(p_str.replace("%", "").strip()) / 100.0
                    on_progress(progress)
                except (ValueError, TypeError):
                    pass
        elif d["status"] == "finished":
            # Post-processing (extraction) starts after 'finished'
            # We can't easily track post-processing progress with this hook,
            # but we can signal that the download part is done.
            on_progress(0.99)

    ydl_opts["progress_hooks"] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Starting download for URL: %s", url)
            ydl.download([url])
            
            # The final file will have the .mp3 extension due to FFmpegExtractAudio
            final_path = out_path / f"{unique_id}.mp3"

            if not final_path.exists():
                # Fallback: search for any file starting with unique_id and ending in .mp3
                # in case yt-dlp did something unexpected.
                matches = list(out_path.glob(f"{unique_id}*.mp3"))
                if matches:
                    final_path = matches[0]
                else:
                    raise FileNotFoundError(f"Downloaded audio file not found: {final_path}")
            
            # Extract title from ydl info
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Downloaded Video")
            
            on_progress(1.0)
            logger.info("Successfully downloaded and extracted audio to: %s (Title: %s)", final_path, title)
            return str(final_path), title
            
    except Exception as e:
        logger.exception("Failed to download audio from %s: %s", url, e)
        raise
