"""
plugins/conversation.py — JARVIS knows when to talk, and when to leave a note.

    "I'm talking to someone" / "give me ten minutes"   action=pause minutes=10
    "I'm on a call"                                     action=pause reason="on a call"
    "I'm back" / "okay, I'm free"                       action=back
    "Are you listening?"                                action=status

While you are busy or away, anything JARVIS wants to tell you — a finished task, an
important email, a reminder, a price drop — becomes a card on the screen that stays
until you dismiss it (and a phone notification when you're away). When you're back
and free, it sums up what you missed. When you're free, it just says it, and after
finishing something it suggests what to do next.

How JARVIS decides you're busy: see core/presence.py (you said so; you were just
talking but not to it; another app is using the microphone for a call; gaming or
watching mode). Away = no keyboard or mouse for a while (settings below).

With the wake word on, pausing puts JARVIS to sleep until "Hey Jarvis", so it does
not hear your conversation at all. Without it, JARVIS keeps listening but stays
quiet unless you use its name.
"""
from __future__ import annotations

import threading
import time

from core import addons, outcome, presence
from memory.config_manager import get_plugin_setting, save_plugin_config

NAMESPACE = "conversation"
_state = {"last": "free"}


def _apply_followup() -> None:
    """Wake-word mode: how long JARVIS keeps listening after the last thing you said."""
    a = addons.assistant()
    if a is None:
        return
    try:
        secs = float(get_plugin_setting(NAMESPACE, "followup_seconds", 45) or 45)
        a._wake_sleep_timeout = max(10.0, secs)
    except Exception:
        pass


def _wake_word_ready(a) -> bool:
    det = getattr(a, "_wake_detector", None)
    return bool(getattr(a, "_wake_enabled", False) and det is not None and getattr(det, "ready", False))


def pause(minutes: float, reason: str) -> str:
    presence.set_busy(minutes, reason)
    a = addons.assistant()
    if a is not None and _wake_word_ready(a):
        a.sleep(reason=f"{reason} — say 'Hey Jarvis' when you're done")
        return "asleep until the wake word"
    return "listening but quiet unless called by name"


def back() -> list:
    presence.clear_busy()
    a = addons.assistant()
    if a is not None and not getattr(a, "_awake", True):
        try:
            a.wake(reason="you're back")
        except Exception:
            pass
    return addons.take_missed()


def _watch() -> None:
    time.sleep(20)
    while True:
        try:
            _apply_followup()
            now, _why = presence.state()
            if now == "free" and _state["last"] != "free" and \
                    get_plugin_setting(NAMESPACE, "welcome_back", True):
                missed = addons.take_missed()
                if missed:
                    addons.say("[SYSTEM] The user is back and free. In one or two short sentences, "
                               "tell them what came in while they were busy (the cards are still on "
                               "screen), then ask what they'd like to do first:\n"
                               + outcome.untrusted("missed", "\n".join(missed)))
            _state["last"] = now
        except Exception as e:
            print(f"[Conversation] {e}")
        time.sleep(10)


