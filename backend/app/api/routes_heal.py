"""
POST /heal — start a background self-healing job.
GET  /heal/{job_tag} — poll status; also nudges stuck jobs forward.

Loop (same collector ID throughout):
  diagnose (scrape + real health) → Bright Data heal → re-scrape → after metrics
"""
from __future__ import annotations

import asyncio
import time
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.heal_schemas import HealRequest, HealResponse, HealthMetrics
from app.scrapers.health import (
    get_current_health,
    issue_prompt,
    needs_heal,
    calculate_health_metrics,
    is_placeholder,
    PLACEHOLDER_HEALTH,
)
from app.scrapers.scrape_runner import run_brightdata_scrape
from app.scrapers.self_heal import (
    trigger_heal,
    fetch_heal_progress,
    auto_approve_heal,
    progress_message,
    DONE_STATUSES,
    FAIL_STATUSES,
    APPROVE_STATUSES,
)

router = APIRouter(prefix="", tags=["heal"])

heal_jobs: dict[str, dict] = {}
_heal_loops: set[str] = set()

MAX_HEAL_SECONDS = 480  # 8 minutes hard cap per job


def _metrics(data: dict) -> HealthMetrics:
    return HealthMetrics(
        empty_title_pct=data.get("empty_title_pct", 0.0),
        empty_body_pct=data.get("empty_body_pct", 0.0),
        success_rate=data.get("success_rate", 0.0),
    )


def _to_response(job_tag: str) -> HealResponse:
    job = heal_jobs[job_tag]
    elapsed = int(time.time() - job.get("started_at", time.time()))
    message = job.get("message", "")
    if job["status"] == "healing":
        message = f"{message} ({elapsed}s elapsed)"
    return HealResponse(
        status=job["status"],
        job_tag=job_tag,
        before=job["before"],
        after=job.get("after"),
        improved=job.get("improved", False),
        message=message,
        heal_job_id=job.get("heal_job_id"),
        step=job.get("step"),
        scraper_name=job.get("scraper_name"),
    )


def _set_job(job_tag: str, **updates) -> None:
    heal_jobs[job_tag].update(updates)


def _finish_with_metrics(job_tag: str, after: HealthMetrics, message: str) -> None:
    before = heal_jobs[job_tag]["before"]
    before_dict = before.model_dump()
    after_dict = after.model_dump()
    if is_placeholder(before_dict):
        improved = after.success_rate > 0 and after.empty_body_pct < 100
    else:
        improved = after.success_rate > before.success_rate or (
            after.empty_title_pct < before.empty_title_pct
            and after.empty_body_pct < before.empty_body_pct
        )
    if is_placeholder(after_dict) and not is_placeholder(before_dict):
        improved = False
    _set_job(
        job_tag,
        status="completed",
        step="done",
        after=after,
        improved=improved,
        message=message,
    )


def _preview_records(data: dict) -> list[dict]:
    preview = data.get("preview_result") or data.get("preview") or data.get("sample_result")
    if isinstance(preview, list):
        return [p for p in preview if isinstance(p, dict)]
    if isinstance(preview, dict):
        return [preview]
    return []


def _complete_from_preview_or_skip(job_tag: str) -> None:
    job = heal_jobs[job_tag]
    records = job.get("preview_records") or []
    if records:
        after = _metrics(calculate_health_metrics(records))
        _finish_with_metrics(
            job_tag,
            after,
            "Collector healed in place. After metrics are from Bright Data's heal preview (re-scrape skipped).",
        )
        return
    before = job["before"]
    _finish_with_metrics(
        job_tag,
        before,
        "Collector healed in place (same ID). Re-scrape skipped to save time — enable it for live after-metrics.",
    )


def _diagnose_sync(job_tag: str) -> None:
    job = heal_jobs[job_tag]
    urls = job.get("urls") or ([job["test_url"]] if job.get("test_url") else [])
    if not urls:
        _set_job(job_tag, status="failed", step="failed", message="No test URL to scrape.")
        return
    try:
        _docs, metrics, _path = run_brightdata_scrape(
            urls=urls,
            job_tag=job_tag,
            scraper_name=job["scraper_name"],
            force=False,
            timeout=settings.HEAL_SCRAPE_TIMEOUT,
        )
    except Exception as e:
        metrics = dict(PLACEHOLDER_HEALTH)
        _set_job(job_tag, message=f"Diagnose scrape failed ({e}); still sending collector to Bright Data heal.")

    before = _metrics(metrics)
    prompt = job.get("issue_description") or issue_prompt(metrics)

    if not job.get("force_heal") and not needs_heal(metrics):
        _set_job(job_tag, before=before, issue_description=prompt)
        _finish_with_metrics(
            job_tag,
            before,
            f"Collector already healthy (success {before.success_rate}%). Skipped Bright Data heal.",
        )
        return

    _set_job(
        job_tag,
        before=before,
        issue_description=prompt,
        phase="trigger",
        step="triggering",
        message=f"Diagnosed success {before.success_rate}% — starting Bright Data heal on the same collector.",
    )


