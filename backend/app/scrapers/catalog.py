"""
Closed collector catalog.

Any key in BRIGHTDATA_SCRAPERS can be used on /scrape and /heal.
This list is the default RAG/console set; extra env keys still work.
"""

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
        "example_url": "https://www.theverge.com/",
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
