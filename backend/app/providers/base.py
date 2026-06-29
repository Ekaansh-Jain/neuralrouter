"""Provider abstraction.

Every provider (Groq, OpenRouter, the mock) implements the same `Provider`
protocol and returns the same `ProviderResult`, so the router can treat them
identically. Pure-Python (stdlib only) so it is importable in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ProviderResult:
    """A successful completion from a provider."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    provider: str
    model_id: str
    raw_latency_ms: float = 0.0
    extra: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@runtime_checkable
class Provider(Protocol):
    """Anything that can turn a prompt into a `ProviderResult`.

    Implementations MUST raise `ProviderError` (see errors.py) on failure so the
    resilience layer can categorize the problem.
    """

    name: str

    async def complete(self, model_id: str, prompt: str, *, timeout: float) -> ProviderResult:
        ...
