"""
Resume polling a Bright Data snapshot that already timed out once,
without re-triggering the scraper (so no extra credit is spent).

Usage:
    python resume_scrape.py <snapshot_id> <job_tag>

Example:
    python resume_scrape.py j_msybsx2t1bzi1ia4xg wikipedia_ai_batch1
"""
import sys
from app.scrapers.brightdata_client import brightdata_client, BrightDataError
from app.scrapers.normalizer import from_brightdata, save_normalized

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python resume_scrape.py <snapshot_id> <job_tag>")
        sys.exit(1)

    snapshot_id = sys.argv[1]
    job_tag = sys.argv[2]

    print(f"Resuming poll for snapshot={snapshot_id}, job_tag={job_tag}...")
    print("This may take up to 25 minutes for large/dense pages. Waiting...")

    try:
        results = brightdata_client.poll_and_fetch(
            snapshot_id=snapshot_id,
            job_tag=job_tag,
            interval=10,
            timeout=1500,  # 25 minutes
        )
    except BrightDataError as e:
        print(f"FAILED: {e}")
        sys.exit(1)

    print(f"Got {len(results)} records.")

    docs = from_brightdata(results)
    path = save_normalized(docs, job_tag)
    print(f"Saved normalized output -> {path}")
    print("You can now call POST /ingest with job_tag:", job_tag)