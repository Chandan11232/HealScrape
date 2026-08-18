"""GET /knowledge — closed corpus the console is allowed to answer from."""
from fastapi import APIRouter

from app.config import settings
from app.models.schemas import KnowledgeResponse
from app.rag.vectorstore import collection_stats
from app.scrapers.catalog import INDEXED_DOMAINS, INDEXED_SOURCES

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=KnowledgeResponse)
def knowledge():
    stats = collection_stats()
    configured = set(settings.BRIGHTDATA_SCRAPERS.keys())
    sources = [
        {**s, "collector_configured": s["scraper_name"] in configured}
        for s in INDEXED_SOURCES
    ]
    return KnowledgeResponse(
        chunk_count=stats.get("count", 0),
        indexed_domains=INDEXED_DOMAINS,
        sources=sources,
    )
