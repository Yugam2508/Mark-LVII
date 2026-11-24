"""
plugins/voice_interrupt.py — the switch for interrupting JARVIS by talking over it.

    "Let me interrupt you"            action=set  enabled=true
    "Be careful about interrupting"   action=set  enabled=true sensitivity=careful
    "Stop letting me interrupt you"   action=set  enabled=false

The listening itself lives in main.py (`_listen_audio`), which already had
everything needed: core/echo.py tells your voice apart from JARVIS's own voice
coming back through the speakers, and learns your room's echo within a second of
the first reply. This file only stores the setting and lets you change it by
voice or in ⚙ → PLUGIN SETTINGS → VOICE INTERRUPT. main.py picks a change up
within three seconds.

OFF BY DEFAULT, ON PURPOSE
    How well it works depends on your speakers, microphone and room. With
    headphones it is reliable. On loud desk speakers it can now and then stop
    itself; choose "careful" (needs about 0.6 s of you talking instead of 0.3 s)
    or keep using the interrupt button / push-to-talk.
    The first fraction of a second you say while interrupting is used to detect
    you and is not sent to the model, so say "stop" or "wait" first.
"""
from __future__ import annotations

from core import outcome
from memory.config_manager import get_plugin_config, save_plugin_config

NAMESPACE = "voice_interrupt"

PLUGIN = {
    "name": "voice_interrupt",
    "description": (
        "Turns on or off the user's ability to interrupt the assistant by speaking "
        "over it, and sets how careful it is. Use when the user asks to be able to "
        "interrupt, or complains that the assistant stops when it should not."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["set", "status"]},
            "enabled": {"type": "BOOLEAN"},
            "sensitivity": {"type": "STRING", "enum": ["normal", "careful"]},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Interrupt-by-voice switch.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "VOICE INTERRUPT",
    "fields": [
        {"key": "enabled", "label": "Let me interrupt JARVIS by talking", "type": "toggle",
         "default": False},
        {"key": "sensitivity", "label": "How sure before stopping (careful = loud speakers)",
         "type": "choice", "options": ["normal", "careful"], "default": "normal"},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        if str(parameters.get("action") or "status") == "set":
            values = {}
            if parameters.get("enabled") is not None:
                values["enabled"] = bool(parameters["enabled"])
            if parameters.get("sensitivity") in ("normal", "careful"):
                values["sensitivity"] = parameters["sensitivity"]
            if not values:
                return outcome.ask("voice_interrupt", "Should I turn it on or off?")
            save_plugin_config(NAMESPACE, values)
        cfg = get_plugin_config(NAMESPACE)
        return outcome.done("voice_interrupt", enabled=bool(cfg.get("enabled", False)),
                            sensitivity=cfg.get("sensitivity", "normal"),
                            note="takes effect within a few seconds")
    except Exception as e:
        return outcome.failed("voice_interrupt", f"could not change the setting: {e}")
