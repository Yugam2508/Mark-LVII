"""
core/claims.py — catch "I've saved that" when nothing was saved.

A live voice model can say "noted" or "I've added it" without calling any tool; the user hears a promise
and later finds nothing. main.py checks each finished turn: the user spoke, Jarvis claimed to have saved or
added something, and no tool ran in that turn -> Jarvis is told at once to either do it now or say plainly
that it is not saved. Turns Jarvis was prompted into by the app itself (a result being reported) are skipped.
"""
from __future__ import annotations

import re

_CLAIM = re.compile(
    r"\b("
    r"i(?:'ve| have) (?:saved|noted|added|stored|written|logged|recorded|made a note|put it|set (?:a|the|your) reminder)"
    r"|(?:it's|it is|that's|that is|they're|they are|all) (?:saved|noted|added|stored|logged|recorded|written down)"
    r"|saved (?:it|that|them|this)\b"
    r"|added (?:it|that|them|this|those) (?:to|in)"
    r"|i(?:'ll| will) remember (?:that|this|it)"
    r"|got (?:it|that) (?:down|saved|noted)"
    r"|made a note"
    r"|(?:^|[.!] )noted[.!,]"
    r")", re.I)

CORRECTION = (
    "[SYSTEM] Check on your last reply: you said something was saved, noted or added, but no tool was called "
    "in that turn, so NOTHING was saved. If the user wanted it kept, call the right tool now (save_memory for a "
    "fact about them, notes for a note, todo_list for a task, dictation for something long, calendar_control "
    "for an event). If you can't, say plainly in one sentence that it is not saved yet. Don't apologise at length.")


def unbacked_save_claim(said: str, user_said: str, tool_ran: bool, seconds_since_app_prompt: float) -> bool:
    """True when this turn claims a save with nothing behind it."""
    if tool_ran or not (said or "").strip() or not (user_said or "").strip():
        return False
    if seconds_since_app_prompt < 30:            # reporting a result the app handed over: not a new claim
        return False
    return bool(_CLAIM.search(said))
