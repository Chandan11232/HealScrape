"""Scrape only — no sentence-transformers / torch."""
from __future__ import annotations

import json

from app.scrapers.scrape_runner import run_brightdata_scrape

JOBS = [
    ("tiangolo", "tiangolo_demo", "https://fastapi.tiangolo.com/tutorial/dependencies/"),
    ("react", "react_demo", "https://react.dev/reference/rsc/server-components"),
    ("wikipedia_ai", "wikipedia_ai_demo", "https://en.wikipedia.org/wiki/Artificial_intelligence"),
    ("python_docs", "python_docs_demo", "https://docs.python.org/3/tutorial/introduction.html"),
    ("openai", "openai_demo", "https://openai.com/index/chatgpt/"),
    ("devpost", "devpost_demo", "https://devpost.com/software"),
]


def main() -> None:
    summary = []
    for scraper_name, job_tag, url in JOBS:
        print(f"\n=== scrape {scraper_name} ===", flush=True)
        try:
            docs, metrics, path = run_brightdata_scrape(
                urls=[url],
                job_tag=job_tag,
                scraper_name=scraper_name,
                force=True,
                timeout=180,
            )
            row = {
                "scraper_name": scraper_name,
                "job_tag": job_tag,
                "ok": True,
                "records": len(docs),
                "success_rate": metrics.get("success_rate"),
                "path": path,
            }
            print(json.dumps(row), flush=True)
            summary.append(row)
        except Exception as e:
            row = {
                "scraper_name": scraper_name,
                "job_tag": job_tag,
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            }
            print(json.dumps(row), flush=True)
            summary.append(row)
    print("\n=== scrape summary ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
