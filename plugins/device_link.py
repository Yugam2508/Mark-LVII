"""
plugins/device_link.py — control your PCs from your phone, and each PC from the other.

FROM YOUR PHONE (the ntfy app, subscribed to your JARVIS command topic)
    Type or dictate a message:
        desktop: turn on and launch spotify and valorant
        launch spotify and valorant            (goes to the PC set to answer untargeted commands)
        laptop: lock
        all: status
    Each PC answers on your alerts topic ("Desktop: ✓ Starting VALORANT").

FROM ONE PC TO THE OTHER (by voice)
    "Wake the desktop", "on the desktop, launch Valorant", "lock the laptop",
    "what's the desktop doing?"

IF THE PC IS OFF
    Commands wait on the channel. When the PC starts and JARVIS opens, it runs the
    commands addressed to it from the last few hours (3 by default), then tells
    your phone it is on. So "desktop: launch spotify and valorant" sent from the
    bus still happens when you get home and the desktop boots.

WAKING A PC (Wake-on-LAN)
    Any JARVIS that is awake on your home network can wake the desktop. Turn on
    "Wake on LAN" in the desktop's BIOS and network adapter settings (see
    ADDONS.md). A wake signal cannot cross the internet by itself, so from outside
    with nothing awake at home, use one of these:
      * a smart plug + the BIOS setting "power on after power loss": put the plug's
        Home Assistant entity in "Wake using this smart plug" and JARVIS switches it;
      * your router's own remote Wake-on-LAN (many ASUS/TP-Link routers have it);
      * Windows does not sign in by itself after a wake: for apps to launch on their
        own, turn on automatic sign-in on the desktop (ADDONS.md explains the trade-off).

PERMISSIONS (⚙ → PLUGIN SETTINGS → PHONE & DEVICES, per PC)
    Open apps and games, Spotify, lock/sleep: on. Shut down / restart: off.
    "Anything else" (a free-form request handed to the assistant): off.
    Commands older than the limit are ignored, and nothing a remote command does
    can press an on-screen CONFIRM — sending email still needs you at the PC.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import threading
import time

from core import addons, outcome
from memory.config_manager import CONFIG_DIR, get_plugin_config
from plugins import _ntfy

NAMESPACE = "phone_link"
STATE_FILE = CONFIG_DIR / "device_link_state.json"
_lock = threading.Lock()
_stop = threading.Event()
_state: dict = {}


# ── identity and settings ─────────────────────────────────────────────────────

def _cfg() -> dict:
    return get_plugin_config(NAMESPACE)


def _is_laptop() -> bool:
    try:
        import psutil
        return psutil.sensors_battery() is not None
    except Exception:
        return False


def me() -> str:
    name = str(_cfg().get("device_name") or "").strip().lower()
    return name or ("laptop" if _is_laptop() else "desktop")


def _perm(key: str, default: bool) -> bool:
    v = _cfg().get(key)
    return default if v is None else bool(v)


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(_state), encoding="utf-8")


def _network() -> dict:
    """This PC's LAN address, network and MAC (for Wake-on-LAN by the others)."""
    info = {"ip": "", "mac": "", "net": "", "bcast": "255.255.255.255"}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))   # no packet is sent; it only picks the route
        info["ip"] = s.getsockname()[0]
        s.close()
        import ipaddress
        import psutil
        for addrs in psutil.net_if_addrs().values():
            v4 = [a for a in addrs if a.family == socket.AF_INET and a.address == info["ip"]]
            if not v4:
                continue
            mac = [a for a in addrs if a.family == psutil.AF_LINK]
            info["mac"] = mac[0].address.replace("-", ":").lower() if mac else ""
            if v4[0].netmask:
                net = ipaddress.ip_network(f"{info['ip']}/{v4[0].netmask}", strict=False)
                info["net"], info["bcast"] = str(net), str(net.broadcast_address)
    except Exception:
        pass
    return info


# ── waking ────────────────────────────────────────────────────────────────────

