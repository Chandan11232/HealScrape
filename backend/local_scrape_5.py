"""
Scrape 5 collectors locally (Bright Data) and push to Railway /ingest.

Run from backend/:
    python local_scrape_5.py
    RAILWAY_URL=https://your-app.up.railway.app python local_scrape_5.py

Credit budget: 35 max. Each fresh scrape = ~1 credit.
  openai/react = CACHED (0 credits).  docker/mdn/stripe = FRESH (~3 credits).
"""
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

# --- path setup (works when run from backend/) ---
BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app.config import settings
from app.scrapers.scrape_runner import run_brightdata_scrape

CREDIT_CAP = 35
RAILWAY_URL = os.getenv("RAILWAY_URL", "").rstrip("/")
JOBS = [
    # Cached first — instant, 0 credits
    ("openai",       "demo_openai", "https://openai.com/index/chatgpt/"),
    ("react",        "demo_react",  "https://react.dev/reference/rsc/server-components"),
    # Fresh scrapes — ~1 credit each, longer timeout
    ("docker_intro", "demo_docker",  "https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-container/"),
    ("mdn_web",      "demo_mdn",    "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
    ("stripe_docs",  "demo_stripe", "https://docs.stripe.com/api/charges"),
]


def has_cache(job_tag: str) -> bool:
    p = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    return p.exists() and p.stat().st_size > 10


def load_cache(job_tag: str) -> list[dict]:
    p = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    return json.loads(p.read_text())


def post_to_railway(job_tag: str, docs: list[dict]) -> dict | None:
    if not RAILWAY_URL:
        return None
    import httpx
    try:
        r = httpx.post(f"{RAILWAY_URL}/ingest", json={"job_tag": job_tag, "documents": docs}, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  WARN railway ingest failed: {e}")
        return None


def main():
    credits = 0
    results = []
    print(f"credit cap: {CREDIT_CAP}  |  railway: {RAILWAY_URL or '(local only)'}\n")

    for name, tag, url in JOBS:
        if credits >= CREDIT_CAP:
            print(f"[--] {name}: skipped (credit cap)")
            results.append({"s": name, "status": "skip"})
            break

        if has_cache(tag):
            docs = load_cache(tag)
            print(f"[C]  {name}: {len(docs)} records (cached)")
            rail = post_to_railway(tag, docs)
            results.append({"s": name, "status": "cached", "n": len(docs), "rail": rail})
            continue

        credits += 1
        print(f"[S]  {name}: scraping... (credits so far: {credits})")
        try:
            docs, metrics, _ = run_brightdata_scrape(
                [url], tag, name, force=True, timeout=900, max_records=0,
            )
            payload = [asdict(d) for d in docs]
            rail = post_to_railway(tag, payload)
            sr = metrics.get("success_rate", 0)
            print(f"     {len(docs)} records, success={sr}%")
            results.append({"s": name, "status": "ok", "n": len(docs), "sr": sr, "rail": rail})
        except Exception as e:
            print(f"     ERROR: {e}")
            results.append({"s": name, "status": "error", "err": str(e)})

    total_n = sum(r.get("n", 0) for r in results)
    print(f"\n{'='*50}")
    print(f"total: {total_n} records, ~{credits} credits used, headroom: {CREDIT_CAP - credits}")
    Path("/tmp/five_scrape_summary.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
