"""
plugins/notes.py — quick notes by voice, kept where every device can see them.

    "Note that the router password is on the fridge"       action=add text=...
    "Take a note: call the bank, book dentist, …" (rough)   action=add text=... tidy=true
    "Note down what we just talked about"                   action=add text=<summary> title=...
    "What did I note today?" / "read my last notes"         action=read
    "Did I note anything about the dentist?"                action=search query=dentist

WHERE NOTES GO (⚙ → PLUGIN SETTINGS → NOTES)
    knowledge  (default) `JARVIS Notes.md` in your knowledge folder — OneDrive, so
               both PCs and the OneDrive phone app see it, and knowledge_base can
               search it with the rest of your documents.
    notion     appended to your Notion home page (plugins/notion.py settings).
    google_doc a "JARVIS Notes" Google Doc, created the first time; open it on your
               phone in Google Docs.

`tidy=true` turns rambling dictation into clean bullet points with the writing
voice (plugins/_writing.py) before saving; the original meaning is kept.
"""
from __future__ import annotations

import datetime as dt
import re
import threading

from core import outcome
from memory.config_manager import get_plugin_setting, save_plugin_config

NAMESPACE = "notes"
BACKENDS = ("knowledge", "notion", "google_doc")
LOCAL_NAME = "JARVIS Notes.md"
_lock = threading.Lock()


def _backend() -> str:
    b = str(get_plugin_setting(NAMESPACE, "backend", "knowledge") or "knowledge")
    return b if b in BACKENDS else "knowledge"


def _stamp(title: str = "") -> str:
    head = dt.datetime.now().strftime("%a %d %b %Y, %H:%M")
    return f"## {head}" + (f" — {title}" if title else "")


# ── knowledge folder (local markdown, synced by OneDrive) ─────────────────────

def _local_path():
    from plugins import knowledge_base
    folder = knowledge_base._folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / LOCAL_NAME


def _local_add(entry: str) -> str:
    path = _local_path()
    with _lock:
        existing = path.read_text(encoding="utf-8") if path.exists() else "# JARVIS Notes\n"
        path.write_text(existing.rstrip() + "\n\n" + entry + "\n", encoding="utf-8")
    try:  # let knowledge_base pick the new note up for searching
        from plugins import knowledge_base
        threading.Thread(target=knowledge_base.build_index, daemon=True).start()
    except Exception:
        pass
    return str(path)


def _local_replace(old_entry: str, new_entry: str) -> bool:
    """Swap one saved note for its edited version. False if it is no longer there
    (edited by hand meanwhile), so nothing else in the file is ever touched."""
    path = _local_path()
    with _lock:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if old_entry not in text:
            return False
        path.write_text(text.replace(old_entry, new_entry, 1), encoding="utf-8")
    return True


def _local_text() -> str:
    path = _local_path()
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ── Notion ────────────────────────────────────────────────────────────────────

def _notion_add(entry: str) -> str:
    from plugins import notion
    pid = notion.home_page()
    if pid is None:
        raise RuntimeError("set a Notion home page in ⚙ → PLUGIN SETTINGS → NOTION first")
    notion.append_text(pid, entry)
    return "your Notion home page"


def _notion_text() -> str:
    from plugins import notion
    pid = notion.home_page()
    if pid is None:
        raise RuntimeError("set a Notion home page in ⚙ → PLUGIN SETTINGS → NOTION first")
    return notion.read_text(pid)


# ── Google Doc ────────────────────────────────────────────────────────────────

def _gdoc_id(create: bool) -> str | None:
    from plugins import _google_auth as gauth
    if not gauth.has_access("docs"):
        raise RuntimeError(gauth.RECONNECT if gauth.load_credentials() else gauth.SETUP_STEPS)
    doc_id = str(get_plugin_setting(NAMESPACE, "gdoc_id", "") or "")
    if doc_id or not create:
        return doc_id or None
    doc = gauth.service("docs", "v1").documents().create(body={"title": "JARVIS Notes"}).execute()
    save_plugin_config(NAMESPACE, {"gdoc_id": doc["documentId"]})
    return doc["documentId"]


def _gdoc_add(entry: str) -> str:
    from plugins import _google_auth as gauth
    doc_id = _gdoc_id(create=True)
    docs = gauth.service("docs", "v1")
    body = docs.documents().get(documentId=doc_id, fields="body(content(endIndex))").execute()
    end = max(1, body["body"]["content"][-1]["endIndex"] - 1)
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"insertText": {"location": {"index": end}, "text": "\n" + entry + "\n"}}]}).execute()
    return "the 'JARVIS Notes' Google Doc"