def send_wol(mac: str, bcast: str = "255.255.255.255") -> bool:
    hexmac = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(hexmac) != 12:
        return False
    packet = bytes.fromhex("ff" * 6 + hexmac * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for addr in {bcast, "255.255.255.255"}:
            for port in (9, 7):
                for _ in range(3):
                    s.sendto(packet, (addr, port))
    return True


def wake(device: str) -> tuple[bool, str]:
    """Wake another PC by Wake-on-LAN or the configured smart plug."""
    device = device.lower()
    if device == me():
        return True, f"{me().title()} is already on."
    peers = _state.get("peers", {})
    peer = peers.get(device, {})
    mac = peer.get("mac") or (_cfg().get("wake_mac") if device == "desktop" else "")
    done = []
    mine = _network()
    if mac and (not peer.get("net") or peer.get("net") == mine["net"]):
        if send_wol(mac, peer.get("bcast") or mine["bcast"]):
            done.append("sent a Wake-on-LAN signal")
    entity = str(_cfg().get("ha_wake_entity") or "").strip()
    if entity:
        try:
            from plugins import home_assistant
            home_assistant._call("homeassistant", "turn_on", {"entity_id": entity})
            done.append(f"switched on {entity}")
        except Exception as e:
            done.append(f"could not switch {entity}: {e}")
    if not done:
        why = ("I don't know its network address yet — open Jarvis on it once" if not mac
               else "it is on a different network from this PC")
        return False, (f"Couldn't wake {device}: {why}. From outside your home, use a smart plug "
                       "(Home Assistant) or your router's remote wake.")
    return True, f"Waking {device}: " + ", ".join(done) + ". It takes a minute to start."


# ── running a command on this PC ──────────────────────────────────────────────

_VERBS = {
    "wake": r"(?:wake(?: up)?|turn on|switch on|boot(?: up)?|start up|power on)",
    "launch": r"(?:launch|open|start|run|play|load)",
    "lock": r"(?:lock)",
    "sleep": r"(?:sleep|go to sleep|put to sleep)",
    "shutdown": r"(?:shut ?down|turn off|switch off|power off)",
    "restart": r"(?:restart|reboot)",
    "cancel": r"(?:cancel shutdown|abort shutdown|cancel)",
    "status": r"(?:status|what'?s (?:on|running|happening)|are you on)",
    "say": r"(?:say|tell (?:me|it))",
}


def parse(text: str) -> list[tuple[str, str]]:
    """'turn on and launch spotify and valorant' -> [(wake,''),(launch,spotify),(launch,valorant)]"""
    steps, verb = [], None
    for part in re.split(r"\s*(?:,|;|\band then\b|\bthen\b|\band\b|&)\s*", text.strip().rstrip(".!")):
        part = part.strip()
        if not part:
            continue
        for name, pat in _VERBS.items():
            m = re.match(rf"^{pat}\b\s*(.*)$", part, re.I)
            if m:
                verb, part = name, m.group(1).strip()
                break
        steps.append((verb or "unknown", part))
    return steps


def _launch(what: str) -> str:
    w = what.strip().lower()
    m = re.match(r"^(.*?)\s+on spotify$", w)
    if m or w.startswith("spotify "):
        if not _perm("allow_spotify", True):
            return "✗ Spotify control is not allowed remotely on this PC"
        from plugins import spotify_control
        query = m.group(1) if m else w[len("spotify "):]
        res = spotify_control.run({"action": "play", "query": query, "device": "here"})
        return ("✓ Playing " + query) if res.startswith("status=done") else "✗ Spotify: " + res.split(" -- ")[0][-80:]
    if not _perm("allow_apps", True):
        return "✗ Opening apps is not allowed remotely on this PC"
    try:
        from plugins import games
        game, _close = games.find(w)
        if game is not None:
            ok, msg = games.launch(w)
            return ("✓ " if ok else "✗ ") + msg
    except Exception:
        pass
    from actions.open_app import open_app
    res = open_app({"app_name": what.strip()}) or ""
    return ("✓ Opening " + what.strip()) if not res.startswith("status=failed") else \
        "✗ " + res.split("reason=")[-1].split(" -- ")[0].strip('"')[:100]


def _power(kind: str) -> str:
    if kind in ("lock", "sleep") and not _perm("allow_lock", True):
        return "✗ Locking/sleeping is not allowed remotely on this PC"
    if kind in ("shutdown", "restart") and not _perm("allow_power", False):
        return "✗ Shutting down/restarting is not allowed remotely on this PC (turn it on in settings)"
    if sys.platform != "win32":
        return f"✗ {kind} is only set up for Windows"
    if kind == "lock":
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "✓ Locked"
    if kind == "sleep":
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return "✓ Going to sleep"
    if kind == "cancel":
        subprocess.run(["shutdown", "/a"], capture_output=True)
        return "✓ Shutdown cancelled"
    flag = "/s" if kind == "shutdown" else "/r"
    subprocess.run(["shutdown", flag, "/t", "60", "/c",
                    "JARVIS: remote request. Say 'cancel shutdown' or run 'shutdown /a' to stop it."],
                   capture_output=True)
    return f"✓ {'Shutting down' if kind == 'shutdown' else 'Restarting'} in 60 seconds"


def _status() -> str:
    bits = [f"{me().title()} is on"]
    try:
        from plugins import modes
        bits.append(f"{modes.current()} mode")
        game = modes._game_running()
        if game:
            bits.append(f"playing {game}")
    except Exception:
        pass
    try:
        import psutil
        bits.append(f"up {int((time.time() - psutil.boot_time()) // 60)} min")
        bat = psutil.sensors_battery()
        if bat:
            bits.append(f"battery {bat.percent:.0f}%")
    except Exception:
        pass
    return "✓ " + ", ".join(bits)


def execute(text: str, source: str) -> list[str]:
    """Run a command addressed to this PC. Returns one result line per step."""
    out = []
    for verb, arg in parse(text):
        try:
            if verb == "wake":
                target = re.sub(r"^(?:the|my)\s+", "", (arg or me()).lower()).strip()
                target = {"pc": "desktop", "home pc": "desktop", "computer": "desktop"}.get(target, target)
                if target in ("", me(), "it", "up", "on"):
                    out.append("✓ Already on")
                elif source == "phone":
                    continue  # the phone path already asked an awake PC to wake it
                else:
                    ok, msg = wake(target)
                    out.append(("✓ " if ok else "✗ ") + msg)
            elif verb == "launch" and arg:
                out.append(_launch(arg))
            elif verb in ("lock", "sleep", "shutdown", "restart", "cancel"):
                out.append(_power(verb))
            elif verb == "status":
                out.append(_status())
            elif verb == "say" and arg:
                addons.say(f"[SYSTEM] A message from the user's {source}. Say it out loud: "
                           + outcome.untrusted("remote", arg))
                out.append("✓ Said it")
            elif _perm("allow_freeform", False):
                addons.say(f"[SYSTEM] A request the user sent from their {source}. Do it if it is "
                           "safe and you can; anything needing confirmation waits for them:\n"
                           + outcome.untrusted("remote", f"{verb if verb != 'unknown' else ''} {arg}".strip()))
                out.append(f"✓ Passed to Jarvis: {arg}")
            else:
                out.append(f"✗ Didn't understand '{arg or verb}' (free-form requests are off)")
        except Exception as e:
            out.append(f"✗ {verb} {arg}: {e}")
    return out


# ── the channel ───────────────────────────────────────────────────────────────

def _targets(text: str) -> tuple[list[str], str]:
    """('desktop: launch x') -> (['desktop'], 'launch x'). [] means untargeted."""
    names = {me(), "desktop", "laptop", "pc", "home pc", "all", "both"} | set(_state.get("peers", {}))
    m = re.match(r"^\s*(?:on (?:the |my )?)?([a-z0-9 _-]{2,20}?)\s*[:,]\s*(.+)$", text, re.I)
    if m and m.group(1).strip().lower() in names:
        t = m.group(1).strip().lower()
        t = {"pc": "desktop", "home pc": "desktop", "both": "all"}.get(t, t)
        return [t], m.group(2)
    return [], text


def _reply(lines: list[str]) -> None:
    if lines:
        _ntfy.publish("alert", "\n".join(lines), title=me().title(), tags=["computer"])


def handle(msg: dict) -> None:
    """One message from the command topic."""
    mid, when = msg.get("id", ""), int(msg.get("time", time.time()))
    with _lock:
        if mid in _state.setdefault("done", []):
            return
        _state["done"] = (_state["done"] + [mid])[-200:]
        _save_state()
    if not _perm("accept_remote", True):
        return
    max_age = float(_cfg().get("max_age_hours") or 3) * 3600
    if time.time() - when > max_age:
        return
    body = str(msg.get("message") or "")[:500]
    try:
        data = json.loads(body)
    except ValueError:
        data = None

    if isinstance(data, dict) and data.get("jarvis"):
        sender = str(data.get("from", "")).lower()
        if sender == me():
            return
        if data.get("kind") == "hello":
            _state.setdefault("peers", {})[sender] = {k: data.get(k) for k in ("mac", "ip", "net", "bcast")}
            _state["peers"][sender]["seen"] = int(time.time())
            _save_state()
            return
        if data.get("kind") == "command" and data.get("to") in (me(), "all"):
            results = execute(str(data.get("cmd", "")), f"{sender} PC")
            _ntfy.publish("command", json.dumps({"jarvis": 1, "kind": "reply", "from": me(),
                                                 "to": sender, "lines": results}))
            addons.log(f"SYS: Remote command from {sender}: {data.get('cmd')} → {'; '.join(results)}")
        elif data.get("kind") == "reply" and data.get("to") == me():
            _state.setdefault("replies", {})[sender] = {"lines": data.get("lines", []), "at": time.time()}
        return

    # Plain text: from the phone.
    targets, command = _targets(body)
    steps = parse(command)
    for_me = (me() in targets or "all" in targets or
              (not targets and _perm("handle_untargeted", not _is_laptop())))
    # Waking: "desktop: turn on ..." or "turn on the desktop" is done by whichever
    # OTHER PC is awake; the rest of the message waits for the woken PC itself.
    to_wake = set()
    for verb, arg in steps:
        if verb != "wake":
            continue
        who = re.sub(r"^(?:the|my)\s+", "", (arg or "").lower()).strip()
        if who in ("", "up", "it", "on"):
            who = targets[0] if targets and targets[0] != "all" else ""
        who = {"pc": "desktop", "home pc": "desktop", "computer": "desktop"}.get(who, who)
        if who and who != me():
            to_wake.add(who)
    for w in sorted(to_wake):
        ok, m = wake(w)
        _reply([("✓ " if ok else "✗ ") + m])
    if for_me:
        lines = [l for l in execute(command, "phone") if "Already on" not in l]
        if lines or not to_wake:
            _reply(lines or [_status()])
        addons.log(f"SYS: Phone command: {command} → {'; '.join(lines) or 'nothing to run here'}")


def _hello() -> None:
    net = _network()
    _ntfy.publish("command", json.dumps({"jarvis": 1, "kind": "hello", "from": me(), **net}))


def _run() -> None:
    global _state
    time.sleep(10)
    _state = _load_state()
    _state.setdefault("done", [])
    try:
        _hello()
        hours = int(float(_cfg().get("max_age_hours") or 3))
        missed = _ntfy.poll("command", f"{hours}h")
        for m in missed:
            handle(m)
        if _perm("announce_on", True):
            _ntfy.publish("alert", f"{me().title()} is on — Jarvis is ready.", tags=["computer"],
                          priority=2)
    except Exception as e:
        print(f"[DeviceLink] start-up: {e}")
    def _say_hello_every_6h():
        while not _stop.wait(6 * 3600):
            _hello()
    threading.Thread(target=_say_hello_every_6h, daemon=True).start()
    _ntfy.listen("command", handle, _stop, since="1m")


# ── tool ──────────────────────────────────────────────────────────────────────

def _send(target: str, command: str, wait: float = 12.0) -> list[str]:
    target = target.lower()
    if target == me():
        return execute(command, "voice")
    _state.setdefault("replies", {}).pop(target, None)
    _ntfy.publish("command", json.dumps({"jarvis": 1, "kind": "command", "from": me(),
                                         "to": target, "cmd": command}))
    deadline = time.time() + wait
    while time.time() < deadline:
        r = _state.get("replies", {}).get(target)
        if r:
            return r["lines"]
        time.sleep(0.5)
    return [f"No answer from {target} yet — if it is off or asleep the command waits and "
            f"runs when it starts (for the next {_cfg().get('max_age_hours') or 3} hours)."]


PLUGIN = {
    "name": "device_link",
    "description": (
        "Controls the user's OTHER computers (e.g. 'desktop', 'laptop'): wake one up, run "
        "a command on it (launch an app or game, play something on Spotify, lock, sleep, "
        "shut down, status), or list known devices. Use for 'wake my desktop', 'on the "
        "desktop launch Valorant', 'what is my desktop doing'. For this computer use the "
        "normal tools instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["wake", "send", "status", "devices"]},
            "device": {"type": "STRING", "description": "Which computer: desktop, laptop, or all"},
            "command": {"type": "STRING",
                        "description": "For send: plain words, e.g. 'launch spotify and valorant', "
                                       "'lock', 'play lofi on spotify'"},
        },
        "required": ["action"],
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "core",
    "brief": "Other PCs: wake / send command / status / devices.",
}


def _settings_test(values: dict) -> tuple[bool, str]:
    from memory.config_manager import save_plugin_config
    save_plugin_config(NAMESPACE, values)
    s = _ntfy.settings()
    ok = _ntfy.publish("alert", f"Test from {me()} — phone alerts work.", title="JARVIS")
    net = _network()
    msg = (f"This PC is '{me()}' ({net['ip'] or '?'}, MAC {net['mac'] or '?'}). "
           f"In the ntfy app subscribe to: {s['alert_topic']} (alerts) and "
           f"{s['command_topic']} (commands).")
    return ok, ("Test notification sent ✓ " if ok else "Could not reach ntfy. ") + msg


PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "PHONE & DEVICES",
    "fields": [
        {"key": "device_name", "label": "This computer's name (desktop / laptop / anything)",
         "type": "text", "placeholder": "desktop"},
        {"key": "phone_link", "label": "Phone dashboard QR code uses (auto = Tailscale when it's on)",
         "type": "choice", "options": ["auto", "tailscale", "home wi-fi"], "default": "auto"},
        {"key": "trust_tailnet", "label": "My own Tailscale devices can connect without a key",
         "type": "toggle", "default": True},
        {"key": "tailscale_https", "label": "Secure phone link through Tailscale (HTTPS, lets the phone mic work)",
         "type": "toggle", "default": False},
        {"key": "accept_remote", "label": "Accept commands from my phone and other PCs",
         "type": "toggle", "default": True},
        {"key": "handle_untargeted", "label": "Answer phone commands that don't name a PC",
         "type": "toggle", "default": True},
        {"key": "allow_apps", "label": "Allow: open apps and games", "type": "toggle", "default": True},
        {"key": "allow_spotify", "label": "Allow: Spotify", "type": "toggle", "default": True},
        {"key": "allow_lock", "label": "Allow: lock and sleep", "type": "toggle", "default": True},
        {"key": "allow_power", "label": "Allow: shut down and restart", "type": "toggle", "default": False},
        {"key": "allow_freeform", "label": "Allow: anything else (sent to Jarvis as a request)",
         "type": "toggle", "default": False},
        {"key": "max_age_hours", "label": "Run waiting commands up to (hours old)", "type": "choice",
         "options": ["1", "3", "12"], "default": "3"},
        {"key": "announce_on", "label": "Tell my phone when this PC turns on", "type": "toggle",
         "default": True},
        {"key": "ha_wake_entity", "label": "Wake the desktop with this smart plug (Home Assistant entity)",
         "type": "text", "placeholder": "switch.desktop_plug"},
        {"key": "wake_mac", "label": "Desktop network MAC (only if it is never found by itself)",
         "type": "text", "placeholder": "a1:b2:c3:d4:e5:f6"},
        {"key": "server", "label": "ntfy server (leave empty for ntfy.sh)", "type": "text",
         "placeholder": "https://ntfy.sh"},
        {"key": "token", "label": "ntfy access token (optional)", "type": "password"},
        {"key": "alert_topic", "label": "Alerts topic (same on every device)", "type": "text"},
        {"key": "command_topic", "label": "Commands topic (same on every device)", "type": "text"},
    ],
    "action": {"label": "SEND TEST + SHOW TOPICS", "run": _settings_test},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "devices")
    device = str(parameters.get("device") or "").strip().lower() or "desktop"
    try:
        if action == "wake":
            ok, msg = wake(device)
            return outcome.started("device_wake", device=device, how=msg) if ok else \
                outcome.failed("device_wake", msg)
        if action == "send":
            cmd = str(parameters.get("command") or "").strip()
            if not cmd:
                return outcome.ask("device_send", f"What should the {device} do?")
            lines = _send(device, cmd)
            return outcome.done("device_send", device=device) + "\n" + \
                outcome.untrusted("device", "\n".join(lines))
        if action == "status":
            lines = _send(device, "status", wait=10)
            return outcome.done("device_status", device=device) + "\n" + \
                outcome.untrusted("device", "\n".join(lines))
        peers = _state.get("peers", {})
        text = "\n".join(f"{n}: last seen {time.strftime('%a %H:%M', time.localtime(p.get('seen', 0)))}"
                         for n, p in peers.items()) or "No other PCs have checked in yet."
        return outcome.done("devices", this_pc=me(), count=len(peers)) + "\n" + \
            outcome.untrusted("device", text)
    except Exception as e:
        return outcome.failed(f"device_{action}", str(e)[:180])


threading.Thread(target=_run, name="device_link", daemon=True).start()
