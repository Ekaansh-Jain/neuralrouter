"""Heuristic complexity classifier (v1).

Zero LLM cost, zero latency, fully deterministic -- and it keeps the classifier
OUT of the critical path, which was the main architectural fix for this project
(an LLM classifier would triple latency and rate-limit usage).

It scores a query on a few cheap signals:
  - length (longer questions tend to be harder)
  - presence of code / stack traces
  - reasoning keywords ("why", "design", "prove", "compare", "optimize"...)
  - multi-part structure (multiple questions / numbered steps)

The score maps to SIMPLE / MODERATE / COMPLEX. Confidence reflects how far the
score sits from the decision boundaries. A trained encoder (v2) can replace this
behind the same interface once enough labeled data is collected.
"""

from __future__ import annotations

import re

from app.agents.classifier.base import Classification
from app.config.model_registry import COMPLEX, MODERATE, SIMPLE

_CODE_HINTS = re.compile(r"```|def |class |import |traceback|stack trace|=>|;\s*$", re.IGNORECASE)
_REASONING_HINTS = re.compile(
    r"\b(why|how come|design|architect|prove|derive|optimi[sz]e|trade[- ]?off|compare|"
    r"explain in detail|step by step|analyze|algorithm|complexity|refactor)\b",
    re.IGNORECASE,
)
_SIMPLE_HINTS = re.compile(
    r"\b(what is|who is|when did|define|spelling|capital of|translate|convert|"
    r"how do you spell)\b",
    re.IGNORECASE,
)


class HeuristicClassifier:
    name = "heuristic-v1"

    async def classify(self, query: str) -> Classification:
        q = query.strip()
        words = len(q.split())

        score = 0.0
        signals: list[str] = []

        if words > 120:
            score += 2.0
            signals.append("very long")
        elif words > 40:
            score += 1.0
            signals.append("long")
        elif words > 20:
            score += 0.5
            signals.append("medium length")
        elif words < 8:
            score -= 1.0
            signals.append("very short")

        if _CODE_HINTS.search(q):
            score += 1.5
            signals.append("contains code")

        # Weight by how MANY distinct reasoning signals appear, not just one.
        reasoning_matches = {m.lower() for m in _REASONING_HINTS.findall(q)}
        if reasoning_matches:
            score += min(2.0, 0.7 * len(reasoning_matches))
            signals.append(f"reasoning x{len(reasoning_matches)}")

        if _SIMPLE_HINTS.search(q):
            score -= 1.5
            signals.append("lookup phrasing")
        if q.count("?") >= 2 or re.search(r"\b\d+\.\s", q):
            score += 1.0
            signals.append("multi-part")

        # Map score -> label with simple thresholds.
        if score >= 2.5:
            label, lo, hi = COMPLEX, 2.5, 5.0
        elif score >= 0.5:
            label, lo, hi = MODERATE, 0.5, 2.5
        else:
            label, lo, hi = SIMPLE, -2.0, 0.5

        # Confidence = how centered the score is within its band (0.5..0.95).
        span = hi - lo
        centered = 1.0 - abs((score - lo) / span - 0.5) * 2 if span else 0.5
        confidence = round(0.5 + 0.45 * max(0.0, min(1.0, centered)), 2)

        reason = ", ".join(signals) if signals else "no strong signals"
        return Classification(label=label, confidence=confidence, reason=reason)
