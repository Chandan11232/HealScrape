"""
Manual smoke test for the scraper layer.
Run from backend/: python test_scrapers.py

This does NOT auto-run everything — it prompts you before any call that
could consume paid/free-tier credits, so you don't accidentally burn quota.
"""
import sys
from app.scrapers.brightdata_client import brightdata_client, BrightDataError
from app.scrapers.firecrawl_client import firecrawl_client
from app.scrapers.tavily_client import tavily_client
from app.scrapers.normalizer import from_brightdata, from_firecrawl, from_tavily, save_normalized


def confirm(label: str) -> bool:
    ans = input(f"\nRun {label}? This may use free-tier/trial credit. (y/N): ").strip().lower()
    return ans == "y"


def test_brightdata():
    if not confirm("Bright Data test scrape"):
        return
    try:
        # Replace with a real URL your Scraper Studio collector is built for
        results = brightdata_client.scrape(
            inputs=[{"url": "https://example.com"}],
            job_tag="smoketest",
        )
        print(f"Bright Data OK — {len(results)} records")
        docs = from_brightdata(results)
        path = save_normalized(docs, "brightdata_smoketest")
        print(f"Saved normalized output -> {path}")
    except BrightDataError as e:
        print(f"Bright Data FAILED: {e}")


def test_firecrawl():
    if not confirm("Firecrawl test scrape"):
        return
    try:
        data = firecrawl_client.scrape_url("https://example.com", job_tag="smoketest")
        print("Firecrawl OK — got keys:", list(data.keys()))
        docs = from_firecrawl([data.get("data", data)])
        path = save_normalized(docs, "firecrawl_smoketest")
        print(f"Saved normalized output -> {path}")
    except Exception as e:
        print(f"Firecrawl FAILED: {e}")


def test_tavily():
    if not confirm("Tavily test search"):
        return
    try:
        data = tavily_client.search("test query hackathon", job_tag="smoketest", max_results=3)
        print(f"Tavily OK — {len(data.get('results', []))} results")
        docs = from_tavily(data)
        path = save_normalized(docs, "tavily_smoketest")
        print(f"Saved normalized output -> {path}")
    except Exception as e:
        print(f"Tavily FAILED: {e}")


if __name__ == "__main__":
    print("=== Scraper Layer Smoke Test ===")
    test_brightdata()
    test_firecrawl()
    test_tavily()
    print("\nDone. Check backend/data/raw/ and backend/data/processed/ for output files.")