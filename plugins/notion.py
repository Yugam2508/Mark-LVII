"""
plugins/notion.py — your Notion pages and databases by voice.

    "Search Notion for my project ideas"        action=search query="project ideas"
    "Read the first one"                        action=read   item_number=1
    "Add 'buy a new mouse' to that page"        action=append item_number=1 content=...
    "Make a Notion page called Trip plan with…" action=create_page title=... content=...
    "Add a row to my reading list: Dune"        action=create_page parent_number=1 title=Dune

SETUP (once, free)
    1. https://www.notion.so/profile/integrations → New integration → name it
       JARVIS, type Internal, your workspace → Save → copy the "Internal
       Integration Secret" (starts with ntn_).
    2. Paste it in ⚙ → PLUGIN SETTINGS → NOTION → TEST.
    3. In Notion, open each page you want JARVIS to use → ••• → Connections →
       JARVIS. Sharing a parent page shares everything inside it.
    Optionally paste the link of a page as the "home page" — new pages and quick
    notes go there when you do not say where.

Text read from Notion is handed to the model as untrusted content.
"""
from __future__ import annotations

import re
import threading

from core import outcome
from memory.config_manager import get_plugin_setting

NAMESPACE = "notion"
API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_READ = 6000

_last: list[dict] = []
_last_lock = threading.Lock()


class NotionError(RuntimeError):
    pass


def _token(values: dict | None = None) -> str:
    v = (values or {}).get("token") or get_plugin_setting(NAMESPACE, "token", "")
    return str(v or "").strip()


def page_id(text: str) -> str | None:
    """A page id from a Notion link or a bare id."""
    m = re.findall(r"[0-9a-f]{32}", (text or "").replace("-", "").lower())
    return m[-1] if m else None


def home_page() -> str | None:
    return page_id(str(get_plugin_setting(NAMESPACE, "home_page", "") or ""))


def api(method: str, path: str, body: dict | None = None, values: dict | None = None):
    import requests
    token = _token(values)
    if not token:
        raise NotionError("Notion is not set up: paste the integration secret in ⚙ → PLUGIN "
                          "SETTINGS → NOTION")
    r = requests.request(method, API + path, json=body, timeout=15, headers={
        "Authorization": f"Bearer {token}", "Notion-Version": VERSION,
        "Content-Type": "application/json"})
    if r.status_code == 401:
        raise NotionError("Notion refused the secret — check it in plugin settings")
    if r.status_code == 404:
        raise NotionError("Notion can't see that page — share it with the JARVIS connection "
                          "(••• → Connections)")
    if r.status_code >= 400:
        try:
            msg = r.json().get("message", r.text)
        except ValueError:
            msg = r.text
        raise NotionError(f"Notion error {r.status_code}: {msg[:160]}")
    return r.json() if r.content else {}


def _plain(rich: list) -> str:
    return "".join(t.get("plain_text", "") for t in rich or [])


def title_of(obj: dict) -> str:
    if obj.get("object") == "database":
        return _plain(obj.get("title")) or "(untitled database)"
    for prop in (obj.get("properties") or {}).values():
        if prop.get("type") == "title":
            return _plain(prop.get("title")) or "(untitled)"
    return "(untitled)"


def _paragraphs(text: str) -> list[dict]:
    blocks = []
    for line in text.splitlines() or [text]:
        line = line.rstrip()
        kind, body = "paragraph", line
        if line.startswith(("- ", "• ", "* ")):
            kind, body = "bulleted_list_item", line[2:]
        elif re.match(r"^\[( |x)\] ", line):
            blocks.append({"object": "block", "type": "to_do", "to_do": {
                "rich_text": [{"type": "text", "text": {"content": line[4:][:2000]}}],
                "checked": line[1] == "x"}})
            continue
        elif line.startswith("# "):
            kind, body = "heading_3", line[2:]
        for i in range(0, max(1, len(body)), 2000):
            blocks.append({"object": "block", "type": kind, kind: {
                "rich_text": [{"type": "text", "text": {"content": body[i:i + 2000]}}]}})
    return blocks


