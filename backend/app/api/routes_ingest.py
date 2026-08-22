"""
POST /ingest — loads a previously-saved normalized_{job_tag}.json and
pushes it through chunking + embedding into the local Chroma store.
Kept separate from /scrape so you control exactly when embedding
compute is spent.
"""
import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.schemas import IngestRequest, IngestResponse
from app.rag.pipeline import ingest_documents

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    path = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{req.job_tag}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No normalized data found for job_tag '{req.job_tag}'. Run /scrape first.")

    docs = json.loads(path.read_text())
    if not isinstance(docs, list):
        raise HTTPException(status_code=500, detail="Normalized file is not a JSON array.")
    if settings.INGEST_MAX_DOCS > 0:
        docs = docs[: settings.INGEST_MAX_DOCS]
    try:
        result = await asyncio.to_thread(ingest_documents, docs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {type(e).__name__}: {e}")
    return IngestResponse(**result)
