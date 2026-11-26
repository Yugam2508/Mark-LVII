"""
plugins/system_tools.py — the hands Jarvis needs to run the computer.

    "Turn Bluetooth on" / "what Bluetooth devices do I have"    bluetooth
    "Install VLC" / "uninstall Zoom"                            install / uninstall   (winget, confirm)
    "Run this: ipconfig /all" / "run the script in Downloads"   run_command           (confirm, time limit)
    "Organise my Downloads"                                     organise  (sorts by type, confirm, undo)
    "Undo the tidy-up"                                          undo_organise
    "Open youtube.com"                                          open_url

Anything that changes the machine waits for the user's confirmation, like email does. Commands that
could wipe a disk or the system are refused whatever the confirmation says. Output comes back as data.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from core import confirm, outcome

WINDOWS = sys.platform.startswith("win")
LOG = Path(__file__).resolve().parent.parent / "config" / "organise_log.json"
_NOWIN = 0x08000000 if WINDOWS else 0   # CREATE_NO_WINDOW

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic", ".tiff"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Installers": {".exe", ".msi", ".dmg", ".apk", ".deb"},
    "Code": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".html", ".css", ".json", ".ipynb"},
}

# Refused outright, however the confirmation goes.
_DANGEROUS = [re.compile(p, re.I) for p in (
    r"\bformat-volume\b", r"\bformat\s+[a-z]:", r"\bdiskpart\b", r"\bclear-disk\b", r"\bremove-partition\b",
    r"\bmkfs\b", r"\bdd\s+if=", r"\brm\s+(-\w+\s+)*-?\w*r\w*\s+/(\s|$|\*)", r"rd\s+/s\s+/q\s+[a-z]:\\\s*$",
    r"\bdel\s+/[sfq]+.*\\windows", r"remove-item.*(-recurse).*[a-z]:\\(windows|users)?\s*$",
    r"\bbcdedit\b", r"\bcipher\s+/w", r"reg\s+delete\s+hk(lm|cr)", r":\(\)\s*\{", r"shutdown\s+/[rsp]",
    # any delete aimed at a drive root or at Windows / Users / Program Files / ProgramData themselves
    r"(remove-item|\brm\b|\brmdir\b|\brd\b|\bdel\b|\berase\b|\bri\b)[^|;&]*?\s['\"]?[a-z]:\\"
    r"(windows|users|program files( \(x86\))?|programdata|system32)?\\?\*?['\"]?(\s|$)",
    r"\$env:(systemroot|windir)", r"\bset-executionpolicy\b.*\bunrestricted\b.*-scope\s+localmachine",
)]


def _flag(cmd: str) -> str:
    for rx in _DANGEROUS:
        if rx.search(cmd):
            return "that can wipe a disk or break the system"
    return ""


def _run(args, timeout: int = 60, shell: bool = False) -> tuple[int, str]:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, shell=shell,
                           creationflags=_NOWIN, errors="replace")
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError as e:
        return 127, f"not found: {e.filename}"


def _ps(script: str, timeout: int = 60) -> tuple[int, str]:
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout)


# ── Bluetooth ────────────────────────────────────────────────────────────────

_BT_SET = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$m = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($t, $r) { $n = $m.MakeGenericMethod($r).Invoke($null, @($t)); $n.Wait(-1) | Out-Null; $n.Result }
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$bt = $radios | ? { $_.Kind -eq 'Bluetooth' }
if (-not $bt) { 'NO_RADIO'; exit }
if ('%s' -ne 'status') { Await ($bt.SetStateAsync('%s')) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null }
'STATE=' + ($radios | ? { $_.Kind -eq 'Bluetooth' }).State
"""


