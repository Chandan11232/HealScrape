"""
Self-healing scraper — triggers Bright Data's AI collector auto-fix.

Bright Data API flow (docs):
1. POST /dca/collectors/{collector_id}/refactor_template
2. GET  /dca/collectors/{collector_id}/refactor_template/progress
3. POST /dca/collectors/{collector_id}/resume_automation_job  (approve/reject fix)

Critical: progress often pauses at pending_answer. A new trigger then returns 409.
Always inspect progress first — approve/join/reject before posting a new trigger.
"""
from __future__ import annotations

import asyncio
import httpx
from typing import Any, Dict

from app.config import settings

BRIGHTDATA_API_KEY = settings.BRIGHTDATA_API_KEY
BRIGHTDATA_BASE_URL = "https://api.brightdata.com"

DONE_STATUSES = {"done", "completed"}
FAIL_STATUSES = {"failed", "error", "cancelled"}
APPROVE_STATUSES = {"pending_answer"}
ACTIVE_STATUSES = {
    "running",
    "in_progress",
    "processing",
    "pending",
    "started",
    "building",
    "queued",
    "planner",
    "agent_picker",
}

STEP_MESSAGES = {
    "planner": "AI is planning the fix...",
    "code_fixer": "AI is rewriting scraper selectors...",
    "control_preview_runner": "Testing fix against live page...",
    "step_preview_runner": "Validating extraction preview...",
    "request_fulfillment_validator": "Checking extraction quality...",
    "css_selector_extractor": "Updating CSS selectors...",
    "agent_picker": "AI choosing the best fix strategy...",
    "user_approval": "Fix ready — auto-approving...",
    "step_advance": "Advancing heal pipeline...",
    "save_new_template": "Saving healed collector template...",
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
    if status in DONE_STATUSES:
        return "Heal completed on Bright Data"
    if status in FAIL_STATUSES:
        return f"Bright Data heal ended: {status}"
    return f"Heal status: {status or 'idle'}"


_async_client: httpx.AsyncClient | None = None
# Serialize trigger calls so we do not stampede the AI Flow API.
_trigger_lock = asyncio.Lock()


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json",
    }


def _progress_url(collector_id: str) -> str:
    return f"{BRIGHTDATA_BASE_URL}/dca/collectors/{collector_id}/refactor_template/progress"


def _client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(timeout=45.0)
    return _async_client


def normalize_status(data: dict | None) -> str:
    if not data:
        return ""
    return str(data.get("status") or "").strip().lower()


def preview_records(data: dict) -> list[dict]:
    preview = data.get("preview_result") or data.get("preview") or data.get("sample_result")
    if isinstance(preview, list):
        return [p for p in preview if isinstance(p, dict)]
    if isinstance(preview, dict):
        return [preview]
    return []


def preview_looks_usable(data: dict) -> bool:
    """True when Bright Data preview has real extraction (not empty/404 stubs)."""
    records = preview_records(data)
    if not records:
        return False

    junk = {"", "none", "null", "[]", "{}", "n/a", "na", "undefined", "404", "error"}
    skip = {
        "product_page_url",
        "input",
        "url",
        "error",
        "warning",
        "author_url",
        "author_image",
        "featured_image",
        "image_credit",
        "source_link",
        "tags",
    }

    filled = 0
    has_titleish = False
    has_bodyish = False
    title_keys = {
        "title",
        "page_title",
        "headline",
        "article_title",
        "job_title",
        "hackathon_title",
        "location",
        "repository_name",
        "name",
        "city",
    }
    body_keys = {
        "content",
        "text",
        "main_content",
        "article_content",
        "description",
        "summary",
        "current_temperature",
        "temperature",
        "repositories",
        "readme_content",
        "forecast",
        "tagline",
    }

    for sample in records:
        for key, value in sample.items():
            if key in skip:
                continue
            text = ""
            if isinstance(value, str):
                text = value.strip()
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                text = str(value)
            elif isinstance(value, list) and value:
                text = "list"
            elif isinstance(value, dict) and value:
                text = "dict"
            else:
                continue
            if not text or text.lower() in junk:
                continue
            filled += 1
            if key in title_keys:
                has_titleish = True
            if key in body_keys:
                has_bodyish = True

    if data.get("success") is True and filled >= 1 and (has_titleish or has_bodyish or filled >= 2):
        return True
    # Even without success flag, require title+body style signal or 3+ filled fields.
    return filled >= 2 and (has_titleish or has_bodyish or filled >= 3)


