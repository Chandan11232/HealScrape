"""Live weather via Open-Meteo (no API key). Used for forecast questions, not RAG."""
from __future__ import annotations

import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

_http = httpx.Client(timeout=15.0)


def _wmo(code: int | None) -> str:
    if code is None:
        return "unknown conditions"
    return WMO.get(int(code), f"weather code {code}")


def geocode(place: str) -> dict | None:
    resp = _http.get(
        GEOCODE_URL,
        params={"name": place, "count": 1, "language": "en", "format": "json"},
    )
    resp.raise_for_status()
    results = (resp.json() or {}).get("results") or []
    if not results:
        return None
    hit = results[0]
    return {
        "name": hit.get("name") or place,
        "country": hit.get("country") or "",
        "admin1": hit.get("admin1") or "",
        "latitude": hit["latitude"],
        "longitude": hit["longitude"],
        "timezone": hit.get("timezone") or "auto",
    }


def forecast(lat: float, lon: float, timezone: str = "auto") -> dict:
    resp = _http.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": timezone or "auto",
            "forecast_days": 7,
        },
    )
    resp.raise_for_status()
    return resp.json()


def format_forecast(place: dict, data: dict) -> str:
    where = ", ".join(p for p in (place["name"], place.get("admin1"), place.get("country")) if p)
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    units = data.get("current_units") or {}
    temp_u = units.get("temperature_2m", "°C")

    lines = [
        f"Live forecast for {where} (Open-Meteo, not scraped pages).",
        "",
        "Current:",
        f"- Temperature: {current.get('temperature_2m')}{temp_u}",
        f"- Conditions: {_wmo(current.get('weather_code'))}",
        f"- Humidity: {current.get('relative_humidity_2m')}%",
        f"- Wind: {current.get('wind_speed_10m')} {units.get('wind_speed_10m', 'km/h')}",
        "",
        "Next days:",
    ]
    dates = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    codes = daily.get("weather_code") or []
    rain = daily.get("precipitation_probability_max") or []
    labels = ["Today", "Tomorrow"]
    for i, day in enumerate(dates[:7]):
        tag = labels[i] if i < len(labels) else day
        hi = tmax[i] if i < len(tmax) else "?"
        lo = tmin[i] if i < len(tmin) else "?"
        cond = _wmo(codes[i] if i < len(codes) else None)
        pop = rain[i] if i < len(rain) else None
        extra = f", rain chance {pop}%" if pop is not None else ""
        lines.append(f"- {tag} ({day}): {cond}, high {hi}{temp_u} / low {lo}{temp_u}{extra}")
    return "\n".join(lines)


def answer_weather(place_name: str) -> dict:
    loc = geocode(place_name)
    if not loc:
        raise ValueError(f"Could not find a location named '{place_name}'. Try a city name.")
    data = forecast(loc["latitude"], loc["longitude"], loc.get("timezone") or "auto")
    label = ", ".join(p for p in (loc["name"], loc.get("admin1"), loc.get("country")) if p)
    lat, lon = loc["latitude"], loc["longitude"]
    url = f"https://open-meteo.com/en/forecast?latitude={lat}&longitude={lon}"
    return {
        "answer": format_forecast(loc, data),
        "sources": [{
            "rank": 1,
            "url": url,
            "title": f"Open-Meteo forecast — {label}",
            "source": "open-meteo",
        }],
    }
