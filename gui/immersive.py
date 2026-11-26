"""gui/immersive.py — the immersive layout: the HUD fills the window and things come to you.

Instead of fixed SYSTEMS / STATUS / TASKS / COMMUNICATIONS panels that sit there
whether or not anything is happening, everything appears when it matters and
goes away when it doesn't:

    FlowCards     what JARVIS shows you (weather, an email, search results, a
                  finished task) slides out of the core as a card, stacks beside
                  it, and drifts away after a while — hover to keep it, pin it,
                  or click EXPAND for the full panel
    Captions      what you and JARVIS say, live, fading out a few seconds later
    Vitals        CPU / memory / mode in one quiet line in the corner
    CommandBar    a slim bar under the HUD: type, mute, interrupt, switch layout

Everything here is a child of the HUD canvas (gui/hud.py), so it moves and
resizes with it, and it never touches the panels: switching back to PANELS
(F2, or the ◫ button) shows the classic layout exactly as it was.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QVBoxLayout, QWidget)

from gui.style import hud_font, px_font
from gui.theme import C

CARD_W = 300
CARD_LIFE = 60.0          # seconds a card stays when nobody touches it
MAX_CARDS = 4


def _btn(text: str, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFixedHeight(22)
    b.setFont(hud_font(7, QFont.Weight.Bold))
    b.setToolTip(tip)
    b.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; background: transparent; border: 1px solid {C.BORDER};"
                    f" border-radius: 3px; padding: 0 6px; }}"
                    f"QPushButton:hover {{ color: {C.TEXT}; border-color: {C.PRI}; }}")
    return b


class FlowCard(QFrame):
    """One thing JARVIS put in front of you."""
    expand = pyqtSignal(str, str)
    closed = pyqtSignal(object)

    def __init__(self, title: str, text: str, parent=None, pinned: bool = False, accent: str = ""):
        super().__init__(parent)
        self.title, self.text = title, text
        self.born = time.time()
        self.pinned = pinned
        accent = accent or C.PRI
        self.setFixedWidth(CARD_W)
        self.setStyleSheet(f"FlowCard {{ background: rgba(0, 10, 18, 225); border: 1px solid {C.BORDER_B};"
                           f" border-top: 2px solid {accent}; border-radius: 4px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 8, 8)
        lay.setSpacing(4)
        top = QHBoxLayout()
        label, dash, rest = str(title).partition(" — ")
        t = QLabel((label.upper() + dash + rest)[:40])
        t.setFont(hud_font(8, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {accent}; background: transparent; border: none;")
        top.addWidget(t, 1)
        when = QLabel(time.strftime("%H:%M"))
        when.setFont(hud_font(7))
        when.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        top.addWidget(when)
        x = QPushButton("✕")
        x.setFixedSize(18, 18)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; background: transparent; border: none; }}"
                        f"QPushButton:hover {{ color: {C.TEXT}; }}")
        x.clicked.connect(lambda: self.closed.emit(self))
        top.addWidget(x)
        lay.addLayout(top)
        lines = [ln for ln in str(text).strip().splitlines() if ln.strip()]
        short = "\n".join(lines[:7])[:420]
        more = len(lines) > 7 or len(str(text)) > 420
        body = QLabel(short + ("…" if more else ""))
        body.setWordWrap(True)
        body.setFont(hud_font(8))
        body.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
        lay.addWidget(body)
        row = QHBoxLayout()
        row.addStretch(1)
        self._pin = _btn("PINNED" if pinned else "PIN", "Keep this card until you close it")
        self._pin.clicked.connect(self._toggle_pin)
        row.addWidget(self._pin)
        ex = _btn("EXPAND", "Open the full text")
        ex.clicked.connect(lambda: self.expand.emit(self.title, self.text))
        row.addWidget(ex)
        lay.addLayout(row)
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._anims = []

    def _toggle_pin(self):
        self.pinned = not self.pinned
        self._pin.setText("PINNED" if self.pinned else "PIN")

    def fade_to(self, value: float, ms: int = 350) -> QPropertyAnimation:
        a = QPropertyAnimation(self._fx, b"opacity", self)
        a.setDuration(ms)
        a.setStartValue(self._fx.opacity())
        a.setEndValue(value)
        a.start()
        self._anims = [x for x in self._anims if x.state() == QPropertyAnimation.State.Running] + [a]
        return a

    def glide_to(self, pos: QPoint, ms: int = 450) -> None:
        a = QPropertyAnimation(self, b"pos", self)
        a.setDuration(ms)
        a.setStartValue(self.pos())
        a.setEndValue(pos)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start()
        self._anims = [x for x in self._anims if x.state() == QPropertyAnimation.State.Running] + [a]

    def expired(self) -> bool:
        return (not self.pinned and not self.underMouse()
                and time.time() - self.born > CARD_LIFE)


class FlowLayer:
    """Cards, captions and vitals over the HUD canvas."""

    def __init__(self, hud: QWidget, on_expand):
        self.hud = hud
        self.on_expand = on_expand
        self.cards: list[FlowCard] = []
        self.enabled = True
        self._next_side = 1
        # captions
        self._cap_you = self._caption_label()
        self._cap_ai = self._caption_label()
        self._cap_t = {"you": 0.0, "ai": 0.0}
        self._cap_text = {"you": "", "ai": ""}
        # vitals
        self._vitals = QLabel(hud)
        self._vitals.setFont(px_font(10, mono=True))
        self._vitals.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._vitals.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._tick = QTimer(hud)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(500)

    # ── cards ───────────────────────────────────────────────────────────
    def add_card(self, title: str, text: str, pinned: bool = False, accent: str = "") -> None:
        """pinned: stays until closed (the 'busy / away' notices)."""
        for c in self.cards:                      # same panel again: replace it
            if not pinned and not c.pinned and c.title.split(" — ")[0] == str(title).split(" — ")[0]:
                self._remove(c, animate=False)
                break
        card = FlowCard(title, text, self.hud, pinned=pinned, accent=accent)
        card.expand.connect(self.on_expand)
        card.closed.connect(lambda c: self._remove(c))
        card.adjustSize()
        # slide out of the core
        cx, cy = self.hud.width() // 2, self.hud.height() // 2
        card.move(cx - CARD_W // 2, cy - card.height() // 2)
        card.show()
        card.raise_()
        card.fade_to(1.0, 300)
        side = self._next_side
        self._next_side = -side
        card.side = side
        self.cards.insert(0, card)
        while len([c for c in self.cards if not c.pinned]) > MAX_CARDS:
            old = next(c for c in reversed(self.cards) if not c.pinned)
            self._remove(old)
        while len(self.cards) > MAX_CARDS * 2:           # room for 8 at most
            self._remove(self.cards[-1])
        self.relayout()

    def _remove(self, card: FlowCard, animate: bool = True) -> None:
        if card not in self.cards:
            return
        self.cards.remove(card)
        if animate:
            a = card.fade_to(0.0, 300)
            a.finished.connect(card.deleteLater)
        else:
            card.deleteLater()
        self.relayout()

    def relayout(self) -> None:
        """Stack cards in two columns either side of the core, newest on top."""
        W, H = self.hud.width(), self.hud.height()
        y = {1: 40, -1: 40}
        for c in self.cards:
            side = getattr(c, "side", 1)
            if W < CARD_W * 2 + 360:               # narrow window: one column, right
                side = 1
            h = c.sizeHint().height()
            if y[side] + h > H - 120:              # column full: the other side
                side = -side
            x = W - CARD_W - 14 if side == 1 else 14
            c.glide_to(QPoint(x, y[side]))
            y[side] += h + 10

    # ── captions ────────────────────────────────────────────────────────
    def _caption_label(self) -> QLabel:
        lb = QLabel(self.hud)
        lb.setWordWrap(True)
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lb.setFont(px_font(14))
        lb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lb.hide()
        return lb

    def caption(self, who: str, text: str, append: bool = True) -> None:
        """Live words. who = 'you' or 'ai'."""
        if not self.enabled:
            return
        now = time.time()
        k = "you" if who == "you" else "ai"
        if append and now - self._cap_t[k] < 3.0:
            self._cap_text[k] = (self._cap_text[k] + " " + text.strip()).strip()[-220:]
        else:
            self._cap_text[k] = text.strip()[-220:]
        self._cap_t[k] = now
        self._place_captions()

    def _place_captions(self) -> None:
        if not self.enabled:
            self._cap_you.hide()
            self._cap_ai.hide()
            return
        W = self.hud.width()
        # never on top of a card: between the two columns, or left of the one
        has_cards = any(c.isVisible() for c in self.cards)
        narrow = W < CARD_W * 2 + 360
        if has_cards and narrow:
            left, right = 14, W - CARD_W - 28
        elif has_cards:
            left, right = CARD_W + 30, W - CARD_W - 30
        else:
            left, right = int(W * 0.15), int(W * 0.85)
        w = int(min(right - left, 720))
        x0 = left + (right - left - w) // 2
        y = 12
        for k, lb, col, tag in (("you", self._cap_you, C.GREEN, "YOU"), ("ai", self._cap_ai, C.PRI, "")):
            age = time.time() - self._cap_t[k]
            if not self._cap_text[k] or age > 8.0:
                lb.hide()
                continue
            fade = 1.0 if age < 6.0 else max(0.0, (8.0 - age) / 2.0)
            alpha = int(255 * fade)
            prefix = f'<span style="color:{col}; font-weight:600;">{tag}&nbsp;&nbsp;</span>' if tag else ""
            text = self._cap_text[k].replace("&", "&amp;").replace("<", "&lt;")
            lb.setText(f'{prefix}<span style="color: rgba(230,240,250,{alpha});">{text}</span>')
            lb.setFixedWidth(w)
            lb.adjustSize()
            lb.move(x0, y)
            lb.show()
            lb.raise_()
            y += lb.height() + 4

    # ── housekeeping ────────────────────────────────────────────────────
    def _on_tick(self) -> None:
        if not self.enabled:
            return
        for c in [c for c in self.cards if c.expired()]:
            self._remove(c)
        self._place_captions()
        self._vitals.setText(self._vitals_text())
        self._vitals.adjustSize()
        self._vitals.move(14, self.hud.height() - self._vitals.height() - 10)

    @staticmethod
    def _vitals_text() -> str:
        parts = []
        try:
            import psutil
            parts.append(f"CPU {psutil.cpu_percent(interval=None):.0f}%")
            parts.append(f"MEM {psutil.virtual_memory().percent:.0f}%")
            b = psutil.sensors_battery()
            if b is not None:
                parts.append(f"BAT {b.percent:.0f}%{'+' if b.power_plugged else ''}")
        except Exception:
            pass
        try:
            from core import addons, presence
            mode = addons.mode_policy().get("mode")
            if mode and mode != "normal":
                parts.append(f"{mode.upper()} MODE")
            where, _ = presence.state()
            if where != "free":
                parts.append(where.upper())
        except Exception:
            pass
        return "  ·  ".join(parts)

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        for w in [self._vitals] + self.cards:
            w.setVisible(on)
        if not on:
            self._cap_you.hide()
            self._cap_ai.hide()

    def resized(self) -> None:
        self.relayout()
        self._place_captions()


class CommandBar(QFrame):
    """The slim bar under the HUD in the immersive layout."""
    send = pyqtSignal(str)
    mute = pyqtSignal()
    stop = pyqtSignal()
    panels = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self.setStyleSheet(f"CommandBar {{ background: rgba(0, 10, 18, 200); border: 1px solid {C.BORDER};"
                           f" border-radius: 6px; }}")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(8)
        p = QLabel("›")
        p.setFont(px_font(20, QFont.Weight.Light))
        p.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        row.addWidget(p)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Talk, or type here…")
        self.input.setFont(px_font(13))
        self.input.setStyleSheet(f"QLineEdit {{ background: transparent; color: {C.WHITE}; border: none; }}")
        self.input.returnPressed.connect(self._go)
        row.addWidget(self.input, 1)
        self.mic = _btn("MIC ON", "Mute or unmute the microphone  [F4]")
        self.mic.clicked.connect(self.mute.emit)
        row.addWidget(self.mic)
        st = _btn("STOP", "Stop JARVIS mid-sentence  [ESC]")
        st.clicked.connect(self.stop.emit)
        row.addWidget(st)
        pn = _btn("◫ PANELS", "Show the classic panels  [F2]")
        pn.clicked.connect(self.panels.emit)
        row.addWidget(pn)

    def _go(self):
        t = self.input.text().strip()
        if t:
            self.input.clear()
            self.send.emit(t)

    def set_muted(self, muted: bool) -> None:
        self.mic.setText("MIC OFF" if muted else "MIC ON")
