"""In-memory metrics store powering the dashboard.

Keeps a bounded window of recent request samples and exposes aggregates:
latency percentiles (p50/p95/p99 -- averages hide the interesting tail),
per-model usage, fallback rate, cache-hit rate, and modeled cost totals.

This is per-process (documented limitation): with a single worker it is exactly
right; to scale horizontally you would move it to Redis. Kept deliberately
simple and dependency-free so it is testable offline.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict, dataclass, field


@dataclass
class RequestSample:
    ts: float
    complexity: str
    chosen_model: str | None
    success: bool
    fallback_occurred: bool
    cache_hit: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    attempts: int


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return round(s[lo] + (s[hi] - s[lo]) * frac, 2)


@dataclass
class MetricsStore:
    maxlen: int = 1000
    _samples: deque[RequestSample] = field(default_factory=lambda: deque(maxlen=1000))
    _cache_hits: int = 0
    _cache_misses: int = 0

    def record(self, sample: RequestSample) -> None:
        self._samples.append(sample)
        if sample.cache_hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    def summary(self, breaker_snapshot: list[dict] | None = None) -> dict:
        samples = list(self._samples)
        total = len(samples)
        latencies = [s.latency_ms for s in samples]
        successes = sum(1 for s in samples if s.success)
        fallbacks = sum(1 for s in samples if s.fallback_occurred)

        by_model: dict[str, int] = {}
        by_complexity: dict[str, int] = {}
        cost_total = 0.0
        tokens_total = 0
        for s in samples:
            if s.chosen_model:
                by_model[s.chosen_model] = by_model.get(s.chosen_model, 0) + 1
            by_complexity[s.complexity] = by_complexity.get(s.complexity, 0) + 1
            cost_total += s.cost_usd
            tokens_total += s.prompt_tokens + s.completion_tokens

        cache_total = self._cache_hits + self._cache_misses
        return {
            "total_requests": total,
            "success_rate": round(successes / total, 4) if total else 0.0,
            "fallback_rate": round(fallbacks / total, 4) if total else 0.0,
            "latency_ms": {
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "p99": _percentile(latencies, 0.99),
            },
            "usage_by_model": by_model,
            "usage_by_complexity": by_complexity,
            "modeled_cost_usd_total": round(cost_total, 6),
            "tokens_total": tokens_total,
            "cache_hit_rate": round(self._cache_hits / cache_total, 4) if cache_total else 0.0,
            "circuit_breakers": breaker_snapshot or [],
        }

    def recent(self, limit: int = 50) -> list[dict]:
        items = list(self._samples)[-limit:]
        return [asdict(s) for s in reversed(items)]


def new_sample(**kwargs) -> RequestSample:
    kwargs.setdefault("ts", time.time())
    return RequestSample(**kwargs)
