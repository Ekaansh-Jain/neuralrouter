"""OpenRouter provider factory (OpenAI-compatible API).

OpenRouter recommends sending Referer / X-Title headers identifying your app;
they are harmless if omitted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.providers.openai_compat import OpenAICompatProvider

if TYPE_CHECKING:  # pragma: no cover
    import httpx

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def build_openrouter(api_key: str, client: httpx.AsyncClient) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        "openrouter",
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        client=client,
        extra_headers={
            "HTTP-Referer": "https://neuralrouter.local",
            "X-Title": "NeuralRouter",
        },
    )
