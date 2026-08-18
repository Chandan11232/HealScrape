"""
Health metrics from normalized scrape output — real files, not stubs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings


def _field(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def calculate_health_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    """empty_title_pct / empty_body_pct / success_rate from normalized or raw rows."""
    if not records:
        return {
            "empty_title_pct": 100.0,
            "empty_body_pct": 100.0,
            "success_rate": 0.0,
        }

    total = len(records)
    titles = [_field(r, "title", "headline", "job_title", "hackathon_title", "page_title") for r in records]
    bodies = [_field(r, "content", "body", "text", "article_content", "description") for r in records]
    empty_title = sum(1 for t in titles if not t)
    empty_body = sum(1 for b in bodies if not b)
    successful = sum(1 for t, b in zip(titles, bodies) if t and b)

    return {
        "empty_title_pct": round((empty_title / total) * 100, 2),
        "empty_body_pct": round((empty_body / total) * 100, 2),
        "success_rate": round((successful / total) * 100, 2),
    }


def load_normalized_records(job_tag: str) -> list[dict[str, Any]]:
    path = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_current_health(job_tag: str) -> dict[str, float]:
    return calculate_health_metrics(load_normalized_records(job_tag))


def needs_heal(metrics: dict[str, float]) -> bool:
    return (
        metrics.get("success_rate", 0) < settings.HEAL_MIN_SUCCESS_RATE
        or metrics.get("empty_title_pct", 100) >= settings.HEAL_MAX_EMPTY_FIELD_PCT
        or metrics.get("empty_body_pct", 100) >= settings.HEAL_MAX_EMPTY_FIELD_PCT
    )


def issue_prompt(metrics: dict[str, float]) -> str:
    return (
        "Extraction quality is low on this collector "
        f"(success {metrics.get('success_rate', 0)}%, "
        f"empty titles {metrics.get('empty_title_pct', 0)}%, "
        f"empty body {metrics.get('empty_body_pct', 0)}%). "
        "Re-capture title and main content from the current page markup. "
        "Keep the same output field names so downstream integrations do not change."
    )
