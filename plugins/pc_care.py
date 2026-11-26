"""
plugins/pc_care.py — looking after the PC: network, updates, battery, clutter.

    "What Wi-Fi am I on?" / "what networks are around?"            wifi status / list
    "Connect to my hotspot" / "what's the Wi-Fi password?"         wifi connect / password
    "Disconnect the Wi-Fi"                                         wifi disconnect (confirm: Jarvis goes offline)
    "Are there app updates?" / "update all my apps"                updates list / install (confirm)
    "How full is the Recycle Bin?" / "empty it"                    recycle_bin status / empty (confirm)
    "Run a speed test"                                             speed_test (answers when it's done)
    "What starts with Windows?"                                    startup_apps (and opens the settings page)
    "How's my battery health?"                                     battery
    "What's my IP address?"                                        ip

Windows only for most of it (netsh, winget, PowerShell); each action says so plainly elsewhere.
Command output is passed on as data. Anything that changes the machine or drops the connection asks first.
"""
from __future__ import annotations

import os
import re
import socket
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

from core import confirm, outcome

WINDOWS = sys.platform.startswith("win")


def _run(args, timeout: int = 60) -> tuple[int, str]:
    from plugins.system_tools import _run as run
    return run(args, timeout)


def _ps(script: str, timeout: int = 60) -> tuple[int, str]:
    from plugins.system_tools import _ps as ps
    return ps(script, timeout)


def _need_windows(action: str) -> str | None:
    return None if WINDOWS else outcome.failed(action, "this only works on Windows")


# ── Wi-Fi (netsh) ─────────────────────────────────────────────────────────────

def parse_kv(out: str) -> dict:
    """'    Name   : Wi-Fi' lines -> {'name': 'Wi-Fi'} (first occurrence wins)."""
    d: dict = {}
    for line in out.splitlines():
        m = re.match(r"^\s*([^:]+?)\s+:\s(.*)$", line)
        if m:
            d.setdefault(m.group(1).strip().lower(), m.group(2).strip())
    return d


def parse_networks(out: str) -> list[dict]:
    nets, cur = [], None
    for line in out.splitlines():
        m = re.match(r"^SSID \d+\s*:\s*(.*)$", line.strip())
        if m:
            cur = {"ssid": m.group(1).strip() or "(hidden)", "signal": 0, "auth": ""}
            nets.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^\s*Signal\s*:\s*(\d+)%", line)
        if m:
            cur["signal"] = max(cur["signal"], int(m.group(1)))
        m = re.match(r"^\s*Authentication\s*:\s*(.*)$", line)
        if m and not cur["auth"]:
            cur["auth"] = m.group(1).strip()
    nets.sort(key=lambda n: -n["signal"])
    return nets


