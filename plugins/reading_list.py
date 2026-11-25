"""
plugins/reading_list.py — things to read, watch, listen to or play later.

    "Save this for later" (the open page)        → screen_helper save_page
    "Add Dune to my watch list"                   action=save item=Dune kind=watch
    "Save https://… to read later"                action=save item=<url> kind=read
    "What's on my watch list?"                    action=list kind=watch
    "Pick something for me to watch tonight"      action=pick kind=watch
    "I've watched Dune" / "done with the second one"  action=done query=Dune | number=2

Kept as a Google Tasks list called "Reading & Watching" — so it is on your phone
in the Google Tasks app, and both PCs share it. Links are stored in the notes,
with the page title looked up for you. Without Google it is kept in
"JARVIS Reading List.md" in your knowledge folder. On weekends the morning
briefing suggests one thing from it.
"""
from __future__ import annotations

import json
import random
import re
import threading

from core import outcome
from memory.config_manager import get_plugin_setting, save_plugin_config

NAMESPACE = "reading_list"
LIST_NAME = "Reading & Watching"
KINDS = ("read", "watch", "listen", "play")
TAG = {"read": "📖", "watch": "🎬", "listen": "🎧", "play": "🎮"}
_last: list[dict] = []
_lock = threading.Lock()


def _kind_for(item: str, kind: str | None) -> str:
    if kind in KINDS:
        return kind
    if re.search(r"youtube\.com|youtu\.be|netflix|primevideo|disneyplus|twitch\.tv", item, re.I):
        return "watch"
    if re.search(r"spotify\.com|podcast", item, re.I):
        return "listen"
    if re.search(r"store\.steampowered|epicgames", item, re.I):
        return "play"
    return "read"


def _title_for(url: str) -> str:
    try:
        from core.tasks import web
        doc = web.fetch_document(url)
        return (doc.get("title") or "").strip()[:120] or url
    except Exception:
        return url


# ── storage ───────────────────────────────────────────────────────────────────

def _tasks():
    from plugins import _google_auth as gauth
    if not gauth.libraries_installed() or not gauth.has_access("tasks"):
        return None
    return gauth.service("tasks", "v1")


def _list_id(svc) -> str:
    lid = str(get_plugin_setting(NAMESPACE, "list_id", "") or "")
    if lid:
        return lid
    lists = svc.tasklists().list(maxResults=100).execute().get("items", [])
    found = next((l for l in lists if l.get("title") == LIST_NAME), None)
    lid = (found or svc.tasklists().insert(body={"title": LIST_NAME}).execute())["id"]
    save_plugin_config(NAMESPACE, {"list_id": lid})
    return lid


def _md_path():
    from plugins import knowledge_base
    folder = knowledge_base._folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "JARVIS Reading List.md"


def _md_items() -> list[dict]:
    path = _md_path()
    items = []
    if path.exists():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            m = re.match(r"^- \[( |x)\] (\S+) (.+?)(?: <(.+)>)?$", line)
            if m and m.group(1) == " ":
                items.append({"id": str(i), "kind": next((k for k, t in TAG.items() if t == m.group(2)), "read"),
                              "title": m.group(3), "link": m.group(4) or ""})
    return items


def items(kind: str | None = None) -> list[dict]:
    svc = _tasks()
    if svc is None:
        out = _md_items()
    else:
        raw = svc.tasks().list(tasklist=_list_id(svc), showCompleted=False,
                               maxResults=100).execute().get("items", [])
        out = []
        for t in raw:
            title = t.get("title", "")
            k = next((k for k, tag in TAG.items() if title.startswith(tag)), "read")
            notes = t.get("notes", "")
            link = re.search(r"https?://\S+", notes)
            out.append({"id": t["id"], "kind": k, "title": title.lstrip("".join(TAG.values())).strip(),
                        "link": link.group(0) if link else ""})
    return [i for i in out if not kind or i["kind"] == kind]


def add(item: str, kind: str | None = None, note: str = "") -> dict:
    item = item.strip()
    link = item if item.startswith(("http://", "https://")) else ""
    k = _kind_for(item, kind)
    title = _title_for(link) if link else item
    svc = _tasks()
    if svc is None:
        with _lock, _md_path().open("a", encoding="utf-8") as f:
            f.write(f"- [ ] {TAG[k]} {title}" + (f" <{link}>" if link else "") + "\n")
    else:
        svc.tasks().insert(tasklist=_list_id(svc), body={
            "title": f"{TAG[k]} {title}", "notes": "\n".join(x for x in (link, note) if x)}).execute()
    return {"kind": k, "title": title, "link": link}


def mark_done(entry: dict) -> None:
    svc = _tasks()
    if svc is None:
        path = _md_path()
        lines = path.read_text(encoding="utf-8").splitlines()
        i = int(entry["id"])
        lines[i] = lines[i].replace("- [ ]", "- [x]", 1)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        svc.tasks().patch(tasklist=_list_id(svc), task=entry["id"], body={"status": "completed"}).execute()


def pick_one(kind: str | None = None) -> str:
    """One suggestion (used by the weekend briefing too). '' when the list is empty."""
    try:
        pool = items(kind)
    except Exception:
        return ""
    if not pool:
        return ""
    e = random.choice(pool)
    return f"{TAG[e['kind']]} {e['title']}"


# ── tool ──────────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "reading_list",
    "description": (
        "The user's 'later' list of things to read, watch, listen to or play: save something "
        "(a title or a link), list what's on it, pick one for them, or mark one done. For the "
        "web page open in the browser use screen_helper save_page."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["save", "list", "pick", "done"]},
            "item": {"type": "STRING", "description": "For save: a title or a link"},
            "kind": {"type": "STRING", "enum": list(KINDS)},
            "note": {"type": "STRING", "description": "For save: who recommended it, why"},
            "number": {"type": "INTEGER", "description": "For done: number in the last list"},
            "query": {"type": "STRING", "description": "For done: words from the title"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Read/watch-later list: save, list, pick, done.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    kind = parameters.get("kind") if parameters.get("kind") in KINDS else None
    try:
        if action == "save":
            item = str(parameters.get("item") or "").strip()
            if not item:
                return outcome.ask("later_save", "What should I save?")
            e = add(item, kind, str(parameters.get("note") or ""))
            return outcome.done("later_save", kind=e["kind"]) + "\n" + outcome.untrusted("later", e["title"])
        if action == "pick":
            pick = pick_one(kind)
            return outcome.done("later_pick", empty=not pick) + \
                ("\n" + outcome.untrusted("later", pick) if pick else "")
        pool = items(kind)
        with _lock:
            _last[:] = pool
        if action == "done":
            entry = None
            if parameters.get("number"):
                n = int(parameters["number"])
                entry = pool[n - 1] if 1 <= n <= len(pool) else None
            elif parameters.get("query"):
                hits = [e for e in pool if str(parameters["query"]).lower() in e["title"].lower()]
                entry = hits[0] if len(hits) == 1 else None
            if entry is None:
                return outcome.ask("later_done", "Which one? Say its number or part of the title.")
            mark_done(entry)
            return outcome.done("later_done") + "\n" + outcome.untrusted("later", entry["title"])
        text = "\n".join(f"{i}. {TAG[e['kind']]} {e['title']}" for i, e in enumerate(pool, 1)) or "The list is empty."
        if player:
            player.show_content("LATER", text)
        return outcome.done("later_list", count=len(pool)) + "\n" + outcome.untrusted("later", text)
    except Exception as e:
        return outcome.failed(f"later_{action}", str(e)[:160])
