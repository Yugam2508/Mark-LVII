"""
plugins/about_jarvis.py — "what's new?", "what version are you?", "what can you do?"

The assistant has no memory of being updated, so without this it guesses — and
usually says nothing changed. This answers from core/edition.py, the same list
the WHAT'S NEW panel shows, and opens that panel.
"""
from __future__ import annotations

from core import edition, outcome

CAPABILITIES = """TALK  "Hey Jarvis" on the PC or the phone · interrupt with "wait" / "stop", then "go on" · tap the phone orb
REMEMBER  every conversation is kept: "what did I tell you yesterday about…" · "remember that…" · "take dictation"
PROTOCOLS  "create a night protocol: …" then "initiate night protocol" · "what protocols do I have?"
DISPLAY  "close that" · "clear the screen" · "pin the calendar" · "expand the email" · "full screen" · "hide"
THE PC  "run diagnostics" · "what's using my GPU?" · "where is my CV?" · "what's taking space on C:?"
        "delete it" (Recycle Bin, undo) · "organise my Downloads" · "install VLC" · "update all my apps"
        "turn Bluetooth on" · "what Wi-Fi am I on?" · "run a speed test" · "take a screenshot" · "shut down in 10 minutes"
        "back up Jarvis" · "clean my temp files" · "empty the Recycle Bin" · "this PC is my hub"
JOBS  "what are you working on?" · "stop that" · "cancel the install" · Claude Code: "ask Claude Code to…"
THE PHONE  "call Mum" · "text Aarav…" · "WhatsApp Riya…" · "any messages?" · "reply to him: on my way"
           "what did Mum text me?" · "did anyone call?" · "answer it" / "decline it" when it rings
           "find my phone" · "where's my phone?" · "open Spotify on my phone" · "set an alarm for 7 on my phone"
           "flashlight on" · "volume to 40" · "Do Not Disturb on" · "send this to my phone" · Share → Jarvis (to my PC)
MUSIC  "play my liked songs" · "play <a playlist> on the desktop" · "next" · "pause"
GOOGLE & NOTES  email, calendar, to-dos, Drive, Notion ("add this to my Jarvis ideas page"), notes, your knowledge folder
THINKING  "think harder about that" / "second opinion" (OpenAI or Claude) · background research: "look into… and report back"
STUDY  "start a 25 minute study session on chemistry" (nudges you off YouTube) · quizzes from your notes · study stats
LIFE  morning briefing · money tracker · reading & watch list · modes (work, study, gaming) · smart home
SELF  "run a self-check" · "what's new?" · "update yourself"
"""

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
            return outcome.done("capabilities", version=edition.tag(),
                                note="the full list with example phrases is on screen; mention three or four things "
                                     "that fit what they seem to want, not the whole list") + "\n" + CAPABILITIES
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
