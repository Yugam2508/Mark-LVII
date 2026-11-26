"""
plugins/updater.py — "Jarvis, update yourself." No more reinstalling.

    "Update yourself" / "Are there any updates?"     action=update / check

What an update does, in order:
    1. `git pull --ff-only` from your fork's main branch (the same thing the
       installer did, without the installer);
    2. if requirements.txt changed, installs the new packages into Jarvis's own
       Python environment;
    3. restarts Jarvis: a fresh copy is scheduled to start a few seconds later and
       this one closes the normal way (session summary saved, engines stopped).

It never overwrites your own changes: if files in the Jarvis folder were edited
by hand, git refuses and Jarvis says so. Your settings, keys and memory live in
files git does not track, so they are never touched.

Once a day it also checks quietly whether an update is waiting and mentions it
(⚙ → PLUGIN SETTINGS → UPDATES; it can also install automatically at start-up).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from core import addons, outcome
from memory.config_manager import get_plugin_setting

NAMESPACE = "updater"
REPO = Path(__file__).resolve().parent.parent
BRANCH = "main"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_lock = threading.Lock()
_state = {"last_check": None, "behind": 0, "busy": False}


def _git(*args: str, timeout: float = 120) -> subprocess.CompletedProcess:
    exe = shutil.which("git")
    if exe is None:
        raise RuntimeError("git is not installed (run install-windows.ps1 once more)")
    return subprocess.run([exe, "-C", str(REPO), *args], capture_output=True, text=True,
                          timeout=timeout, creationflags=_NO_WINDOW)


def _python_console() -> str:
    """python.exe next to the running pythonw.exe — pip wants a console interpreter."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return str(exe)


def check() -> tuple[int, str]:
    """(commits behind, one-line summary of what's new)."""
    if not (REPO / ".git").exists():
        raise RuntimeError("this copy of Jarvis was not installed with git")
    f = _git("fetch", "--quiet", "origin", BRANCH)
    if f.returncode != 0:
        raise RuntimeError("could not reach GitHub: " + (f.stderr.strip()[:120] or "fetch failed"))
    n = _git("rev-list", "--count", f"HEAD..origin/{BRANCH}")
    behind = int((n.stdout or "0").strip() or 0)
    log = _git("log", "--format=%s", f"HEAD..origin/{BRANCH}", "-n", "5").stdout.strip().splitlines()
    _state.update(last_check=time.strftime("%H:%M"), behind=behind)
    return behind, "; ".join(log)


def _blocking_files(err: str) -> list[str]:
    """The paths git lists (tab-indented) under 'would be overwritten'."""
    return [ln.strip() for ln in err.splitlines() if ln.startswith(("\t", "        ")) and ln.strip()]


def _is_own_file(rel: str) -> bool:
    """A file Jarvis itself writes (settings, keys, state): anything in config/
    or memory/ except the icon, or anything .gitignore says is not code."""
    rel = rel.replace("\\", "/")
    if rel.startswith(("config/", "memory/")) and not rel.endswith((".ico", ".py")):
        return True
    return _git("check-ignore", "-q", "--no-index", rel).returncode == 0


def _pull_keeping_own_files(err: str) -> tuple[bool, str]:
    """git refused because files would be overwritten. When every one of them is
    Jarvis's own (ignored) data — which happens when an old version tracked a
    settings file by mistake — keep a copy, let git update, put the copy back.
    Anything else is a real hand edit and is left alone."""
    files = _blocking_files(err) or [
        ln[3:].strip() for ln in _git("status", "--porcelain").stdout.splitlines()
        if ln[:2].strip() in ("M", "D", "MM", "AM")]
    if not files or not all(_is_own_file(f) for f in files):
        return False, ", ".join(files[:6])
    saved: dict[str, bytes] = {}
    for f in files:
        try:
            saved[f] = (REPO / f).read_bytes()
        except OSError:
            pass
    backup = REPO.parent / f"jarvis-update-backup-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        backup.mkdir(parents=True, exist_ok=True)
        for f, data in saved.items():
            (backup / f.replace("/", "__")).write_bytes(data)
    except OSError:
        pass
    _git("checkout", "--", *files)
    for f in files:      # untracked files git would have to overwrite
        if (REPO / f).exists() and f in saved and \
                _git("ls-files", "--error-unmatch", f).returncode != 0:
            (REPO / f).unlink()
    pull = _git("pull", "--ff-only", "origin", BRANCH, timeout=300)
    for f, data in saved.items():
        (REPO / f).parent.mkdir(parents=True, exist_ok=True)
        (REPO / f).write_bytes(data)
    if pull.returncode != 0:
        return False, (pull.stderr or pull.stdout).strip()[:160]
    return True, ""


