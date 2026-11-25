"""
core/presence.py — is the user free to be spoken to right now?

    free   at the PC and not busy: JARVIS can just say things
    busy   talking to someone else, on a call, gaming or watching something:
           things go on screen as cards that stay until dismissed, no speech
    away   no keyboard or mouse for a while: cards stay on screen, and the phone
           gets a notification (plugins/phone_alerts.py)

Busy comes from any of:
    * you said so ("I'm talking to someone", "I'm on a call") — plugins/conversation.py
    * you just spoke and the assistant judged it was not meant for it (main.py
      calls note_not_addressed() when a turn of your speech gets no reply)
    * another app is using the microphone — Discord, Zoom, Teams, a browser call
      (Windows records this; JARVIS's own use is ignored)
    * gaming or watching mode is on

Standard library only (winreg/ctypes on Windows), so the routines engine and the
task engine can ask without importing the GUI.
"""
from __future__ import annotations

import sys
import threading
import time

_lock = threading.Lock()
_busy_until = 0.0
_busy_reason = ""
_not_addressed_at = 0.0
NOT_ADDRESSED_WINDOW = 120.0      # seconds a not-for-me remark keeps us quiet
_SELF = ("python", "pythonw", "jarvis")


def _setting(key: str, default):
    try:
        from memory.config_manager import get_plugin_setting
        v = get_plugin_setting("conversation", key, default)
        return default if v in (None, "") else v
    except Exception:
        return default


def idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input (0 when it can't be known)."""
    if sys.platform != "win32":
        return 0.0
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0
    except Exception:
        return 0.0


def mic_in_use_by() -> str:
    """Name of another app using the microphone right now ('' if none / unknown)."""
    if sys.platform != "win32":
        return ""
    try:
        import winreg
        base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
        for path in (base + r"\NonPackaged", base):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                if name == "NonPackaged":
                    continue
                try:
                    with winreg.OpenKey(key, name) as sub:
                        start = winreg.QueryValueEx(sub, "LastUsedTimeStart")[0]
                        stop = winreg.QueryValueEx(sub, "LastUsedTimeStop")[0]
                except OSError:
                    continue
                if start and not stop:
                    app = name.replace("#", "\\").split("\\")[-1].split("_")[0]
                    if not any(s in app.lower() for s in _SELF):
                        return app.replace(".exe", "")
    except Exception:
        pass
    return ""


def set_busy(minutes: float, reason: str = "talking to someone") -> None:
    global _busy_until, _busy_reason
    with _lock:
        _busy_until = time.time() + max(1.0, minutes) * 60
        _busy_reason = reason


def clear_busy() -> None:
    global _busy_until, _not_addressed_at
    with _lock:
        _busy_until = 0.0
        _not_addressed_at = 0.0


def note_not_addressed() -> None:
    """The user spoke and it wasn't to the assistant."""
    global _not_addressed_at
    with _lock:
        _not_addressed_at = time.time()


def state() -> tuple[str, str]:
    """('free' | 'busy' | 'away', why)."""
    away_after = float(_setting("away_minutes", 10)) * 60
    if idle_seconds() >= away_after:
        return "away", f"no input for {int(idle_seconds() // 60)} min"
    now = time.time()
    with _lock:
        if now < _busy_until:
            return "busy", _busy_reason or "busy"
        if now - _not_addressed_at < NOT_ADDRESSED_WINDOW:
            return "busy", "talking to someone else"
    app = mic_in_use_by()
    if app:
        return "busy", f"on a call ({app})"
    try:
        from core import addons
        mode = addons.mode_policy().get("mode")
        if mode in ("gaming", "watching"):
            return "busy", f"{mode} mode"
    except Exception:
        pass
    return "free", ""
