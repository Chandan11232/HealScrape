"""
FastAPI entrypoint. Run with: uvicorn app.main:app --reload
Then open http://localhost:8000/docs for interactive Swagger UI —
that's the easiest way to test every endpoint without writing curl commands.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_scrape,
    routes_ingest,
    routes_query,
    routes_export,
    routes_heal,
    routes_knowledge,
)

app = FastAPI(
    title="Hackathon RAG API",
    description="Scrape (Bright Data Scraper Studio) -> closed-corpus RAG (local, free)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo-only; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_scrape.router)
app.include_router(routes_ingest.router)
app.include_router(routes_query.router)
app.include_router(routes_export.router)
app.include_router(routes_heal.router)
app.include_router(routes_knowledge.router)


@app.get("/health")
def health():
    return {"status": "ok"}
