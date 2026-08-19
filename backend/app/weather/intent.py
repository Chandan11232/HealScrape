"""Detect forecast questions and pull a place name for Open-Meteo."""
from __future__ import annotations

import re

_WEATHER = re.compile(
    r"\b(weather|forecast|temperature|humidity|\brain\b|rainfall|snow(?:y|ing)?|how hot|how cold)\b",
    re.I,
)

_PLACE = re.compile(
    r"\b(?:in|for|at)\s+([A-Za-z][A-Za-z .'-]{1,48}?)(?:\s*[?.,!]|$)",
    re.I,
)

_PLACE_BEFORE = re.compile(
    r"\b([A-Za-z][A-Za-z .'-]{1,40}?)\s+(?:weather|forecast)\b",
    re.I,
)

_STRIP = re.compile(
    r"\b(today|tomorrow|tonight|current|currently|the|a|an|my|week'?s?|daily)\b",
    re.I,
)


def is_weather_query(query: str) -> bool:
    return bool(_WEATHER.search(query or ""))


def extract_place(query: str) -> str | None:
    q = (query or "").strip()
    match = _PLACE.search(q)
    raw = match.group(1) if match else None
    if not raw:
        match = _PLACE_BEFORE.search(q)
        raw = match.group(1) if match else None
    if not raw:
        return None
    place = _STRIP.sub(" ", raw)
    place = re.sub(r"\s+", " ", place).strip(" ,.-")
    if len(place) < 2:
        return None
    return place