def _wifi(p: dict) -> str:
    bad = _need_windows("wifi")
    if bad:
        return bad
    what = str(p.get("what") or "status").lower()
    name = str(p.get("name") or "").strip().strip('"')
    if what == "status":
        rc, out = _run(["netsh", "wlan", "show", "interfaces"], 20)
        kv = parse_kv(out)
        if "ssid" in kv:
            return outcome.done("wifi_status", connected_to=kv.get("ssid"), signal=kv.get("signal", "?"),
                                speed_mbps=kv.get("receive rate (mbps)", "?"), band=kv.get("radio type", "?"))
        if kv.get("state", "").lower().startswith("disconnected"):
            return outcome.done("wifi_status", connected_to="nothing (Wi-Fi is on but not connected)")
        return outcome.done("wifi_status") + "\n" + outcome.untrusted("netsh", out[:1500] or "no Wi-Fi adapter")
    if what == "list":
        rc, out = _run(["netsh", "wlan", "show", "networks", "mode=bssid"], 30)
        nets = parse_networks(out)
        if not nets:
            return outcome.done("wifi_list", count=0) + "\n" + outcome.untrusted("netsh", out[:800])
        text = "\n".join(f"{n['ssid']}  {n['signal']}%  {n['auth']}" for n in nets[:15])
        return outcome.done("wifi_list", count=len(nets)) + "\n" + outcome.untrusted("wifi networks", text)
    if what == "saved":
        rc, out = _run(["netsh", "wlan", "show", "profiles"], 20)
        names = re.findall(r"All User Profile\s*:\s*(.+)", out)
        return outcome.done("wifi_saved", count=len(names)) + "\n" + outcome.untrusted("wifi", "\n".join(n.strip() for n in names) or out[:800])
    if what == "connect":
        if not name:
            return outcome.ask("wifi_connect", "Which network?")
        rc, out = _run(["netsh", "wlan", "connect", f"name={name}"], 30)
        if rc == 0 and "success" in out.lower():
            return outcome.done("wifi_connect", network=name, note="the connection may drop for a few seconds")
        return outcome.failed("wifi_connect", "Windows has no saved login for that network; join it once from the "
                              "Wi-Fi menu and then I can switch to it any time" if "no profile" in out.lower()
                              else (out.strip()[:160] or f"exit {rc}"))
    if what == "password":
        if not name:
            rc, out = _run(["netsh", "wlan", "show", "interfaces"], 20)
            name = parse_kv(out).get("profile") or parse_kv(out).get("ssid") or ""
            if not name:
                return outcome.ask("wifi_password", "Which network?")
        rc, out = _run(["netsh", "wlan", "show", "profile", f"name={name}", "key=clear"], 20)
        m = re.search(r"Key Content\s*:\s*(.+)", out)
        if not m:
            return outcome.failed("wifi_password", "Windows didn't show a password for that network (no saved "
                                  "profile, or it needs Jarvis to run as administrator)")
        return outcome.done("wifi_password", network=name, note="show it on screen rather than reading it out "
                            "if other people are around") + "\n" + outcome.untrusted("wifi password", m.group(1).strip())
    if what == "disconnect":
        def go() -> str:
            rc, out = _run(["netsh", "wlan", "disconnect"], 20)
            return outcome.done("wifi_disconnect") if rc == 0 else outcome.failed("wifi_disconnect", out[:160])
        return confirm.request("wifi:disconnect", "Disconnect Wi-Fi",
                               "Disconnect this PC from Wi-Fi. Jarvis will go offline until it reconnects.", go)
    return outcome.ask("wifi", "Status, list, saved, connect, password or disconnect?")


# ── app updates (winget) ─────────────────────────────────────────────────────

def parse_upgrades(out: str) -> list[dict]:
    lines = [l.rstrip("\r") for l in out.splitlines()]
    for i, line in enumerate(lines):
        if re.search(r"\bName\b", line) and re.search(r"\bId\b", line) and re.search(r"\bAvailable\b", line):
            id_at, ver_at, av_at = line.index("Id"), line.index("Version"), line.index("Available")
            src_at = line.index("Source") if "Source" in line else len(line) + 40
            rows = []
            for row in lines[i + 1:]:
                s = row.strip()
                if not s or set(s) <= {"-"}:
                    continue
                if re.match(r"^\d+ upgrades? available", s) or s.lower().startswith("the following packages"):
                    break
                ids = [m for m in re.finditer(r"\S+", row) if m.start() > 0 and re.match(r"^[\w.+-]+\.[\w.+-]+$", m.group())]
                if not ids:
                    continue
                pid = min(ids, key=lambda m: abs(m.start() - id_at))
                rest = row[pid.end():].split()
                rows.append({"name": row[:pid.start()].strip(), "id": pid.group(),
                             "version": rest[0] if len(rest) > 0 else "", "available": rest[1] if len(rest) > 1 else ""})
            return rows
    return []


