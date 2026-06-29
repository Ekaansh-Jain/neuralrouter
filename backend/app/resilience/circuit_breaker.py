"""Async circuit breaker with a per-model state machine.

States
------
CLOSED      Normal. Calls flow through. Consecutive failures are counted; on
            reaching the threshold the breaker trips to OPEN.
OPEN        The model is considered down. Calls are rejected immediately
            (no wasted latency) until `reset_seconds` elapse, then the breaker
            moves to HALF_OPEN.
HALF_OPEN   Recovery probe. Exactly ONE call is allowed through to test the
            model. If it succeeds -> CLOSED. If it fails -> back to OPEN.

Why the lock
------------
asyncio is single-threaded, so plain counter writes are safe between awaits.
But the HALF_OPEN probe is a classic check-then-act race: many coroutines can
observe "reset time elapsed" simultaneously and all rush in as the probe. An
`asyncio.Lock` guards the allow/record transitions so only ONE probe is ever
admitted.

Failures are also tracked at the *provider* level: a 429 from one Groq model
usually means every Groq model is throttled, so the registry can cool the whole
provider down instead of walking the chain into the same wall.

Pure-Python (stdlib only) -> fully unit-testable offline.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from enum import StrEnum

from app.providers.base import ProviderResult  # noqa: F401  (type docs only)
from app.providers.errors import ProviderError


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        model_key: str,
        *,
        failure_threshold: int = 3,
        reset_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.model_key = model_key
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._clock = clock

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def allow(self) -> bool:
        """Decide whether a call may proceed, advancing the state machine."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                assert self._opened_at is not None
                if (self._clock() - self._opened_at) >= self.reset_seconds:
                    # Cool-off elapsed: admit exactly one probe.
                    self._state = CircuitState.HALF_OPEN
                    self._probe_in_flight = True
                    return True
                return False

            # HALF_OPEN: only the single in-flight probe is allowed.
            if self._state == CircuitState.HALF_OPEN and not self._probe_in_flight:
                self._probe_in_flight = True
                return True
            return False

    async def record_success(self) -> None:
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = None
            self._probe_in_flight = False

    async def record_failure(self) -> None:
        async with self._lock:
            self._probe_in_flight = False
            if self._state == CircuitState.HALF_OPEN:
                # Probe failed -> reopen and restart the cool-off.
                self._trip()
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()

    def snapshot(self) -> dict:
        """Serializable view for the dashboard / metrics."""
        return {
            "model_key": self.model_key,
            "state": self._state.value,
            "consecutive_failures": self._consecutive_failures,
        }


class CircuitBreakerRegistry:
    """Owns one breaker per model plus provider-level rate-limit cooldowns."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        reset_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._clock = clock
        self._breakers: dict[str, CircuitBreaker] = {}
        self._provider_cooldown_until: dict[str, float] = {}

    def breaker(self, model_key: str) -> CircuitBreaker:
        if model_key not in self._breakers:
            self._breakers[model_key] = CircuitBreaker(
                model_key,
                failure_threshold=self._failure_threshold,
                reset_seconds=self._reset_seconds,
                clock=self._clock,
            )
        return self._breakers[model_key]

    def provider_cooling(self, provider: str) -> bool:
        until = self._provider_cooldown_until.get(provider)
        return until is not None and self._clock() < until

    def note_rate_limited(self, provider: str, retry_after: float | None) -> None:
        cooldown = retry_after if retry_after and retry_after > 0 else self._reset_seconds
        self._provider_cooldown_until[provider] = self._clock() + cooldown

    async def on_error(self, model_key: str, provider: str, error: ProviderError) -> None:
        """Update breaker/provider state from a categorized provider error."""
        if error.category.value == "RATE_LIMITED":
            self.note_rate_limited(provider, error.retry_after)
            return
        if error.trips_breaker:
            await self.breaker(model_key).record_failure()

    def snapshot(self) -> list[dict]:
        return [b.snapshot() for b in self._breakers.values()]
