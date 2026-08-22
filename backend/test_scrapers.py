"""
Manual smoke test for the Bright Data scraper layer.
Run from backend/: python test_scrapers.py

This does NOT auto-run everything — it prompts you before any call that
could consume paid/free-tier credits, so you don't accidentally burn quota.
"""
from app.scrapers.brightdata_client import brightdata_client, BrightDataError
from app.scrapers.normalizer import from_brightdata, save_normalized


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


if __name__ == "__main__":
    print("=== Bright Data Scraper Smoke Test ===")
    test_brightdata()
    print("\nDone. Check backend/data/raw/ and backend/data/processed/ for output files.")
