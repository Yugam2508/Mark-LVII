"""
core/aec.py — hear the user over JARVIS's own voice, the way video calls do.

WHY
    Talking over JARVIS should stop it. On a laptop's speakers the microphone
    hears JARVIS as loudly as it hears you, so "is the mic loud?" can't tell
    the two apart, and core/echo.py's spectral comparison could only guess:
    two voices look alike in coarse bands. In practice interrupting rarely
    worked.

WHAT
    Real acoustic echo cancellation — the WebRTC module every video-call app
    uses, from the `livekit` package (prebuilt for Windows, macOS and Linux).
    It is told what is being played and removes it from the microphone signal.
    What is left is you. Measured on a simulated laptop (echo as loud as the
    user, speaker-to-mic delay 40-400 ms, the delay hint off by 300 ms): the
    echo left over is 0.0006, a voice 0.010-0.035 — 13 to 54 times louder.

    Then the decision is simple and fast: clean level above a floor learned
    from this room's leftover echo, counted with a leaky score (a pause
    between syllables lowers it, it doesn't reset it), about a quarter of a
    second of speech to interrupt.

    If the package is missing, main.py falls back to core/echo.py.
"""
from __future__ import annotations

import threading
import time

import numpy as np

_FRAME = 160                 # 10 ms at 16 kHz — what the WebRTC module takes
BAR_MIN = 0.0025             # cleaned level a voice must clear, at least
BAR_MULT = 3.0               # ...and this many times what this room's echo leaves
SCORE_TO_FIRE = 4.0          # leaky score (64 ms blocks) before interrupting
VOICED_FRACTION = 0.35       # share of a block's 10 ms slices that must carry a voice
_SR = 16000

try:
    from livekit import rtc as _rtc
except Exception:            # not installed / no wheel for this platform
    _rtc = None


def available() -> bool:
    return _rtc is not None


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst or len(x) == 0:
        return x
    n = int(round(len(x) * dst / src))
    t_src = np.arange(len(x)) / src
    t_dst = np.arange(n) / dst
    return np.interp(t_dst, t_src, x.astype(np.float32)).astype(np.int16)


def _level(x: np.ndarray) -> float:
    if len(x) == 0:
        return 0.0
    f = x.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(f * f)))


