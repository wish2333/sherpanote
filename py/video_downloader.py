"""Video downloader utility using yt-dlp.

This module provides functionality to download audio from video URLs
(e.g., Bilibili, YouTube) and extract it as an MP3 file.
"""

from __future__ import annotations

import logging
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
    """
    output_dir: str
    proxy: str = ""
    format: str = "bestaudio/best"


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
    }

    if config.proxy:
        ydl_opts["proxy"] = config.proxy

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
