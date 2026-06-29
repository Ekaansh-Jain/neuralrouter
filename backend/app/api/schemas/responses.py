"""Public API response models (the output contract).

Kept deliberately separate from the DB row schemas: the wire format and the
storage format evolve for different reasons.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.pipeline.orchestrator import GatewayResponse


class AttemptInfo(BaseModel):
    model_key: str
    ok: bool
    error_category: str | None = None
    detail: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    success: bool
    answer: str | None
    complexity: str
    confidence: float
    classifier_reason: str
    chosen_model: str | None
    chosen_model_label: str | None
    provider: str | None
    fallback_occurred: bool
    cache_hit: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    modeled_cost_usd: float
    attempts: list[AttemptInfo]
    error: str | None = None

    @classmethod
    def from_gateway(cls, resp: GatewayResponse) -> ChatResponse:
        return cls(
            request_id=resp.request_id,
            success=resp.success,
            answer=resp.answer,
            complexity=resp.complexity,
            confidence=resp.confidence,
            classifier_reason=resp.classifier_reason,
            chosen_model=resp.chosen_model,
            chosen_model_label=resp.chosen_model_label,
            provider=resp.provider,
            fallback_occurred=resp.fallback_occurred,
            cache_hit=resp.cache_hit,
            latency_ms=resp.latency_ms,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            modeled_cost_usd=resp.modeled_cost_usd,
            attempts=[AttemptInfo(**a) for a in resp.attempts],
            error=resp.error,
        )