PLUGIN = {
    "name": "conversation",
    "description": (
        "Controls when the assistant speaks up. Use 'pause' when the user says they're "
        "talking to someone, on a call, busy, or asks you to give them some minutes; "
        "'back' when they say they're back or free (then mention anything they missed); "
        "'status' when they ask if you're listening; 'handoff' for 'where were we on my "
        "desktop/laptop', 'continue what I was saying on the other computer' (it returns the "
        "last turns another device had with them); 'careful' with on=true/false for 'be careful', "
        "'ask me before you do anything', 'you can just do things again'. While paused, say nothing unless "
        "they use your name."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["pause", "back", "status", "handoff", "careful"]},
            "on": {"type": "BOOLEAN", "description": "For careful: true = ask before every action"},
            "minutes": {"type": "NUMBER", "description": "For pause: how long, default from settings"},
            "reason": {"type": "STRING", "description": "For pause: e.g. 'talking to someone', 'on a call'"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Pause / back: stay quiet while the user talks to someone.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "CONVERSATION & PRESENCE",
    "fields": [
        {"key": "voice_confirm", "label": "Let me answer confirmations by saying 'confirm' / 'cancel'",
         "type": "toggle", "default": True},
        {"key": "pause_minutes", "label": "'I'm talking to someone' lasts (minutes)", "type": "choice",
         "options": ["5", "10", "15", "30", "60"], "default": "15"},
        {"key": "away_minutes", "label": "I'm 'away' after this many idle minutes", "type": "choice",
         "options": ["5", "10", "20", "30"], "default": "10"},
        {"key": "followup_seconds", "label": "Wake-word mode: keep listening after I stop talking (seconds)",
         "type": "choice", "options": ["20", "45", "120"], "default": "45"},
        {"key": "welcome_back", "label": "When I'm back, tell me what I missed", "type": "toggle",
         "default": True},
        {"key": "screen_time", "label": "Keep track of which apps and sites I spend time on (stays on this PC)",
         "type": "toggle", "default": True},
        {"key": "rain_alerts", "label": "Tell me before it rains (home city, 7am–9pm)", "type": "toggle",
         "default": True},
        {"key": "home_city", "label": "Home city (for the weather when you don't name one)", "type": "text",
         "placeholder": "London"},
        {"key": "open_shared_links", "label": "Open links I share to Jarvis from my phone in the browser",
         "type": "toggle", "default": True},
        {"key": "careful_mode", "label": "Careful mode: Jarvis asks before every action, not just risky ones",
         "type": "toggle", "default": False},
        {"key": "keep_transcript", "label": "Keep a full log of our conversations on this PC "
         "(so Jarvis can look back at what you said)", "type": "toggle", "default": True},
        {"key": "hub_mode", "label": "This PC is my always-on hub (never sleeps while plugged in, "
         "stays in the tray; also switch on AUTO-START)", "type": "toggle", "default": False},
        {"key": "keep_awake_for_phone", "label": "Keep this PC awake while my phone is connected "
         "(on mains power only)", "type": "toggle", "default": True},
        {"key": "close_to_tray", "label": "Closing the window keeps Jarvis running in the tray "
         "(Ctrl+Alt+J brings it back)", "type": "toggle", "default": True},
        {"key": "follow_audio", "label": "Follow audio devices: switch when headphones or Bluetooth "
         "connect or disconnect", "type": "toggle", "default": True},
    ],
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    try:
        if action == "pause":
            minutes = float(parameters.get("minutes") or get_plugin_setting(NAMESPACE, "pause_minutes", 15) or 15)
            reason = str(parameters.get("reason") or "talking to someone")
            how = pause(minutes, reason)
            return outcome.done("conversation_pause", minutes=minutes, how=how,
                                note="acknowledge in three words at most, then stay silent unless "
                                     "the user says your name; anything new goes on screen as cards")
        if action == "back":
            missed = back()
            return outcome.done("conversation_back", missed=len(missed)) + \
                ("\n" + outcome.untrusted("missed", "\n".join(missed)) if missed else "")
        if action == "careful":
            on = bool(parameters.get("on", True))
            save_plugin_config(NAMESPACE, {"careful_mode": on})
            return outcome.done("careful_mode", on=on,
                                note=("[CAREFUL MODE IS ON] Before you do ANYTHING that changes something — opening or closing apps, playing music, changing a setting, sending, saving, deleting, moving, typing into an app, phone actions — first say in one short sentence exactly what you are about to do and wait for the user's yes. Answering questions and looking things up need no permission." if on else "careful mode is off: act on clear requests "
                                      "straight away again (risky ones still ask on screen)"))
        if action == "handoff":
            from core import handoff
            other = handoff.latest_other()
            if not other:
                return outcome.failed("conversation_handoff", "no other device has talked to you in the "
                                      "last 30 minutes (or device sync is off)")
            return outcome.done("conversation_handoff", device=other["device"],
                                minutes_ago=int((time.time() - other["at"]) // 60),
                                note="carry on from this naturally") + "\n" + \
                outcome.untrusted("conversation", "\n".join(other["turns"]))
        where, why = presence.state()
        return outcome.done("conversation_status", state=where, reason=why or None)
    except Exception as e:
        return outcome.failed(f"conversation_{action}", str(e)[:150])


threading.Thread(target=_watch, name="conversation_watch", daemon=True).start()
