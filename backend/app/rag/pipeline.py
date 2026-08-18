"""
Orchestrates the full RAG flow: retrieve relevant chunks -> build prompt
-> generate answer via local Ollama model. This is what routes_query.py
will call.
"""
import re
from app.rag.retriever import retrieve_and_format
from app.rag.vectorstore import collection_stats
from app.scrapers.catalog import INDEXED_DOMAINS, domain_list_text
from app.llm.client import generate

SYSTEM_PROMPT = (
    "You are a research assistant for a closed knowledge base of scraped pages. "
    "Answer using only the provided context. "
    "If the context is not enough to answer, say so in one sentence. "
    "Do not invent facts, news, or APIs that are not in the context. "
    "Cite sources using the [n] markers from the context."
)


def clean_citations(text: str) -> str:
    """
    Remove citation markers from text.
    Strips patterns like 'Source: [1]', '[1]', '(Source 1)', etc.
    """
    # Remove "Source: [n]" patterns
    text = re.sub(r'\s*Source:\s*\[\d+\]\s*', ' ', text)
    # Remove standalone "[n]" citation brackets
    text = re.sub(r'\s*\[\d+\]\s*', ' ', text)
    # Remove "(Source n)" patterns
    text = re.sub(r'\s*\(Source\s+\d+\)\s*', ' ', text)
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _empty_result(reason: str, answer: str) -> dict:
    stats = collection_stats()
    return {
        "answer": answer,
        "sources": [],
        "in_scope": False,
        "reason": reason,
        "indexed_domains": INDEXED_DOMAINS,
        "chunk_count": stats.get("count", 0),
    }


def answer_query(query_text: str, top_k: int = 5, source_filter: str | None = None) -> dict:
    stats = collection_stats()
    chunk_count = stats.get("count", 0)
    domains = domain_list_text()

    if chunk_count == 0:
        return _empty_result(
            "empty_index",
            "The knowledge base is empty. Scrape and ingest one of the nine "
            f"collector sites first ({domains}), then ask again.",
        )

    context, hits = retrieve_and_format(query_text, top_k=top_k, source_filter=source_filter)
    if not context.strip():
        return _empty_result(
            "below_relevance",
            "This question is outside the scraped knowledge base. "
            f"I only answer from these collectors: {domains}. "
            "Ask about those sites, or scrape a matching URL with an existing collector.",
        )

    prompt = f"Context:\n{context}\n\nQuestion: {query_text}\n\nAnswer:"
    answer = generate(prompt, system=SYSTEM_PROMPT)
    answer = clean_citations(answer)
    sources = [{
        "rank": i + 1,
        "url": h["metadata"].get("doc_url"),
        "title": h["metadata"].get("doc_title"),
        "source": h["metadata"].get("source"),
    } for i, h in enumerate(hits)]
    return {
        "answer": answer,
        "sources": sources,
        "in_scope": True,
        "reason": None,
        "indexed_domains": INDEXED_DOMAINS,
        "chunk_count": chunk_count,
    }


def ingest_documents(normalized_docs: list[dict]) -> dict:
    """Chunks + embeds + stores a batch of normalized docs."""
    from app.rag.chunker import chunk_documents
    from app.rag.vectorstore import add_chunks
    chunks = chunk_documents(normalized_docs)
    added = add_chunks(chunks)
    return {"documents_in": len(normalized_docs), "chunks_added": added}
