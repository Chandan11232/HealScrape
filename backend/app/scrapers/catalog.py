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
        "example_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
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
        "example_url": "https://react.dev/reference/rsc/server-components",
    },
    {
        "domain": "docs.python.org",
        "scraper_name": "python_docs",
        "kind": "docs",
        "covers": "Python tutorial pages that were scraped",
        "example_url": "https://docs.python.org/3/tutorial/introduction.html",
    },
    {
        "domain": "openai.com",
        "scraper_name": "openai",
        "kind": "blog",
        "covers": "OpenAI public pages that were scraped",
        "example_url": "https://openai.com/index/chatgpt/",
    },
    {
        "domain": "devpost.com",
        "scraper_name": "devpost",
        "kind": "listings",
        "covers": "hackathon project listings that were scraped",
        "example_url": "https://devpost.com/software",
    },
    {
        "domain": "github.com",
        "scraper_name": "github_readme",
        "kind": "code",
        "covers": "GitHub repository README pages that were scraped",
        "example_url": "https://github.com/fastapi/fastapi",
    },
    {
        "domain": "developer.mozilla.org",
        "scraper_name": "mdn_web",
        "kind": "docs",
        "covers": "MDN Web Docs pages that were scraped",
        "example_url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
    },
    {
        "domain": "docs.docker.com",
        "scraper_name": "docker_intro",
        "kind": "docs",
        "covers": "Docker concept pages that were scraped",
        "example_url": "https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-container/",
    },
    {
        "domain": "docs.stripe.com",
        "scraper_name": "stripe_docs",
        "kind": "docs",
        "covers": "Stripe API documentation that was scraped",
        "example_url": "https://docs.stripe.com/api/charges",
    },
    {
        "domain": "en.wikipedia.org",
        "scraper_name": "wiki_javascript",
        "kind": "encyclopedia",
        "covers": "Wikipedia JavaScript article that was scraped",
        "example_url": "https://en.wikipedia.org/wiki/JavaScript",
    },
    {
        "domain": "www.anthropic.com",
        "scraper_name": "anthropic_news",
        "kind": "blog",
        "covers": "Anthropic news posts that were scraped",
        "example_url": "https://www.anthropic.com/news/claude-3-family",
    },
    {
        "domain": "www.sqlite.org",
        "scraper_name": "sqlite_docs",
        "kind": "docs",
        "covers": "SQLite language reference pages that were scraped",
        "example_url": "https://www.sqlite.org/lang_select.html",
    },
]

INDEXED_DOMAINS = list(dict.fromkeys(s["domain"] for s in INDEXED_SOURCES))

# Collectors whose Bright Data heal API rejects {"url": ...} in custom_input.
# Heal still passes the test URL inside the prompt text.
PROMPT_ONLY_HEAL_SCRAPERS = frozenset({"openai", "devpost"})

SCRAPER_BY_NAME = {s["scraper_name"]: s for s in INDEXED_SOURCES}

# Bright Data Collection API inputs for collectors that reject plain {"url": ...}.
# Sitemap URLs verified via each site's robots.txt (not guessed /sitemap.xml paths).
# Intentionally empty — these collectors are single-page only (credit-safe).
SITEMAP_SCRAPE_INPUTS: dict[str, dict[str, str]] = {}

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
    ("developer.mozilla.org", "developer.mozilla.org"),
    ("docs.python.org", "docs.python.org"),
    ("docs.docker.com", "docs.docker.com"),
    ("docs.stripe.com", "docs.stripe.com"),
    ("www.anthropic.com", "www.anthropic.com"),
    ("www.sqlite.org", "www.sqlite.org"),
    ("en.wikipedia.org", "en.wikipedia.org"),
    ("react.dev", "react.dev"),
    ("openai.com", "openai.com"),
    ("devpost.com", "devpost.com"),
    ("github.com", "github.com"),
    ("javascript", "en.wikipedia.org"),
    ("wikipedia", "en.wikipedia.org"),
    ("tiangolo", "fastapi.tiangolo.com"),
    ("fastapi", "fastapi.tiangolo.com"),
    ("python docs", "docs.python.org"),
    ("sqlite", "www.sqlite.org"),
    ("stripe", "docs.stripe.com"),
    ("docker", "docs.docker.com"),
    ("anthropic", "www.anthropic.com"),
    ("mdn", "developer.mozilla.org"),
    ("mozilla", "developer.mozilla.org"),
    ("react", "react.dev"),
    ("openai", "openai.com"),
    ("devpost", "devpost.com"),
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
