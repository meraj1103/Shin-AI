"""
weather.py — OpenWeatherMap integration for Shin Voice Assistant
================================================================
Provides weather queries with city override support.

.env keys:
    OPENWEATHER_API_KEY  — free key from openweathermap.org
    WEATHER_CITY         — default city (e.g. "Mumbai")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def _api_key() -> str:
    return os.getenv("OPENWEATHER_API_KEY", "").strip()


def _default_city() -> str:
    return os.getenv("WEATHER_CITY", "London").strip()


def get_current_weather(city: Optional[str] = None) -> str:
    """
    Fetch current weather for *city* (defaults to WEATHER_CITY env var).
    Returns a human-readable speech string.
    """
    api_key = _api_key()
    if not api_key:
        return (
            "I don't have an OpenWeatherMap API key configured. "
            "Please add OPENWEATHER_API_KEY to your .env file."
        )

    city = (city or _default_city()).strip()

    try:
        import requests

        resp = requests.get(
            _BASE_URL,
            params={"q": city, "appid": api_key, "units": "metric"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        desc = data["weather"][0]["description"].capitalize()
        temp = round(data["main"]["temp"])
        feels = round(data["main"]["feels_like"])
        humidity = data["main"]["humidity"]
        wind_kph = round(data["wind"]["speed"] * 3.6)

        # Human-like environment comments
        comment = ""
        if "rain" in data or "drizzle" in desc.lower() or "thunderstorm" in desc.lower():
            comment = " Make sure you stay indoors or carry an umbrella, MJ!"
        elif temp >= 35:
            comment = " It is extremely hot today, MJ. Remember to stay hydrated and keep cool."
        elif temp <= 15:
            comment = " It is quite cold today, MJ. Keep warm!"

        return (
            f"In {city} it's currently {temp}°C, feels like {feels}°C. "
            f"{desc}. Humidity is {humidity}%, wind at {wind_kph} km/h.{comment}"
        )

    except Exception as exc:
        logger.warning("Weather fetch failed for '%s': %s", city, exc)
        return f"I couldn't fetch the weather for {city} right now. Please check your internet connection."


def will_it_rain(city: Optional[str] = None) -> str:
    """
    Check next 12 hours forecast to see if rain is expected.
    """
    api_key = _api_key()
    if not api_key:
        return "No OpenWeatherMap API key configured."

    city = (city or _default_city()).strip()

    try:
        import requests

        resp = requests.get(
            _FORECAST_URL,
            params={"q": city, "appid": api_key, "units": "metric", "cnt": 4},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        rain_slots = []
        for slot in data.get("list", []):
            weather_main = slot["weather"][0]["main"].lower()
            if "rain" in weather_main or "drizzle" in weather_main or "thunderstorm" in weather_main:
                import datetime
                dt = datetime.datetime.fromtimestamp(slot["dt"])
                rain_slots.append(dt.strftime("%I %p"))

        if rain_slots:
            times = ", ".join(rain_slots[:3])
            return f"Yes, rain is expected in {city} around {times}. You might want an umbrella."
        else:
            return f"No rain expected in the next 12 hours in {city}. Looks clear!"

    except Exception as exc:
        logger.warning("Rain forecast failed for '%s': %s", city, exc)
        return "I couldn't fetch the rain forecast right now."
