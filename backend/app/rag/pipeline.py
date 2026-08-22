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
    "You are a research assistant for a closed corpus of scraped pages. "
    "Answer ONLY using the provided context. Never invent facts.\n\n"
    "Use this exact structure (plain text, no markdown tables):\n"
    "Summary: <one direct sentence>\n"
    "Key points:\n"
    "- <model, technique, or finding> — <short reason from context>\n"
    "(3–5 bullets maximum)\n\n"
    "Rules: no preamble ('the pages you provided…'), no emoji, no pipe tables, "
    "no long paragraphs. If context lacks an official ranked list, say that once in Summary, "
    "then still list what the sources mention."
)

# Strip LLM filler and markdown noise from answers shown in Console.
_ANSWER_NOISE = re.compile(
    r"^(The pages you provided|The supplied (material|context)|However, they do|In short,)\b.*?\n+",
    re.I | re.S,
)
_TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_MULTI_BLANK = re.compile(r"\n{3,}")


def format_answer(text: str) -> str:
    text = (text or "").strip()
    text = _ANSWER_NOISE.sub("", text)
    text = _TABLE_LINE.sub("", text)
    text = re.sub(r"\s*Source:\s*\[\d+\]\s*", " ", text)
    text = re.sub(r"\s*\[\d+\]\s*", " ", text)
    text = re.sub(r"\s*\(Source\s+\d+\)\s*", " ", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


_CACHE_MAX = 32
_cache_lock = threading.Lock()
_query_cache: OrderedDict[tuple, dict] = OrderedDict()


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
    stats = collection_stats()
    chunk_count = stats.get("count", 0)
    # Include chunk_count so ingest invalidates stale "missing_source" answers.
    cache_key = (8, query_text.strip(), top_k, source_filter, chunk_count)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    domains = domain_list_text()

    if is_weather_query(query_text):
        place = extract_place(query_text)
        if not place:
            return {
                "answer": (
                    "Ask for a city or place, for example: "
                    "What is the weather in Delhi tomorrow?"
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

    prompt = (
        f"Context:\n{context}\n\n"
        f"Question: {query_text}\n\n"
        "Reply with Summary + Key points only."
    )
    answer = format_answer(generate(prompt, system=SYSTEM_PROMPT))

    def _source_title(meta: dict) -> str:
        title = (meta.get("doc_title") or "").strip()
        url = (meta.get("doc_url") or "").strip()
        if len(title) > 100 or not title:
            slug = url.rstrip("/").split("/")[-1] if url else ""
            if slug and slug not in {"index", "blog"}:
                title = slug.replace("-", " ").replace("_", " ").strip().title()
        if len(title) > 100:
            title = title[:97].rstrip() + "..."
        return title or url or "Untitled"

    sources = [{
        "rank": i + 1,
        "url": h["metadata"].get("doc_url"),
        "title": _source_title(h["metadata"]),
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
    import gc

    from app.rag.chunker import chunk_documents
    from app.rag.vectorstore import add_chunks

    added = 0
    # Small slices so Railway 1–2GB boxes don't OOM on MiniLM.
    step = 4
    for i in range(0, len(normalized_docs), step):
        chunks = chunk_documents(normalized_docs[i : i + step])
        added += add_chunks(chunks)
        gc.collect()
    clear_query_cache()
    return {"documents_in": len(normalized_docs), "chunks_added": added}
