"""
plugins/phone_control.py — Jarvis uses your phone as a limb.

    "Call Mum"                                   call     (asks you to confirm)
    "Text Aarav that I'm running ten minutes late" text   (shows the message, EDIT / confirm)
    "Find my phone"                              find_phone  (rings at full volume)
    "How's my phone's battery?"                  status
    "What's Aarav's number?"                     contacts

The Jarvis Android app (android/) links to the PC over the same connection the phone dashboard
uses and says what it can do. This plugin sends it an action and waits for the answer.

Calls and texts always wait for your CONFIRM, by voice ("confirm") or on screen, exactly like
email: a contact name that was misheard should never ring someone at 2am. If a name matches
several contacts you are asked which. Contact names and numbers are treated as data.
Requires the phone to be connected (the app open or its link service running).
"""
from __future__ import annotations

import re

from core import addons, outcome

_DIGITS = re.compile(r"^[+()\d\s.-]{5,}$")


def _dashboard():
    a = addons.assistant()
    return getattr(a, "_dashboard", None)


def phone(action: str, args: dict | None = None, timeout: float = 25.0) -> dict:
    d = _dashboard()
    if d is None:
        raise RuntimeError("the phone link isn't running — turn on Remote Control in Jarvis")
    return d.call_phone_sync(action, args or {}, timeout)


def clean_number(text: str) -> str:
    return re.sub(r"[^\d+]", "", text)


def resolve(who: str) -> tuple[str, str, list]:
    """(display name, number, []) when one person; ('', '', matches) when ambiguous or none."""
    who = (who or "").strip()
    if _DIGITS.match(who):
        n = clean_number(who)
        return n, n, []
    r = phone("contacts", {"query": who})
    if not r.get("ok"):
        raise RuntimeError(r.get("text") or "the phone couldn't look up contacts")
    found = [c for c in (r.get("data") or {}).get("contacts", []) if c.get("number")]
    exact = [c for c in found if c.get("name", "").lower() == who.lower()]
    pick = exact or found
    names = {c["name"] for c in pick}
    if len(names) == 1:
        c = pick[0]
        return c["name"], clean_number(c["number"]), []
    return "", "", pick


PLUGIN = {
    "name": "phone_control",
    "description": (
        "Uses the user's Android phone: call someone, send a text, find the phone (rings loudly), "
        "check battery and connection, look up a contact's number. Pass the person as they said "
        "it (a name or a number). Calls and texts need the user's confirmation, which this tool "
        "asks for. Not for messages on WhatsApp or email — use those tools."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["call", "text", "find_phone", "status", "contacts"]},
            "who": {"type": "STRING", "description": "Contact name or phone number"},
            "message": {"type": "STRING", "description": "For text: the message, in the user's words"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Phone: call, text, find phone, status, contacts.",
}


def _ambiguous(action: str, matches: list) -> str:
    listing = "\n".join(f"{i}. {c.get('name')} ({c.get('label') or 'phone'})" for i, c in enumerate(matches[:6], 1))
    if not matches:
        return outcome.failed(f"phone_{action}", "no contact with that name on the phone")
    return outcome.ask(f"phone_{action}", "Which one? Say the full name.") + "\n" + \
        outcome.untrusted("contacts", listing)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    who = str(parameters.get("who") or "").strip()
    try:
        if action == "status":
            r = phone("status")
            return outcome.done("phone_status") + "\n" + outcome.untrusted("phone", r.get("text", "")) \
                if r.get("ok") else outcome.failed("phone_status", r.get("text") or "no answer")
        if action == "find_phone":
            r = phone("find_phone", {"seconds": 30})
            return outcome.done("phone_find", note="it is ringing at full volume for 30 seconds; the "
                                "user can stop it from the phone") if r.get("ok") else \
                outcome.failed("phone_find", r.get("text") or "no answer")
        if action in ("call", "text", "contacts") and not who:
            return outcome.ask(f"phone_{action}", "Who?")
        if action == "contacts":
            r = phone("contacts", {"query": who})
            found = (r.get("data") or {}).get("contacts", []) if r.get("ok") else []
            text = "\n".join(f"{c.get('name')}: {c.get('number')}" for c in found[:8]) or "no match"
            return outcome.done("phone_contacts", count=len(found)) + "\n" + outcome.untrusted("contacts", text)

        name, number, matches = resolve(who)
        if not number:
            return _ambiguous(action, matches)

        from core import confirm
        if action == "call":
            def do_call() -> str:
                r = phone("call", {"number": number})
                return outcome.done("phone_call", to=name) if r.get("ok") else \
                    outcome.failed("phone_call", r.get("text") or "the phone couldn't place the call")
            return confirm.request(f"phone_call:{number}", f"Call {name}", f"Call {name} ({number}) from your phone",
                                   do_call)

        if action == "text":
            message = str(parameters.get("message") or "").strip()
            if not message:
                return outcome.ask("phone_text", f"What should I say to {name}?")
            box = {"message": message}

            def do_text() -> str:
                r = phone("text", {"number": number, "message": box["message"]})
                return outcome.done("phone_text", to=name) if r.get("ok") else \
                    outcome.failed("phone_text", r.get("text") or "the phone couldn't send it")

            def do_edited(values: dict) -> str:
                box["message"] = str(values.get("message") or box["message"])
                return do_text()
            return confirm.request(f"phone_text:{number}:{message[:30]}", f"Text {name}",
                                   f"To {name} ({number}):\n{message}", do_text,
                                   fields=[{"key": "message", "label": "Message", "value": message,
                                            "multiline": True}], run_edited=do_edited)
        return outcome.failed("phone_control", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"phone_{action}", str(e)[:160])
