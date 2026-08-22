"""
Run a Bright Data collector scrape, normalize, persist, and score health.
Used by /scrape and by the heal loop (diagnose + re-scrape). Same collector ID.
"""
from pathlib import Path

from app.config import settings
from app.scrapers.brightdata_client import brightdata_client
from app.scrapers.catalog import scrape_inputs_for
from app.scrapers.health import calculate_health_metrics
from app.scrapers.normalizer import from_brightdata, save_normalized


def run_brightdata_scrape(
    urls: list[str],
    job_tag: str,
    scraper_name: str,
    force: bool = False,
    timeout: int | None = None,
    max_records: int | None = None,
) -> tuple[list, dict, str]:
    if force:
        cache = Path(settings.RAW_DATA_DIR) / f"brightdata_{job_tag}.json"
        if cache.exists():
            cache.unlink()

    inputs = scrape_inputs_for(scraper_name, urls)
    results = brightdata_client.scrape(
        inputs, job_tag=job_tag, scraper_name=scraper_name, timeout=timeout
    )
    docs = from_brightdata(results)
    limit = max_records if max_records is not None else settings.SCRAPE_MAX_RECORDS
    if limit > 0:
        docs = docs[:limit]
    path = save_normalized(docs, job_tag)
    metrics = calculate_health_metrics(
        [{"title": d.title, "content": d.content} for d in docs]
    )
    if not results:
        # Scrape ran but collector returned no rows — still a real measurement.
        metrics["_measured"] = True
    return docs, metrics, str(path)
