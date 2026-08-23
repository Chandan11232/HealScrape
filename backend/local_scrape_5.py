"""
Scrape 5 sources and push to Railway /ingest.

  openai/react  = CACHED (0 credits, 0 API calls)
  docker/mdn/stripe = DIRECT HTTP fetch (0 credits, no Bright Data needed)

Run from backend/:
    RAILWAY_URL=https://your-app.up.railway.app python local_scrape_5.py
"""
import json
import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app.config import settings

RAILWAY_URL = os.getenv("RAILWAY_URL", "").rstrip("/")

SOURCES = [
    # (name, job_tag, url, method)
    # method: "cached" = use existing normalized_*.json
    #         "direct" = fetch with httpx, extract text
    ("openai",       "openai_batch1",  "https://openai.com/index/chatgpt/",                "cached"),
    ("react",        "react_batch1",   "https://react.dev/reference/rsc/server-components", "cached"),
    ("docker_intro", "demo_docker",    "https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-container/", "direct"),
    ("mdn_web",      "demo_mdn",       "https://developer.mozilla.org/en-US/docs/Web/JavaScript", "direct"),
    ("stripe_docs",  "demo_stripe",    "https://docs.stripe.com/api/charges",              "direct"),
]


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    from html import unescape
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def fetch_direct(url: str, name: str) -> list[dict]:
    """Fetch a public page with httpx, extract text content."""
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    title = _extract_title(html)
    # For docs sites, try to get main content area
    main = re.search(r"<main[^>]*>(.*?)</main>", html, re.S | re.I)
    content_html = main.group(1) if main else html
    content = _strip_html(content_html)
    # Truncate to reasonable size for embedding
    if len(content) > 10000:
        content = content[:10000]
    return [{
        "source": "direct",
        "url": url,
        "title": title,
        "content": content,
        "metadata": {"scraper_name": name},
    }]


def load_cache(job_tag: str) -> list[dict]:
    p = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    return json.loads(p.read_text())


def has_cache(job_tag: str) -> bool:
    p = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    return p.exists() and p.stat().st_size > 10


def save_local(docs: list[dict], job_tag: str) -> Path:
    Path(settings.PROCESSED_DATA_DIR).mkdir(parents=True, exist_ok=True)
    p = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    p.write_text(json.dumps(docs, separators=(",", ":")))
    return p


def post_to_railway(job_tag: str, docs: list[dict]) -> dict | None:
    if not RAILWAY_URL:
        return None
    import httpx
    try:
        r = httpx.post(f"{RAILWAY_URL}/ingest", json={"job_tag": job_tag, "documents": docs}, timeout=300)
        r.raise_for_status()
        resp = r.json()
        print(f"  -> ingest: {resp}")
        return {"documents_in": resp.get("documents_in", 0), "chunks_added": resp.get("chunks_added", 0)}
    except Exception as e:
        print(f"  WARN railway ingest failed: {e}")
        return None


def main():
    results = []
    print(f"railway: {RAILWAY_URL or '(local only)'}\n")

    for name, tag, url, method in SOURCES:
        print(f"--- {name} ---")

        if method == "cached":
            if has_cache(tag):
                docs = load_cache(tag)
                # Strip HTML and cap content size for large cached docs
                for d in docs:
                    c = d.get("content", "")
                    if "<" in c:
                        c = _strip_html(c)
                    if len(c) > 10000:
                        c = c[:10000]
                    d["content"] = c
                docs = [d for d in docs if d.get("content")]
                print(f"  CACHED: {len(docs)} records")
            else:
                print(f"  SKIP: no cache found")
                results.append({"s": name, "status": "no_cache"})
                continue
        else:
            try:
                print(f"  FETCH: {url}")
                docs = fetch_direct(url, name)
                save_local(docs, tag)
                print(f"  OK: {len(docs)} records, {len(docs[0]['content'])} chars")
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({"s": name, "status": "error", "err": str(e)})
                continue

        rail = post_to_railway(tag, docs)
        if rail:
            print(f"  -> Railway: {rail}")
        results.append({"s": name, "status": "ok", "n": len(docs), "rail": rail})

    total = sum(r.get("n", 0) for r in results)
    print(f"\n{'='*50}")
    print(f"total: {total} records, 0 credits used")
    Path("/tmp/five_scrape_summary.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