def _updates(p: dict) -> str:
    bad = _need_windows("updates")
    if bad:
        return bad
    rc, out = _run(["winget", "upgrade", "--include-unknown", "--accept-source-agreements"], 120)
    if rc == 127:
        return outcome.failed("updates", "winget isn't installed (App Installer from the Microsoft Store)")
    ups = parse_upgrades(out)
    if str(p.get("what") or "list").lower() != "install":
        if not ups:
            return outcome.done("updates", count=0, note="everything winget knows about is up to date")
        text = "\n".join(f"{u['name']}: {u['version']} → {u['available']}" for u in ups[:25])
        return outcome.done("updates", count=len(ups)) + "\n" + outcome.untrusted("winget", text)
    if not ups:
        return outcome.done("updates_install", count=0, note="nothing to update")

    def go() -> str:
        rc2, out2 = _run(["winget", "upgrade", "--all", "--silent", "--accept-package-agreements",
                          "--accept-source-agreements", "--include-unknown"], 3600)
        tail = "\n".join(out2.strip().splitlines()[-6:])
        return (outcome.done("updates_install", count=len(ups)) if rc2 == 0 else
                outcome.failed("updates_install", f"winget ended with code {rc2}; some apps may not have updated")) \
            + "\n" + outcome.untrusted("winget", tail)

    names = ", ".join(u["name"] for u in ups[:8]) + (" …" if len(ups) > 8 else "")
    return confirm.request("updates:all", f"Update {len(ups)} apps",
                           f"Update with winget: {names}. Apps being updated may close.", go)


# ── Recycle Bin ──────────────────────────────────────────────────────────────

def _recycle_bin(p: dict) -> str:
    bad = _need_windows("recycle_bin")
    if bad:
        return bad
    rc, out = _ps("$i=@((New-Object -ComObject Shell.Application).NameSpace(10).Items()); "
                  "'COUNT=' + $i.Count; 'BYTES=' + (($i | Measure-Object -Property Size -Sum).Sum)", 60)
    count = int((re.search(r"COUNT=(\d+)", out) or [0, 0])[1])
    size = int((re.search(r"BYTES=(\d+)", out) or [0, 0])[1])
    if str(p.get("what") or "status").lower() != "empty":
        return outcome.done("recycle_bin", items=count, size_mb=round(size / 1e6, 1))
    if count == 0:
        return outcome.done("recycle_bin_empty", note="it's already empty")

    def go() -> str:
        rc2, out2 = _ps("Clear-RecycleBin -Force -ErrorAction Stop", 300)
        return outcome.done("recycle_bin_empty", freed_mb=round(size / 1e6, 1)) if rc2 == 0 else \
            outcome.failed("recycle_bin_empty", out2[:160])

    return confirm.request("recycle_bin:empty", "Empty the Recycle Bin",
                           f"Permanently delete {count} item(s), {size / 1e6:.0f} MB. They can't be restored after.", go)


# ── speed test ───────────────────────────────────────────────────────────────

SPEED_HOST = "https://speed.cloudflare.com"


def measure_speed(down_bytes: int = 25_000_000, up_bytes: int = 5_000_000) -> dict:
    import requests
    s = requests.Session()
    pings = []
    for _ in range(5):
        t = time.perf_counter()
        s.get(f"{SPEED_HOST}/__down?bytes=0", timeout=10)
        pings.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    got = 0
    with s.get(f"{SPEED_HOST}/__down?bytes={down_bytes}", stream=True, timeout=60) as r:
        for chunk in r.iter_content(65536):
            got += len(chunk)
    down_s = time.perf_counter() - t
    t = time.perf_counter()
    s.post(f"{SPEED_HOST}/__up", data=b"0" * up_bytes, timeout=60)
    up_s = time.perf_counter() - t
    return {"ping_ms": round(statistics.median(pings)), "down_mbps": round(got * 8 / down_s / 1e6, 1),
            "up_mbps": round(up_bytes * 8 / up_s / 1e6, 1)}


def _speed_test(p: dict) -> str:
    def work():
        try:
            r = measure_speed()
            msg = outcome.done("speed_test", **r)
        except Exception as e:
            msg = outcome.failed("speed_test", str(e)[:160])
        try:
            from core import addons
            addons.say("The internet speed test the user asked for has finished. Tell them the result in one "
                       "short sentence: " + msg)
            addons.show("SPEED TEST", outcome.unwrap(msg))
        except Exception:
            pass
    threading.Thread(target=work, daemon=True, name="speed-test").start()
    return outcome.started("speed_test", note="say you're running it; it takes about 15 seconds and you'll "
                                               "report the result when it's done")


# ── startup apps, battery, IP ────────────────────────────────────────────────

