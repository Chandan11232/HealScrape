"""
POST /scrape — trigger a collector, normalize, score health.
For Bright Data, unhealthy extraction can auto-start heal on the same
collector ID, then the heal loop re-scrapes.
"""
import asyncio
from fastapi import APIRouter, HTTPException

from app.api.routes_heal import start_heal_job
from app.models.heal_schemas import HealthMetrics
from app.models.schemas import ScrapeRequest, ScrapeResponse, HealthSnapshot
from app.scrapers.brightdata_client import BrightDataError
from app.scrapers.firecrawl_client import firecrawl_client
from app.scrapers.tavily_client import tavily_client
from app.scrapers.health import calculate_health_metrics, issue_prompt, needs_heal
from app.scrapers.normalizer import from_firecrawl, from_tavily, save_normalized
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
    health = None
    heal_started = False
    message = ""

    if req.source == "brightdata":
        if not req.scraper_name:
            raise HTTPException(status_code=400, detail="scraper_name is required for source=brightdata")
        if not req.urls:
            raise HTTPException(status_code=400, detail="urls is required for source=brightdata")
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

        health = metrics
        unhealthy = needs_heal(metrics)
        if req.auto_heal and unhealthy:
            start_heal_job(
                scraper_name=req.scraper_name,
                test_url=req.urls[0],
                job_tag=req.job_tag,
                issue_description=issue_prompt(metrics),
                urls=req.urls,
                skip_diagnose=True,
                before=HealthMetrics(**metrics),
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

    elif req.source == "firecrawl":
        if len(req.urls) != 1:
            raise HTTPException(status_code=400, detail="firecrawl source expects exactly one URL")
        data = await asyncio.to_thread(
            firecrawl_client.scrape_url, req.urls[0], req.job_tag
        )
        docs = from_firecrawl([data.get("data", data)])
        path = str(save_normalized(docs, req.job_tag))
        health = calculate_health_metrics([{"title": d.title, "content": d.content} for d in docs])
        message = "Firecrawl scrape stored. Self-heal applies to Bright Data collectors only."

    elif req.source == "tavily":
        if not req.tavily_query:
            raise HTTPException(status_code=400, detail="tavily_query is required for source=tavily")
        data = await asyncio.to_thread(
            tavily_client.search, req.tavily_query, req.job_tag
        )
        docs = from_tavily(data)
        path = str(save_normalized(docs, req.job_tag))
        health = calculate_health_metrics([{"title": d.title, "content": d.content} for d in docs])
        message = "Tavily search stored. Self-heal applies to Bright Data collectors only."

    else:
        raise HTTPException(status_code=400, detail=f"Unknown source: {req.source}")

    return ScrapeResponse(
        job_tag=req.job_tag,
        source=req.source,
        records_found=len(docs),
        normalized_path=str(path),
        health=_snapshot(health) if health else None,
        needs_heal=needs_heal(health) if health else False,
        heal_started=heal_started,
        heal_job_tag=req.job_tag if heal_started else None,
        message=message,
    )
