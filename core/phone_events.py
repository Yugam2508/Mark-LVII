"""
core/phone_events.py — things the phone tells the PC on its own.

    share        "Share → Jarvis" in any phone app: the text goes on the PC clipboard, a link opens in the
                 browser (switch off in CONVERSATION & PRESENCE), and a card shows what arrived.
    phone_event  battery_low: the phone is running out; Jarvis says so (or shows a card if you're busy).

The shared text is the user's own, but it is still treated as data: nothing in it is acted on except opening
a link the user shared on purpose.
"""
from __future__ import annotations

import re
import time

_last_battery_note = 0.0
URL = re.compile(r"https?://\S+")


def _setting(key: str, default):
    try:
        from memory.config_manager import get_plugin_setting
        return get_plugin_setting("conversation", key, default)
    except Exception:
        return default


def handle(data: dict) -> str:
    """Called by the dashboard for 'share' and 'phone_event' messages from a linked phone. Returns what it did."""
    kind = str(data.get("type") or "")
    if kind == "share":
        return _share(str(data.get("text") or "")[:20000])
    if kind == "phone_event" and str(data.get("event")) == "battery_low":
        return _battery_low(data.get("level"))
    return ""


def _share(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    did = []
    try:
        import pyperclip
        pyperclip.copy(text)
        did.append("copied to the clipboard")
    except Exception:
        pass
    link = URL.search(text)
    if link and bool(_setting("open_shared_links", True)):
        try:
            import webbrowser
            webbrowser.open(link.group(0).rstrip(").,;'\""))
            did.append("opened the link")
        except Exception:
            pass
    try:
        from core import addons, transcript
        addons.notice("FROM YOUR PHONE", text[:1500] + ("\n\n(" + ", ".join(did) + ")" if did else ""), "info")
        transcript.append("You (shared from phone)", text[:2000])
    except Exception:
        pass
    return ", ".join(did) or "shown"


def _battery_low(level) -> str:
    global _last_battery_note
    now = time.time()
    if now - _last_battery_note < 30 * 60:              # once per half hour is plenty
        return ""
    _last_battery_note = now
    try:
        pct = int(level)
    except (TypeError, ValueError):
        pct = -1
    try:
        from core import addons
        where = f"{pct}%" if pct >= 0 else "low"
        addons.notify("PHONE BATTERY LOW", f"Your phone is at {where}.",
                      f"The user's phone battery is {where}. Mention it briefly (one short sentence), "
                      "suggesting they charge it.", kind="warning")
    except Exception:
        pass
    return "told"
