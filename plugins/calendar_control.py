"""
plugins/calendar_control.py — read and change your Google Calendar by voice.

    "What's on my calendar today?"            action=list   range=today
    "Anything on Friday?"                     action=list   range=2026-11-27
    "When is my dentist appointment?"         action=search query=dentist
    "What's next?"                            action=next
    "Add gym tomorrow at 6pm for an hour"     action=create title=Gym start="tomorrow 18:00"
    "Delete the second one"                   action=delete event_number=2

Sign-in is shared with gmail_control — see plugins/_google_auth.py.
Deleting goes through the on-screen confirmation (core/confirm.py); creating
does not, because a new event is one sentence away from being removed again.
"""
from __future__ import annotations

import datetime as dt
import re
import threading

from core import confirm, outcome
from plugins import _google_auth as gauth

PLUGIN_SETTINGS = gauth.PLUGIN_SETTINGS

PLUGIN = {
    "name": "calendar_control",
    "description": (
        "Reads and edits the user's Google Calendar. Use for anything about their "
        "schedule, meetings, appointments or events: what is on today/tomorrow/this "
        "week or on a date, finding an event, what is next, adding an event, or "
        "deleting one. For timed alerts that are not calendar events use `reminder` "
        "instead. Dates and times are the user's local time."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["list", "search", "next", "create", "delete"],
                "description": "list = events in a range; search = find by words; "
                               "next = the next upcoming event; create; delete",
            },
            "range": {
                "type": "STRING",
                "description": "For list: today, tomorrow, this_week, next_7_days, "
                               "or a date YYYY-MM-DD. Default today.",
            },
            "query": {
                "type": "STRING",
                "description": "For search, or for delete when no event_number: words in the event title",
            },
            "title": {"type": "STRING", "description": "For create: the event title"},
            "start": {
                "type": "STRING",
                "description": "For create: 'YYYY-MM-DD HH:MM' (24h), 'YYYY-MM-DD' for an "
                               "all-day event, or 'today HH:MM' / 'tomorrow HH:MM'",
            },
            "duration_minutes": {"type": "INTEGER", "description": "For create: length, default 60"},
            "location": {"type": "STRING", "description": "For create: optional place"},
            "description": {"type": "STRING", "description": "For create: optional notes"},
            "event_number": {
                "type": "INTEGER",
                "description": "For delete: the number of the event in the list you last read out",
            },
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Google Calendar: list/search/next/create/delete events.",
}

# The events read out last, so "delete the second one" means something.
_last: list[dict] = []
_last_lock = threading.Lock()


# ── time helpers ──────────────────────────────────────────────────────────────

def _local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _day_start(d: dt.date) -> dt.datetime:
    return dt.datetime.combine(d, dt.time.min).astimezone()


def _range(spec: str) -> tuple[dt.datetime, dt.datetime, str] | None:
    """(start, end, spoken label) for a list range, or None if not understood."""
    spec = (spec or "today").strip().lower().replace(" ", "_")
    today = _local_now().date()
    if spec == "today":
        return _day_start(today), _day_start(today + dt.timedelta(days=1)), "today"
    if spec == "tomorrow":
        t = today + dt.timedelta(days=1)
        return _day_start(t), _day_start(t + dt.timedelta(days=1)), "tomorrow"
    if spec in ("this_week", "week"):
        end = today + dt.timedelta(days=7 - today.weekday())  # through Sunday
        return _local_now(), _day_start(end), "this week"
    if spec in ("next_7_days", "week_ahead", "upcoming"):
        return _local_now(), _day_start(today + dt.timedelta(days=7)), "the next 7 days"
    try:
        d = dt.date.fromisoformat(spec)
    except ValueError:
        return None
    return _day_start(d), _day_start(d + dt.timedelta(days=1)), d.strftime("%A %d %B")


def _parse_start(text: str) -> tuple[dt.datetime | dt.date, bool] | None:
    """(when, all_day) from 'YYYY-MM-DD HH:MM', 'YYYY-MM-DD', 'today 18:00', ..."""
    text = re.sub(r"^(\d{4}-\d{2}-\d{2})t", r"\1 ", (text or "").strip().lower())
    text = re.sub(r"\s+", " ", text)
    today = _local_now().date()
    words = {"today": today, "tomorrow": today + dt.timedelta(days=1)}
    m = re.match(r"^(today|tomorrow|\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2})[:.](\d{2}))?$", text)
    if not m:
        return None
    day_word, hh, mm = m.groups()
    try:
        day = words.get(day_word) or dt.date.fromisoformat(day_word)
        if hh is None:
            return day, True
        return dt.datetime.combine(day, dt.time(int(hh), int(mm))).astimezone(), False
    except ValueError:
        return None


def _event_when(ev: dict) -> str:
    start = ev.get("start", {})
    if "dateTime" in start:
        t = dt.datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone()
        return t.strftime("%a %d %b %H:%M")
    if "date" in start:
        return dt.date.fromisoformat(start["date"]).strftime("%a %d %b") + " (all day)"
    return "?"


def _describe(events: list[dict]) -> str:
    lines = []
    for i, ev in enumerate(events, 1):
        line = f"{i}. {_event_when(ev)} — {ev.get('summary') or '(no title)'}"
        if ev.get("location"):
            line += f" @ {ev['location']}"
        lines.append(line)
    return "\n".join(lines)


def _remember(events: list[dict]) -> None:
    with _last_lock:
        _last[:] = [{"id": e["id"], "summary": e.get("summary", ""),
                     "when": _event_when(e)} for e in events]


