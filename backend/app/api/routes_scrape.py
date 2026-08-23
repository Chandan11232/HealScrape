"""
POST /scrape — trigger a Bright Data collector, normalize, score health.
Unhealthy extraction can auto-start heal on the same collector ID.
"""
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.api.routes_heal import start_heal_job
from app.config import settings
from app.models.heal_schemas import HealthMetrics
from app.models.schemas import ScrapeRequest, ScrapeResponse, HealthSnapshot
from app.scrapers.brightdata_client import brightdata_client, BrightDataError
from app.scrapers.health import calculate_health_metrics, issue_prompt, needs_heal
from app.scrapers.normalizer import from_brightdata, save_normalized
from app.scrapers.scrape_runner import run_brightdata_scrape
from app.scrapers.catalog import scrape_inputs_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scrape", tags=["scrape"])

_scrape_jobs: dict[str, dict] = {}


def _snapshot(metrics: dict) -> HealthSnapshot:
    return HealthSnapshot(
        empty_title_pct=metrics["empty_title_pct"],
        empty_body_pct=metrics["empty_body_pct"],
        success_rate=metrics["success_rate"],
    )


def _background_scrape(urls: list[str], job_tag: str, scraper_name: str, auto_heal: bool) -> None:
    try:
        docs, metrics, path = run_brightdata_scrape(urls, job_tag, scraper_name, force=True)
        _scrape_jobs[job_tag] = {
            "status": "completed",
            "records_found": len(docs),
            "normalized_path": str(path),
            "health": metrics,
            "needs_heal": needs_heal(metrics),
        }
        unhealthy = needs_heal(metrics)
        if auto_heal and unhealthy:
            start_heal_job(
                scraper_name=scraper_name,
                test_url=urls[0],
                job_tag=f"{job_tag}_heal",
                issue_description=issue_prompt(metrics),
                urls=urls,
                skip_diagnose=True,
                before=HealthMetrics(
                    empty_title_pct=float(metrics["empty_title_pct"]),
                    empty_body_pct=float(metrics["empty_body_pct"]),
                    success_rate=float(metrics["success_rate"]),
                ),
                rescrape_after=False,
                auto_approve=True,
            )
    except Exception as e:
        logger.exception("Background scrape failed for %s", job_tag)
        _scrape_jobs[job_tag] = {"status": "failed", "error": str(e)}


@router.post("", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest):
    if req.source != "brightdata":
        raise HTTPException(
            status_code=400,
            detail="Only source=brightdata is supported. Use Scraper Studio collectors.",
        )
    if not req.scraper_name:
        raise HTTPException(status_code=400, detail="scraper_name is required")
    if not req.urls:
        raise HTTPException(status_code=400, detail="urls is required")

    collector_id = settings.BRIGHTDATA_SCRAPERS.get(req.scraper_name)
    if not collector_id:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scraper_name '{req.scraper_name}'. "
            f"Available: {list(settings.BRIGHTDATA_SCRAPERS.keys())}",
        )

    _scrape_jobs[req.job_tag] = {"status": "triggering"}

    try:
        inputs = scrape_inputs_for(req.scraper_name, req.urls)
        snapshot_id = brightdata_client.trigger_scrape(inputs, req.job_tag, req.scraper_name, use_cache=False)
    except BrightDataError as e:
        _scrape_jobs[req.job_tag] = {"status": "failed", "error": str(e)}
        raise HTTPException(status_code=502, detail=str(e))

    _scrape_jobs[req.job_tag] = {
        "status": "running",
        "snapshot_id": snapshot_id,
    }

    asyncio.create_task(asyncio.to_thread(
        _poll_and_finish, snapshot_id, req.job_tag, req.scraper_name, req.urls, req.auto_heal
    ))

    return ScrapeResponse(
        job_tag=req.job_tag,
        source="brightdata",
        records_found=0,
        normalized_path="",
        health=None,
        needs_heal=False,
        heal_started=False,
        heal_job_tag=None,
        message=f"Scrape triggered. Snapshot {snapshot_id}. Poll GET /scrape/{req.job_tag}/status",
    )


def _poll_and_finish(snapshot_id: str, job_tag: str, scraper_name: str, urls: list[str], auto_heal: bool) -> None:
    try:
        results = brightdata_client.poll_and_fetch(snapshot_id, job_tag, timeout=300)
        docs = from_brightdata(results)
        limit = settings.SCRAPE_MAX_RECORDS
        if limit > 0:
            docs = docs[:limit]
        path = save_normalized(docs, job_tag)
        metrics = calculate_health_metrics(
            [{"title": d.title, "content": d.content} for d in docs]
        )
        if not results:
            metrics["_measured"] = True

        _scrape_jobs[job_tag] = {
            "status": "completed",
            "records_found": len(docs),
            "normalized_path": str(path),
            "health": metrics,
            "needs_heal": needs_heal(metrics),
        }

        unhealthy = needs_heal(metrics)
        if auto_heal and unhealthy:
            start_heal_job(
                scraper_name=scraper_name,
                test_url=urls[0],
                job_tag=f"{job_tag}_heal",
                issue_description=issue_prompt(metrics),
                urls=urls,
                skip_diagnose=True,
                before=HealthMetrics(
                    empty_title_pct=float(metrics["empty_title_pct"]),
                    empty_body_pct=float(metrics["empty_body_pct"]),
                    success_rate=float(metrics["success_rate"]),
                ),
                rescrape_after=False,
                auto_approve=True,
            )
    except Exception as e:
        logger.exception("Scrape poll failed for %s", job_tag)
        _scrape_jobs[job_tag] = {"status": "failed", "error": str(e)}


@router.get("/{job_tag}/status")
async def scrape_status(job_tag: str):
    if job_tag not in _scrape_jobs:
        raise HTTPException(status_code=404, detail=f"No scrape job '{job_tag}' found")
    return _scrape_jobs[job_tag]
