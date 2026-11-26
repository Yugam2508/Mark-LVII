"""
plugins/claude_web.py — work with Claude on claude.ai from Jarvis, in your own Chrome profile.

    "Open Claude Code"                              open      your Jarvis session, in the right profile
    "Ask Claude to add a pomodoro mode to yourself"  improve   writes a proper request, pastes it
    "Tell Claude: …"                                 send      pastes your words into the session
    "Send it" / "go ahead"                           submit    presses Enter, after checking the page
    "Add the study timer to your own features"       improve

How it works (no automation framework, nothing to log in to):
  1. finds your Chrome profile by its NAME (default "yugamsmart") in Chrome's own
     profile list, and opens Chrome with that profile — so you are already signed in;
  2. goes to the Jarvis session's address (copy it from the browser once and paste
     it into settings), or to claude.ai/code when none is set;
  3. PASTES the message into the page. It does not send it. You read it, then say
     "send it" and Jarvis presses Enter — but only if the Claude page is the window
     in front, so it can never type into something else.

"improve" (adding features to Jarvis itself) writes the request for you: what you asked
for, where Jarvis's code lives (its GitHub repo and branch rules), and the conventions
it must follow (AGENTS.md, one plugin per feature, tests, docs). It shows it for editing
and confirmation first. Claude then works in that session as usual; when a pull request
is ready, you say "merge it" there.

Windows only for the Chrome part (the profile lookup and window check); elsewhere it
opens the default browser.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from core import addons, outcome
from memory.config_manager import get_plugin_setting

NAMESPACE = "claude_web"
DEFAULT_URL = "https://claude.ai/code"
_state = {"last_message": "", "opened_at": 0.0}
_lock = threading.Lock()


def _s(key: str, default=""):
    v = get_plugin_setting(NAMESPACE, key, default)
    return default if v in (None, "") else v


# ── Chrome ────────────────────────────────────────────────────────────────────

def chrome_exe() -> str:
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application")):
            p = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe") \
                if "Application" not in base else os.path.join(base, "chrome.exe")
            if os.path.exists(p):
                return p
    return shutil.which("google-chrome") or shutil.which("chrome") or shutil.which("chromium") or ""


def user_data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    return Path.home() / ".config" / "google-chrome"


def profiles() -> dict[str, str]:
    """{profile display name: directory name} from Chrome's own Local State."""
    try:
        data = json.loads((user_data_dir() / "Local State").read_text(encoding="utf-8"))
        cache = (data.get("profile") or {}).get("info_cache") or {}
        return {str(v.get("name") or k): k for k, v in cache.items()}
    except (OSError, ValueError):
        return {}


def find_profile(name: str) -> tuple[str, str] | None:
    """(display name, directory) for a spoken/typed profile name, tolerant of case and spaces."""
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    want = norm(name)
    found = profiles()
    for disp, d in found.items():
        if norm(disp) == want:
            return disp, d
    for disp, d in found.items():
        if want and (want in norm(disp) or norm(disp) in want):
            return disp, d
    return None


def open_page(url: str) -> tuple[bool, str]:
    """Open `url` in the configured Chrome profile. (ok, message)."""
    name = str(_s("chrome_profile", "yugamsmart"))
    exe = chrome_exe()
    if not exe:
        import webbrowser
        webbrowser.open(url)
        return True, "Chrome was not found, so the default browser was used"
    prof = find_profile(name)
    if prof is None:
        have = ", ".join(sorted(profiles())) or "none found"
        return False, (f"No Chrome profile named '{name}'. Profiles I can see: {have}. "
                       f"Set the right name in settings → CLAUDE ON THE WEB.")
    try:
        subprocess.Popen([exe, f"--profile-directory={prof[1]}", url],
                         creationflags=0x00000008 if sys.platform == "win32" else 0,
                         close_fds=True)
    except OSError as e:
        return False, str(e)
    _state["opened_at"] = time.time()
    return True, f"opened in Chrome profile '{prof[0]}'"


def session_url() -> str:
    u = str(_s("session_url", "")).strip()
    return u if u.startswith("https://claude.ai/") else DEFAULT_URL


# ── the foreground window (so Enter never goes to the wrong place) ────────────

def foreground_title() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        h = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(h, buf, n + 1)
        return buf.value
    except Exception:
        return ""


def claude_in_front() -> bool:
    t = foreground_title().lower()
    return "claude" in t and ("chrome" in t or "google" in t)


def paste_message(text: str) -> tuple[bool, str]:
    """Put `text` in the clipboard and paste it into the focused Claude page."""
    import pyautogui
    import pyperclip
    old = ""
    try:
        old = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(text)
    if sys.platform == "win32" and not claude_in_front():
        # give a slow page a few more seconds to come to the front
        for _ in range(20):
            if claude_in_front():
                break
            time.sleep(0.5)
        if not claude_in_front():
            return False, "the Claude page isn't in front, so I didn't paste (it's on your clipboard)"
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    try:
        pyperclip.copy(old)
    except Exception:
        pass
    return True, "pasted"


# ── the self-improvement request ──────────────────────────────────────────────