async def fetch_heal_progress(collector_id: str) -> Dict[str, Any]:
    """Single progress check — no blocking loop."""
    if not BRIGHTDATA_API_KEY or collector_id.startswith("mock"):
        return {"status": "pending_answer", "step": "user_approval", "success": True}

    resp = await _client().get(_progress_url(collector_id), headers=_headers())
    if resp.status_code == 404:
        return {"status": "", "step": "", "success": None}
    resp.raise_for_status()
    body = resp.json()
    return body if isinstance(body, dict) else {"status": "", "raw": body}


async def reject_heal(collector_id: str) -> Dict[str, Any]:
    """Reject a bad pending_answer proposal so a fresh heal can start."""
    if not BRIGHTDATA_API_KEY or collector_id.startswith("mock"):
        return {"status": "rejected", "heal_job_id": collector_id, "message": "Mock heal rejected"}

    url = f"{BRIGHTDATA_BASE_URL}/dca/collectors/{collector_id}/resume_automation_job"
    try:
        resp = await _client().post(
            url,
            json={"message": False},
            headers=_headers(),
        )
        resp.raise_for_status()
        return {
            "status": "rejected",
            "heal_job_id": collector_id,
            "message": "Rejected bad AI proposal — will re-trigger heal",
        }
    except Exception as e:
        return {
            "status": "error",
            "heal_job_id": collector_id,
            "message": f"Failed to reject heal: {e}",
        }


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

    prompt = (issue_description or "").strip()
    if test_url and test_url not in prompt:
        prompt = f"{prompt}\n\nTest against: {test_url}".strip()
    prompt = prompt[:1000]

    custom_input: list[dict] = []
    if test_url:
        custom_input = [{"url": test_url}]

    url = f"{BRIGHTDATA_BASE_URL}/dca/collectors/{collector_id}/refactor_template"
    payload = {"prompt": prompt, "custom_input": custom_input}

    async with _trigger_lock:
        # Prefer joining an in-flight / pending job over creating a conflicting one.
        try:
            existing = await fetch_heal_progress(collector_id)
            existing_status = normalize_status(existing)
            step = existing.get("step") or ""
            if existing_status in APPROVE_STATUSES or (
                step == "user_approval" and existing_status not in DONE_STATUSES | FAIL_STATUSES
            ):
                return {
                    "heal_job_id": collector_id,
                    "status": "pending_answer",
                    "progress": existing,
                    "message": (
                        f"Collector {collector_id} already has an AI proposal waiting — "
                        "joining to auto-approve."
                    ),
                }
            if existing_status in ACTIVE_STATUSES:
                return {
                    "heal_job_id": collector_id,
                    "status": "already_running",
                    "progress": existing,
                    "message": (
                        f"Heal already running on collector {collector_id}. "
                        "Joining the in-flight Bright Data job."
                    ),
                }
        except Exception:
            pass

        try:
            resp = await _client().post(url, json=payload, headers=_headers())
            if resp.status_code == 409:
                progress = {}
                try:
                    progress = await fetch_heal_progress(collector_id)
                except Exception:
                    pass
                return {
                    "heal_job_id": collector_id,
                    "status": "already_running",
                    "progress": progress,
                    "message": (
                        f"Heal already running on collector {collector_id} (409). "
                        "Joining the in-flight Bright Data job."
                    ),
                }
            resp.raise_for_status()
            return {
                "heal_job_id": collector_id,
                "status": "pending_answer",
                "message": f"Self-heal triggered for collector {collector_id}",
            }
        except httpx.HTTPStatusError as e:
            body = ""
            try:
                body = e.response.text[:300]
            except Exception:
                pass
            return {
                "heal_job_id": None,
                "status": "error",
                "message": f"Failed to trigger heal: {e} {body}",
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
            status = normalize_status(data)
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
            status = normalize_status(data)
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
