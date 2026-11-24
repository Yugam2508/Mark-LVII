"""
plugins/device_sync.py — one memory for every computer JARVIS runs on.

THE PROBLEM
    JARVIS keeps what it knows about you in memory/long_term.json, inside the
    install folder. Run it on a desktop and a laptop and you get two assistants
    that each know half of you.

WHAT THIS DOES
    Every minute (and at start-up) it merges this computer's memory with a copy in
    a folder your cloud drive already syncs — OneDrive by default on Windows:

        %OneDrive%\\JARVIS Sync\\long_term.json

    Point both computers at the same folder in ⚙ → PLUGIN SETTINGS → DEVICE SYNC
    and switch it on. Nothing else to set up; OneDrive (or Google Drive / Dropbox
    desktop) moves the file between machines.

HOW THE MERGE STAYS CORRECT
    A plain "newest file wins" copy loses whatever the other computer learnt in
    the meantime, and a plain union brings back anything you told one of them to
    forget. So this is a three-way merge per memory entry, against a snapshot of
    what this computer last agreed with the shared copy:

        unchanged here, changed there     -> take theirs (including a deletion)
        changed here, unchanged there     -> keep ours   (including a deletion)
        changed on both                   -> keep ours; the other side picks it
                                             up on its next run

    Both computers can be on at the same time. The shared file is written to a
    temporary name and renamed, so a cloud client never uploads half a file.

WHAT IS NOT SYNCED, ON PURPOSE
    * config/api_keys.json — it holds per-machine choices (which microphone and
      speakers, window scale) next to your keys. Set each computer up once.
    * Routines — a briefing or reminder that lives on both machines would be said
      twice. Keep routines on the computer you use most.
    * The to-do list needs nothing: todo_list keeps it in Google Tasks, which every
      device (including your phone) already sees.
"""
from __future__ import annotations

import copy
import json
import os
import platform
import threading
import time
from pathlib import Path

from core import outcome
from memory import memory_manager
from memory.config_manager import CONFIG_DIR, get_plugin_setting

NAMESPACE = "device_sync"
SNAPSHOT_FILE = CONFIG_DIR / "device_sync_base.json"   # what we last agreed on
SHARED_NAME = "long_term.json"
INTERVAL_SECONDS = 60

_lock = threading.Lock()
_status = {"last_run": None, "last_result": "not run yet", "changes_in": 0, "changes_out": 0}


def _default_folder() -> str:
    root = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if root:
        return str(Path(root) / "JARVIS Sync")
    return str(Path.home() / "JARVIS Sync")


def _folder() -> Path | None:
    if not get_plugin_setting(NAMESPACE, "enabled", False):
        return None
    raw = str(get_plugin_setting(NAMESPACE, "folder", "") or "").strip()
    return Path(raw or _default_folder()).expanduser()


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return None   # mid-download by the cloud client, or corrupt: skip this round


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{platform.node() or 'pc'}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _flatten(mem: dict) -> dict[tuple[str, str], object]:
    out = {}
    for cat, items in (mem or {}).items():
        if isinstance(items, dict):
            for key, entry in items.items():
                out[(cat, key)] = entry
        else:
            out[(cat, "")] = items   # a non-dict top-level value, kept whole
    return out


def _unflatten(flat: dict[tuple[str, str], object], categories: set[str]) -> dict:
    mem: dict = {c: {} for c in categories}
    for (cat, key), entry in flat.items():
        if key == "" and not isinstance(entry, dict):
            mem[cat] = entry
        else:
            mem.setdefault(cat, {})[key] = entry
    return mem


_GONE = object()


def merge(base: dict, ours: dict, theirs: dict) -> tuple[dict, int, int]:
    """Three-way merge of two memory stores. Returns (merged, taken_in, sent_out)."""
    b, o, t = _flatten(base), _flatten(ours), _flatten(theirs)
    merged, taken_in, sent_out = {}, 0, 0
    for k in set(b) | set(o) | set(t):
        bv, ov, tv = b.get(k, _GONE), o.get(k, _GONE), t.get(k, _GONE)
        if ov == tv:
            result = ov
        elif ov == bv:          # only they changed it
            result, taken_in = tv, taken_in + 1
        elif tv == bv:          # only we changed it
            result, sent_out = ov, sent_out + 1
        else:                   # both changed it: ours, the other side follows
            result, sent_out = ov, sent_out + 1
        if result is not _GONE:
            merged[k] = result
    cats = {c for (c, _) in merged} | set(ours) | set(theirs)
    return _unflatten(merged, cats), taken_in, sent_out


def sync_once() -> str:
    folder = _folder()
    if folder is None:
        return "Device sync is switched off."
    shared = folder / SHARED_NAME
    with _lock:
        ours = memory_manager.load_memory()
        theirs = _read_json(shared)
        if theirs is None:
            if shared.exists():
                return "The shared memory file is being synced right now; trying again later."
            theirs = {}
        base = _read_json(SNAPSHOT_FILE) or {}
        merged, taken_in, sent_out = merge(base, ours, theirs)

        if merged != ours:
            memory_manager.save_memory(copy.deepcopy(merged))
        if merged != theirs:
            _write_atomic(shared, merged)
        _write_atomic(SNAPSHOT_FILE, merged)

    _status.update(last_run=time.strftime("%H:%M:%S"), changes_in=taken_in,
                   changes_out=sent_out,
                   last_result=f"in sync ({taken_in} from other devices, {sent_out} sent)")
    return _status["last_result"]


def _loop() -> None:
    time.sleep(5)  # let the app finish starting
    while True:
        try:
            if _folder() is not None:
                sync_once()
        except Exception as e:  # never take the app down over a sync
            _status["last_result"] = f"error: {e}"
        time.sleep(INTERVAL_SECONDS)


_thread: threading.Thread | None = None


def _start() -> None:
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_loop, name="device_sync", daemon=True)
        _thread.start()


def _test(values: dict) -> tuple[bool, str]:
    """The TEST & SYNC NOW button."""
    folder = Path(str(values.get("folder") or "").strip() or _default_folder()).expanduser()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".jarvis_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        return False, f"Cannot write to {folder}: {e}"
    if not values.get("enabled"):
        return True, f"{folder} is writable. Switch ON and save to start syncing."
    return True, sync_once()


PLUGIN = {
    "name": "device_sync",
    "description": (
        "Reports or runs the memory sync between the user's computers. Use when they "
        "ask whether their computers are in sync, or to sync now."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["status", "sync_now"]},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Memory sync between computers: status / sync_now.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "DEVICE SYNC (MEMORY ACROSS COMPUTERS)",
    "fields": [
        {"key": "enabled", "label": "Sync memory with my other computers", "type": "toggle",
         "default": False},
        {"key": "folder", "label": "Shared folder (same on every computer)", "type": "text",
         "placeholder": _default_folder()},
    ],
    "action": {"label": "TEST & SYNC NOW", "run": _test},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status").lower()
    try:
        if _folder() is None:
            return outcome.failed("device_sync", "sync is switched off; turn it on in "
                                  "plugin settings on each computer")
        result = sync_once() if action == "sync_now" else _status["last_result"]
        return outcome.done(f"device_sync_{action}", result=result,
                            last_run=_status["last_run"], folder=str(_folder()))
    except Exception as e:
        return outcome.failed(f"device_sync_{action}", f"sync error: {e}")


_start()
