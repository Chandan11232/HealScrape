"""
LLM calls via Groq's OpenAI-compatible Chat Completions API.
Free-tier default: openai/gpt-oss-120b (stable production model).
"""
from __future__ import annotations

import httpx

from app.config import settings

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMUnavailable(RuntimeError):
    pass


# Back-compat alias for older imports
OllamaUnavailable = LLMUnavailable


def generate(prompt: str, system: str | None = None) -> str:
    api_key = (settings.GROQ_API_KEY or "").strip()
    if not api_key:
        raise LLMUnavailable(
            "GROQ_API_KEY is not set. Create a free key at https://console.groq.com/keys "
            "and add GROQ_API_KEY to backend/.env."
        )

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": 0,
        "max_tokens": settings.GROQ_MAX_TOKENS,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                GROQ_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as e:
        raise LLMUnavailable(f"Could not reach Groq API: {e}") from e

    if resp.status_code == 401:
        raise LLMUnavailable("Groq rejected the API key (401). Check GROQ_API_KEY.")
    if resp.status_code == 429:
        raise LLMUnavailable(
            "Groq rate limit hit (429). Free tier is limited — wait a minute and retry."
        )
    if resp.status_code >= 400:
        detail = (resp.text or "")[:300]
        raise LLMUnavailable(f"Groq error HTTP {resp.status_code}: {detail}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMUnavailable(f"Unexpected Groq response shape: {data!r}") from e
