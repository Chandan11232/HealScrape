from pydantic import BaseModel


class HealthSnapshot(BaseModel):
    empty_title_pct: float
    empty_body_pct: float
    success_rate: float


class ScrapeRequest(BaseModel):
    job_tag: str
    urls: list[str]
    source: str  # "brightdata" | "firecrawl" | "tavily"
    scraper_name: str | None = None  # required when source == "brightdata" — key in BRIGHTDATA_SCRAPERS
    tavily_query: str | None = None  # only used when source == "tavily"
    auto_heal: bool = True  # Bright Data only: heal + re-scrape if extraction is unhealthy


class ScrapeResponse(BaseModel):
    job_tag: str
    source: str
    records_found: int
    normalized_path: str
    health: HealthSnapshot | None = None
    needs_heal: bool = False
    heal_started: bool = False
    heal_job_tag: str | None = None
    message: str = ""


class IngestRequest(BaseModel):
    job_tag: str  # matches normalized_{job_tag}.json in data/processed/


class IngestResponse(BaseModel):
    documents_in: int
    chunks_added: int


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    source_filter: str | None = None


class SourceRef(BaseModel):
    rank: int
    url: str | None
    title: str | None
    source: str | None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    in_scope: bool = True
    reason: str | None = None  # None | "empty_index" | "below_relevance"
    indexed_domains: list[str] = []
    chunk_count: int = 0


class KnowledgeResponse(BaseModel):
    chunk_count: int
    indexed_domains: list[str]
    sources: list[dict]