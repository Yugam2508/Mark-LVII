"""
plugins/home_assistant.py — lights, plugs, fans, heating and scenes through Home Assistant.

    "Turn off the bedroom light"              action=turn_off  target="bedroom light"
    "Desk lamp to 30 percent, warm white"     action=turn_on   target="desk lamp" brightness=30 color=warm
    "Make the LED strip blue"                 action=turn_on   target="led strip" color=blue
    "Set the heating to 21"                   action=set_temperature target=heating temperature=21
    "Movie mode"                              action=scene     target="movie"
    "Is the PC plug on?"                      action=status    target="pc plug"
    "What devices do you know?"               action=list

WHY HOME ASSISTANT
    Home Assistant (home-assistant.io, free) talks to almost every brand — Philips
    Hue, Tuya / Smart Life, TP-Link Kasa / Tapo, IKEA, Govee, Xiaomi, Google and
    Alexa devices — so one plugin here covers all of them. It runs on a Raspberry
    Pi, a spare PC, or in Docker on the desktop.

SETUP
    In Home Assistant: your profile → Security → Long-lived access tokens → Create.
    In JARVIS: ⚙ → PLUGIN SETTINGS → HOME ASSISTANT: the address (for example
    http://homeassistant.local:8123) and the token, then TEST.

SAFETY
    Locks, garage doors, alarms and covers go through the on-screen confirmation
    (core/confirm.py): unlocking a door is not something a misheard sentence
    should be able to do.
"""
from __future__ import annotations

import difflib
import re

from core import confirm, outcome
from memory.config_manager import get_plugin_setting

NAMESPACE = "home_assistant"
CONTROLLABLE = ("light", "switch", "fan", "climate", "media_player", "cover", "lock",
                "scene", "script", "input_boolean", "vacuum", "humidifier", "alarm_control_panel")
NEEDS_CONFIRM = ("lock", "cover", "alarm_control_panel")

COLORS = {
    "red": [255, 0, 0], "green": [0, 255, 0], "blue": [0, 0, 255], "purple": [128, 0, 255],
    "pink": [255, 105, 180], "orange": [255, 140, 0], "yellow": [255, 220, 0],
    "cyan": [0, 255, 255], "white": [255, 255, 255], "teal": [0, 128, 128],
}
KELVIN = {"warm": 2700, "warm white": 2700, "neutral": 4000, "cool": 5500,
          "cool white": 5500, "daylight": 6500}


def _cfg(values: dict | None = None) -> tuple[str, str]:
    v = values or {}
    url = str(v.get("url") or get_plugin_setting(NAMESPACE, "url", "") or "").strip().rstrip("/")
    token = str(v.get("token") or get_plugin_setting(NAMESPACE, "token", "") or "").strip()
    return url, token


