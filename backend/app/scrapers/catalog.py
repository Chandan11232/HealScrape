"""
Closed collector catalog.

The product is a RAG console over a fixed set of Bright Data Scraper Studio
collectors — not a general-purpose web search. That matches the hackathon
"docs site to RAG" idea and keeps credits, collector IDs, and self-heal
scoped to scrapers you actually own.
"""

# Display domain, scraper_name key in BRIGHTDATA_SCRAPERS, and what it covers.
INDEXED_SOURCES = [
    {
        "domain": "docs.python.org",
        "scraper_name": "python_docs",
        "kind": "docs",
        "covers": "Python language and standard-library documentation",
    },
    {
        "domain": "fastapi.tiangolo.com",
        "scraper_name": "fastapi",
        "kind": "docs",
        "covers": "FastAPI framework docs",
    },
    {
        "domain": "react.dev",
        "scraper_name": "react",
        "kind": "docs",
        "covers": "React documentation",
    },
    {
        "domain": "techcrunch.com",
        "scraper_name": "techcrunch",
        "kind": "news",
        "covers": "TechCrunch articles that were scraped",
    },
    {
        "domain": "theverge.com",
        "scraper_name": "theverge",
        "kind": "news",
        "covers": "The Verge articles that were scraped",
    },
    {
        "domain": "venturebeat.com",
        "scraper_name": "venturebeat",
        "kind": "news",
        "covers": "VentureBeat articles that were scraped",
    },
    {
        "domain": "openai.com",
        "scraper_name": "openai",
        "kind": "blog",
        "covers": "OpenAI public pages that were scraped",
    },
    {
        "domain": "devpost.com",
        "scraper_name": "devpost",
        "kind": "listings",
        "covers": "hackathon listings that were scraped",
    },
    {
        "domain": "remoteok.com",
        "scraper_name": "remoteok",
        "kind": "jobs",
        "covers": "remote job listings that were scraped",
    },
]

INDEXED_DOMAINS = [s["domain"] for s in INDEXED_SOURCES]


def domain_list_text() -> str:
    return ", ".join(INDEXED_DOMAINS)
