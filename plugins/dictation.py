"""
plugins/dictation.py — "take dictation": write down everything the user says, exactly, until they say stop.

    "Take dictation, it's my feature list" / "I'm going to tell you a list, write it all down"   start
    "End dictation" / "that's all for the dictation"                                           stop
    "Read back the dictation" / "tidy it up and save it to Notion"                             stop / save

See core/dictation.py for why the raw speech is written to disk by the app, not by the model.
"""
from __future__ import annotations

import threading

from core import addons, dictation, outcome

PLUGIN = {
    "name": "dictation",
    "description": (
        "Takes dictation: while on, EVERYTHING the user says is written down word for word by the app "
        "itself and you stay completely silent (no replies, no 'got it'). Use start when the user wants "
        "to narrate something long (a list, ideas, a story, meeting thoughts): 'take dictation', 'I'll "
        "tell you my ideas, write them down', 'let me dump my thoughts'. Use stop when they say they are "
        "done ('end dictation', 'that's all'); stop saves the full text to their notes and says how many "
        "words were kept. Use read to read it back, tidy to turn it into clean bullet points saved in "
        "their notes. Never claim anything was saved unless this tool's result says so."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["start", "stop", "read", "tidy", "status"]},
            "title": {"type": "STRING", "description": "For start: what it is about, a few words"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Dictation: write down everything said, verbatim, until told to stop.",
}


def _save_to_notes(text: str, title: str, tidy: bool = False) -> str:
    from plugins import notes
    r = notes.run({"action": "add", "text": text, "title": title or "Dictation", "tidy": tidy})
    return r


def _finish(title: str) -> str:
    """Save the dictated text to the notes backend and say what happened, truthfully."""
    text = dictation.read().strip()
    info = dictation.status()
    path = info.get("path")
    words = len(text.split())
    if words < 3:
        return outcome.done("dictation_stop", words=words, note="nothing was said")
    result = _save_to_notes(text, title)
    ok = not outcome.is_problem(result)
    return outcome.done("dictation_stop", words=words, kept_file=str(path),
                        notes_saved="yes" if ok else "NO: " + outcome.unwrap(result)[:120],
                        note="the full text is in kept_file either way")


def _auto_stop() -> None:
    """The user said 'end dictation' out loud: the app already stopped recording; save and tell them."""
    info = dictation.status()
    msg = _finish(info.get("title") or "")
    try:
        addons.say("The dictation has ended. Tell the user briefly how many words were kept and whether "
                   "it reached their notes, exactly as this says. " + msg)
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "status")
    try:
        if action == "start":
            if dictation.active():
                return outcome.done("dictation_start", note="already taking dictation")
            title = str(parameters.get("title") or "").strip()
            path = dictation.start(title, on_stop=_auto_stop)
            return outcome.done("dictation_start", file=str(path),
                                note="now stay silent: no replies and no acknowledgements until they say "
                                     "'end dictation'; everything they say is being written to disk")
        if action == "stop":
            if dictation.active():
                info = dictation.stop_now()
                title = info.get("title") or ""
            else:
                title = dictation.status().get("title") or ""
            return _finish(title)
        if action == "read":
            text = dictation.read().strip()
            if not text:
                return outcome.done("dictation_read", words=0)
            return outcome.done("dictation_read", words=len(text.split())) + "\n" + outcome.untrusted("dictation", text[-6000:])
        if action == "tidy":
            if dictation.active():
                dictation.stop_now()
            text = dictation.read().strip()
            if not text:
                return outcome.failed("dictation_tidy", "there is no dictation to tidy")
            result = _save_to_notes(text, dictation.status().get("title") or "Dictation", tidy=True)
            return outcome.done("dictation_tidy", saved="yes") if not outcome.is_problem(result) \
                else outcome.failed("dictation_tidy", outcome.unwrap(result)[:160])
        st = dictation.status()
        return outcome.done("dictation_status", on=st["on"], words=st["words"], file=str(st["path"] or ""))
    except Exception as e:
        return outcome.failed(f"dictation_{action}", str(e)[:160])
