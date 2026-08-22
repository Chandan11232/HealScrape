"""Detect Wikipedia-style questions and extract a topic title."""
from __future__ import annotations

import re

from app.weather.intent import is_weather_query

_WIKI = re.compile(r"\bwikipedia\b", re.I)

_ENCYCLOPEDIA = re.compile(
    r"\b(what is|what are|who is|who was|tell me about|define|explain|describe)\b",
    re.I,
)

# Site names that should stay on scraped RAG, not live Wikipedia.
_OTHER_SITES = re.compile(
    r"\b(fastapi|tiangolo|react\.dev|openai|devpost|github|python docs|"
    r"docs\.python|docker|stripe|mdn|mozilla|sqlite|anthropic|javascript)\b",
    re.I,
)

_TOPIC = re.compile(
    r"(?:what is|what are|who is|who was|tell me about|define|explain|describe)\s+"
    r"(?:the\s+)?(.+?)(?:\s+according to|\s+on wikipedia|\s+from wikipedia|\s*\?|$)",
    re.I,
)

_STRIP = re.compile(
    r"\b(the|a|an|according to|scraped|ingested|page|wikipedia|article)\b",
    re.I,
)

# Ranking / listicle questions belong on scraped sources, not live Wikipedia.
_LISTICLE = re.compile(
    r"\b(best|top|greatest|most popular|most efficient|leading)\b",
    re.I,
)


def is_wikipedia_query(query: str) -> bool:
    q = query or ""
    if _WIKI.search(q):
        return True
    if is_weather_query(q):
        return False
    if _OTHER_SITES.search(q):
        return False
    if _LISTICLE.search(q):
        return False
    return bool(_ENCYCLOPEDIA.search(q))


def extract_topic(query: str) -> str | None:
    q = (query or "").strip()
    match = _TOPIC.search(q)
    if match:
        topic = match.group(1)
    else:
        # "Wikipedia article on dogs" / "Wikipedia: Dog"
        match = re.search(r"wikipedia(?:\s+article)?\s+(?:on|about)\s+(.+?)(?:\?|$)", q, re.I)
        if match:
            topic = match.group(1)
        else:
            return None
    topic = _STRIP.sub(" ", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" ,.-")
    if len(topic) < 2:
        return None
    return topic
