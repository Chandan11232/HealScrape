"""
POST /ingest — loads a previously-saved normalized_{job_tag}.json and
pushes it through chunking + embedding into the local Chroma store.
Kept separate from /scrape so you control exactly when embedding
compute is spent.
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.schemas import IngestRequest, IngestResponse
from app.rag.pipeline import ingest_documents

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
def ingest(req: IngestRequest):
    path = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{req.job_tag}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No normalized data found for job_tag '{req.job_tag}'. Run /scrape first.")

    docs = json.loads(path.read_text())
    try:
        result = ingest_documents(docs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {type(e).__name__}: {e}")
    return IngestResponse(**result)
