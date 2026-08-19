"""
Health metrics from normalized scrape output — real files, not stubs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings

PLACEHOLDER_HEALTH = {
    "empty_title_pct": 100.0,
    "empty_body_pct": 100.0,
    "success_rate": 0.0,
}


def _field(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_placeholder(metrics: dict) -> bool:
    return (
        float(metrics.get("success_rate", 0)) == 0.0
        and float(metrics.get("empty_title_pct", 0)) == 100.0
        and float(metrics.get("empty_body_pct", 0)) == 100.0
    )


def _title_body_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Map raw collector rows through the same normalizer the scrape path uses."""
    if not records:
        return []
    sample = records[0]
    already_normalized = sample.get("source") in ("brightdata", "firecrawl", "tavily")
    if already_normalized:
        return [
            {"title": _field(r, "title"), "content": _field(r, "content", "body", "text")}
            for r in records
        ]

    from app.scrapers.normalizer import from_brightdata
    docs = from_brightdata(records)
    return [{"title": d.title, "content": d.content} for d in docs]


def calculate_health_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    """empty_title_pct / empty_body_pct / success_rate from normalized or raw rows."""
    rows = _title_body_rows(records)
    if not rows:
        return dict(PLACEHOLDER_HEALTH)

    total = len(rows)
    empty_title = sum(1 for r in rows if not r["title"])
    empty_body = sum(1 for r in rows if not r["content"])
    successful = sum(1 for r in rows if r["title"] and r["content"])

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
