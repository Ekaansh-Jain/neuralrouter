"""Deterministic model selection.

Given a complexity label, return the ordered list of model specs to attempt.
This is pure data lookup against the registry -- intentionally NOT an "agent",
because the choice must be predictable and explainable.
"""

from __future__ import annotations

from app.config.model_registry import ModelSpec, chain_for


def select_chain(complexity: str) -> list[ModelSpec]:
    """Ordered candidate models for a complexity label (primary first)."""
    return chain_for(complexity)
