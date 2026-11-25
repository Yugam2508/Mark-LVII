"""
plugins/persona.py — "Switch to the Irish voice", "be more like a butler", "list your voices".

Personas pair a Gemini voice with an accent and a manner (see core/personas.py).
Switching reconnects the voice session a few seconds after JARVIS answers, so it
finishes its sentence in the old voice and the next one is in the new voice.
Recent conversation is not carried across a voice change (Gemini fixes the voice
when the session starts); memory, settings and everything else are.
"""
from __future__ import annotations

import threading
import time

from core import addons, outcome, personas
from memory.config_manager import get_plugin_config, save_plugin_config

NAMESPACE = "persona"


def _reconnect_soon(delay: float = 4.0) -> bool:
    a = addons.assistant()
    if a is None or not hasattr(a, "request_reconnect"):
        return False

    def go():
        time.sleep(delay)
        try:
            a.request_reconnect(keep_context=False, reason="new persona")
        except Exception as e:
            print(f"[Persona] reconnect failed: {e}")
    threading.Thread(target=go, daemon=True).start()
    return True


def set_persona(key: str, custom_voice: str = "", custom_style: str = "") -> tuple[bool, str]:
    key = (key or "").strip().lower()
    if key not in personas.CHOICES:
        return False, "unknown persona; choose from " + ", ".join(personas.CHOICES)
    cfg = get_plugin_config(NAMESPACE)
    cfg["persona"] = key
    if custom_voice:
        v = next((x for x in personas.ALL_VOICES if x.lower() == custom_voice.strip().lower()), "")
        if not v:
            return False, f"'{custom_voice}' is not one of the available voices"
        cfg["custom_voice"] = v
    if custom_style:
        cfg["custom_style"] = custom_style.strip()[:800]
    save_plugin_config(NAMESPACE, cfg)
    return True, personas.describe(key)


def _apply(values: dict) -> tuple[bool, str]:
    """Settings button: save happens first, then this reconnects."""
    return (True, "Switching voice in a few seconds.") if _reconnect_soon(0.5) \
        else (False, "Saved; it applies the next time JARVIS starts.")


PLUGIN = {
    "name": "persona",
    "description": (
        "Changes how the assistant sounds: its voice, accent and manner. Personas: classic "
        "(British butler), irish (co-pilot), tactical (mission control), coach (Australian), "
        "mentor (deep, calm), desi (Indian English), custom, off. Use for 'change your voice', "
        "'use a British/Irish/Australian/Indian accent', 'sound like a butler', 'what voices do "
        "you have'. For custom, pass voice and/or style. Never imitate a real person or a film "
        "character: offer the closest original persona instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["set", "list", "current"]},
            "persona": {"type": "STRING", "enum": list(personas.CHOICES)},
            "voice": {"type": "STRING", "description": "For custom: one of the Gemini voice names"},
            "style": {"type": "STRING", "description": "For custom: accent and manner, in words"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Voice personas: set / list / current.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "VOICE PERSONA",
    "fields": [
        {"key": "persona", "label": "Persona (" + "; ".join(
            f"{k} = {v['label'].split(' — ')[1]}" for k, v in personas.PERSONAS.items()) + ")",
         "type": "choice", "options": list(personas.CHOICES), "default": "off"},
        {"key": "custom_voice", "label": "Custom persona: voice", "type": "choice",
         "options": list(personas.ALL_VOICES), "default": "Charon"},
        {"key": "custom_style", "label": "Custom persona: accent and manner, in your words", "type": "text",
         "placeholder": "Scottish accent, dry humour, calls me 'boss'"},
    ],
    "action": {"label": "APPLY NOW", "run": _apply},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "current")
    try:
        if action == "list":
            text = "\n".join(personas.describe(k) for k in personas.CHOICES)
            addons.show("VOICE PERSONAS", text + "\n\nCustom voices: " + ", ".join(personas.ALL_VOICES))
            return outcome.done("persona_list", current=personas.current()) + "\n" + \
                outcome.untrusted("personas", text)
        if action == "current":
            return outcome.done("persona_current", persona=personas.describe(personas.current()))
        ok, msg = set_persona(str(parameters.get("persona") or ""), str(parameters.get("voice") or ""),
                              str(parameters.get("style") or ""))
        if not ok:
            return outcome.failed("persona_set", msg)
        live = _reconnect_soon()
        return outcome.done("persona_set", persona=msg,
                            note=("say one short line in your CURRENT voice that you're switching; "
                                  "the new voice starts in a few seconds and recent chat is not carried over")
                            if live else "applies the next time JARVIS starts")
    except Exception as e:
        return outcome.failed(f"persona_{action}", str(e)[:150])
