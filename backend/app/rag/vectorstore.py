"""
Local, persisted ChromaDB collection. No server, no cloud, no cost —
data lives on disk at settings.CHROMA_PERSIST_DIR.
"""
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from app.rag.chunker import Chunk
from app.rag.embedder import embed_texts

_client = None
_collection = None

COLLECTION_NAME = "hackathon_docs_cosine"
COLLECTION_METADATA = {"hnsw:space": "cosine"}


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata=COLLECTION_METADATA,
        )
    return _collection


def add_chunks(chunks: list[Chunk]) -> int:
    """Embeds and upserts chunks. Returns count added."""
    if not chunks:
        return 0

    collection = get_collection()
    batch = settings.CHROMA_UPSERT_BATCH

    for start in range(0, len(chunks), batch):
        end = start + batch
        slice_chunks = chunks[start:end]
        embeddings = embed_texts([c.text for c in slice_chunks])
        collection.upsert(
            ids=[c.chunk_id for c in slice_chunks],
            embeddings=embeddings,
            documents=[c.text for c in slice_chunks],
            metadatas=[{
                "doc_url": c.doc_url,
                "doc_title": c.doc_title,
                "source": c.source,
                "domain": c.domain,
                "chunk_index": c.chunk_index,
            } for c in slice_chunks],
        )
    return len(chunks)


def _normalize_filters(source_filter: str | list[str] | None) -> list[str]:
    if not source_filter:
        return []
    if isinstance(source_filter, str):
        if source_filter in ("brightdata", "firecrawl", "tavily"):
            return [source_filter]
        return [source_filter.removeprefix("www.")]
    return [d.removeprefix("www.") for d in source_filter]


def _where_filter(source_filter: str | list[str] | None) -> dict | None:
    filters = _normalize_filters(source_filter)
    if not filters:
        return None
    if filters[0] in ("brightdata", "firecrawl", "tavily") and len(filters) == 1:
        return {"source": filters[0]}
    if len(filters) == 1:
        return {"domain": filters[0]}
    return {"domain": {"$in": filters}}


def _hit_matches_domains(hit: dict, domains: list[str]) -> bool:
    meta = hit.get("metadata") or {}
    url = (meta.get("doc_url") or "").lower()
    host = (meta.get("domain") or "").lower()
    return any(d in url or host == d for d in domains)


def query(
    query_text: str,
    top_k: int = 5,
    source_filter: str | list[str] | None = None,
) -> list[dict]:
    """Returns top_k most relevant chunks with metadata + distance score."""
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []

    query_embedding = embed_texts([query_text])[0]
    domains = [
        d for d in _normalize_filters(source_filter)
        if d not in ("brightdata", "firecrawl", "tavily")
    ]
    where = _where_filter(source_filter)
    if where:
        fetch_n = min(total, max(top_k, 20))
    elif domains:
        fetch_n = min(total, max(top_k * 40, 800))
    else:
        fetch_n = min(top_k, total)

    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": fetch_n,
    }
    if where:
        kwargs["where"] = where

    try:
        results = collection.query(**kwargs)
    except Exception:
        if not where:
            raise
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_n,
        )

    ids = results.get("ids") or [[]]
    if where and (not ids or not ids[0]):
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(total, max(top_k * 40, 800)),
        )
        ids = results.get("ids") or [[]]

    if not ids or not ids[0]:
        return []

    hits = []
    for i in range(len(ids[0])):
        hits.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    if domains:
        hits = [h for h in hits if _hit_matches_domains(h, domains)]
    return hits[:top_k]


def collection_stats() -> dict:
    collection = get_collection()
    return {"count": collection.count(), "name": COLLECTION_NAME}
