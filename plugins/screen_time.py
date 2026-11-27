"""
plugins/screen_time.py — "How long have I been on YouTube today?" / "Where did my time go this week?"
"""
from __future__ import annotations

from core import outcome, screen_time


def _fmt(sec: float) -> str:
    m = int(sec // 60)
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


PLUGIN = {
    "name": "screen_time",
    "description": (
        "How the user's time on this PC was spent, by app and by website: today, yesterday or the last week "
        "(days), or one app/site (app, e.g. 'YouTube', 'Valorant', 'VS Code'). Use for 'how long have I been on "
        "YouTube today', 'my screen time this week', 'what did I spend the most time on'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "days": {"type": "INTEGER", "description": "1 = today (default), 7 = the last week"},
            "app": {"type": "STRING", "description": "One app or site to ask about"},
        },
        "required": [],
    },
    "tier": "extra",
    "brief": "Screen time by app/site.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    days = max(1, min(31, int(parameters.get("days") or 1)))
    t = screen_time.totals(days)
    when = "today" if days == 1 else f"the last {days} days"
    if not t:
        return outcome.done("screen_time", when=when, note="nothing tracked yet (it starts counting once Jarvis runs)")
    app = str(parameters.get("app") or "").strip().lower()
    if app:
        hits = {k: v for k, v in t.items() if app in k.lower()}
        total = sum(hits.values())
        return outcome.done("screen_time", app=app, when=when, time=_fmt(total) if total else "none")
    total = sum(t.values())
    lines = [f"{k:<16} {_fmt(v):>10}  {'█' * max(1, int(v / max(t.values()) * 20))}" for k, v in list(t.items())[:12]]
    text = f"Total {_fmt(total)} — {when}\n" + "\n".join(lines)
    if player:
        try:
            player.show_content(f"SCREEN TIME — {when.upper()}", text)
        except Exception:
            pass
    return outcome.done("screen_time", when=when, total=_fmt(total)) + "\n" + outcome.untrusted("screen time", text)