def append_text(pid: str, text: str) -> int:
    """Append ALL of `text` (Notion takes 100 blocks per request, so in batches). Returns the number of
    blocks written; raises if any batch fails, so a partial save is never reported as a save."""
    blocks = _paragraphs(text)
    written = 0
    for i in range(0, len(blocks), 100):
        batch = blocks[i:i + 100]
        data = api("PATCH", f"/blocks/{pid}/children", {"children": batch})
        got = len(data["results"]) if isinstance(data, dict) and "results" in data else len(batch)
        if got < len(batch):
            raise NotionError(f"Notion only accepted {written + got} of {len(blocks)} blocks")
        written += got
    return written


def read_text(pid: str) -> str:
    out, cursor = [], None
    for _ in range(10):
        path = f"/blocks/{pid}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        data = api("GET", path)
        for b in data.get("results", []):
            t = b.get("type")
            body = b.get(t, {}) if t else {}
            text = _plain(body.get("rich_text"))
            if t == "to_do":
                text = f"[{'x' if body.get('checked') else ' '}] {text}"
            elif t in ("bulleted_list_item", "numbered_list_item"):
                text = f"- {text}"
            elif t == "child_page":
                text = f"(page) {body.get('title', '')}"
            elif t and t.startswith("heading"):
                text = f"# {text}"
            if text.strip():
                out.append(text)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return "\n".join(out)


def _remember(items: list[dict]) -> None:
    with _last_lock:
        _last[:] = items


def _pick(n) -> dict | None:
    with _last_lock:
        last = list(_last)
    if n is None and len(last) == 1:
        return last[0]
    if n is not None and 1 <= int(n) <= len(last):
        return last[int(n) - 1]
    return None


def _show(player, title: str, text: str) -> None:
    if player:
        try:
            player.show_content(title, text)
        except Exception:
            pass


def find_by_name(name: str) -> dict | None:
    """The page or database the user named, without a separate search step: an exact title match
    first, then one that contains the words, then Notion's best hit."""
    name = (name or "").strip()
    if not name:
        return None
    data = api("POST", "/search", {"query": name, "page_size": 10})
    items = [{"id": r["id"], "object": r["object"], "title": title_of(r), "url": r.get("url")}
             for r in data.get("results", [])]
    if not items:
        return None
    low = name.lower()
    pick = next((i for i in items if i["title"].lower() == low), None) \
        or next((i for i in items if low in i["title"].lower()), None) or items[0]
    _remember([pick])
    return pick


def _target(p: dict, number_key: str = "item_number") -> dict | None:
    if p.get("page"):
        return find_by_name(str(p["page"]))
    return _pick(p.get(number_key))


# ── actions ───────────────────────────────────────────────────────────────────

def _search(p, player) -> str:
    q = (p.get("query") or "").strip()
    data = api("POST", "/search", {"query": q, "page_size": 10,
                                   "sort": {"direction": "descending",
                                            "timestamp": "last_edited_time"}})
    items = [{"id": r["id"], "object": r["object"], "title": title_of(r), "url": r.get("url")}
             for r in data.get("results", [])]
    _remember(items)
    if not items:
        return outcome.done("notion_search", count=0,
                            note="nothing found; pages must be shared with the JARVIS connection")
    text = "\n".join(f"{i}. {it['title']}{' (database)' if it['object'] == 'database' else ''}"
                     for i, it in enumerate(items, 1))
    _show(player, "NOTION", text)
    return outcome.done("notion_search", count=len(items)) + "\n" + outcome.untrusted("notion", text)


def _read(p, player) -> str:
    it = _target(p)
    if it is None:
        if p.get("page"):
            return outcome.failed("notion_read", f"no page called {p['page']} is shared with the JARVIS connection")
        return outcome.ask("notion_read", "Which page?")
    if it["object"] == "database":
        rows = api("POST", f"/databases/{it['id']}/query", {"page_size": 50}).get("results", [])
        text = "\n".join(f"- {title_of(r)}" for r in rows)
    else:
        text = read_text(it["id"])
    cut = len(text) > MAX_READ
    _show(player, it["title"], text[:3000])
    return outcome.done("notion_read", item_number=p.get("item_number"), truncated=cut) + "\n" + \
        outcome.untrusted("notion", f"{it['title']}\n\n{text[:MAX_READ]}")


