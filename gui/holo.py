"""gui/holo.py — the holographic centrepiece, and the satellites that show what JARVIS is doing.

An original design built from the vocabulary of sci-fi interfaces — segmented
rings, tick dials, a radial spectrum, a scanning sweep — drawn with the same
software QPainter as the rest of the HUD (no GPU, no images).

Everything on it means something:
    tick dial          turns slowly; faster while thinking
    segment ring       the state colour: green listening, gold thinking, accent speaking
    sweep              only while thinking — a radar arm working the problem
    spectrum ring      the real audio level (your mic while listening, the voice while speaking)
    ripples            a pulse leaves the core on each loud moment
    core               brightens with the voice; the name and state sit inside it

SATELLITES are the "stuff moves around based on what we're doing" part. Each tool
JARVIS uses, each panel it opens and each card it leaves becomes a small labelled
node that flies out of the core along a beam, pulses while it is fresh, takes up
an orbit and drifts, then fades after a few minutes. Glance at the HUD and you see
what it has been doing: SPOTIFY, GMAIL, CLAUDE CODE, CALENDAR.
"""
from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QPainter, QPainterPath,
                         QPen, QRadialGradient)

from gui.style import px_font, with_alpha

KIND_TONE = {"tool": "PRI", "panel": "ACC", "notice": "ACC2", "agent": "GREEN", "error": "MUTED_C"}
_LIFE = 240.0          # seconds a satellite stays
_FADE = 30.0           # of which the last part fades
_MAX_SATS = 7

# Tool names that read better another way on a 10-letter tag.
_NICE = {"gmail_control": "GMAIL", "calendar_control": "CALENDAR", "spotify_control": "SPOTIFY",
         "claude_code": "CLAUDE CODE", "todo_list": "TO-DO", "home_assistant": "HOME",
         "google_drive": "DRIVE", "web_search": "WEB", "screen_process": "SCREEN",
         "save_memory": "MEMORY", "life_profile": "MEMORY", "background_tasks": "TASKS",
         "device_link": "DEVICES", "phone_alerts": "PHONE", "knowledge_base": "KNOWLEDGE",
         "agent_watch": "AGENTS", "proactive_alerts": "ALERTS", "money_tracker": "MONEY",
         "reading_list": "READ LATER", "study_timer": "STUDY", "daily_briefing": "BRIEFING",
         "conversation": "PRESENCE", "browser_control": "BROWSER", "dev_agent": "CODE"}


