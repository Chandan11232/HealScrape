"""
Closed collector catalog.

Any key in BRIGHTDATA_SCRAPERS can be used on /scrape and /heal.
This list is the default RAG/console set; extra env keys still work.
"""
import re
from urllib.parse import urlparse

INDEXED_SOURCES = [
    {
        "domain": "en.wikipedia.org",
        "scraper_name": "wikipedia_ai",
        "kind": "encyclopedia",
        "covers": "Wikipedia articles that were scraped",
        "example_url": "https://en.wikipedia.org/wiki/Dog",
    },
    {
        "domain": "weather.com",
        "scraper_name": "weather",
        "kind": "weather",
        "covers": "Current conditions and forecast pages that were scraped",
        "example_url": "https://weather.com/",
    },
    {
        "domain": "docs.python.org",
        "scraper_name": "python",
        "kind": "docs",
        "covers": "Python language and standard-library documentation",
        "example_url": "https://docs.python.org/3/",
    },
    {
        "domain": "fastapi.tiangolo.com",
        "scraper_name": "tiangolo",
        "kind": "docs",
        "covers": "FastAPI framework docs",
        "example_url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
    },
    {
        "domain": "react.dev",
        "scraper_name": "react",
        "kind": "docs",
        "covers": "React documentation",
        "example_url": "https://react.dev/",
    },
    {
        "domain": "techcrunch.com",
        "scraper_name": "techcrunch",
        "kind": "news",
        "covers": "TechCrunch articles that were scraped",
        "example_url": "https://techcrunch.com/",
    },
    {
        "domain": "theverge.com",
        "scraper_name": "theverge",
        "kind": "news",
        "covers": "The Verge articles that were scraped",
        "example_url": "https://www.theverge.com/ai-artificial-intelligence/980160/apple-intelligence-china-custom-ai-model-alibaba",
    },
    {
        "domain": "venturebeat.com",
        "scraper_name": "venturebeat",
        "kind": "news",
        "covers": "VentureBeat articles that were scraped",
        "example_url": "https://venturebeat.com/",
    },
    {
        "domain": "openai.com",
        "scraper_name": "openai",
        "kind": "blog",
        "covers": "OpenAI public pages that were scraped",
        "example_url": "https://openai.com/",
    },
    {
        "domain": "devpost.com",
        "scraper_name": "devpost",
        "kind": "listings",
        "covers": "hackathon listings that were scraped",
        "example_url": "https://devpost.com/hackathons",
    },
    {
        "domain": "remoteok.com",
        "scraper_name": "remoteok",
        "kind": "jobs",
        "covers": "remote job listings that were scraped",
        "example_url": "https://remoteok.com/",
    },
    {
        "domain": "github.com",
        "scraper_name": "github",
        "kind": "code",
        "covers": "GitHub pages that were scraped",
        "example_url": "https://github.com/",
    },
    {
        "domain": "huggingface.co",
        "scraper_name": "huggingface",
        "kind": "docs",
        "covers": "Hugging Face pages that were scraped",
        "example_url": "https://huggingface.co/",
    },
]

INDEXED_DOMAINS = [s["domain"] for s in INDEXED_SOURCES]

# Collectors whose Bright Data heal API rejects {"url": ...} in custom_input.
# Heal still passes the test URL inside the prompt text.
PROMPT_ONLY_HEAL_SCRAPERS = frozenset(
    {
        "theverge",
        "python",
        "techcrunch",
        "venturebeat",
        "huggingface",
        "weather",
        "openai",
        "remoteok",
    }
)

SCRAPER_BY_NAME = {s["scraper_name"]: s for s in INDEXED_SOURCES}

# Bright Data Collection API inputs for collectors that reject plain {"url": ...}.
# Sitemap URLs verified via each site's robots.txt (not guessed /sitemap.xml paths).
SITEMAP_SCRAPE_INPUTS: dict[str, dict[str, str]] = {
    "theverge": {
        "sitemap_url": "https://www.theverge.com/sitemaps/google_news",
        "url_pattern": ".*",
    },
    "techcrunch": {
        "sitemap_url": "https://techcrunch.com/news-sitemap.xml",
        "url_pattern": ".*",
    },
    "venturebeat": {
        "sitemap_url": "https://venturebeat.com/news-sitemap.xml",
        "url_pattern": ".*",
    },
    "python": {
        "sitemap_url": "https://docs.python.org/sitemap.xml",
        "url_pattern": ".*",
    },
    "huggingface": {
        "sitemap_url": "https://huggingface.co/sitemap.xml",
        "url_pattern": ".*",
    },
}

