"""
core/dictation.py — take down what the user says, word for word, without the model in the way.

Why this exists: asking a live voice model to "remember" a long monologue means trusting it to copy
all of it into one tool call, and it summarises, shortens, or just says "got it, saved" and does not.
Here the speech recognition the app already runs is written to a file the moment it arrives (flushed
to disk on every chunk), so nothing said while dictation is on can be lost, whatever the model does.
While it is on, Jarvis stays silent. Saying "end dictation" (caught here, not left to the model)
stops it; the plugin then offers the text to the user's notes and reads back how much was kept.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import threading
from pathlib import Path

_lock = threading.Lock()
_state: dict = {"on": False, "path": None, "title": "", "words": 0, "started": None, "last": None}
_STOP = re.compile(r"\b(end|stop|finish|finished|close)\s+(the\s+)?dictation\b|\bthat'?s\s+(all|everything|it)\s+for\s+(the\s+)?dictation\b|\bdictation\s+(over|done|complete)\b", re.I)
_stop_cb = None


def active() -> bool:
    return bool(_state["on"])


def folder() -> Path:
    try:
        from plugins import knowledge_base
        base = Path(knowledge_base._folder())
    except Exception:
        base = Path(__file__).resolve().parent.parent / "memory"
    d = base / "Dictations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def start(title: str = "", on_stop=None) -> Path:
    global _stop_cb
    with _lock:
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H-%M")
        slug = re.sub(r"[^\w\- ]+", "", title).strip()[:40]
        path = folder() / (f"{stamp}{' ' + slug if slug else ''}.md")
        n = 1
        while path.exists():
            n += 1
            path = path.with_name(f"{path.stem.split(' (')[0]} ({n}).md")
        head = f"# Dictation {stamp}" + (f" — {title}" if title else "") + "\n\n"
        _write(path, head, "w")
        _state.update(on=True, path=path, title=title, words=0, started=dt.datetime.now(), last=dt.datetime.now())
        _stop_cb = on_stop
        return path


def _write(path: Path, text: str, mode: str = "a") -> None:
    with open(path, mode, encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())                    # on disk now, not in a buffer


def feed(text: str) -> bool:
    """Called with each chunk of recognised speech. True if it ended the dictation."""
    if not _state["on"] or not text.strip():
        return False
    stop = bool(_STOP.search(text))
    body = _STOP.sub("", text).strip(" ,.")
    with _lock:
        if body:
            _write(_state["path"], body + " ")
            _state["words"] += len(body.split())
            _state["last"] = dt.datetime.now()
    if stop:
        cb = _stop_cb
        stop_now()
        if cb:
            try:
                threading.Thread(target=cb, daemon=True).start()
            except Exception:
                pass
    return stop


def paragraph() -> None:
    """The speaker paused / a turn ended: start a new line so the file reads naturally."""
    if _state["on"]:
        with _lock:
            _write(_state["path"], "\n\n")


def stop_now() -> dict:
    with _lock:
        info = dict(_state)
        _state.update(on=False)
    return info


def read(path: Path | None = None) -> str:
    p = path or _state["path"]
    return Path(p).read_text(encoding="utf-8") if p and Path(p).exists() else ""


def status() -> dict:
    return dict(_state)
