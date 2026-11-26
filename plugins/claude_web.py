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

WORK LAPTOP: set "Open Claude in" to the desktop app (or say "use the desktop app") and
the same things work in the Claude desktop app instead of Chrome: it is started the way
Windows starts any app (Start menu entry), the message is pasted into its window, and
Enter is pressed only when that window is in front.

SETTING IT UP BY VOICE: with your Jarvis session open in Chrome, say "remember this as my
Jarvis session" — Jarvis copies the page address from the browser bar and saves it.

Windows only for the Chrome/desktop part (profile lookup, app start, window check);
elsewhere it opens the default browser.
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


def desktop_app_id() -> str:
    """The Start-menu AppID of the Claude desktop app ('' if not installed). Works for
    both the Store/MSIX and the classic installer, which `Get-StartApps` lists alike."""
    if sys.platform != "win32":
        return ""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Get-StartApps | Where-Object { $_.Name -eq 'Claude' } | "
                            "Select-Object -First 1 -ExpandProperty AppID"],
                           capture_output=True, text=True, timeout=20, creationflags=0x08000000)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def target() -> str:
    t = str(_s("open_in", "chrome")).lower()
    return "desktop" if t.startswith("desktop") else "chrome"


def open_desktop() -> tuple[bool, str]:
    app = desktop_app_id()
    try:
        if app:
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app}"], close_fds=True)
            _state["opened_at"] = time.time()
            return True, "opened the Claude desktop app (use its Code tab for sessions)"
        if sys.platform == "win32":
            os.startfile("claude://")            # the app registers this link type
            _state["opened_at"] = time.time()
            return True, "asked Windows to open the Claude desktop app"
    except Exception as e:
        return False, f"could not start the Claude desktop app: {e}"
    return False, "the Claude desktop app was not found (install it from claude.ai/download)"


def open_page(url: str) -> tuple[bool, str]:
    """Open `url` in the configured Chrome profile — or the desktop app, when that is
    where the user works. (ok, message)."""
    if target() == "desktop":
        return open_desktop()
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
    if target() == "desktop":
        return t.strip().startswith("claude") and "chrome" not in t
    return "claude" in t and ("chrome" in t or "google" in t)


def learn_session_url() -> tuple[bool, str]:
    """Copy the address of the Claude page in front and keep it as the Jarvis session."""
    import pyautogui
    import pyperclip
    if sys.platform == "win32" and not ("claude" in foreground_title().lower()
                                         and "chrome" in foreground_title().lower()):
        return False, "open your Jarvis session in Chrome and leave it in front first"
    old = ""
    try:
        old = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy("")
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.4)
    url = (pyperclip.paste() or "").strip()
    pyautogui.press("escape")
    try:
        pyperclip.copy(old)
    except Exception:
        pass
    if not url.startswith("https://claude.ai/code/"):
        return False, "that page isn't a Claude Code session (its address starts claude.ai/code/…)"
    from memory.config_manager import get_plugin_config, save_plugin_config
    cfg = get_plugin_config(NAMESPACE)
    cfg["session_url"] = url
    save_plugin_config(NAMESPACE, cfg)
    return True, url


def focus_claude() -> bool:
    """Bring the Claude window (Chrome tab or desktop app) to the front. True when it is."""
    if claude_in_front():
        return True
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        want_desktop = target() == "desktop"
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                n = user32.GetWindowTextLengthW(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    user32.GetWindowTextW(hwnd, buf, n + 1)
                    t = buf.value.lower()
                    if "claude" in t and (("chrome" not in t) if want_desktop else ("chrome" in t)):
                        found.append(hwnd)
            return True
        user32.EnumWindows(each, 0)
        if not found:
            return False
        hwnd = found[0]
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)                       # SW_RESTORE
        user32.keybd_event(0x12, 0, 0, 0)                    # a tap of Alt lets us take focus
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.6)
        return claude_in_front()
    except Exception:
        return False


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
        # a slow page may still be coming up; then take the window to the front
        for _ in range(8):
            if claude_in_front() or focus_claude():
                break
            time.sleep(0.5)
        if not claude_in_front():
            return False, ("I couldn't find the Claude window to paste into (the text is on your "
                           "clipboard)")
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
        f"ADDONS.md and the changelog in core/edition.py (bump MARK_NUMBER by one — releases are numbered by Mark: LVIII, LIX, …), run the existing "
        f"tests, and open a pull request against main on my fork. I'll say 'merge it' when I've "
        f"seen it. After it merges I'll tell Jarvis to 'update yourself'."
    )