def _bluetooth(p: dict) -> str:
    what = str(p.get("state") or "status").lower()
    if what in ("settings", "open"):
        _open_settings("bluetooth")
        return outcome.done("bluetooth_settings", note="opened the Bluetooth settings page, where a device is picked to connect")
    if not WINDOWS:
        return outcome.failed("bluetooth", "Bluetooth control is only built for Windows")
    if what in ("on", "off"):
        rc, out = _ps(_BT_SET % (what, "On" if what == "on" else "Off"), 30)
        if "NO_RADIO" in out:
            return outcome.failed("bluetooth", "this PC has no Bluetooth radio")
        m = re.search(r"STATE=(\w+)", out)
        if not m:
            return outcome.failed("bluetooth", out[:160] or "no answer")
        if m.group(1).lower() != what:
            _open_settings("bluetooth")
            return outcome.failed("bluetooth", f"Windows kept it {m.group(1).lower()} (switched off in "
                                  "airplane mode, or not allowed); I opened the Bluetooth page")
        return outcome.done("bluetooth", state=what)
    if what == "devices":
        rc, out = _ps("Get-PnpDevice -Class Bluetooth | ? { $_.InstanceId -match '^(BTHENUM|BTHLE)\\\\DEV_' -and "
                      "$_.FriendlyName } | Select -Expand FriendlyName | Sort -Unique")
        return outcome.done("bluetooth_devices") + "\n" + outcome.untrusted("bluetooth", out or "no paired devices")
    rc, out = _ps(_BT_SET % ("status", "On"), 30)
    m = re.search(r"STATE=(\w+)", out)
    return outcome.done("bluetooth", state=(m.group(1).lower() if m else "unknown"))


def _open_settings(page: str) -> None:
    if WINDOWS:
        os.startfile(f"ms-settings:{page}")  # type: ignore[attr-defined]


# ── install / uninstall ──────────────────────────────────────────────────────

def _winget_find(query: str) -> tuple[str, str]:
    rc, out = _run(["winget", "search", query, "--accept-source-agreements"], 60)
    if rc == 127:
        return "", "winget isn't installed on this PC (it comes with the App Installer from the Microsoft Store)"
    pkg, label = parse_winget(out)
    return (pkg, label) if pkg else ("", f"winget found nothing called {query}")


def parse_winget(out: str) -> tuple[str, str]:
    """(id, name) of the first result in `winget search` output."""
    lines = [l.rstrip("\r") for l in out.splitlines()]
    for i, line in enumerate(lines):
        if re.search(r"\bName\b", line) and re.search(r"\bId\b", line) and re.search(r"\bVersion\b", line):
            id_at, ver_at = line.index("Id"), line.index("Version")
            for row in lines[i + 1:]:
                if not row.strip() or set(row.strip()) <= {"-"}:
                    continue
                # The id is the dotted word nearest the Id column (a long name can push it right,
                # and names themselves can contain dots, like Paint.NET).
                cands = [m for m in re.finditer(r"\S+", row)
                         if m.start() > 0 and re.match(r"^[\w.+-]+\.[\w.+-]+$", m.group()) and m.start() < ver_at + 40]
                if not cands:
                    continue
                best = min(cands, key=lambda m: abs(m.start() - id_at))
                return best.group(), row[:best.start()].strip() or best.group()
            break
    for line in lines:                                   # no header recognised: split on wide gaps
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 2 and re.match(r"^[\w.+-]+\.[\w.+-]+$", parts[1]):
            return parts[1], parts[0]
    return "", ""


def _install(p: dict, remove: bool = False) -> str:
    query = str(p.get("name") or p.get("query") or "").strip()
    if not query:
        return outcome.ask("install", "What should I install?")
    verb = "uninstall" if remove else "install"
    pkg, label = _winget_find(query)
    if not pkg:
        return outcome.failed(verb, label)

    def go() -> str:
        args = ["winget", verb, "--id", pkg, "-e", "--accept-source-agreements"]
        if not remove:
            args.append("--accept-package-agreements")
        rc, out = _run(args, 900)
        tail = out.splitlines()[-1] if out else ""
        return outcome.done(verb, app=label) if rc == 0 else outcome.failed(verb, tail[:160] or f"exit {rc}")

    return confirm.request(f"{verb}:{pkg}", f"{verb.title()} {label}",
                           f"{verb.title()} {label} ({pkg}) with winget", go)


