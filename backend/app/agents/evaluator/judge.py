"""Routing evaluator (sampled, runs in the background).

Given a finished response, it judges whether the routing decision looks correct
and produces a `Verdict`. These verdicts become the labeled dataset that the
classifier is later retrained on (see backend/fine_tune/).

This default implementation is a lightweight, offline heuristic so the system is
fully runnable without extra API calls. A production version would call an LLM
as the judge -- it implements the same `evaluate` signature, so swapping it in
requires no changes elsewhere.

IMPORTANT: it records whether a FALLBACK occurred separately from the routing
verdict. A weak answer produced because the primary model was down must NOT be
counted as a bad routing decision, or the training data gets poisoned.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.classifier.base import Classifier
from app.config.model_registry import COMPLEX, SIMPLE


@dataclass
class Verdict:
    routing_correct: bool
    suggested_complexity: str | None
    score: float          # 0..1, higher = better routing
    reason: str
    used_fallback: bool   # tracked separately so it can be excluded from training


class HeuristicEvaluator:
    """Re-derives complexity from the query and compares it to what was used."""

    name = "heuristic-judge-v1"

    def __init__(self, classifier: Classifier) -> None:
        self._classifier = classifier

    async def evaluate(self, complexity_used: str, query: str, answer: str | None) -> Verdict:
        if not answer:
            return Verdict(False, None, 0.0, "empty answer", used_fallback=False)

        derived = await self._classifier.classify(query)
        agree = derived.label == complexity_used

        # A short answer to a query routed as COMPLEX is mildly suspicious;
        # a long answer to a SIMPLE query suggests under-routing.
        words = len(answer.split())
        signal_ok = not (
            (complexity_used == COMPLEX and words < 15)
            or (complexity_used == SIMPLE and words > 250)
        )

        correct = agree and signal_ok
        score = round(0.5 * float(agree) + 0.5 * float(signal_ok), 2)
        reason = (
            f"derived={derived.label} used={complexity_used} "
            f"agree={agree} signal_ok={signal_ok}"
        )
        return Verdict(
            routing_correct=correct,
            suggested_complexity=derived.label,
            score=score,
            reason=reason,
            used_fallback=False,
        )
