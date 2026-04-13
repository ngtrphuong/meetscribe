"""Audio device enumeration for MeetScribe.

Lists system audio (loopback) and microphone inputs via sounddevice.
Cross-platform: Windows WASAPI, Linux PulseAudio/PipeWire, macOS CoreAudio.
"""

from __future__ import annotations

import sys
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


def list_devices() -> list[dict]:
    """Return all available audio devices with their properties.

    Returns:
        List of device dicts with keys:
            id, name, hostapi, max_input_channels, max_output_channels,
            default_samplerate, is_loopback, is_default_input, is_default_output
    """
    try:
        import sounddevice as sd

        devices = []
        device_list = sd.query_devices()
        default_input = sd.default.device[0]
        default_output = sd.default.device[1]

        for idx, dev in enumerate(device_list):
            devices.append({
                "id": idx,
                "name": dev["name"],
                "hostapi": sd.query_hostapis(dev["hostapi"])["name"],
                "max_input_channels": dev["max_input_channels"],
                "max_output_channels": dev["max_output_channels"],
                "default_samplerate": int(dev["default_samplerate"]),
                "is_loopback": _is_loopback_device(dev["name"]),
                "is_default_input": idx == default_input,
                "is_default_output": idx == default_output,
            })

        return devices

    except ImportError:
        logger.warning("sounddevice not installed — returning empty device list")
        return []
    except Exception as exc:
        logger.error("Failed to enumerate audio devices", error=str(exc))
        return []


def list_input_devices() -> list[dict]:
    """Return only input-capable devices (microphones)."""
    return [d for d in list_devices() if d["max_input_channels"] > 0]


def list_loopback_devices() -> list[dict]:
    """Return system audio loopback devices (for capturing meeting audio).

    Platform notes:
    - Windows:  WASAPI loopback devices appear automatically
    - Linux:    PulseAudio/PipeWire monitor sources (name ends with .monitor)
    - macOS:    Requires virtual audio driver (BlackHole, Loopback, etc.)
    """
    all_devices = list_devices()
    return [d for d in all_devices if d["is_loopback"] or d["max_output_channels"] > 0 and d["max_input_channels"] > 0]


def get_default_input_device() -> Optional[dict]:
    """Return the system default microphone device."""
    devices = list_input_devices()
    for d in devices:
        if d["is_default_input"]:
            return d
    return devices[0] if devices else None


def get_device_by_name(name: str) -> Optional[dict]:
    """Find a device by partial name match (case-insensitive)."""
    name_lower = name.lower()
    for d in list_devices():
        if name_lower in d["name"].lower():
            return d
    return None


def _is_loopback_device(name: str) -> bool:
    """Heuristic: detect loopback/monitor devices by name patterns."""
    name_lower = name.lower()
    loopback_patterns = [
        ".monitor",          # PulseAudio/PipeWire monitor sources
        "loopback",          # Generic
        "stereo mix",        # Windows legacy
        "what u hear",       # Realtek
        "wave out mix",      # Legacy Windows
        "blackhole",         # macOS virtual driver
        "soundflower",       # macOS legacy virtual driver
        "virtual",           # Generic virtual audio
        "wasapi",            # Windows WASAPI loopback
    ]
    return any(p in name_lower for p in loopback_patterns)