# ── run a command ────────────────────────────────────────────────────────────

def _command(p: dict) -> str:
    cmd = str(p.get("command") or "").strip()
    if not cmd:
        return outcome.ask("run_command", "What should I run?")
    why = _flag(cmd)
    if why:
        return outcome.failed("run_command", f"refused: {why}")
    timeout = max(5, min(int(p.get("timeout") or 120), 900))

    def go() -> str:
        rc, out = _ps(cmd, timeout) if WINDOWS else _run(cmd, timeout, shell=True)
        return outcome.done("run_command", exit_code=rc) + "\n" + outcome.untrusted("command output", out[-3000:] or "(no output)")

    return confirm.request(f"cmd:{cmd[:60]}", "Run command", f"Run on this PC:\n{cmd}", go)


# ── organise a folder ────────────────────────────────────────────────────────

def _folder(name: str) -> Path:
    home = Path.home()
    low = (name or "downloads").strip().lower()
    known = {"downloads": "Downloads", "desktop": "Desktop", "documents": "Documents",
             "pictures": "Pictures", "videos": "Videos", "music": "Music"}
    if low in known:
        return home / known[low]
    return Path(os.path.expandvars(os.path.expanduser(name)))


def _category(path: Path) -> str:
    ext = path.suffix.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Other"


_PARTIAL = (".crdownload", ".part", ".partial", ".download", ".tmp", ".opdownload", ".!ut")


def plan_organise(folder: Path) -> list[tuple[Path, Path]]:
    moves = []
    now = time.time()
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.name.startswith((".", "~$")) or f.suffix.lower() in (".lnk", ".ini") + _PARTIAL:
            continue
        try:
            if now - f.stat().st_mtime < 120:        # probably still being written
                continue
        except OSError:
            continue
        dest = folder / _category(f) / f.name
        if not dest.exists():
            moves.append((f, dest))
    return moves


def _organise(p: dict) -> str:
    folder = _folder(str(p.get("folder") or "downloads"))
    if not folder.is_dir():
        return outcome.failed("organise", f"no folder {folder}")
    try:
        from plugins import file_finder
        why = file_finder.protected_reason(folder)
        if why:
            return outcome.failed("organise", why)
    except Exception:
        pass
    moves = plan_organise(folder)
    if not moves:
        return outcome.done("organise", moved=0, note="nothing loose to sort")
    counts: dict[str, int] = {}
    for _, d in moves:
        counts[d.parent.name] = counts.get(d.parent.name, 0) + 1
    summary = ", ".join(f"{n} → {c}" for c, n in sorted(counts.items()))

    def go() -> str:
        done = []
        for src, dst in moves:
            try:
                dst.parent.mkdir(exist_ok=True)
                shutil.move(str(src), str(dst))
                done.append([str(src), str(dst)])
            except OSError:
                continue
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(json.dumps({"at": time.time(), "moves": done}), encoding="utf-8")
        return outcome.done("organise", moved=len(done), folder=folder.name, note="say 'undo the tidy-up' to put it all back")

    return confirm.request(f"organise:{folder}", f"Organise {folder.name}",
                           f"Sort {len(moves)} loose files in {folder}:\n{summary}", go)


def _undo(p: dict) -> str:
    try:
        data = json.loads(LOG.read_text(encoding="utf-8"))
    except Exception:
        return outcome.failed("undo_organise", "there's nothing to undo")
    back = 0
    for src, dst in reversed(data.get("moves", [])):
        try:
            if Path(dst).exists() and not Path(src).exists():
                shutil.move(dst, src)
                back += 1
        except OSError:
            pass
    for d in {Path(m[1]).parent for m in data.get("moves", [])}:
        try:
            d.rmdir()
        except OSError:
            pass
    LOG.unlink(missing_ok=True)
    return outcome.done("undo_organise", restored=back)


