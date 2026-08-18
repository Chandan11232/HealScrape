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

COLLECTION_NAME = "hackathon_docs"


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
        _collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def add_chunks(chunks: list[Chunk]) -> int:
    """Embeds and upserts chunks. Returns count added."""
    if not chunks:
        return 0

    collection = get_collection()
    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{
            "doc_url": c.doc_url,
            "doc_title": c.doc_title,
            "source": c.source,
            "chunk_index": c.chunk_index,
        } for c in chunks],
    )
    return len(chunks)


def query(query_text: str, top_k: int = 5, source_filter: str | None = None) -> list[dict]:
    """Returns top_k most relevant chunks with metadata + distance score."""
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []

    query_embedding = embed_texts([query_text])[0]
    where = {"source": source_filter} if source_filter else None
    n_results = min(top_k, total)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
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
    return hits


def collection_stats() -> dict:
    collection = get_collection()
    return {"count": collection.count(), "name": COLLECTION_NAME}