def _append(p, player) -> str:
    content = (p.get("content") or "").strip()
    if not content:
        return outcome.ask("notion_append", "What should I add?")
    it = _target(p)
    if p.get("page") and it is None:
        return outcome.failed("notion_append", f"no page called {p['page']} is shared with the JARVIS connection")
    pid = it["id"] if it and it["object"] == "page" else (None if (p.get("item_number") or p.get("page")) else home_page())
    if pid is None:
        return outcome.ask("notion_append", "Which page should I add it to?")
    n = append_text(pid, content)
    return outcome.done("notion_append", page=it["title"] if it else "home page", blocks_written=n)


def _create_page(p, player) -> str:
    title = (p.get("title") or "").strip()
    if not title:
        return outcome.ask("notion_create_page", "What should the page be called?")
    content = (p.get("content") or "").strip()
    parent = find_by_name(str(p["parent"])) if p.get("parent") else \
        (_pick(p.get("parent_number")) if p.get("parent_number") else None)
    if p.get("parent") and parent is None:
        return outcome.failed("notion_create_page", f"no page called {p['parent']} is shared with the JARVIS connection")
    if parent and parent["object"] == "database":
        db = api("GET", f"/databases/{parent['id']}")
        title_prop = next((k for k, v in db.get("properties", {}).items() if v.get("type") == "title"), "Name")
        body = {"parent": {"database_id": parent["id"]},
                "properties": {title_prop: {"title": [{"text": {"content": title}}]}}}
    else:
        pid = parent["id"] if parent else home_page()
        if pid is None:
            return outcome.ask("notion_create_page", "Where should the page go? Search for the "
                               "parent page first, or set a home page in plugin settings.")
        body = {"parent": {"page_id": pid},
                "properties": {"title": {"title": [{"text": {"content": title}}]}}}
    blocks = _paragraphs(content) if content else []
    if blocks:
        body["children"] = blocks[:100]           # Notion takes 100 on create; the rest are appended
    page = api("POST", "/pages", body)
    for i in range(100, len(blocks), 100):
        api("PATCH", f"/blocks/{page['id']}/children", {"children": blocks[i:i + 100]})
    _remember([{"id": page["id"], "object": "page", "title": title, "url": page.get("url")}])
    return outcome.done("notion_create_page", title=title, url=page.get("url"))


def _test(values: dict) -> tuple[bool, str]:
    try:
        me = api("GET", "/users/me", values=values)
        n = len(api("POST", "/search", {"page_size": 100}, values=values).get("results", []))
    except NotionError as e:
        return False, str(e)
    note = "" if n else " — share some pages with it in Notion (••• → Connections)"
    return True, f"Connected as {me.get('name') or 'JARVIS'}: {n} shared page(s){note}"


INTEGRATIONS_URL = "https://www.notion.so/profile/integrations"


def _clipboard_secret() -> str:
    try:
        import pyperclip
        c = (pyperclip.paste() or "").strip()
        return c if re.match(r"^(ntn_|secret_)[A-Za-z0-9]{20,}$", c) else ""
    except Exception:
        return ""


