"""
plugins/conversation_history.py — "what did I tell you yesterday about…?"

Reads the word-for-word conversation log (core/transcript.py): search it, or read a day back.
"""
from __future__ import annotations

from core import outcome, transcript

PLUGIN = {
    "name": "conversation_history",
    "description": (
        "Searches and reads back the full word-for-word log of past conversations with the user, kept "
        "on this PC (every day, both sides). Use whenever the user refers to something they told you "
        "before ('what did I say about…', 'the feature list I gave you', 'what were we talking about "
        "yesterday', 'find where I mentioned…'), or when you need to recover something you should "
        "have saved. Search with a few key words; read with a day ('today', 'yesterday', '3 days ago' "
        "or a date). Prefer this over saying you don't remember."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["search", "read"]},
            "query": {"type": "STRING", "description": "For search: a few key words"},
            "day": {"type": "STRING", "description": "For read: today, yesterday, 'N days ago' or YYYY-MM-DD"},
            "days": {"type": "INTEGER", "description": "For search: how many days back (default 30)"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Search/read the full log of past conversations.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "search")
    try:
        if action == "read":
            day = str(parameters.get("day") or "today")
            text = transcript.read(day, 150)
            if not text:
                return outcome.done("history_read", lines=0, note=f"nothing logged for {day}")
            if player:
                try:
                    player.show_content(f"CONVERSATION · {transcript.day_of(day).isoformat()}", text[-4000:])
                except Exception:
                    pass
            return outcome.done("history_read", lines=text.count("\n") + 1) + "\n" + outcome.untrusted("conversation log", text[-8000:])
        q = str(parameters.get("query") or "").strip()
        if not q:
            return outcome.ask("history_search", "What should I look for?")
        hits = transcript.search(q, int(parameters.get("days") or 30))
        if not hits:
            return outcome.done("history_search", matches=0)
        return outcome.done("history_search", matches=len(hits)) + "\n" + outcome.untrusted("conversation log", "\n".join(hits))
    except Exception as e:
        return outcome.failed(f"history_{action}", str(e)[:160])
