from random import Random

from _helpers import run

from app.agents.classifier.heuristic import HeuristicClassifier
from app.cache.memory_cache import TTLCache
from app.observability.metrics import MetricsStore
from app.pipeline.orchestrator import Orchestrator
from app.providers.hub import ProviderHub
from app.providers.mock import MockProvider
from app.resilience.circuit_breaker import CircuitBreakerRegistry


def _build(scheduled, logged):
    hub = ProviderHub({
        "groq": MockProvider("groq", transient_rate=0.0, rate_limit_rate=0.0, rng=Random(0)),
        "openrouter": MockProvider("openrouter", transient_rate=0.0, rate_limit_rate=0.0,
                                   rng=Random(1)),
    })

    async def db_logger(resp, query):
        logged.append(resp.request_id)

    return Orchestrator(
        classifier=HeuristicClassifier(),
        breakers=CircuitBreakerRegistry(),
        cache=TTLCache(ttl_seconds=100),
        metrics=MetricsStore(),
        call_provider=hub.call,
        deadline_seconds=10.0,
        scheduler=lambda coro: scheduled.append(coro),
        db_logger=db_logger,
        evaluator=None,
    )


def test_end_to_end_success_and_cache():
    scheduled: list = []
    logged: list = []
    orch = _build(scheduled, logged)

    async def scenario():
        first = await orch.handle("What is the capital of France?")
        assert first.success is True
        assert first.answer is not None
        assert first.cache_hit is False
        assert first.chosen_model is not None

        # Identical query -> served from cache, no provider call.
        second = await orch.handle("What is the capital of France?")
        assert second.cache_hit is True
        assert second.answer == first.answer

        # Drain scheduled background work so no coroutine is left un-awaited.
        for coro in scheduled:
            await coro

    run(scenario())
    assert orch.metrics.summary()["total_requests"] == 2
    assert len(logged) >= 1
