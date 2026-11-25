"""
plugins/_ntfy.py — the channel between your phone and your PCs, through ntfy.

ntfy (https://ntfy.sh, free, open source) delivers short messages to "topics".
JARVIS uses two private topics:

    alerts topic    PCs -> phone   notifications (plugins/phone_alerts.py)
    command topic   phone -> PCs   and PC -> PC commands (plugins/device_link.py)

The topic name is the password: anyone who knows it can read and post. So the
names are long and random, generated once, and shared only with your own
devices. Commands that arrive are also limited by each PC's permissions, and the
risky ones (shutting down, free-form requests) are off unless you switch them on.
If you run your own ntfy server or have an ntfy account, set the server address
and an access token in settings and nothing goes through the public server.

SHARING THE TOPICS BETWEEN YOUR PCS
    With device sync on (OneDrive), the topics are written to the sync folder and
    every PC picks them up by itself. Otherwise copy them from ⚙ → PLUGIN
    SETTINGS → PHONE & DEVICES on one PC into the same fields on the other.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Callable

from memory.config_manager import get_plugin_config, save_plugin_config

NAMESPACE = "phone_link"
DEFAULT_SERVER = "https://ntfy.sh"
_lock = threading.Lock()


def _shared_file() -> Path | None:
    """link.json in the device-sync folder, when device sync is on."""
    try:
        from plugins import device_sync
        folder = device_sync._folder()
        return folder / "link.json" if folder else None
    except Exception:
        return None


def settings() -> dict:
    """Server, token and the two topics — creating the topics on first use."""
    with _lock:
        cfg = get_plugin_config(NAMESPACE)
        shared = _shared_file()
        if shared and shared.exists():
            try:
                data = json.loads(shared.read_text(encoding="utf-8"))
                for k in ("alert_topic", "command_topic"):
                    if data.get(k) and not cfg.get(k):
                        cfg[k] = data[k]
                save_plugin_config(NAMESPACE, {k: cfg[k] for k in ("alert_topic", "command_topic")
                                               if cfg.get(k)})
            except (OSError, ValueError):
                pass
        changed = {}
        for k, prefix in (("alert_topic", "jarvis-alerts-"), ("command_topic", "jarvis-cmd-")):
            if not str(cfg.get(k) or "").strip():
                cfg[k] = changed[k] = prefix + secrets.token_urlsafe(18).replace("_", "x").replace("-", "y")
        if changed:
            save_plugin_config(NAMESPACE, changed)
            if shared:
                try:
                    shared.parent.mkdir(parents=True, exist_ok=True)
                    shared.write_text(json.dumps({"alert_topic": cfg["alert_topic"],
                                                  "command_topic": cfg["command_topic"]}),
                                      encoding="utf-8")
                except OSError:
                    pass
        return {
            "server": str(cfg.get("server") or DEFAULT_SERVER).rstrip("/"),
            "token": str(cfg.get("token") or "").strip(),
            "alert_topic": cfg["alert_topic"],
            "command_topic": cfg["command_topic"],
        }


def _headers(s: dict) -> dict:
    return {"Authorization": f"Bearer {s['token']}"} if s["token"] else {}


def publish(topic_kind: str, message: str, *, title: str = "", priority: int = 3,
            tags: list[str] | None = None, click: str = "", actions: list | None = None) -> bool:
    """Post to the 'alert' or 'command' topic. True when ntfy accepted it."""
    import requests
    s = settings()
    topic = s["alert_topic"] if topic_kind == "alert" else s["command_topic"]
    body = {"topic": topic, "message": message[:3800], "priority": int(priority)}
    if title:
        body["title"] = title[:200]
    if tags:
        body["tags"] = tags
    if click:
        body["click"] = click
    if actions:
        body["actions"] = actions[:3]
    try:
        r = requests.post(s["server"], json=body, headers=_headers(s), timeout=10)
        return r.status_code < 300
    except Exception as e:
        print(f"[ntfy] publish failed: {e}")
        return False


def poll(topic_kind: str, since: str) -> list[dict]:
    """Cached messages on a topic since a message id or a duration like '3h'."""
    import requests
    s = settings()
    topic = s["alert_topic"] if topic_kind == "alert" else s["command_topic"]
    r = requests.get(f"{s['server']}/{topic}/json", params={"poll": "1", "since": since},
                     headers=_headers(s), timeout=15)
    out = []
    for line in r.text.splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("event") == "message":
            out.append(m)
    return out


def listen(topic_kind: str, on_message: Callable[[dict], None], stop: threading.Event,
           since: str = "") -> None:
    """Stream new messages forever (reconnecting), calling on_message for each."""
    import requests
    backoff = 5
    while not stop.is_set():
        s = settings()
        topic = s["alert_topic"] if topic_kind == "alert" else s["command_topic"]
        try:
            params = {"since": since} if since else {}
            with requests.get(f"{s['server']}/{topic}/json", params=params, stream=True,
                              headers=_headers(s), timeout=(10, 90)) as r:
                backoff = 5
                for line in r.iter_lines(decode_unicode=True):
                    if stop.is_set():
                        return
                    if not line:
                        continue
                    try:
                        m = json.loads(line)
                    except ValueError:
                        continue
                    if m.get("event") == "message":
                        since = m.get("id", since)
                        try:
                            on_message(m)
                        except Exception as e:
                            print(f"[ntfy] handler: {e}")
        except Exception:
            pass  # timeouts and dropped connections are normal; reconnect
        stop.wait(backoff)
        backoff = min(backoff * 2, 120)
