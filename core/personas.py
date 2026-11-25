"""
core/personas.py — how JARVIS sounds: a voice plus an accent and a manner.

Gemini Live has a fixed set of voices; it can't copy a real person's voice, and
this project doesn't try to (no cloning actors or celebrities). What it does do
well is take direction: the same voice told to speak with a soft Irish accent,
or as a clipped mission controller, sounds like a different character. A persona
is one of those pairings. Original characters, not impressions:

    classic   British, formal, dry wit — the old-school butler AI
    irish     soft Irish accent, warm, quick and teasing — the co-pilot
    tactical  crisp, neutral American, minimal words — mission control
    coach     lively Australian, upbeat, pushes you a bit — training days
    mentor    deep, slow and calm
    desi      warm Indian English, the odd Hindi word
    custom    your own voice + your own description
    off       no persona (the voice picked in Customize, the default manner)

Read by main.py when the Live session is built (voice + one prompt block), and
by plugins/persona.py, which switches personas by voice and reconnects.
"""
from __future__ import annotations

# Gemini Live prebuilt voices. The first eight are the long-standing Live voices
# and are what presets use; the rest are newer native-audio voices, offered for
# the custom persona.
LIVE_VOICES = ("Charon", "Puck", "Kore", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr")
EXTRA_VOICES = ("Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
                "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
                "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
                "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat")
ALL_VOICES = LIVE_VOICES + EXTRA_VOICES

PERSONAS: dict[str, dict] = {
    "classic": {
        "label": "Classic — British butler",
        "voice": "Charon",
        "style": "Speak with a refined, Received Pronunciation British accent, like a "
                 "long-serving English butler: composed, formal, unhurried, quietly witty. "
                 "Understatement over enthusiasm.",
    },
    "irish": {
        "label": "Co-pilot — soft Irish",
        "voice": "Aoede",
        "style": "Speak with a soft, natural Irish accent. Warm, quick and informal; a bit "
                 "of teasing when things are going well, straight to the point when they "
                 "aren't. Sound like a trusted co-pilot, not a servant.",
    },
    "tactical": {
        "label": "Tactical — mission control",
        "voice": "Kore",
        "style": "Neutral American accent. Crisp and efficient: status first, as few words "
                 "as possible, like a calm mission controller. No small talk unless invited.",
    },
    "coach": {
        "label": "Coach — lively Australian",
        "voice": "Puck",
        "style": "Speak with a lively Australian accent. Upbeat and encouraging, celebrates "
                 "progress, pushes a little when the user is slacking. Short punchy sentences.",
    },
    "mentor": {
        "label": "Mentor — deep and calm",
        "voice": "Orus",
        "style": "Deep, slow and calm. Thoughtful pauses, warm, never rushed. Sounds like "
                 "someone who has seen it all and is on the user's side.",
    },
    "desi": {
        "label": "Desi — Indian English",
        "voice": "Zephyr",
        "style": "Speak with a natural Indian English accent. Warm and friendly; you may use "
                 "an occasional everyday Hindi word (accha, chalo, bas) where it fits, but "
                 "answer in English unless the user switches language.",
    },
}

CHOICES = ("off",) + tuple(PERSONAS) + ("custom",)


def _setting(key: str, default):
    try:
        from memory.config_manager import get_plugin_setting
        v = get_plugin_setting("persona", key, default)
        return default if v in (None, "") else v
    except Exception:
        return default


def current() -> str:
    v = str(_setting("persona", "off")).lower()
    return v if v in CHOICES else "off"


def voice(fallback: str) -> str:
    """The Live voice to connect with."""
    p = current()
    if p in PERSONAS:
        return PERSONAS[p]["voice"]
    if p == "custom":
        v = str(_setting("custom_voice", fallback))
        return v if v in ALL_VOICES else fallback
    return fallback


def style() -> str:
    p = current()
    if p in PERSONAS:
        return PERSONAS[p]["style"]
    if p == "custom":
        return str(_setting("custom_style", "")).strip()[:800]
    return ""


def prompt_block() -> str:
    """Appended after the main system prompt. Empty when no persona is on."""
    s = style()
    if not s:
        return ""
    return ("[PERSONA]\n" + s + "\nThis changes only HOW you sound — accent, manner, word "
            "choice. Every rule above still applies, you keep your name, and you never "
            "claim to be or imitate a real person or a film character.")


def describe(key: str) -> str:
    if key in PERSONAS:
        return f"{PERSONAS[key]['label']} (voice {PERSONAS[key]['voice']})"
    return {"off": "Off — your Customize voice, default manner",
            "custom": "Custom — your own voice and description"}.get(key, key)
