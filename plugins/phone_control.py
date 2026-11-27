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
        "check battery and connection, look up a contact's number; open an app by name (open_app), "
        "open a website (open_url), open the Bluetooth/Wi-Fi/sound/display settings page "
        "(settings; Android won't let apps flip Bluetooth or Wi-Fi themselves, so say it is one tap "
        "on the page), phone volume, flashlight, set a timer, play/pause/next on whatever the phone "
        "is playing (media), start navigation (navigate); send text or a link (or the PC clipboard) to the "
        "phone (send_to_phone: copied there and shown as a notification); where the phone is (location, "
        "gives a map link); Do Not Disturb on/off (dnd, with on); set an alarm (alarm: hour, minute, label); "
        "take a screenshot on the phone (screenshot) or lock it (lock); operate the app open on the phone: read "
        "what's on its screen (screen_read), tap a button by its words (tap + button), scroll up/down (scroll + "
        "direction), type into the box in focus (type_text + text), go back / home / recents / notifications "
        "(nav + nav_to); the ringer: normal / vibrate / silent (ringer + mode). For a multi-step job on the phone, "
        "read the screen, act, and read again. For a person pass the name or number. "
        "Calls and texts need the user's confirmation, which this tool asks for. Not for messages on "
        "WhatsApp or email — use those tools. For music by name use spotify_control with the phone as the device."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["call", "text", "find_phone", "status", "contacts", "open_app", "open_url",
                                                    "settings", "volume", "flashlight", "timer", "media", "navigate",
                                                    "send_to_phone", "location", "dnd", "alarm", "screenshot", "lock",
                                                    "screen_read", "tap", "scroll", "type_text", "nav", "ringer"]},
            "mode": {"type": "STRING", "enum": ["normal", "vibrate", "silent"], "description": "For ringer"},
            "button": {"type": "STRING", "description": "For tap: the words on the button or item to tap"},
            "nav_to": {"type": "STRING", "enum": ["back", "home", "recents", "notifications", "quick settings"],
                       "description": "For nav"},
            "label": {"type": "STRING", "description": "For timer/alarm: what it's for, e.g. 'swim'"},
            "title": {"type": "STRING", "description": "For send_to_phone: a short heading"},
            "hour": {"type": "INTEGER", "description": "For alarm: hour 0-23"},
            "minute": {"type": "INTEGER", "description": "For alarm: minute 0-59"},
            "text": {"type": "STRING", "description": "For send_to_phone: the text or link; empty = what's on the PC clipboard"},
            "name": {"type": "STRING", "description": "For open_app: the app's name, e.g. 'Spotify'"},
            "url": {"type": "STRING", "description": "For open_url: a full https:// address"},
            "page": {"type": "STRING", "description": "For settings: bluetooth, wifi, sound, display, location, battery"},
            "level": {"type": "INTEGER", "description": "For volume: 0-100"},
            "direction": {"type": "STRING", "description": "For volume: up or down"},
            "on": {"type": "BOOLEAN", "description": "For flashlight: true or false"},
            "seconds": {"type": "INTEGER", "description": "For timer: length in seconds"},
            "key": {"type": "STRING", "description": "For media: play, pause, next or previous"},
            "where": {"type": "STRING", "description": "For navigate: the destination"},
            "who": {"type": "STRING", "description": "Contact name or phone number"},
            "message": {"type": "STRING", "description": "For text: the message, in the user's words"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Phone: call, text, find phone, status, contacts.",
}


_RISKY = re.compile(r"\b(send|pay|buy|purchase|order|checkout|check out|delete|remove|confirm|transfer|post|"
                    r"publish|call|subscribe|install|uninstall|sign out|log out|reset|format|unfriend|block)\b", re.I)


def _tap(button: str) -> str:
    """Tap something on the phone's screen; a button that sends, pays, deletes or posts asks first."""
    if not button:
        return outcome.ask("phone_tap", "Which button? Say the words on it.")

    def do_tap() -> str:
        r = phone("tap", {"text": button})
        return outcome.done("phone_tap", tapped=button) if r.get("ok") else \
            outcome.failed("phone_tap", r.get("text") or "no answer")

    if _RISKY.search(button):
        from core import confirm
        return confirm.request(f"phone_tap:{button[:40]}", f"Tap \"{button}\" on your phone",
                               f"Tap \"{button}\" in the app open on your phone", do_tap)
    return do_tap()


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
        simple = {"open_app": ("name",), "open_url": ("url",), "settings": ("page",),
                  "volume": ("level", "direction"), "flashlight": ("on",), "timer": ("seconds", "label"),
                  "media": ("key",), "navigate": ("where",), "send_to_phone": ("text", "title"),
                  "location": (), "dnd": ("on",), "alarm": ("hour", "minute", "label"),
                  "screenshot": (), "lock": (), "screen_read": (), "scroll": ("direction",),
                  "type_text": ("text",), "nav": ("nav_to",), "ringer": ("mode",)}
        if action == "tap":
            return _tap(str(parameters.get("button") or parameters.get("text") or "").strip())
        if action in simple:
            args = {k: parameters[k] for k in simple[action] if parameters.get(k) is not None}
            if action == "nav" and "nav_to" in args:
                args = {"where": args["nav_to"]}
            if action == "send_to_phone" and not str(args.get("text") or "").strip():
                try:
                    import pyperclip
                    args["text"] = pyperclip.paste()
                except Exception:
                    args["text"] = ""
                if not str(args["text"]).strip():
                    return outcome.ask("phone_send_to_phone", "What should I send? The clipboard is empty.")
            if action == "open_url":
                u = str(args.get("url", ""))
                if not re.match(r"^https?://", u, re.I) and re.match(r"^[\w-]+(\.[\w-]+)+", u):
                    args["url"] = "https://" + u
            r = phone(action, args)
            if action == "screen_read" and r.get("ok"):
                return outcome.done("phone_screen_read") + "\n" + outcome.untrusted("phone screen", r.get("text", ""))
            return outcome.done(f"phone_{action}", result=r.get("text", "")) if r.get("ok") else \
                outcome.failed(f"phone_{action}", r.get("text") or "no answer")
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
