"""
plugins/protocols.py — named protocols, like the ones Tony calls out: one phrase, several actions.

    "Create a night protocol: lock the PC, phone on Do Not Disturb, lights off, play rain sounds"
    "Jarvis, initiate night protocol" / "run the study protocol"
    "What protocols do I have?" / "show me the night protocol" / "add 'close Discord' to it"
    "Delete the gaming protocol"

A protocol is a list of plain-language steps. Running one shows it on screen and hands the steps to Jarvis to
carry out in order with its normal tools, so anything Jarvis can do by voice can be a step — and anything
that needs your confirmation (sending a message, shutting down) still asks. Stored in memory/protocols.json.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from core import outcome

STORE = Path(__file__).resolve().parent.parent / "memory" / "protocols.json"
_lock = threading.Lock()

IDEAS = {
    "study": "set study mode; close YouTube, Discord and games; put my phone on Do Not Disturb; play focus music on Spotify; start a 25 minute study session",
    "night": "lock the PC; put my phone on Do Not Disturb; set an alarm on my phone for tomorrow's first event; turn off the lights",
    "leaving": "tell me anything urgent in my email; turn off the lights; send the current Spotify music to my phone; lock the PC",
    "gaming": "switch to gaming mode; close the browser; turn the volume to 60; open Discord",
}


def _load() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def _key(name: str) -> str:
    n = re.sub(r"\bprotocols?\b", "", (name or "").lower())
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    return " ".join(n.split())


def split_steps(text) -> list[str]:
    """'a; b, then c' / '1. a 2. b' / a list -> clean steps."""
    if isinstance(text, list):
        parts = [str(x) for x in text]
    else:
        t = str(text or "")
        t = re.sub(r"\s*\b(?:and then|then|after that|next|finally)\b\s*", ";", t, flags=re.I)
        t = re.sub(r"(?:^|\s)\d+[.)]\s+", ";", t)
        parts = re.split(r"[;\n]+", t)
        if len(parts) == 1:                       # "a, b, c" — commas only when nothing else split it
            parts = t.split(",")
    return [p.strip(" .,-–—") for p in parts if p.strip(" .,-–—")]


def find(name: str, protos: dict) -> str | None:
    k = _key(name)
    if not k:
        return None
    if k in protos:
        return k
    hits = [p for p in protos if k in p or p in k]
    if len(hits) == 1:
        return hits[0]
    words = set(k.split())
    scored = sorted(((len(words & set(p.split())), p) for p in protos), reverse=True)
    if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def _show(player, title: str, steps: list[str]) -> None:
    text = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    try:
        if player:
            player.show_content(title, text)
        else:
            from core import addons
            addons.show(title, text)
    except Exception:
        pass


PLUGIN = {
    "name": "protocols",
    "description": (
        "Named protocols: one phrase that runs several actions, like Tony Stark's ('initiate night protocol', "
        "'run the study protocol', 'house party protocol'). create (name + steps, in the user's words), run "
        "(name), list, show (name), add_step (name + steps), delete (name), ideas. When you get the steps back "
        "from run, carry them out in order straight away with your tools, then say in one sentence that the "
        "protocol is done (and what, if anything, couldn't be done)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["create", "run", "list", "show", "add_step", "delete", "ideas"]},
            "name": {"type": "STRING", "description": "The protocol's name, e.g. 'night', 'study', 'house party'"},
            "steps": {"type": "STRING", "description": "For create/add_step: the steps, separated by ; or 'then'"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Protocols: named multi-step routines run by a phrase.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "list")
    name = str(parameters.get("name") or "").strip()
    try:
        with _lock:
            protos = _load()
            if action == "ideas":
                text = "\n".join(f"{k}: {v}" for k, v in IDEAS.items())
                return outcome.done("protocol_ideas") + "\n" + outcome.untrusted("protocol ideas", text)
            if action == "list":
                if not protos:
                    return outcome.done("protocol_list", count=0, note="none yet; offer to create one (say 'ideas' for examples)")
                text = "\n".join(f"{k}: {len(v['steps'])} steps" for k, v in protos.items())
                return outcome.done("protocol_list", count=len(protos)) + "\n" + outcome.untrusted("protocols", text)
            if action == "create":
                k = _key(name)
                steps = split_steps(parameters.get("steps"))
                if not k:
                    return outcome.ask("protocol_create", "What should the protocol be called?")
                if not steps:
                    if k in IDEAS:
                        steps = split_steps(IDEAS[k])
                    else:
                        return outcome.ask("protocol_create", f"What should the {k} protocol do, step by step?")
                existed = k in protos
                protos[k] = {"steps": steps, "created": time.time(), "runs": 0, "last_run": 0.0}
                _save(protos)
                _show(player, f"PROTOCOL — {k.upper()} — SAVED", steps)
                return outcome.done("protocol_create", name=k, steps=len(steps), replaced=existed,
                                    note=f"run it any time with 'initiate {k} protocol'")
            k = find(name, protos)
            if k is None:
                if not name:
                    return outcome.ask(f"protocol_{action}", "Which protocol?")
                have = ", ".join(protos) or "none"
                return outcome.failed(f"protocol_{action}", f"no protocol called {name}", have=have)
            p = protos[k]
            if action == "show":
                _show(player, f"PROTOCOL — {k.upper()}", p["steps"])
                return outcome.done("protocol_show", name=k) + "\n" + outcome.untrusted("protocol", "\n".join(p["steps"]))
            if action == "add_step":
                more = split_steps(parameters.get("steps"))
                if not more:
                    return outcome.ask("protocol_add_step", "What should I add?")
                p["steps"].extend(more)
                _save(protos)
                return outcome.done("protocol_add_step", name=k, steps=len(p["steps"]))
            if action == "delete":
                protos.pop(k)
                _save(protos)
                return outcome.done("protocol_delete", name=k)
            if action == "run":
                p["runs"] = int(p.get("runs", 0)) + 1
                p["last_run"] = time.time()
                _save(protos)
                _show(player, f"PROTOCOL — {k.upper()} — INITIATED", p["steps"])
                steps = "\n".join(f"{i}. {s}" for i, s in enumerate(p["steps"], 1))
                return outcome.done("protocol_run", name=k, steps=len(p["steps"]),
                                    note="carry these out now, in order, with your tools; don't stop to ask between "
                                         "steps (actions that need confirmation will ask by themselves); then report "
                                         "in one sentence") + "\nSTEPS (written by the user, to carry out):\n" + steps
        return outcome.failed("protocols", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"protocol_{action}", str(e)[:160])