def improvement_request(wish: str) -> str:
    repo = str(_s("repo", "Yugam2508/Mark-LVII"))
    return (
        f"This session is for improving my personal JARVIS assistant (repo: {repo}, a fork of "
        f"FatihMakes' Mark LVII). Please read AGENTS.md first and follow it: one plugin per "
        f"feature in plugins/, go through core/gemini and memory/config_manager, no new "
        f"dependencies unless needed (then requirements.txt), Windows is the target, keep the "
        f"code public-safe (nothing personal in the repo).\n\n"
        f"What I want added or changed:\n{wish.strip()}\n\n"
        f"Please: plan briefly, implement it, add or update an offline test, document it in "
        f"ADDONS.md and the changelog in core/edition.py (bump the version), run the existing "
        f"tests, and open a pull request against main on my fork. I'll say 'merge it' when I've "
        f"seen it. After it merges I'll tell Jarvis to 'update yourself'."
    )


# ── the tool ──────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "claude_web",
    "description": (
        "Works with Claude on claude.ai in the user's own Chrome profile (a Claude Code session "
        "for improving this assistant). 'open' opens the session; 'send' pastes a message into "
        "it (not sent yet); 'submit' presses Enter after the user has seen it ('send it', "
        "'go ahead'); 'improve' is for 'add X to yourself', 'give yourself the ability to …', "
        "'change how you …' — it drafts a proper feature request, asks the user to confirm, "
        "then pastes it. For quick edits to local project files use claude_code instead. "
        "Pass the user's wish in their words."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["open", "send", "submit", "improve", "status"]},
            "message": {"type": "STRING", "description": "For send: the text to paste"},
            "wish": {"type": "STRING", "description": "For improve: what to add or change, in the user's words"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Claude on the web: open the Jarvis session, paste, send; improve yourself.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "CLAUDE ON THE WEB",
    "fields": [
        {"key": "chrome_profile", "label": "Chrome profile name (as shown in Chrome's profile menu)",
         "type": "text", "placeholder": "yugamsmart"},
        {"key": "session_url", "label": "Address of the Jarvis session (copy it from the browser bar)",
         "type": "text", "placeholder": "https://claude.ai/code/session_…"},
        {"key": "repo", "label": "Jarvis's repository", "type": "text", "placeholder": "Yugam2508/Mark-LVII"},
        {"key": "wait_seconds", "label": "Seconds to wait for the page to load before pasting",
         "type": "choice", "options": ["4", "6", "10", "15"], "default": "6"},
    ],
    "action": {"label": "OPEN NOW", "run": lambda values: open_page(session_url())},
}


def _open_and_paste(text: str) -> str:
    ok, msg = open_page(session_url())
    if not ok:
        return outcome.failed("claude_web_open", msg)
    time.sleep(float(_s("wait_seconds", 6)))

    def go():
        try:
            done, m = paste_message(text)
        except Exception as e:
            done, m = False, str(e)
        addons.log("CLAUDE WEB: " + m)
        addons.notify("Claude page" if done else "Claude page — not pasted",
                      (text[:600] + "\n\n" if done else "") + (
                          "Pasted into the session. Say 'send it' when you're happy with it."
                          if done else m),
                      "[SYSTEM] " + ("The message is pasted into the Claude page but NOT sent. In one "
                                     "sentence tell the user to look at it and say 'send it'."
                                     if done else "Pasting into the Claude page failed: " + m +
                                     " In one sentence tell the user."),
                      kind="task" if done else "error")
    threading.Thread(target=go, daemon=True, name="claude_web_paste").start()
    return outcome.started("claude_web", note="opening the page; say you'll tell them when it is "
                           "pasted and that they must say 'send it' to submit")


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    try:
        if action == "status":
            prof = find_profile(str(_s("chrome_profile", "yugamsmart")))
            return outcome.done("claude_web_status", chrome=bool(chrome_exe()),
                                profile=prof[0] if prof else None,
                                profiles_seen=", ".join(sorted(profiles())) or None,
                                session=session_url())
        if action == "open":
            ok, msg = open_page(session_url())
            return outcome.done("claude_web_open", result=msg) if ok else outcome.failed("claude_web_open", msg)

        if action == "submit":
            if not _state["last_message"]:
                return outcome.failed("claude_web_submit", "nothing has been pasted yet")
            if sys.platform == "win32" and not claude_in_front():
                return outcome.failed("claude_web_submit", "the Claude page isn't the window in front, "
                                      "so I didn't press Enter. Click the page and try again.")
            import pyautogui
            pyautogui.press("enter")
            _state["last_message"] = ""
            return outcome.done("claude_web_submit", note="sent; Claude is working in the session — "
                                "tell them to say 'merge it' when the pull request is ready")

        if action in ("send", "improve"):
            if action == "improve":
                wish = str(parameters.get("wish") or parameters.get("message") or "").strip()
                if not wish:
                    return outcome.ask("claude_web_improve", "What should I add or change in myself?")
                text = improvement_request(wish)
                title = "Ask Claude to improve Jarvis"
            else:
                text = str(parameters.get("message") or "").strip()
                if not text:
                    return outcome.ask("claude_web_send", "What should I tell Claude?")
                title = "Paste this into the Claude session"

            def launch() -> str:
                _state["last_message"] = text
                return _open_and_paste(text)

            def launch_edited(values: dict) -> str:
                nonlocal text
                text = str(values.get("message") or text)
                return launch()

            from core import confirm
            return confirm.request("claude_web", title, text[:900], launch,
                                   fields=[{"key": "message", "label": "Message", "value": text,
                                            "multiline": True}],
                                   run_edited=launch_edited)
        return outcome.failed("claude_web", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"claude_web_{action}", str(e)[:200])
