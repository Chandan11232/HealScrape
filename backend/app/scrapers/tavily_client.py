"""
Tavily client — used for search-driven enrichment (finding URLs, quick answers),
not as the primary scraper. Free tier: 1000 calls/month, so headroom is fine,
but we still cap per-run calls to keep behavior predictable in demos.
"""
import json
from pathlib import Path
import httpx
from app.config import settings


class TavilyClient:
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"
        self._calls_this_run = 0
        Path(settings.RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)

    def search(self, query: str, job_tag: str, max_results: int = 5) -> dict:
        if self._calls_this_run >= settings.MAX_TAVILY_CALLS_PER_RUN:
            raise RuntimeError("Tavily call cap reached for this run — raise MAX_TAVILY_CALLS_PER_RUN if intentional.")

        cache_file = Path(settings.RAW_DATA_DIR) / f"tavily_{job_tag}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        resp = httpx.post(
            self.base_url,
            json={
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",  # "advanced" costs more credits — avoid unless needed
            },
            timeout=30,
        )
        resp.raise_for_status()
        self._calls_this_run += 1

        data = resp.json()
        cache_file.write_text(json.dumps(data, indent=2))
        return data


tavily_client = TavilyClient()