# ── self-check ────────────────────────────────────────────────────────────────

def check() -> list[str]:
    """What this PC has for Claude on the web. Also: python -m plugins.claude_web"""
    out: list[str] = []
    ok = lambda m: out.append("OK    " + m)
    bad = lambda m, fix="": out.append("FAIL  " + m + (f"\n      FIX: {fix}" if fix else ""))
    for mod in ("pyautogui", "pyperclip"):
        try:
            __import__(mod); ok(f"{mod} is installed")
        except Exception:
            bad(f"{mod} is missing", "run the installer again (it installs requirements.txt)")
    ok(f"Claude opens in: {target()}")
    if target() == "chrome":
        exe = chrome_exe()
        (ok if exe else bad)(f"Chrome: {exe}" if exe else "Chrome was not found")
        name = str(_s("chrome_profile", "yugamsmart"))
        prof = find_profile(name)
        if prof:
            ok(f"Chrome profile '{prof[0]}' found")
        else:
            bad(f"no Chrome profile named '{name}'. Profiles seen: {', '.join(sorted(profiles())) or 'none'}",
                "set the exact profile name in settings → CLAUDE ON THE WEB")
        if str(_s("session_url", "")).startswith("https://claude.ai/"):
            ok("Jarvis session address is saved")
        else:
            bad("no Jarvis session address saved yet (it will open claude.ai/code instead)",
                "open the session in that Chrome profile and say: 'remember this as my Jarvis session'")
    else:
        app = desktop_app_id()
        if app:
            ok(f"Claude desktop app found ({app})")
        else:
            bad("the Claude desktop app was not found in the Start menu",
                "install it from claude.ai/download, sign in, then run this check again")
    return out


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
            "action": {"type": "STRING", "enum": ["open", "send", "submit", "improve", "status", "learn_session", "use"]},
            "where": {"type": "STRING", "enum": ["chrome", "desktop"],
                      "description": "For 'use': open Claude in Chrome (home) or the desktop app (work)"},
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
        {"key": "open_in", "label": "Open Claude in (chrome = your profile, desktop = the Claude app)",
         "type": "choice", "options": ["chrome", "desktop"], "default": "chrome"},
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
            lines = check()
            addons.show("CLAUDE ON THE WEB — CHECK", "\n".join(lines))
            return outcome.done("claude_web_check", failures=sum(l.startswith("FAIL") for l in lines)) + \
                "\n" + outcome.untrusted("claude_web", "\n".join(lines)) + \
                "\nIn two sentences tell the user what works and what to fix."
        if action == "use":
            where = "desktop" if str(parameters.get("where") or "").lower().startswith("desk") else "chrome"
            from memory.config_manager import get_plugin_config, save_plugin_config
            cfg = get_plugin_config(NAMESPACE); cfg["open_in"] = where; save_plugin_config(NAMESPACE, cfg)
            return outcome.done("claude_web_use", now=where)
        if action == "learn_session":
            ok, msg = learn_session_url()
            return outcome.done("claude_web_learn", saved=msg) if ok else outcome.failed("claude_web_learn", msg)
        if action == "open":
            ok, msg = open_page(session_url())
            return outcome.done("claude_web_open", result=msg) if ok else outcome.failed("claude_web_open", msg)

        if action == "submit":
            if not _state["last_message"]:
                return outcome.failed("claude_web_submit", "nothing has been pasted yet")
            if sys.platform == "win32" and not focus_claude():
                return outcome.failed("claude_web_submit", "I couldn't find the Claude window to send "
                                      "from, so I didn't press Enter (nothing was sent anywhere else).")
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


if __name__ == "__main__":      # python -m plugins.claude_web
    print("\n".join(check()))
