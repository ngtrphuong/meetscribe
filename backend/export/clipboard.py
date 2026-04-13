"""Clipboard export utility — copy meeting notes to system clipboard.

Used by Electron IPC handler and API endpoint for one-click copying.

File: backend/export/clipboard.py
"""

from __future__ import annotations

import asyncio
import sys


async def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard.

    Platform support:
    - Linux: xclip or xsel or wl-copy (Wayland)
    - macOS: pbcopy
    - Windows: clip

    Returns True if successful.
    """
    if sys.platform == "darwin":
        cmd = ["pbcopy"]
    elif sys.platform == "win32":
        cmd = ["clip"]
    else:
        # Linux — try xclip, then xsel, then wl-copy
        import shutil
        if shutil.which("xclip"):
            cmd = ["xclip", "-selection", "clipboard"]
        elif shutil.which("xsel"):
            cmd = ["xsel", "--clipboard", "--input"]
        elif shutil.which("wl-copy"):
            cmd = ["wl-copy"]
        else:
            return False

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=text.encode("utf-8"))
        return proc.returncode == 0
    except Exception:
        return False
