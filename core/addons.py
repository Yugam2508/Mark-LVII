"""
core/addons.py — what background add-ons need from the running app, in one place.

A plugin's run() receives `player` (the HUD) when it is called as a tool. A
plugin that works on its own — the proactive assistant checking mail, modes
noticing a game start — has no tool call to receive it from. main.py binds the
HUD here once at start-up and those plugins read it from here.

It is standard library only and imports nothing from the app, because
core/routines (which reads the current mode for quiet hours) also runs on the
headless cloud server, where there is no HUD and nothing is ever bound.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Optional

_lock = threading.Lock()
_player: Any = None
_say: Optional[Callable[[str], None]] = None
_assistant: Any = None
_missed: list = []          # notices delivered as cards while busy/away

# Set by plugins/modes.py; read by core/routines/engine.py and the proactive
# plugin. A function rather than a value so the routines engine never imports
# a plugin.
_mode_policy: Optional[Callable[[], dict]] = None


def bind(player: Any = None, say: Optional[Callable[[str], None]] = None,
         assistant: Any = None) -> None:
    """Called once by main.py when the HUD exists."""
    global _player, _say, _assistant
    with _lock:
        _player, _say = player, say
        if assistant is not None:
            _assistant = assistant


def assistant() -> Any:
    """The running JarvisLive (sleep/wake, mute). None in tests and on the server."""
    return _assistant


def player() -> Any:
    return _player


def say(instruction: str) -> bool:
    """Ask the assistant to say something now (phrased by the model, in the
    user's language). False when no session is connected or nothing is bound."""
    fn = _say
    if fn is None:
        return False
    try:
        fn(instruction)
        return True
    except Exception:
        return False


def show(title: str, text: str) -> None:
    p = _player
    if p is not None:
        try:
            p.show_content(title, text)
        except Exception:
            pass


def edit(title: str, fields: list, actions: list, note: str = "", copy: str = "",
         player: Any = None) -> bool:
    """Open an editable draft panel (see JarvisUI.show_editable). Falls back to
    the plain content panel on a HUD without it. False when there is no HUD.
    `player` is the one a tool call received, when there is one."""
    p = player or _player
    if p is None:
        return False
    try:
        if hasattr(p, "show_editable"):
            p.show_editable(title, fields, actions, note=note, copy=copy)
        else:
            p.show_content(title, "\n\n".join(str(f.get("value", "")) for f in fields))
        return True
    except Exception:
        return False


def log(text: str) -> None:
    p = _player
    if p is not None:
        try:
            p.write_log(text)
        except Exception:
            pass


def notice(title: str, text: str, kind: str = "info") -> bool:
    """A card on the HUD that stays until dismissed (falls back to the content panel)."""
    p = _player
    if p is None:
        return False
    try:
        if hasattr(p, "show_notice"):
            p.show_notice(title, text, kind)
        else:
            p.show_content(title, text)
        return True
    except Exception:
        return False


def notify(title: str, text: str, instruction: str, *, urgent: bool = False,
           kind: str = "info", phone: bool = True) -> str:
    """Tell the user something JARVIS decided to bring up on its own.

        free  -> said out loud (instruction goes to the model) + shown briefly
        busy  -> a card that stays on screen; no speech
        away  -> the card, and a phone notification
    Returns 'said', 'card' or 'card+phone'. `instruction` should already wrap any
    outside text with core.outcome.untrusted()."""
    try:
        from core import presence
        where, why = presence.state()
    except Exception:
        where, why = "free", ""
    if where == "free" and say(instruction):
        show(title, text)
        return "said"
    notice(title, text, kind)
    with _lock:
        _missed.append(title if not text else f"{title}: {text.splitlines()[0][:120]}")
        del _missed[:-20]
    if where == "away" and phone:
        try:
            from plugins import phone_alerts
            if phone_alerts.should_push(urgent):
                phone_alerts.push(kind, title, text[:500], urgent=urgent)
                return "card+phone"
        except Exception:
            pass
    return "card"


def take_missed() -> list:
    """What was carded while busy/away — once, for the 'welcome back' summary."""
    with _lock:
        out, _missed[:] = list(_missed), []
    return out


def set_mode_policy(fn: Callable[[], dict]) -> None:
    global _mode_policy
    _mode_policy = fn


def mode_policy() -> dict:
    """The current mode's rules, or an empty dict when modes are not installed."""
    fn = _mode_policy
    if fn is None:
        return {}
    try:
        return fn() or {}
    except Exception:
        return {}