SITEMAP_SCRAPER_NAMES = frozenset(SITEMAP_SCRAPE_INPUTS.keys())


def example_url_for(scraper_name: str) -> str:
    entry = SCRAPER_BY_NAME.get(scraper_name)
    return (entry or {}).get("example_url", "")


def scrape_inputs_for(scraper_name: str, urls: list[str]) -> list[dict]:
    """
    Build trigger payloads for a collector's input schema.
    Most collectors: [{"url": "..."}]. Sitemap collectors: sitemap_url + url_pattern.
    """
    fixed = SITEMAP_SCRAPE_INPUTS.get(scraper_name)
    if fixed:
        payload = dict(fixed)
        test_url = next((u.strip() for u in urls if u and u.strip()), "") or example_url_for(scraper_name)
        if test_url:
            path = urlparse(test_url).path
            article_id = re.search(r"/(\d+)/", path)
            if article_id:
                payload["url_pattern"] = f".*{article_id.group(1)}.*"
            elif path and path != "/":
                payload["url_pattern"] = re.escape(path.rstrip("/")) + ".*"
        return [payload]

    test_urls = [u.strip() for u in urls if u and u.strip()]
    if not test_urls:
        fallback = example_url_for(scraper_name)
        if fallback:
            test_urls = [fallback]
    if not test_urls:
        raise ValueError(
            f"No URLs provided for scraper '{scraper_name}' and no example_url in catalog."
        )
    return [{"url": u} for u in test_urls]


def heal_trigger_payloads(scraper_name: str, prompt: str, test_url: str) -> list[dict]:
    """Ordered refactor_template bodies — first match wins per collector input schema."""
    prompt = (prompt or "").strip()[:1000]
    url_row = [{"url": test_url}] if test_url else []
    empty_row: list[dict] = []

    if scraper_name in PROMPT_ONLY_HEAL_SCRAPERS:
        ordered = [empty_row, url_row] if test_url else [empty_row]
    else:
        ordered = [url_row, empty_row] if test_url else [empty_row]

    seen: set[str] = set()
    payloads: list[dict] = []
    for custom_input in ordered:
        key = str(custom_input)
        if key in seen:
            continue
        seen.add(key)
        payloads.append({"prompt": prompt, "custom_input": custom_input})
    return payloads or [{"prompt": prompt, "custom_input": []}]

# Longer aliases first so "the verge" matches before a bare token.
_QUERY_ALIASES = (
    ("fastapi.tiangolo.com", "fastapi.tiangolo.com"),
    ("docs.python.org", "docs.python.org"),
    ("en.wikipedia.org", "en.wikipedia.org"),
    ("huggingface.co", "huggingface.co"),
    ("techcrunch.com", "techcrunch.com"),
    ("theverge.com", "theverge.com"),
    ("venturebeat.com", "venturebeat.com"),
    ("weather.com", "weather.com"),
    ("react.dev", "react.dev"),
    ("openai.com", "openai.com"),
    ("devpost.com", "devpost.com"),
    ("remoteok.com", "remoteok.com"),
    ("github.com", "github.com"),
    ("tech crunch", "techcrunch.com"),
    ("techcrunch", "techcrunch.com"),
    ("the verge", "theverge.com"),
    ("venturebeat", "venturebeat.com"),
    ("wikipedia", "en.wikipedia.org"),
    ("huggingface", "huggingface.co"),
    ("tiangolo", "fastapi.tiangolo.com"),
    ("fastapi", "fastapi.tiangolo.com"),
    ("python docs", "docs.python.org"),
    ("weather", "weather.com"),
    ("react", "react.dev"),
    ("openai", "openai.com"),
    ("devpost", "devpost.com"),
    ("remoteok", "remoteok.com"),
    ("github", "github.com"),
    ("python", "docs.python.org"),
)


def domain_list_text() -> str:
    return ", ".join(INDEXED_DOMAINS)


def domains_from_query(query_text: str) -> list[str]:
    """Domains the user named in the question (for retrieval routing)."""
    q = (query_text or "").lower()
    found: list[str] = []
    for alias, domain in _QUERY_ALIASES:
        if alias in q and domain not in found:
            found.append(domain)
    return found
