"""
core/edition.py — which release of this fork is running, and what changed.

RELEASES ARE NUMBERED BY MARK. Fatih's project counts its generations in Roman
numerals (Mark LVII); this fork now does too, instead of v1.x: every update
bumps the Mark — LVIII, LIX, LX… — and says so in the header ("MARK LVIII ·
YUGAM EDITION"), the status bar, the WHAT'S NEW panel that opens once after each
update (and when the header label is clicked), and to the assistant itself
through plugins/about_jarvis.py, so "what's new?" has a real answer.

To release: raise MARK_NUMBER by one, set DATE, and put a new entry at the top
of CHANGELOG with "version": MARK. (Entries before Mark LVIII keep their old
"1.x" numbers.)
"""
from __future__ import annotations


def roman(n: int) -> str:
    """60 -> 'LX'."""
    out = ""
    for value, sym in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                       (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out += sym
            n -= value
    return out


MARK_NUMBER = 60                      # <- the only number to change at each update
MARK = roman(MARK_NUMBER)             # "LX"
VERSION = MARK                        # what "have I seen this release?" compares
DATE = "2026-11-30"

CHANGELOG = [
    {"version": "LX", "date": "2026-11-30", "items": [
        "Deep thinking no longer jumps in on its own: Jarvis answers itself unless you ask (\"think harder\", "
        "\"are you sure?\", \"second opinion\") or doubt it; a switch in PLUGIN SETTINGS → DEEP THINKING lets it "
        "decide for itself again",
        "Dictation: say \"take dictation\" before a long ramble (a feature list, ideas) and the app writes every "
        "word to a file as you say it while Jarvis stays silent; \"end dictation\" saves it to your notes and "
        "tells you how many words were kept and whether they reached the notes. Nothing depends on the AI remembering",
        "Jarvis may no longer say \"saved\" unless a tool said so; Notion notes longer than 100 lines used to be "
        "silently cut off and are now sent in full (or reported as failed); \"run a self-check\" tests screenshots, "
        "notes, Notion, dictation and the phone link for real and says exactly what is broken",
        "Jarvis stops forgetting: every conversation is now kept word for word on this PC (memory/conversations), "
        "and \"what did I tell you yesterday about…\" searches it; before, a whole session shrank to two "
        "sentences when it ended. \"Take a screenshot\" now actually saves one to Pictures/Screenshots",
        "Fixed the Android build error (\"Can not extract resource\" in mergeDebugResources)",
        "Deep thinking is sturdier: a model your OpenAI key can't call is skipped for the next one, the real "
        "OpenAI error is shown instead of a guess, and after every route fails it waits five minutes instead "
        "of failing again and again",
    ]},
    {"version": "LIX", "date": "2026-11-30", "items": [
        "The phone is now Jarvis's microphone and speaker: it listens all the time (no button), plays "
        "Jarvis's own voice (same accent and personality as on the PC), the PC goes quiet while you use the "
        "phone so only one device answers, and what Jarvis shows on the PC appears on the phone too",
        "More hands: Bluetooth on/off and device list, install/uninstall apps (winget), run commands, "
        "tidy a messy folder by file type (with undo), open websites, and \"play my liked songs\"; on the "
        "phone: open any app or link, Bluetooth/Wi-Fi settings pages, volume, flashlight, timers, media keys, "
        "navigation. Anything that changes the PC asks you to confirm first; disk-wiping commands are refused",
        "Read and answer your phone's messages: \"any WhatsApp messages?\", \"reply to Aarav: on my way\" "
        "(shown for edit/confirm, sent through the notification's own Reply button, so it works for WhatsApp, "
        "Telegram, Messages and more), new chat messages announced as they arrive, \"did anyone call?\"; "
        "plus shut down / restart / sleep the PC (with a delay, confirmed) and clearing temp files",
        "WhatsApp that works: \"WhatsApp Mum I'm late\" finds her number (from your phone's contacts), shows "
        "the message to edit or confirm, opens the right chat and sends, from the PC or from the phone",
        "When Jarvis can't reach Google it now says why on screen (usage limit, blocked or invalid key, "
        "billing, Google overloaded, no network) instead of silently looking frozen",
        "The window footer credits you instead of the original author (the original credit stays in "
        "the README and LICENSE, as the licence requires)",
        "Jarvis can see inside the computer and act on it: which programs use the GPU/CPU/memory/disk/"
        "network/a port, find files on every drive (instant, from an index), what's taking disk space, "
        "delete to the Recycle Bin and close programs (always confirmed), and hand whole-computer jobs "
        "(\"clean up my D: drive\") to Claude Code, which proposes a plan first and runs it only on your confirm",
        "Hub mode: tell Jarvis \"this PC is my hub\" (or tick it in CONVERSATION & PRESENCE) and it stays awake "
        "while plugged in, starts at login and lives in the tray, so your phone can always reach it; ask "
        "\"hub status\" to see which phones are linked, the Tailscale address and what's holding it awake",
    ]},
    {"version": "LVIII", "date": "2026-11-30", "items": [
        "Releases are now numbered by Mark, like the project itself: this is Mark LVIII, "
        "the next will be Mark LIX (no more v1.x)",
        "Android app (android/): pair your phone with a Jarvis PC, talk or type, and make it "
        "the phone's assistant (long-press power); see android/README.md",
        "Jarvis can use your phone: \"call Mum\", \"text Aarav I'm running late\", \"find my phone\", "
        "\"how's my phone's battery\" — calls and texts always wait for your confirm",
        "Paired phones are remembered across Jarvis restarts (they used to be forgotten, which made "
        "the app ask to pair again); the PC stays awake on mains power while a phone is connected",
        "Deeper thinking on its own: when a question needs real reasoning, Jarvis isn't sure, or you "
        "doubt it in any words, it hands the question (with the conversation and your memory boxes) to "
        "a stronger model — your OpenAI keys (several, rotated when one runs out) or Claude through your "
        "subscription — and brings back the analysis; \"use Claude\" / \"add this OpenAI key\" by voice",
        "No more pairing code for your own devices: a phone on the same Tailscale account as the PC "
        "connects with just the address (others still need the key from Remote Control)",
    ]},
    {"version": "1.8", "date": "2026-11-30", "items": [
        "Phone pairing endpoint for the new Android app (android/): pair once with the Remote "
        "Control key and the phone is remembered",
    ]},
    {"version": "1.7", "date": "2026-11-29", "items": [
        "Memory boxes: 'WHO YOU ARE' (Jarvis's own character and rules) and 'THE ESSENTIALS' "
        "(what matters most about you) are always in front of Jarvis, in full, every session, "
        "and steer what it says. Tell it \"remember this always\" or \"this is who you are to me\"",
        "Claude on the web: opens your Chrome profile straight to your Jarvis session (or the "
        "Claude desktop app on a work laptop), pastes requests into it, and sends on your 'send it'. \"Add X to yourself\" drafts a proper "
        "feature request for Claude Code to build and open a pull request for",
        "'Diagnose Claude Code' and a phone-link check tell you exactly which step is broken "
        "and the one command that fixes it",
        "'Set up Notion' walks the setup step by step and takes the secret from your clipboard",
        "Jarvis lives in the system tray: closing the window keeps it listening, Ctrl+Alt+J brings "
        "it forward from any window, and Quit really quits",
        "Conversation handoff: the last turns follow you between devices (needs device sync); "
        "ask \"where were we on the desktop?\" any time",
        "'Send it' brings the Claude window forward itself, so it works from any window",
    ]},
    {"version": "1.6", "date": "2026-11-28", "items": [
        "Immersive layout: the holographic display fills the window; what Jarvis shows you "
        "slides out of the core as cards that drift away (pin or expand them), with live "
        "captions of the conversation and a slim command bar. F2 or ◫ switches to the panels",
        "Talking over Jarvis now stops it: real echo cancellation (the kind video calls use) "
        "tells your voice from its own, even on laptop speakers",
        "Phone dashboard over Tailscale: the firewall fix now also marks the Tailscale "
        "connection as private (and only that one)",
        "Updates no longer stop with 'files changed by hand' because of Jarvis's own settings",
        "One personality instead of voice presets: shape it by talking (\"be more sarcastic\", "
        "\"stop calling me sir\", \"a slight British accent\"); it applies at once, no reconnect, "
        "and is remembered. The persona presets are gone",
        "Changing the voice no longer loses the conversation: the last turns carry over, and "
        "it waits for the end of the sentence",
    ]},
    {"version": "1.5", "date": "2026-11-27", "items": [
        "Holographic HUD: rings that turn with what Jarvis is doing, a live voice spectrum, "
        "and satellites for each tool, panel and alert (HUD button cycles holo / face / core)",
        "Knows when you're talking to someone else and stays quiet; \"I'm talking to "
        "someone\" / \"I'm back\" pause and resume, with a summary of what you missed",
        "Busy or away? Alerts become cards that stay on screen (and a phone ping when you're "
        "away); when you're free it just tells you, and suggests what to do next",
        "Confirm or cancel by voice: say \"confirm\" or \"cancel\" instead of clicking",
        "Claude Code control: \"ask Claude Code to …\" in your projects — plan first, "
        "\"go ahead\", follow-ups, status, stop, open a window",
        "Voice personas: British butler, Irish co-pilot, mission control, Australian coach, "
        "deep mentor, Indian English, or your own; eight voices in Customize",
        "Audio follows your devices: headphones or Bluetooth connecting or disconnecting "
        "switches over by itself",
        "Phone dashboard works over Tailscale (QR code uses the 100.x address), with an "
        "optional secure link so the phone microphone works",
    ]},
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


def entry_tag(version: str) -> str:
    """'LVIII' -> 'MARK LVIII'; the older '1.8' -> 'v1.8'."""
    return f"v{version}" if version[:1].isdigit() else f"MARK {version}"


def tag() -> str:
    """This release, for display: 'MARK LVIII'."""
    return entry_tag(VERSION)


def label() -> str:
    """The edition line; the Mark itself is shown beside it by the header."""
    return edition_name()


def whats_new_text(all_versions: bool = False) -> str:
    entries = CHANGELOG if all_versions else CHANGELOG[:1]
    out = []
    for e in entries:
        out.append(f"{entry_tag(e['version'])} — {e['date']}")
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
