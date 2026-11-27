"""
core/transcript.py — every conversation, kept word for word, on this PC.

Before this, a conversation lived only in memory and shrank to a one-or-two-sentence summary when the
session ended, so anything the user said (a feature list, a plan) was gone after a restart. Now each
line the user says and Jarvis answers is appended to memory/conversations/YYYY-MM-DD.md as it happens,
and plugins/conversation_history.py lets Jarvis search and read it back. The folder is git-ignored and
never leaves the PC. Turn it off in CONVERSATION & PRESENCE ("Keep a full log of our conversations").
"""
from __future__ import annotations

import datetime as dt
import os
import re
import threading
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "memory" / "conversations"
_lock = threading.Lock()


def enabled() -> bool:
    try:
        from memory.config_manager import get_plugin_setting
        return bool(get_plugin_setting("conversation", "keep_transcript", True))
    except Exception:
        return True


def _file(day: dt.date) -> Path:
    return DIR / f"{day.isoformat()}.md"


def append(speaker: str, text: str) -> None:
    text = (text or "").strip()
    if not text or not enabled():
        return
    now = dt.datetime.now()
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        with _lock, open(_file(now.date()), "a", encoding="utf-8") as f:
            f.write(f"{now:%H:%M}  {speaker}: {text}\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        print(f"[Transcript] {e}")


def day_of(when: str) -> dt.date:
    w = (when or "today").strip().lower()
    today = dt.date.today()
    if w in ("", "today"):
        return today
    if w == "yesterday":
        return today - dt.timedelta(days=1)
    m = re.match(r"(\d+)\s*days?\s*ago", w)
    if m:
        return today - dt.timedelta(days=int(m.group(1)))
    return dt.date.fromisoformat(w)


def read(when: str = "today", last: int = 80) -> str:
    p = _file(day_of(when))
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-last:])


_SUFFIX = re.compile(r"(ings?|ed|es|s)$")


def _stem(word: str) -> str:
    """'features' -> 'feature', 'planned' -> 'plann': close enough to find a line by its words."""
    w = word.lower()
    return _SUFFIX.sub("", w) if len(w) > 4 else w


def search(query: str, days: int = 30, limit: int = 40) -> list[str]:
    stop = {"the", "and", "for", "you", "what", "did", "about", "that", "this", "with", "told", "said", "tell"}
    words = [_stem(w) for w in re.findall(r"\w+", (query or "").lower()) if len(w) > 2 and w not in stop]
    if not words:
        return []
    hits = []
    today = dt.date.today()
    for i in range(days):
        day = today - dt.timedelta(days=i)
        p = _file(day)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            low = line.lower()
            if all(w in low for w in words) or (len(words) > 2 and sum(w in low for w in words) >= len(words) - 1):
                hits.append(f"{day.isoformat()} {line}")
        if len(hits) >= limit:
            break
    return hits[:limit]