def _gdoc_text() -> str:
    from plugins import _google_auth as gauth
    doc_id = _gdoc_id(create=False)
    if not doc_id:
        return ""
    data = gauth.service("drive", "v3").files().export(fileId=doc_id, mimeType="text/plain").execute()
    return data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)


_ADD = {"knowledge": _local_add, "notion": _notion_add, "google_doc": _gdoc_add}
_TEXT = {"knowledge": _local_text, "notion": _notion_text, "google_doc": _gdoc_text}


def _entries(text: str) -> list[str]:
    """Split the notes into entries, newest last."""
    parts = re.split(r"\n(?=## )", "\n" + text)
    return [p.strip() for p in parts if p.strip().startswith("## ")]


def _open_editor(backend: str, header: str, entry: str, text: str, player) -> None:
    """Show the saved note so it can be corrected with a click."""
    from core import addons
    fields = [{"key": "text", "label": "Note", "value": text, "multiline": True}]
    actions, note = [], "Saved. Edit it and press SAVE CHANGES to fix it."
    if backend == "knowledge":
        current = {"entry": entry}

        def save(v: dict):
            new_entry = header + "\n" + v["text"].strip()
            if not _local_replace(current["entry"], new_entry):
                return False, "That note changed in the file meanwhile; edit JARVIS Notes.md directly."
            current["entry"] = new_entry
            return True, "Note updated ✓"

        actions = [{"label": "SAVE CHANGES", "run": save, "primary": True, "close": False,
                    "busy": "Saving…"}]
    else:
        note = (f"Saved to {'Notion' if backend == 'notion' else 'the JARVIS Notes Google Doc'}. "
                "To change it, edit it there.")
    if not addons.edit("NOTE SAVED", fields, actions, note=note, copy="text", player=player):
        if player:
            try:
                player.show_content("NOTE SAVED", text)
            except Exception:
                pass


# ── plugin ────────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "notes",
    "description": (
        "The user's quick notes: save a note ('note that…', 'take a note', 'write down', "
        "'note what we just discussed' — pass a summary as text), read recent notes, or "
        "search them. Set tidy=true for rambling dictation. Not for to-dos (todo_list), "
        "calendar events (calendar_control) or long documents (writer / google_drive)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["add", "read", "search"]},
            "text": {"type": "STRING", "description": "For add: the note"},
            "title": {"type": "STRING", "description": "For add: optional short heading"},
            "tidy": {"type": "BOOLEAN",
                     "description": "For add: clean rough dictation into bullet points first"},
            "count": {"type": "INTEGER", "description": "For read: how many recent notes (default 5)"},
            "query": {"type": "STRING", "description": "For search"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Quick notes: add / read / search.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "NOTES",
    "fields": [
        {"key": "backend", "label": "Keep notes in (knowledge = OneDrive knowledge folder)",
         "type": "choice", "options": list(BACKENDS), "default": "knowledge"},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "add")
    backend = _backend()
    try:
        if action == "add":
            text = (parameters.get("text") or "").strip()
            if not text:
                return outcome.ask("notes_add", "What should I note down?")
            if parameters.get("tidy"):
                from plugins import _writing
                try:
                    text, _ = _writing.write(
                        "Tidy these spoken notes into short bullet points ('- ' at the start of "
                        "each). Keep every fact, name, number and date; add nothing.\n\n" + text,
                        timeout=60)
                except RuntimeError:
                    pass  # save the original rather than nothing
            header = _stamp(str(parameters.get("title") or "").strip())
            entry = header + "\n" + text
            _ADD[backend](entry)
            _open_editor(backend, header, entry, text, player)
            return outcome.done("notes_add", saved_in=backend if backend != "knowledge"
                                else "JARVIS Notes.md in the knowledge folder")

        entries = _entries(_TEXT[backend]())
        if action == "search":
            q = (parameters.get("query") or "").strip().lower()
            if not q:
                return outcome.ask("notes_search", "What should I look for in your notes?")
            words = [w for w in re.findall(r"\w+", q) if len(w) > 2] or [q]
            hits = [e for e in entries if any(w in e.lower() for w in words)][-8:]
            if not hits:
                return outcome.done("notes_search", matches=0)
            return outcome.done("notes_search", matches=len(hits)) + "\n" + \
                outcome.untrusted("notes", "\n\n".join(hits))

        count = max(1, min(20, int(parameters.get("count") or 5)))
        recent = entries[-count:]
        if not recent:
            return outcome.done("notes_read", count=0)
        text = "\n\n".join(recent)
        if player:
            try:
                player.show_content("NOTES", text[-3000:])
            except Exception:
                pass
        return outcome.done("notes_read", count=len(recent)) + "\n" + outcome.untrusted("notes", text)
    except Exception as e:
        return outcome.failed(f"notes_{action}", str(e)[:200])
