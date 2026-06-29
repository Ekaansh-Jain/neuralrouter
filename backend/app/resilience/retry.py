"""Explicit async retry with exponential backoff.

Deliberately hand-rolled rather than using tenacity, for two reasons:

1. Transparency. In a portfolio gateway it should be obvious *exactly* what gets
   retried and when. We retry ONLY errors the taxonomy marks `is_retryable`
   (transient/unknown). Rate limits, refusals, and bad requests are never
   retried here -- the fallback layer decides what to do with those.
2. Layer hygiene. Retry (same model, transient blips), circuit breaker
   (provider down), and fallback (try a different model) must not compound into
   surprise latency. Keeping retry tiny and local makes the boundaries clear.

Backoff: base * 2**attempt, capped, with optional deterministic jitter for tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.providers.base import ProviderResult
from app.providers.errors import ProviderError

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Awaitable[ProviderResult]],
    *,
    max_attempts: int = 2,
    base_delay: float = 0.2,
    max_delay: float = 2.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ProviderResult:
    """Call `func`, retrying only retryable ProviderErrors.

    `max_attempts` counts the FIRST try plus retries (so 2 = one retry).
    The last error is re-raised if all attempts are exhausted.
    """
    last_error: ProviderError | None = None
    for attempt in range(max_attempts):
        try:
            return await func()
        except ProviderError as err:
            last_error = err
            if not err.is_retryable or attempt == max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2**attempt))
            await sleep(delay)
    # Unreachable in practice, but keeps the type checker happy.
    assert last_error is not None
    raise last_error
