"""
plugins/about_jarvis.py — "what's new?", "what version are you?", "what can you do?"

The assistant has no memory of being updated, so without this it guesses — and
usually says nothing changed. This answers from core/edition.py, the same list
the WHAT'S NEW panel shows, and opens that panel.
"""
from __future__ import annotations

from core import edition, outcome

CAPABILITIES = """Email (Gmail): check, read, reply, draft, send with confirmation
Calendar: what's on, add, change, delete events; reminders before events
To-do list (Google Tasks, on the phone too)
Spotify: play anything, on any device (phone, laptop, desktop)
Games: launch by name, recently played
Writing in your style (Claude through your subscription); edit drafts before sending
Notes, knowledge folder (ask about your documents), Google Drive & Docs, Notion
Life profile: remembers you, your studies, work, lessons, comedy, travel, training
Proactive alerts and phone notifications; price-drop watches; exam and interview prep
Modes: work, study, music, watching, gaming
Study timer with quizzes; money tracker with budgets; reading & watch list
Phone and PC-to-PC control: wake the desktop, launch things on it, lock it, status
Morning briefing with your day; "summarise this page"; "explain this"
Update yourself; smart home (Home Assistant); memory shared between PCs"""

PLUGIN = {
    "name": "about_jarvis",
    "description": (
        "Answers questions about the assistant itself: what's new since the last update, "
        "what version is running, and what it can do. Use for 'what's new', 'did you "
        "update', 'what changed', 'what version are you', 'what can you do'. Always use "
        "this instead of guessing — you do not otherwise know what was added."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["whats_new", "version", "capabilities"]},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "What's new / version / capabilities of the assistant.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "whats_new")
    try:
        if action == "capabilities":
            if player:
                player.show_content(f"WHAT I CAN DO · {edition.tag()}", CAPABILITIES)
            return outcome.done("capabilities", version=edition.tag()) + "\n" + CAPABILITIES
        if action == "version":
            return outcome.done("version", version=edition.tag(), date=edition.DATE,
                                edition=edition.edition_name())
        if player:
            player.show_content(f"WHAT'S NEW · v{edition.VERSION}", edition.whats_new_text())
        return outcome.done("whats_new", version=edition.VERSION, date=edition.DATE,
                            note="summarise the top items in a sentence or two; the full list "
                                 "is on screen") + "\n" + edition.whats_new_text()
    except Exception as e:
        return outcome.failed("about", str(e)[:150])
