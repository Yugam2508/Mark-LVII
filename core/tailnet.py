"""
core/tailnet.py — this PC's Tailscale address, so the phone link works away from home.

The phone dashboard's QR code used to carry the PC's home/office Wi-Fi address
(192.168.x.x). That only works while the phone is on the same Wi-Fi; at work, on
mobile data or on a network that keeps devices apart, the page never loads. With
Tailscale running on both the PC and the phone, the PC also has a 100.x.y.z
address that the phone can reach from anywhere, so the QR code uses that.

    address()      the 100.x address, '' when Tailscale is not running
    dns_name()     e.g. 'g14.tail1234.ts.net' (MagicDNS), '' when unknown
    https_url()    https://<dns_name> when `tailscale serve` already proxies the
                   dashboard; '' otherwise
    enable_https() turn that on: `tailscale serve --bg <port>`. It gives the
                   dashboard a real certificate, so the phone's browser treats the
                   page as secure and lets it use the microphone. It needs HTTPS
                   certificates switched on once in the Tailscale admin console.

Standard library + psutil (already a requirement). Every call is best-effort and
cached for a minute: it is asked from the GUI thread when the QR code opens.
"""
from __future__ import annotations

import ipaddress
import json
import os
import shutil
import subprocess
import sys
import time

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_CGNAT = ipaddress.ip_network("100.64.0.0/10")      # the range Tailscale hands out
_cache: dict = {"at": 0.0, "status": None}
_TTL = 60.0


def cli() -> str:
    """Path to the tailscale command, '' when it is not installed."""
    exe = shutil.which("tailscale")
    if exe:
        return exe
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            p = os.path.join(base, "Tailscale", "tailscale.exe")
            if os.path.exists(p):
                return p
    elif sys.platform == "darwin":
        p = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
        if os.path.exists(p):
            return p
    return ""


def _run(*args: str, timeout: float = 5) -> subprocess.CompletedProcess | None:
    exe = cli()
    if not exe:
        return None
    try:
        return subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, creationflags=_NO_WINDOW)
    except Exception:
        return None


def _interface_address() -> str:
    """A 100.64/10 address on any network adapter — works without the CLI."""
    try:
        import psutil
        import socket
        for name, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET:
                    try:
                        if ipaddress.ip_address(a.address) in _CGNAT:
                            return a.address
                    except ValueError:
                        pass
    except Exception:
        pass
    return ""


def status(refresh: bool = False) -> dict:
    """{'ip', 'dns', 'running', 'installed'} — cached for a minute."""
    now = time.time()
    if not refresh and _cache["status"] is not None and now - _cache["at"] < _TTL:
        return _cache["status"]
    out = {"ip": "", "dns": "", "running": False, "installed": bool(cli())}
    r = _run("status", "--json")
    if r is not None and r.returncode == 0 and r.stdout.strip():
        try:
            data = json.loads(r.stdout)
            me = data.get("Self") or {}
            out["running"] = data.get("BackendState") == "Running"
            for ip in me.get("TailscaleIPs") or []:
                if ":" not in ip:
                    out["ip"] = ip
                    break
            out["dns"] = str(me.get("DNSName") or "").rstrip(".")
        except ValueError:
            pass
    if not out["ip"]:
        out["ip"] = _interface_address()
        out["running"] = out["running"] or bool(out["ip"])
    _cache.update(at=now, status=out)
    return out


def address() -> str:
    s = status()
    return s["ip"] if s["running"] else ""


def dns_name() -> str:
    s = status()
    return s["dns"] if s["running"] else ""


def https_url(port: int) -> str:
    """https://<name> when `tailscale serve` is already sending HTTPS to our port."""
    name = dns_name()
    if not name:
        return ""
    r = _run("serve", "status", "--json")
    if r is None or r.returncode != 0:
        return ""
    text = r.stdout or ""
    if f"127.0.0.1:{port}" in text or f"localhost:{port}" in text:
        return f"https://{name}"
    return ""


