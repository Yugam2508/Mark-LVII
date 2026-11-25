"""
core/edition.py — which version of this fork is running, and what changed.

Shown in the header ("MARK LVII · YUGAM EDITION · v1.4"), in the status bar, in
the WHAT'S NEW panel that opens once after each update (and when the version
label is clicked), and to the assistant itself through plugins/about_jarvis.py,
so "what's new?" has a real answer.

When you add features, bump VERSION and put a new entry at the top of CHANGELOG.
"""
from __future__ import annotations

VERSION = "1.4"
DATE = "2026-11-26"

CHANGELOG = [
    {"version": "1.4", "date": "2026-11-26", "items": [
        "Life profile: Jarvis remembers who you are and everything you tell it about your "
        "studies, work, music lessons, comedy and writing, travel goals and training — with "
        "goals and a dated log for each, kept in OneDrive so every device knows",
        "Version label in the header and this What's new panel, so you can see an update landed",
        "Ask \"what's new?\" or \"what can you do?\" and Jarvis answers from this list",
    ]},
    {"version": "1.3", "date": "2026-11-25", "items": [
        "Update yourself: say \"update yourself\" — no more reinstalling",
        "Phone link (ntfy): alerts on your phone when you're away, commands from your phone, "
        "PC-to-PC control, Wake-on-LAN, queued commands for a PC that is off, per-PC permissions",
        "Proactive agents: price-drop alerts, automatic exam and interview prep, daily digest",
        "Games: \"launch Valorant\", recently played (Steam, Epic, Riot, Battle.net)",
        "Morning briefing covers your day first: calendar, important email, to-dos, weather",
        "Study timer with study mode, break quizzes from your notes and weekly stats",
        "Screen helper: \"summarise this page\", \"explain this\", save the page for later",
        "Money tracker in a Google Sheet with budgets",
        "Reading & watch list in Google Tasks",
        "EDIT on confirmations; drafts, replies, notes and events open editable",
        "Talking over Jarvis now interrupts it (bug fixed, on by default)",
    ]},
    {"version": "1.2", "date": "2026-11-24", "items": [
        "Claude through your Claude subscription (Claude Code) — no API key",
        "Writing voice: emails and documents written in your style",
        "Proactive alerts: important email with suggested replies, calendar from email, reminders",
        "Modes: work, study, music, watching, gaming (automatic when a game starts)",
        "Spotify on a chosen device; Google Drive & Docs; Notion; notes",
    ]},
    {"version": "1.1", "date": "2026-11-24", "items": [
        "Gmail, Google Calendar and a to-do list in Google Tasks",
        "Spotify control, Claude with an API key, background agents (digest, study coach, deal hunter)",
        "Knowledge folder, smart home (Home Assistant), memory synced between PCs",
        "One-step Windows installer",
    ]},
]


def edition_name() -> str:
    """'YUGAM EDITION' from the name you gave at first launch, else 'PERSONAL EDITION'."""
    try:
        from memory.config_manager import get_user_name
        name = (get_user_name() or "").strip()
    except Exception:
        name = ""
    first = name.split()[0].upper() if name else ""
    return f"{first} EDITION" if first and first.lower() not in ("sir", "madam", "boss") else "PERSONAL EDITION"


def label() -> str:
    return f"{edition_name()}  ·  v{VERSION}"


def whats_new_text(all_versions: bool = False) -> str:
    entries = CHANGELOG if all_versions else CHANGELOG[:1]
    out = []
    for e in entries:
        out.append(f"v{e['version']} — {e['date']}")
        out += [f"  • {i}" for i in e["items"]]
        out.append("")
    return "\n".join(out).strip()


def unseen() -> bool:
    """True once after each update (per computer)."""
    try:
        from memory.config_manager import get_plugin_setting
        return str(get_plugin_setting("edition", "last_seen", "") or "") != VERSION
    except Exception:
        return False


def mark_seen() -> None:
    try:
        from memory.config_manager import save_plugin_config
        save_plugin_config("edition", {"last_seen": VERSION})
    except Exception:
        pass
