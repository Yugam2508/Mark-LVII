"""
core/clip_history.py — what you copied, for "what did I copy earlier?".

Kept in memory only (never written to disk: passwords get copied too), the last 40 distinct texts, newest
first. The window feeds it on every clipboard change; plugins/clipboard.py reads it.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_items: list[dict] = []
MAX = 40


def add(text: str) -> None:
    t = (text or "").strip()
    if not t:
        return
    with _lock:
        _items[:] = [i for i in _items if i["text"] != t]
        _items.insert(0, {"text": t[:5000], "at": time.time()})
        del _items[MAX:]


def recent(n: int = 10) -> list[dict]:
    with _lock:
        return [dict(i) for i in _items[:n]]


def find(query: str) -> list[dict]:
    q = (query or "").lower().strip()
    with _lock:
        if q in ("link", "url", "a link", "the link"):
            return [dict(i) for i in _items if "http" in i["text"].lower()]
        words = [w for w in q.split() if len(w) > 2]
        return [dict(i) for i in _items if all(w in i["text"].lower() for w in words)] if words else []


def clear() -> None:
    with _lock:
        _items.clear()
