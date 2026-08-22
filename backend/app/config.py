"""
Central config. All keys come from .env — never hardcode.
Free-tier notes:
- BRIGHTDATA_API_KEY: from Scraper Studio dashboard (trial credit, no card needed to start)
- GROQ_API_KEY: free Chat Completions for Console RAG answers
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Bright Data (required tech for this hackathon) ---
    BRIGHTDATA_API_KEY: str = os.getenv("BRIGHTDATA_API_KEY", "")
    BRIGHTDATA_BASE_URL: str = "https://api.brightdata.com/dca"  # dataset/collector API

    # Multiple scrapers: one collector per site.
    # Set in .env as a JSON object string, e.g.:
    # BRIGHTDATA_SCRAPERS={"techcrunch": "c_abc123", "wikipedia": "c_def456"}
    BRIGHTDATA_SCRAPERS: dict = json.loads(os.getenv("BRIGHTDATA_SCRAPERS", "{}"))

    # --- RAG stack ---
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Groq free production model (best stable quality on free tier as of 2026).
    # Alternatives: openai/gpt-oss-20b (faster).
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "768"))
    EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "8"))
    CHROMA_UPSERT_BATCH: int = int(os.getenv("CHROMA_UPSERT_BATCH", "32"))
    # Keep Railway 1GB ingest from embedding huge collector dumps.
    SCRAPE_MAX_RECORDS: int = int(os.getenv("SCRAPE_MAX_RECORDS", "3"))
    INGEST_MAX_DOCS: int = int(os.getenv("INGEST_MAX_DOCS", "3"))

    # --- Storage ---
    RAW_DATA_DIR: str = "data/raw"
    PROCESSED_DATA_DIR: str = "data/processed"
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")

    # --- Safety limits so free tiers never get exceeded ---
    MAX_PAGES_PER_SCRAPE: int = 20

    # Auto-heal when a collector's extraction quality drops below these.
    HEAL_MIN_SUCCESS_RATE: float = float(os.getenv("HEAL_MIN_SUCCESS_RATE", "60"))
    HEAL_MAX_EMPTY_FIELD_PCT: float = float(os.getenv("HEAL_MAX_EMPTY_FIELD_PCT", "40"))

    # Heal path: give Bright Data AI enough time; keep scrapes bounded.
    SCRAPE_POLL_INTERVAL: int = int(os.getenv("SCRAPE_POLL_INTERVAL", "2"))
    HEAL_SCRAPE_TIMEOUT: int = int(os.getenv("HEAL_SCRAPE_TIMEOUT", "150"))
    HEAL_SCRAPE_RETRIES: int = int(os.getenv("HEAL_SCRAPE_RETRIES", "1"))
    HEAL_POLL_SECONDS: int = int(os.getenv("HEAL_POLL_SECONDS", "2"))
    # BD AI (code_fixer etc.) often needs 5–12 minutes — do not soft-abort at 2–3 min.
    HEAL_MAX_SECONDS: int = int(os.getenv("HEAL_MAX_SECONDS", "900"))
    HEAL_STUCK_STEP_SECONDS: int = int(os.getenv("HEAL_STUCK_STEP_SECONDS", "420"))
    HEAL_ACTIVE_WATCH_SECONDS: int = int(os.getenv("HEAL_ACTIVE_WATCH_SECONDS", "600"))


settings = Settings()
