"""
actions/weather_report.py — the weather, answered (not a browser tab).

Real data from Open-Meteo through core/weather.py: now, when rain comes, today / tomorrow / the next days.
Without a city it uses the home city (setting WEATHER → city, or the city in Jarvis's memory).
"""
from core import outcome


def weather_action(parameters: dict, player=None, session_memory=None) -> str:
    from core import weather
    city = str((parameters or {}).get("city") or "").strip()
    when = str((parameters or {}).get("time") or "today").strip().lower()
    try:
        place, text = weather.report(city, when)
    except LookupError as e:
        return outcome.ask("weather", f"{e}. Which city?")
    except Exception as e:
        return outcome.failed("weather", f"the weather service didn't answer ({str(e)[:100]})")
    if player:
        try:
            player.show_content(f"WEATHER — {place}", text)
        except Exception:
            pass
    return outcome.done("weather", place=place, when=when,
                        note="say it naturally in a sentence or two (what it's like, and when rain comes, if it does)") \
        + "\n" + text


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "weather_report",
    "description": (
        "The weather from a forecast service: what it's like now, when rain is coming, and today / tomorrow / "
        "the next few days. city is optional (the user's home city is used when they don't name one); time = "
        "now, today, tomorrow or week. Use for any weather question ('do I need an umbrella', 'good for a run "
        "after 4?')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {"type": "STRING", "description": "City name; leave empty for the user's home city"},
            "time": {"type": "STRING", "enum": ["now", "today", "tomorrow", "week"]},
        },
        "required": [],
    },
    "handler": weather_action,
}
