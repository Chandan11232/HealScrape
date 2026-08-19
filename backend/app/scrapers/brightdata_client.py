"""
Bright Data Scraper Studio client.

Scraper Studio scrapers are triggered via the "trigger" endpoint and
polled via "progress" / "snapshot" endpoints. This client does NOT use
a pre-built Scrapers Library scraper — it targets custom collectors
you build in Scraper Studio, one per site, mapped by name in
BRIGHTDATA_SCRAPERS (see config.py). Using a custom collector is a
hackathon requirement.

Cost control:
- Bright Data trial gives free credit; every trigger call consumes it.
- We cap pages via MAX_PAGES_PER_SCRAPE and cache raw results to disk
  so re-running your pipeline during dev doesn't re-trigger scrapes.
"""
import time
import json
import httpx
from pathlib import Path
from app.config import settings


class BrightDataError(Exception):
    pass


class BrightDataClient:
    def __init__(self):
        self.api_key = settings.BRIGHTDATA_API_KEY
        self.scrapers = settings.BRIGHTDATA_SCRAPERS  # {name: collector_id}
        self.base_url = settings.BRIGHTDATA_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        Path(settings.RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)
        self._http = httpx.Client(headers=self.headers, timeout=30)

    def _cache_path(self, job_tag: str) -> Path:
        return Path(settings.RAW_DATA_DIR) / f"brightdata_{job_tag}.json"

    def _resolve_collector_id(self, scraper_name: str) -> str:
        collector_id = self.scrapers.get(scraper_name)
        if not collector_id:
            raise BrightDataError(
                f"Unknown scraper_name '{scraper_name}'. "
                f"Available: {list(self.scrapers.keys())}. "
                "Add it to BRIGHTDATA_SCRAPERS in .env."
            )
        return collector_id

    def trigger_scrape(self, inputs: list[dict], job_tag: str, scraper_name: str, use_cache: bool = True) -> str:
        """
        inputs: list of dicts matching your Scraper Studio input schema,
                e.g. [{"url": "https://example.com/page"}]
        job_tag: local identifier for caching (e.g. "techcrunch_batch1")
        scraper_name: which collector to use, must be a key in BRIGHTDATA_SCRAPERS
        Returns a snapshot_id to poll.
        """
        cache_file = self._cache_path(job_tag)
        if use_cache and cache_file.exists():
            raise BrightDataError(
                f"Cached result already exists at {cache_file}. "
                "Delete it if you intentionally want to re-scrape (costs credit)."
            )

        if len(inputs) > settings.MAX_PAGES_PER_SCRAPE:
            inputs = inputs[: settings.MAX_PAGES_PER_SCRAPE]

        collector_id = self._resolve_collector_id(scraper_name)
        url = f"{self.base_url}/trigger?collector={collector_id}&queue_next=1"
        resp = self._http.post(url, json=inputs)
        if resp.status_code != 200:
            raise BrightDataError(f"Trigger failed: {resp.status_code} {resp.text}")

        data = resp.json()
        snapshot_id = data.get("collection_id") or data.get("snapshot_id")
        if not snapshot_id:
            raise BrightDataError(f"No collection_id returned: {data}")
        return snapshot_id

    def poll_and_fetch(
        self,
        snapshot_id: str,
        job_tag: str,
        interval: int | None = None,
        timeout: int | None = None,
    ) -> list[dict]:
        """
        Poll /dca/dataset until it returns a JSON array (ready) instead of
        a status object like {"status": "building"}, then cache + return it.
        """
        interval = interval if interval is not None else settings.SCRAPE_POLL_INTERVAL
        timeout = timeout if timeout is not None else 300
        dataset_url = f"{self.base_url}/dataset?id={snapshot_id}"
        elapsed = 0

        while elapsed < timeout:
            resp = self._http.get(dataset_url)

            # 200 = ready (JSON array) or occasionally a status object.
            # 202 = still collecting — this is expected, not an error.
            if resp.status_code not in (200, 202):
                raise BrightDataError(
                    f"Dataset request failed: {resp.status_code} — {resp.text[:500]}. "
                    f"URL used: {dataset_url}"
                )
            try:
                body = resp.json()
            except Exception:
                # Might be newline-delimited JSON (JSONL) instead of a single
                # JSON array — Bright Data sometimes returns one object per line.
                lines = [l for l in resp.text.strip().split("\n") if l.strip()]
                try:
                    body = [json.loads(l) for l in lines]
                except Exception:
                    raise BrightDataError(
                        f"Dataset endpoint returned unparseable content. "
                        f"Status: {resp.status_code}. Body: {resp.text[:500]}"
                    )

            if isinstance(body, list):
                # Ready — could be empty [] if snapshot had no rows or expired
                cache_file = self._cache_path(job_tag)
                cache_file.write_text(json.dumps(body, separators=(",", ":")))
                return body

            # Still building — body is a status object like
            # {"status": "collecting", "message": "Job is not finished"}
            time.sleep(interval)
            elapsed += interval

        raise BrightDataError(f"Timed out waiting for snapshot {snapshot_id}")

    def scrape(
        self,
        inputs: list[dict],
        job_tag: str,
        scraper_name: str,
        timeout: int | None = None,
    ) -> list[dict]:
        """Convenience: trigger + poll + fetch, with cache short-circuit."""
        cache_file = self._cache_path(job_tag)
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        snapshot_id = self.trigger_scrape(inputs, job_tag, scraper_name, use_cache=False)
        return self.poll_and_fetch(snapshot_id, job_tag, timeout=timeout)


brightdata_client = BrightDataClient()
