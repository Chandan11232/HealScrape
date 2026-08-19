"""Live Wikipedia via the free MediaWiki / REST APIs (no API key)."""
from __future__ import annotations

from urllib.parse import quote

import httpx

from app.llm.client import generate

SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
API_URL = "https://en.wikipedia.org/w/api.php"

WIKI_SYSTEM = (
    "You answer using only the Wikipedia excerpt below. "
    "Be concise. If the excerpt does not contain the answer, say so in one sentence."
)

_http = httpx.Client(
    timeout=15.0,
    headers={"User-Agent": "HackathonRAG/0.1 (local demo; contact: demo@example.com)"},
)


def _title_slug(topic: str) -> str:
    return topic.strip().replace(" ", "_")


def search_title(query: str, limit: int = 5) -> str | None:
    """Find the best-matching article title when the topic is not an exact page name."""
    resp = _http.get(
        API_URL,
        params={
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
        },
    )
    resp.raise_for_status()
    hits = (resp.json().get("query") or {}).get("search") or []
    if not hits:
        return None
    return hits[0].get("title")


def resolve_title(topic: str, query: str) -> str:
    """Direct title lookup, then Wikipedia search on topic and full question."""
    try:
        summary = fetch_summary(topic)
        return summary.get("title") or topic
    except ValueError:
        pass
    for term in (topic, query):
        found = search_title(term)
        if found:
            return found
    raise ValueError(f"No Wikipedia article found for '{topic}'.")


def fetch_summary(topic: str) -> dict:
    slug = quote(_title_slug(topic), safe="")
    resp = _http.get(SUMMARY_URL.format(title=slug))
    if resp.status_code == 404:
        raise ValueError(f"No Wikipedia article found for '{topic}'.")
    resp.raise_for_status()
    data = resp.json()
    if data.get("type") == "disambiguation":
        raise ValueError(
            f"'{topic}' is a disambiguation page on Wikipedia. Try a more specific title."
        )
    return data


def fetch_extract(topic: str, sentences: int = 25) -> str:
    resp = _http.get(
        API_URL,
        params={
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": 1,
            "exsentences": sentences,
            "redirects": 1,
            "titles": topic,
        },
    )
    resp.raise_for_status()
    pages = (resp.json().get("query") or {}).get("pages") or {}
    if not pages:
        raise ValueError(f"No Wikipedia article found for '{topic}'.")
    page = next(iter(pages.values()))
    if page.get("missing"):
        raise ValueError(f"No Wikipedia article found for '{topic}'.")
    extract = (page.get("extract") or "").strip()
    if not extract:
        raise ValueError(f"Wikipedia returned an empty article for '{topic}'.")
    return extract


def answer_wikipedia(topic: str, query: str) -> dict:
    title = resolve_title(topic, query)
    summary = fetch_summary(title)
    title = summary.get("title") or title
    description = summary.get("description") or ""
    short = (summary.get("extract") or "").strip()
    long_extract = fetch_extract(title)

    context = short
    if long_extract and len(long_extract) > len(short):
        context = long_extract

    subtitle = f"Subtitle: {description}\n" if description else ""
    prompt = (
        f"Article: {title}\n"
        f"{subtitle}"
        f"Excerpt:\n{context}\n\n"
        f"Question: {query}\n\nAnswer:"
    )
    answer = generate(prompt, system=WIKI_SYSTEM)

    page_url = (summary.get("content_urls") or {}).get("desktop", {}).get("page")
    page_url = page_url or f"https://en.wikipedia.org/wiki/{_title_slug(title)}"

    return {
        "answer": answer,
        "sources": [{
            "rank": 1,
            "url": page_url,
            "title": f"Wikipedia — {title}",
            "source": "wikipedia",
        }],
    }