def _rescrape_sync(job_tag: str) -> None:
    job = heal_jobs[job_tag]
    urls = job.get("urls") or ([job["test_url"]] if job.get("test_url") else [])
    try:
        _docs, metrics, _path = run_brightdata_scrape(
            urls=urls,
            job_tag=job_tag,
            scraper_name=job["scraper_name"],
            force=True,
            timeout=settings.HEAL_SCRAPE_TIMEOUT,
        )
        after = _metrics(metrics)
        _finish_with_metrics(
            job_tag,
            after,
            "Collector healed in place and re-scraped. Same Bright Data collector ID throughout.",
        )
    except Exception as e:
        after = _metrics(get_current_health(job_tag))
        _finish_with_metrics(
            job_tag,
            after,
            f"Collector updated on Bright Data, but re-scrape failed: {e}",
        )


async def _advance_heal_step(job_tag: str) -> None:
    job = heal_jobs[job_tag]
    if job["status"] != "healing":
        return

    collector_id = job["collector_id"]
    phase = job.get("phase", "trigger")

    if phase == "diagnose":
        _set_job(job_tag, step="diagnosing", message="Scraping to measure extraction health...")
        await asyncio.to_thread(_diagnose_sync, job_tag)
        return

    if phase == "rescrape":
        _set_job(job_tag, step="rescraping", message="Re-scraping with the same collector ID...")
        await asyncio.to_thread(_rescrape_sync, job_tag)
        return

    if phase == "trigger":
        _set_job(job_tag, step="triggering", message="Sending fix request to Bright Data AI...")
        heal_result = await trigger_heal(
            scraper_name=job["scraper_name"],
            collector_id=collector_id,
            issue_description=job["issue_description"] or issue_prompt(
                {"empty_title_pct": job["before"].empty_title_pct,
                 "empty_body_pct": job["before"].empty_body_pct,
                 "success_rate": job["before"].success_rate}
            ),
            test_url=job["test_url"],
            job_tag=job_tag,
        )
        if heal_result.get("status") == "error":
            _set_job(job_tag, status="failed", step="failed", message=heal_result["message"])
            return
        _set_job(job_tag, phase="poll", heal_job_id=collector_id)
        return

    try:
        data = await fetch_heal_progress(collector_id)
    except Exception as e:
        _set_job(job_tag, message=f"Waiting for Bright Data... ({e})")
        return

    status = data.get("status", "")
    step = data.get("step") or "waiting"
    preview = _preview_records(data)
    updates = {"step": step, "message": progress_message(data)}
    if preview:
        updates["preview_records"] = preview
    _set_job(job_tag, **updates)

    if status in FAIL_STATUSES:
        _set_job(job_tag, status="failed", step="failed", message=f"Heal failed: {status}")
        return

    if status in DONE_STATUSES:
        if job.get("rescrape_after"):
            _set_job(
                job_tag,
                phase="rescrape",
                step="rescraping",
                message="Bright Data saved the collector — re-scraping to measure after metrics...",
            )
        else:
            _complete_from_preview_or_skip(job_tag)
        return

    if status in APPROVE_STATUSES or step == "user_approval":
        if not job.get("approved"):
            _set_job(job_tag, step="approving", message="Auto-approving AI-proposed fix...")
            approve_result = await auto_approve_heal(collector_id)
            if approve_result["status"] == "error":
                _set_job(job_tag, status="failed", step="failed", message=approve_result["message"])
                return
            _set_job(job_tag, approved=True, phase="poll", message="Fix approved — saving collector...")
        return


async def _heal_loop(job_tag: str) -> None:
    if job_tag in _heal_loops:
        return
    _heal_loops.add(job_tag)
    try:
        while heal_jobs.get(job_tag, {}).get("status") == "healing":
            if time.time() - heal_jobs[job_tag]["started_at"] > MAX_HEAL_SECONDS:
                _set_job(
                    job_tag,
                    status="failed",
                    step="failed",
                    message="Heal timed out after 8 minutes. Try again or approve manually in Bright Data.",
                )
                break
            await _advance_heal_step(job_tag)
            if heal_jobs[job_tag]["status"] != "healing":
                break
            await asyncio.sleep(settings.HEAL_POLL_SECONDS)
    finally:
        _heal_loops.discard(job_tag)


