"""
plugins/hub.py — this PC as the always-on hub.

    "This PC is my hub" / "stop being the hub"     enable / disable
    "Hub status"                                   which phones are linked, address, what keeps it awake

Hub mode is the decision to run Jarvis on one PC that is simply left on (HUB.md): it never sleeps
while plugged in, closing the window keeps it in the tray, and the phone reaches it over Tailscale. It
cannot start a PC that is off or on battery, so Jarvis says what is missing instead of pretending.
"""
from __future__ import annotations

import time

from core import addons, outcome

_started = time.time()


def _autostart_on(ui) -> bool:
    try:
        return bool(ui._win._check_autostart())
    except Exception:
        return False


def startup_check(ui) -> None:
    """At launch, in hub mode, say what still stops this PC from being a hub."""
    from core import keepawake
    if not keepawake.hub_mode():
        return
    problems = []
    if not _autostart_on(ui):
        problems.append("Jarvis doesn't start at login yet: press AUTO-START in the controls")
    if not keepawake.on_mains():
        problems.append("it's on battery, so it can still sleep: plug it in")
    if problems:
        ui.write_log("SYS: Hub mode is on, but " + "; and ".join(problems) + ".")


def _set(on: bool) -> str:
    from memory.config_manager import save_plugin_config
    save_plugin_config("conversation", {"hub_mode": on})
    from core import keepawake
    ui = getattr(addons.assistant(), "ui", None)
    todo = []
    if on:
        if not keepawake.on_mains():
            todo.append("plug it in (it only stays awake on mains power)")
        if ui is not None and not _autostart_on(ui):
            todo.append("press AUTO-START in the controls so it starts at login")
    return outcome.done("hub_mode", enabled=on, still_needed="; ".join(todo) or "nothing")


def _status() -> str:
    from core import keepawake, tailnet
    a = addons.assistant()
    d = getattr(a, "_dashboard", None)
    phones = [p.get("name", "phone") for p in (getattr(d, "_phones", {}) or {}).values()]
    ts = tailnet.status()
    mins = int((time.time() - _started) / 60)
    ui = getattr(a, "ui", None)
    facts = dict(
        hub_mode=keepawake.hub_mode(), on_mains=keepawake.on_mains(),
        holding_awake=keepawake.wanted(), starts_at_login=_autostart_on(ui) if ui is not None else "unknown",
        tailscale=("running at " + ts["ip"]) if ts.get("running") and ts.get("ip") else "not running",
        phones_linked=", ".join(phones) or "none", up_minutes=mins,
        dashboard="running" if d is not None else "off")
    return outcome.done("hub_status", **facts)


PLUGIN = {
    "name": "hub",
    "description": (
        "Makes this PC the always-on hub that the phone connects to (action enable/disable) or reports "
        "its state (status): is hub mode on, which phones are linked, Tailscale address, whether it "
        "starts at login and is being kept awake. Use for 'this PC is my hub', 'hub status', "
        "'is my phone connected', 'why can't my phone reach you'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "enum": ["status", "enable", "disable"]}},
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Hub: this PC always on for the phone; status.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    try:
        if action == "enable":
            return _set(True)
        if action == "disable":
            return _set(False)
        return _status()
    except Exception as e:
        return outcome.failed("hub", str(e)[:160])
