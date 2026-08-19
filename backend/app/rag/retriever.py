"""
Retriever: turns a query into a ranked, prompt-ready context block.
Kept separate from vectorstore.py so retrieval logic (filters, ranking,
dedup) can evolve without touching storage internals.
"""
from __future__ import annotations

import re

from app.rag.vectorstore import query as vs_query
from app.scrapers.catalog import _QUERY_ALIASES, domains_from_query

# Chroma cosine distance is 1 - cosine similarity. MiniLM same-topic chunks
# usually land below ~0.68; unrelated questions land higher.
MAX_DISTANCE = 0.68
MAX_DISTANCE_FILTERED = 1.05
FETCH_K = 12

_STOP = re.compile(
    r"\b(what|which|who|how|does|do|did|is|are|the|a|an|in|on|for|about|"
    r"according|to|from|scraped|pages?|say|said|ingested|article|current|"
    r"will|be|used|work|with|and|or|of|that|this)\b",
    re.I,
)
_HTML = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def _strip_site_mentions(query_text: str) -> str:
    q = query_text or ""
    for alias, _domain in sorted(_QUERY_ALIASES, key=lambda x: len(x[0]), reverse=True):
        q = re.sub(re.escape(alias), " ", q, flags=re.I)
    return _SPACE.sub(" ", q).strip(" ?.,")


def expand_queries(query_text: str) -> list[str]:
    """Site names bias embeddings toward marketing pages; expand ranking questions."""
    queries = [query_text]
    stripped = _STOP.sub(" ", _strip_site_mentions(query_text))
    stripped = _SPACE.sub(" ", stripped).strip(" ?.,")
    if stripped and stripped.lower() not in {query_text.lower(), ""}:
        queries.append(stripped)
    low = stripped.lower()
    ranking = bool(re.search(r"\b(best|top|greatest|leading)\b", low) and re.search(r"\bmodels?\b", low))
    efficient = bool(re.search(r"\b(efficient|efficiency|small|fast|quantiz)\b", low))
    if ranking:
        queries.append("open LLM leaderboard best models")
        queries.append("state of open models")
    if efficient:
        queries.append("quantized efficient small language models Optimum")
    unique, seen = [], set()
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:5]


def _unique_by_url(hits: list[dict]) -> list[dict]:
    seen, out = set(), []
    for hit in hits:
        url = (hit.get("metadata") or {}).get("doc_url") or hit.get("id")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(hit)
    return out


def retrieve(query_text: str, top_k: int = 5, source_filter: str | list[str] | None = None) -> list[dict]:
    per_query = max(top_k, FETCH_K)
    queries = expand_queries(query_text)
    if len(queries) > 1:
        queries = queries[1:] + queries[:1]
    buckets = [
        _unique_by_url(vs_query(q, top_k=per_query, source_filter=source_filter))
        for q in queries
    ]
    # Interleave so expanded searches (leaderboards, quantized models) are not
    # buried by a generic embedding match on the original wording.
    merged, seen = [], set()
    depth = max((len(b) for b in buckets), default=0)
    for i in range(depth):
        for bucket in buckets:
            if i >= len(bucket):
                continue
            hit = bucket[i]
            url = (hit.get("metadata") or {}).get("doc_url") or hit.get("id")
            if url in seen:
                continue
            seen.add(url)
            merged.append(hit)
            if len(merged) >= max(top_k * 3, FETCH_K):
                return merged
    return merged


def retrieve_in_scope(
    query_text: str,
    top_k: int = 5,
    source_filter: str | list[str] | None = None,
) -> list[dict]:
    """Nearest neighbors that are actually about the question — not just 'closest of 9 sites'."""
    hits = retrieve(query_text, top_k=top_k, source_filter=source_filter)
    if source_filter:
        return hits[:top_k]
    return [h for h in hits if h.get("distance", 999) <= MAX_DISTANCE][:top_k]


def _visible_text(text: str) -> str:
    cleaned = _HTML.sub(" ", text or "")
    return _SPACE.sub(" ", cleaned).strip()


def format_context(hits: list[dict], max_chars: int = 4000) -> tuple[str, list[dict]]:
    """Builds a citation-friendly context block; returns only the hits that fit."""
    parts, used, total = [], [], 0
    for i, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        body = _visible_text(hit["text"])
        if not body:
            continue
        entry = (
            f"[{i}] Source: {meta.get('source')} | "
            f"{meta.get('doc_title') or meta.get('doc_url')}\n{body}"
        )
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        used.append(hit)
        total += len(entry)
    return "\n\n".join(parts), used


def retrieve_and_format(
    query_text: str,
    top_k: int = 5,
    source_filter: str | list[str] | None = None,
) -> tuple[str, list[dict]]:
    if source_filter is None:
        named = domains_from_query(query_text)
        if len(named) == 1:
            source_filter = named[0]
        elif len(named) > 1:
            source_filter = named
    fetch_k = max(top_k, FETCH_K)
    hits = retrieve_in_scope(query_text, top_k=fetch_k, source_filter=source_filter)[:top_k]
    context, used = format_context(hits, max_chars=5500)
    return context, used