def enable_https(port: int, backend_tls: bool = False) -> tuple[bool, str]:
    """Ask Tailscale to serve the dashboard over HTTPS on this PC's tailnet name.
    `backend_tls`: the dashboard itself speaks (self-signed) HTTPS on `port`."""
    if not cli():
        return False, "Tailscale is not installed on this PC."
    if not address():
        return False, "Tailscale is installed but not connected — open it and sign in."
    existing = https_url(port)
    if existing:
        return True, existing
    target = f"https+insecure://127.0.0.1:{port}" if backend_tls else str(port)
    r = _run("serve", "--bg", target, timeout=25)
    if r is None:
        return False, "Could not run the tailscale command."
    msg = ((r.stderr or "") + (r.stdout or "")).strip()
    if r.returncode != 0:
        low = msg.lower()
        if "https" in low and ("not enabled" in low or "disabled" in low or "enable" in low):
            return False, ("HTTPS certificates are off for your tailnet. In the Tailscale admin "
                           "console open DNS, make sure MagicDNS is on and press 'Enable HTTPS', "
                           "then try again.")
        if "access denied" in low or "permission" in low or "operator" in low:
            return False, ("Tailscale refused: run JARVIS once as administrator, or run "
                           f"'tailscale serve --bg {port}' yourself in an admin terminal.")
        return False, "tailscale serve failed: " + msg[:200]
    _cache["at"] = 0.0
    url = https_url(port) or (f"https://{dns_name()}" if dns_name() else "")
    return (True, url) if url else (False, "tailscale serve ran but reported no address.")


# ── self-check ────────────────────────────────────────────────────────────────

def report(port: int = 8000) -> list[str]:
    """Walk the chain the phone's request takes and say which link is broken.
    Run on the PC:  python -m core.tailnet   (Jarvis running, Remote Control open)."""
    import socket
    out: list[str] = []
    ok = lambda m: out.append("OK    " + m)
    bad = lambda m, fix="": out.append("FAIL  " + m + (f"\n      FIX: {fix}" if fix else ""))

    if not cli():
        bad("Tailscale is not installed on this PC.", "Install it from tailscale.com/download and sign in.")
        return out
    s = status(refresh=True)
    if not (s["running"] and s["ip"]):
        bad("Tailscale is installed but not connected on this PC.",
            "Open Tailscale from the tray and sign in (same account as the phone).")
        return out
    ok(f"Tailscale is connected: {s['ip']}" + (f"  ({s['dns']})" if s["dns"] else ""))

    # 1. Is Jarvis's dashboard listening?
    try:
        c = socket.create_connection(("127.0.0.1", port), timeout=3); c.close()
        ok(f"Jarvis's phone page is running on this PC (port {port})")
    except OSError:
        bad(f"nothing is listening on port {port}.",
            "Start Jarvis. If it is running, another copy may hold the port: close all Jarvis windows and "
            "start one. Pip packages needed: fastapi, uvicorn.")
        return out
    # 2. Does it answer on the Tailscale address itself (from this PC)?
    try:
        c = socket.create_connection((s["ip"], port), timeout=4); c.close()
        ok(f"it also answers on {s['ip']}:{port}")
    except OSError as e:
        bad(f"it does not answer on {s['ip']}:{port} ({e.__class__.__name__}).",
            "Windows is blocking it. Run the firewall fix below.")

    if sys.platform == "win32":
        # 3. Network category of the Tailscale adapter
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                "(Get-NetConnectionProfile -InterfaceAlias 'Tailscale*' "
                                "-ErrorAction SilentlyContinue).NetworkCategory"],
                               capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW)
            cat = (r.stdout or "").strip()
            if "Public" in cat:
                bad("Windows treats the Tailscale connection as a PUBLIC network, which blocks incoming connections.",
                    'PowerShell as administrator:  Set-NetConnectionProfile -InterfaceAlias "Tailscale*" -NetworkCategory Private')
            elif cat:
                ok(f"Tailscale network category: {cat}")
        except Exception:
            pass
        # 4. An allow rule for the port
        try:
            r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"],
                               capture_output=True, text=True, timeout=20, creationflags=_NO_WINDOW,
                               encoding="utf-8", errors="replace")
            blocks = [b for b in (r.stdout or "").split("\n\n") if f"{port}" in b and "Allow" in b and "TCP" in b]
            if blocks:
                ok(f"a firewall rule allows TCP {port}")
            else:
                bad(f"no firewall rule allows TCP {port}.",
                    f'PowerShell as administrator:  New-NetFirewallRule -DisplayName "JARVIS dashboard" '
                    f"-Direction Inbound -Protocol TCP -LocalPort {port},8001 -Action Allow -Profile Any")
        except Exception:
            pass
    # 5. The secure link
    https = https_url(port)
    if https:
        ok(f"secure link is on: {https}")
    else:
        out.append(f"INFO  secure link (phone microphone) is off. After enabling HTTPS in the Tailscale admin "
                   f"console, run:  tailscale serve --bg {port}")
    out.append(f"INFO  on the phone: Tailscale ON, then open  http://{s['ip']}:{port}  in Chrome")
    return out


if __name__ == "__main__":      # python -m core.tailnet
    print("\n".join(report()))
