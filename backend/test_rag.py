"""
Manual smoke test for the RAG layer. Run from backend/: python test_rag.py

Requires: `ollama serve` running locally with OLLAMA_MODEL pulled.
Uses whatever normalized_*.json files exist in data/processed/ from
your scraper smoke test — no new scraping, no cost.
"""
import json
import glob
from app.rag.pipeline import ingest_documents, answer_query
from app.rag.vectorstore import collection_stats


def load_all_normalized_docs() -> list[dict]:
    docs = []
    for path in glob.glob("data/processed/normalized_*.json"):
        docs.extend(json.loads(open(path).read()))
    return docs


if __name__ == "__main__":
    print("=== RAG Layer Smoke Test ===")

    docs = load_all_normalized_docs()
    if not docs:
        print("No normalized docs found in data/processed/. Run test_scrapers.py first.")
        exit(1)

    print(f"Loaded {len(docs)} normalized docs")
    result = ingest_documents(docs)
    print(f"Ingested: {result}")
    print(f"Vector store stats: {collection_stats()}")

    query = input("\nEnter a test query: ").strip() or "What is this data about?"
    response = answer_query(query, top_k=3)

    print("\n--- Answer ---")
    print(response["answer"])
    print("\n--- Sources ---")
    for s in response["sources"]:
        print(f"[{s['rank']}] {s['title'] or s['url']} ({s['source']})")
