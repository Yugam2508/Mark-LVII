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
    """61 -> 'LXI'."""
    out = ""
    for value, sym in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                       (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out += sym
            n -= value
    return out


MARK_NUMBER = 61                      # <- the only number to change at each update
MARK = roman(MARK_NUMBER)             # "LXI"
VERSION = MARK                        # what "have I seen this release?" compares
DATE = "2026-11-27"

CHANGELOG = [
    {"version": "LXI", "date": "2026-11-27", "items": [
        "Jarvis can operate any app on your phone when you ask: \"what's on my phone screen?\", \"tap Sign in\", "
        "\"scroll down\", \"type hello\", \"go back\", \"go home\", \"open my notifications\" — through the optional "
        "accessibility switch; taps on anything that sends, pays, buys, deletes or posts ask you first",
        "Windows by voice: \"switch to Chrome\", \"snap VS Code to the left\", \"move Spotify to my other screen\", "
        "\"maximise this\", \"minimise everything\", \"close Notepad\" (politely — it can still ask to save)",
        "Clipboard history: \"what did I copy earlier?\", \"copy that link again\", \"paste the address I copied\" — the "
        "last 40 things you copied, kept in memory only and never written to disk",
        "Real weather: \"what's the weather?\" now answers from a forecast service (it used to open a Google search) — "
        "now, when the rain comes, today / tomorrow / the week — for your home city unless you name one (set it in "
        "CONVERSATION & PRESENCE → Home city, or just tell Jarvis where you live)",
        "\"Show me my day\": one TODAY panel with your calendar, to-dos, weather and rain, study so far, what Jarvis is "
        "working on and your phone's battery, and a two-sentence summary",
        "From any app on the PC: Ctrl+Alt+S stops Jarvis talking and Ctrl+Alt+M mutes or unmutes the microphone "
        "(Esc and F4 only worked while Jarvis's window was in front); \"Hey Jarvis\" on the phone lights a PHONE "
        "satellite on the PC's hologram",
        "Releases are named by Mark only, everywhere — the What's new panel, \"which Mark are you?\", the phone app "
        "in Android's settings — never \"version\"",
    ]},
    {"version": "LX", "date": "2026-11-27", "items": [
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
        "Notion by name: \"add this to my Jarvis ideas page\" finds the page itself (no search-then-number step), "
        "and long pages are created in full. Remembering a fact now reports when it did NOT save, instead of "
        "always answering ok; session summaries keep every item of a list you gave",
        "\"Save this to Notion\" now really goes to Notion (it used to follow the default notes place and could "
        "still say Notion). Phone: \"send this to my phone\" (text, a link or the PC clipboard: copied there and "
        "shown as a notification), \"where's my phone?\" with a map link, Do Not Disturb on/off",
        "After you confirm something (a message, a reply, an install, organising a folder) Jarvis now tells you "
        "how it really went; before, the result only reached the log, so Jarvis could only guess",
        "PC care: Wi-Fi (what you're on, networks around, switch network, the Wi-Fi password), \"update all my apps\" "
        "(winget, confirmed), Recycle Bin size and emptying, an internet speed test, what starts with Windows, "
        "battery health (wear and cycles), and your local / Tailscale / public IP",
        "Daily backups of Jarvis's memory, conversation log and settings to OneDrive/JARVIS Backups (keys and "
        "passwords blanked unless you allow them); \"restore my Jarvis backup\" after a reinstall",
        "Phone app: a ⋮ button opens \"Permissions & setup\" (phones have no menu key, so those switches were "
        "out of reach), with a tick or cross for each permission and one tap to fix it, including battery "
        "restrictions that kill the link; \"Share → Jarvis (to my PC)\" from any app puts text on the PC "
        "clipboard and opens links there; the PC says when the phone battery is low; \"what did Mum text me?\" "
        "reads your texts; opening apps or links on the phone now says when Android blocked it instead of "
        "claiming it worked; headphones and Bluetooth headsets are used when connected",
        "Smaller fixes: repeated notices no longer stack up as identical cards; the header and footer use your "
        "name from memory when the setup name was 'sir'; WhatsApp from the PC presses Enter only when WhatsApp is "
        "in front and adds your country code to local numbers; organising Downloads leaves files that are still "
        "downloading; \"sleep\" really sleeps; temp cleanup leaves anything used in the last day; a forgotten "
        "dictation saves itself after four quiet minutes",
        "\"Take a screenshot\" was only opening the Snipping Tool and waiting for a drag, so nothing was ever "
        "saved; it now saves the whole screen (\"snip\" still opens the tool). Study sessions have a focus guard: "
        "if YouTube, a game or social media holds the screen for a minute during a block, Jarvis nudges you back",
        "Phone: \"set an alarm for 7 on my phone\", and with the accessibility switch on, \"take a screenshot on my "
        "phone\" and \"lock my phone\"; the phone timer's label and the send-to-phone heading now reach the phone",
        "If Jarvis says \"saved\", \"noted\" or \"I've added it\" in a turn where no tool ran, it is told at once "
        "to do it properly or say it isn't saved — the \"it said it saved it and hadn't\" problem, caught as it happens",
        "The always-listening phone no longer streams silence: it sends the microphone only while someone talks "
        "(plus a moment either side), which saves roughly 100 MB of mobile data an hour and battery; the PC "
        "microphone stays off the whole time the phone is your speaker (switch in ⋮ → Permissions & setup)",
        "\"Hey Jarvis\" on the phone: the phone listens all the time once the app is open (no button), and nothing it "
        "hears reaches Jarvis until the PC's wake-word detector hears \"Hey Jarvis\" in it — then the whole sentence "
        "goes through, with a chime and a buzz, and the conversation flows until it's quiet for a while. Tap the orb "
        "to talk without the phrase, long-press to send it back to waiting; the screen says which state it's in. "
        "If the PC hasn't got the wake word yet it sets it up once and listens to everything meanwhile",
        "Protocols, Tony-style: \"create a night protocol: lock the PC, phone on Do Not Disturb, lights off\", then "
        "\"initiate night protocol\" runs every step (anything that needs your OK still asks); \"what protocols do I "
        "have?\", add or delete steps by voice",
        "\"Run diagnostics\": a status readout of processor, memory, graphics, disks, temperatures, battery, internet "
        "latency, whether your Gemini key is answering (or blocked / out of quota), Tailscale, the phone link, backups "
        "and the wake word, with Jarvis saying only what needs attention",
        "A controllable agent: \"what are you working on?\" lists everything running in the background (installs, "
        "updates, deep thinking, speed tests, dictation, Claude Code jobs, agent tasks) and \"stop that\" / \"cancel "
        "the install\" stops it — or says plainly when something can't be stopped half-way",
        "Interrupting: \"stop\", \"wait\", \"hold on\" now just stop Jarvis (no \"okay, stopping\"), \"go on\" picks up "
        "where it was cut off, and tapping the orb on the phone while Jarvis talks cuts it off instantly on both devices",
        "A more alive hologram: a wireframe globe turns inside the core, a field of motes drifts in while Jarvis "
        "listens and is blown outward when it speaks, live processor / memory / network / graphics gauges sit "
        "around the dial, the whole thing leans slightly toward your mouse, and every new card is projected — a "
        "beam from the core, the frame drawing itself, a scan line revealing the content",
        "One Jarvis instead of a menu of agents: background work picks its own way of working (research with "
        "checked sources, price hunting, a study pack, a news digest, or general work) from what you ask — "
        "nobody has to choose a \"researcher\" or a \"general\" agent any more",
        "Easier to drive: the tray icon has a Quick menu (diagnostics, what's running, stop everything, screenshot, "
        "back up, what did I miss) and a wake-word switch, and a confirmation that goes up while Jarvis is hidden in "
        "the tray pops up a notification. Phone: a Jarvis tile in the pull-down Quick Settings, Mute and Stop on the "
        "listening notification (tap it to open the app), \"Tailscale looks off — tap to open it\" when the PC can't "
        "be reached, and long-press the conversation to copy it",
        "Talk to the display like Tony: \"close that\", \"close the weather\", \"clear the screen\", \"pin the calendar\", "
        "\"expand the email\", \"full screen\", \"switch to panels\", \"hide\" — and the phone's orb now has the same "
        "living layers as the PC (glow, drifting motes, ripples on loud moments, a turning globe in the core)",
        "\"Sir, Mum is calling your phone\": when your phone rings, the PC says who it is (or shows a card if you're "
        "busy), and \"answer it\" / \"decline it\" presses the call's own buttons on the phone (needs notification access)",
        "Confirm from the phone: when Jarvis needs your OK (a text, an install), the phone shows it with CONFIRM and "
        "CANCEL — in the app and as a notification you can answer from the lock screen; a stale card can never "
        "confirm a different request",
        "Fixed the Android build error (\"Can not extract resource\" in mergeDebugResources)",
        "Deep thinking is sturdier: a model your OpenAI key can't call is skipped for the next one, the real "
        "OpenAI error is shown instead of a guess, and after every route fails it waits five minutes instead "
        "of failing again and again",
    ]},
    {"version": "LIX", "date": "2026-11-26", "items": [
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
    {"version": "LVIII", "date": "2026-11-26", "items": [
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


_HONORIFICS = {"sir", "madam", "boss", "mr", "mrs", "ms", "miss", "maam", "ma'am", "master", "chief", "dear", "friend"}


def owner_first_name() -> str:
    """The owner's first name: the name typed at first launch, or, when that was an honorific like
    'sir', the name Jarvis has in memory (from 'my name is…' / 'call me…'). '' when neither is known."""
    try:
        from memory.config_manager import get_user_name
        parts = (get_user_name() or "").strip().split()
        if parts and parts[0].strip(".,").lower() not in _HONORIFICS:
            return parts[0].strip(".,")
    except Exception:
        pass
    try:
        from memory.memory_manager import load_memory
        ident = load_memory().get("identity", {}) or {}
        for key in ("name", "first_name", "preferred_name", "nickname"):
            v = ident.get(key)
            v = v.get("value") if isinstance(v, dict) else v
            parts = str(v or "").strip().split()
            if parts and parts[0].strip(".,").lower() not in _HONORIFICS:
                return parts[0].strip(".,")
    except Exception:
        pass
    return ""


def edition_name() -> str:
    """'YUGAM EDITION' from your name (first launch, or what Jarvis remembers), else 'PERSONAL EDITION'."""
    first = owner_first_name().upper()
    return f"{first} EDITION" if first else "PERSONAL EDITION"


def entry_tag(version: str) -> str:
    """'LVIII' -> 'MARK LVIII'. The fork's early updates ('1.8') were updates of Mark LVII:
    'MARK LVII · UPDATE 8'. Releases are named by Mark only — never 'version'."""
    if version[:1].isdigit():
        return f"MARK LVII · UPDATE {version.split('.')[-1]}"
    return f"MARK {version}"


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
