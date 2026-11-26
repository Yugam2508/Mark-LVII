"""
plugins/system_insight.py — "what's using my GPU?", "why is it slow?", "what's on port 8000?".

    "What's using my GPU right now?"                 gpu      (per program, plus video memory)
    "What's eating my CPU / memory / disk?"          top      by=cpu|memory|disk
    "Is Chrome running?" / "how much is it using?"   find
    "What's using port 8000?"                        port
    "How full are my drives?"                        disks
    "What's using the network?"                      network
    "Close Chrome" / "kill that process"             end      (asks you to confirm)

The old system_status tool only returned totals, so any "which program…" question got "I can't
see that". This looks at individual processes: CPU and memory from the operating system, GPU per
program the way Task Manager does it (Windows' GPU Engine counters), and the GPU's own totals
from NVIDIA's NVML when there is one.

ENDING PROCESSES always asks for your confirmation, refuses Windows' own critical processes and
Jarvis itself, and — if Windows says access is denied — can retry through the normal Windows
"do you want to allow this app to make changes?" prompt, so the permission is yours to give
each time rather than Jarvis running with administrator rights all the time.
Process names, command lines and window titles come from other programs and are treated as data.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

from core import addons, outcome

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_CRITICAL = {"system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
             "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe", "memory compression",
             "secure system", "init", "systemd", "kthreadd", "launchd", "kernel_task"}
_last: list[dict] = []


# ── processes ─────────────────────────────────────────────────────────────────

def _procs(sample: float = 0.6) -> list[dict]:
    import psutil
    ps = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            ps.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(sample)
    out = []
    ncpu = psutil.cpu_count() or 1
    for p in ps:
        try:
            with p.oneshot():
                mem = p.memory_info()
                try:
                    io = p.io_counters()
                    iob = io.read_bytes + io.write_bytes
                except (psutil.AccessDenied, AttributeError):
                    iob = 0
                out.append({"pid": p.pid, "name": p.info.get("name") or "?", "cpu": round(p.cpu_percent(None) / ncpu, 1),
                            "mem_mb": round(mem.rss / 1048576), "io": iob})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return out


def _group(procs: list[dict]) -> list[dict]:
    """Browsers and games run dozens of processes: add them up per program name."""
    by: dict[str, dict] = {}
    for p in procs:
        g = by.setdefault(p["name"].lower(), {"name": p["name"], "pids": [], "cpu": 0.0, "mem_mb": 0, "io": 0, "gpu": 0.0, "vram_mb": 0})
        g["pids"].append(p["pid"]); g["cpu"] += p["cpu"]; g["mem_mb"] += p["mem_mb"]; g["io"] += p.get("io", 0)
        g["gpu"] += p.get("gpu", 0.0); g["vram_mb"] += p.get("vram_mb", 0)
    return list(by.values())


# ── GPU ───────────────────────────────────────────────────────────────────────

_GPU_PS = ("$e = (Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples | "
           "Where-Object { $_.CookedValue -gt 0 } | ForEach-Object { \"E|$($_.InstanceName)|$($_.CookedValue)\" }; "
           "$m = (Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage' -ErrorAction SilentlyContinue).CounterSamples | "
           "Where-Object { $_.CookedValue -gt 0 } | ForEach-Object { \"M|$($_.InstanceName)|$($_.CookedValue)\" }; "
           "$e; $m")


def parse_gpu_counters(text: str) -> dict[int, dict]:
    """Windows' 'GPU Engine' / 'GPU Process Memory' counter lines -> {pid: {'gpu': %, 'vram_mb': MB}}.
    Instance names look like 'pid_1234_luid_0x…_phys_0_eng_0_engtype_3D'."""
    out: dict[int, dict] = {}
    for line in text.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3 or parts[0] not in ("E", "M"):
            continue
        m = re.search(r"pid_(\d+)", parts[1])
        if not m:
            continue
        try:
            val = float(parts[2])
        except ValueError:
            continue
        d = out.setdefault(int(m.group(1)), {"gpu": 0.0, "vram_mb": 0.0})
        if parts[0] == "E":
            d["gpu"] += val
        else:
            d["vram_mb"] += val / 1048576.0
    for d in out.values():
        d["gpu"] = round(min(d["gpu"], 100.0), 1)
        d["vram_mb"] = round(d["vram_mb"])
    return out


def _gpu_per_process() -> dict[int, dict]:
    if sys.platform == "win32":
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _GPU_PS],
                               capture_output=True, text=True, timeout=25, creationflags=_NO_WINDOW,
                               encoding="utf-8", errors="replace")
            return parse_gpu_counters(r.stdout or "")
        except Exception:
            return {}
    try:                                                    # Linux with NVIDIA: compute processes only
        r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        return {int(a.split(",")[0]): {"gpu": 0.0, "vram_mb": float(a.split(",")[1])}
                for a in (r.stdout or "").strip().splitlines() if "," in a}
    except Exception:
        return {}


def _gpu_totals() -> dict:
    """{'name', 'util', 'vram_used_mb', 'vram_total_mb', 'temp_c', 'power_w'} from NVML, {} without one."""
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(h)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        out = {"name": name.decode() if isinstance(name, bytes) else str(name),
               "util": pynvml.nvmlDeviceGetUtilizationRates(h).gpu,
               "vram_used_mb": round(mem.used / 1048576), "vram_total_mb": round(mem.total / 1048576)}
        try:
            out["temp_c"] = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            out["power_w"] = round(pynvml.nvmlDeviceGetPowerUsage(h) / 1000)
        except Exception:
            pass
        return out
    except Exception:
        return {}


def gpu_report() -> tuple[str, list[dict]]:
    totals = _gpu_totals()
    per = _gpu_per_process()
    procs = _procs(0.1)
    for p in procs:
        g = per.get(p["pid"])
        if g:
            p["gpu"], p["vram_mb"] = g["gpu"], g["vram_mb"]
    groups = [g for g in _group(procs) if g["gpu"] > 0 or g["vram_mb"] > 0]
    groups.sort(key=lambda g: (g["gpu"], g["vram_mb"]), reverse=True)
    lines = []
    if totals:
        lines.append(f"{totals['name']}: {totals['util']}% busy, video memory {totals['vram_used_mb']} of "
                     f"{totals['vram_total_mb']} MB" + (f", {totals['temp_c']}°C" if "temp_c" in totals else "")
                     + (f", {totals['power_w']} W" if "power_w" in totals else ""))
    else:
        lines.append("No GPU totals available (no NVIDIA driver found)")
    for i, g in enumerate(groups[:8], 1):
        lines.append(f"{i}. {g['name']} — GPU {g['gpu']:.0f}%, video memory {g['vram_mb']} MB ({len(g['pids'])} process"
                     f"{'es' if len(g['pids']) != 1 else ''})")
    if len(lines) == 1 and totals:
        lines.append("No program is using the GPU right now" if totals.get("util", 0) < 5 else
                     "The GPU is busy but Windows didn't report which program (it can hide system and driver work)")
    return "\n".join(lines), groups


# ── processes: end, find, ports ───────────────────────────────────────────────

def critical_reason(name: str, pid: int) -> str:
    if name.lower() in _CRITICAL:
        return f"{name} is part of the operating system"
    if pid in (os.getpid(), os.getppid()):
        return "that's Jarvis itself"
    return ""


def _elevated_kill(pid: int) -> tuple[bool, str]:
    """taskkill through Windows' own 'allow this app to make changes?' prompt (UAC)."""
    if sys.platform != "win32":
        return False, "I can't raise permissions on this system"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            f"Start-Process taskkill -ArgumentList '/F','/PID','{int(pid)}' -Verb RunAs -Wait"],
                           capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW)
        return r.returncode == 0, (r.stderr or "").strip()[:150]
    except subprocess.TimeoutExpired:
        return False, "the permission prompt wasn't answered in time"
    except Exception as e:
        return False, str(e)[:150]


