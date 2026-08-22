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
        True,
        description=(
            "If true (default), run a live re-scrape after heal for authentic after-metrics. "
            "If false, uses Bright Data heal preview when available (faster, less accurate)."
        ),
    )
    auto_approve: bool = Field(
        False,
        description=(
            "If true, skip manual diff review and auto-approve like the CLI --auto-approve flag. "
            "Default false matches Bright Data docs: review diff, accept/decline, then save to production."
        ),
    )


class HealthMetrics(BaseModel):
    """Health metrics before/after healing."""
    empty_title_pct: float = Field(..., description="Percentage of empty title fields")
    empty_body_pct: float = Field(..., description="Percentage of empty body fields")
    success_rate: float = Field(..., description="Overall extraction success rate")


class SchemaChanges(BaseModel):
    """Output schema diff between production and heal preview."""
    has_changes: bool = False
    added_fields: list[str] = Field(default_factory=list)
    removed_fields: list[str] = Field(default_factory=list)
    production_fields: list[str] = Field(default_factory=list)
    preview_fields: list[str] = Field(default_factory=list)


class HealProposal(BaseModel):
    """Bright Data self-heal proposal shown at user_approval."""
    diff: dict | None = None
    preview: list[dict] = Field(default_factory=list)
    schema_changes: SchemaChanges | None = None
    step: str | None = None
    status: str | None = None


class HealReviewRequest(BaseModel):
    """POST /heal/{job_tag}/review — accept or decline the AI diff."""
    approve: bool
    save_to_production: bool = Field(
        False,
        description="When approving: true = accept and publish (auto_save), false = accept to draft only",
    )


class HealSaveRequest(BaseModel):
    """POST /heal/{job_tag}/save-production — publish an accepted draft."""
    update_schema: bool = Field(
        True,
        description="Acknowledge output schema changes before publishing (Bright Data docs step)",
    )


class CollectorVersionInfo(BaseModel):
    job_id: str
    status: str
    finished: str | None = None
    data_lines: int | None = None
    failed_pages: int | None = None


class CollectorVersionsResponse(BaseModel):
    scraper_name: str
    collector_id: str
    collector_url: str
    versions_url: str
    active: bool | None = None
    last_run: str | None = None
    output_schema: dict | None = None
    recent_jobs: list[CollectorVersionInfo] = Field(default_factory=list)
    rollback_note: str = (
        "Bright Data version rollback is managed in the scraper dashboard Versions menu. "
        "Use versions_url to open it."
    )


class HealResponse(BaseModel):
    """POST /heal and GET /heal/{job_tag} response body."""
    status: str = Field(
        ...,
        description="'healing', 'awaiting_review', 'draft_ready', 'completed', or 'failed'",
    )
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
    proposal: HealProposal | None = None
    saved_to_production: bool = False
    schema_update_required: bool = False
    collector_url: str | None = None


class BatchHealRequest(BaseModel):
    """POST /heal/batch — queue authentic heal jobs for many collectors (sequential)."""
    scraper_names: list[str] | None = Field(
        None,
        description="Subset to heal; default = all keys in BRIGHTDATA_SCRAPERS",
    )
    force_heal: bool = Field(
        True,
        description="Run Bright Data heal even when diagnose scrape looks healthy",
    )
    rescrape_after: bool = Field(
        True,
        description="Live re-scrape after heal for authentic after-metrics",
    )
    auto_approve: bool = Field(
        False,
        description="Skip manual review and auto-approve proposals (CLI --auto-approve style)",
    )
