"""
plugins/personality.py — "be more sarcastic", "stop calling me sir", "what have I asked you to change?"

Shapes JARVIS's one personality (core/personality.py) by conversation. A change
applies straight away — the tool result tells the model to behave that way from
now on — and is saved, so the next session starts with it. Nothing reconnects.
"""
from __future__ import annotations

from core import outcome, personality

PLUGIN = {
    "name": "personality",
    "description": (
        "Adjusts the assistant's own personality and manner when the user asks: tone, humour, "
        "how chatty, how to address them, accent or way of speaking. Use 'adjust' for 'be more "
        "sarcastic', 'call me by my name', 'less formal', 'talk with a slight British accent'; "
        "'list' for 'what have I asked you to change about yourself'; 'remove' to drop one "
        "(by number); 'reset' to go back to default. Pass the request in the user's words. "
        "Never use it to imitate a real person or a film character — offer the qualities instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["adjust", "list", "remove", "reset"]},
            "change": {"type": "STRING", "description": "For adjust: the change, in the user's words"},
            "number": {"type": "INTEGER", "description": "For remove: number from the list"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Personality tweaks: adjust / list / remove / reset.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    try:
        items = personality.tweaks()
        if action == "adjust":
            change = str(parameters.get("change") or "").strip()
            if not change:
                return outcome.ask("personality_adjust", "What would you like me to change?")
            # a newer instruction on the same thing replaces the older one
            low = change.lower()
            items = [x for x in items if x.lower() != low]
            items.append(change)
            personality.save_tweaks(items)
            return outcome.done("personality_adjust", saved=change,
                                note="behave this way from this moment on, in this conversation and "
                                     "every later one; acknowledge in a few words, already in the "
                                     "new manner")
        if action == "remove":
            n = int(parameters.get("number") or 0)
            if not 1 <= n <= len(items):
                return outcome.ask("personality_remove", "Which one? Say its number.")
            gone = items.pop(n - 1)
            personality.save_tweaks(items)
            return outcome.done("personality_remove", removed=gone,
                                note="stop doing that from now on")
        if action == "reset":
            personality.save_tweaks([])
            return outcome.done("personality_reset",
                                note="back to your default character from now on")
        text = "\n".join(f"{i}. {x}" for i, x in enumerate(items, 1)) or "No changes — default character."
        return outcome.done("personality_list", count=len(items)) + "\n" + \
            outcome.untrusted("personality", text)
    except Exception as e:
        return outcome.failed(f"personality_{action}", str(e)[:150])
