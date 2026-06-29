"""Fallback executor -- the heart of the resilience design.

Walks the ordered model chain and returns the first successful completion,
coordinating four mechanisms with clear, non-overlapping responsibilities:

    Deadline         caps TOTAL latency across the whole chain.
    CircuitBreaker   skips models/providers already known to be failing.
    retry_async      retries a single model on transient blips only.
    error taxonomy   decides skip vs. stop vs. fall back per failure type.

Returns a `RouteOutcome` describing what happened -- including whether a
fallback occurred, which is recorded separately from the routing decision so it
never poisons the classifier's training data later.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.config.model_registry import ModelSpec
from app.providers.base import ProviderResult
from app.providers.errors import ErrorCategory, ProviderError
from app.resilience.circuit_breaker import CircuitBreakerRegistry
from app.resilience.deadline import Deadline
from app.resilience.retry import retry_async

# A function that actually calls a provider for one model, given a timeout.
ProviderCaller = Callable[[ModelSpec, str, float], Awaitable[ProviderResult]]


@dataclass
class AttemptRecord:
    model_key: str
    ok: bool
    error_category: str | None = None
    detail: str | None = None


@dataclass
class RouteOutcome:
    success: bool
    result: ProviderResult | None = None
    chosen_model: ModelSpec | None = None
    primary_model_key: str | None = None
    fallback_occurred: bool = False
    attempts: list[AttemptRecord] = field(default_factory=list)
    error: str | None = None


async def execute_chain(
    chain: list[ModelSpec],
    prompt: str,
    *,
    deadline: Deadline,
    breakers: CircuitBreakerRegistry,
    call_provider: ProviderCaller,
    per_call_timeout: float = 20.0,
    retry_attempts: int = 2,
    semaphore: asyncio.Semaphore | None = None,
) -> RouteOutcome:
    primary_key = chain[0].key if chain else None
    attempts: list[AttemptRecord] = []

    for index, model in enumerate(chain):
        if deadline.expired:
            attempts.append(AttemptRecord(model.key, ok=False, detail="deadline_exceeded"))
            break

        # Skip models the breaker has opened or whose provider is cooling down.
        if breakers.provider_cooling(model.provider):
            attempts.append(AttemptRecord(model.key, ok=False, detail="provider_cooling"))
            continue
        if not await breakers.breaker(model.key).allow():
            attempts.append(AttemptRecord(model.key, ok=False, detail="circuit_open"))
            continue

        timeout = deadline.slice_for_attempt(per_call_timeout)
        if timeout <= 0:
            attempts.append(AttemptRecord(model.key, ok=False, detail="no_time_left"))
            break

        # Bind loop vars as defaults so the closure captures THIS iteration's
        # model/timeout (it is awaited before the next iteration anyway).
        async def _call(model=model, timeout=timeout) -> ProviderResult:
            if semaphore is not None:
                async with semaphore:
                    return await call_provider(model, prompt, timeout)
            return await call_provider(model, prompt, timeout)

        try:
            result = await retry_async(_call, max_attempts=retry_attempts)
        except ProviderError as err:
            attempts.append(
                AttemptRecord(model.key, ok=False, error_category=err.category.value,
                              detail=err.message)
            )
            await breakers.on_error(model.key, model.provider, err)
            if not err.should_try_next_model:
                # Refusal / invalid request: the chain won't help. Stop now.
                return RouteOutcome(
                    success=False,
                    primary_model_key=primary_key,
                    attempts=attempts,
                    error=f"{err.category.value}: {err.message}",
                )
            continue  # fall back to the next model
        except TimeoutError:
            attempts.append(
                AttemptRecord(model.key, ok=False,
                              error_category=ErrorCategory.TRANSIENT.value, detail="timeout")
            )
            await breakers.breaker(model.key).record_failure()
            continue

        # Success.
        await breakers.breaker(model.key).record_success()
        attempts.append(AttemptRecord(model.key, ok=True))
        return RouteOutcome(
            success=True,
            result=result,
            chosen_model=model,
            primary_model_key=primary_key,
            fallback_occurred=index > 0,
            attempts=attempts,
        )

    return RouteOutcome(
        success=False,
        primary_model_key=primary_key,
        fallback_occurred=len(attempts) > 1,
        attempts=attempts,
        error="all_models_failed",
    )
