"""Shared test helpers."""

from __future__ import annotations

import asyncio
from typing import Any

from app.config.model_registry import ModelSpec
from app.providers.base import ProviderResult


def run(coro) -> Any:
    """Run an async coroutine in a fresh event loop (no pytest-asyncio needed)."""
    return asyncio.run(coro)


class MutableClock:
    """A controllable clock for deterministic time-based tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def spec(key: str, provider: str, model_id: str = "m") -> ModelSpec:
    return ModelSpec(
        key=key,
        provider=provider,
        model_id=model_id,
        label=key,
        prompt_usd_per_1m=1.0,
        completion_usd_per_1m=1.0,
        context_window=8192,
    )


def ok_result(provider: str = "groq", model_id: str = "m") -> ProviderResult:
    return ProviderResult(
        text="ok answer with several words here",
        prompt_tokens=10,
        completion_tokens=20,
        provider=provider,
        model_id=model_id,
    )
