"""
POST /scrape — trigger a Bright Data collector, normalize, score health.
Unhealthy extraction can auto-start heal on the same collector ID.
"""
import asyncio
from fastapi import APIRouter, HTTPException

from app.api.routes_heal import start_heal_job
from app.models.heal_schemas import HealthMetrics
from app.models.schemas import ScrapeRequest, ScrapeResponse, HealthSnapshot
from app.scrapers.brightdata_client import BrightDataError
from app.scrapers.health import calculate_health_metrics, issue_prompt, needs_heal
from app.scrapers.scrape_runner import run_brightdata_scrape

router = APIRouter(prefix="/scrape", tags=["scrape"])


def _snapshot(metrics: dict) -> HealthSnapshot:
    return HealthSnapshot(
        empty_title_pct=metrics["empty_title_pct"],
        empty_body_pct=metrics["empty_body_pct"],
        success_rate=metrics["success_rate"],
    )


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

    heal_started = False
    try:
        docs, metrics, path = await asyncio.to_thread(
            run_brightdata_scrape,
            req.urls,
            req.job_tag,
            req.scraper_name,
            False,
        )
    except BrightDataError as e:
        raise HTTPException(status_code=502, detail=str(e))

    unhealthy = needs_heal(metrics)
    if req.auto_heal and unhealthy:
        start_heal_job(
            scraper_name=req.scraper_name,
            test_url=req.urls[0],
            job_tag=req.job_tag,
            issue_description=issue_prompt(metrics),
            urls=req.urls,
            skip_diagnose=True,
            before=HealthMetrics(
                empty_title_pct=float(metrics["empty_title_pct"]),
                empty_body_pct=float(metrics["empty_body_pct"]),
                success_rate=float(metrics["success_rate"]),
            ),
            rescrape_after=False,
            auto_approve=True,
        )
        heal_started = True
        message = (
            f"Extraction unhealthy (success {metrics['success_rate']}%). "
            "Started self-heal on the same collector; poll GET /heal/{job_tag}."
        )
    elif unhealthy:
        message = (
            f"Extraction unhealthy (success {metrics['success_rate']}%). "
            "Pass auto_heal=true to repair this collector in place."
        )
    else:
        message = f"Collector healthy (success {metrics['success_rate']}%). No heal needed."

    return ScrapeResponse(
        job_tag=req.job_tag,
        source="brightdata",
        records_found=len(docs),
        normalized_path=str(path),
        health=_snapshot(metrics),
        needs_heal=unhealthy,
        heal_started=heal_started,
        heal_job_tag=req.job_tag if heal_started else None,
        message=message,
    )
