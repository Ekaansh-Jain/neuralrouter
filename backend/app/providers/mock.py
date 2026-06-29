"""Mock provider for keyless demo mode.

Lets the entire gateway run -- and the dashboard fill with realistic data --
without any API keys. It simulates:
  - latency that scales with model size (bigger model = slower),
  - occasional transient failures (so the retry + fallback path actually fires),
  - occasional rate limits (so the provider-cooldown path fires),
so circuit breakers trip and recover during a normal demo session.

Deterministic when seeded, which is what the tests rely on.
"""

from __future__ import annotations

import asyncio
import random

from app.observability.tokens import count_tokens
from app.providers.base import ProviderResult
from app.providers.errors import ErrorCategory, ProviderError


class MockProvider:
    def __init__(
        self,
        name: str,
        *,
        base_latency_ms: float = 200.0,
        transient_rate: float = 0.06,
        rate_limit_rate: float = 0.03,
        rng: random.Random | None = None,
    ) -> None:
        self.name = name
        self.base_latency_ms = base_latency_ms
        self.transient_rate = transient_rate
        self.rate_limit_rate = rate_limit_rate
        self._rng = rng or random.Random()

    async def complete(self, model_id: str, prompt: str, *, timeout: float) -> ProviderResult:
        # Bigger models are slower; add jitter.
        size_factor = 3.0 if "70b" in model_id else (1.3 if "gemma" in model_id else 1.0)
        latency_ms = self.base_latency_ms * size_factor * self._rng.uniform(0.7, 1.5)
        await asyncio.sleep(min(latency_ms / 1000.0, timeout))

        roll = self._rng.random()
        if roll < self.rate_limit_rate:
            raise ProviderError(
                ErrorCategory.RATE_LIMITED,
                "simulated rate limit",
                provider=self.name,
                status_code=429,
                retry_after=5.0,
            )
        if roll < self.rate_limit_rate + self.transient_rate:
            raise ProviderError(
                ErrorCategory.TRANSIENT,
                "simulated transient upstream error",
                provider=self.name,
                status_code=503,
            )

        answer = (
            f"[mock:{model_id}] Here is a simulated answer to: "
            f"{prompt.strip()[:160]}"
        )
        return ProviderResult(
            text=answer,
            prompt_tokens=count_tokens(prompt),
            completion_tokens=count_tokens(answer),
            provider=self.name,
            model_id=model_id,
            raw_latency_ms=round(latency_ms, 1),
        )
