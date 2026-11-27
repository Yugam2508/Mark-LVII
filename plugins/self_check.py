"""
plugins/self_check.py — "run a self-check": find out what is actually broken, and say why.

    "Run a self-check" / "is everything working?" / "why can't you take a screenshot?"

Each part is tried for real (a screenshot is grabbed, a file is written and read back, Notion is asked
who it is talking to), and the exact reason for a failure is shown, so a vague "it doesn't work" becomes
one sentence that can be fixed.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from core import outcome

PLUGIN = {
    "name": "self_check",
    "description": (
        "Tests Jarvis's own parts for real and reports exactly what is broken and why: screenshots, "
        "the notes folder (write and read back), Notion, dictation, the phone link, API keys. Use when "
        "the user says something isn't working, asks 'is everything working', 'run a self-check', "
        "'why can't you take a screenshot', or after a tool failed in a way you can't explain."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    "tier": "core",
    "brief": "Self-check: test screenshot, notes, Notion, phone link; say what's broken.",
}


def _screenshot() -> str:
    from actions import screen_processor as sp
    png, _ = sp._capture_screen()
    if len(png) < 2000:
        raise RuntimeError("the capture came back empty (a locked screen, or another program blocking it)")
    return f"works ({len(png) // 1024} KB)"


def _notes() -> str:
    from plugins import notes
    path = notes._local_path()
    probe = path.parent / f".jarvis-selfcheck-{int(time.time())}.tmp"
    probe.write_text("ok", encoding="utf-8")
    ok = probe.read_text(encoding="utf-8") == "ok"
    probe.unlink(missing_ok=True)
    if not ok:
        raise RuntimeError("wrote a file but could not read it back")
    return f"folder writable: {path.parent}"


def _dictation() -> str:
    from core import dictation
    d = dictation.folder()
    probe = Path(d) / ".selfcheck"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return f"can write to {d}"


def _notion() -> str:
    from plugins import notion
    if not notion._token():
        raise RuntimeError("no Notion secret set (⚙ → PLUGIN SETTINGS → NOTION)")
    me = notion.api("GET", "/users/me")
    home = notion.home_page()
    if home is None:
        return f"connected as {me.get('name') or 'the integration'}, but NO home page is set, so notes can't go to Notion"
    notion.api("GET", f"/blocks/{home}/children?page_size=1")
    return f"connected as {me.get('name') or 'the integration'}; the home page is readable"


def _phone() -> str:
    from core import addons
    d = getattr(addons.assistant(), "_dashboard", None)
    if d is None:
        raise RuntimeError("the phone link isn't running")
    phones = [p.get("name", "phone") for p in getattr(d, "_phones", {}).values()]
    return ("phone linked: " + ", ".join(phones)) if phones else "link is up, but no phone is connected"


def _keys() -> str:
    from memory.config_manager import load_api_keys
    cfg = load_api_keys()
    return "Gemini key present" if cfg.get("gemini_api_key") else "NO Gemini key"


def run(parameters: dict, player=None, session_memory=None) -> str:
    lines, bad = [], 0
    for name, fn in (("Screenshot", _screenshot), ("Notes folder", _notes), ("Dictation", _dictation),
                     ("Notion", _notion), ("Phone link", _phone), ("API keys", _keys)):
        try:
            lines.append(f"OK    {name}: {fn()}")
        except Exception as e:
            bad += 1
            lines.append(f"FAIL  {name}: {str(e)[:200]}")
    text = "\n".join(lines)
    if player:
        try:
            player.show_content("SELF-CHECK", text)
        except Exception:
            pass
    return outcome.done("self_check", failures=bad) + "\n" + outcome.untrusted("self-check", text)