# ── websites ─────────────────────────────────────────────────────────────────

def _open_url(p: dict) -> str:
    url = str(p.get("url") or "").strip()
    if not url:
        return outcome.ask("open_url", "Which site?")
    if not re.match(r"^https?://", url, re.I):
        if re.match(r"^[\w-]+(\.[\w-]+)+(/.*)?$", url):
            url = "https://" + url
        else:
            url = "https://www.google.com/search?q=" + re.sub(r"\s+", "+", url)
    webbrowser.open(url)
    return outcome.done("open_url", url=url)


# ── power and housekeeping ───────────────────────────────────────────────────

def _power(p: dict) -> str:
    what = str(p.get("what") or "").lower()
    delay = max(0, min(int(p.get("minutes") or 0), 600)) * 60
    if what == "cancel":
        rc, out = _run(["shutdown", "/a"] if WINDOWS else ["shutdown", "-c"], 15)
        return outcome.done("power_cancel") if rc == 0 else outcome.failed("power_cancel", out[:120] or "nothing was scheduled")
    cmds = {
        "shutdown": (["shutdown", "/s", "/t", str(delay)], ["shutdown", "-h", f"+{delay // 60}"]),
        "restart": (["shutdown", "/r", "/t", str(delay)], ["shutdown", "-r", f"+{delay // 60}"]),
        "sleep": (["powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Windows.Forms; "
                   "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"],
                  ["systemctl", "suspend"]),
        "hibernate": (["shutdown", "/h"], ["systemctl", "hibernate"]),
    }
    if what not in cmds:
        return outcome.ask("power", "Shut down, restart, sleep or hibernate?")
    win, other = cmds[what]
    when = f" in {delay // 60} minutes" if delay and what in ("shutdown", "restart") else " now"

    def go() -> str:
        rc, out = _run(win if WINDOWS else other, 30)
        return outcome.done(f"power_{what}", when=when.strip()) if rc == 0 else outcome.failed(f"power_{what}", out[:120])

    return confirm.request(f"power:{what}:{delay}", what.title() + " the PC",
                           f"{what.title()} this PC{when}. Unsaved work in open programs may be lost.", go)


def _dir_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _clean_temp(p: dict) -> str:
    dirs = [Path(d) for d in {os.environ.get("TEMP", ""), os.environ.get("TMP", "")} if d and Path(d).is_dir()]
    if not dirs:
        return outcome.failed("clean_temp", "no temp folder found")
    cutoff = time.time() - 24 * 3600

    def old_items(d: Path) -> list[Path]:
        out = []
        for child in d.iterdir():
            try:
                if child.stat().st_mtime < cutoff:
                    out.append(child)
            except OSError:
                pass
        return out

    items = [c for d in dirs for c in old_items(d)]
    size = sum((_dir_size(c) if c.is_dir() else c.stat().st_size) for c in items if c.exists())

    def go() -> str:
        freed = 0
        for child in items:
            try:
                n = _dir_size(child) if child.is_dir() else child.stat().st_size
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    n -= _dir_size(child) if child.exists() else 0
                else:
                    child.unlink()
                freed += max(0, n)
            except OSError:
                continue                      # in use by a program: leave it
        return outcome.done("clean_temp", freed_mb=round(freed / 1e6, 1))

    if not items:
        return outcome.done("clean_temp", freed_mb=0, note="nothing older than a day in the temp folder")
    return confirm.request("clean_temp", "Clean temp files",
                           f"Delete {len(items)} temporary items older than a day ({size / 1e6:.0f} MB) from "
                           f"{', '.join(str(d) for d in dirs)}. Files in use are skipped.", go)


# ── screenshot ───────────────────────────────────────────────────────────────

