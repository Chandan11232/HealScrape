"""
Local LLM calls via Ollama. No API key, no per-token cost —
just needs `ollama serve` running with the model pulled.
"""
import httpx
import ollama
from app.config import settings


class OllamaUnavailable(RuntimeError):
    pass


def generate(prompt: str, system: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
        )
    except (httpx.ConnectError, ConnectionError) as e:
        raise OllamaUnavailable(
            "Ollama is not running. Start it with `ollama serve`, then "
            f"`ollama pull {settings.OLLAMA_MODEL}`. Tried {settings.OLLAMA_BASE_URL}."
        ) from e
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "pull" in msg:
            raise OllamaUnavailable(
                f"Ollama is up but model '{settings.OLLAMA_MODEL}' is missing. "
                f"Run: ollama pull {settings.OLLAMA_MODEL}"
            ) from e
        raise

    return response["message"]["content"]
