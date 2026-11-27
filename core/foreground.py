"""
core/foreground.py — which window is in front, and whose it is (Windows).

Used where Jarvis must not act blind: WhatsApp presses Enter only when WhatsApp is in front, and the
study focus guard notices YouTube taking over a study block. Returns '' anywhere it can't tell.
"""
from __future__ import annotations

import sys


def title() -> str:
    if not sys.platform.startswith("win"):
        return ""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value
    except Exception:
        return ""


def process_name() -> str:
    if not sys.platform.startswith("win"):
        return ""
    try:
        import ctypes
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        import psutil
        return psutil.Process(pid.value).name()
    except Exception:
        return ""