def _setup(p, player) -> str:
    """Walk the setup one step at a time; each call does what it can and says what is next.
    The secret is taken from the clipboard — never spoken, typed to Jarvis or shown."""
    from memory.config_manager import get_plugin_config, save_plugin_config
    cfg = get_plugin_config(NAMESPACE)
    if not _token():
        secret = _clipboard_secret()
        if not secret:
            try:
                from plugins import claude_web
                claude_web.open_page(INTEGRATIONS_URL)
            except Exception:
                import webbrowser
                webbrowser.open(INTEGRATIONS_URL)
            return outcome.done(
                "notion_setup", step="1 of 3: create the connection", opened=INTEGRATIONS_URL,
                note="tell the user, briefly: on the page that just opened choose New integration, "
                     "name it JARVIS, type Internal, pick their workspace, Save; then press Copy on "
                     "the Internal Integration Secret (it starts ntn_) and say 'set up Notion' again — "
                     "you will read it from the clipboard, they never need to say or type it")
        cfg["token"] = secret
        save_plugin_config(NAMESPACE, cfg)
        try:
            import pyperclip; pyperclip.copy("")           # the secret does not linger
        except Exception:
            pass
    try:
        me = api("GET", "/users/me")
        results = api("POST", "/search", {"page_size": 100}).get("results", [])
    except NotionError as e:
        return outcome.failed("notion_setup", str(e),
                              note="the secret was saved but Notion refused it: copy it again from the "
                                   "integration page and say 'set up Notion' again")
    pages = [r for r in results if r.get("object") == "page"]
    if not pages:
        return outcome.done(
            "notion_setup", step="2 of 3: share a page", connected=me.get("name") or "JARVIS", shared=0,
            note="connected, but no pages are shared yet. Tell the user: in Notion make a page called "
                 "Jarvis (or open any page), press the ••• menu, Connections, and add JARVIS; sharing "
                 "a parent page shares everything inside. Then say 'set up Notion' again")
    msg = ""
    if not home_page():
        pick = next((r for r in pages if "jarvis" in title_of(r).lower()), None) or pages[0]
        cfg = get_plugin_config(NAMESPACE)
        cfg["home_page"] = pick.get("url") or pick["id"]
        save_plugin_config(NAMESPACE, cfg)
        msg = f"home page set to '{title_of(pick)}'"
    return outcome.done("notion_setup", step="3 of 3: done", connected=me.get("name") or "JARVIS",
                        shared=len(pages), home=msg or "kept the existing home page",
                        note="say it is ready in one sentence and give an example, like 'add buy a new "
                             "mouse to my Jarvis page'")


_ACTIONS = {"search": _search, "read": _read, "append": _append, "create_page": _create_page,
            "setup": _setup}

PLUGIN = {
    "name": "notion",
    "description": (
        "The user's Notion: search pages and databases, read one, add text to a page, or "
        "create a page (or a row in a database). Use whenever the user mentions Notion. "
        "'setup' for 'set up Notion' / 'connect Notion': it does the setup step by step and says "
        "what to do next; call it again after each step. "
        "Name the page with 'page' (e.g. page='Jarvis ideas') to read or add to it directly, no search "
        "needed; or refer to a number from the last list."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": list(_ACTIONS)},
            "query": {"type": "STRING", "description": "For search"},
            "page": {"type": "STRING", "description": "For read/append: the page's name as the user said it"},
            "parent": {"type": "STRING", "description": "For create_page: name of the parent page or database"},
            "item_number": {"type": "INTEGER", "description": "For read/append: number from the last list"},
            "parent_number": {"type": "INTEGER",
                              "description": "For create_page: number of the parent page or database "
                                             "in the last list; empty = the home page"},
            "title": {"type": "STRING"},
            "content": {"type": "STRING",
                        "description": "Text; lines starting '- ' become bullets, '[ ] ' to-dos, '# ' headings"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Notion: search, read, append, create_page.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "NOTION",
    "fields": [
        {"key": "token", "label": "Internal integration secret (ntn_…)", "type": "password"},
        {"key": "home_page", "label": "Home page link (where new pages and notes go)",
         "type": "text", "placeholder": "https://www.notion.so/My-JARVIS-page-1a2b3c…"},
    ],
    "action": {"label": "TEST", "run": _test},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "search")
    handler = _ACTIONS.get(action)
    if handler is None:
        return outcome.failed("notion", f"unknown action {action}")
    try:
        return handler(parameters, player)
    except NotionError as e:
        return outcome.failed(f"notion_{action}", str(e))
    except Exception as e:
        return outcome.failed(f"notion_{action}", f"Notion error: {str(e)[:160]}")
