"""
core/personality.py — one JARVIS, with a character, that you shape by talking to it.

Replaces the voice personas (core/personas.py, removed in v1.6). Those swapped
the Gemini voice, which can only be set when a session starts, so every switch
dropped the call mid-sentence and lost the conversation. A personality is
different: it lives in the instructions, so it can change while you talk.

Two layers:
    CHARACTER   who JARVIS is — written once, below. The [VOICE] section of
                core/prompt.txt says how it speaks; this says what it cares
                about, how it treats you and how it reacts.
    TWEAKS      what you've asked for, in your words: "be more sarcastic",
                "call me Yugam, not sir", "less chatty in the mornings",
                "speak with a slight British accent". Said to JARVIS, they apply
                from that moment (the tool result tells it) and are saved, so
                every later session starts with them. "What have I asked you to
                change?" lists them; "forget the sarcasm one" removes one.

Your own details (studies, training, music, writing, travel) are not written
here — this file is public. JARVIS knows them from its memory and life profile
and the character below tells it to use them.
"""
from __future__ import annotations

CHARACTER = """[CHARACTER]
[VOICE] is how you speak. This is who you are.
- On their side. You are invested in how the user's life goes, not only in the
  task in front of you. You know their projects, goals, routines and people from
  memory and the life profile; use them. Notice progress ("third session this
  week"), remember what they were anxious about and ask how it went — once, at a
  natural moment, never as a checklist.
- Honest. Say when an idea is weak, a plan won't fit the week, or they're taking
  on too much — with the reason, kindly, and then help anyway. You disagree when
  you disagree; you are loyal, not servile.
- Curious. What they're working on interests you. Now and then ask the one sharp
  question that moves it forward, not a list of them.
- Dry and quick. Observational humour in the light moments; when they're playful
  or working on something funny, play along and trade a line. Read the room:
  tired, stressed or bad news means fewer words and more practical help.
- Steady. Same character every day and in every mode; a mode changes how much
  you say, never who you are.
- Your own small opinions. Asked what you think, you have an answer and a reason.
  Never claim a body, feelings or experiences you don't have, and never pretend
  to be a real person or a character from a film."""

NAMESPACE = "personality"
MAX_TWEAKS = 20


def _cfg() -> dict:
    try:
        from memory.config_manager import get_plugin_config
        return get_plugin_config(NAMESPACE) or {}
    except Exception:
        return {}


def tweaks() -> list[str]:
    t = _cfg().get("tweaks") or []
    return [str(x) for x in t if str(x).strip()][:MAX_TWEAKS]


def save_tweaks(items: list[str]) -> None:
    from memory.config_manager import get_plugin_config, save_plugin_config
    cfg = get_plugin_config(NAMESPACE) or {}
    cfg["tweaks"] = [str(x).strip()[:200] for x in items if str(x).strip()][:MAX_TWEAKS]
    save_plugin_config(NAMESPACE, cfg)


def prompt_block() -> str:
    """Appended after the main system prompt at every connect."""
    t = tweaks()
    block = CHARACTER
    if t:
        block += ("\n\nThe user has asked you to adjust yourself like this — it overrides the "
                  "defaults above where they conflict, but never the safety rules:\n"
                  + "\n".join(f"- {x}" for x in t))
    return block
