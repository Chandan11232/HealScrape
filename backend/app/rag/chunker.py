"""
Splits normalized documents into chunks small enough to embed well
and retrieve precisely. Pure Python, no API calls — free.
"""
from dataclasses import dataclass
import re


@dataclass
class Chunk:
    chunk_id: str
    doc_url: str
    doc_title: str
    source: str
    text: str
    chunk_index: int


def _split_sentences(text: str) -> list[str]:
    # lightweight sentence split — avoids pulling in a heavy NLP dep
    text = re.sub(r"\s+", " ", text).strip()
    return re.split(r"(?<=[.!?])\s+", text)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Character-based chunking with sentence-aware boundaries where possible.
    chunk_size / overlap are in characters (roughly ~150-200 tokens per chunk).
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    sentences = _split_sentences(text)
    chunks, current = [], ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            # start new chunk with overlap from the end of the previous one
            overlap_text = current[-overlap:] if current else ""
            current = f"{overlap_text} {sentence}".strip()

    if current:
        chunks.append(current)

    return chunks


def chunk_documents(docs: list[dict], chunk_size: int = 800, overlap: int = 150) -> list[Chunk]:
    """docs: list of normalized doc dicts (source, url, title, content, metadata)."""
    all_chunks = []
    for doc_index, doc in enumerate(docs):
        text_chunks = chunk_text(doc.get("content", ""), chunk_size, overlap)
        # Use doc_index in the ID so multiple docs sharing the same URL
        # (e.g. per-section scrapes of one page) never collide in the vector store.
        doc_key = f"{doc.get('url', 'unknown')}#{doc_index}"
        for i, text in enumerate(text_chunks):
            all_chunks.append(Chunk(
                chunk_id=f"{doc_key}::{i}",
                doc_url=doc.get("url", ""),
                doc_title=doc.get("title", ""),
                source=doc.get("source", ""),
                text=text,
                chunk_index=i,
            ))
    return all_chunks