def _ensure_loop(job_tag: str) -> None:
    if job_tag in heal_jobs and heal_jobs[job_tag]["status"] == "healing":
        asyncio.create_task(_heal_loop(job_tag))


def start_heal_job(
    *,
    scraper_name: str,
    test_url: str,
    job_tag: str,
    issue_description: str = "",
    urls: list[str] | None = None,
    skip_diagnose: bool = False,
    before: HealthMetrics | None = None,
    force_heal: bool = True,
    rescrape_after: bool = False,
) -> HealResponse:
    existing = heal_jobs.get(job_tag)
    if existing and existing.get("status") == "healing":
        _ensure_loop(job_tag)
        return _to_response(job_tag)

    collector_id = settings.BRIGHTDATA_SCRAPERS.get(scraper_name)
    if not collector_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown scraper_name '{scraper_name}'. "
                f"Available: {list(settings.BRIGHTDATA_SCRAPERS.keys())}."
            ),
        )

    url_list = urls or ([test_url] if test_url else [])
    stored = get_current_health(job_tag)
    before_metrics = before or _metrics(stored)
    has_real_before = before is not None or not is_placeholder(stored)
    stored_or_before = before.model_dump() if before else stored

    if not force_heal and has_real_before and not needs_heal(stored_or_before):
        heal_jobs[job_tag] = {
            "status": "completed",
            "phase": "done",
            "step": "done",
            "message": (
                f"Collector already healthy (success {before_metrics.success_rate}%). "
                "Skipped Bright Data heal."
            ),
            "heal_job_id": collector_id,
            "collector_id": collector_id,
            "scraper_name": scraper_name,
            "issue_description": issue_description.strip(),
            "test_url": test_url,
            "urls": url_list,
            "before": before_metrics,
            "after": before_metrics,
            "improved": False,
            "approved": False,
            "force_heal": force_heal,
            "rescrape_after": rescrape_after,
            "started_at": time.time(),
        }
        return _to_response(job_tag)

    prompt = issue_description.strip() or issue_prompt(
        {
            "empty_title_pct": before_metrics.empty_title_pct,
            "empty_body_pct": before_metrics.empty_body_pct,
            "success_rate": before_metrics.success_rate,
        }
    )

    # Skip a second scrape when this job_tag already has real normalized metrics.
    initial_phase = "trigger" if (skip_diagnose or has_real_before) else "diagnose"
    heal_jobs[job_tag] = {
        "status": "healing",
        "phase": initial_phase,
        "step": "queued" if initial_phase == "trigger" else "diagnosing",
        "message": (
            "Starting Bright Data heal on the same collector..."
            if initial_phase == "trigger"
            else "Queued — will scrape, then heal the same collector if needed."
        ),
        "heal_job_id": collector_id,
        "collector_id": collector_id,
        "scraper_name": scraper_name,
        "issue_description": prompt,
        "test_url": test_url,
        "urls": url_list,
        "before": before_metrics,
        "after": None,
        "improved": False,
        "approved": False,
        "force_heal": force_heal,
        "rescrape_after": rescrape_after,
        "started_at": time.time(),
    }
    _ensure_loop(job_tag)
    return _to_response(job_tag)


@router.post("/heal", response_model=HealResponse)
async def heal_endpoint(req: HealRequest):
    return start_heal_job(
        scraper_name=req.scraper_name,
        test_url=req.test_url,
        job_tag=req.job_tag,
        issue_description=req.issue_description,
        urls=[req.test_url] if req.test_url else None,
        skip_diagnose=req.skip_diagnose,
        force_heal=req.force_heal,
        rescrape_after=req.rescrape_after,
    )


@router.get("/heal/{job_tag}", response_model=HealResponse)
async def get_heal_status(job_tag: str):
    if job_tag not in heal_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_tag} not found")
    _ensure_loop(job_tag)
    return _to_response(job_tag)


_ZERO = HealthMetrics(empty_title_pct=0.0, empty_body_pct=0.0, success_rate=0.0)


@router.post("/heal/{job_tag}/cancel", response_model=HealResponse)
async def cancel_heal(job_tag: str):
    if job_tag not in heal_jobs:
        return HealResponse(
            status="failed",
            job_tag=job_tag,
            before=_ZERO,
            after=None,
            improved=False,
            message="No active heal job (already gone or server restarted).",
            step="failed",
        )
    _set_job(
        job_tag,
        status="failed",
        step="failed",
        message="Heal cancelled by user.",
    )
    return _to_response(job_tag)
