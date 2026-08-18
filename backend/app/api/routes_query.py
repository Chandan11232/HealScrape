"""
POST /query — the actual RAG endpoint. Retrieves relevant chunks from
Chroma, generates an answer via local Ollama, returns answer + sources.
"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import QueryRequest, QueryResponse, SourceRef
from app.rag.pipeline import answer_query
from app.llm.client import OllamaUnavailable

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        result = answer_query(req.query, top_k=req.top_k, source_filter=req.source_filter)
    except OllamaUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return QueryResponse(
        answer=result["answer"],
        sources=[SourceRef(**s) for s in result["sources"]],
        in_scope=result.get("in_scope", True),
        reason=result.get("reason"),
        indexed_domains=result.get("indexed_domains", []),
        chunk_count=result.get("chunk_count", 0),
    )