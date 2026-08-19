"""
Orchestrates the full RAG flow: retrieve relevant chunks -> build prompt
-> generate answer via local Ollama model. This is what routes_query.py
will call.
"""
import re
import threading
from collections import OrderedDict

from app.rag.retriever import retrieve_and_format
from app.rag.vectorstore import collection_stats
from app.scrapers.catalog import INDEXED_DOMAINS, domain_list_text, domains_from_query
from app.llm.client import generate
from app.weather.intent import extract_place, is_weather_query
from app.weather.client import answer_weather
from app.wikipedia.intent import extract_topic, is_wikipedia_query
from app.wikipedia.client import answer_wikipedia

SYSTEM_PROMPT = (
    "You are a research assistant for a closed knowledge base of scraped pages. "
    "Answer using only the provided context. "
    "Name the models, techniques, or products the sources discuss and what they claim. "
    "If the pages do not give a numbered ranking, say that, then still summarize "
    "the strongest models or efficiency methods that appear. "
    "Do not invent facts that are not in the context. "
    "Cite sources using the [n] markers from the context."
)

_CACHE_MAX = 32
_cache_lock = threading.Lock()
_query_cache: OrderedDict[tuple, dict] = OrderedDict()


def clean_citations(text: str) -> str:
    """
    Remove citation markers from text.
    Strips patterns like 'Source: [1]', '[1]', '(Source 1)', etc.
    """
    text = re.sub(r'\s*Source:\s*\[\d+\]\s*', ' ', text)
    text = re.sub(r'\s*\[\d+\]\s*', ' ', text)
    text = re.sub(r'\s*\(Source\s+\d+\)\s*', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clear_query_cache() -> None:
    with _cache_lock:
        _query_cache.clear()


def _cache_get(key: tuple) -> dict | None:
    with _cache_lock:
        if key in _query_cache:
            _query_cache.move_to_end(key)
            return _query_cache[key]
    return None


def _cache_put(key: tuple, value: dict) -> None:
    with _cache_lock:
        _query_cache[key] = value
        _query_cache.move_to_end(key)
        while len(_query_cache) > _CACHE_MAX:
            _query_cache.popitem(last=False)


def _empty_result(reason: str, answer: str, chunk_count: int) -> dict:
    return {
        "answer": answer,
        "sources": [],
        "in_scope": False,
        "reason": reason,
        "indexed_domains": INDEXED_DOMAINS,
        "chunk_count": chunk_count,
    }


def answer_query(query_text: str, top_k: int = 5, source_filter: str | None = None) -> dict:
    cache_key = (6, query_text.strip(), top_k, source_filter)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    stats = collection_stats()
    chunk_count = stats.get("count", 0)
    domains = domain_list_text()

    if is_weather_query(query_text):
        place = extract_place(query_text)
        if not place:
            return {
                "answer": (
                    "Ask for a city or place, for example: "
                    "What is the weather in Rupnagar tomorrow?"
                ),
                "sources": [],
                "in_scope": True,
                "reason": "weather_need_place",
                "indexed_domains": INDEXED_DOMAINS,
                "chunk_count": chunk_count,
            }
        try:
            wx = answer_weather(place)
        except Exception as e:
            return {
                "answer": f"Could not fetch a live forecast for '{place}': {e}",
                "sources": [],
                "in_scope": True,
                "reason": "weather_error",
                "indexed_domains": INDEXED_DOMAINS,
                "chunk_count": chunk_count,
            }
        return {
            **wx,
            "in_scope": True,
            "reason": "open_meteo",
            "indexed_domains": INDEXED_DOMAINS,
            "chunk_count": chunk_count,
        }

    if is_wikipedia_query(query_text):
        topic = extract_topic(query_text)
        if not topic:
            return {
                "answer": (
                    "Name a topic for Wikipedia, for example: "
                    "What is artificial intelligence according to Wikipedia?"
                ),
                "sources": [],
                "in_scope": True,
                "reason": "wikipedia_need_topic",
                "indexed_domains": INDEXED_DOMAINS,
                "chunk_count": chunk_count,
            }
        try:
            wiki = answer_wikipedia(topic, query_text)
        except Exception as e:
            return {
                "answer": f"Could not fetch Wikipedia for '{topic}': {e}",
                "sources": [],
                "in_scope": True,
                "reason": "wikipedia_error",
                "indexed_domains": INDEXED_DOMAINS,
                "chunk_count": chunk_count,
            }
        return {
            **wiki,
            "in_scope": True,
            "reason": "wikipedia_live",
            "indexed_domains": INDEXED_DOMAINS,
            "chunk_count": chunk_count,
        }

    named = domains_from_query(query_text)
    route = source_filter
    if route is None and named:
        route = named[0] if len(named) == 1 else named

    if chunk_count == 0:
        result = _empty_result(
            "empty_index",
            "The knowledge base is empty. Scrape and ingest a collector first "
            f"({domains}), then ask again.",
            chunk_count,
        )
        _cache_put(cache_key, result)
        return result

    context, hits = retrieve_and_format(query_text, top_k=top_k, source_filter=route)
    if not context.strip():
        if named:
            named_txt = ", ".join(named)
            result = _empty_result(
                "missing_source",
                f"I could not find indexed chunks from {named_txt} in the current vector store. "
                "Those sites may have been scraped to disk but not ingested into this cosine index. "
                f"Run POST /ingest with the job_tag for {named_txt} (e.g. techcrunch_batch1, theverge_batch1), then ask again.",
                chunk_count,
            )
        else:
            result = _empty_result(
                "below_relevance",
                "This question is outside the scraped knowledge base. "
                f"I only answer from these collectors: {domains}. "
                "Ask about those sites, or scrape a matching URL with an existing collector.",
                chunk_count,
            )
        return result

    prompt = f"Context:\n{context}\n\nQuestion: {query_text}\n\nAnswer:"
    answer = generate(prompt, system=SYSTEM_PROMPT)
    answer = clean_citations(answer)
    sources = [{
        "rank": i + 1,
        "url": h["metadata"].get("doc_url"),
        "title": h["metadata"].get("doc_title"),
        "source": h["metadata"].get("source"),
    } for i, h in enumerate(hits)]
    result = {
        "answer": answer,
        "sources": sources,
        "in_scope": True,
        "reason": None,
        "indexed_domains": INDEXED_DOMAINS,
        "chunk_count": chunk_count,
    }
    _cache_put(cache_key, result)
    return result


def ingest_documents(normalized_docs: list[dict]) -> dict:
    """Chunks + embeds + stores a batch of normalized docs."""
    from app.rag.chunker import chunk_documents
    from app.rag.vectorstore import add_chunks
    chunks = chunk_documents(normalized_docs)
    added = add_chunks(chunks)
    clear_query_cache()
    return {"documents_in": len(normalized_docs), "chunks_added": added}
