"""
core/rain_alert.py — "Rain in about half an hour" before it starts, not after.

While Jarvis runs (7am–9pm), the forecast for the home city is checked every 20 minutes; when the next hour
looks wet and the current one doesn't, Jarvis says so once (a card if you're busy). Not again for three hours.
Switch off in CONVERSATION & PRESENCE ("Tell me before it rains").
"""
from __future__ import annotations

import datetime as dt
import os
import threading
import time

_last = 0.0
_started = False


def coming(data: dict, now_iso: str) -> int:
    """Probability (%) of rain in the coming hour when it isn't raining now, else 0."""
    h = data.get("hourly") or {}
    times, probs = h.get("time") or [], h.get("precipitation_probability") or []
    i = next((k for k, t in enumerate(times) if t[:13] >= now_iso[:13]), None)
    if i is None or i + 1 >= len(probs):
        return 0
    now_p, next_p = probs[i] or 0, probs[i + 1] or 0
    return int(next_p) if next_p >= 70 and now_p < 40 else 0


def check(now: dt.datetime | None = None) -> str:
    """One check; returns what it said ('' when nothing)."""
    global _last
    now = now or dt.datetime.now()
    if not (7 <= now.hour < 21) or time.time() - _last < 3 * 3600:
        return ""
    from core import weather
    city = weather.home_city()
    if not city:
        return ""
    g = weather.geocode(city)
    data = weather.forecast(g["lat"], g["lon"])
    p = coming(data, (data.get("current") or {}).get("time", now.isoformat()))
    if not p:
        return ""
    _last = time.time()
    msg = f"Rain likely in {g['name']} within the hour ({p}%)."
    from core import addons
    addons.notify("RAIN SOON", msg, "Rain is about to start where the user is. Tell them in one short sentence, "
                  "like a heads-up (take a jacket / bring the washing in), nothing more.", kind="weather")
    return msg


def _loop() -> None:
    while True:
        time.sleep(20 * 60)
        try:
            from memory.config_manager import get_plugin_setting
            if get_plugin_setting("conversation", "rain_alerts", True):
                check()
        except Exception:
            pass


def start() -> None:
    global _started
    if _started or os.environ.get("JARVIS_NO_BACKGROUND") == "1":
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="rain_alert").start()
