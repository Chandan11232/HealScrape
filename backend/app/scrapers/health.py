"""
Health metrics from normalized scrape output — real files, not stubs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings

# Used only when there are zero records to score. Never treat as a real measurement.
PLACEHOLDER_HEALTH = {
    "empty_title_pct": 100.0,
    "empty_body_pct": 100.0,
    "success_rate": 0.0,
    "_measured": False,
}


def _field(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_placeholder(metrics: dict | None) -> bool:
    """True for unknown/unmeasured stand-in metrics (not a real scrape result)."""
    if not metrics:
        return True
    if "_measured" in metrics:
        return not bool(metrics["_measured"])
    return (
        float(metrics.get("success_rate", 0)) == 0.0
        and float(metrics.get("empty_title_pct", 0)) == 100.0
        and float(metrics.get("empty_body_pct", 0)) == 100.0
    )


def metrics_equal(a: dict | None, b: dict | None, tol: float = 0.01) -> bool:
    if not a or not b:
        return False
    keys = ("empty_title_pct", "empty_body_pct", "success_rate")
    return all(abs(float(a.get(k, 0)) - float(b.get(k, 0))) <= tol for k in keys)


def compute_improved(
    before: dict | None,
    after: dict | None,
    *,
    before_source: str | None = None,
    after_source: str | None = None,
) -> bool:
    """True only when both sides are measured and after is strictly better than before."""
    if not before or not after:
        return False
    if before_source == "placeholder" or after_source in (None, "none"):
        return False

    # diagnose_scrape / rescrape / preview count as real even when extraction is empty
    # (same numeric shape as PLACEHOLDER_HEALTH).
    measured_before = before_source in ("diagnose_scrape", "cached") or (
        before_source is None and not is_placeholder(before)
    )
    measured_after = after_source in ("rescrape", "preview", "skipped_healthy", "unchanged")
    if not measured_before or not measured_after:
        return False
    if metrics_equal(before, after):
        return False
    return (
        float(after.get("success_rate", 0)) > float(before.get("success_rate", 0))
        or (
            float(after.get("empty_title_pct", 100)) < float(before.get("empty_title_pct", 100))
            and float(after.get("empty_body_pct", 100)) < float(before.get("empty_body_pct", 100))
        )
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
        out = dict(PLACEHOLDER_HEALTH)
        out["_measured"] = False
        return out

    total = len(rows)
    empty_title = sum(1 for r in rows if not r["title"])
    empty_body = sum(1 for r in rows if not r["content"])
    successful = sum(1 for r in rows if r["title"] and r["content"])

    return {
        "empty_title_pct": round((empty_title / total) * 100, 2),
        "empty_body_pct": round((empty_body / total) * 100, 2),
        "success_rate": round((successful / total) * 100, 2),
        "_measured": True,
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
    if is_placeholder(metrics):
        return True
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
        "Re-capture the primary fields from the current page markup. "
        "Keep the exact same output field names and schema so downstream integrations do not change. "
        "Prefer filled strings over null/empty values."
    )
