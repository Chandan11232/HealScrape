"""
Firecrawl client — supplementary crawler (Bright Data remains the required tool).
Free tier: 500 credits/month. Each /scrape call ~1 credit, /crawl scales with pages.
We hard-cap page count to avoid burning the whole month's quota in one run.
"""
import json
from pathlib import Path
import httpx
from app.config import settings


class FirecrawlClient:
    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY
        self.base_url = "https://api.firecrawl.dev/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        Path(settings.RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)

    def scrape_url(self, url: str, job_tag: str) -> dict:
        cache_file = Path(settings.RAW_DATA_DIR) / f"firecrawl_{job_tag}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        resp = httpx.post(
            f"{self.base_url}/scrape",
            headers=self.headers,
            json={"url": url, "formats": ["markdown"]},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        cache_file.write_text(json.dumps(data, indent=2))
        return data

    def crawl_site(self, base_url: str, job_tag: str, limit: int = 10) -> list[dict]:
        """Capped crawl — limit defaults low to protect free credits."""
        cache_file = Path(settings.RAW_DATA_DIR) / f"firecrawl_crawl_{job_tag}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        resp = httpx.post(
            f"{self.base_url}/crawl",
            headers=self.headers,
            json={"url": base_url, "limit": limit, "scrapeOptions": {"formats": ["markdown"]}},
            timeout=60,
        )
        resp.raise_for_status()
        job_id = resp.json()["id"]

        # poll
        import time
        while True:
            status_resp = httpx.get(f"{self.base_url}/crawl/{job_id}", headers=self.headers, timeout=30)
            status_data = status_resp.json()
            if status_data.get("status") == "completed":
                break
            time.sleep(4)

        results = status_data.get("data", [])
        cache_file.write_text(json.dumps(results, indent=2))
        return results


firecrawl_client = FirecrawlClient()
