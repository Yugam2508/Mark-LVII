"""
plugins/google_drive.py — find, read and create files in Google Drive and Google Docs.

    "Find my chemistry notes in Drive"          action=search  query="chemistry notes"
    "What were my most recent files?"           action=recent
    "Read the second one" / "summarise it"      action=read    file_number=2
    "Open it"                                   action=open    file_number=1
    "Make a Google Doc with my packing list"    action=create_doc title=... content=...
    "Write a Google Doc about X for me"         action=create_doc title=... request=...
    "Add this to that doc: ..."                 action=append  file_number=1 content=...

Reads Google Docs, Sheets, Slides, PDFs, Word and text files (text only).
Writing is limited to Docs that JARVIS created (Google's drive.file permission):
it can never change or delete your existing files.

Uses the shared Google sign-in. A sign-in made before this plugin existed has no
Drive permission; the plugin says so and asks for one reconnect.
"""
from __future__ import annotations

import io
import tempfile
import threading
import webbrowser
from pathlib import Path

from core import outcome
from plugins import _google_auth as gauth

PLUGIN_SETTINGS = gauth.PLUGIN_SETTINGS
MAX_READ = 6000
FIELDS = "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName))"
EXPORT = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
}
KIND = {
    "application/vnd.google-apps.document": "Doc",
    "application/vnd.google-apps.spreadsheet": "Sheet",
    "application/vnd.google-apps.presentation": "Slides",
    "application/vnd.google-apps.folder": "Folder",
    "application/pdf": "PDF",
}

_last: list[dict] = []
_last_lock = threading.Lock()


def _remember(files: list[dict]) -> None:
    with _last_lock:
        _last[:] = files


def _pick(p: dict) -> dict | None:
    with _last_lock:
        last = list(_last)
    n = p.get("file_number")
    if n is None and len(last) == 1:
        return last[0]
    if n is not None and 1 <= int(n) <= len(last):
        return last[int(n) - 1]
    return None


def _render(files: list[dict]) -> str:
    return "\n".join(f"{i}. {f['name']} ({KIND.get(f['mimeType'], f['mimeType'].split('/')[-1])}, "
                     f"{f.get('modifiedTime', '')[:10]})" for i, f in enumerate(files, 1))


def _listing(action: str, files: list[dict], player, title: str) -> str:
    _remember(files)
    if not files:
        return outcome.done(action, count=0)
    text = _render(files)
    if player:
        try:
            player.show_content(title, text)
        except Exception:
            pass
    return outcome.done(action, count=len(files)) + "\n" + outcome.untrusted("drive", text)


def _search(svc, p, player) -> str:
    q = (p.get("query") or "").strip().replace("\\", "").replace("'", "\\'")
    if not q:
        return outcome.ask("drive_search", "What should I look for in your Drive?")
    files = svc.files().list(
        q=f"(name contains '{q}' or fullText contains '{q}') and trashed = false",
        pageSize=10, fields=FIELDS).execute().get("files", [])
    return _listing("drive_search", files, player, f"DRIVE — '{p.get('query')}'")


def _recent(svc, p, player) -> str:
    files = svc.files().list(q="trashed = false and mimeType != 'application/vnd.google-apps.folder'",
                             orderBy="modifiedTime desc", pageSize=10,
                             fields=FIELDS).execute().get("files", [])
    return _listing("drive_recent", files, player, "DRIVE — RECENT")


def _read_text(svc, f: dict) -> str:
    mime = f["mimeType"]
    if mime in EXPORT:
        data = svc.files().export(fileId=f["id"], mimeType=EXPORT[mime]).execute()
        return data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
    if mime.startswith("text/") or mime in ("application/json", "text/csv"):
        data = svc.files().get_media(fileId=f["id"]).execute()
        return data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
    ext = {"application/pdf": ".pdf",
           "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
           "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx"}.get(mime)
    if not ext:
        raise ValueError(f"this kind of file ({mime}) can't be read as text")
    data = svc.files().get_media(fileId=f["id"]).execute()
    from plugins import knowledge_base
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"file{ext}"
        path.write_bytes(data)
        return knowledge_base._read(path)


def _read(svc, p, player) -> str:
    f = _pick(p)
    if f is None:
        return outcome.ask("drive_read", "Which file? Search or list them first, then say its number.")
    text = _read_text(svc, f).strip()
    cut = len(text) > MAX_READ
    text = text[:MAX_READ]
    if player:
        try:
            player.show_content(f["name"], text[:3000])
        except Exception:
            pass
    return outcome.done("drive_read", file_number=p.get("file_number"), truncated=cut) + "\n" + \
        outcome.untrusted("drive", f"File: {f['name']}\n\n{text}")


