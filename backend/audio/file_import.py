"""Audio/video file import for MeetScribe.

Converts any audio/video file to 16kHz mono PCM WAV using FFmpeg.
Supported formats: WAV, MP3, M4A, OGG, FLAC, MP4, WEBM, MKV, AVI, MOV.

File: backend/audio/file_import.py
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

SUPPORTED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac",
    ".mp4", ".webm", ".mkv", ".avi", ".mov", ".ts",
}


async def import_audio_file(
    source_path: str,
    output_path: Optional[str] = None,
) -> str:
    """Convert an audio/video file to 16kHz mono WAV.

    Args:
        source_path: Path to source audio/video file
        output_path: Where to write WAV (default: temp file)

    Returns:
        Path to the converted WAV file

    Raises:
        FileNotFoundError: If source file doesn't exist
        RuntimeError: If FFmpeg is not installed or conversion fails
        ValueError: If file format is not supported
    """
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{src.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg is not installed. Install with: sudo apt install ffmpeg"
        )

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()

    cmd = [
        "ffmpeg",
        "-y",                       # Overwrite output
        "-i", str(src),             # Input file
        "-ar", "16000",             # 16kHz sample rate
        "-ac", "1",                 # Mono
        "-acodec", "pcm_s16le",    # 16-bit PCM
        "-vn",                      # No video stream
        output_path,
    ]

    logger.info("Converting audio file", src=str(src), dst=output_path)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace")
        raise RuntimeError(f"FFmpeg conversion failed: {error_msg}")

    logger.info("Audio file converted", output=output_path)
    return output_path


def get_audio_duration(wav_path: str) -> float:
    """Get duration of a WAV file in seconds."""
    import wave
    try:
        with wave.open(wav_path, "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 0.0
