"""
Schemas for the /heal endpoint (self-healing scraper collector).
"""
from pydantic import BaseModel, Field
from typing import Optional


class HealRequest(BaseModel):
    """POST /heal request body."""
    scraper_name: str = Field(..., description="Name of the scraper (e.g., 'wikipedia_ai')")
    issue_description: str = Field("", description="What's broken; generated from metrics if empty")
    test_url: str = Field(..., description="URL to test the scraper against")
    job_tag: str = Field(..., description="Unique job tag for tracking")
    skip_diagnose: bool = Field(
        False,
        description="True when /scrape already ran; skip the first scrape and start Bright Data heal",
    )
    force_heal: bool = Field(
        True,
        description="If false, skip Bright Data heal when diagnose scrape already looks healthy",
    )
    rescrape_after: bool = Field(
        False,
        description=(
            "If true, run a live re-scrape after heal (slower, can time out). "
            "Default false uses Bright Data heal preview when available — reliable after-metrics."
        ),
    )


class HealthMetrics(BaseModel):
    """Health metrics before/after healing."""
    empty_title_pct: float = Field(..., description="Percentage of empty title fields")
    empty_body_pct: float = Field(..., description="Percentage of empty body fields")
    success_rate: float = Field(..., description="Overall extraction success rate")


class HealResponse(BaseModel):
    """POST /heal and GET /heal/{job_tag} response body."""
    status: str = Field(..., description="'healing', 'completed', or 'failed'")
    job_tag: str = Field(..., description="Job tracking ID")
    before: HealthMetrics = Field(..., description="Health metrics before healing")
    after: Optional[HealthMetrics] = Field(None, description="After metrics; null until measured")
    improved: bool = Field(..., description="True only when after is measured and strictly better")
    message: str = Field(..., description="Status message")
    heal_job_id: Optional[str] = Field(None, description="Bright Data collector ID")
    step: Optional[str] = Field(None, description="Current pipeline step while healing")
    scraper_name: Optional[str] = Field(None, description="Scraper that was healed")
    before_source: Optional[str] = Field(
        None,
        description="Where before came from: diagnose_scrape | cached | placeholder",
    )
    after_source: Optional[str] = Field(
        None,
        description="Where after came from: rescrape | preview | none | skipped_healthy | unchanged",
    )
