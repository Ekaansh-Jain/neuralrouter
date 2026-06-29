"""Token counting and *modeled* cost.

`tiktoken` is used if available, otherwise we fall back to a ~4-chars-per-token
heuristic so the system still runs offline / without the dependency. The
tokenizer is cached at module load (not per request).

Cost is MODELED: on the free tier the real spend is $0, but we compute what the
traffic WOULD cost at each model's list price. That is the figure the dashboard
charts -- and being explicit that it's modeled is part of honest observability.
"""

from __future__ import annotations

from app.config.model_registry import ModelSpec

try:  # pragma: no cover - depends on optional dependency
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        if not text:
            return 0
        return len(_ENCODER.encode(text))

    TOKENIZER_BACKEND = "tiktoken/cl100k_base"
except Exception:  # tiktoken missing or no cache available
    def count_tokens(text: str) -> int:
        if not text:
            return 0
        # Rough but stable approximation: ~4 characters per token.
        return max(1, (len(text) + 3) // 4)

    TOKENIZER_BACKEND = "heuristic-chars/4"


def modeled_cost_usd(model: ModelSpec, prompt_tokens: int, completion_tokens: int) -> float:
    """Modeled USD cost for one completion at the model's list price."""
    prompt_cost = (prompt_tokens / 1_000_000) * model.prompt_usd_per_1m
    completion_cost = (completion_tokens / 1_000_000) * model.completion_usd_per_1m
    return round(prompt_cost + completion_cost, 8)
