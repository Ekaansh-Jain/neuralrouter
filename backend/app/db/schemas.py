"""Database row shapes (kept separate from the API response schemas).

These describe what we persist for analytics and the fine-tuning pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestRow:
    request_id: str
    query: str
    complexity: str
    confidence: float
    classifier_reason: str
    chosen_model: str | None
    provider: str | None
    success: bool
    fallback_occurred: bool
    cache_hit: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    modeled_cost_usd: float
    attempts: list[dict] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


@dataclass
class VerdictRow:
    request_id: str
    routing_correct: bool
    suggested_complexity: str | None
    score: float
    reason: str
    used_fallback: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__
