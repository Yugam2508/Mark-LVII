"""
core/handoff.py — start a conversation on one device and carry on on another.

Each running JARVIS writes its last few turns to a small file in the shared sync folder
(the same OneDrive folder that already shares memory — plugins/device_sync.py). When a
JARVIS connects and another device was talking to you more recently, those turns go into
its instructions: "the user was just talking to you on their desktop; this is what was
said". So you walk to the laptop, say "where were we?" or just carry on, and it knows.

Needs device sync switched on (that is what makes the folder shared). Files hold only the
last turns, are overwritten, and are ignored after 30 minutes.
"""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

KEEP_TURNS = 12
FRESH_SECONDS = 30 * 60
_PREFIX = "handoff_"


def device_name() -> str:
    try:
        from memory.config_manager import get_plugin_setting
        n = str(get_plugin_setting("device_link", "device_name", "") or "").strip().lower()
    except Exception:
        n = ""
    return n or socket.gethostname().lower()


def _folder() -> Path | None:
    try:
        from plugins import device_sync
        return device_sync._folder()
    except Exception:
        return None


def _safe(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in "-_") or "device"


def publish(turns: list[str], folder: Path | None = None, name: str | None = None) -> bool:
    folder = folder or _folder()
    if folder is None or not turns:
        return False
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{_PREFIX}{_safe(name or device_name())}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"device": name or device_name(), "at": time.time(),
                                   "turns": [t[:500] for t in turns[-KEEP_TURNS:]]}), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def latest_other(folder: Path | None = None, me: str | None = None,
                 now: float | None = None) -> dict | None:
    """The freshest conversation another device left, or None."""
    folder = folder or _folder()
    if folder is None or not folder.exists():
        return None
    me = _safe(me or device_name())
    now = time.time() if now is None else now
    best = None
    for p in folder.glob(f"{_PREFIX}*.json"):
        if p.stem[len(_PREFIX):] == me:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not d.get("turns") or now - float(d.get("at", 0)) > FRESH_SECONDS:
            continue
        if best is None or d["at"] > best["at"]:
            best = d
    return best