def _show(player, title: str, text: str) -> None:
    if player:
        try:
            player.show_content(title, text)
        except Exception:
            pass


def _fetch(svc, **kw) -> list[dict]:
    resp = svc.events().list(calendarId="primary", singleEvents=True,
                             orderBy="startTime", maxResults=25, **kw).execute()
    return [e for e in resp.get("items", []) if e.get("status") != "cancelled"]


def _listing(action: str, events: list[dict], label: str, player) -> str:
    _remember(events)
    if not events:
        _show(player, "CALENDAR", f"Nothing on {label}.")
        return outcome.done(action, range=label, count=0)
    text = _describe(events)
    _show(player, f"CALENDAR — {label.upper()}", text)
    # Event titles can be written by whoever invited you, so they are data.
    return outcome.done(action, range=label, count=len(events)) + "\n" + \
        outcome.untrusted("calendar", text)


# ── actions ───────────────────────────────────────────────────────────────────

def _list(svc, p, player) -> str:
    r = _range(p.get("range") or "today")
    if r is None:
        return outcome.failed("calendar_list", "range not understood; use today, tomorrow, "
                              "this_week, next_7_days or YYYY-MM-DD", range=p.get("range"))
    start, end, label = r
    events = _fetch(svc, timeMin=start.isoformat(), timeMax=end.isoformat())
    return _listing("calendar_list", events, label, player)


def _search(svc, p, player) -> str:
    q = (p.get("query") or "").strip()
    if not q:
        return outcome.ask("calendar_search", "What should I look for in the calendar?")
    now = _local_now()
    events = _fetch(svc, q=q, timeMin=(now - dt.timedelta(days=30)).isoformat(),
                    timeMax=(now + dt.timedelta(days=365)).isoformat())
    return _listing("calendar_search", events, f"'{q}'", player)


def _next(svc, p, player) -> str:
    events = _fetch(svc, timeMin=_local_now().isoformat())[:1]
    return _listing("calendar_next", events, "next", player)


def _create(svc, p, player) -> str:
    title = (p.get("title") or "").strip()
    if not title:
        return outcome.ask("calendar_create", "What should the event be called?")
    parsed = _parse_start(p.get("start") or "")
    if parsed is None:
        return outcome.ask("calendar_create", "When should it start? I need a day and a time.",
                           start=p.get("start"))
    when, all_day = parsed
    body: dict = {"summary": title}
    if p.get("location"):
        body["location"] = p["location"]
    if p.get("description"):
        body["description"] = p["description"]
    if all_day:
        body["start"] = {"date": when.isoformat()}
        body["end"] = {"date": (when + dt.timedelta(days=1)).isoformat()}
    else:
        minutes = int(p.get("duration_minutes") or 60)
        if minutes <= 0:
            minutes = 60
        body["start"] = {"dateTime": when.isoformat()}
        body["end"] = {"dateTime": (when + dt.timedelta(minutes=minutes)).isoformat()}

    ev = svc.events().insert(calendarId="primary", body=body).execute()
    if not ev.get("id"):
        return outcome.unverified("calendar_create", "Google did not return the new event",
                                  title=title)
    _remember([ev])
    _show(player, "CALENDAR — ADDED", _describe([ev]))
    return outcome.done("calendar_create", title=title, when=_event_when(ev),
                        undo="say 'delete it' to remove it")


def _delete(svc, p, player) -> str:
    with _last_lock:
        last = list(_last)
    target = None
    n = p.get("event_number")
    if n:
        if 1 <= int(n) <= len(last):
            target = last[int(n) - 1]
        else:
            return outcome.failed("calendar_delete", "there is no event with that number in "
                                  "the last list; list the calendar first", event_number=n)
    elif len(last) == 1:
        target = last[0]
    elif p.get("query"):
        q = p["query"].lower()
        hits = [e for e in last if q in e["summary"].lower()]
        if len(hits) == 1:
            target = hits[0]
        elif not hits:
            return outcome.failed("calendar_delete", "no event in the last list matches; "
                                  "search for it first", query=p["query"])
    if target is None:
        return outcome.ask("calendar_delete", "Which event should I delete? Tell me its number.")

    def really_delete() -> str:
        s = gauth.service("calendar", "v3")
        if s is None:
            return gauth.SETUP_STEPS
        s.events().delete(calendarId="primary", eventId=target["id"]).execute()
        return f"Deleted '{target['summary']}'."

    # The title is shown to the person on the banner, but kept out of the sentence
    # the model reads back: an invite's title is written by whoever sent it.
    return confirm.request(key=f"calendar_delete:{target['id']}",
                           title="Delete calendar event",
                           detail=f"{target['summary']}\n{target['when']}", run=really_delete)


_ACTIONS = {"list": _list, "search": _search, "next": _next,
            "create": _create, "delete": _delete}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list").lower()
    handler = _ACTIONS.get(action)
    if handler is None:
        return outcome.failed("calendar", f"unknown action {action}")
    if not gauth.libraries_installed():
        return outcome.failed("calendar", "the Google libraries are not installed; run "
                              "pip install google-api-python-client google-auth-oauthlib")
    try:
        svc = gauth.service("calendar", "v3")
        if svc is None:
            return outcome.failed("calendar", gauth.SETUP_STEPS)
        return handler(svc, parameters, player)
    except Exception as e:  # HttpError, network, a revoked token — never raise
        return outcome.failed(f"calendar_{action}", f"Google Calendar error: {e}")
