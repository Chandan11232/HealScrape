"""
Load pre-scraped normalized JSON onto Railway (or any empty deploy).

Set SEED_PROCESSED_URL to a .tar.gz containing a top-level ``processed/`` folder
with ``normalized_*.json`` files. On startup, if Chroma is empty, the archive is
downloaded, extracted, and demo job tags are ingested in the background.
"""
from __future__ import annotations

import json
import logging
import os
import tarfile
import tempfile
from pathlib import Path

import httpx

from app.config import settings
from app.rag.pipeline import ingest_documents
from app.rag.vectorstore import collection_stats

logger = logging.getLogger(__name__)

# Job tags that power Console in-scope example questions (13 small collectors).
DEMO_JOB_TAGS = [
    "demo_tiangolo",
    "demo_react",
    "demo_python",
    "demo_openai",
    "demo_mdn",
    "demo_docker",
    "demo_stripe",
    "demo_wiki_js",
]


def list_job_tags(*, demo_only: bool = False) -> list[str]:
    processed = Path(settings.PROCESSED_DATA_DIR)
    if not processed.is_dir():
        return []
    tags = sorted(
        p.name.removeprefix("normalized_").removesuffix(".json")
        for p in processed.glob("normalized_*.json")
    )
    if demo_only:
        return [t for t in DEMO_JOB_TAGS if (processed / f"normalized_{t}.json").exists()]
    return tags


def ingest_job_tag(job_tag: str) -> dict:
    path = Path(settings.PROCESSED_DATA_DIR) / f"normalized_{job_tag}.json"
    if not path.exists():
        raise FileNotFoundError(f"No normalized data for job_tag '{job_tag}'")
    docs = json.loads(path.read_text())
    result = ingest_documents(docs)
    return {"job_tag": job_tag, **result}


def ingest_all(*, demo_only: bool = False) -> dict:
    tags = list_job_tags(demo_only=demo_only)
    if not tags:
        return {
            "job_tags": [],
            "documents_in": 0,
            "chunks_added": 0,
            "chunk_count": collection_stats().get("count", 0),
            "results": [],
            "message": "No normalized_*.json files found in processed/",
        }

    total_docs = 0
    total_chunks = 0
    results: list[dict] = []
    errors: list[dict] = []

    for job_tag in tags:
        try:
            row = ingest_job_tag(job_tag)
            total_docs += row["documents_in"]
            total_chunks += row["chunks_added"]
            results.append(row)
        except Exception as e:
            errors.append({"job_tag": job_tag, "error": str(e)})

    chunk_count = collection_stats().get("count", 0)
    return {
        "job_tags": tags,
        "documents_in": total_docs,
        "chunks_added": total_chunks,
        "chunk_count": chunk_count,
        "results": results,
        "errors": errors,
        "message": f"Ingested {len(results)} job(s); {chunk_count} chunks in Chroma.",
    }


def _download_and_extract(url: str) -> None:
    processed_dir = Path(settings.PROCESSED_DATA_DIR)
    processed_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        logger.info("Downloading seed archive from %s", url)
        with httpx.Client(timeout=300, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            Path(tmp_path).write_bytes(resp.content)

        with tarfile.open(tmp_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            tar.extractall(path=processed_dir.parent, members=members, filter="data")
        logger.info("Extracted seed data into %s", processed_dir.parent)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def maybe_reingest_local(*, demo_only: bool = True) -> None:
    """If Chroma is empty but normalized JSON exists on disk, ingest it (needs a Railway volume)."""
    if collection_stats().get("count", 0) > 0:
        return
    tags = list_job_tags(demo_only=demo_only)
    if not tags:
        return
    logger.info("Chroma empty — re-ingesting %d local job tag(s)", len(tags))
    summary = ingest_all(demo_only=demo_only)
    logger.info("Local re-ingest: %s", summary.get("message"))


def maybe_seed_from_env() -> None:
    """Download + ingest demo corpus when SEED_PROCESSED_URL is set and Chroma is empty."""
    url = os.getenv("SEED_PROCESSED_URL", "").strip()
    if not url:
        return

    if collection_stats().get("count", 0) > 0:
        logger.info("Chroma already has chunks — skipping SEED_PROCESSED_URL")
        return

    demo_only = os.getenv("SEED_DEMO_ONLY", "true").lower() in ("1", "true", "yes")
    _download_and_extract(url)
    summary = ingest_all(demo_only=demo_only)
    logger.info("Seed ingest complete: %s", summary.get("message"))
