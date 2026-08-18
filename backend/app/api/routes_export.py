"""
GET /export/{job_tag} — returns the normalized structured data for a job.
This satisfies the hackathon requirement of providing "example structured
output" in your submission — hit this and save the response as a sample.
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{job_tag}")
def export(job_tag: str):
    path = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No data found for job_tag '{job_tag}'")
    return json.loads(path.read_text())