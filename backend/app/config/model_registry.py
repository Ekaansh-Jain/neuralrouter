"""Data-driven model pool and fallback chains.

This module is intentionally free of third-party imports so the routing logic
that depends on it stays unit-testable without installing anything.

A `ModelSpec` describes one model on one provider, including its *modeled*
price (USD per 1M tokens). Prices are what the model WOULD cost on a paid plan;
on the free tier the real cost is $0, but tracking modeled cost is what makes
the dashboard interesting.

`FALLBACK_CHAINS` maps a complexity label to an ordered list of model keys to
try. The router walks the chain top-to-bottom until one succeeds (or the global
deadline is hit).
"""

from __future__ import annotations

from dataclasses import dataclass

# Complexity labels produced by the classifier.
SIMPLE = "SIMPLE"
MODERATE = "MODERATE"
COMPLEX = "COMPLEX"
COMPLEXITY_LABELS = (SIMPLE, MODERATE, COMPLEX)


@dataclass(frozen=True)
class ModelSpec:
    """Static description of a single routable model."""

    key: str           # unique id used across the system, e.g. "groq/llama-3.1-8b"
    provider: str      # "groq" | "openrouter"
    model_id: str      # the id the provider's API expects
    label: str         # human-friendly name for the dashboard
    prompt_usd_per_1m: float    # modeled input price per 1M tokens
    completion_usd_per_1m: float  # modeled output price per 1M tokens
    context_window: int


# ── The model pool ───────────────────────────────────────────────
# Add or remove a model here and the whole system picks it up. No code changes.
MODEL_POOL: dict[str, ModelSpec] = {
    "groq/llama-3.1-8b": ModelSpec(
        key="groq/llama-3.1-8b",
        provider="groq",
        model_id="llama-3.1-8b-instant",
        label="Llama 3.1 8B (Groq)",
        prompt_usd_per_1m=0.05,
        completion_usd_per_1m=0.08,
        context_window=131072,
    ),
    "groq/llama-3.3-70b": ModelSpec(
        key="groq/llama-3.3-70b",
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        label="Llama 3.3 70B (Groq)",
        prompt_usd_per_1m=0.59,
        completion_usd_per_1m=0.79,
        context_window=131072,
    ),
    "groq/mixtral-8x7b": ModelSpec(
        key="groq/mixtral-8x7b",
        provider="groq",
        model_id="mixtral-8x7b-32768",
        label="Mixtral 8x7B (Groq)",
        prompt_usd_per_1m=0.24,
        completion_usd_per_1m=0.24,
        context_window=32768,
    ),
    "openrouter/llama-3.1-8b-free": ModelSpec(
        key="openrouter/llama-3.1-8b-free",
        provider="openrouter",
        model_id="meta-llama/llama-3.1-8b-instruct:free",
        label="Llama 3.1 8B (OpenRouter free)",
        prompt_usd_per_1m=0.0,
        completion_usd_per_1m=0.0,
        context_window=131072,
    ),
}


# ── Fallback chains per complexity ───────────────────────────────
# Ordered: the router tries index 0 first, then 1, etc.
# Note each chain ends on a DIFFERENT provider so a provider-wide outage
# (e.g. Groq rate-limiting every model) can still be escaped.
FALLBACK_CHAINS: dict[str, list[str]] = {
    SIMPLE: [
        "groq/llama-3.1-8b",
        "openrouter/llama-3.1-8b-free",
    ],
    MODERATE: [
        "groq/mixtral-8x7b",
        "groq/llama-3.1-8b",
        "openrouter/llama-3.1-8b-free",
    ],
    COMPLEX: [
        "groq/llama-3.3-70b",
        "groq/mixtral-8x7b",
        "openrouter/llama-3.1-8b-free",
    ],
}


def get_model(key: str) -> ModelSpec:
    """Look up a model spec by key, raising a clear error if it is missing."""
    try:
        return MODEL_POOL[key]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown model key: {key!r}") from exc


def chain_for(complexity: str) -> list[ModelSpec]:
    """Return the ordered list of model specs to try for a complexity label."""
    keys = FALLBACK_CHAINS.get(complexity, FALLBACK_CHAINS[SIMPLE])
    return [get_model(k) for k in keys]
