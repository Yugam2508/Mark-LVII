"""
plugins/display_control.py — talk to the hologram the way Tony does.

    "Close that" / "close the weather" / "clear the screen"        close (that | a title | all)
    "Pin it" / "unpin the calendar"                                pin / unpin
    "Expand that" / "show me the email in full"                    expand
    "What's on screen?"                                            list
    "Full screen" / "switch to panels" / "immersive view"          fullscreen / panels / immersive
    "Hide yourself" / "come back"                                  hide / show
"""
from __future__ import annotations

import threading

from core import addons, outcome

PLUGIN = {
    "name": "display_control",
    "description": (
        "Controls what is on Jarvis's screen by voice: close a panel (target = 'that' for the newest, a few "
        "words of its title, or 'all' to clear the screen), pin / unpin one, expand one to full text, list "
        "what's open, toggle full screen, switch between the immersive hologram and the panels layout, hide "
        "the window to the tray or show it. Use for 'close that', 'clear the screen', 'pin the calendar', "
        "'make it full screen', 'hide'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["close", "pin", "unpin", "expand", "list", "fullscreen",
                                                  "immersive", "panels", "hide", "show"]},
            "target": {"type": "STRING", "description": "Which panel: 'that' (newest), words of its title, or 'all'"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Close / pin / expand panels, full screen, layout, hide/show.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    target = str(parameters.get("target") or "")
    ui = player or getattr(addons.assistant(), "ui", None)
    win = getattr(ui, "_win", None)
    if win is None or not hasattr(win, "_display_sig"):
        return outcome.failed("display_control", "the screen isn't available")
    box = {"done": threading.Event(), "msg": ""}
    win._display_sig.emit(action, target, box)
    if not box["done"].wait(3.0):
        return outcome.unverified("display_control", "the screen didn't answer in time")
    msg = box["msg"]
    bad = msg.startswith(("no ", "failed", "unknown"))
    return outcome.failed("display_control", msg) if bad else outcome.done("display_control", result=msg)
