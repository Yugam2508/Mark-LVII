"""
core/screen_time.py — where the time on this PC goes, by app (and by site in the browser).

Every 30 seconds the app in front is noted (not while you're away from the keyboard for more than two
minutes, unless it's a video playing). Kept per day in memory/conversations' sibling folder
memory/screen_time/ (git-ignored, never leaves the PC). plugins/screen_time.py answers from it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "memory" / "screen_time"
PERIOD = 30.0
_lock = threading.Lock()
_today: dict = {"day": "", "apps": {}}
_started = False

SITES = (("YouTube", r"youtube"), ("Netflix", r"netflix"), ("Instagram", r"instagram"), ("TikTok", r"tiktok"),
         ("Reddit", r"reddit"), ("X / Twitter", r"\btwitter\b|\b- x\b| / x\b"), ("WhatsApp Web", r"whatsapp"),
         ("Gmail", r"gmail|inbox"), ("Google Docs", r"google docs"), ("ChatGPT", r"chatgpt"),
         ("Claude", r"\bclaude\b"), ("Notion", r"notion"), ("Twitch", r"twitch"), ("Prime Video", r"prime video"),
         ("Spotify (web)", r"spotify"), ("GitHub", r"github"), ("Stack Overflow", r"stack overflow"))
BROWSERS = ("chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "arc")
NICE = {"code": "VS Code", "winword": "Word", "excel": "Excel", "powerpnt": "PowerPoint", "explorer": "File Explorer",
        "spotify": "Spotify", "discord": "Discord", "steam": "Steam", "valorant-win64-shipping": "Valorant",
        "windowsterminal": "Terminal", "obsidian": "Obsidian", "notion": "Notion", "teams": "Teams", "ms-teams": "Teams",
        "zoom": "Zoom", "python": "Python", "pythonw": "Jarvis", "studio64": "Android Studio", "idea64": "IntelliJ"}


def label(process: str, title: str) -> str:
    p = (process or "").lower().removesuffix(".exe")
    if not p and not title:
        return ""
    if p in BROWSERS:
        low = (title or "").lower()
        for name, rx in SITES:
            if re.search(rx, low):
                return name
        return "Browsing"
    return NICE.get(p, p.capitalize() if p else (title or "")[:30])


def _file(day: str) -> Path:
    return DIR / f"{day}.json"


def load(day: str) -> dict:
    try:
        return json.loads(_file(day).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _flush() -> None:
    with _lock:
        if not _today["day"]:
            return
        DIR.mkdir(parents=True, exist_ok=True)
        tmp = _file(_today["day"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(_today["apps"]), encoding="utf-8")
        os.replace(tmp, _file(_today["day"]))


def note(app: str, seconds: float, day: str | None = None) -> None:
    if not app:
        return
    day = day or dt.date.today().isoformat()
    with _lock:
        if _today["day"] != day:
            _today.update(day=day, apps=load(day))
        _today["apps"][app] = _today["apps"].get(app, 0) + seconds


def totals(days: int = 1) -> dict[str, float]:
    """Seconds per app over the last `days` days (today included)."""
    out: dict[str, float] = {}
    today = dt.date.today()
    for i in range(days):
        d = (today - dt.timedelta(days=i)).isoformat()
        src = dict(_today["apps"]) if d == _today["day"] else load(d)
        for k, v in src.items():
            out[k] = out.get(k, 0) + float(v)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _loop() -> None:
    from core import foreground, presence
    last_flush = time.time()
    while True:
        time.sleep(PERIOD)
        try:
            app = label(foreground.process_name(), foreground.title())
            idle = presence.idle_seconds()
            watching = app in ("YouTube", "Netflix", "Prime Video", "Twitch")
            if app and (idle < 120 or watching):
                note(app, PERIOD)
            if time.time() - last_flush > 300:
                _flush()
                last_flush = time.time()
        except Exception:
            pass


def start() -> None:
    global _started
    if _started or os.environ.get("JARVIS_NO_BACKGROUND") == "1":
        return
    try:
        from memory.config_manager import get_plugin_setting
        if not get_plugin_setting("conversation", "screen_time", True):
            return
    except Exception:
        pass
    _started = True
    threading.Thread(target=_loop, daemon=True, name="screen_time").start()
