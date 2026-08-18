"""
Retriever: turns a query into a ranked, prompt-ready context block.
Kept separate from vectorstore.py so retrieval logic (filters, ranking,
dedup) can evolve without touching storage internals.
"""
from app.rag.vectorstore import query as vs_query

# Chroma default metric is L2. MiniLM same-topic chunks usually land below ~1.1;
# unrelated questions (weather, sports, sites we never scraped) land higher.
MAX_L2_DISTANCE = 1.12


def retrieve(query_text: str, top_k: int = 5, source_filter: str | None = None) -> list[dict]:
    hits = vs_query(query_text, top_k=top_k, source_filter=source_filter)
    return sorted(hits, key=lambda h: h["distance"])


def retrieve_in_scope(query_text: str, top_k: int = 5, source_filter: str | None = None) -> list[dict]:
    """Nearest neighbors that are actually about the question — not just 'closest of 9 sites'."""
    hits = retrieve(query_text, top_k=top_k, source_filter=source_filter)
    return [h for h in hits if h.get("distance", 999) <= MAX_L2_DISTANCE]


def format_context(hits: list[dict], max_chars: int = 4000) -> str:
    """Builds a citation-friendly context block for the LLM prompt."""
    parts, total = [], 0
    for i, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        entry = f"[{i}] Source: {meta.get('source')} | {meta.get('doc_title') or meta.get('doc_url')}\n{hit['text']}"
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        total += len(entry)
    return "\n\n".join(parts)


def retrieve_and_format(query_text: str, top_k: int = 5, source_filter: str | None = None) -> tuple[str, list[dict]]:
    hits = retrieve_in_scope(query_text, top_k=top_k, source_filter=source_filter)
    context = format_context(hits)
    return context, hits
