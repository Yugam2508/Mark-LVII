"""
core/weather.py — real weather, from Open-Meteo (free, no key, no account).

The old weather tool only opened a Google search in the browser. This one answers: what it's like now,
when the rain comes, today / tomorrow / the next few days. The city is the one asked about, else the
user's home city (CONVERSATION & PRESENCE → Home city, or the city in Jarvis's memory).
"""
from __future__ import annotations

import time

GEO = "https://geocoding-api.open-meteo.com/v1/search"
API = "https://api.open-meteo.com/v1/forecast"
_cache: dict = {}

WMO = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers", 81: "showers",
    82: "heavy showers", 85: "snow showers", 86: "heavy snow showers", 95: "thunderstorms",
    96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


def words(code) -> str:
    try:
        return WMO.get(int(code), "mixed")
    except (TypeError, ValueError):
        return "mixed"


def home_city() -> str:
    try:
        from memory.config_manager import get_plugin_setting
        c = str(get_plugin_setting("conversation", "home_city", "") or "").strip() or \
            str(get_plugin_setting("daily_briefing", "city", "") or "").strip()
        if c:
            return c
    except Exception:
        pass
    try:
        from memory.memory_manager import load_memory
        ident = load_memory().get("identity", {}) or {}
        for k in ("city", "home_city", "location", "hometown"):
            v = ident.get(k)
            v = v.get("value") if isinstance(v, dict) else v
            if v:
                return str(v).split(",")[0].strip()
    except Exception:
        pass
    return ""


def geocode(city: str) -> dict:
    import requests
    key = ("geo", city.lower())
    if key in _cache:
        return _cache[key]
    r = requests.get(GEO, params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=10)
    r.raise_for_status()
    res = (r.json().get("results") or [])
    if not res:
        raise LookupError(f"no place called {city}")
    g = res[0]
    out = {"lat": g["latitude"], "lon": g["longitude"], "name": g.get("name", city),
           "country": g.get("country", ""), "tz": g.get("timezone", "auto")}
    _cache[key] = out
    return out


def forecast(lat: float, lon: float) -> dict:
    import requests
    key = ("fc", round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    r = requests.get(API, params={
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 4,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
    }, timeout=10)
    r.raise_for_status()
    data = r.json()
    _cache[key] = (time.time(), data)
    return data


def rain_window(data: dict, hours: int = 12) -> str:
    """'rain likely from 15:00 to 18:00' for the next hours, or ''."""
    h = data.get("hourly") or {}
    times, probs = h.get("time") or [], h.get("precipitation_probability") or []
    now = (data.get("current") or {}).get("time", "")
    start = next((i for i, t in enumerate(times) if t >= now), 0)
    wet = [i for i in range(start, min(len(times), start + hours)) if (probs[i] or 0) >= 50]
    if not wet:
        return ""
    end_h = (int(times[wet[-1]][11:13]) + 1) % 24          # the end of the last wet hour
    return f"rain likely from {times[wet[0]][11:16]} until about {end_h:02d}:00 (up to {max(probs[i] for i in wet)}%)"


def report(city: str = "", when: str = "today") -> tuple[str, str]:
    """(place, text) — a short readout for today / tomorrow / week."""
    city = (city or "").strip() or home_city()
    if not city:
        raise LookupError("no city: say which city, or tell me your home city once")
    g = geocode(city)
    d = forecast(g["lat"], g["lon"])
    cur, day = d.get("current") or {}, d.get("daily") or {}
    place = f"{g['name']}, {g['country']}".strip(", ")
    lines = []

    def day_line(i: int, label: str) -> str:
        return (f"{label}: {words(day['weather_code'][i])}, {round(day['temperature_2m_min'][i])}–"
                f"{round(day['temperature_2m_max'][i])}°C, rain chance {day['precipitation_probability_max'][i]}%")

    w = (when or "today").lower()
    if w in ("now", "today", "", "current"):
        lines.append(f"Now: {words(cur.get('weather_code'))}, {round(cur.get('temperature_2m', 0))}°C "
                     f"(feels {round(cur.get('apparent_temperature', 0))}°C), wind {round(cur.get('wind_speed_10m', 0))} km/h")
        rw = rain_window(d)
        lines.append(rw.capitalize() if rw else "No rain expected in the next 12 hours")
        lines.append(day_line(0, "Today"))
        lines.append(f"Sunset {str(day['sunset'][0])[11:16]}")
    elif w == "tomorrow":
        lines.append(day_line(1, "Tomorrow"))
        lines.append(f"Sunrise {str(day['sunrise'][1])[11:16]}, sunset {str(day['sunset'][1])[11:16]}")
    else:
        for i, label in enumerate(("Today", "Tomorrow", "Day after", "Then")):
            if i < len(day.get("weather_code") or []):
                lines.append(day_line(i, label))
    return place, "\n".join(lines)
