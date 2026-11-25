"""
plugins/phone_alerts.py — JARVIS's alerts on your phone when you're not at the PC.

Install the free ntfy app (Play Store) on the OnePlus and subscribe to your
alerts topic (shown in ⚙ → PLUGIN SETTINGS → PHONE & DEVICES → SEND TEST).

    * Important email, "event in 15 minutes" and due to-dos (proactive alerts) are
      pushed to the phone when you have been away from this PC for a while —
      or always, or never (⚙ → PHONE ALERTS).
    * "Send this to my phone" / "send the address to my phone" works any time.
    * Replies to phone commands and "Desktop is on" come here too (device_link).

What a notification shows is up to you: just "New important email", or the
sender and subject too. The message passes through the ntfy server (encrypted
in transit); use your own ntfy server in PHONE & DEVICES to keep it entirely yours.
"""
from __future__ import annotations

import sys
import time

from core import outcome
from memory.config_manager import get_plugin_config
from plugins import _ntfy

NAMESPACE = "phone_alerts"


def _cfg() -> dict:
    c = get_plugin_config(NAMESPACE)
    return {"when": str(c.get("when") or "away"),
            "away_minutes": int(str(c.get("away_minutes") or "10")),
            "detail": str(c.get("detail") or "sender_subject")}


def idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input on this PC (0 when unknown)."""
    if sys.platform != "win32":
        return 0.0
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0
    except Exception:
        return 0.0


def away() -> bool:
    return idle_seconds() >= _cfg()["away_minutes"] * 60


def should_push(urgent: bool = False) -> bool:
    when = _cfg()["when"]
    if when == "never":
        return False
    if when == "always":
        return True
    return away() or (urgent and when == "away_or_urgent")


def push(kind: str, title: str, detail: str, *, urgent: bool = False) -> bool:
    """A proactive alert for the phone. `detail` is dropped at the 'minimal' level."""
    level = _cfg()["detail"]
    body = {"email": "New important email", "event": "Coming up", "todo": "To-dos due"}.get(kind, title)
    if level != "minimal" and detail:
        body = detail
    return _ntfy.publish("alert", body, title=title if level != "minimal" else "JARVIS",
                         priority=5 if urgent else 4, tags=[{"email": "envelope", "event": "calendar",
                                                             "todo": "white_check_mark"}.get(kind, "bell")])


PLUGIN = {
    "name": "phone_alerts",
    "description": (
        "Sends something to the user's phone as a notification: 'send this to my phone', "
        "'text me the address', 'put that on my phone'. Also reports whether phone alerts "
        "are on."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["send", "status"]},
            "text": {"type": "STRING", "description": "For send: what to put on the phone"},
            "title": {"type": "STRING", "description": "For send: optional short title"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Send a notification to the user's phone.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "PHONE ALERTS",
    "fields": [
        {"key": "when", "label": "Push alerts to my phone", "type": "choice",
         "options": ["away", "away_or_urgent", "always", "never"], "default": "away"},
        {"key": "away_minutes", "label": "I'm 'away' after this many idle minutes", "type": "choice",
         "options": ["5", "10", "20", "30"], "default": "10"},
        {"key": "detail", "label": "What a notification shows", "type": "choice",
         "options": ["sender_subject", "minimal"], "default": "sender_subject"},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        if parameters.get("action") == "send":
            text = str(parameters.get("text") or "").strip()
            if not text:
                return outcome.ask("phone_send", "What should I send to your phone?")
            ok = _ntfy.publish("alert", text, title=str(parameters.get("title") or "From JARVIS"))
            return outcome.done("phone_send") if ok else \
                outcome.failed("phone_send", "ntfy did not accept it; check PHONE & DEVICES settings")
        c = _cfg()
        return outcome.done("phone_alerts_status", when=c["when"], away_after_min=c["away_minutes"],
                            idle_min=round(idle_seconds() / 60))
    except Exception as e:
        return outcome.failed("phone_alerts", str(e)[:150])