def _api(method: str, path: str, body: dict | None = None, values: dict | None = None):
    import requests
    url, token = _cfg(values)
    if not (url and token):
        raise RuntimeError("Home Assistant is not set up: add its address and a "
                           "long-lived token in ⚙ → PLUGIN SETTINGS → HOME ASSISTANT")
    r = requests.request(method, f"{url}/api{path}", json=body, timeout=10,
                         headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 401:
        raise RuntimeError("Home Assistant refused the token")
    if r.status_code >= 400:
        raise RuntimeError(f"Home Assistant error {r.status_code}: {r.text[:150]}")
    return r.json() if r.content else None


def _entities() -> list[dict]:
    return [s for s in _api("GET", "/states") or []
            if s.get("entity_id", "").split(".")[0] in CONTROLLABLE]


def _name(e: dict) -> str:
    return e.get("attributes", {}).get("friendly_name") or e["entity_id"]


def _match(target: str, domains: tuple[str, ...] | None = None) -> tuple[dict | None, list[str]]:
    """Best entity for a spoken name, or (None, close candidates)."""
    t = re.sub(r"\b(the|my|a)\b", "", (target or "").lower()).strip()
    pool = [e for e in _entities() if not domains or e["entity_id"].split(".")[0] in domains]
    if not t or not pool:
        return None, []
    exact = [e for e in pool if _name(e).lower() == t or e["entity_id"].lower() == t]
    if len(exact) == 1:
        return exact[0], []
    contains = [e for e in pool if t in _name(e).lower()]
    if len(contains) == 1:
        return contains[0], []
    names = {_name(e).lower(): e for e in (contains or pool)}
    close = difflib.get_close_matches(t, list(names), n=3, cutoff=0.6)
    if len(close) == 1 or (close and difflib.SequenceMatcher(None, t, close[0]).ratio() > 0.85):
        return names[close[0]], []
    return None, [names[c]["attributes"].get("friendly_name", c) for c in close] or \
        [_name(e) for e in contains[:4]]


def _call(domain: str, service: str, data: dict) -> None:
    _api("POST", f"/services/{domain}/{service}", data)


def _state_line(e: dict) -> str:
    a = e.get("attributes", {})
    extra = ""
    if e["entity_id"].startswith("light.") and a.get("brightness") is not None:
        extra = f", {round(a['brightness'] / 255 * 100)}%"
    if e["entity_id"].startswith("climate.") and a.get("temperature") is not None:
        extra = f", set to {a['temperature']}°, now {a.get('current_temperature', '?')}°"
    return f"{_name(e)}: {e.get('state')}{extra}"


def _turn(p: dict, on: bool, player) -> str:
    target = p.get("target") or ""
    e, close = _match(target)
    if e is None:
        return outcome.ask("home_turn", f"Which device? Close matches: {', '.join(close)}"
                           if close else "I couldn't find that device. What is it called?")
    domain = e["entity_id"].split(".")[0]
    data: dict = {"entity_id": e["entity_id"]}
    if domain in NEEDS_CONFIRM:
        service = {"lock": "unlock" if on else "lock",
                   "cover": "open_cover" if on else "close_cover",
                   "alarm_control_panel": "alarm_disarm" if on else "alarm_arm_away"}[domain]
        return confirm.request(key=f"ha:{e['entity_id']}:{service}",
                               title=f"{service.replace('_', ' ').title()}: {_name(e)}",
                               detail=e["entity_id"],
                               run=lambda: (_call(domain, service, data), f"Done: {service}")[1])
    if domain in ("scene", "script"):
        _call(domain, "turn_on", data)
        return outcome.done("home_scene", target=_name(e))
    if on and domain == "light":
        if p.get("brightness") is not None:
            data["brightness_pct"] = max(1, min(100, int(p["brightness"])))
        color = str(p.get("color") or "").lower().strip()
        if color in KELVIN:
            data["color_temp_kelvin"] = KELVIN[color]
        elif color in COLORS:
            data["rgb_color"] = COLORS[color]
    _call("homeassistant", "turn_on" if on else "turn_off", data)
    after = _api("GET", f"/states/{e['entity_id']}") or {}
    want = "on" if on else "off"
    if after.get("state") != want and domain in ("light", "switch", "fan", "input_boolean"):
        return outcome.unverified("home_turn", f"the device reports '{after.get('state')}'",
                                  target=_name(e))
    return outcome.done("home_turn", target=_name(e), state=after.get("state", want))


def _scene(p: dict, player) -> str:
    e, close = _match(p.get("target") or "", ("scene", "script"))
    if e is None:
        return outcome.ask("home_scene", f"Which scene? Close matches: {', '.join(close)}"
                           if close else "Which scene or routine?")
    _call(e["entity_id"].split(".")[0], "turn_on", {"entity_id": e["entity_id"]})
    return outcome.done("home_scene", target=_name(e))


def _temperature(p: dict, player) -> str:
    e, close = _match(p.get("target") or "heating", ("climate",))
    if e is None:
        return outcome.ask("home_temperature", "Which thermostat?")
    try:
        temp = float(p.get("temperature"))
    except (TypeError, ValueError):
        return outcome.ask("home_temperature", "What temperature?")
    _call("climate", "set_temperature", {"entity_id": e["entity_id"], "temperature": temp})
    return outcome.done("home_temperature", target=_name(e), temperature=temp)


def _status(p: dict, player) -> str:
    if p.get("target"):
        e, close = _match(p["target"])
        if e is None:
            return outcome.ask("home_status", "Which device?")
        return outcome.done("home_status") + "\n" + outcome.untrusted("home", _state_line(e))
    on = [e for e in _entities() if e.get("state") in ("on", "open", "unlocked", "playing")]
    text = "\n".join(_state_line(e) for e in on) or "Everything is off."
    if player:
        player.show_content("HOME — ON NOW", text)
    return outcome.done("home_status", on_count=len(on)) + "\n" + outcome.untrusted("home", text)


def _list(p: dict, player) -> str:
    ents = _entities()
    text = "\n".join(sorted(_state_line(e) for e in ents))
    if player and text:
        player.show_content(f"HOME — {len(ents)} DEVICES", text)
    return outcome.done("home_list", count=len(ents)) + "\n" + outcome.untrusted("home", text[:3000])


def _test(values: dict) -> tuple[bool, str]:
    try:
        info = _api("GET", "/config", values=values) or {}
        n = len([s for s in _api("GET", "/states", values=values) or []
                 if s.get("entity_id", "").split(".")[0] in CONTROLLABLE])
        return True, f"Connected to {info.get('location_name', 'Home Assistant')} — {n} devices ✓"
    except Exception as e:
        return False, str(e)[:160]


PLUGIN = {
    "name": "home_assistant",
    "description": (
        "Controls smart-home devices through Home Assistant: turn lights, plugs, fans "
        "and other devices on or off, set light brightness and colour, set a "
        "thermostat, run a scene, or say what is on. Use for anything about lights, "
        "smart plugs, heating or 'the house'. `target` is the device name the user said."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "enum": ["turn_on", "turn_off", "scene", "set_temperature", "status", "list"]},
            "target": {"type": "STRING", "description": "Device, room or scene name as the user said it"},
            "brightness": {"type": "INTEGER", "description": "For lights: 1-100 percent"},
            "color": {"type": "STRING",
                      "description": "For lights: red, green, blue, purple, pink, orange, yellow, "
                                     "cyan, white, teal, warm, neutral, cool or daylight"},
            "temperature": {"type": "NUMBER", "description": "For set_temperature: degrees"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Smart home via Home Assistant: on/off, brightness, colour, scenes.",
}

PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "HOME ASSISTANT",
    "fields": [
        {"key": "url", "label": "Home Assistant address", "type": "text",
         "placeholder": "http://homeassistant.local:8123"},
        {"key": "token", "label": "Long-lived access token", "type": "password"},
    ],
    "action": {"label": "TEST", "run": _test},
}

_ACTIONS = {"turn_on": lambda p, pl: _turn(p, True, pl), "turn_off": lambda p, pl: _turn(p, False, pl),
            "scene": _scene, "set_temperature": _temperature, "status": _status, "list": _list}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "").lower()
    handler = _ACTIONS.get(action)
    if handler is None:
        return outcome.failed("home", f"unknown action {action}")
    try:
        return handler(parameters, player)
    except Exception as e:  # network, auth, a device that went away — never raise
        return outcome.failed(f"home_{action}", str(e)[:200])
