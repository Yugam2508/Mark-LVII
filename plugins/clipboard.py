"""
plugins/clipboard.py — "What did I copy earlier?" / "copy that link again" / "paste the address I copied".

Reads core/clip_history.py (memory only, the last 40 things copied). `copy` puts an earlier one back on the
clipboard; `paste` also presses Ctrl+V into the app in front; `clear` forgets them all.
"""
from __future__ import annotations

import time

from core import clip_history, outcome


def _age(at: float) -> str:
    s = time.time() - at
    return "just now" if s < 60 else f"{int(s // 60)} min ago" if s < 3600 else f"{int(s // 3600)} h ago"


def _pick(p: dict):
    items = clip_history.recent(40)
    if p.get("number"):
        n = int(p["number"])
        return items[n - 1] if 1 <= n <= len(items) else None
    if p.get("query"):
        hits = clip_history.find(str(p["query"]))
        return hits[0] if hits else None
    return items[1] if len(items) > 1 else (items[0] if items else None)   # "the one before"


PLUGIN = {
    "name": "clipboard",
    "description": (
        "The user's clipboard history on this PC (the last 40 things copied, kept in memory only): list them "
        "('what did I copy?'), find one ('the link I copied', 'the address'), copy an earlier one back to the "
        "clipboard, or paste it into the app in front (number = its place in the list, or query = words in it). "
        "clear forgets them all."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["list", "copy", "paste", "clear"]},
            "number": {"type": "INTEGER", "description": "Its number in the list (1 = newest)"},
            "query": {"type": "STRING", "description": "Words in it, or 'link'"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Clipboard history: list / copy back / paste / clear.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    try:
        if action == "clear":
            clip_history.clear()
            return outcome.done("clipboard_clear")
        if action == "list":
            items = clip_history.find(str(parameters["query"])) if parameters.get("query") else clip_history.recent(10)
            if not items:
                return outcome.done("clipboard", count=0)
            text = "\n".join(f"{i}. {it['text'][:140].replace(chr(10), ' ')} ({_age(it['at'])})"
                             for i, it in enumerate(items, 1))
            if player:
                try:
                    player.show_content("CLIPBOARD", text)
                except Exception:
                    pass
            return outcome.done("clipboard", count=len(items)) + "\n" + outcome.untrusted("clipboard", text)
        it = _pick(parameters)
        if it is None:
            return outcome.failed(f"clipboard_{action}", "nothing like that was copied")
        import pyperclip
        pyperclip.copy(it["text"])
        if action == "paste":
            from actions.send_message import pyautogui
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "v")
            return outcome.done("clipboard_paste", chars=len(it["text"]))
        return outcome.done("clipboard_copy", chars=len(it["text"]), note="it's on the clipboard now")
    except Exception as e:
        return outcome.failed(f"clipboard_{action}", str(e)[:160])
