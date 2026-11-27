"""
plugins/messaging.py — WhatsApp that actually goes where it should.

    "WhatsApp Aarav I'm running late"            shown for EDIT / confirm, then sent
    "Message Mum on WhatsApp from my phone"      same, but through the phone

The old route searched for the contact by clicking around WhatsApp's window and typing, which
broke whenever the layout changed. This one resolves the person to a phone NUMBER first (typed, saved,
or looked up in the phone's contacts through the Jarvis app), then opens WhatsApp's own
`whatsapp://send?phone=…&text=…` link, so the right chat opens with the message already in it, and presses
Send. Nothing is sent before the user confirms; a misheard name never reaches the wrong person.

On the PC this needs WhatsApp Desktop (or WhatsApp Web signed in) and cannot verify delivery, so it
says so. On the phone it presses Send itself only if the user enabled "Let Jarvis tap Send in WhatsApp";
otherwise the chat opens ready for one tap.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path

from core import confirm, outcome

SAVED = Path(__file__).resolve().parent.parent / "config" / "whatsapp_contacts.json"
_DIGITS_ONLY = re.compile(r"^[+()\d\s.-]+$")


def _saved() -> dict:
    try:
        return json.loads(SAVED.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _remember(name: str, number: str) -> None:
    d = _saved()
    d[name.lower()] = number
    SAVED.parent.mkdir(parents=True, exist_ok=True)
    SAVED.write_text(json.dumps(d), encoding="utf-8")


def resolve(who: str, number: str = "") -> tuple[str, str, list]:
    """(name, digits, ambiguous matches)."""
    from plugins import phone_control
    if number:
        n = phone_control.clean_number(number)
        return who or n, n, []
    saved = _saved().get((who or "").lower())
    if saved:
        return who, saved, []
    try:
        return phone_control.resolve(who)
    except Exception:
        return "", "", []


def _digits(n: str) -> str:
    return re.sub(r"\D", "", n)


def country_code() -> str:
    try:
        from memory.config_manager import get_plugin_setting
        return re.sub(r"\D", "", str(get_plugin_setting("whatsapp", "country_code", "") or ""))
    except Exception:
        return ""


def international(raw: str) -> str:
    """WhatsApp needs the full international number without '+' or a leading 0.
    '' means a country code is needed and none is set."""
    raw = (raw or "").strip()
    d = _digits(raw)
    if raw.startswith("+"):
        return d
    if d.startswith("00"):
        return d[2:]
    cc = country_code()
    if d.startswith("0"):
        return cc + d[1:] if cc else ""
    if cc and len(d) <= 10 and not d.startswith(cc):
        return cc + d
    return d


def _foreground_title() -> str:
    from core import foreground
    return foreground.title()


def _send_on_pc(digits: str, message: str) -> str:
    text = urllib.parse.quote(message)
    opened_web = False
    if sys.platform.startswith("win"):
        try:
            os.startfile(f"whatsapp://send?phone={digits}&text={text}")  # type: ignore[attr-defined]
        except OSError:                                  # no WhatsApp Desktop: WhatsApp Web instead
            webbrowser.open(f"https://web.whatsapp.com/send?phone={digits}&text={text}")
            opened_web = True
    else:
        webbrowser.open(f"https://web.whatsapp.com/send?phone={digits}&text={text}")
        opened_web = True
    # Wait for the chat to be in front with the text in the box, and only then press Enter:
    # an Enter that lands in some other window could send or submit something else.
    deadline = time.time() + (25 if opened_web else 12)
    while time.time() < deadline:
        time.sleep(1.0)
        if "whatsapp" in _foreground_title().lower():
            time.sleep(2.5 if opened_web else 1.2)       # the text box fills a moment after the window
            break
    else:
        if sys.platform.startswith("win"):
            return outcome.failed("whatsapp", "the chat didn't come to the front, so I didn't press Enter; it may "
                                  "be open with the message typed, ready for the user to send")
    from actions.send_message import pyautogui
    pyautogui.press("enter")
    return outcome.unverified("whatsapp", "I opened the chat and pressed Enter, but nothing reports whether "
                              "it was delivered; the user can look at the chat")


def _send_on_phone(digits: str, message: str) -> str:
    from plugins import phone_control
    r = phone_control.phone("whatsapp", {"number": digits, "message": message}, 30)
    if not r.get("ok"):
        return outcome.failed("whatsapp", r.get("text") or "the phone couldn't open WhatsApp")
    if (r.get("data") or {}).get("auto_send"):
        return outcome.unverified("whatsapp", "the phone opened the chat and pressed Send; delivery isn't reported")
    return outcome.started("whatsapp", note="the chat is open on the phone with the message typed; "
                           "the user must tap Send (turn on 'Let Jarvis tap Send in WhatsApp' in the app menu to skip that)")


PLUGIN = {
    "name": "whatsapp_message",
    "description": (
        "Sends a WhatsApp message to a person, from this PC or from the user's phone (device='phone' "
        "when they say 'from my phone'). Pass the person as said and the message in the user's own "
        "words and language. Asks the user to confirm (and lets them edit) before sending. If the "
        "person has no known number it asks for it once and remembers it. Use this for ALL "
        "WhatsApp messages instead of send_message; send_message is only for other apps."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "who": {"type": "STRING", "description": "Contact name, or a phone number with country code"},
            "message": {"type": "STRING", "description": "What to send"},
            "number": {"type": "STRING", "description": "The person's number, when the user just told you it"},
            "device": {"type": "STRING", "enum": ["pc", "phone"], "description": "Where to send from; default pc"},
            "country_code": {"type": "STRING", "description": "Only when the user tells you their country code "
                             "for contacts without one, e.g. '44'; it is remembered"},
        },
        "required": ["who", "message"],
    },
    "tier": "core",
    "brief": "WhatsApp: send a message (confirmed first).",
}

PLUGIN_SETTINGS = {
    "namespace": "whatsapp",
    "title": "WHATSAPP",
    "fields": [
        {"key": "country_code", "label": "Country code for numbers saved without one (e.g. 44, 91)",
         "type": "text", "placeholder": "44"},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    who = str(parameters.get("who") or "").strip()
    message = str(parameters.get("message") or "").strip()
    number = str(parameters.get("number") or "").strip()
    cc = re.sub(r"\D", "", str(parameters.get("country_code") or ""))
    if cc:
        from memory.config_manager import save_plugin_config
        save_plugin_config("whatsapp", {"country_code": cc})
    device = "phone" if str(parameters.get("device") or "").lower() == "phone" else "pc"
    if not who:
        return outcome.ask("whatsapp", "Who should I message?")
    if not message:
        return outcome.ask("whatsapp", f"What should I say to {who}?")
    try:
        name, n, matches = resolve(who, number)
        if not n:
            if matches:
                names = ", ".join(sorted({c.get("name", "?") for c in matches[:6]}))
                return outcome.ask("whatsapp", "Which one? Say the full name.") + "\n" + \
                    outcome.untrusted("contacts", names)
            return outcome.ask("whatsapp", f"I don't have a number for {who}. What is it, with the country code?")
        digits = international(n)
        if not digits:
            return outcome.ask("whatsapp", f"{who}'s number has no country code. Which country code should I use "
                               "for your contacts (for example 44 for the UK, 91 for India)? I'll remember it.",
                               note="when they answer, call again with country_code")
        if len(digits) < 8:
            return outcome.ask("whatsapp", f"That number looks too short for WhatsApp; I need the country code. What is {who}'s number?")
        if number and not _DIGITS_ONLY.match(who):
            _remember(who, digits)
        box = {"message": message}

        def go() -> str:
            try:
                return (_send_on_phone if device == "phone" else _send_on_pc)(digits, box["message"])
            except Exception as e:
                return outcome.failed("whatsapp", str(e)[:160])

        def edited(values: dict) -> str:
            box["message"] = str(values.get("message") or box["message"])
            return go()

        return confirm.request(f"whatsapp:{digits}:{message[:30]}", f"WhatsApp {name}",
                               f"To {name} (+{digits}) from your {device}:\n{message}", go,
                               fields=[{"key": "message", "label": "Message", "value": message,
                                        "multiline": True}], run_edited=edited)
    except Exception as e:
        return outcome.failed("whatsapp", str(e)[:160])
