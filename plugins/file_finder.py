"""
plugins/file_finder.py — "where is …?", "what's taking up space?", "delete that".

    "Where is my thermodynamics report?"            find
    "Show me that one in Explorer" / "open its folder"  reveal   (by the number in the last list)
    "What's taking up space on D:?"                 biggest
    "Delete the second one"                         delete   (asks you to confirm; goes to the Recycle Bin)
    "Refresh your file list"                        refresh

WHY THIS EXISTS: the older file tool only touched your user folders and gave up after 500
folders, so "where is X" often found nothing and "delete this" said access denied. This one
looks at every drive, using a small index (config/file_index.db, built in the background at
start-up and refreshed every few hours), so a search is instant and complete.

DELETING: always the Recycle Bin (undoable by voice: "undo"), always behind CONFIRM, never
permanent. Windows itself, Program Files, drive roots and your profile folder are refused
outright; uninstalling a program belongs in Settings → Apps. Searching and revealing never
change anything.
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

from core import addons, outcome

NAMESPACE = "file_finder"
REFRESH_SECONDS = 6 * 3600
MAX_ROWS = 4_000_000
_SKIP_NAMES = {"$recycle.bin", "system volume information", "windows", "winsxs", "node_modules", ".git",
               "__pycache__", "cache", "code cache", "gpucache", "temp", ".cache", "recovery", "$windows.~bt",
               "$sysreset", "config.msi", "msocache"}
_state = {"building": False, "rows": 0, "built_at": 0.0, "error": ""}
_lock = threading.Lock()
_last: list[dict] = []                      # the numbered results of the last search


# ── the index ─────────────────────────────────────────────────────────────────

def db_path() -> Path:
    from memory.config_manager import CONFIG_DIR
    return CONFIG_DIR / "file_index.db"


def _connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p), timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, name TEXT, nl TEXT, size INTEGER, "
              "mtime REAL, isdir INTEGER)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_nl ON files(nl)")
    c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    return c


def roots() -> list[Path]:
    """Every drive on Windows (fixed disks), else the home folder; or what the setting lists."""
    try:
        from memory.config_manager import get_plugin_setting
        raw = str(get_plugin_setting(NAMESPACE, "index_roots", "") or "")
    except Exception:
        raw = ""
    if raw.strip():
        return [Path(p.strip().strip('"')) for p in raw.split(";") if p.strip()]
    if sys.platform == "win32":
        try:
            import psutil
            found = [Path(p.mountpoint) for p in psutil.disk_partitions(all=False)
                     if "cdrom" not in p.opts.lower() and p.fstype]
            if found:
                return found
        except Exception:
            pass
        return [Path("C:/")]
    return [Path.home()]


def build_index(root_list: list[Path] | None = None) -> int:
    """Walk the disks and rebuild the index. Returns the number of entries. Safe to call from a thread."""
    with _lock:
        if _state["building"]:
            return _state["rows"]
        _state.update(building=True, error="")
    n = 0
    try:
        conn = _connect()
        conn.execute("DELETE FROM files")
        batch: list[tuple] = []
        dir_bytes: dict[str, int] = {}
        dir_rows: dict[str, tuple] = {}
        for root in (root_list or roots()):
            for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
                dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_NAMES]
                total = 0
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    total += st.st_size
                    batch.append((fp, f, f.lower(), st.st_size, st.st_mtime, 0))
                dir_bytes[dirpath] = total
                try:
                    dir_rows[dirpath] = (dirpath, os.path.basename(dirpath) or dirpath,
                                         (os.path.basename(dirpath) or dirpath).lower(), 0,
                                         os.stat(dirpath).st_mtime, 1)
                except OSError:
                    pass
                if len(batch) >= 5000:
                    conn.executemany("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)", batch)
                    n += len(batch); batch = []
                    _state["rows"] = n
                if n > MAX_ROWS:
                    break
        # roll folder sizes up to their parents (deepest first), then store the folders
        for d in sorted(dir_bytes, key=len, reverse=True):
            parent = os.path.dirname(d)
            if parent and parent != d and parent in dir_bytes:
                dir_bytes[parent] += dir_bytes[d]
        batch += [(*row[:3], dir_bytes.get(p, 0), row[4], 1) for p, row in dir_rows.items()]
        conn.executemany("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)", batch)
        n += len(batch)
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('built_at', ?)", (str(time.time()),))
        conn.commit(); conn.close()
        _state.update(rows=n, built_at=time.time())
    except Exception as e:
        _state["error"] = str(e)[:150]
    finally:
        _state["building"] = False
    return n


def index_age() -> float | None:
    try:
        c = _connect()
        row = c.execute("SELECT v FROM meta WHERE k='built_at'").fetchone()
        c.close()
        return time.time() - float(row[0]) if row else None
    except Exception:
        return None


def search(query: str, where: str = "", kind: str = "", limit: int = 10) -> list[dict]:
    """Entries whose name contains every word of `query` (and whose path contains `where`)."""
    tokens = [t for t in re.split(r"[\s_\-.]+", query.lower()) if t]
    ext = ""
    if tokens and re.fullmatch(r"\.?[a-z0-9]{1,5}", tokens[-1]) and kind in ("", "file") and query.strip().startswith("."):
        ext = tokens.pop()
    clauses, args = [], []
    for t in tokens:
        clauses.append("nl LIKE ?"); args.append(f"%{t}%")
    if ext:
        clauses.append("nl LIKE ?"); args.append(f"%.{ext.lstrip('.')}")
    if where:
        clauses.append("lower(path) LIKE ?"); args.append(f"%{where.lower()}%")
    if kind == "folder":
        clauses.append("isdir=1")
    elif kind == "file":
        clauses.append("isdir=0")
    if not clauses:
        return []
    c = _connect()
    rows = c.execute(f"SELECT path,name,size,mtime,isdir FROM files WHERE {' AND '.join(clauses)} LIMIT 400", args).fetchall()
    c.close()
    q = query.lower().strip()

    def rank(r):
        path, name, size, mtime, isdir = r
        nl = name.lower()
        return (0 if nl == q else 1 if nl.startswith(q) else 2, isdir, -mtime, len(path))
    rows.sort(key=rank)
    return [{"path": p, "name": n, "size": s, "mtime": m, "isdir": bool(d)} for p, n, s, m, d in rows[:limit]]


def biggest(where: str = "", kind: str = "folder", limit: int = 10) -> list[dict]:
    c = _connect()
    clause = "isdir=1" if kind == "folder" else "isdir=0"
    args: list = []
    if where:
        clause += " AND lower(path) LIKE ?"; args.append(f"{where.lower()}%" if re.match(r"^[a-z]:", where.lower()) or where.startswith("/") else f"%{where.lower()}%")
    rows = c.execute(f"SELECT path,name,size,mtime,isdir FROM files WHERE {clause} ORDER BY size DESC LIMIT ?", args + [limit]).fetchall()
    c.close()
    return [{"path": p, "name": n, "size": s, "mtime": m, "isdir": bool(d)} for p, n, s, m, d in rows]


def _forget(path: str) -> None:
    try:
        c = _connect()
        c.execute("DELETE FROM files WHERE path=? OR path LIKE ?", (path, path.rstrip("/\\") + os.sep + "%"))
        c.commit(); c.close()
    except Exception:
        pass


# ── safety ────────────────────────────────────────────────────────────────────

def protected_reason(p: Path) -> str:
    """Why this path must never be deleted by voice ('' when it may be, after confirmation)."""
    try:
        r = p.resolve()
    except OSError:
        return "I can't resolve that path"
    low = str(r).lower().replace("/", "\\") if sys.platform == "win32" else str(r)
    if r.parent == r or (sys.platform == "win32" and re.fullmatch(r"[a-z]:\\?", low)):
        return "that's a whole drive"
    home = Path.home().resolve()
    if r == home or r in home.parents:
        return "that's your user folder or above it"
    if sys.platform == "win32":
        win = os.environ.get("SystemRoot", r"C:\Windows").lower()
        pf = [os.environ.get("ProgramFiles", r"C:\Program Files").lower(),
              os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)").lower(),
              os.environ.get("ProgramData", r"C:\ProgramData").lower()]
        if low == win or low.startswith(win + "\\"):
            return "that's part of Windows"
        if any(low == x or low.startswith(x + "\\") for x in pf):
            return "that's installed software: uninstall it from Settings → Apps instead"
    else:
        for sysdir in ("/bin", "/boot", "/etc", "/lib", "/lib64", "/proc", "/sbin", "/sys", "/usr", "/var", "/dev"):
            if low == sysdir or low.startswith(sysdir + "/"):
                return "that's part of the operating system"
    try:
        here = Path(__file__).resolve().parent.parent
        if r == here or here in r.parents or r in here.parents:
            return "that's Jarvis itself (or a folder that contains it)"
    except Exception:
        pass
    return ""


def _recycle(path: Path) -> str:
    try:
        import send2trash
    except ImportError:
        raise RuntimeError("the Recycle Bin library (send2trash) isn't installed")
    send2trash.send2trash(str(path))
    return f"Moved to the Recycle Bin: {path.name}"


def _size_text(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


def _line(i: int, r: dict) -> str:
    when = time.strftime("%Y-%m-%d", time.localtime(r["mtime"]))
    kind = (f"folder, {_size_text(r['size'])}" if r["size"] else "folder") if r["isdir"] else _size_text(r["size"])
    return f"{i}. {r['name']} — {kind}, {when} — {r['path']}"


def _listing(results: list[dict]) -> str:
    return "\n".join(_line(i, r) for i, r in enumerate(results, 1))


def _pick(parameters: dict) -> dict | None:
    n = parameters.get("item_number")
    if n is not None and 1 <= int(n) <= len(_last):
        return _last[int(n) - 1]
    p = str(parameters.get("path") or "").strip().strip('"')
    if p and Path(p).exists():
        return {"path": p, "name": Path(p).name, "size": 0, "mtime": 0, "isdir": Path(p).is_dir()}
    return None


def reveal(path: str) -> None:
    p = str(Path(path))
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{p}"], creationflags=0x08000000)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", p])
    else:
        subprocess.Popen(["xdg-open", str(Path(p).parent)])


# ── the tool ──────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "file_finder",
    "description": (
        "Find files and folders ANYWHERE on this computer (every drive), show one in Explorer, report what's "
        "taking up disk space, and delete to the Recycle Bin (with the user's confirmation). Use for 'where "
        "is …', 'find my … file', 'which folder is biggest', 'what's using my disk', 'delete that', 'show me "
        "that in Explorer'. Search results are numbered; refer to them by number afterwards. Prefer this over "
        "file_controller for anything outside simple Desktop/Documents/Downloads work."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["find", "reveal", "biggest", "delete", "refresh", "status"]},
            "query": {"type": "STRING", "description": "For find: words from the name (or '.pdf' for an extension)"},
            "where": {"type": "STRING", "description": "For find/biggest: part of the path, e.g. 'D:' or 'Documents'"},
            "kind": {"type": "STRING", "enum": ["file", "folder"], "description": "For find/biggest"},
            "item_number": {"type": "INTEGER", "description": "For reveal/delete: number from the last list"},
            "path": {"type": "STRING", "description": "For reveal/delete when no list exists: the full path"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Find files anywhere, reveal, disk usage, delete to the Recycle Bin.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "FILE FINDER",
    "fields": [
        {"key": "index_roots", "label": "Folders and drives to index (; between them, empty = every drive)",
         "type": "text", "placeholder": r"C:\; D:\; E:\Games"},
    ],
}


def _ensure_index(wait: float = 0.0) -> str:
    """'' when the index can answer; otherwise a sentence about why not yet."""
    age = index_age()
    if age is None:
        if not _state["building"]:
            threading.Thread(target=build_index, daemon=True, name="file_index").start()
        if wait:
            for _ in range(int(wait * 10)):
                if index_age() is not None:
                    return ""
                time.sleep(0.1)
        return ("I'm still making my first list of the files on this computer (it takes a minute or two); "
                "ask again shortly")
    if age > REFRESH_SECONDS and not _state["building"]:
        threading.Thread(target=build_index, daemon=True, name="file_index").start()   # answer from the old one meanwhile
    return ""


def run(parameters: dict, player=None, session_memory=None) -> str:
    global _last
    action = str(parameters.get("action") or "find")
    try:
        if action == "status":
            age = index_age()
            return outcome.done("file_index", entries=_state["rows"] or None, building=_state["building"],
                                age_minutes=None if age is None else int(age // 60), error=_state["error"] or None)
        if action == "refresh":
            if not _state["building"]:
                threading.Thread(target=build_index, daemon=True, name="file_index").start()
            return outcome.started("file_index", note="say you're refreshing your list of files; it takes a minute or two")

        if action in ("find", "biggest"):
            wait = _ensure_index(wait=2.0)
            if wait:
                return outcome.failed(f"file_{action}", wait)
            if action == "find":
                q = str(parameters.get("query") or "").strip()
                if not q:
                    return outcome.ask("file_find", "What should I look for?")
                results = search(q, str(parameters.get("where") or ""), str(parameters.get("kind") or ""))
                if not results:
                    return outcome.done("file_find", count=0, note="nothing matched; try fewer or different "
                                        "words, or say 'refresh your file list' if it is brand new")
            else:
                results = biggest(str(parameters.get("where") or ""), str(parameters.get("kind") or "folder"))
                if not results:
                    return outcome.done("file_biggest", count=0)
            _last = results
            text = _listing(results)
            addons.show("FILES — " + (str(parameters.get("query") or "biggest")[:30]), text)
            return outcome.done(f"file_{action}", count=len(results)) + "\n" + outcome.untrusted("files", text)

        target = _pick(parameters)
        if target is None:
            return outcome.ask(f"file_{action}", "Which one? Say its number from the list, or the full path.")
        path = Path(target["path"])
        if not path.exists():
            _forget(str(path))
            return outcome.failed(f"file_{action}", "it no longer exists (I've dropped it from my list)")

        if action == "reveal":
            reveal(str(path))
            return outcome.done("file_reveal", opened=target["name"])

        if action == "delete":
            why = protected_reason(path)
            if why:
                return outcome.failed("file_delete", f"I won't delete that: {why}")
            from core import confirm
            what = "folder" if path.is_dir() else "file"
            extra = ""
            if path.is_dir():
                size = target.get("size") or 0
                extra = f" ({_size_text(size)} with everything inside)" if size else " with everything inside"

            def do() -> str:
                try:
                    msg = _recycle(path)
                except PermissionError:
                    return outcome.failed("file_delete", "Windows won't let me delete that without administrator "
                                          "rights, or something is using it. Close the program using it and try again")
                except Exception as e:
                    return outcome.failed("file_delete", str(e)[:150])
                _forget(str(path))
                try:
                    from core.undo import push_undo
                    from actions.file_controller import _restore_from_trash
                    push_undo(f"deleted {path.name}", lambda p=path.resolve(): _restore_from_trash(p))
                except Exception:
                    pass
                return outcome.done("file_delete", result=msg, note="it's in the Recycle Bin; 'undo' restores it")
            return confirm.request(f"file_delete:{path}", f"Delete this {what}",
                                   f"Move the {what} {path.name}{extra} to the Recycle Bin?\n{path}", do)
        return outcome.failed("file_finder", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"file_{action}", str(e)[:160])


def _boot() -> None:
    time.sleep(90)                                  # let Jarvis finish starting before walking the disks
    try:
        age = index_age()
        if age is None or age > REFRESH_SECONDS:
            build_index()
    except Exception as e:
        print(f"[FileFinder] {e}")


threading.Thread(target=_boot, daemon=True, name="file_index_boot").start()