def end_process(pids: list[int], label: str) -> str:
    import psutil
    ended, denied = 0, []
    for pid in pids:
        try:
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(3)
            except psutil.TimeoutExpired:
                p.kill()
            ended += 1
        except psutil.NoSuchProcess:
            ended += 1
        except psutil.AccessDenied:
            denied.append(pid)
    if denied:
        ok, err = _elevated_kill(denied[0]) if len(denied) == 1 else (False, "")
        if ok:
            ended += 1
            denied = []
    if denied:
        return outcome.failed("end_process", f"Windows denied permission for {len(denied)} process(es); "
                              "they need administrator rights" + (f" ({err})" if err else ""),
                              ended=ended, label=label)
    return outcome.done("end_process", ended=ended, label=label)


def _by_name(name: str) -> list[dict]:
    n = name.lower().strip().removesuffix(".exe")
    return [g for g in _group(_procs(0.1)) if n and n in g["name"].lower().removesuffix(".exe")]


def port_users(port: int) -> list[dict]:
    import psutil
    out = []
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.laddr and c.laddr.port == port and c.pid:
                try:
                    out.append({"pid": c.pid, "name": psutil.Process(c.pid).name(), "status": c.status})
                except psutil.NoSuchProcess:
                    pass
    except (psutil.AccessDenied, PermissionError):
        return []
    return out


def disks() -> list[str]:
    import psutil
    out = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
        except OSError:
            continue
        out.append(f"{p.mountpoint} — {u.used / 1e9:.0f} of {u.total / 1e9:.0f} GB used ({u.percent:.0f}%), "
                   f"{u.free / 1e9:.0f} GB free")
    return out


