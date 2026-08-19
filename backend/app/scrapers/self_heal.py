"""
Self-healing scraper — triggers Bright Data's AI collector auto-fix.

Bright Data API flow (docs):
1. POST /dca/collectors/{collector_id}/refactor_template
2. GET  /dca/collectors/{collector_id}/refactor_template/progress
3. POST /dca/collectors/{collector_id}/resume_automation_job  (approve fix)
"""
import asyncio
import httpx
from typing import Dict, Any

from app.config import settings

BRIGHTDATA_API_KEY = settings.BRIGHTDATA_API_KEY
BRIGHTDATA_BASE_URL = "https://api.brightdata.com"

DONE_STATUSES = {"done", "completed"}
FAIL_STATUSES = {"failed", "error", "cancelled"}
APPROVE_STATUSES = {"pending_answer"}
ACTIVE_STATUSES = {"running", "in_progress", "processing", "pending", "started", "building"}

STEP_MESSAGES = {
    "planner": "AI is planning the fix...",
    "code_fixer": "AI is rewriting scraper selectors...",
    "control_preview_runner": "Testing fix against live page...",
    "user_approval": "Fix ready — auto-approving...",
    "step_advance": "Advancing heal pipeline...",
}


def progress_message(data: dict) -> str:
    step = data.get("step") or ""
    status = data.get("status") or ""
    if step in STEP_MESSAGES:
        return STEP_MESSAGES[step]
    if status in ACTIVE_STATUSES:
        return f"Bright Data AI working ({step or status})..."
    if status in APPROVE_STATUSES:
        return "AI proposal ready — auto-approving..."
    return f"Heal status: {status or 'unknown'}"


_async_client: httpx.AsyncClient | None = None


def _headers() -> dict:
    return {"Authorization": f"Bearer {BRIGHTDATA_API_KEY}"}


def _progress_url(collector_id: str) -> str:
    return f"{BRIGHTDATA_BASE_URL}/dca/collectors/{collector_id}/refactor_template/progress"


def _client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(timeout=30.0)
    return _async_client


async def fetch_heal_progress(collector_id: str) -> Dict[str, Any]:
    """Single progress check — no blocking loop."""
    if not BRIGHTDATA_API_KEY or collector_id.startswith("mock"):
        return {"status": "pending_answer", "step": "user_approval"}

    resp = await _client().get(_progress_url(collector_id), headers=_headers())
    resp.raise_for_status()
    return resp.json()


async def trigger_heal(
    scraper_name: str,
    collector_id: str,
    issue_description: str,
    test_url: str,
    job_tag: str,
) -> Dict[str, Any]:
    if not BRIGHTDATA_API_KEY:
        return {
            "heal_job_id": f"mock-{job_tag}",
            "status": "mock",
            "message": "BRIGHTDATA_API_KEY not set — running mock heal",
        }

    prompt = issue_description
    if test_url:
        prompt = f"{issue_description}\n\nTest against: {test_url}"

    url = f"{BRIGHTDATA_BASE_URL}/dca/collectors/{collector_id}/refactor_template"
    try:
        resp = await _client().post(
            url,
            json={"prompt": prompt[:1000], "custom_input": []},
            headers=_headers(),
        )
        resp.raise_for_status()
        return {
            "heal_job_id": collector_id,
            "status": "pending_answer",
            "message": f"Self-heal triggered for collector {collector_id}",
        }
    except Exception as e:
        return {
            "heal_job_id": None,
            "status": "error",
            "message": f"Failed to trigger heal: {e}",
        }


async def poll_heal_status(
    collector_id: str,
    max_wait_seconds: int = 300,
    poll_interval: int = 3,
    on_progress=None,
) -> Dict[str, Any]:
    if not BRIGHTDATA_API_KEY or collector_id.startswith("mock"):
        await asyncio.sleep(0.5)
        return {
            "status": "ready_to_approve",
            "heal_job_id": collector_id,
            "message": "Mock heal ready (no real API call)",
        }

    elapsed = 0
    while elapsed < max_wait_seconds:
        try:
            data = await fetch_heal_progress(collector_id)
            status = data.get("status", "")
            if on_progress:
                on_progress(data)

            if status in APPROVE_STATUSES:
                return {
                    "status": "ready_to_approve",
                    "heal_job_id": collector_id,
                    "message": "AI proposal ready, auto-approving...",
                }
            if status in DONE_STATUSES:
                return {
                    "status": "completed",
                    "heal_job_id": collector_id,
                    "message": "Heal completed",
                }
            if status in FAIL_STATUSES:
                return {
                    "status": "error",
                    "heal_job_id": collector_id,
                    "message": f"Heal job failed with status: {status}",
                }
        except Exception as e:
            print(f"Poll error: {e}")

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    return {
        "status": "timeout",
        "heal_job_id": collector_id,
        "message": f"Timed out waiting for AI proposal after {max_wait_seconds}s",
    }


async def auto_approve_heal(collector_id: str) -> Dict[str, Any]:
    if not BRIGHTDATA_API_KEY or collector_id.startswith("mock"):
        return {
            "status": "approved",
            "heal_job_id": collector_id,
            "message": "Mock heal approved",
        }

    url = f"{BRIGHTDATA_BASE_URL}/dca/collectors/{collector_id}/resume_automation_job"
    try:
        resp = await _client().post(
            url,
            json={"message": True, "auto_save": True},
            headers=_headers(),
        )
        resp.raise_for_status()
        return {
            "status": "approved",
            "heal_job_id": collector_id,
            "message": "Heal approved, applying fix...",
        }
    except Exception as e:
        return {
            "status": "error",
            "heal_job_id": collector_id,
            "message": f"Failed to approve heal: {e}",
        }


async def wait_for_completion(
    collector_id: str,
    max_wait_seconds: int = 300,
    poll_interval: int = 3,
    on_progress=None,
) -> Dict[str, Any]:
    if not BRIGHTDATA_API_KEY or collector_id.startswith("mock"):
        await asyncio.sleep(0.5)
        return {
            "status": "completed",
            "heal_job_id": collector_id,
            "message": "Mock heal complete",
        }

    elapsed = 0
    while elapsed < max_wait_seconds:
        try:
            data = await fetch_heal_progress(collector_id)
            status = data.get("status", "")
            if on_progress:
                on_progress(data)

            if status in DONE_STATUSES:
                return {
                    "status": "completed",
                    "heal_job_id": collector_id,
                    "message": "Heal job fully completed",
                }
            if status in FAIL_STATUSES:
                return {
                    "status": "error",
                    "heal_job_id": collector_id,
                    "message": f"Heal job failed with status: {status}",
                }
        except Exception as e:
            print(f"Poll error: {e}")

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    return {
        "status": "timeout",
        "heal_job_id": collector_id,
        "message": f"Timed out waiting for heal to finish after {max_wait_seconds}s",
    }
