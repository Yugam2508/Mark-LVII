"""
core/keepawake.py — keep the PC awake while your phone is connected, so Jarvis is still
there when you message it from lunch.

Windows puts the laptop to sleep after a while, which silently drops the phone link. While a
phone (or the phone page in a browser) is connected, this asks Windows not to sleep — but only
on mains power, so it can't flatten a battery, and only until the phone disconnects. The
screen can still turn off and the PC can still be locked. Closing the lid still sleeps it.

Setting: CONVERSATION & PRESENCE → "Keep this PC awake while my phone is connected".
"""
from __future__ import annotations

import sys
import threading
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
_started = False


def enabled() -> bool:
    try:
        from memory.config_manager import get_plugin_setting
        return bool(get_plugin_setting("conversation", "keep_awake_for_phone", True))
    except Exception:
        return True


def on_mains() -> bool:
    """True on a desktop or a plugged-in laptop; False only when running on battery."""
    try:
        import psutil
        b = psutil.sensors_battery()
        return b is None or bool(b.power_plugged)
    except Exception:
        return False


def phone_linked() -> bool:
    try:
        from core import addons
        d = getattr(addons.assistant(), "_dashboard", None)
        return bool(d is not None and (d._phones or d._clients))
    except Exception:
        return False


def wanted() -> bool:
    return enabled() and phone_linked() and on_mains()


def _set(flags: int) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def _loop(period: float = 30.0) -> None:
    # The execution state belongs to the thread that set it, so this thread sets it and
    # keeps living; it is cleared the moment the phone goes or the setting changes.
    held = False
    while True:
        want = wanted()
        if want:
            _set(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        elif held:
            _set(ES_CONTINUOUS)
        held = want
        time.sleep(period)


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="keepawake", daemon=True).start()