class Canceller:
    """Echo canceller + 'is the user talking over us?' detector.

    feed_far()  — from the playback thread, with each batch just before it is
                  written to the speakers (any sample rate, int16 mono)
    process()   — from the microphone callback, with each 16 kHz block; returns
                  (cleaned level, raw level)
    barge()     — from the microphone callback while JARVIS speaks; True when
                  the user has been talking over it long enough to stop
    """

    def __init__(self, delay_ms: int = 40, play_delay_s: float = 0.0):
        if _rtc is None:
            raise RuntimeError("livekit is not installed")
        self._apm = _rtc.AudioProcessingModule(echo_cancellation=True, noise_suppression=True,
                                               high_pass_filter=True, auto_gain_control=False)
        self._apm.set_stream_delay_ms(int(delay_ms))
        self._lock = threading.Lock()
        self._far = np.zeros(0, dtype=np.int16)
        # What JARVIS plays is handed over when it is WRITTEN, but heard only
        # after the speaker buffer drains. Queue it and pass it to the canceller
        # at the moment it is actually audible, so the two signals line up.
        self._play_delay = float(play_delay_s)
        self._pending: list[tuple[float, np.ndarray]] = []
        self._near = np.zeros(0, dtype=np.int16)
        self._floor_hist: list[float] = []
        self._floor = 0.004
        self._score = 0.0
        self._blocks_speaking = 0
        self._idle_hist: list[float] = []
        self._idle_floor = 0.0

    def set_play_delay(self, seconds: float) -> None:
        """The speaker buffer's latency (main.py measures it when playback opens)."""
        self._play_delay = max(0.0, min(0.8, float(seconds)))

    def set_delay(self, ms: float) -> None:
        try:
            with self._lock:
                self._apm.set_stream_delay_ms(int(max(0, min(500, ms))))
        except Exception:
            pass

    # ── the far end: what JARVIS is playing ──────────────────────────────
    def feed_far(self, pcm: bytes | np.ndarray, sr: int, now: float | None = None) -> None:
        """Call with each batch as it is written to the speakers."""
        try:
            x = np.frombuffer(pcm, dtype=np.int16) if isinstance(pcm, (bytes, bytearray)) \
                else np.asarray(pcm, dtype=np.int16).reshape(-1)
            x = _resample(x, sr, _SR)
            t = (time.monotonic() if now is None else now) + self._play_delay
            with self._lock:
                # contiguous audio: continue where the queued audio ends
                if self._pending:
                    last_t, last_x = self._pending[-1]
                    t = max(t, last_t + len(last_x) / _SR)
                self._pending.append((t, x))
        except Exception:
            pass

    def _release_far(self, now: float) -> None:
        """Hand the canceller what has become audible by `now` (lock held)."""
        ready, keep = [], []
        for t, x in self._pending:
            if t >= now:
                keep.append((t, x))
                continue
            k = min(len(x), int((now - t) * _SR))
            if k > 0:
                ready.append(x[:k])
            if k < len(x):
                keep.append((t + k / _SR, x[k:]))
        self._pending = keep
        if not ready:
            return
        try:
            buf = np.concatenate([self._far] + ready)
            n = len(buf) // _FRAME * _FRAME
            for i in range(0, n, _FRAME):
                fr = _rtc.AudioFrame(buf[i:i + _FRAME].tobytes(), _SR, 1, _FRAME)
                self._apm.process_reverse_stream(fr)
            self._far = buf[n:]
        except Exception:
            pass       # never disturb the microphone

    # ── the near end: the microphone ─────────────────────────────────────
    def process(self, block, now: float | None = None) -> tuple[float, float]:
        """Run one mic block through the canceller. (clean level, raw level)."""
        clean, raw, _ = self._process(block, now)
        return clean, raw

    def _process(self, block, now: float | None = None) -> tuple[float, float, np.ndarray]:
        """(clean level, raw level, clean level of each 10 ms slice)."""
        x = np.asarray(block, dtype=np.int16).reshape(-1)
        raw = _level(x)
        try:
            with self._lock:
                self._release_far(time.monotonic() if now is None else now)
                buf = np.concatenate([self._near, x])
                n = len(buf) // _FRAME * _FRAME
                out = np.empty(n, dtype=np.int16)
                for i in range(0, n, _FRAME):
                    fr = _rtc.AudioFrame(buf[i:i + _FRAME].tobytes(), _SR, 1, _FRAME)
                    self._apm.process_stream(fr)
                    out[i:i + _FRAME] = np.frombuffer(bytes(fr.data), dtype=np.int16)
                self._near = buf[n:]
            slices = np.array([_level(out[i:i + _FRAME]) for i in range(0, n, _FRAME)]) \
                if n else np.zeros(0)
            return _level(out), raw, slices
        except Exception:
            return raw, raw, np.full(max(1, len(x) // _FRAME), raw)

    def barge(self, block, sensitivity_extra: int = 0, now: float | None = None) -> bool:
        """Call for every mic block while JARVIS is speaking."""
        clean, raw, slices = self._process(block, now)
        self._blocks_speaking += 1
        # The first few blocks of every answer let the canceller settle.
        # (And until this room's leftover echo has been measured at all —
        # only the first answer of a session pays that, about half a second.)
        if self._blocks_speaking <= 3:
            return False
        warm = len(self._floor_hist) >= 6
        bar = max(BAR_MIN, self._floor * BAR_MULT, self._idle_floor * BAR_MULT)
        # A voice fills the block; a key click or a tap fills one 10 ms slice.
        voiced = float(np.mean(slices > bar)) if len(slices) else 0.0
        if voiced >= VOICED_FRACTION and raw > 0.01 and warm:
            self._score += 0.5 + voiced          # a fully voiced block counts 1.5
        else:
            self._score = max(0.0, self._score - 0.5)
            # learn what this room leaves behind when it is only us talking
            self._floor_hist.append(clean)
            if len(self._floor_hist) > 80:
                del self._floor_hist[:-80]
            if len(self._floor_hist) >= 10:
                # 75th percentile: a few key clicks among them don't lift it
                self._floor = float(np.percentile(self._floor_hist, 75))
        if self._score >= SCORE_TO_FIRE + sensitivity_extra:   # ~0.25-0.5 s of you
            self._score = 0.0
            return True
        return False

    def observe_idle(self, block) -> None:
        """Every mic block while JARVIS is silent: keeps the canceller's state
        running and learns this room's background noise after cleaning, so a
        loud fan raises the bar instead of interrupting."""
        clean, _ = self.process(block)
        self._idle_hist.append(clean)
        if len(self._idle_hist) > 150:
            del self._idle_hist[:-150]
        if len(self._idle_hist) >= 10:
            self._idle_floor = float(np.percentile(self._idle_hist, 75))

    def speaking_stopped(self) -> None:
        self._score = 0.0
        self._blocks_speaking = 0

    @property
    def floor(self) -> float:
        return self._floor
