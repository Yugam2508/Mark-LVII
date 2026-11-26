"""
core/phone_wake.py — "Hey Jarvis" for the phone, heard by the PC.

The phone sends what its microphone hears while someone is talking (Android/LiveAudio + SpeechGate). With
the wake word on, nothing of it reaches Gemini until the PC's own "Hey Jarvis" detector (core/wake_word.py,
openWakeWord) hears the phrase in that audio. Then the last moment of audio is passed on too — so
"Hey Jarvis, what's the weather" arrives whole — and the conversation flows normally until it has been
quiet for the follow-up window, when it waits for "Hey Jarvis" again. Tapping the orb in the app wakes it
without the phrase. The phone is told each change so it can chime, buzz and show the state.

No model runs on the phone: it stays a thin client, and the PC already has the detector.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Optional

SAMPLE_RATE = 16000
CHUNK = 1280                     # openWakeWord's natural step: 80 ms at 16 kHz


class PhoneWake:
    def __init__(self, detector_factory: Callable[[Callable[[], None]], object],
                 on_state: Callable[[bool], None], follow_up: float = 45.0, preroll_s: float = 1.6):
        self._factory = detector_factory
        self._on_state = on_state
        self.follow_up = follow_up
        self._preroll = deque()
        self._preroll_bytes = 0
        self._preroll_max = int(SAMPLE_RATE * 2 * preroll_s)
        self._pending = bytearray()              # audio waiting to make up a whole detector chunk
        self._detected = threading.Event()
        self._detector = None
        self.available: Optional[bool] = None   # None = not tried yet
        self._retry_at = 0.0
        self.awake = False
        self.awake_until = 0.0

    # ── the detector ─────────────────────────────────────────────────────────
    def _ensure(self) -> bool:
        now = time.monotonic()
        if self.available is None or (self.available is False and now >= self._retry_at):
            try:
                self._detector = self._factory(self._detected.set)
                self.available = bool(getattr(self._detector, "ready", True))
            except Exception:
                self._detector, self.available = None, False
            if not self.available:
                self._retry_at = now + 60.0            # it may be being set up: try again in a minute
        return bool(self.available)

    def _feed_detector(self, data: bytes) -> None:
        self._pending.extend(data)
        while len(self._pending) >= CHUNK * 2:
            frame = bytes(self._pending[:CHUNK * 2])
            del self._pending[:CHUNK * 2]
            try:
                import numpy as np
                self._detector.feed(np.frombuffer(frame, dtype=np.int16))
            except Exception:
                try:
                    self._detector.feed(frame)
                except Exception:
                    pass

    def _remember(self, data: bytes) -> None:
        self._preroll.append(data)
        self._preroll_bytes += len(data)
        while self._preroll_bytes > self._preroll_max and self._preroll:
            self._preroll_bytes -= len(self._preroll.popleft())

    # ── state ────────────────────────────────────────────────────────────────
    def _set(self, awake: bool, now: float) -> None:
        if awake == self.awake:
            if awake:
                self.awake_until = now + self.follow_up
            return
        self.awake = awake
        self.awake_until = now + self.follow_up if awake else 0.0
        if not awake:
            self._detected.clear()
            try:
                self._detector.reset()
            except Exception:
                pass
        try:
            self._on_state(awake)
        except Exception:
            pass

    def wake_now(self, now: Optional[float] = None) -> None:
        self._set(True, now if now is not None else time.monotonic())

    def sleep_now(self, now: Optional[float] = None) -> None:
        self._set(False, now if now is not None else time.monotonic())

    def keep_awake(self, now: Optional[float] = None) -> None:
        """Jarvis is talking (or working): the follow-up window starts again from now."""
        if self.awake:
            self.awake_until = (now if now is not None else time.monotonic()) + self.follow_up

    def tick(self, now: Optional[float] = None) -> None:
        now = now if now is not None else time.monotonic()
        if self.awake and now > self.awake_until:
            self._set(False, now)

    # ── audio ────────────────────────────────────────────────────────────────
    def process(self, data: bytes, now: Optional[float] = None) -> list[bytes]:
        """The audio to pass on to Gemini for this chunk from the phone (often none while asleep)."""
        now = now if now is not None else time.monotonic()
        self.tick(now)
        if self.awake:
            self.awake_until = now + self.follow_up       # they're still talking
            return [data]
        if not self._ensure():
            return [data]                                 # no detector on this PC: listen to everything
        self._remember(data)
        self._feed_detector(data)
        if self._detected.is_set():
            return self._release(now)                     # the phrase and whatever followed it
        return []

    def check_detected(self, now: Optional[float] = None) -> list[bytes]:
        """The detector runs on its own thread and may fire between chunks: pass the held audio on then."""
        if not self.awake and self._detected.is_set():
            return self._release(now)
        return []

    def _release(self, now: Optional[float]) -> list[bytes]:
        now = now if now is not None else time.monotonic()
        self._detected.clear()
        out = list(self._preroll)
        self._preroll.clear()
        self._preroll_bytes = 0
        self._set(True, now)
        return out
