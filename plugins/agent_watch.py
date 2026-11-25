"""
plugins/agent_watch.py — agents that start themselves when something needs doing.

    PRICE WATCH   "Tell me when the RTX 5080 drops below 800 pounds"
                  Checked every 12 hours (by default) with a web search. When the price
                  hits your target: an alert on screen and on your phone, and an offer
                  to run the deal hunter for a full where-to-buy report.

    DEADLINE PREP Every morning it looks at the next few days of your calendar for
                  exams, tests, quizzes, deadlines, interviews and presentations. For each
                  new one it either ASKS ("You have a chemistry test on Friday — want a
                  study pack?") or just DOES it (study coach for exams, a research brief
                  for interviews and presentations), as you choose in settings.

    DAILY DIGEST  At the time you set, the daily digest agent writes your news digest.

Only the PC with "run proactive agents here" on does any of this (the desktop by
default), so two PCs never do the same work twice. Results arrive the usual way:
announced when ready, in the Tasks panel and in the reports folder.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time

from core import addons, outcome
from memory.config_manager import CONFIG_DIR, get_plugin_config

NAMESPACE = "agent_watch"
STATE_FILE = CONFIG_DIR / "agent_watch.json"
DEADLINE_WORDS = re.compile(r"\b(exam|test|quiz|midterm|final|assessment|mock|deadline|due|"
                            r"submission|interview|presentation|viva|essay)\b", re.I)
_lock = threading.Lock()


def _cfg() -> dict:
    c = get_plugin_config(NAMESPACE)
    try:
        import psutil
        laptop = psutil.sensors_battery() is not None
    except Exception:
        laptop = False
    return {"run_here": c.get("run_here", not laptop),
            "prep": str(c.get("prep") or "ask"),
            "prep_days": int(str(c.get("prep_days") or "3")),
            "digest_time": str(c.get("digest_time") or "").strip(),
            "price_hours": int(str(c.get("price_hours") or "12"))}


def _load() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(state: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1), encoding="utf-8")


def _start_agent(task: str, agent: str) -> str:
    from core.tasks import desktop
    eng = desktop.ensure(addons.player())
    t = eng.start(task, agent=agent, deliver="voice", title=task[:60])
    return t["id"]


def _alert(title: str, text: str, instruction: str, urgent: bool = False) -> None:
    addons.show(title, text)
    addons.say(instruction)
    try:
        from plugins import phone_alerts
        if phone_alerts.should_push(urgent):
            phone_alerts.push("agent", title, text, urgent=urgent)
    except Exception:
        pass


# ── price watches ─────────────────────────────────────────────────────────────

def check_price(w: dict) -> dict | None:
    from core import gemini
    data = gemini.as_json(
        f"Find the lowest current price, new, in stock, at a reputable shop, for: {w['product']}. "
        f"Prices in {w.get('currency') or 'the local currency'}. Reply with JSON only: "
        '{"price": number or null, "currency": str, "shop": str, "url": str}', tier=gemini.SEARCH,
        timeout_ms=60000)
    if isinstance(data, dict) and isinstance(data.get("price"), (int, float)):
        return data
    return None


def _price_round(state: dict) -> list[str]:
    out, hours = [], _cfg()["price_hours"]
    for w in state.get("prices", []):
        if time.time() - w.get("checked", 0) < hours * 3600:
            continue
        w["checked"] = time.time()
        found = check_price(w)
        if not found:
            continue
        w["last"] = found["price"]
        out.append(f"{w['product']}: {found['price']}")
        if found["price"] <= float(w["target"]) and not w.get("hit"):
            w["hit"] = True
            text = (f"{w['product']} is {found['price']} {found.get('currency', '')} at "
                    f"{found.get('shop', '?')} (your target: {w['target']}).\n{found.get('url', '')}")
            _alert("PRICE DROP", text,
                   "[SYSTEM] A price the user is watching has dropped to their target. In one "
                   "sentence tell them, and offer to run the deal_hunter agent for a full "
                   "where-to-buy report (background_tasks start, agent deal_hunter):\n"
                   + outcome.untrusted("web", text), urgent=True)
        elif found["price"] > float(w["target"]):
            w["hit"] = False   # re-arm once it rises again
    return out


# ── deadline prep ─────────────────────────────────────────────────────────────

def _prep_task(title: str, when: str) -> tuple[str, str]:
    if re.search(r"\b(interview|presentation|viva)\b", title, re.I):
        return (f"Prepare me for '{title}' on {when}: research what it is about, the likely "
                f"questions or points to cover, and give me a short prep sheet.", "general")
    return (f"Make a study pack for '{title}' on {when}. Use my knowledge folder notes on the "
            f"subject if there are any.", "study_coach")


def _deadline_round(state: dict) -> list[str]:
    if _cfg()["prep"] == "off":
        return []
    from plugins import _google_auth as gauth
    svc = gauth.service("calendar", "v3") if gauth.libraries_installed() else None
    if svc is None:
        return []
    cfg = _cfg()
    now = dt.datetime.now().astimezone()
    items = svc.events().list(calendarId="primary", singleEvents=True, orderBy="startTime",
                              timeMin=now.isoformat(),
                              timeMax=(now + dt.timedelta(days=cfg["prep_days"])).isoformat(),
                              maxResults=50).execute().get("items", [])
    handled = state.setdefault("prepped", {})
    out = []
    for ev in items:
        title = ev.get("summary") or ""
        if not DEADLINE_WORDS.search(title) or ev["id"] in handled:
            continue
        handled[ev["id"]] = time.time()
        start = ev.get("start", {})
        when = (start.get("dateTime") or start.get("date") or "")[:16].replace("T", " ")
        task, agent = _prep_task(title, when)
        if cfg["prep"] == "auto":
            tid = _start_agent(task, agent)
            out.append(f"started {agent} for {title} ({tid})")
            _alert("PREPARING", f"{title} — {when}\nStarted the {agent.replace('_', ' ')}.",
                   "[SYSTEM] In one sentence tell the user you've started preparing for this "
                   "and will say when it is ready:\n" + outcome.untrusted("calendar", f"{title} {when}"))
        else:
            out.append(f"offered prep for {title}")
            _alert("COMING UP SOON", f"{title} — {when}",
                   "[SYSTEM] The user has this coming up. In one sentence mention it and offer "
                   f"to prepare (if they say yes, use background_tasks start with agent {agent} "
                   f"and task: {task}):\n" + outcome.untrusted("calendar", f"{title} {when}"))
    cutoff = time.time() - 14 * 86400
    state["prepped"] = {k: v for k, v in handled.items() if v > cutoff}
    return out


# ── daily digest ──────────────────────────────────────────────────────────────

def _digest_round(state: dict) -> list[str]:
    at = _cfg()["digest_time"]
    if not re.match(r"^\d{1,2}:\d{2}$", at):
        return []
    today = dt.date.today().isoformat()
    hh, mm = map(int, at.split(":"))
    if state.get("digest_day") == today or dt.datetime.now().time() < dt.time(hh, mm):
        return []
    state["digest_day"] = today
    _start_agent("Write my daily digest for today.", "daily_digest")
    return ["started daily digest"]


# ── loop and tool ─────────────────────────────────────────────────────────────

def check_once(force: bool = False) -> list[str]:
    if not force and not _cfg()["run_here"]:
        return []
    with _lock:
        state = _load()
        results = []
        for fn in (_digest_round, _price_round, _deadline_round):
            try:
                results += fn(state)
            except Exception as e:
                results.append(f"{fn.__name__} skipped: {e}")
        _save(state)
    return results


def _loop() -> None:
    time.sleep(90)
    while True:
        check_once()
        time.sleep(30 * 60)


PLUGIN = {
    "name": "agent_watch",
    "description": (
        "Proactive background agents: watch a product's price and alert when it drops to a "
        "target; list or remove watches; prepare for upcoming exams, tests, deadlines and "
        "interviews found in the calendar. Use for 'tell me when X drops below Y', 'what "
        "prices are you watching', 'prepare me for my upcoming exams'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "enum": ["watch_price", "list", "remove", "check_now", "prep_now"]},
            "product": {"type": "STRING", "description": "For watch_price: exact product"},
            "target_price": {"type": "NUMBER", "description": "For watch_price: alert at or below this"},
            "currency": {"type": "STRING", "description": "For watch_price: e.g. GBP, USD, INR"},
            "number": {"type": "INTEGER", "description": "For remove: number in the list"},
        },
        "required": ["action"],
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "extra",
    "brief": "Price watches and automatic exam/deadline prep.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "PROACTIVE AGENTS",
    "fields": [
        {"key": "run_here", "label": "Run proactive agents on this PC (only one PC should)",
         "type": "toggle", "default": True},
        {"key": "prep", "label": "Before exams, deadlines and interviews", "type": "choice",
         "options": ["ask", "auto", "off"], "default": "ask"},
        {"key": "prep_days", "label": "Look this many days ahead", "type": "choice",
         "options": ["2", "3", "5", "7"], "default": "3"},
        {"key": "price_hours", "label": "Check watched prices every (hours)", "type": "choice",
         "options": ["6", "12", "24"], "default": "12"},
        {"key": "digest_time", "label": "Daily digest at (HH:MM, empty = off)", "type": "text",
         "placeholder": "07:30"},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    try:
        with _lock:
            state = _load()
            prices = state.setdefault("prices", [])
            if action == "watch_price":
                product = str(parameters.get("product") or "").strip()
                if not product or parameters.get("target_price") is None:
                    return outcome.ask("price_watch", "Which product, and at what price should I tell you?")
                prices.append({"product": product, "target": float(parameters["target_price"]),
                               "currency": str(parameters.get("currency") or ""), "checked": 0})
                _save(state)
                return outcome.done("price_watch", product=product, target=parameters["target_price"],
                                    every_hours=_cfg()["price_hours"],
                                    note="first check runs within the next half hour")
            if action == "remove":
                n = int(parameters.get("number") or 0)
                if not 1 <= n <= len(prices):
                    return outcome.ask("price_unwatch", "Which watch? Say its number.")
                gone = prices.pop(n - 1)
                _save(state)
                return outcome.done("price_unwatch", product=gone["product"])
        if action == "list":
            text = "\n".join(f"{i}. {w['product']} — target {w['target']} {w.get('currency', '')}"
                             f"{', last ' + str(w['last']) if w.get('last') else ''}"
                             for i, w in enumerate(prices, 1)) or "No price watches."
            return outcome.done("price_list", count=len(prices)) + "\n" + outcome.untrusted("watch", text)
        if action == "prep_now":
            if _cfg()["prep"] == "off":
                return outcome.failed("prep", "deadline prep is switched off in settings")
            with _lock:
                state = _load()
                state["prepped"] = {}
                res = _deadline_round(state)
                _save(state)
            return outcome.done("prep", found=len(res), results="; ".join(res) or "nothing coming up")
        res = check_once(force=True)
        return outcome.done("agent_check", results="; ".join(res) or "nothing to report")
    except Exception as e:
        return outcome.failed(f"agent_{action}", str(e)[:180])


threading.Thread(target=_loop, name="agent_watch", daemon=True).start()
