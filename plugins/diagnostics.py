"""
plugins/diagnostics.py — "Jarvis, run diagnostics."

A quick check-up of the whole setup, like the suit's status readout: processor, graphics card, memory,
disks, temperatures, battery, the internet and how fast it answers, Tailscale, the phone link, the last
backup, and whether the wake word is ready. Each line is OK, WATCH or PROBLEM; the panel shows them all and
Jarvis says only what needs attention ("all systems normal, except C: is 94% full"). Takes a few seconds,
makes no changes. For a deeper look at one thing use system_insight or pc_care.
"""
from __future__ import annotations

import socket
import time

from core import outcome

OK, WATCH, BAD = "OK", "WATCH", "PROBLEM"


def _check(name: str, fn) -> tuple[str, str, str]:
    try:
        level, text = fn()
        return level, name, text
    except Exception as e:
        return WATCH, name, f"couldn't check ({str(e)[:80]})"


def _cpu():
    import psutil
    pct = psutil.cpu_percent(interval=0.5)
    level = BAD if pct > 95 else WATCH if pct > 80 else OK
    temps = ""
    try:
        t = psutil.sensors_temperatures() or {}
        vals = [x.current for v in t.values() for x in v if getattr(x, "current", None)]
        if vals:
            hot = max(vals)
            temps = f", {hot:.0f} °C"
            level = BAD if hot >= 95 else (WATCH if hot >= 85 and level == OK else level)
    except Exception:
        pass
    return level, f"{pct:.0f}% busy{temps}, {psutil.cpu_count()} threads"


def _memory():
    import psutil
    m = psutil.virtual_memory()
    level = BAD if m.percent > 95 else WATCH if m.percent > 85 else OK
    return level, f"{m.percent:.0f}% used ({m.used / 1e9:.1f} of {m.total / 1e9:.0f} GB)"


def _gpu():
    from plugins import system_insight
    g = system_insight._gpu_totals()
    if not g:
        return OK, "no NVIDIA card readings (fine on integrated graphics)"
    level = OK
    t = g.get("temp_c")
    if t is not None:
        level = BAD if t >= 90 else WATCH if t >= 82 else OK
    return level, (f"{g.get('name', 'GPU')}: {g.get('util', 0)}% busy, "
                   f"{g.get('vram_used_mb', 0)}/{g.get('vram_total_mb', 0)} MB"
                   + (f", {t} °C" if t is not None else ""))


def _disks():
    import psutil
    worst, parts = OK, []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
        except OSError:
            continue
        lvl = BAD if u.percent >= 95 else WATCH if u.percent >= 88 else OK
        if lvl != OK or len(parts) < 4:
            parts.append(f"{p.mountpoint.rstrip(chr(92))} {u.percent:.0f}% ({u.free / 1e9:.0f} GB free)")
        worst = BAD if BAD in (worst, lvl) else WATCH if WATCH in (worst, lvl) else OK
    return worst, ", ".join(parts) or "no disks found"


def _battery():
    import psutil
    b = psutil.sensors_battery()
    if b is None:
        return OK, "on mains (no battery)"
    level = WATCH if (b.percent < 20 and not b.power_plugged) else OK
    return level, f"{b.percent:.0f}%{' charging' if b.power_plugged else ' on battery'}"


def _internet():
    t = time.perf_counter()
    with socket.create_connection(("1.1.1.1", 443), timeout=4):
        pass
    ms = (time.perf_counter() - t) * 1000
    level = WATCH if ms > 250 else OK
    return level, f"online, {ms:.0f} ms to the internet"


def _tailscale():
    from core import tailnet
    s = tailnet.status()
    if s.get("running") and s.get("ip"):
        return OK, f"running at {s['ip']}"
    return (WATCH, "not running: your phone can't reach Jarvis away from home") if s.get("installed") else \
        (WATCH, "not installed")


def _phone():
    from core import addons
    d = getattr(addons.assistant(), "_dashboard", None)
    if d is None:
        return WATCH, "the phone link is off"
    phones = [p.get("name", "phone") for p in getattr(d, "_phones", {}).values()]
    return OK, ("linked: " + ", ".join(phones)) if phones else "ready, no phone connected right now"


def _backup():
    from plugins import backup
    bs = backup.backups()
    if not bs:
        return WATCH, "no backup yet (say 'back up Jarvis')"
    hours = (time.time() - bs[-1].stat().st_mtime) / 3600
    return (WATCH if hours > 48 else OK), f"last one {hours:.0f} h ago"


GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini():
    """Is the Gemini key answering? The same plain reasons as the on-screen connection errors."""
    from memory.config_manager import load_api_keys
    key = str(load_api_keys().get("gemini_api_key") or "")
    if not key:
        return BAD, "no Gemini key set"
    import requests
    r = requests.get(GEMINI_MODELS_URL, params={"key": key, "pageSize": 1}, timeout=8)
    if r.status_code == 200:
        return OK, "the key answers"
    from core import apihealth
    kind, msg = apihealth.diagnose(f"{r.status_code} {r.text[:300]}")
    return (WATCH if kind in ("overloaded", "network") else BAD), msg


def _wake():
    from core import wake_word
    return (OK, "ready") if wake_word.is_ready() else (WATCH, "not set up (CONTROLS → WAKE WORD)")


CHECKS = [("Processor", _cpu), ("Memory", _memory), ("Graphics", _gpu), ("Disks", _disks),
          ("Battery", _battery), ("Internet", _internet), ("Gemini key", _gemini), ("Tailscale", _tailscale),
          ("Phone link", _phone), ("Backups", _backup), ("Wake word", _wake)]


def diagnose() -> list[tuple[str, str, str]]:
    return [_check(name, fn) for name, fn in CHECKS]


PLUGIN = {
    "name": "diagnostics",
    "description": (
        "Runs a full diagnostic of the PC and Jarvis's own links in a few seconds: processor, memory, graphics, "
        "disks, temperatures, battery, internet latency, Tailscale, the phone link, backups, the wake word. Use "
        "for 'run diagnostics', 'system status', 'how's everything looking', 'is anything wrong with my PC'. "
        "Say only what needs attention, briefly, like a status readout ('all systems normal' if nothing does)."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    "tier": "core",
    "brief": "Full system diagnostic readout.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    rows = diagnose()
    icon = {OK: "●", WATCH: "▲", BAD: "■"}
    text = "\n".join(f"{icon[lvl]} {name.upper():<11} {msg}" for lvl, name, msg in rows)
    attention = [f"{name}: {msg}" for lvl, name, msg in rows if lvl != OK]
    if player:
        try:
            player.show_content("DIAGNOSTICS", text)
        except Exception:
            pass
    return outcome.done("diagnostics", problems=sum(1 for r in rows if r[0] == BAD),
                        watch=sum(1 for r in rows if r[0] == WATCH),
                        needs_attention="; ".join(attention) or "nothing — all systems normal") \
        + "\n" + outcome.untrusted("diagnostics", text)
