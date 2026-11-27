"""
plugins/my_day.py — "Show me my day": everything about today on one panel, like the suit's overview.

Gathers in parallel (a few seconds at most, whatever answers in time): today's calendar, the to-do list,
the weather and when rain comes, study time so far, what Jarvis is working on, and the phone's battery.
Shows it as a TODAY panel and hands Jarvis the summary to say in two or three sentences.
"""
from __future__ import annotations

import datetime as dt
import threading

from core import outcome


def _calendar() -> str:
    from plugins import calendar_control
    return outcome.unwrap(calendar_control.run({"action": "list", "range": "today"}))


def _todos() -> str:
    from plugins import todo_list
    return outcome.unwrap(todo_list.run({"action": "list"}))


def _weather() -> str:
    from core import weather
    place, text = weather.report("", "today")
    return f"{place}\n{text}"


def _study() -> str:
    from plugins import study_timer
    stats = study_timer._stats(1)
    total = sum(stats.values())
    return (", ".join(f"{s} {m:.0f} min" for s, m in stats.items()) + f" (total {total / 60:.1f} h)") if stats else "none yet today"


def _jobs() -> str:
    from plugins import operations
    rows = operations.listing()
    return "\n".join(rows) if rows else "nothing running"


def _phone() -> str:
    from plugins import phone_control
    r = phone_control.phone("status", {}, 6)
    return r.get("text") or "no answer"


PARTS = [("CALENDAR", _calendar), ("TO-DO", _todos), ("WEATHER", _weather), ("STUDY", _study),
         ("JARVIS IS WORKING ON", _jobs), ("PHONE", _phone)]


def gather(timeout: float = 9.0) -> list[tuple[str, str]]:
    got: dict[str, str] = {}

    def one(name, fn):
        try:
            text = (fn() or "").strip()
            got[name] = "\n".join(l for l in text.splitlines() if not l.startswith("status="))[:900]
        except Exception as e:
            got[name] = f"(not available: {str(e)[:60]})"
    threads = [threading.Thread(target=one, args=p, daemon=True) for p in PARTS]
    for t in threads:
        t.start()
    import time as _t
    deadline = _t.time() + timeout                 # one shared deadline, not one per part
    for t in threads:
        t.join(max(0.0, deadline - _t.time()))
    return [(name, got.get(name, "(didn't answer in time)")) for name, _ in PARTS]


PLUGIN = {
    "name": "my_day",
    "description": (
        "Shows the user's whole day on one panel — calendar, to-dos, weather and rain, study time so far, "
        "what Jarvis is working on, the phone's battery — and gives a short summary to say. Use for 'show me my "
        "day', 'what's my day looking like', 'today's overview', 'status report'."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    "tier": "core",
    "brief": "Today's overview panel.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    parts = gather()
    text = "\n\n".join(f"▸ {name}\n{body}" for name, body in parts)
    title = "TODAY — " + dt.datetime.now().strftime("%a %d %b").upper()
    if player:
        try:
            player.show_content(title, text)
        except Exception:
            pass
    return outcome.done("my_day", note="give the gist in two or three sentences: what's next, weather worth "
                                       "knowing, anything urgent; the full panel is on screen") \
        + "\n" + outcome.untrusted("today", text)
