"""
plugins/money_tracker.py — "I spent 12 on lunch" and where the money went.

    "I spent 12 pounds on lunch"                 action=add amount=12 what=lunch
    "Paid 9.99 for Spotify"                      action=add amount=9.99 what=Spotify
    "How much did I spend this week/month?"      action=summary period=week|month|last_month
    "Set my food budget to 150 a month"          action=set_budget category=food amount=150
    "How am I doing on my budgets?"              action=budgets
    "Undo that" (the last expense)               action=undo

WHERE IT IS KEPT
    A Google Sheet called "JARVIS Money" in your Drive (created on first use): open it
    in the Google Sheets app on your phone, edit rows by hand, and both PCs add to the
    same sheet. Needs the Google Sheets API enabled in your Google Cloud project and the
    Drive permission (CONNECT GOOGLE once more if you haven't since Drive was added).
    Without Google it uses "JARVIS Money.csv" in your OneDrive knowledge folder.

Categories are guessed from what you say (lunch -> food, Uber -> transport, Steam ->
games…) and can be given explicitly. After each expense you hear if a category is
near or over its monthly budget.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import platform
import re
import threading

from core import outcome
from memory.config_manager import get_plugin_setting, save_plugin_config

NAMESPACE = "money_tracker"
SHEET_NAME = "JARVIS Money"
HEADER = ["Date", "Amount", "Currency", "Category", "What", "Device"]
CATEGORIES = {
    "food": r"lunch|dinner|breakfast|coffee|snack|groceries|grocery|food|takeaway|restaurant|pizza|burger|"
            r"mcdonald|kfc|subway|starbucks|cafe|meal|tesco|sainsbury|aldi|lidl|swiggy|zomato",
    "transport": r"uber|bolt|taxi|cab|bus|train|tube|metro|fuel|petrol|diesel|parking|ola|travel card|oyster",
    "games": r"steam|game|valorant|riot|epic|xbox|playstation|psn|nintendo|vp\b|battle pass|skins?",
    "subscriptions": r"spotify|netflix|youtube premium|prime|disney|subscription|icloud|chatgpt|claude",
    "shopping": r"amazon|clothes|shoes|hoodie|shirt|jeans|shopping|flipkart|ebay|mouse|keyboard|headset",
    "bills": r"rent|electric|gas bill|water bill|phone bill|internet|wifi|bill",
    "fun": r"cinema|movie|concert|ticket|bowling|bar|drinks|party",
    "education": r"book|course|textbook|stationery|tuition|exam fee",
}
_lock = threading.Lock()


def _currency() -> str:
    return str(get_plugin_setting(NAMESPACE, "currency", "") or "GBP").strip().upper()


def guess_category(what: str) -> str:
    w = (what or "").lower()
    for cat, pat in CATEGORIES.items():
        if re.search(pat, w):
            return cat
    return "other"


def budgets() -> dict[str, float]:
    raw = str(get_plugin_setting(NAMESPACE, "budgets", "") or "")
    out = {}
    for part in raw.split(","):
        k, sep, v = part.partition("=")
        try:
            if sep:
                out[k.strip().lower()] = float(v.strip())
        except ValueError:
            pass
    return out


# ── storage: Google Sheet, else CSV in the knowledge folder ───────────────────

def _sheets():
    from plugins import _google_auth as gauth
    if not gauth.libraries_installed() or not gauth.has_access("sheets"):
        return None
    return gauth.service("sheets", "v4")


def _sheet_id(create: bool = True) -> str | None:
    sid = str(get_plugin_setting(NAMESPACE, "sheet_id", "") or "")
    if sid:
        return sid
    from plugins import _google_auth as gauth
    drive = gauth.service("drive", "v3")
    found = drive.files().list(q=f"name = '{SHEET_NAME}' and mimeType = "
                                 "'application/vnd.google-apps.spreadsheet' and trashed = false",
                               fields="files(id)", pageSize=1).execute().get("files", [])
    if found:
        sid = found[0]["id"]
    elif create:
        sheet = _sheets().spreadsheets().create(body={
            "properties": {"title": SHEET_NAME},
            "sheets": [{"properties": {"title": "Expenses"}}]}).execute()
        sid = sheet["spreadsheetId"]
        _sheets().spreadsheets().values().update(
            spreadsheetId=sid, range="Expenses!A1", valueInputOption="RAW",
            body={"values": [HEADER]}).execute()
    else:
        return None
    save_plugin_config(NAMESPACE, {"sheet_id": sid})
    return sid


def _csv_path():
    from plugins import knowledge_base
    folder = knowledge_base._folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{SHEET_NAME}.csv"


def read_rows() -> list[dict]:
    svc = _sheets()
    if svc is not None:
        sid = _sheet_id(create=False)
        if not sid:
            return []
        vals = svc.spreadsheets().values().get(spreadsheetId=sid, range="Expenses!A2:F").execute().get("values", [])
    else:
        path = _csv_path()
        if not path.exists():
            return []
        vals = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))[1:]
    rows = []
    for v in vals:
        v = (v + [""] * 6)[:6]
        try:
            rows.append({"date": v[0], "amount": float(str(v[1]).replace(",", "")), "currency": v[2],
                         "category": v[3] or "other", "what": v[4], "device": v[5]})
        except ValueError:
            continue
    return rows


def append_row(row: list) -> str:
    svc = _sheets()
    if svc is not None:
        svc.spreadsheets().values().append(spreadsheetId=_sheet_id(), range="Expenses!A1",
                                           valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
                                           body={"values": [row]}).execute()
        return "Google Sheet"
    path = _csv_path()
    with _lock:
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(HEADER)
            w.writerow(row)
    return "CSV in the knowledge folder"


def delete_last() -> dict | None:
    rows = read_rows()
    if not rows:
        return None
    svc = _sheets()
    if svc is not None:
        sid = _sheet_id()
        meta = svc.spreadsheets().get(spreadsheetId=sid, fields="sheets(properties(sheetId,title))").execute()
        gid = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == "Expenses")
        n = len(rows) + 1   # header is row 1 (index 0); last data row index = len(rows)
        svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [{"deleteDimension": {
            "range": {"sheetId": gid, "dimension": "ROWS", "startIndex": n - 1, "endIndex": n}}}]}).execute()
    else:
        path = _csv_path()
        lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    return rows[-1]


# ── maths ─────────────────────────────────────────────────────────────────────

def _period(name: str) -> tuple[dt.date, dt.date, str]:
    today = dt.date.today()
    if name == "week":
        start = today - dt.timedelta(days=today.weekday())
        return start, today, "this week"
    if name == "last_month":
        end = today.replace(day=1) - dt.timedelta(days=1)
        return end.replace(day=1), end, end.strftime("%B")
    if name == "today":
        return today, today, "today"
    return today.replace(day=1), today, "this month"


def totals(period: str) -> tuple[dict[str, float], float, str]:
    start, end, label = _period(period)
    by_cat: dict[str, float] = {}
    for r in read_rows():
        try:
            d = dt.date.fromisoformat(r["date"][:10])
        except ValueError:
            continue
        if start <= d <= end:
            by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]
    return dict(sorted(by_cat.items(), key=lambda kv: -kv[1])), sum(by_cat.values()), label


def _budget_note(category: str) -> str | None:
    limit = budgets().get(category)
    if not limit:
        return None
    spent = totals("month")[0].get(category, 0)
    if spent > limit:
        return f"over the {category} budget: {spent:.2f} of {limit:.0f}"
    if spent >= 0.8 * limit:
        return f"{spent / limit:.0%} of the {category} budget used ({spent:.2f} of {limit:.0f})"
    return None


# ── tool ──────────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "money_tracker",
    "description": (
        "Tracks the user's spending: log an expense ('I spent 12 on lunch'), totals for "
        "today/this week/this month/last month by category, set a monthly budget for a "
        "category, check budgets, undo the last expense."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["add", "summary", "set_budget", "budgets", "undo"]},
            "amount": {"type": "NUMBER"},
            "what": {"type": "STRING", "description": "For add: what it was for"},
            "category": {"type": "STRING", "description": "Optional; guessed from 'what' if empty"},
            "date": {"type": "STRING", "description": "For add: YYYY-MM-DD if not today"},
            "period": {"type": "STRING", "enum": ["today", "week", "month", "last_month"]},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Expenses: add / summary / budgets / undo.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "MONEY",
    "fields": [
        {"key": "currency", "label": "Currency", "type": "text", "placeholder": "GBP"},
        {"key": "budgets", "label": "Monthly budgets (category=amount, comma-separated)",
         "type": "text", "placeholder": "food=150, games=40, transport=60, shopping=80"},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "summary")
    try:
        if action == "add":
            if parameters.get("amount") is None:
                return outcome.ask("money_add", "How much was it?")
            amount = round(float(parameters["amount"]), 2)
            what = str(parameters.get("what") or "").strip()
            cat = str(parameters.get("category") or "").strip().lower() or guess_category(what)
            date = str(parameters.get("date") or dt.date.today().isoformat())[:10]
            where = append_row([date, amount, _currency(), cat, what, platform.node()])
            return outcome.done("money_add", amount=amount, currency=_currency(), category=cat,
                                saved_in=where, budget=_budget_note(cat))
        if action == "undo":
            gone = delete_last()
            return outcome.done("money_undo", removed=f"{gone['amount']} {gone['what']}") if gone \
                else outcome.done("money_undo", note="nothing to undo")
        if action == "set_budget":
            cat = str(parameters.get("category") or "").strip().lower()
            if not cat or parameters.get("amount") is None:
                return outcome.ask("money_budget", "Which category, and how much a month?")
            b = budgets()
            b[cat] = float(parameters["amount"])
            save_plugin_config(NAMESPACE, {"budgets": ", ".join(f"{k}={v:g}" for k, v in b.items())})
            return outcome.done("money_budget", category=cat, monthly=b[cat])
        if action == "budgets":
            spent = totals("month")[0]
            lines = [f"{c}: {spent.get(c, 0):.2f} of {lim:.0f} ({spent.get(c, 0) / lim:.0%})"
                     for c, lim in budgets().items()]
            if not lines:
                return outcome.done("money_budgets", note="no budgets set yet")
            if player:
                player.show_content("BUDGETS — THIS MONTH", "\n".join(lines))
            return outcome.done("money_budgets") + "\n" + outcome.untrusted("money", "\n".join(lines))
        by_cat, total, label = totals(str(parameters.get("period") or "month"))
        text = "\n".join(f"{c}: {v:.2f}" for c, v in by_cat.items()) or "Nothing logged."
        if player:
            player.show_content(f"SPENDING — {label.upper()}", text + f"\n\nTotal: {total:.2f} {_currency()}")
        return outcome.done("money_summary", period=label, total=round(total, 2), currency=_currency()) + \
            "\n" + outcome.untrusted("money", text)
    except Exception as e:
        msg = str(e)
        if "has not been used" in msg or "is disabled" in msg:
            msg = "the Google Sheets API is not enabled in your Google Cloud project (APIs & Services → Library)"
        return outcome.failed(f"money_{action}", msg[:180])
