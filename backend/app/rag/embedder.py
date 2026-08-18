"""
Local embeddings via sentence-transformers. Runs on CPU, no API key,
no per-call cost — model downloads once (~80MB) and is cached locally.
"""
from sentence_transformers import SentenceTransformer
from app.config import settings

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embeds a list of strings. Returns list of float vectors."""
    if not texts:
        return []
    model = get_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
