"""Request-wide time budget.

The single most important fallback bug is *latency stacking*: model A times out
at 25s, then B times out, then C... and the user waits over a minute. A
`Deadline` is created once per request and threaded through the fallback chain.
Each attempt asks how much time is left and caps its own timeout accordingly,
so the TOTAL wait can never exceed the budget.

Uses a monotonic clock (injectable for deterministic tests).
"""

from __future__ import annotations

import time
from collections.abc import Callable


class Deadline:
    def __init__(self, budget_seconds: float, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._start = clock()
        self.budget = budget_seconds

    @property
    def elapsed(self) -> float:
        return self._clock() - self._start

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget - self.elapsed)

    @property
    def expired(self) -> bool:
        return self.remaining <= 0.0

    def slice_for_attempt(self, per_call_cap: float) -> float:
        """Timeout to give a single provider call: the smaller of the per-call
        cap and whatever budget remains."""
        return max(0.0, min(per_call_cap, self.remaining))