def _startup_apps(p: dict) -> str:
    bad = _need_windows("startup_apps")
    if bad:
        return bad
    rc, out = _ps("Get-CimInstance Win32_StartupCommand | ForEach-Object { $_.Name + ' | ' + $_.Location }", 60)
    if p.get("open"):
        try:
            os.startfile("ms-settings:startupapps")  # type: ignore[attr-defined]
        except Exception:
            pass
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return outcome.done("startup_apps", count=len(lines), note="to switch one off, open the Startup apps page "
                        "(say 'open the startup settings')") + "\n" + outcome.untrusted("startup apps", "\n".join(lines[:30]) or "none")


def battery_health(html: str) -> dict:
    def mwh(label: str) -> int:
        m = re.search(label + r"</span></td><td>\s*([\d.,\s]+)\s*mWh", html, re.I)
        return int(re.sub(r"[^\d]", "", m.group(1))) if m else 0
    design, full = mwh("DESIGN CAPACITY"), mwh("FULL CHARGE CAPACITY")
    out = {"design_mwh": design, "full_mwh": full}
    if design and full:
        out["health_pct"] = round(full * 100 / design)
    cyc = re.search(r"CYCLE COUNT</span></td><td>\s*(\d+)", html, re.I)
    if cyc:
        out["cycles"] = int(cyc.group(1))
    return out


def _battery(p: dict) -> str:
    facts: dict = {}
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return outcome.done("battery", note="this PC has no battery (a desktop)")
        facts.update(percent=round(b.percent), plugged_in=bool(b.power_plugged))
        if not b.power_plugged and b.secsleft not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
            facts["time_left"] = f"{b.secsleft // 3600}h {b.secsleft % 3600 // 60}m"
    except Exception as e:
        facts["note"] = f"no battery reading ({e})"
    if WINDOWS:
        path = Path(tempfile.gettempdir()) / "jarvis-battery-report.html"
        rc, out = _run(["powercfg", "/batteryreport", "/output", str(path)], 60)
        try:
            facts.update(battery_health(path.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            pass
    return outcome.done("battery", **facts)


def _ip(p: dict) -> str:
    facts: dict = {}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))            # picks the outgoing interface; nothing is sent
            facts["local"] = s.getsockname()[0]
    except OSError:
        facts["local"] = "offline"
    try:
        from core import tailnet
        a = tailnet.address()
        if a:
            facts["tailscale"] = a
    except Exception:
        pass
    try:
        import requests
        facts["public"] = requests.get("https://api.ipify.org", timeout=6).text.strip()[:45]
    except Exception:
        facts["public"] = "unknown (no internet?)"
    return outcome.done("ip", **facts)


_ACTIONS = {
    "wifi": _wifi, "updates": _updates, "recycle_bin": _recycle_bin, "speed_test": _speed_test,
    "startup_apps": _startup_apps, "battery": _battery, "ip": _ip,
}

PLUGIN = {
    "name": "pc_care",
    "description": (
        "Looks after this PC: Wi-Fi (wifi with what=status / list / saved / connect + name / password + name / "
        "disconnect), app updates through winget (updates: what=list, or install to update everything, asks first), "
        "the Recycle Bin (status, or what=empty, asks first), an internet speed test (speed_test; answers when "
        "done), what starts with Windows (startup_apps; open=true opens the settings page), battery level and "
        "health (battery), and IP addresses (ip: local, Tailscale, public). For CPU/GPU/memory use system_insight."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": list(_ACTIONS)},
            "what": {"type": "STRING", "description": "Sub-action: for wifi status/list/saved/connect/password/"
                                                      "disconnect; for updates list/install; for recycle_bin status/empty"},
            "name": {"type": "STRING", "description": "For wifi connect/password: the network name"},
            "open": {"type": "BOOLEAN", "description": "For startup_apps: also open the Startup apps settings page"},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "PC care: Wi-Fi, app updates, Recycle Bin, speed test, startup apps, battery, IP.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action") or "").lower()
    fn = _ACTIONS.get(action)
    if fn is None:
        return outcome.failed("pc_care", f"unknown action {action}")
    try:
        return fn(parameters)
    except Exception as e:
        return outcome.failed(action, str(e)[:160])