def nice_label(raw: str) -> str:
    raw = (raw or "").strip()
    if raw in _NICE:
        return _NICE[raw]
    s = raw.split(" — ")[0]
    if ":" in s:                       # "Done: laptop research" -> the subject
        s = s.split(":", 1)[1].strip() or s.split(":", 1)[0]
    for suffix in ("_control", "_agent", "_tool"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s.replace("_", " ").upper()[:16] or "?"


class HoloCore:
    """State, animation and painting for the 'holo' HUD style."""

    def __init__(self):
        self._t = 0.0
        self._spin = 0.0          # integrated so a speed change never jumps
        self._sweep = 0.0
        self._sweep_a = 0.0       # sweep visibility, eased
        self._ripples: list[list[float]] = []   # [age, strength]
        self._last_peak = 0.0
        self._bands = [0.0] * 72
        self.sats: list[dict] = []
        # Living layers (Mark LX): a turning wireframe globe in the core, a field of drifting motes with
        # depth, live readouts around the dial, and a slight tilt toward the mouse.
        rnd = random.Random(7)
        self._motes = [{"a": rnd.uniform(0, 2 * math.pi), "d": rnd.uniform(0.55, 1.7), "z": rnd.uniform(0.25, 1.0),
                        "sp": rnd.uniform(0.02, 0.09) * rnd.choice((-1, 1)), "ph": rnd.uniform(0, 6.3)}
                       for _ in range(70)]
        self.tilt = (0.0, 0.0)           # -1..1 each way, set by the HUD from the mouse position
        self._tilt_e = [0.0, 0.0]        # eased
        self._read = {"CPU": 0.0, "MEM": 0.0, "NET": 0.0, "GPU": 0.0}
        self._mode = "idle"
        self._beams: list[dict] = []      # projection beams from the core to a card that just appeared

    # ── satellites ───────────────────────────────────────────────────────
    def push(self, label: str, kind: str = "tool") -> None:
        """A new thing JARVIS is doing. Re-pushing an existing label refreshes it."""
        name = nice_label(label)
        now = time.time()
        for s in self.sats:
            if s["label"] == name:
                s.update(born=now, kind=kind, fresh=now)
                return
        angle = self._free_angle()
        self.sats.append({"label": name, "kind": kind, "born": now, "fresh": now,
                          "angle": angle, "out": 0.0,
                          "drift": random.choice((-1, 1)) * random.uniform(0.025, 0.05)})
        if len(self.sats) > _MAX_SATS:
            self.sats.pop(0)

    def _free_angle(self) -> float:
        """The middle of the widest gap between existing satellites (avoids top/bottom text)."""
        if not self.sats:
            return math.radians(-35)
        angs = sorted(s["angle"] % (2 * math.pi) for s in self.sats)
        gaps = [((angs[(i + 1) % len(angs)] - a) % (2 * math.pi) or 2 * math.pi, a)
                for i, a in enumerate(angs)]
        gap, start = max(gaps)
        return start + gap / 2

    def beam(self, x: float, y: float, colour: str = "") -> None:
        """A card just appeared at (x, y): project a beam to it from the core for a moment."""
        self._beams.append({"x": x, "y": y, "born": time.time(), "col": colour})
        del self._beams[:-6]

    # ── animation ───────────────────────────────────────────────────────
    def step(self, dt: float, amp: float, speaking: bool, thinking: bool,
             listening: bool, muted: bool) -> None:
        dt = min(0.1, max(0.0, dt))
        self._t += dt
        rate = 0.12 + (0.55 if thinking else 0.0) + (0.25 if speaking else 0.0)
        if muted:
            rate = 0.03
        self._spin += rate * dt
        self._sweep += (2.4 if thinking else 0.6) * dt
        self._sweep_a += ((1.0 if thinking else 0.0) - self._sweep_a) * min(1.0, dt * 4)

        # spectrum: smoothed pseudo-bands driven by the real level
        live = (speaking or listening) and not muted
        for i in range(len(self._bands)):
            wob = (0.5 + 0.5 * math.sin(self._t * 7.0 + i * 0.9)) * \
                  (0.6 + 0.4 * math.sin(self._t * 3.1 + i * 2.3))
            target = (amp * (0.35 + 0.95 * wob)) if live else 0.0
            k = 0.45 if target > self._bands[i] else 0.12
            self._bands[i] += (target - self._bands[i]) * k

        # a ripple on each new loud moment
        if not muted and amp > 0.35 and amp > self._last_peak * 1.25 and \
                (not self._ripples or self._ripples[-1][0] > 0.35):
            self._ripples.append([0.0, min(1.0, amp)])
        self._last_peak = max(amp, self._last_peak * 0.92)
        for r in self._ripples:
            r[0] += dt
        self._ripples = [r for r in self._ripples if r[0] < 1.6][-6:]

        now = time.time()
        for s in self.sats:
            s["out"] = min(1.0, s["out"] + dt * 1.4)
            s["angle"] += s["drift"] * dt
        self.sats = [s for s in self.sats if now - s["born"] < _LIFE]

        # motes: drawn in while listening, blown out by the voice, wandering when idle
        self._mode = "speak" if speaking else "think" if thinking else "listen" if (listening and not muted) else "idle"
        push = {"speak": 0.10 + 0.55 * amp, "think": 0.02, "listen": -0.06, "idle": 0.0}[self._mode]
        for m in self._motes:
            m["a"] += m["sp"] * dt * (2.2 if thinking else 1.0)
            m["d"] += push * dt * (0.4 + m["z"])
            m["ph"] += dt * (1.5 + m["z"])
            if m["d"] > 1.75:
                m["d"] = 0.55
            elif m["d"] < 0.5:
                m["d"] = 1.7
        # the mouse tilt eases in, so the hologram leans rather than jumps
        for i in (0, 1):
            self._tilt_e[i] += (self.tilt[i] - self._tilt_e[i]) * min(1.0, dt * 3.0)
        # live readouts, eased toward the sampler's values
        try:
            from gui import metrics as _m
            src = {"CPU": _m._metrics.cpu / 100.0, "MEM": _m._metrics.mem / 100.0,
                   "NET": min(1.0, _m._metrics.net / 5.0), "GPU": max(0.0, _m._metrics.gpu) / 100.0}
        except Exception:
            src = {}
        for k, v in src.items():
            self._read[k] += (max(0.0, min(1.0, v)) - self._read[k]) * min(1.0, dt * 2.0)

    # ── painting ────────────────────────────────────────────────────────
    def paint(self, p: QPainter, cx: float, cy: float, r: float, main: QColor, acc: QColor,
              white: QColor, tone, amp: float, name: str, state: str, W: float, H: float,
              muted: bool) -> None:
        """`tone(key)` maps a KIND_TONE key ('PRI', 'ACC'…) to a QColor."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tx, ty = self._tilt_e
        self._paint_glow(p, cx + tx * 10, cy + ty * 8, r, acc, amp)
        self._paint_motes(p, cx, cy, r, main, acc, tx, ty)
        self._paint_sats(p, cx, cy, r, tone, W, H, main)
        self._paint_readouts(p, cx + tx * 3, cy + ty * 3, r, main, acc, W)
        self._paint_dial(p, cx, cy, r, main, acc)
        self._paint_segments(p, cx, cy, r * 0.86, acc, main)
        self._paint_sweep(p, cx, cy, r, acc)
        self._paint_spectrum(p, cx, cy, r * 0.50, r * 0.70, acc, main)
        self._paint_ripples(p, cx, cy, r, acc)
        self._paint_core(p, cx - tx * 4, cy - ty * 3, r * 0.40, main, acc, white, amp, name, state, muted)
        self._paint_beams(p, cx, cy, r, acc)
        p.restore()

    def _paint_beams(self, p, cx, cy, r, acc):
        now = time.time()
        self._beams = [b for b in self._beams if now - b["born"] < 0.9]
        for b in self._beams:
            k = (now - b["born"]) / 0.9
            col = QColor(b["col"]) if b["col"] else acc
            a = math.atan2(b["y"] - cy, b["x"] - cx)
            sx, sy = cx + math.cos(a) * r * 0.42, cy + math.sin(a) * r * 0.42
            # the beam reaches out over the first third, then fades
            reach = min(1.0, k / 0.33)
            ex, ey = sx + (b["x"] - sx) * reach, sy + (b["y"] - sy) * reach
            alpha = 0.85 * (1.0 - max(0.0, (k - 0.33) / 0.67))
            for w_, a_ in ((6.0, 0.12), (2.4, 0.35), (1.0, 0.95)):
                p.setPen(QPen(with_alpha(col, a_ * alpha), w_, cap=Qt.PenCapStyle.RoundCap))
                p.drawLine(QLineF(sx, sy, ex, ey))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(with_alpha(col, 0.9 * alpha))
            p.drawEllipse(QPointF(ex, ey), 3.0, 3.0)
        p.setBrush(Qt.BrushStyle.NoBrush)

    # ── living layers ───────────────────────────────────────────────────
    def _paint_motes(self, p, cx, cy, r, main, acc, tx, ty):
        p.setPen(Qt.PenStyle.NoPen)
        col = acc if self._mode in ("speak", "listen") else main
        for m in self._motes:
            z = m["z"]
            x = cx + math.cos(m["a"]) * m["d"] * r + tx * 14 * z
            y = cy + math.sin(m["a"]) * m["d"] * r * 0.82 + ty * 10 * z
            tw = 0.55 + 0.45 * math.sin(m["ph"])
            edge = min(1.0, max(0.0, (1.75 - m["d"]) / 0.3), max(0.0, (m["d"] - 0.5) / 0.15))
            p.setBrush(with_alpha(col, (0.10 + 0.45 * z) * tw * edge))
            p.drawEllipse(QPointF(x, y), 0.8 + 1.5 * z, 0.8 + 1.5 * z)

    def _paint_readouts(self, p, cx, cy, r, main, acc, W):
        """Four small live gauges around the dial: processor, memory, network, graphics."""
        rr = r * 1.21
        rect = QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr)
        spots = (("CPU", 207), ("MEM", 243), ("NET", 297), ("GPU", 333))   # degrees, clockwise from 3 o'clock
        p.setFont(px_font(max(8, r * 0.055), QFont.Weight.DemiBold, mono=True, spacing=1.0))
        for key, deg in spots:
            v = self._read.get(key, 0.0)
            span = 26
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(with_alpha(main, 0.22), 3.0, cap=Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, int(-(deg - span / 2) * 16), int(-span * 16))
            hot = v > 0.85
            p.setPen(QPen(with_alpha(acc if not hot else QColor(255, 90, 70), 0.85), 3.0, cap=Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, int(-(deg - span / 2) * 16), int(-span * max(0.02, v) * 16))
            a = math.radians(deg)
            lx, ly = cx + math.cos(a) * (rr + r * 0.07), cy + math.sin(a) * (rr + r * 0.07)
            label = f"{key} {v * 100:.0f}%" if key != "NET" else f"NET {v * 5:.1f}MB/s"
            box = QRectF(lx - 50, ly - 8, 100, 16)
            p.setPen(QPen(with_alpha(main, 0.65)))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_globe(self, p, cx, cy, R, main):
        """A wireframe globe turning inside the core: meridians and parallels in 3-D, the back half faint."""
        yaw, tilt = self._spin * 0.9, 0.38
        ct, st = math.cos(tilt), math.sin(tilt)

        def proj(lat, lon):
            x = math.cos(lat) * math.sin(lon)
            y = math.sin(lat)
            z = math.cos(lat) * math.cos(lon)
            y2, z2 = y * ct - z * st, y * st + z * ct
            return cx + x * R, cy + y2 * R, z2

        lines = []
        for k in range(8):                                   # meridians
            lon = yaw + k * math.pi / 8
            prev = None
            for i in range(25):
                lat = -math.pi / 2 + i * math.pi / 24
                pt = proj(lat, lon)
                if prev:
                    lines.append((prev, pt))
                prev = pt
        for lat_deg in (-60, -30, 0, 30, 60):                # parallels
            lat = math.radians(lat_deg)
            prev = None
            for i in range(37):
                pt = proj(lat, yaw + i * 2 * math.pi / 36)
                if prev:
                    lines.append((prev, pt))
                prev = pt
        for (x1, y1, z1), (x2, y2, z2) in lines:
            front = (z1 + z2) / 2
            p.setPen(QPen(with_alpha(main, 0.07 + 0.22 * max(0.0, front)), 1))
            p.drawLine(QLineF(x1, y1, x2, y2))

    def _paint_glow(self, p, cx, cy, r, acc, amp):
        g = QRadialGradient(QPointF(cx, cy), r * 1.25)
        g.setColorAt(0.0, with_alpha(acc, 0.20 + 0.25 * amp))
        g.setColorAt(0.45, with_alpha(acc, 0.06 + 0.06 * amp))
        g.setColorAt(1.0, with_alpha(acc, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r * 1.25, r * 1.25)

    def _paint_dial(self, p, cx, cy, r, main, acc):
        # outer hairline + 120 ticks, every 10th long, slowly turning
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(with_alpha(main, 0.35), 1))
        p.drawEllipse(QPointF(cx, cy), r * 1.06, r * 1.06)
        base = self._spin * 0.35
        for i in range(120):
            a = base + i * (2 * math.pi / 120)
            long_ = i % 10 == 0
            r0 = r * (0.95 if long_ else 0.985)
            c, s = math.cos(a), math.sin(a)
            p.setPen(QPen(with_alpha(main, 0.85 if long_ else 0.35), 1.6 if long_ else 1))
            p.drawLine(QLineF(cx + c * r0, cy + s * r0, cx + c * r * 1.03, cy + s * r * 1.03))
        # two counter-turning bracket arcs outside the dial
        p.setPen(QPen(with_alpha(acc, 0.75), 2.2, cap=Qt.PenCapStyle.FlatCap))
        rr = r * 1.13
        rect = QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr)
        b2 = -self._spin * 0.6
        for k in range(2):
            start = math.degrees(b2) + k * 180
            p.drawArc(rect, int(start * 16), int(38 * 16))
            p.drawArc(rect, int((start + 44) * 16), int(6 * 16))

    def _paint_segments(self, p, cx, cy, r, acc, main):
        # three arcs of different lengths, turning against the dial
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        base = -math.degrees(self._spin * 1.1)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for start, span, w, a in ((0, 96, 5.0, 0.95), (120, 60, 5.0, 0.7), (205, 128, 3.0, 0.55)):
            p.setPen(QPen(with_alpha(acc, a), w, cap=Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, int((base + start) * 16), int(span * 16))
        # dashed inner guide with two markers
        ri = r * 0.88
        pen = QPen(with_alpha(main, 0.35), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawEllipse(QPointF(cx, cy), ri, ri)
        for k in (0, math.pi):
            a = self._spin * 1.8 + k
            mx, my = cx + math.cos(a) * ri, cy + math.sin(a) * ri
            path = QPainterPath()
            path.moveTo(mx + math.cos(a) * 6, my + math.sin(a) * 6)
            path.lineTo(mx + math.cos(a + 2.4) * 5, my + math.sin(a + 2.4) * 5)
            path.lineTo(mx + math.cos(a - 2.4) * 5, my + math.sin(a - 2.4) * 5)
            path.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(with_alpha(acc, 0.9))
            p.drawPath(path)
        p.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_sweep(self, p, cx, cy, r, acc):
        if self._sweep_a < 0.02:
            return
        g = QConicalGradient(QPointF(cx, cy), -math.degrees(self._sweep))
        g.setColorAt(0.0, with_alpha(acc, 0.45 * self._sweep_a))
        g.setColorAt(0.12, with_alpha(acc, 0.0))
        g.setColorAt(1.0, with_alpha(acc, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r * 0.98, r * 0.98)
        p.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_spectrum(self, p, cx, cy, r0, r1, acc, main):
        n = len(self._bands)
        span = r1 - r0
        for i, v in enumerate(self._bands):
            a = -math.pi / 2 + i * (2 * math.pi / n)
            h = 2.0 + span * min(1.0, v)
            c, s = math.cos(a), math.sin(a)
            col = with_alpha(acc if v > 0.08 else main, 0.35 + 0.6 * min(1.0, v * 1.4))
            p.setPen(QPen(col, 2.2, cap=Qt.PenCapStyle.FlatCap))
            p.drawLine(QLineF(cx + c * r0, cy + s * r0, cx + c * (r0 + h), cy + s * (r0 + h)))

    def _paint_ripples(self, p, cx, cy, r, acc):
        p.setBrush(Qt.BrushStyle.NoBrush)
        for age, strength in self._ripples:
            k = age / 1.6
            rr = r * (0.42 + 0.75 * k)
            p.setPen(QPen(with_alpha(acc, (1 - k) * 0.55 * strength), 1.5))
            p.drawEllipse(QPointF(cx, cy), rr, rr)

    def _paint_core(self, p, cx, cy, r, main, acc, white, amp, name, state, muted):
        lift = 1.0 + 0.10 * amp
        rr = r * lift
        g = QRadialGradient(QPointF(cx, cy), rr)
        g.setColorAt(0.0, with_alpha(acc, 0.30 + 0.35 * amp))
        g.setColorAt(0.75, with_alpha(acc, 0.08))
        g.setColorAt(1.0, with_alpha(acc, 0.0))
        p.setPen(QPen(with_alpha(main, 0.8), 1.4))
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), rr, rr)
        p.setBrush(Qt.BrushStyle.NoBrush)
        self._paint_globe(p, cx, cy, rr * 0.92, main)
        # hexagon frame inside the core, slowly turning
        hex_ = QPainterPath()
        for k in range(7):
            a = self._spin * 0.5 + k * math.pi / 3
            pt = QPointF(cx + math.cos(a) * rr * 0.82, cy + math.sin(a) * rr * 0.82)
            hex_.moveTo(pt) if k == 0 else hex_.lineTo(pt)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(with_alpha(main, 0.30), 1))
        p.drawPath(hex_)
        # name and a tiny clock-ish readout
        p.setPen(QPen(with_alpha(white, 0.92)))
        p.setFont(px_font(max(10, rr * 0.30), QFont.Weight.DemiBold, spacing=max(1.0, rr * 0.05)))
        label = (name or "JARVIS").replace(".", "").upper()[:10]
        p.drawText(QRectF(cx - rr, cy - rr * 0.30, 2 * rr, rr * 0.42),
                   Qt.AlignmentFlag.AlignCenter, label)
        p.setPen(QPen(with_alpha(acc, 0.85)))
        p.setFont(px_font(max(7, rr * 0.13), QFont.Weight.Normal, mono=True, spacing=1.0))
        sub = "OFFLINE" if muted else time.strftime("%H:%M:%S")
        p.drawText(QRectF(cx - rr, cy + rr * 0.14, 2 * rr, rr * 0.25),
                   Qt.AlignmentFlag.AlignCenter, sub)

    def _paint_sats(self, p, cx, cy, r, tone, W, H, main):
        now = time.time()
        orbit_x = min(r * 1.55, W / 2 - 70)
        orbit_y = min(r * 1.38, cy - 26)
        for s in self.sats:
            age = now - s["born"]
            fade = 1.0 if age < _LIFE - _FADE else max(0.0, (_LIFE - age) / _FADE)
            out = 1 - (1 - s["out"]) ** 3                 # ease out
            a = s["angle"]
            # leave a clear lane for the state line below the core
            ox = cx + math.cos(a) * (r * 0.45 + (orbit_x - r * 0.45) * out)
            oy = cy + math.sin(a) * (r * 0.45 + (orbit_y - r * 0.45) * out)
            col = tone(KIND_TONE.get(s["kind"], "PRI"))
            fresh = max(0.0, 1.0 - (now - s["fresh"]) / 6.0)
            # beam from the dial to the node, with a packet running along it while fresh
            ex, ey = cx + math.cos(a) * r * 1.07, cy + math.sin(a) * r * 1.07
            p.setPen(QPen(with_alpha(col, (0.18 + 0.4 * fresh) * fade), 1, Qt.PenStyle.DashLine))
            p.drawLine(QLineF(ex, ey, ox, oy))
            if fresh > 0:
                k = ((now - s["fresh"]) * 0.9) % 1.0
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(with_alpha(col, 0.9 * fade))
                p.drawEllipse(QPointF(ex + (ox - ex) * k, ey + (oy - ey) * k), 2.2, 2.2)
            # node: ring + dot, pulsing while fresh
            pulse = 1.0 + 0.35 * fresh * (0.5 + 0.5 * math.sin(now * 8))
            p.setBrush(with_alpha(col, 0.25 * fade))
            p.setPen(QPen(with_alpha(col, 0.95 * fade), 1.4))
            p.drawEllipse(QPointF(ox, oy), 7 * pulse, 7 * pulse)
            p.setBrush(with_alpha(col, 0.95 * fade))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(ox, oy), 2.6, 2.6)
            # tag on the outer side of the node
            p.setFont(px_font(10, QFont.Weight.DemiBold, spacing=1.5))
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(s["label"]) + 12
            right = math.cos(a) >= 0
            tx = ox + 12 if right else ox - 12 - tw
            tx = max(4.0, min(W - tw - 4.0, tx))
            ty = max(4.0, min(H - 22.0, oy - 9))
            box = QRectF(tx, ty, tw, 18)
            p.setPen(QPen(with_alpha(col, 0.7 * fade), 1))
            p.setBrush(with_alpha(QColor(0, 8, 14), 0.75 * fade))
            p.drawRect(box)
            p.setPen(QPen(with_alpha(col, fade)))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, s["label"])
            # minutes since, small, under the tag
            mins = int(age // 60)
            if mins:
                p.setFont(px_font(8, mono=True))
                p.setPen(QPen(with_alpha(main, 0.5 * fade)))
                p.drawText(QRectF(tx, ty + 18, tw, 12), Qt.AlignmentFlag.AlignCenter, f"{mins}m")
        p.setBrush(Qt.BrushStyle.NoBrush)
