"""
core/ops.py — everything Jarvis is busy with in the background, in one place, so it can be seen and stopped.

Long jobs register here (an install, app updates, deep thinking, a speed test, dictation, a backup, the file
index). plugins/operations.py answers "what are you working on?" and "stop that" from it — together with
Claude Code jobs and background agent tasks, which keep their own lists — and each job shows on the HUD as a
satellite while it runs. A job that can't be stopped half-way says so instead of pretending.
"""
from __future__ import annotations

import itertools
import threading
import time
from typing import Callable, Optional

_lock = threading.Lock()
_ids = itertools.count(1)
_ops: list["Op"] = []
_KEEP_DONE = 300.0                # finished jobs stay listed for five minutes


class Op:
    def __init__(self, name: str, kind: str, cancel: Optional[Callable[[], None]]):
        self.id = next(_ids)
        self.name = name
        self.kind = kind
        self.started = time.time()
        self.ended = 0.0
        self.state = "running"            # running | done | failed | cancelled
        self.detail = ""
        self.progress: Optional[float] = None
        self._cancel = cancel
        self.cancelled = threading.Event()

    @property
    def cancellable(self) -> bool:
        return self._cancel is not None

    def update(self, detail: str = "", progress: Optional[float] = None) -> None:
        self.detail = detail or self.detail
        if progress is not None:
            self.progress = max(0.0, min(1.0, progress))

    def finish(self, ok: bool = True, detail: str = "") -> None:
        if self.state == "running":
            self.state = "done" if ok else "failed"
        self.detail = detail or self.detail
        self.ended = time.time()

    def cancel(self) -> bool:
        if self.state != "running" or self._cancel is None:
            return False
        self.cancelled.set()
        try:
            self._cancel()
        except Exception:
            pass
        self.state = "cancelled"
        self.ended = time.time()
        return True

    def line(self) -> str:
        mins = (time.time() - self.started) / 60
        took = f"{mins:.0f} min" if mins >= 1 else f"{(time.time() - self.started):.0f} s"
        pct = f", {self.progress * 100:.0f}%" if self.progress is not None else ""
        stop = "" if self.cancellable else " (can't be stopped half-way)"
        return f"{self.name}: {self.state}{pct}, {took}{(' — ' + self.detail) if self.detail else ''}{stop if self.state == 'running' else ''}"


def start(name: str, kind: str = "task", cancel: Optional[Callable[[], None]] = None) -> Op:
    op = Op(name, kind, cancel)
    with _lock:
        now = time.time()
        _ops[:] = [o for o in _ops if o.state == "running" or now - o.ended < _KEEP_DONE]
        _ops.append(op)
    try:
        from core import addons
        assistant = addons.assistant()
        ui = getattr(assistant, "ui", None)
        if ui is not None and hasattr(ui, "push_context"):
            ui.push_context(name, "agent")
    except Exception:
        pass
    return op


def running() -> list[Op]:
    with _lock:
        return [o for o in _ops if o.state == "running"]


def recent() -> list[Op]:
    with _lock:
        now = time.time()
        return [o for o in _ops if o.state == "running" or now - o.ended < _KEEP_DONE]


def find(name: str) -> list[Op]:
    """Running jobs whose name contains the words given ('install', 'speed'); all running for 'all'/''."""
    q = (name or "").strip().lower()
    ops = running()
    if q in ("", "all", "everything", "that", "it", "last"):
        return ops[-1:] if q in ("that", "it", "last") else ops
    words = [w for w in q.split() if len(w) > 2]
    return [o for o in ops if any(w in o.name.lower() for w in words)]
