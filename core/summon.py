"""
core/summon.py — a global key chord (default Ctrl+Alt+J) that brings JARVIS to the front
from any window, the way an assistant built into the system would feel.

Windows: GetAsyncKeyState polled by one small thread (the same approach as core/hotkey.py,
which needs no message loop and no extra package); fires once per press. Elsewhere the
chord is bound as a window shortcut by the caller, so `scope` says which one you got.
"""
from __future__ import annotations

import platform
import threading
import time
from typing import Callable

VK_CONTROL, VK_MENU, VK_J = 0x11, 0x12, 0x4A
VK_S, VK_M = 0x53, 0x4D        # Ctrl+Alt+S: stop talking · Ctrl+Alt+M: mute / unmute


class Summon:
    def __init__(self, on_press: Callable[[], None], poll: float = 0.05):
        self._cb, self._poll = on_press, poll
        self._extra: dict[tuple, Callable[[], None]] = {}     # more chords, e.g. stop talking from anywhere
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.scope = "global" if platform.system() == "Windows" else "window"
        self._down = lambda vk: False
        if platform.system() == "Windows":
            try:
                import ctypes
                f = ctypes.windll.user32.GetAsyncKeyState
                self._down = lambda vk: bool(f(vk) & 0x8000)
            except Exception:
                self.scope = "window"

    def start(self) -> None:
        if self.scope != "global" or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="summon_hotkey", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def add(self, keys: tuple, on_press: Callable[[], None]) -> None:
        """Another global chord (virtual-key codes, all held together)."""
        self._extra[tuple(keys)] = on_press

    def _chord(self) -> bool:
        return self._down(VK_CONTROL) and self._down(VK_MENU) and self._down(VK_J)

    def _loop(self) -> None:
        was = False
        was_extra: dict[tuple, bool] = {}
        while not self._stop.is_set():
            now = self._chord()
            if now and not was:                 # once per press, not once per poll
                try:
                    self._cb()
                except Exception as e:
                    print(f"[Summon] {e}")
            was = now
            for keys, cb in list(self._extra.items()):
                held = all(self._down(k) for k in keys)
                if held and not was_extra.get(keys):
                    try:
                        cb()
                    except Exception as e:
                        print(f"[Summon] {e}")
                was_extra[keys] = held
            time.sleep(self._poll)
