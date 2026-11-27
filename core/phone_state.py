"""
core/phone_state.py — the linked phone's battery, kept fresh for the hologram's gauges.

While a phone is linked, its status is asked for every few minutes (a tiny request); the HUD shows a PHONE
gauge from it. Nothing is asked when no phone is connected.
"""
from __future__ import annotations

import threading
import time

battery: float = -1.0            # 0..100, -1 = unknown / no phone
charging: bool = False
updated: float = 0.0
_started = False


def _linked() -> bool:
    try:
        from core import addons
        d = getattr(addons.assistant(), "_dashboard", None)
        return bool(d is not None and d._phones)
    except Exception:
        return False


def refresh() -> None:
    global battery, charging, updated
    from plugins import phone_control
    r = phone_control.phone("status", {}, 8)
    data = r.get("data") or {}
    if r.get("ok") and isinstance(data.get("battery"), (int, float)):
        battery = float(data["battery"])
        charging = bool(data.get("charging"))
        updated = time.time()


def _loop(period: float) -> None:
    global battery
    while True:
        try:
            if _linked():
                refresh()
            elif time.time() - updated > period * 2:
                battery = -1.0
        except Exception:
            pass
        time.sleep(period)


def start(period: float = 180.0) -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, args=(period,), daemon=True, name="phone_state").start()
