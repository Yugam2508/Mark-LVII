"""
plugins/backup.py — Jarvis's memory and settings, copied somewhere safe every day.

    "Back up Jarvis"                       backup (now)
    "When was the last backup?"            status
    "Restore Jarvis from the backup"       restore (asks first; the current state is backed up before)

What goes in: everything Jarvis has learned (memory/*.json: facts, personality, routines, the life profile),
the word-for-word conversation log (memory/conversations), and the settings in config/ — with passwords,
keys and tokens blanked out unless "Include keys and passwords" is switched on, because the backup folder
is usually OneDrive. Backups go to OneDrive/JARVIS Backups (or ~/JARVIS Backups), one zip per day, the
last 14 kept. A backup is made automatically once a day when Jarvis is running.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import threading
import time
import zipfile
from pathlib import Path

from core import confirm, outcome

ROOT = Path(__file__).resolve().parent.parent
KEEP = 14
_SECRET = re.compile(r"(token|secret|password|passwd|api_?key|key$|_key|credential|refresh|cookie|session|"
                     r"client_id|private|auth)", re.I)
_lock = threading.Lock()


def _setting(key: str, default):
    try:
        from memory.config_manager import get_plugin_setting
        return get_plugin_setting("backup", key, default)
    except Exception:
        return default


def folder() -> Path:
    raw = str(_setting("folder", "") or "").strip()
    if raw:
        d = Path(os.path.expandvars(raw)).expanduser()
    else:
        od = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        d = Path(od) / "JARVIS Backups" if od else Path.home() / "JARVIS Backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def redact(obj, keep_secrets: bool = False):
    """A copy of a settings structure with secret-looking values blanked."""
    if keep_secrets:
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            # A secret-looking name blanks the whole value, lists and nested tokens included
            # (several OpenAI keys are stored as a list).
            if _SECRET.search(str(k)) and not isinstance(v, bool) and v not in (None, "", [], {}):
                out[k] = "<removed from backup>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def _files() -> list[tuple[Path, str]]:
    """(path on disk, path in the zip) for everything that is backed up."""
    out = []
    mem = ROOT / "memory"
    for p in sorted(mem.glob("*.json")) + sorted(mem.glob("*.db")):
        out.append((p, f"memory/{p.name}"))
    for sub in ("conversations", "tasks"):
        d = mem / sub
        if d.is_dir():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    out.append((p, f"memory/{p.relative_to(mem).as_posix()}"))
    cfg = ROOT / "config"
    if cfg.is_dir():
        for p in sorted(cfg.glob("*.json")):
            out.append((p, f"config/{p.name}"))
    return out


def make_backup(reason: str = "manual") -> Path:
    keep_secrets = bool(_setting("include_secrets", False))
    with _lock:
        dest = folder() / f"jarvis-backup-{dt.datetime.now():%Y-%m-%d-%H%M%S}.zip"
        tmp = dest.with_suffix(".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for path, arc in _files():
                try:
                    if arc.startswith("config/") and path.suffix == ".json":
                        data = json.loads(path.read_text(encoding="utf-8"))
                        z.writestr(arc, json.dumps(redact(data, keep_secrets), indent=2, ensure_ascii=False))
                    else:
                        z.write(path, arc)
                except Exception:
                    continue                                    # unreadable right now: skip that one file
            z.writestr("BACKUP-INFO.txt", f"Jarvis backup, {dt.datetime.now():%Y-%m-%d %H:%M} ({reason}).\n"
                       f"Keys and passwords included: {'yes' if keep_secrets else 'no (blanked)'}.\n")
        os.replace(tmp, dest)
        for old in sorted(folder().glob("jarvis-backup-*.zip"))[:-KEEP]:
            try:
                old.unlink()
            except OSError:
                pass
        return dest


def backups() -> list[Path]:
    try:
        return sorted(folder().glob("jarvis-backup-*.zip"))
    except Exception:
        return []


def restore(zip_path) -> int:
    """Put memory/ back from a backup (settings are restored only where the backup has real values).
    `zip_path` may also be the backup's bytes, read before anything else was written."""
    n = 0
    src = io.BytesIO(zip_path) if isinstance(zip_path, (bytes, bytearray)) else zip_path
    with zipfile.ZipFile(src) as z:
        for name in z.namelist():
            if not name.startswith(("memory/", "config/")) or name.endswith("/") or ".." in name:
                continue
            target = ROOT / name
            data = z.read(name)
            if name.startswith("config/"):
                try:
                    incoming = json.loads(data.decode("utf-8"))
                    current = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
                    data = json.dumps(_merge_keep_secrets(incoming, current), indent=2, ensure_ascii=False).encode("utf-8")
                except Exception:
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            n += 1
    return n