def _open(svc, p, player) -> str:
    f = _pick(p)
    if f is None or not f.get("webViewLink"):
        return outcome.ask("drive_open", "Which file should I open?")
    webbrowser.open(f["webViewLink"])
    return outcome.unverified("drive_open", "it was handed to the browser", file=f["name"])


def _create_doc(svc, p, player) -> str:
    title = (p.get("title") or "").strip() or "Untitled (JARVIS)"
    content = (p.get("content") or "").strip()
    engine = None
    if not content and p.get("request"):
        from plugins import _writing
        content, engine = _writing.write(f"Write a document. {p['request']}\nUse plain text with "
                                         "simple headings; no markdown symbols.")
    docs = gauth.service("docs", "v1")
    doc = docs.documents().create(body={"title": title}).execute()
    if content:
        docs.documents().batchUpdate(documentId=doc["documentId"], body={"requests": [
            {"insertText": {"location": {"index": 1}, "text": content}}]}).execute()
    link = f"https://docs.google.com/document/d/{doc['documentId']}/edit"
    f = {"id": doc["documentId"], "name": title, "webViewLink": link,
         "mimeType": "application/vnd.google-apps.document"}
    _remember([f])
    if p.get("open", True):
        webbrowser.open(link)
    if player:
        try:
            player.show_content(f"NEW DOC — {title}", (content or "(empty)")[:3000])
        except Exception:
            pass
    return outcome.done("drive_create_doc", title=title, written_by=engine, link=link)


def _append(svc, p, player) -> str:
    f = _pick(p)
    content = (p.get("content") or "").strip()
    if f is None or f["mimeType"] != "application/vnd.google-apps.document":
        return outcome.ask("drive_append", "Which Google Doc should I add to?")
    if not content:
        return outcome.ask("drive_append", "What should I add?")
    docs = gauth.service("docs", "v1")
    doc = docs.documents().get(documentId=f["id"], fields="body(content(endIndex))").execute()
    end = max(1, doc["body"]["content"][-1]["endIndex"] - 1)
    try:
        docs.documents().batchUpdate(documentId=f["id"], body={"requests": [
            {"insertText": {"location": {"index": end}, "text": "\n" + content}}]}).execute()
    except Exception as e:
        if "403" in str(e) or "permission" in str(e).lower():
            return outcome.failed("drive_append", "JARVIS can only edit Docs it created itself; "
                                  "this one belongs to you, so add it there yourself or ask me "
                                  "to make a new doc", file=f["name"])
        raise
    return outcome.done("drive_append", file=f["name"])


_ACTIONS = {"search": _search, "recent": _recent, "read": _read, "open": _open,
            "create_doc": _create_doc, "append": _append}

PLUGIN = {
    "name": "google_drive",
    "description": (
        "The user's Google Drive and Google Docs: search files, list recent ones, read a "
        "file (Docs, Sheets, Slides, PDF, Word), open it in the browser, create a new "
        "Google Doc (with given content, or written for them from a request), or add text "
        "to a Doc you created. Refer to files by their number in the last list. For files "
        "on this computer use file_processor; for the knowledge folder use knowledge_base."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": list(_ACTIONS)},
            "query": {"type": "STRING", "description": "For search: words in the name or text"},
            "file_number": {"type": "INTEGER", "description": "Number from the last list"},
            "title": {"type": "STRING", "description": "For create_doc"},
            "content": {"type": "STRING", "description": "For create_doc/append: exact text"},
            "request": {"type": "STRING",
                        "description": "For create_doc: what to write, when the user wants it written for them"},
            "open": {"type": "BOOLEAN", "description": "For create_doc: open it afterwards (default true)"},
        },
        "required": ["action"],
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "core",
    "brief": "Google Drive/Docs: search, recent, read, open, create_doc, append.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "recent")
    handler = _ACTIONS.get(action)
    if handler is None:
        return outcome.failed("drive", f"unknown action {action}")
    if not gauth.libraries_installed():
        return outcome.failed("drive", "the Google libraries are not installed")
    try:
        if gauth.load_credentials() is None:
            return outcome.failed("drive", gauth.SETUP_STEPS)
        if not gauth.has_access("drive"):
            return outcome.failed("drive", gauth.RECONNECT)
        return handler(gauth.service("drive", "v3"), parameters, player)
    except Exception as e:
        msg = str(e)
        if "has not been used" in msg or "is disabled" in msg:
            return outcome.failed(f"drive_{action}", "the Drive or Docs API is not enabled in "
                                  "your Google Cloud project (APIs & Services → Library)")
        return outcome.failed(f"drive_{action}", f"Google Drive error: {msg[:180]}")
