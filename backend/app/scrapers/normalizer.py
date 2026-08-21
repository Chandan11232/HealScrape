"""
Normalizes Bright Data / Firecrawl / Tavily outputs into one schema
so the RAG pipeline never has to care which source a document came from.
"""
from dataclasses import dataclass, asdict
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings


@dataclass
class NormalizedDoc:
    source: str          # "brightdata" | "firecrawl" | "tavily"
    url: str
    title: str
    content: str
    metadata: dict


def _strip_html(html: str) -> str:
    """Strip HTML tags and unescape entities — no bs4 dependency needed."""
    from html import unescape
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _infer_title(record: dict, content: str) -> str:
    """Fill missing titles for news/docs rows (common on The Verge section scrapes)."""
    for key in ("title", "headline", "article_title", "page_title"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    page_url = record.get("product_page_url") or record.get("url") or ""
    if isinstance(page_url, str) and page_url.strip():
        slug = urlparse(page_url.strip()).path.rstrip("/").split("/")[-1]
        slug = re.sub(r"[-_]+", " ", slug).strip()
        if slug and not slug.isdigit():
            return slug[:120].title()

    text = (content or "").strip()
    if text:
        first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
        if len(first) > 140:
            first = first[:137].rstrip() + "..."
        if first:
            return first
    return ""


def _stringify_list(items) -> str:
    """Safely join a list that might contain strings, dicts, or mixed types."""
    if not items:
        return ""
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            # common shapes: {"text": ...}, {"code": ...}, {"content": ...}
            parts.append(
                item.get("code") or item.get("text") or item.get("content")
                or item.get("description") or json.dumps(item)
            )
        else:
            parts.append(str(item))
    return "\n".join(parts)


def from_brightdata(records: list[dict]) -> list[NormalizedDoc]:
    docs = []
    for r in records:
        # Different collectors produce different schemas. Handle common shapes:
        url = r.get("url") or r.get("product_page_url") or r.get("input", {}).get("url", "")

        title = (
            r.get("title") or r.get("section_title") or r.get("job_title")
            or r.get("page_title") or r.get("headline") or r.get("hackathon_title")
            or r.get("article_title") or r.get("location") or r.get("city") or ""
        )

        content = r.get("text") or r.get("content") or r.get("article_body") or r.get("excerpt") or ""

        if not content and "content_paragraphs" in r:
            # Section-based docs scrapers (e.g. Python docs)
            content = "\n\n".join(r.get("content_paragraphs", []))

        if not content and "description" in r and "job_title" in r:
            # Job-listing scrapers (e.g. RemoteOK)
            parts = []
            if r.get("job_title"):
                parts.append(f"Job Title: {r['job_title']}")
            if r.get("company_name"):
                parts.append(f"Company: {r['company_name']}")
            if r.get("location"):
                parts.append(f"Location: {r['location']}")
            if r.get("tags"):
                parts.append(f"Tags: {_stringify_list(r['tags'])}")
            if r.get("description"):
                parts.append(f"Description: {r['description']}")
            content = "\n".join(parts)

        if not content and "main_content" in r:
            # Docs/product pages with structured sections (e.g. FastAPI/tiangolo)
            parts = [r.get("main_content", "")]
            if r.get("section_headings"):
                parts.append("Sections: " + _stringify_list(r["section_headings"]))
            if r.get("feature_descriptions"):
                parts.append(_stringify_list(r["feature_descriptions"]))
            if r.get("code_examples"):
                parts.append(_stringify_list(r["code_examples"]))
            content = "\n\n".join(p for p in parts if p)

        if not content and "article_content" in r and "article_title" in r:
            # Encyclopedia/wiki-style scrapers (e.g. Wikipedia) — content is raw HTML
            parts = []
            if r.get("short_description"):
                parts.append(f"Summary: {r['short_description']}")
            parts.append(_strip_html(r.get("article_content", "")))
            if r.get("categories"):
                parts.append("Categories: " + _stringify_list(r["categories"]))
            content = "\n\n".join(p for p in parts if p)

        if not content and "article_content" in r and "headline" in r:
            # News article scrapers (e.g. VentureBeat, some Verge shapes)
            parts = []
            if r.get("headline"):
                parts.append(f"Headline: {r['headline']}")
            if r.get("author"):
                parts.append(f"Author: {r['author']}")
            if r.get("publish_date"):
                parts.append(f"Published: {r['publish_date']}")
            parts.append(r.get("article_content", ""))
            content = "\n".join(p for p in parts if p)

        if not content and "tagline" in r and "hackathon_title" in r:
            # Hackathon listing scrapers (e.g. Devpost)
            parts = []
            if r.get("hackathon_title"):
                parts.append(f"Hackathon: {r['hackathon_title']}")
            if r.get("tagline"):
                parts.append(f"Tagline: {r['tagline']}")
            if r.get("organizer"):
                parts.append(f"Organizer: {r['organizer']}")
            if r.get("deadline"):
                parts.append(f"Deadline: {r['deadline']}")
            if r.get("total_prize_amount"):
                parts.append(f"Prize: {r['total_prize_amount']}")
            if r.get("participant_count"):
                parts.append(f"Participants: {r['participant_count']}")
            if r.get("themes"):
                parts.append("Themes: " + _stringify_list(r["themes"]))
            if r.get("description"):
                parts.append(f"Description: {r['description']}")
            content = "\n".join(parts)

        if not content and any(
            k in r for k in ("temperature", "temp", "current_temperature", "condition", "forecast")
        ):
            parts = []
            loc = r.get("location") or r.get("city") or r.get("place")
            if loc:
                parts.append(f"Location: {loc}")
            temp = r.get("temperature") or r.get("temp") or r.get("current_temperature")
            if temp:
                parts.append(f"Temperature: {temp}")
            if r.get("feels_like"):
                parts.append(f"Feels like: {r['feels_like']}")
            if r.get("high_temperature"):
                parts.append(f"High: {r['high_temperature']}")
            if r.get("low_temperature"):
                parts.append(f"Low: {r['low_temperature']}")
            if r.get("chance_of_rain") is not None:
                parts.append(f"Chance of rain: {r['chance_of_rain']}")
            if r.get("condition") or r.get("weather"):
                parts.append(f"Condition: {r.get('condition') or r.get('weather')}")
            if r.get("humidity"):
                parts.append(f"Humidity: {r['humidity']}")
            if r.get("wind") or r.get("wind_speed"):
                parts.append(f"Wind: {r.get('wind') or r.get('wind_speed')}")
            if r.get("forecast"):
                parts.append(f"Forecast: {_stringify_list(r['forecast']) if isinstance(r.get('forecast'), list) else r['forecast']}")
            if r.get("description"):
                parts.append(str(r["description"]))
            content = "\n".join(str(p) for p in parts if p)

        if not content and isinstance(r.get("repositories"), list) and r["repositories"]:
            # GitHub trending / repo listing collectors
            parts = []
            for repo in r["repositories"][:20]:
                if isinstance(repo, dict):
                    name = repo.get("repository_name") or repo.get("name") or ""
                    url = repo.get("repository_url") or repo.get("url") or ""
                    desc = repo.get("description") or repo.get("about") or ""
                    line = " — ".join(x for x in (name, desc, url) if x)
                    if line:
                        parts.append(line)
                elif isinstance(repo, str) and repo.strip():
                    parts.append(repo.strip())
            if not title:
                title = "GitHub repositories"
            content = "\n".join(parts)

        if not title and r.get("repository_name"):
            title = str(r.get("repository_name") or "").strip()
        if not content and r.get("readme_content"):
            content = str(r.get("readme_content") or "").strip()
        if not content and r.get("description") and r.get("repository_name"):
            content = str(r.get("description") or "").strip()

        if not content:
            # Generic fallback: stitch remaining non-empty scalar fields.
            skip = {
                "url", "product_page_url", "input", "error", "warning", "images",
                "external_links", "github_edit_url", "author_url", "author_image",
            }
            parts = []
            for key, value in r.items():
                if key in skip:
                    continue
                if isinstance(value, str) and value.strip() and value.strip().lower() not in {"none", "null"}:
                    parts.append(f"{key}: {value.strip()}")
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    parts.append(f"{key}: {value}")
                elif isinstance(value, list) and value:
                    parts.append(f"{key}: {_stringify_list(value)}")
            if parts and not title:
                title = next((p.split(":", 1)[1].strip() for p in parts if p), "")[:120]
            if parts and not content:
                content = "\n".join(parts)

        if not title:
            title = _infer_title(r, content)

        docs.append(NormalizedDoc(
            source="brightdata",
            url=url,
            title=title,
            content=content,
            metadata={k: v for k, v in r.items() if k not in (
                "url", "title", "text", "content", "content_paragraphs", "input",
                "job_title", "description", "main_content", "section_headings",
                "feature_descriptions", "code_examples", "article_content",
                "headline", "author", "publish_date", "hackathon_title",
                "tagline", "organizer", "deadline", "total_prize_amount",
                "participant_count", "themes", "article_title", "location",
                "city", "temperature", "temp", "current_temperature",
                "condition", "forecast", "humidity", "wind", "wind_speed",
                "weather", "place", "feels_like", "high_temperature",
                "low_temperature", "chance_of_rain", "repositories",
            )},
        ))
    return docs


def from_firecrawl(records: list[dict]) -> list[NormalizedDoc]:
    docs = []
    for r in records:
        meta = r.get("metadata", {})
        docs.append(NormalizedDoc(
            source="firecrawl",
            url=meta.get("sourceURL", ""),
            title=meta.get("title", ""),
            content=r.get("markdown", ""),
            metadata=meta,
        ))
    return docs


def from_tavily(response: dict) -> list[NormalizedDoc]:
    docs = []
    for r in response.get("results", []):
        docs.append(NormalizedDoc(
            source="tavily",
            url=r.get("url", ""),
            title=r.get("title", ""),
            content=r.get("content", ""),
            metadata={"score": r.get("score")},
        ))
    return docs


def save_normalized(docs: list[NormalizedDoc], job_tag: str) -> Path:
    Path(settings.PROCESSED_DATA_DIR).mkdir(parents=True, exist_ok=True)
    out_path = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    out_path.write_text(json.dumps([asdict(d) for d in docs], separators=(",", ":")))
    return out_path