def network() -> list[str]:
    import psutil
    a = psutil.net_io_counters()
    time.sleep(1.0)
    b = psutil.net_io_counters()
    down, up = (b.bytes_recv - a.bytes_recv) / 1024, (b.bytes_sent - a.bytes_sent) / 1024
    counts: dict[str, int] = {}
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.pid and c.status == "ESTABLISHED":
                try:
                    n = psutil.Process(c.pid).name()
                    counts[n] = counts.get(n, 0) + 1
                except psutil.NoSuchProcess:
                    pass
    except (psutil.AccessDenied, PermissionError):
        pass
    lines = [f"Right now: {down:.0f} KB/s down, {up:.0f} KB/s up"]
    for name, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:6]:
        lines.append(f"{name}: {n} open connection(s)")
    return lines


# ── the tool ──────────────────────────────────────────────────────────────────

PLUGIN = {
    "name": "system_insight",
    "description": (
        "Look inside this computer: WHICH programs are using the GPU, CPU, memory, disk or network; whether a "
        "program is running and how much it uses; what is using a port; how full the drives are; and close a "
        "program (with the user's confirmation). Use for 'what's using my GPU', 'why is my PC slow', 'what's "
        "eating my RAM', 'is X running', 'what's on port 8000', 'close Chrome', 'kill that'. For overall totals "
        "only, system_status is enough. Never say you can't see this: use this tool."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["gpu", "top", "find", "port", "disks", "network", "end"]},
            "by": {"type": "STRING", "enum": ["cpu", "memory", "disk"], "description": "For top"},
            "name": {"type": "STRING", "description": "For find/end: the program name, e.g. chrome"},
            "item_number": {"type": "INTEGER", "description": "For end: number from the last list"},
            "port": {"type": "INTEGER", "description": "For port"},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Which programs use GPU/CPU/RAM/disk/network/ports; close a program.",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    global _last
    action = str(parameters.get("action") or "top")
    try:
        if action == "gpu":
            text, groups = gpu_report()
            _last = groups
            addons.show("GPU", text)
            return outcome.done("gpu") + "\n" + outcome.untrusted("system", text)
        if action == "top":
            by = str(parameters.get("by") or "cpu")
            groups = _group(_procs())
            key = {"cpu": "cpu", "memory": "mem_mb", "disk": "io"}.get(by, "cpu")
            groups.sort(key=lambda g: g[key], reverse=True)
            _last = groups[:8]
            lines = [f"{i}. {g['name']} — CPU {g['cpu']:.0f}%, memory {g['mem_mb']} MB, "
                     f"{len(g['pids'])} process{'es' if len(g['pids']) != 1 else ''}" for i, g in enumerate(_last, 1)]
            text = f"Top by {by}:\n" + "\n".join(lines)
            addons.show(f"TOP — {by.upper()}", text)
            return outcome.done("top", by=by) + "\n" + outcome.untrusted("system", text)
        if action == "find":
            name = str(parameters.get("name") or "").strip()
            if not name:
                return outcome.ask("find_process", "Which program?")
            found = _by_name(name)
            _last = found
            if not found:
                return outcome.done("find_process", running=False, name=name)
            text = "\n".join(f"{i}. {g['name']} — CPU {g['cpu']:.0f}%, memory {g['mem_mb']} MB, {len(g['pids'])} process(es)"
                             for i, g in enumerate(found[:6], 1))
            return outcome.done("find_process", running=True) + "\n" + outcome.untrusted("system", text)
        if action == "port":
            port = int(parameters.get("port") or 0)
            if not 1 <= port <= 65535:
                return outcome.ask("port", "Which port number?")
            users = port_users(port)
            text = "\n".join(f"{u['name']} (pid {u['pid']}, {u['status']})" for u in users) or "nothing is using it"
            return outcome.done("port", port=port, in_use=bool(users)) + "\n" + outcome.untrusted("system", text)
        if action == "disks":
            return outcome.done("disks") + "\n" + outcome.untrusted("system", "\n".join(disks()))
        if action == "network":
            return outcome.done("network") + "\n" + outcome.untrusted("system", "\n".join(network()))
        if action == "end":
            target = None
            n = parameters.get("item_number")
            if n is not None and 1 <= int(n) <= len(_last):
                target = _last[int(n) - 1]
            elif parameters.get("name"):
                hits = _by_name(str(parameters["name"]))
                target = hits[0] if len(hits) == 1 else None
                if len(hits) > 1:
                    _last = hits
                    return outcome.ask("end_process", "Which one? " + ", ".join(f"{i}. {h['name']}" for i, h in enumerate(hits[:6], 1)))
            if target is None:
                return outcome.ask("end_process", "Which program should I close?")
            for pid in target["pids"]:
                why = critical_reason(target["name"], pid)
                if why:
                    return outcome.failed("end_process", f"I won't end that: {why}")
            from core import confirm
            pids = list(target["pids"])
            return confirm.request(f"end_process:{target['name']}", f"Close {target['name']}",
                                   f"End {target['name']} ({len(pids)} process{'es' if len(pids) != 1 else ''}, "
                                   f"{target['mem_mb']} MB). Unsaved work in it will be lost.",
                                   lambda: end_process(pids, target["name"]))
        return outcome.failed("system_insight", f"unknown action {action}")
    except Exception as e:
        return outcome.failed(f"system_{action}", str(e)[:160])
