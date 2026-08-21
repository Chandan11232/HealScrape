"""
POST /heal — start a background self-healing job.
GET  /heal/{job_tag} — poll status; also nudges stuck jobs forward.

Loop (same collector ID throughout):
  [diagnose scrape] → Bright Data heal (join/approve) → after from preview (or optional re-scrape)

Rules:
- Diagnose & auto-heal measures before; Force heal skips diagnose for speed
- After prefers Bright Data heal preview (reliable); optional live re-scrape
- Never invent healthy scores; never soft-abort BD AI in under ~7 minutes
- pending_answer must be auto-approved when preview looks usable
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
    compute_improved,
    metrics_equal,
)
from app.scrapers.scrape_runner import run_brightdata_scrape
from app.scrapers.self_heal import (
    trigger_heal,
    fetch_heal_progress,
    auto_approve_heal,
    reject_heal,
    progress_message,
    normalize_status,
    preview_records,
    preview_looks_usable,
    DONE_STATUSES,
    FAIL_STATUSES,
    APPROVE_STATUSES,
    ACTIVE_STATUSES,
)

router = APIRouter(prefix="", tags=["heal"])

heal_jobs: dict[str, dict] = {}
_heal_loops: set[str] = set()

# Bright Data AI alone often needs several minutes; soft-complete rather than hard-fail.
MAX_HEAL_SECONDS = settings.HEAL_MAX_SECONDS
STUCK_STEP_SECONDS = settings.HEAL_STUCK_STEP_SECONDS
MAX_ACTIVE_WATCH_SECONDS = settings.HEAL_ACTIVE_WATCH_SECONDS
MAX_HEAL_ATTEMPTS = 0  # never chain another long Bright Data AI job after a bad preview


def _metrics(data: dict) -> HealthMetrics:
    return HealthMetrics(
        empty_title_pct=float(data.get("empty_title_pct", 0.0)),
        empty_body_pct=float(data.get("empty_body_pct", 0.0)),
        success_rate=float(data.get("success_rate", 0.0)),
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
        before_source=job.get("before_source"),
        after_source=job.get("after_source"),
    )


def _set_job(job_tag: str, **updates) -> None:
    heal_jobs[job_tag].update(updates)


def _finish(
    job_tag: str,
    *,
    after: HealthMetrics | None,
    after_source: str,
    message: str,
    status: str = "completed",
) -> None:
    job = heal_jobs[job_tag]
    before = job["before"]
    before_dict = before.model_dump()
    after_dict = after.model_dump() if after is not None else None
    improved = compute_improved(
        before_dict,
        after_dict,
        before_source=job.get("before_source"),
        after_source=after_source,
    )

    if after is not None and metrics_equal(before_dict, after_dict) and "unchanged" not in message.lower():
        message = (
            f"{message.rstrip('.')} — metrics unchanged "
            f"(success stayed {before.success_rate}%)."
        )

    _set_job(
        job_tag,
        status=status,
        step="done" if status == "completed" else "failed",
        after=after,
        after_source=after_source,
        improved=improved,
        message=message,
    )


def _finish_unchanged(job_tag: str, message: str) -> None:
    """Heal did not change the collector — still produce after-metrics when possible."""
    job = heal_jobs[job_tag]
    _set_job(job_tag, bd_success=False)

    # Prefer any measured preview over another long scrape when heal was aborted.
    preview_after = _after_from_preview(job)
    if preview_after is not None:
        _finish(
            job_tag,
            after=preview_after,
            after_source="preview",
            message=(
                f"{message.rstrip('.')} After metrics are from the last Bright Data preview."
            ),
            status="completed",
        )
        return

    urls = job.get("urls") or ([job["test_url"]] if job.get("test_url") else [])
    if job.get("rescrape_after") and urls:
        _set_job(
            job_tag,
            phase="rescrape",
            step="rescraping",
            message=(
                f"{message.rstrip('.')} — re-scraping for after-metrics "
                "(collector was left unchanged)..."
            ),
        )
        return

    before = job["before"]
    _finish(
        job_tag,
        after=before,
        after_source="unchanged",
        message=(
            f"{message.rstrip('.')} After metrics match before "
            f"(success {before.success_rate}%; collector left unchanged)."
        ),
        status="completed",
    )


def _complete_after_bright_data(job_tag: str) -> None:
    """After BD heal: prefer measured preview (fast/reliable); optional live re-scrape."""
    job = heal_jobs[job_tag]
    urls = job.get("urls") or ([job["test_url"]] if job.get("test_url") else [])

    # Prefer heal preview when it maps to title/body — avoids long snapshot timeouts.
    preview_after = _after_from_preview(job)
    if preview_after is not None and not job.get("rescrape_after"):
        _finish(
            job_tag,
            after=preview_after,
            after_source="preview",
            message=(
                "Bright Data heal finished on the same collector. "
                "After metrics are from the heal preview."
            ),
        )
        return

    if job.get("rescrape_after", False) and urls:
        _set_job(
            job_tag,
            phase="rescrape",
            step="rescraping",
            message="Bright Data saved the collector — re-scraping for live after-metrics...",
        )
        return

    if preview_after is not None:
        _finish(
            job_tag,
            after=preview_after,
            after_source="preview",
            message=(
                "Bright Data heal finished. After metrics are from heal preview "
                "(live re-scrape was not requested)."
            ),
        )
        return

    if urls:
        # No usable preview — fall back to a live scrape once.
        _set_job(
            job_tag,
            phase="rescrape",
            step="rescraping",
            message="No usable heal preview — re-scraping for after-metrics...",
        )
        return

    _finish(
        job_tag,
        after=None,
        after_source="none",
        message=(
            "Bright Data heal finished on the same collector ID, but after-metrics were not measured "
            "(no usable preview and no test URL for re-scrape)."
        ),
    )


def _scrape_with_retries(
    *,
    urls: list[str],
    job_tag: str,
    scraper_name: str,
) -> tuple[list, dict, str]:
    """Run Bright Data scrape; retry on timeout/transient errors."""
    attempts = max(1, int(getattr(settings, "HEAL_SCRAPE_RETRIES", 2)))
    timeout = settings.HEAL_SCRAPE_TIMEOUT
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return run_brightdata_scrape(
                urls=urls,
                job_tag=f"{job_tag}__try{i + 1}" if i else job_tag,
                scraper_name=scraper_name,
                force=True,
                timeout=timeout,
            )
        except Exception as e:
            last_err = e
            if i + 1 < attempts:
                time.sleep(2)
    assert last_err is not None
    raise last_err


def _after_from_preview(job: dict) -> HealthMetrics | None:
    records = job.get("preview_records") or []
    if not records:
        return None
    raw = calculate_health_metrics(records)
    if not raw.get("_measured"):
        return None
    return _metrics(raw)


def _diagnose_sync(job_tag: str) -> None:
    job = heal_jobs[job_tag]
    urls = job.get("urls") or ([job["test_url"]] if job.get("test_url") else [])
    if not urls:
        _set_job(job_tag, status="failed", step="failed", message="No test URL to scrape.")
        return
    try:
        _docs, metrics, _path = _scrape_with_retries(
            urls=urls,
            job_tag=f"{job_tag}__before",
            scraper_name=job["scraper_name"],
        )
        before_source = "diagnose_scrape"
    except Exception as e:
        metrics = dict(PLACEHOLDER_HEALTH)
        before_source = "placeholder"
        _set_job(
            job_tag,
            message=(
                f"Diagnose scrape failed ({e}). "
                "Before metrics are unknown placeholders — still attempting Bright Data heal."
            ),
        )

    before = _metrics(metrics)
    prompt = (job.get("issue_description") or "").strip() or issue_prompt(metrics)

    if not job.get("force_heal") and not needs_heal(metrics):
        _set_job(
            job_tag,
            before=before,
            before_source=before_source,
            issue_description=prompt,
        )
        _finish(
            job_tag,
            after=before,
            after_source="skipped_healthy",
            message=(
                f"Collector already healthy (success {before.success_rate}%). "
                "Skipped Bright Data heal — no fix was applied."
            ),
        )
        return

    _set_job(
        job_tag,
        before=before,
        before_source=before_source,
        issue_description=prompt,
        phase="trigger",
        step="triggering",
        message=(
            f"Diagnosed success {before.success_rate}% "
            f"(empty title {before.empty_title_pct}%, empty body {before.empty_body_pct}%) "
            "— starting Bright Data heal on the same collector."
        ),
    )


def _rescrape_sync(job_tag: str) -> None:
    job = heal_jobs[job_tag]
    urls = job.get("urls") or ([job["test_url"]] if job.get("test_url") else [])
    before = job.get("before")
    before_source = job.get("before_source")

    try:
        _docs, metrics, _path = _scrape_with_retries(
            urls=urls,
            job_tag=f"{job_tag}__after",
            scraper_name=job["scraper_name"],
        )
        after = _metrics(metrics)
        measured = bool(metrics.get("_measured", not is_placeholder(metrics)))
        if job.get("bd_success"):
            msg = (
                "Collector healed in place and re-scraped. After metrics are from a live scrape."
                if measured
                else (
                    "Collector updated on Bright Data, but the live re-scrape returned no "
                    "extractable title/body rows. After metrics reflect that empty result."
                )
            )
        else:
            msg = (
                "Heal did not change the collector. After metrics are from a live re-scrape "
                "of the current (unchanged) extractor."
                if measured
                else (
                    "Heal did not change the collector. Live re-scrape returned no extractable "
                    "title/body rows — after metrics reflect that empty result."
                )
            )
        _finish(job_tag, after=after, after_source="rescrape", message=msg)
        return
    except Exception as e:
        scrape_err = e

    # Fallbacks so the UI never ends on after=n/a when we have any signal.
    preview_after = _after_from_preview(job)
    if preview_after is not None:
        _finish(
            job_tag,
            after=preview_after,
            after_source="preview",
            message=(
                f"Live re-scrape failed ({scrape_err}). "
                "After metrics are from Bright Data heal preview instead."
            ),
        )
        return

    if before is not None and before_source in ("diagnose_scrape", "cached"):
        _finish(
            job_tag,
            after=before,
            after_source="unchanged" if not job.get("bd_success") else "preview",
            message=(
                f"Live re-scrape failed ({scrape_err}). "
                f"Showing before metrics as after (success {before.success_rate}%) — "
                "re-run later for a fresh after scrape."
            ),
        )
        return

    if before is not None:
        _finish(
            job_tag,
            after=before,
            after_source="unchanged",
            message=(
                f"Live re-scrape failed ({scrape_err}). "
                "After could not be measured; showing the same stand-in numbers as before. "
                "Re-run later for a fresh after scrape."
            ),
        )
        return

    _finish(
        job_tag,
        after=None,
        after_source="none",
        message=(
            f"Collector may be updated on Bright Data, but re-scrape failed: {scrape_err}. "
            "After metrics were not measured."
        ),
    )


async def _maybe_retry_heal(job_tag: str, reason: str) -> bool:
    """Reject bad state if needed and schedule another trigger. Returns True if retrying."""
    job = heal_jobs[job_tag]
    attempts = int(job.get("heal_attempts", 0))
    if attempts >= MAX_HEAL_ATTEMPTS:
        return False

    collector_id = job["collector_id"]
    try:
        data = await fetch_heal_progress(collector_id)
        status = normalize_status(data)
        if status in APPROVE_STATUSES:
            await reject_heal(collector_id)
            await asyncio.sleep(1.5)
    except Exception:
        pass

    _set_job(
        job_tag,
        heal_attempts=attempts + 1,
        approved=False,
        bd_success=False,
        phase="trigger",
        step="triggering",
        message=f"{reason} Retrying Bright Data heal ({attempts + 1}/{MAX_HEAL_ATTEMPTS})...",
    )
    return True


async def _handle_pending_answer(job_tag: str, data: dict) -> None:
    job = heal_jobs[job_tag]
    collector_id = job["collector_id"]
    preview = preview_records(data)
    if preview:
        _set_job(job_tag, preview_records=preview)

    usable = preview_looks_usable(data)
    if not usable:
        # Bad proposal — reject and retry instead of approving a broken template.
        if await _maybe_retry_heal(job_tag, "AI proposal had empty/unusable preview."):
            return
        _finish_unchanged(
            job_tag,
            "Bright Data returned an unusable heal proposal and retries are exhausted. "
            "Collector left unchanged.",
        )
        return

    if not job.get("approved"):
        _set_job(job_tag, step="approving", message="Auto-approving AI-proposed fix...")
        approve_result = await auto_approve_heal(collector_id)
        if approve_result["status"] == "error":
            # Approval race: another client may have approved — re-check progress.
            try:
                again = await fetch_heal_progress(collector_id)
                if normalize_status(again) in DONE_STATUSES:
                    _set_job(job_tag, approved=True, bd_success=bool(again.get("success", True)))
                    _complete_after_bright_data(job_tag)
                    return
            except Exception:
                pass
            if await _maybe_retry_heal(job_tag, f"Approve failed ({approve_result['message']})."):
                return
            _finish_unchanged(
                job_tag,
                f"Could not auto-approve Bright Data proposal ({approve_result['message']}). "
                "Collector left unchanged — re-run heal to try again.",
            )
            return
        _set_job(job_tag, approved=True, phase="poll", message="Fix approved — saving collector...")


async def _advance_heal_step(job_tag: str) -> None:
    job = heal_jobs[job_tag]
    if job["status"] != "healing":
        return

    collector_id = job["collector_id"]
    phase = job.get("phase", "trigger")

    if phase == "diagnose":
        _set_job(job_tag, step="diagnosing", message="Scraping to measure extraction health (before)...")
        await asyncio.to_thread(_diagnose_sync, job_tag)
        return

    if phase == "rescrape":
        _set_job(job_tag, step="rescraping", message="Re-scraping with the same collector ID (after)...")
        await asyncio.to_thread(_rescrape_sync, job_tag)
        return

    if phase == "trigger":
        _set_job(job_tag, step="triggering", message="Sending fix request to Bright Data AI...")
        # Inspect first so we join pending_answer / running jobs instead of hard-failing.
        try:
            existing = await fetch_heal_progress(collector_id)
            existing_status = normalize_status(existing)
            step = existing.get("step") or ""
            preview = preview_records(existing)
            if preview:
                _set_job(job_tag, preview_records=preview)

            if existing_status in APPROVE_STATUSES or (
                step == "user_approval" and existing_status not in DONE_STATUSES | FAIL_STATUSES
            ):
                await _handle_pending_answer(job_tag, existing)
                return

            if existing_status in ACTIVE_STATUSES:
                _set_job(
                    job_tag,
                    phase="poll",
                    heal_job_id=collector_id,
                    step=step or "waiting",
                    message="A heal was already running on this collector — joining that job...",
                )
                return

            if existing_status in DONE_STATUSES:
                # Prefer a usable preview. success=True with a 404/empty preview is NOT a win.
                if preview_looks_usable(existing):
                    _set_job(job_tag, bd_success=True)
                    if preview:
                        _set_job(job_tag, preview_records=preview)
                    _set_job(
                        job_tag,
                        message="Collector already has a completed Bright Data heal — using that result.",
                    )
                    _complete_after_bright_data(job_tag)
                    return
                if existing.get("success") is True and not preview:
                    _set_job(job_tag, bd_success=True)
                    _set_job(
                        job_tag,
                        message="Collector already healed on Bright Data (no preview payload) — treating as saved.",
                    )
                    _complete_after_bright_data(job_tag)
                    return
                # done but junk preview — fall through and start a fresh heal
            if existing_status in FAIL_STATUSES:
                # Clear failed job by rejecting if stuck, then re-trigger below.
                pass
        except Exception as e:
            _set_job(job_tag, message=f"Progress check before trigger failed ({e}); trying trigger again...")

        heal_result = await trigger_heal(
            scraper_name=job["scraper_name"],
            collector_id=collector_id,
            issue_description=job["issue_description"] or issue_prompt(job["before"].model_dump()),
            test_url=job["test_url"],
            job_tag=job_tag,
        )
        if heal_result.get("status") == "error":
            if await _maybe_retry_heal(job_tag, heal_result.get("message") or "Trigger failed."):
                return
            _finish_unchanged(
                job_tag,
                f"Bright Data trigger failed after retries ({heal_result.get('message')}). "
                "Collector left unchanged.",
            )
            return

        progress = heal_result.get("progress") or {}
        if heal_result.get("status") == "pending_answer" and progress:
            await _handle_pending_answer(job_tag, progress)
            return

        _set_job(
            job_tag,
            phase="poll",
            heal_job_id=collector_id,
            heal_attempts=int(job.get("heal_attempts", 0)) + (1 if heal_result.get("status") not in ("already_running",) else 0),
            step="waiting",
            message=heal_result.get("message") or "Heal triggered — waiting for Bright Data AI...",
        )
        return

    # ---- poll phase ----
    try:
        data = await fetch_heal_progress(collector_id)
    except Exception as e:
        _set_job(job_tag, message=f"Waiting for Bright Data... ({e})")
        return

    status = normalize_status(data)
    step = data.get("step") or "waiting"
    preview = preview_records(data)
    updates = {"step": step, "message": progress_message(data)}
    if preview:
        updates["preview_records"] = preview
    if data.get("success") is True:
        updates["bd_success"] = True

    if status in ACTIVE_STATUSES:
        watch_started = job.get("active_watch_started_at") or time.time()
        updates["active_watch_started_at"] = watch_started
        # Hard cap on watching a slow Bright Data AI job — soft-complete, never hang the UI.
        if time.time() - float(watch_started) >= MAX_ACTIVE_WATCH_SECONDS:
            _set_job(job_tag, **updates)
            _finish_unchanged(
                job_tag,
                f"Bright Data AI still working after {MAX_ACTIVE_WATCH_SECONDS // 60} minutes "
                f"(step={step}). Soft-completed so Heal Lab never hangs — re-run to join later.",
            )
            return
    else:
        updates["active_watch_started_at"] = None

    # Detect BD AI stuck on the same step.
    prev_step = job.get("step")
    if step and step == prev_step and status in ACTIVE_STATUSES:
        stuck_since = job.get("stuck_since") or time.time()
        updates["stuck_since"] = stuck_since
        if time.time() - float(stuck_since) >= STUCK_STEP_SECONDS:
            _set_job(job_tag, **updates)
            _finish_unchanged(
                job_tag,
                f"Bright Data AI stayed on '{step}' for over {STUCK_STEP_SECONDS // 60} minutes. "
                "Soft-completed so the job does not hang — re-run later to join if it finishes.",
            )
            return
    else:
        updates["stuck_since"] = time.time()

    _set_job(job_tag, **updates)

    if status in FAIL_STATUSES:
        if await _maybe_retry_heal(job_tag, f"Heal failed on Bright Data: {status}."):
            return
        # Soft-complete so the lab does not show every collector as hard-failed.
        _finish_unchanged(
            job_tag,
            f"Bright Data heal ended with status={status} after {job.get('heal_attempts', 0)} attempt(s). "
            "Collector left unchanged.",
        )
        return

    if status in DONE_STATUSES:
        if preview_looks_usable(data) or (data.get("success") is True and not preview):
            _set_job(job_tag, bd_success=True)
            _complete_after_bright_data(job_tag)
            return
        if await _maybe_retry_heal(job_tag, "Bright Data marked done but preview was unusable."):
            return
        _finish_unchanged(
            job_tag,
            "Bright Data finished but the healed preview was empty/unusable after retries. "
            "Collector left unchanged.",
        )
        return

    if status in APPROVE_STATUSES or step == "user_approval":
        await _handle_pending_answer(job_tag, data)
        return

    if status and status not in ACTIVE_STATUSES and status not in DONE_STATUSES:
        _set_job(job_tag, message=f"Bright Data status: {status} (step={step})")


async def _heal_loop(job_tag: str) -> None:
    if job_tag in _heal_loops:
        return
    _heal_loops.add(job_tag)
    try:
        while heal_jobs.get(job_tag, {}).get("status") == "healing":
            elapsed = time.time() - heal_jobs[job_tag]["started_at"]
            if elapsed > MAX_HEAL_SECONDS:
                collector_id = heal_jobs[job_tag]["collector_id"]
                try:
                    data = await fetch_heal_progress(collector_id)
                    status = normalize_status(data)
                    preview = preview_records(data)
                    if preview:
                        _set_job(job_tag, preview_records=preview)

                    # Last-chance approve if proposal is waiting.
                    if status in APPROVE_STATUSES:
                        await _handle_pending_answer(job_tag, data)
                        for _ in range(20):
                            await asyncio.sleep(2)
                            data = await fetch_heal_progress(collector_id)
                            if normalize_status(data) in DONE_STATUSES:
                                _set_job(job_tag, bd_success=bool(data.get("success", True)))
                                _complete_after_bright_data(job_tag)
                                break
                            if normalize_status(data) in FAIL_STATUSES:
                                break
                            if normalize_status(data) in APPROVE_STATUSES:
                                await _handle_pending_answer(job_tag, data)
                        if heal_jobs[job_tag]["status"] != "healing":
                            break

                    # Soft-complete rather than hard-fail / endless wait.
                    if status in ACTIVE_STATUSES:
                        _finish_unchanged(
                            job_tag,
                            "Bright Data AI is still running on this collector. "
                            "Heal Lab soft-completed so the UI does not hang — re-run to join when ready.",
                        )
                        break

                    if status in DONE_STATUSES:
                        if preview_looks_usable(data) or (data.get("success") is True and not preview):
                            _set_job(job_tag, bd_success=True)
                            _complete_after_bright_data(job_tag)
                        else:
                            _finish_unchanged(
                                job_tag,
                                "Bright Data finished with an unusable preview. Collector left unchanged.",
                            )
                        break
                except Exception:
                    pass

                _finish_unchanged(
                    job_tag,
                    f"Heal wait exceeded {MAX_HEAL_SECONDS // 60} minutes. "
                    "Re-run heal to join any in-flight Bright Data job.",
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

    # force_heal still diagnoses for real before-metrics; it only means "heal even if healthy".
    if skip_diagnose and before is not None:
        before_metrics = before
        before_source = "cached"
        initial_phase = "trigger"
    elif force_heal and not skip_diagnose:
        # Fast path for Force heal: skip diagnose scrape, go straight to Bright Data.
        # Before may be placeholder unless a prior scrape for this job_tag exists.
        stored = get_current_health(job_tag)
        if not is_placeholder(stored):
            before_metrics = _metrics(stored)
            before_source = "cached"
        else:
            before_metrics = _metrics(PLACEHOLDER_HEALTH)
            before_source = "placeholder"
        initial_phase = "trigger"
    elif skip_diagnose:
        stored = get_current_health(job_tag)
        if is_placeholder(stored):
            before_metrics = _metrics(PLACEHOLDER_HEALTH)
            before_source = "placeholder"
            initial_phase = "diagnose"
        else:
            before_metrics = _metrics(stored)
            before_source = "cached"
            if not force_heal and not needs_heal(stored):
                heal_jobs[job_tag] = {
                    "status": "completed",
                    "phase": "done",
                    "step": "done",
                    "message": (
                        f"Collector already healthy (success {before_metrics.success_rate}%). "
                        "Skipped Bright Data heal — no fix was applied."
                    ),
                    "heal_job_id": collector_id,
                    "collector_id": collector_id,
                    "scraper_name": scraper_name,
                    "issue_description": issue_description.strip(),
                    "test_url": test_url,
                    "urls": url_list,
                    "before": before_metrics,
                    "before_source": before_source,
                    "after": before_metrics,
                    "after_source": "skipped_healthy",
                    "improved": False,
                    "approved": False,
                    "force_heal": force_heal,
                    "rescrape_after": rescrape_after,
                    "heal_attempts": 0,
                    "bd_success": False,
                    "started_at": time.time(),
                }
                return _to_response(job_tag)
            initial_phase = "trigger"
    else:
        before_metrics = _metrics(PLACEHOLDER_HEALTH)
        before_source = "placeholder"
        initial_phase = "diagnose"

    prompt = issue_description.strip() or issue_prompt(before_metrics.model_dump())

    heal_jobs[job_tag] = {
        "status": "healing",
        "phase": initial_phase,
        "step": "diagnosing" if initial_phase == "diagnose" else "queued",
        "message": (
            "Queued — will scrape for real before-metrics, then heal if needed."
            if initial_phase == "diagnose"
            else "Starting Bright Data heal on the same collector (diagnose scrape skipped for speed)..."
        ),
        "heal_job_id": collector_id,
        "collector_id": collector_id,
        "scraper_name": scraper_name,
        "issue_description": prompt,
        "test_url": test_url,
        "urls": url_list,
        "before": before_metrics,
        "before_source": before_source,
        "after": None,
        "after_source": None,
        "improved": False,
        "approved": False,
        "force_heal": force_heal,
        "rescrape_after": rescrape_after,
        "heal_attempts": 0,
        "bd_success": False,
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
            after_source="none",
            before_source="placeholder",
        )
    _set_job(
        job_tag,
        status="failed",
        step="failed",
        message="Heal cancelled by user.",
        after=None,
        after_source="none",
        improved=False,
    )
    return _to_response(job_tag)
