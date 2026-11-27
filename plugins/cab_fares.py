"""
plugins/cab_fares.py — "What's the cheapest cab to Changi Airport?"

    "Cheapest cab to Jewel"                         compare  (Grab, Gojek, TADA and Zig, one after another)
    "Check Grab and Zig for a ride to NUS"          compare  (only those apps)
    "Open the cheapest one" / "open Gojek for it"   open     (the app, on its fares screen, for you to book)

HOW IT WORKS
    None of these apps has a public fare API, so the phone does what you would: Jarvis opens each app,
    types the destination into its "Where to?", picks the first matching place and reads the prices the
    app quotes (android/.../FareCheck.kt). Pickup is wherever the app puts it, normally where the phone
    is. It needs the phone unlocked, the Accessibility switch on and "Open apps and sites when asked".
    It takes about 15–30 seconds an app, and the phone visibly flips between them while it runs.

IT NEVER BOOKS
    The phone side refuses to tap anything that books, orders, requests or pays, and taps nothing at all
    once prices are on screen. "Open" stops on the fares screen; pressing Book is yours.

TRADE-OFFS, SAID PLAINLY
    Reading another app's screen for yourself is what screen readers do and is fine for personal use, but
    the apps' terms forbid automated access in general terms, and a heavy, frequent use could get noticed;
    this checks once when you ask, nothing runs on a schedule. Their screens change with updates, so a
    check can stop working for one app until its words are adjusted: every failure says what was on
    screen so that is quick. Prices are quotes at that moment (surge and promos move them) and each app
    may pick a slightly different place for the same name, so the place each one picked is shown.
"""
from __future__ import annotations

import re
import threading
import time

from core import addons, outcome

APPS = ["Grab", "Gojek", "TADA", "Zig"]

_lock = threading.Lock()
_last: dict = {}            # the latest check: destination, rows, cheapest app


def _phone(action: str, args: dict, timeout: float) -> dict:
    from plugins.phone_control import phone
    return phone(action, args, timeout)


def _phone_ready() -> str | None:
    """Why a check can't start, or None."""
    a = addons.assistant()
    d = getattr(a, "_dashboard", None)
    if d is None:
        return "the phone link isn't running — turn on Remote Control in Jarvis"
    info = d.phone_info() if hasattr(d, "phone_info") else None
    if not info:
        return "no phone is connected — open the Jarvis app on it"
    if "cab_fare" not in (info.get("abilities") or []):
        return "the Jarvis app on the phone is too old for fare checks — install the new build"
    return None


def _pick_apps(text: str) -> list[str]:
    want = [w.strip().lower() for w in (text or "").replace(" and ", ",").split(",") if w.strip()]
    if not want:
        return list(APPS)
    out = []
    for a in APPS:
        if any(w in a.lower() or a.lower() in w or (a == "Zig" and ("cdg" in w or "comfort" in w)) for w in want):
            out.append(a)
    return out or list(APPS)


def money(o: dict) -> str:
    lo, hi = float(o.get("low", 0)), float(o.get("high", 0))
    return f"S${lo:.2f}–{hi:.2f}" if hi > lo else f"S${lo:.2f}"


_SHARED = re.compile(r"share|pool|shared|carpool", re.I)


def summarise(results: dict, shared: bool = False) -> dict:
    """{app: phone answer} -> rows, cheapest and a panel text. Ranks by the low end of each quote.
    Shared rides (GrabShare and the like) are left out unless asked for: a cheaper fare with strangers
    and detours isn't the same ride."""
    rows, problems = [], []
    for app, r in results.items():
        data = (r or {}).get("data") or {}
        opts = [o for o in data.get("options") or [] if isinstance(o, dict) and o.get("low")
                and (shared or not _SHARED.search(str(o.get("product", ""))))]
        if (r or {}).get("ok") and opts:
            best = min(opts, key=lambda o: float(o["low"]))
            rows.append({"app": app, "product": str(best.get("product", ""))[:40], "low": float(best["low"]),
                         "high": float(best.get("high") or best["low"]), "place": str(data.get("place") or "")[:80],
                         "options": len(opts)})
        else:
            why = str((r or {}).get("text") or "no answer")
            if why.lower().startswith(app.lower() + ":"):
                why = why[len(app) + 1:].strip()
            if (r or {}).get("ok") and not opts:
                why = "only shared rides quoted" if data.get("options") else "no fares read"
            problems.append({"app": app, "status": str(data.get("status") or "failed"), "why": why[:160],
                             "screen": str(data.get("screen") or "")[:600]})
    rows.sort(key=lambda x: (x["low"], x["high"]))
    lines = []
    for i, x in enumerate(rows):
        mark = "★ " if i == 0 else "  "
        lines.append(f"{mark}{x['app']:<6} {x['product']:<22} {money(x)}" + (f"   → {x['place']}" if x['place'] else ""))
    for p in problems:
        lines.append(f"  {p['app']:<6} — {p['why']}")
    return {"rows": rows, "problems": problems, "cheapest": rows[0] if rows else None, "text": "\n".join(lines)}


