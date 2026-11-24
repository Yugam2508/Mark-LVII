"""
plugins/modes.py — work, study, music, watching and gaming modes.

    "Gaming mode" / "I'm studying" / "Back to normal"     action=set mode=...
    "What mode are you in?"                                action=status

A mode decides how much JARVIS speaks up on its own and how it talks:

    normal    everything on (the default)
    work      email and calendar alerts on, short to-the-point replies
    study     alerts held back and summarised afterwards; routines quiet
    music     only urgent alerts; very short replies; Spotify first
    watching  silent unless spoken to; only urgent alerts
    gaming    silent, nothing popping up on screen; only urgent alerts

Held alerts are not lost: when the mode ends, JARVIS sums up what came in.

PER DEVICE
    Each computer keeps its own mode and its own default (⚙ → PLUGIN SETTINGS →
    MODES), because the setting lives in that computer's config — e.g. the laptop
    starts in work, the desktop in normal.

AUTOMATIC GAMING MODE
    With "switch to gaming when a game starts" on, a game launched from Steam,
    Epic, Riot, Battle.net, EA or Ubisoft (or any program in your own list) turns
    gaming mode on, and closing it puts back the mode you were in.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from core import addons, outcome
from memory.config_manager import get_plugin_config, save_plugin_config

NAMESPACE = "modes"
MODES = ("normal", "work", "study", "music", "watching", "gaming")

# What each mode allows. Read by plugins/proactive.py and core/routines.
POLICY = {
    "normal":   {"email_alerts": "important", "reminders": True, "popups": True,
                 "quiet_routines": False, "hold": False},
    "work":     {"email_alerts": "important", "reminders": True, "popups": True,
                 "quiet_routines": False, "hold": False},
    "study":    {"email_alerts": "urgent", "reminders": True, "popups": True,
                 "quiet_routines": True, "hold": True},
    "music":    {"email_alerts": "urgent", "reminders": True, "popups": True,
                 "quiet_routines": False, "hold": True},
    "watching": {"email_alerts": "urgent", "reminders": "urgent", "popups": True,
                 "quiet_routines": True, "hold": True},
    "gaming":   {"email_alerts": "urgent", "reminders": "urgent", "popups": False,
                 "quiet_routines": True, "hold": True},
}

# What the assistant is told when a mode starts, so its replies change too.
STYLE = {
    "normal": "Normal mode: behave as usual.",
    "work": "Work mode: keep replies short and practical; prioritise email, calendar "
            "and to-dos.",
    "study": "Study mode: keep replies short, do not bring up unrelated things, and "
             "help with studying (the knowledge folder and study coach) when asked.",
    "music": "Music mode: one-sentence replies; for music requests use spotify_control.",
    "watching": "Watching mode: the user is watching something. Answer in one short "
                "sentence and do not start conversations.",
    "gaming": "Gaming mode: the user is playing. Answer in one short sentence, do not "
              "start conversations and do not put things on screen unless asked.",
}

GAME_FOLDERS = ("steamapps\\common", "steamapps/common", "epic games", "riot games",
                "battle.net", "ea games", "ubisoft game launcher\\games", "xboxgames")
KNOWN_GAMES = {"valorant-win64-shipping.exe", "cs2.exe", "r5apex.exe", "fortniteclient-win64-shipping.exe",
               "league of legends.exe", "rocketleague.exe", "gta5.exe", "gta5_enhanced.exe",
               "eldenring.exe", "overwatch.exe", "cod.exe", "minecraft.exe", "fc25.exe", "fc26.exe", "marvel-win64-shipping.exe", "deadlock.exe", "dota2.exe"}

_lock = threading.Lock()
_state = {"mode": None, "auto_from": None, "since": time.time()}
_held: list[str] = []          # alerts held back while a quiet mode is on


# ── state ─────────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    return get_plugin_config(NAMESPACE)


def current() -> str:
    with _lock:
        if _state["mode"] is None:
            default = str(_cfg().get("default_mode") or "normal")
            _state["mode"] = default if default in MODES else "normal"
        return _state["mode"]


def policy() -> dict:
    return dict(POLICY.get(current(), POLICY["normal"]), mode=current())


def hold(alert: str) -> None:
    """Keep an alert for the summary when the quiet mode ends."""
    with _lock:
        _held.append(alert)
        del _held[:-30]


def _set(mode: str, *, auto: bool = False) -> list[str]:
    """Switch mode; returns the alerts that were held, if this ends a holding mode."""
    with _lock:
        old = _state["mode"] or "normal"
        if auto and mode == "gaming":
            _state["auto_from"] = old
        elif not auto:
            _state["auto_from"] = None
        _state["mode"], _state["since"] = mode, time.time()
        released = []
        if POLICY.get(old, {}).get("hold") and not POLICY[mode]["hold"]:
            released, _held[:] = list(_held), []
    addons.log(f"SYS: {mode.upper()} MODE")
    return released


def _announce_release(released: list[str]) -> None:
    if released:
        addons.show("WHILE YOU WERE BUSY", "\n".join(f"• {a}" for a in released))
        # Alerts quote email subjects and senders — text strangers wrote.
        addons.say("[SYSTEM] The user's quiet mode has ended. In one or two short "
                   "sentences, sum up what came in meanwhile:\n"
                   + outcome.untrusted("alerts", "\n".join(released)))


# ── automatic gaming mode ─────────────────────────────────────────────────────

def _game_running() -> str | None:
    try:
        import psutil
    except ImportError:
        return None
    extra = {s.strip().lower() for s in str(_cfg().get("game_processes") or "").split(",")
             if s.strip()}
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            name = (proc.info.get("name") or "").lower()
            exe = (proc.info.get("exe") or "").lower()
        except Exception:
            continue
        if name in KNOWN_GAMES or name in extra:
            return name
        if exe and name.endswith(".exe") and any(f in exe for f in GAME_FOLDERS):
            # launchers and helpers live in those folders too; skip the obvious ones
            if not any(w in name for w in ("launcher", "crash", "helper", "update",
                                           "setup", "redist", "unins", "webhelper")):
                return name
    return None


def _watch_games() -> None:
    time.sleep(15)
    while True:
        try:
            if _cfg().get("auto_gaming", True):
                game = _game_running()
                mode = current()
                if game and mode != "gaming":
                    _set("gaming", auto=True)
                    addons.say(f"[SYSTEM] A game started ({Path(game).stem}). Gaming mode "
                               "is on. Say so in three words or fewer.")
                elif not game and mode == "gaming" and _state.get("auto_from"):
                    back = _state["auto_from"]
                    _announce_release(_set(back))
        except Exception as e:
            print(f"[Modes] game watch: {e}")
        time.sleep(20)


# ── plugin ────────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "modes",
    "description": (
        "Switches the assistant's mode: normal, work, study, music, watching (a film or "
        "video) or gaming. Use when the user says things like 'gaming mode', 'I'm "
        "studying', 'I'm watching a movie', 'work mode', 'back to normal', or asks "
        "which mode is on. Modes control how much you speak up on your own."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["set", "status"]},
            "mode": {"type": "STRING", "enum": list(MODES)},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Modes: normal/work/study/music/watching/gaming.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "MODES",
    "fields": [
        {"key": "default_mode", "label": "Mode this computer starts in", "type": "choice",
         "options": list(MODES), "default": "normal"},
        {"key": "auto_gaming", "label": "Switch to gaming mode when a game starts",
         "type": "toggle", "default": True},
        {"key": "game_processes", "label": "Extra game programs (comma-separated .exe names)",
         "type": "text", "placeholder": "mygame.exe, emulator.exe"},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        if parameters.get("action") == "set":
            mode = str(parameters.get("mode") or "").lower()
            if mode not in MODES:
                return outcome.ask("mode_set", "Which mode: normal, work, study, music, "
                                               "watching or gaming?")
            released = _set(mode)
            note = STYLE[mode]
            if released:
                note += (" Then briefly sum up what came in meanwhile:\n"
                         + outcome.untrusted("alerts", "\n".join(released)))
                addons.show("WHILE YOU WERE BUSY", "\n".join(f"• {a}" for a in released))
            return outcome.done("mode_set", mode=mode) + "\n" + note
        mode = current()
        return outcome.done("mode_status", mode=mode, held_alerts=len(_held)) + "\n" + STYLE[mode]
    except Exception as e:
        return outcome.failed("mode", str(e)[:150])


addons.set_mode_policy(policy)
threading.Thread(target=_watch_games, name="modes_games", daemon=True).start()