def screenshot_folder() -> Path:
    d = Path.home() / "Pictures" / "Screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _screenshot(p: dict) -> str:
    """Save what is on screen as a PNG (all screens, or one), and say where. Optionally open it."""
    import datetime as _dt
    path = screenshot_folder() / f"Jarvis {_dt.datetime.now():%Y-%m-%d %H-%M-%S}.png"
    which = str(p.get("screen") or "main").lower()
    err = ""
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            mons = sct.monitors
            mon = mons[0] if which == "all" or len(mons) < 2 else mons[1]
            if which.isdigit() and int(which) < len(mons):
                mon = mons[int(which)]
            shot = sct.grab(mon)
            mss.tools.to_png(shot.rgb, shot.size, output=str(path))
    except Exception as e:
        err = str(e)
        try:
            from PIL import ImageGrab
            ImageGrab.grab(all_screens=(which == "all")).save(path)
        except Exception as e2:
            return outcome.failed("screenshot", f"{err or e2}"[:160])
    if not path.exists() or path.stat().st_size < 1000:
        return outcome.failed("screenshot", "the capture came back empty (a locked screen or a protected window)")
    if p.get("open") and WINDOWS:
        os.startfile(str(path))  # type: ignore[attr-defined]
    return outcome.done("screenshot", saved=str(path))


_ACTIONS = {
    "screenshot": _screenshot,
    "power": _power,
    "clean_temp": _clean_temp,
    "bluetooth": _bluetooth,
    "install": _install,
    "uninstall": lambda p: _install(p, remove=True),
    "run_command": _command,
    "organise": _organise,
    "undo_organise": _undo,
    "open_url": _open_url,
}

PLUGIN = {
    "name": "system_tools",
    "description": (
        "Does things on this PC: take a screenshot and save it to Pictures/Screenshots (screenshot; "
        "for LOOKING at the screen to answer a question use screen_process instead); turn Bluetooth on/off, list paired Bluetooth devices or open the "
        "Bluetooth page to connect one (state: on/off/status/devices/settings); install or uninstall "
        "an app with winget (name); run a PowerShell command or script the user dictated (command; "
        "asks to confirm); organise a messy folder like Downloads into folders by file type "
        "(folder; asks to confirm) and undo it; shut down, restart, sleep or hibernate the PC, now or after N minutes, or cancel a scheduled shutdown (power; asks to confirm); delete temp files to free space (clean_temp; asks to confirm); open a website or search (url). Use for 'install X', "
        "'run this', 'tidy my downloads', 'turn on Bluetooth', 'open youtube.com'. For finding or "
        "deleting files use file_finder; for Spotify use spotify_control."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": list(_ACTIONS)},
            "state": {"type": "STRING", "description": "For bluetooth: on, off, status, devices or settings"},
            "name": {"type": "STRING", "description": "For install/uninstall: the app, e.g. 'VLC'"},
            "command": {"type": "STRING", "description": "For run_command: the PowerShell to run"},
            "timeout": {"type": "INTEGER", "description": "For run_command: seconds before it is stopped (default 120)"},
            "screen": {"type": "STRING", "description": "For screenshot: main (default), all, or a screen number"},
            "open": {"type": "BOOLEAN", "description": "For screenshot: open it after saving"},
            "what": {"type": "STRING", "description": "For power: shutdown, restart, sleep, hibernate or cancel"},
            "minutes": {"type": "INTEGER", "description": "For power shutdown/restart: delay in minutes"},
            "folder": {"type": "STRING", "description": "For organise: downloads, desktop, documents or a path"},
            "url": {"type": "STRING", "description": "For open_url: a site, address or search words"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "PC: Bluetooth, install apps, run commands, organise folders, open sites.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "").lower()
    fn = _ACTIONS.get(action)
    if fn is None:
        return outcome.failed("system_tools", f"unknown action {action}")
    try:
        return fn(parameters)
    except Exception as e:
        return outcome.failed(action, str(e)[:160])
