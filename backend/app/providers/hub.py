"""Provider hub: builds the right provider instances and dispatches calls.

Acts as the single `ProviderCaller` the router uses. In "mock" mode every
provider is simulated (no keys, fully offline). In "live" mode it builds real
Groq/OpenRouter clients -- but if a key is missing it falls back to the mock for
that provider so the app still boots and the demo still works.

httpx is imported lazily (only when a live provider is actually built) so this
module -- and anything that imports it -- stays importable without httpx.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from app.config.model_registry import ModelSpec
from app.providers.base import Provider, ProviderResult
from app.providers.errors import ErrorCategory, ProviderError
from app.providers.mock import MockProvider

if TYPE_CHECKING:  # pragma: no cover
    import httpx

    from app.config.settings import Settings


class ProviderHub:
    def __init__(self, providers: dict[str, Provider]) -> None:
        self._providers = providers

    @property
    def names(self) -> list[str]:
        return list(self._providers)

    async def call(self, model: ModelSpec, prompt: str, timeout: float) -> ProviderResult:
        provider = self._providers.get(model.provider)
        if provider is None:
            raise ProviderError(
                ErrorCategory.INVALID_REQUEST,
                f"no provider configured for {model.provider!r}",
                provider=model.provider,
                model_key=model.key,
            )
        return await provider.complete(model.model_id, prompt, timeout=timeout)


def build_hub(settings: Settings, client: httpx.AsyncClient | None) -> ProviderHub:
    providers: dict[str, Provider] = {}

    if settings.provider_mode == "live" and settings.groq_api_key and client is not None:
        from app.providers.groq import build_groq

        providers["groq"] = build_groq(settings.groq_api_key, client)
    else:
        providers["groq"] = MockProvider("groq", base_latency_ms=180, rng=random.Random(1))

    if settings.provider_mode == "live" and settings.openrouter_api_key and client is not None:
        from app.providers.openrouter import build_openrouter

        providers["openrouter"] = build_openrouter(settings.openrouter_api_key, client)
    else:
        providers["openrouter"] = MockProvider(
            "openrouter", base_latency_ms=320, transient_rate=0.04, rng=random.Random(2)
        )

    return ProviderHub(providers)
