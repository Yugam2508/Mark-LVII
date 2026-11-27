"""
plugins/interpreter.py — "Jarvis, interpret between English and Spanish."

Jarvis becomes a live interpreter: whatever is said in one language it says in the other, straight away,
nothing added, for everyone in the room (not only the user) — until "stop interpreting". The state shows on
screen. Works on the phone too, which is the point when you're abroad.
"""
from __future__ import annotations

from core import outcome

_state = {"on": False, "a": "", "b": ""}


def active() -> bool:
    return bool(_state["on"])


PLUGIN = {
    "name": "interpreter",
    "description": (
        "Live interpreter mode between two languages (start with language_a and language_b; stop). While on, "
        "translate EVERYTHING you hear — from anyone in the room, not only the user — into the other language, "
        "immediately, nothing added, no commentary, in a natural voice; ignore the usual rule about staying quiet "
        "when the user talks to someone else. Use for 'interpret for me', 'translate between English and Hindi', "
        "'be my translator'; stop for 'stop interpreting' / 'that's enough translating'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["start", "stop", "status"]},
            "language_a": {"type": "STRING", "description": "Usually the user's language, e.g. English"},
            "language_b": {"type": "STRING", "description": "The other person's language, e.g. Spanish"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Live two-way interpreter: start / stop.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    if action == "start":
        a = str(parameters.get("language_a") or "English").strip()
        b = str(parameters.get("language_b") or "").strip()
        if not b:
            return outcome.ask("interpreter", "Which language should I interpret to and from?")
        _state.update(on=True, a=a, b=b)
        try:
            if player:
                player.show_content("INTERPRETER", f"{a.upper()}  ⇄  {b.upper()}\nSay \"stop interpreting\" to end.")
        except Exception:
            pass
        return outcome.done("interpreter_start", between=f"{a} and {b}",
                            note=f"from now on: everything you hear in {a}, say in {b}; everything in {b}, say in "
                                 f"{a}; only the translation, immediately, from anyone speaking; first say in both "
                                 "languages, in a few words, that you're ready to interpret")
    if action == "stop":
        was = f"{_state['a']} and {_state['b']}" if _state["on"] else ""
        _state.update(on=False)
        return outcome.done("interpreter_stop", was=was or None,
                            note="interpreting is over: answer normally again, in the user's language")
    return outcome.done("interpreter_status", on=_state["on"], between=f"{_state['a']} and {_state['b']}" if _state["on"] else None)
