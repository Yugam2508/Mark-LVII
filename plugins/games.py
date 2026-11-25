"""
plugins/games.py — find and launch your PC games by name.

    "Launch Valorant" / "start CS"           action=launch name=...
    "What games do I have?"                   action=list
    "What did I play recently?"               action=recent

Finds installed games from Steam (every library folder), the Epic Games
Launcher, Riot (VALORANT, League of Legends) and Battle.net, and starts them the
way their own launcher would. Short names work: "cs", "val", "league", "gta",
"apex", "rl". Starting a game also switches on gaming mode by itself when
automatic gaming mode is on (plugins/modes.py).

Discord: messages to friends already work through the built-in send_message
tool ("message Sam on Discord: running late"), which drives the Discord app.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from core import outcome
from memory.config_manager import CONFIG_DIR

LAUNCH_LOG = CONFIG_DIR / "games_played.json"
ALIASES = {"cs": "counter-strike 2", "cs2": "counter-strike 2", "csgo": "counter-strike 2",
           "val": "valorant", "valo": "valorant", "lol": "league of legends",
           "league": "league of legends", "gta": "grand theft auto v", "gta 5": "grand theft auto v",
           "apex": "apex legends", "rl": "rocket league", "ow": "overwatch", "ow2": "overwatch",
           "mc": "minecraft", "fn": "fortnite", "r6": "rainbow six siege", "cod": "call of duty"}
STEAM_SKIP = {"228980", "1070560", "1391110", "1628350", "250820", "1493710"}  # redists, runtimes, SteamVR, Proton
BATTLENET = {"overwatch": "Pro", "world of warcraft": "WoW", "diablo iv": "Fen",
             "call of duty": "Fore", "hearthstone": "WTCG", "starcraft ii": "S2"}

_cache: dict = {"games": [], "at": 0.0}
_lock = threading.Lock()


# ── discovery ─────────────────────────────────────────────────────────────────

def _steam_root() -> Path | None:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                return Path(winreg.QueryValueEx(k, "SteamPath")[0])
        except OSError:
            pass
        p = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam"
        return p if p.exists() else None
    p = Path.home() / ".steam" / "steam"
    return p if p.exists() else None


def _acf_value(text: str, key: str) -> str:
    m = re.search(rf'"{key}"\s+"([^"]*)"', text)
    return m.group(1) if m else ""


def _steam_games() -> list[dict]:
    root = _steam_root()
    if root is None:
        return []
    libs = {root}
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for path in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
            libs.add(Path(path.replace("\\\\", "\\")))
    games = []
    for lib in libs:
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            try:
                text = acf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            appid, name = _acf_value(text, "appid"), _acf_value(text, "name")
            if not appid or not name or appid in STEAM_SKIP or "redistributable" in name.lower():
                continue
            games.append({"name": name, "store": "Steam", "launch": f"steam://rungameid/{appid}",
                          "last_played": int(_acf_value(text, "LastPlayed") or 0)})
    return games


def _epic_games() -> list[dict]:
    base = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    games = []
    for item in base.glob("*.item") if base.exists() else []:
        try:
            d = json.loads(item.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if not d.get("bIsApplication", True) or not d.get("DisplayName"):
            continue
        ns, cid, app = d.get("CatalogNamespace", ""), d.get("CatalogItemId", ""), d.get("AppName", "")
        games.append({"name": d["DisplayName"], "store": "Epic", "last_played": 0,
                      "launch": f"com.epicgames.launcher://apps/{ns}%3A{cid}%3A{app}?action=launch&silent=true"})
    return games


def _riot_games() -> list[dict]:
    base = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Riot Games"
    installs = base / "RiotClientInstalls.json"
    if not installs.exists():
        return []
    try:
        client = json.loads(installs.read_text(encoding="utf-8")).get("rc_default", "")
    except (OSError, ValueError):
        return []
    games = []
    for product, name in (("valorant", "VALORANT"), ("league_of_legends", "League of Legends")):
        if (base / "Metadata" / f"{product}.live").exists():
            games.append({"name": name, "store": "Riot", "last_played": 0,
                          "launch": [client, f"--launch-product={product}", "--launch-patchline=live"]})
    return games


def _battlenet_games() -> list[dict]:
    exe = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Battle.net" / "Battle.net.exe"
    if not exe.exists():
        return []
    return [{"name": n.title() if n != "diablo iv" else "Diablo IV", "store": "Battle.net",
             "launch": f"battlenet://{code}", "last_played": 0} for n, code in BATTLENET.items()]


def installed(refresh: bool = False) -> list[dict]:
    with _lock:
        if refresh or not _cache["games"] or time.time() - _cache["at"] > 600:
            found = []
            for fn in (_steam_games, _epic_games, _riot_games, _battlenet_games):
                try:
                    found += fn()
                except Exception as e:
                    print(f"[Games] {fn.__name__}: {e}")
            seen, unique = set(), []
            for g in found:
                if g["name"].lower() not in seen:
                    seen.add(g["name"].lower())
                    unique.append(g)
            _cache.update(games=sorted(unique, key=lambda g: g["name"].lower()), at=time.time())
        return list(_cache["games"])


def find(name: str) -> tuple[dict | None, list[str]]:
    """Best match for a spoken name, or (None, close names)."""
    want = (name or "").strip().lower()
    want = ALIASES.get(want, want)
    games = installed()
    names = {g["name"].lower(): g for g in games}
    if want in names:
        return names[want], []
    hits = [g for n, g in names.items() if want and (want in n or n in want)]
    if len(hits) == 1:
        return hits[0], []
    close = difflib.get_close_matches(want, list(names), n=3, cutoff=0.6)
    if len(close) == 1:
        return names[close[0]], []
    return None, [names[c]["name"] for c in (close or [h["name"].lower() for h in hits][:3])]


def _log_launch(game: str) -> None:
    try:
        log = json.loads(LAUNCH_LOG.read_text(encoding="utf-8")) if LAUNCH_LOG.exists() else {}
    except (OSError, ValueError):
        log = {}
    log[game] = int(time.time())
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_LOG.write_text(json.dumps(log), encoding="utf-8")


def launch(name: str) -> tuple[bool, str]:
    """Start a game. (ok, message) — used by device_link too."""
    game, close = find(name)
    if game is None:
        if close:
            return False, f"Which one: {', '.join(close)}?"
        return False, f"No installed game matches '{name}'."
    target = game["launch"]
    try:
        if isinstance(target, list):
            subprocess.Popen(target, close_fds=True,
                             creationflags=0x00000008 if sys.platform == "win32" else 0)
        elif sys.platform == "win32":
            os.startfile(target)  # noqa: S606 — a launcher URI, not a shell command
        else:
            webbrowser.open(target)
    except Exception as e:
        return False, f"Could not start {game['name']}: {e}"
    _log_launch(game["name"])
    return True, f"Starting {game['name']} ({game['store']})"


def _recent() -> list[tuple[str, int]]:
    try:
        ours = json.loads(LAUNCH_LOG.read_text(encoding="utf-8")) if LAUNCH_LOG.exists() else {}
    except (OSError, ValueError):
        ours = {}
    for g in installed():
        if g.get("last_played"):
            ours[g["name"]] = max(ours.get(g["name"], 0), g["last_played"])
    return sorted(ours.items(), key=lambda kv: kv[1], reverse=True)[:8]


PLUGIN = {
    "name": "games",
    "description": (
        "The user's PC games (Steam, Epic, Riot, Battle.net): launch a game by name, list "
        "installed games, or say what was played recently. Use for 'launch/play/start <game>'. "
        "For music use spotify_control; for Discord messages use send_message."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["launch", "list", "recent"]},
            "name": {"type": "STRING", "description": "For launch: the game, short names are fine"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "PC games: launch / list / recent.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    try:
        if action == "launch":
            ok, msg = launch(str(parameters.get("name") or ""))
            if not ok and msg.startswith("Which one"):
                return outcome.ask("game_launch", msg)
            return (outcome.unverified("game_launch", "it was handed to the game's launcher, "
                                       "which can take a minute", game=msg)
                    if ok else outcome.failed("game_launch", msg))
        if action == "recent":
            rows = _recent()
            if not rows:
                return outcome.done("games_recent", count=0)
            text = "\n".join(f"{n} — {time.strftime('%a %d %b', time.localtime(t))}" for n, t in rows)
            if player:
                player.show_content("RECENTLY PLAYED", text)
            return outcome.done("games_recent", count=len(rows)) + "\n" + outcome.untrusted("games", text)
        games = installed(refresh=True)
        text = "\n".join(f"{g['name']} ({g['store']})" for g in games) or "No games found."
        if player:
            player.show_content(f"GAMES — {len(games)}", text)
        return outcome.done("games_list", count=len(games)) + "\n" + outcome.untrusted("games", text[:2500])
    except Exception as e:
        return outcome.failed(f"games_{action}", str(e)[:150])
