"""Classifier interface.

The classifier decides query complexity (SIMPLE / MODERATE / COMPLEX). It is
defined as a Protocol with a `Classification` result so implementations are
swappable: v1 is a zero-cost heuristic; a v2 trained encoder model can drop in
later WITHOUT touching the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class Classification:
    label: str          # one of model_registry.COMPLEXITY_LABELS
    confidence: float   # 0..1
    reason: str         # human-readable explanation (shown in logs/dashboard)


@runtime_checkable
class Classifier(Protocol):
    name: str

    async def classify(self, query: str) -> Classification:
        ...
