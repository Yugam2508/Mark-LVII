"""
plugins/todo_list.py — a to-do list you can talk to, kept in Google Tasks.

    "Add buy milk to my list"                  action=add      title="Buy milk"
    "Remind me to submit the essay by Friday"  action=add      title="Submit the essay" due=2026-11-27
    "What's on my to-do list?"                 action=list
    "Tick off the second one" / "done: milk"   action=complete item_number=2 | query=milk
    "Remove the essay one"                     action=remove   query=essay
    "Clear the finished ones"                  action=clear_completed

WHY GOOGLE TASKS
    The same list then shows up everywhere without any sync of ours: the Google
    Tasks app on your phone, Gmail and Calendar's side panel, and every computer
    JARVIS runs on. Sign-in is the one shared with Gmail and Calendar
    (plugins/_google_auth.py) — connecting Google once covers all three.

    The list is also put on the HUD each time it changes, so you can see it while
    you talk.
"""
from __future__ import annotations

import datetime as dt
import threading

from core import outcome
from plugins import _google_auth as gauth

PLUGIN_SETTINGS = gauth.PLUGIN_SETTINGS
LIST_ID = "@default"   # the "My Tasks" list every Google account has

PLUGIN = {
    "name": "todo_list",
    "description": (
        "The user's to-do list (Google Tasks, also on their phone). Use to add a task, "
        "read the list, tick a task off, remove one, or clear finished ones. Use for "
        "'add X to my list', 'what do I need to do', 'I've done X'. For a spoken alert "
        "at a set time use `reminder`; for meetings use `calendar_control`."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "enum": ["add", "list", "complete", "remove", "clear_completed"]},
            "title": {"type": "STRING", "description": "For add: the task, short"},
            "due": {"type": "STRING", "description": "For add: optional due date YYYY-MM-DD"},
            "notes": {"type": "STRING", "description": "For add: optional details"},
            "item_number": {"type": "INTEGER",
                            "description": "For complete/remove: number in the last list read out"},
            "query": {"type": "STRING",
                      "description": "For complete/remove: words from the task title"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "To-do list (Google Tasks): add/list/complete/remove.",
}

_last: list[dict] = []
_last_lock = threading.Lock()


def _open_tasks(svc) -> list[dict]:
    items, token = [], None
    for _ in range(5):  # up to 500 open tasks
        resp = svc.tasks().list(tasklist=LIST_ID, showCompleted=False, showHidden=False,
                                maxResults=100, pageToken=token).execute()
        items += [t for t in resp.get("items", []) if t.get("title", "").strip()]
        token = resp.get("nextPageToken")
        if not token:
            break
    # Due ones first (soonest first), then the rest in Google's own order.
    return sorted(items, key=lambda t: (t.get("due") is None, t.get("due") or "",
                                        t.get("position", "")))


def _due_label(task: dict) -> str:
    if not task.get("due"):
        return ""
    d = dt.date.fromisoformat(task["due"][:10])
    today = dt.date.today()
    if d < today:
        return " (overdue)"
    if d == today:
        return " (today)"
    if d == today + dt.timedelta(days=1):
        return " (tomorrow)"
    return f" (by {d.strftime('%a %d %b')})"


def _render(tasks: list[dict]) -> str:
    if not tasks:
        return "Nothing to do. ✓"
    return "\n".join(f"{i}. {t['title']}{_due_label(t)}" for i, t in enumerate(tasks, 1))


def _refresh(svc, player) -> list[dict]:
    tasks = _open_tasks(svc)
    with _last_lock:
        _last[:] = tasks
    if player:
        try:
            player.show_content(f"TO-DO — {len(tasks)} OPEN", _render(tasks))
        except Exception:
            pass
    return tasks


def _find(svc, p) -> tuple[dict | None, str | None]:
    """(task, question-to-ask) for complete/remove."""
    with _last_lock:
        last = list(_last)
    if not last:
        last = _open_tasks(svc)
    n = p.get("item_number")
    if n:
        if 1 <= int(n) <= len(last):
            return last[int(n) - 1], None
        return None, "There's no task with that number. Which one did you mean?"
    q = (p.get("query") or "").strip().lower()
    if q:
        hits = [t for t in last if q in t["title"].lower()]
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            names = "; ".join(t["title"] for t in hits[:4])
            return None, f"Several tasks match: {names}. Which one?"
        return None, "No task matches that. Which one did you mean?"
    return None, "Which task? Say its number or a word from it."


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list").lower()
    if not gauth.libraries_installed():
        return outcome.failed("todo", "the Google libraries are not installed; run "
                              "pip install google-api-python-client google-auth-oauthlib")
    try:
        svc = gauth.service("tasks", "v1")
        if svc is None:
            return outcome.failed("todo", gauth.SETUP_STEPS)

        if action == "add":
            title = (parameters.get("title") or "").strip()
            if not title:
                return outcome.ask("todo_add", "What should I add?")
            body = {"title": title}
            if parameters.get("notes"):
                body["notes"] = parameters["notes"]
            if parameters.get("due"):
                try:
                    d = dt.date.fromisoformat(str(parameters["due"]).strip()[:10])
                except ValueError:
                    return outcome.ask("todo_add", "When is it due? I need a date.")
                body["due"] = f"{d.isoformat()}T00:00:00.000Z"   # Tasks stores the date only
            made = svc.tasks().insert(tasklist=LIST_ID, body=body).execute()
            if not made.get("id"):
                return outcome.unverified("todo_add", "Google did not return the new task")
            tasks = _refresh(svc, player)
            return outcome.done("todo_add", title=title, open_tasks=len(tasks))

        if action == "list":
            tasks = _refresh(svc, player)
            if not tasks:
                return outcome.done("todo_list", count=0)
            return outcome.done("todo_list", count=len(tasks)) + "\n" + \
                outcome.untrusted("todo", _render(tasks))

        if action in ("complete", "remove"):
            task, question = _find(svc, parameters)
            if task is None:
                return outcome.ask(f"todo_{action}", question)
            if action == "complete":
                svc.tasks().patch(tasklist=LIST_ID, task=task["id"],
                                  body={"status": "completed"}).execute()
            else:
                svc.tasks().delete(tasklist=LIST_ID, task=task["id"]).execute()
            tasks = _refresh(svc, player)
            return outcome.done(f"todo_{action}", task=task["title"], open_tasks=len(tasks),
                                undo="completed tasks can be restored in Google Tasks"
                                if action == "complete" else None)

        if action == "clear_completed":
            svc.tasks().clear(tasklist=LIST_ID).execute()
            return outcome.done("todo_clear_completed")

        return outcome.failed("todo", f"unknown action {action}")
    except Exception as e:  # HttpError, network, a revoked token — never raise
        return outcome.failed(f"todo_{action}", f"Google Tasks error: {e}")