def _merge_keep_secrets(incoming, current):
    """Restored settings, but a blanked secret never overwrites the real one on this PC."""
    if isinstance(incoming, dict):
        cur = current if isinstance(current, dict) else {}
        out = dict(cur)
        for k, v in incoming.items():
            if v == "<removed from backup>":
                continue
            out[k] = _merge_keep_secrets(v, cur.get(k))
        return out
    return incoming


PLUGIN = {
    "name": "backup",
    "description": (
        "Backs up Jarvis's memory, conversation log and settings to the backup folder (OneDrive by default), "
        "or restores them. Use for 'back up Jarvis', 'when was my last backup', 'restore my Jarvis backup' "
        "(after a reinstall or on a new PC). A backup is also made automatically once a day."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "enum": ["backup", "status", "restore"]}},
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Back up / restore Jarvis's memory and settings.",
}

PLUGIN_SETTINGS = {
    "namespace": "backup",
    "title": "BACKUPS",
    "fields": [
        {"key": "auto", "label": "Back up automatically once a day", "type": "toggle", "default": True},
        {"key": "folder", "label": "Backup folder (empty = OneDrive/JARVIS Backups)", "type": "text",
         "placeholder": "%OneDrive%\\JARVIS Backups"},
        {"key": "include_secrets", "label": "Include keys and passwords (only if the folder is private)",
         "type": "toggle", "default": False},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    try:
        if action == "backup":
            p = make_backup("asked for")
            return outcome.done("backup", saved=str(p), size_kb=round(p.stat().st_size / 1024))
        bs = backups()
        if action == "status":
            if not bs:
                return outcome.done("backup_status", backups=0, folder=str(folder()))
            last = bs[-1]
            age_h = round((time.time() - last.stat().st_mtime) / 3600, 1)
            return outcome.done("backup_status", backups=len(bs), latest=last.name, hours_ago=age_h, folder=str(folder()))
        if action == "restore":
            if not bs:
                return outcome.failed("backup_restore", f"no backups in {folder()}")
            latest = bs[-1]

            def go() -> str:
                data = latest.read_bytes()                      # read first: the next backup must not replace it
                make_backup("before restoring")                 # so a restore can itself be undone
                n = restore(data)
                return outcome.done("backup_restore", files=n, from_backup=latest.name,
                                    note="restart Jarvis so everything is reloaded")

            return confirm.request("backup:restore", "Restore Jarvis",
                                   f"Replace Jarvis's memory and settings with the backup {latest.name}. "
                                   "The current state is backed up first.", go)
        return outcome.failed("backup", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"backup_{action}", str(e)[:160])


def _boot() -> None:
    time.sleep(120)                                     # let Jarvis finish starting
    while True:
        try:
            if bool(_setting("auto", True)):
                bs = backups()
                if not bs or time.time() - bs[-1].stat().st_mtime > 24 * 3600:
                    make_backup("daily")
        except Exception as e:
            print(f"[Backup] {e}")
        time.sleep(6 * 3600)


if os.environ.get("JARVIS_NO_BACKGROUND") != "1":
    threading.Thread(target=_boot, daemon=True, name="daily_backup").start()
