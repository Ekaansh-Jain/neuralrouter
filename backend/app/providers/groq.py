"""Groq provider factory (OpenAI-compatible API)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.providers.openai_compat import OpenAICompatProvider

if TYPE_CHECKING:  # pragma: no cover
    import httpx

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def build_groq(api_key: str, client: httpx.AsyncClient) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        "groq", base_url=GROQ_BASE_URL, api_key=api_key, client=client
    )