def _compare(destination: str, apps: list[str], shared: bool = False) -> None:
    results: dict = {}
    try:
        for app in apps:
            try:
                results[app] = _phone("cab_fare", {"app": app, "destination": destination}, timeout=75)
            except Exception as e:
                results[app] = {"ok": False, "text": f"{app}: {str(e)[:120]}", "data": {"status": "no_answer"}}
            st = ((results[app] or {}).get("data") or {}).get("status")
            if st in ("locked", "no_access", "no_overlay"):
                break                                   # the same for every app: say it once
        s = summarise(results, shared)
        _last.clear()
        _last.update({"destination": destination, "at": time.time(), **s})
        addons.show(f"CAB FARES — {destination[:40]}", s["text"] or "No fares came back.")
        c = s["cheapest"]
        if c:
            facts = outcome.done("cab_fares", destination=destination, cheapest_app=c["app"], price=money(c),
                                 checked=", ".join(results), failed=", ".join(p["app"] for p in s["problems"]) or "none",
                                 note="prices are quotes right now; offer to open the cheapest app on its fares screen "
                                      "so they can book it (Jarvis never books)")
        else:
            facts = outcome.failed("cab_fares", "no app showed a fare", destination=destination)
        addons.say("The cab fare check has finished. Tell the user in a sentence or two, from this: " + facts
                   + "\n" + outcome.untrusted("ride apps", s["text"][:1500]))
    finally:
        _lock.release()


def _open(app: str, destination: str) -> None:
    try:
        try:
            r = _phone("cab_fare", {"app": app, "destination": destination, "leave_open": True}, timeout=75)
        except Exception as e:
            r = {"ok": False, "text": str(e)[:160]}
        msg = outcome.done("cab_open", app=app, destination=destination,
                           note="it is on the fares screen; the user presses Book themselves") if r.get("ok") else \
            outcome.failed("cab_open", str(r.get("text") or "no answer")[:160], app=app)
        addons.say("Opening the ride app has finished. Tell the user briefly: " + msg)
    finally:
        _lock.release()


PLUGIN = {
    "name": "cab_fares",
    "description": (
        "Finds the cheapest taxi / cab / ride to a place by checking Grab, Gojek, TADA and Zig (CDG) on the user's "
        "phone: compare (destination; optional apps, e.g. 'Grab, Zig') opens each app, enters the destination and "
        "reads the fares it quotes, then reports the cheapest (takes about a minute; the answer follows by itself). "
        "open (app, or empty for the cheapest from the last check) leaves that app on its fares screen so the user "
        "can book. It NEVER books or pays. Use for 'cheapest cab to X', 'how much is a Grab to X', 'compare ride "
        "prices'. Not for directions (phone_control navigate) or flights (flight_finder)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["compare", "open"]},
            "destination": {"type": "STRING", "description": "Where to, as the user said it, e.g. 'Changi Airport T3'"},
            "apps": {"type": "STRING", "description": "For compare: only these, comma separated (Grab, Gojek, TADA, Zig)"},
            "app": {"type": "STRING", "description": "For open: which app; empty = the cheapest from the last check"},
            "shared": {"type": "BOOLEAN", "description": "For compare: include shared rides (GrabShare etc.); "
                                                         "off unless the user asks for them"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Cheapest cab: compares Grab, Gojek, TADA, Zig fares on the phone.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "compare")
    destination = str(parameters.get("destination") or "").strip()[:120]
    try:
        if action == "open" and not destination:
            destination = str(_last.get("destination") or "")
        if not destination:
            return outcome.ask("cab_fares", "Where to?")
        why = _phone_ready()
        if why:
            return outcome.failed("cab_fares", why)
        if action == "open":
            app = str(parameters.get("app") or "").strip()
            if not app:
                c = _last.get("cheapest") if _last.get("destination") == destination else None
                if not c:
                    return outcome.ask("cab_open", "Which app — Grab, Gojek, TADA or Zig?")
                app = c["app"]
            picked = _pick_apps(app)
            if len(picked) != 1:
                return outcome.ask("cab_open", "Which one app — Grab, Gojek, TADA or Zig?")
            if not _lock.acquire(blocking=False):
                return outcome.failed("cab_open", "a fare check is still running on the phone")
            threading.Thread(target=_open, args=(picked[0], destination), daemon=True, name="cab-open").start()
            return outcome.started("cab_open", app=picked[0], destination=destination)
        apps = _pick_apps(str(parameters.get("apps") or ""))
        if not _lock.acquire(blocking=False):
            return outcome.failed("cab_fares", "a fare check is already running on the phone")
        threading.Thread(target=_compare, args=(destination, apps, bool(parameters.get("shared"))), daemon=True, name="cab-fares").start()
        return outcome.started("cab_fares", destination=destination, apps=", ".join(apps),
                               note=f"about {20 * len(apps)} seconds; the phone will switch between the apps, "
                                    "and it needs to stay unlocked")
    except Exception as e:
        return outcome.failed("cab_fares", str(e)[:160])