def update(restart: bool = True) -> tuple[bool, str]:
    """Pull, install new requirements, restart. (ok, message)."""
    with _lock:
        if _state["busy"]:
            return False, "An update is already running."
        _state["busy"] = True
    try:
        behind, summary = check()
        if behind == 0:
            return True, "Jarvis is already up to date."
        before = _git("rev-parse", "HEAD").stdout.strip()
        pull = _git("pull", "--ff-only", "origin", BRANCH, timeout=300)
        if pull.returncode != 0:
            err = (pull.stderr or pull.stdout)
            if "local changes" in err or "would be overwritten" in err:
                ok, which = _pull_keeping_own_files(err)
                if not ok:
                    return False, ("Files in the Jarvis folder were changed by hand, so the update "
                                   "stopped without touching them" + (f" ({which})" if which else "")
                                   + ". Ask for help to merge them.")
            else:
                return False, "The update failed: " + err.strip()[:160]
        changed = _git("diff", "--name-only", before, "HEAD").stdout.split()
        if "requirements.txt" in changed:
            pip = subprocess.run([_python_console(), "-m", "pip", "install", "-q", "-r",
                                  str(REPO / "requirements.txt")], capture_output=True, text=True,
                                 timeout=900, cwd=str(REPO), creationflags=_NO_WINDOW)
            if pip.returncode != 0:
                return False, ("The new code is in place but installing its packages failed: "
                               + (pip.stderr or pip.stdout).strip()[-200:])
        msg = f"Updated ({behind} change{'s' if behind != 1 else ''}: {summary[:160]})."
        if restart:
            threading.Thread(target=_restart, daemon=True).start()
            msg += " Restarting in a few seconds."
        return True, msg
    except Exception as e:
        return False, f"Update failed: {e}"
    finally:
        _state["busy"] = False


def _restart() -> None:
    """Start a fresh Jarvis a few seconds from now, then close this one."""
    time.sleep(2.5)  # let the assistant finish its sentence
    exe = sys.executable
    main_py = str(REPO / "main.py")
    boot = ("import time, subprocess, sys; time.sleep(6); "
            f"subprocess.Popen([{exe!r}, {main_py!r}], cwd={str(REPO)!r})")
    flags = 0
    if sys.platform == "win32":
        flags = 0x00000008 | 0x00000200 | _NO_WINDOW   # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen([exe, "-c", boot], cwd=str(REPO), creationflags=flags,
                     start_new_session=(sys.platform != "win32"), close_fds=True)
    p = addons.player()
    if p is not None and hasattr(p, "request_quit"):
        p.request_quit()
    else:
        os._exit(0)


def _daily() -> None:
    time.sleep(120)
    if get_plugin_setting(NAMESPACE, "auto_install", False):
        ok, msg = update(restart=True)
        if ok and "Updated" in msg:
            return
    while True:
        try:
            if get_plugin_setting(NAMESPACE, "check_daily", True):
                behind, summary = check()
                if behind:
                    addons.notify("Update ready", f"{behind} change(s): {summary}\nSay \"update "
                                  "yourself\" or press UPDATE NOW in plugin settings.",
                                  "[SYSTEM] An update for you is ready. In one short sentence, "
                                  "tell the user and that they can say 'update yourself'.",
                                  phone=False)
        except Exception as e:
            print(f"[Updater] check skipped: {e}")
        time.sleep(24 * 3600)


PLUGIN = {
    "name": "updater",
    "description": (
        "Updates the assistant itself to the newest version and restarts it, or checks "
        "whether an update is available. Use for 'update yourself', 'are there updates', "
        "'get the latest version'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "enum": ["check", "update"]}},
        "required": ["action"],
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "extra",
    "brief": "Update the assistant: check / update.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "UPDATES",
    "fields": [
        {"key": "check_daily", "label": "Tell me when an update is ready", "type": "toggle",
         "default": True},
        {"key": "auto_install", "label": "Install updates by itself when Jarvis starts",
         "type": "toggle", "default": False},
    ],
    "action": {"label": "UPDATE NOW", "run": lambda values: update(restart=True)},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        if parameters.get("action") == "update":
            ok, msg = update(restart=True)
            return (outcome.done("update", result=msg) if ok
                    else outcome.failed("update", msg))
        behind, summary = check()
        return outcome.done("update_check", updates_waiting=behind,
                            whats_new=summary[:200] or None)
    except Exception as e:
        return outcome.failed("update", str(e)[:200])


threading.Thread(target=_daily, name="updater", daemon=True).start()
