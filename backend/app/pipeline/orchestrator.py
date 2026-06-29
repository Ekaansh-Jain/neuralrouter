"""Request orchestrator -- coordinates the pipeline, owns no business logic.

Sequence for one request:
    1. cache lookup (identical query within TTL -> instant return)
    2. classify complexity (cheap heuristic, off the critical path)
    3. select the fallback chain for that complexity
    4. execute the chain under a global deadline (+ breakers, retry, semaphore)
    5. count tokens + modeled cost
    6. record a metrics sample
    7. schedule background work (DB log always; evaluator on a sample)
    8. return the response

Everything is injected (classifier, breakers, cache, metrics, provider caller,
scheduler, loggers) so this class has NO framework imports and is unit-testable
with the mock provider entirely offline.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from random import Random

from app.agents.classifier.base import Classifier
from app.cache.memory_cache import TTLCache, make_key
from app.observability.metrics import MetricsStore, new_sample
from app.observability.tokens import modeled_cost_usd
from app.providers.base import ProviderResult
from app.resilience.circuit_breaker import CircuitBreakerRegistry
from app.resilience.deadline import Deadline
from app.routing.fallback import ProviderCaller, execute_chain
from app.routing.selector import select_chain


@dataclass
class GatewayResponse:
    request_id: str
    success: bool
    answer: str | None
    complexity: str
    confidence: float
    classifier_reason: str
    chosen_model: str | None
    chosen_model_label: str | None
    provider: str | None
    fallback_occurred: bool
    cache_hit: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    modeled_cost_usd: float
    attempts: list[dict] = field(default_factory=list)
    error: str | None = None


# Async callback that receives a finished response for logging/evaluation.
LogCallback = Callable[[GatewayResponse, str], Awaitable[None]]
# Schedules a coroutine to run in the background (with backpressure in prod).
Scheduler = Callable[[Awaitable[None]], None]


def _default_scheduler(coro: Awaitable[None]) -> None:
    asyncio.ensure_future(coro)


class Orchestrator:
    def __init__(
        self,
        *,
        classifier: Classifier,
        breakers: CircuitBreakerRegistry,
        cache: TTLCache,
        metrics: MetricsStore,
        call_provider: ProviderCaller,
        semaphore: asyncio.Semaphore | None = None,
        deadline_seconds: float = 25.0,
        per_call_timeout: float = 20.0,
        retry_attempts: int = 2,
        evaluator_sample_rate: float = 0.1,
        scheduler: Scheduler = _default_scheduler,
        db_logger: LogCallback | None = None,
        evaluator: LogCallback | None = None,
        rng: Random | None = None,
    ) -> None:
        self.classifier = classifier
        self.breakers = breakers
        self.cache = cache
        self.metrics = metrics
        self.call_provider = call_provider
        self.semaphore = semaphore
        self.deadline_seconds = deadline_seconds
        self.per_call_timeout = per_call_timeout
        self.retry_attempts = retry_attempts
        self.evaluator_sample_rate = evaluator_sample_rate
        self.scheduler = scheduler
        self.db_logger = db_logger
        self.evaluator = evaluator
        self._rng = rng or Random()

    async def handle(self, query: str) -> GatewayResponse:
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        key = make_key(query)

        # 1. Cache hit -> instant return.
        cached: GatewayResponse | None = self.cache.get(key)
        if cached is not None:
            resp = _as_cache_hit(cached, request_id, started)
            self._record(resp)
            return resp

        # 2. Classify.
        classification = await self.classifier.classify(query)

        # 3. Select chain.
        chain = select_chain(classification.label)

        # 4. Execute with global deadline.
        deadline = Deadline(self.deadline_seconds)
        outcome = await execute_chain(
            chain,
            query,
            deadline=deadline,
            breakers=self.breakers,
            call_provider=self.call_provider,
            per_call_timeout=self.per_call_timeout,
            retry_attempts=self.retry_attempts,
            semaphore=self.semaphore,
        )

        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        if outcome.success and outcome.result is not None:
            resp = self._success_response(
                request_id, classification, outcome, outcome.result, latency_ms
            )
            # Only cache successful answers.
            self.cache.set(key, resp)
        else:
            resp = GatewayResponse(
                request_id=request_id,
                success=False,
                answer=None,
                complexity=classification.label,
                confidence=classification.confidence,
                classifier_reason=classification.reason,
                chosen_model=None,
                chosen_model_label=None,
                provider=None,
                fallback_occurred=outcome.fallback_occurred,
                cache_hit=False,
                latency_ms=latency_ms,
                prompt_tokens=0,
                completion_tokens=0,
                modeled_cost_usd=0.0,
                attempts=[asdict(a) for a in outcome.attempts],
                error=outcome.error,
            )

        self._record(resp)
        self._schedule_background(resp, query)
        return resp

    # ── helpers ──────────────────────────────────────────────────
    def _success_response(
        self, request_id, classification, outcome, result: ProviderResult, latency_ms
    ) -> GatewayResponse:
        model = outcome.chosen_model
        cost = modeled_cost_usd(model, result.prompt_tokens, result.completion_tokens)
        return GatewayResponse(
            request_id=request_id,
            success=True,
            answer=result.text,
            complexity=classification.label,
            confidence=classification.confidence,
            classifier_reason=classification.reason,
            chosen_model=model.key,
            chosen_model_label=model.label,
            provider=model.provider,
            fallback_occurred=outcome.fallback_occurred,
            cache_hit=False,
            latency_ms=latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            modeled_cost_usd=cost,
            attempts=[asdict(a) for a in outcome.attempts],
            error=None,
        )

    def _record(self, resp: GatewayResponse) -> None:
        self.metrics.record(
            new_sample(
                complexity=resp.complexity,
                chosen_model=resp.chosen_model,
                success=resp.success,
                fallback_occurred=resp.fallback_occurred,
                cache_hit=resp.cache_hit,
                latency_ms=resp.latency_ms,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                cost_usd=resp.modeled_cost_usd,
                attempts=len(resp.attempts),
            )
        )

    def _schedule_background(self, resp: GatewayResponse, query: str) -> None:
        if self.db_logger is not None:
            self.scheduler(self.db_logger(resp, query))
        # Evaluator runs on a sample only -- never on every request.
        if (
            self.evaluator is not None
            and resp.success
            and self._rng.random() < self.evaluator_sample_rate
        ):
            self.scheduler(self.evaluator(resp, query))


def _as_cache_hit(cached: GatewayResponse, request_id: str, started: float) -> GatewayResponse:
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return GatewayResponse(
        request_id=request_id,
        success=cached.success,
        answer=cached.answer,
        complexity=cached.complexity,
        confidence=cached.confidence,
        classifier_reason=cached.classifier_reason,
        chosen_model=cached.chosen_model,
        chosen_model_label=cached.chosen_model_label,
        provider=cached.provider,
        fallback_occurred=cached.fallback_occurred,
        cache_hit=True,
        latency_ms=latency_ms,
        prompt_tokens=cached.prompt_tokens,
        completion_tokens=cached.completion_tokens,
        modeled_cost_usd=0.0,  # a cache hit incurs no modeled cost
        attempts=cached.attempts,
        error=cached.error,
    )
