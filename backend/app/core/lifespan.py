"""Application lifespan: build shared resources once, tear them down cleanly.

Everything expensive or long-lived is created here and stored on `app.state`:
the shared httpx client, the provider hub, breaker registry, cache, metrics
store, repository, and the background runner. Request handlers pull what they
need from this container instead of constructing things per request.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from app.agents.classifier.heuristic import HeuristicClassifier
from app.agents.evaluator.judge import HeuristicEvaluator
from app.background.queue import BackgroundRunner
from app.cache.memory_cache import TTLCache
from app.config.settings import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.repository import build_repository
from app.db.schemas import RequestRow, VerdictRow
from app.observability.metrics import MetricsStore
from app.observability.tokens import TOKENIZER_BACKEND
from app.pipeline.orchestrator import GatewayResponse, Orchestrator
from app.providers.hub import build_hub
from app.resilience.circuit_breaker import CircuitBreakerRegistry

logger = get_logger("lifespan")


@dataclass
class AppContainer:
    settings: Settings
    http_client: Any
    breakers: CircuitBreakerRegistry
    cache: TTLCache
    metrics: MetricsStore
    background: BackgroundRunner
    orchestrator: Orchestrator


def _build_http_client(settings: Settings):
    """Create the single shared httpx client (live mode only)."""
    if settings.provider_mode != "live":
        return None
    import httpx  # lazy: keeps httpx out of import path in mock/test mode

    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    return httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(30.0, connect=5.0))


def build_container(settings: Settings) -> AppContainer:
    http_client = _build_http_client(settings)
    hub = build_hub(settings, http_client)
    breakers = CircuitBreakerRegistry(
        failure_threshold=settings.circuit_failure_threshold,
        reset_seconds=settings.circuit_reset_seconds,
    )
    cache = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
    metrics = MetricsStore()
    repository = build_repository(
        settings.use_supabase, settings.supabase_url, settings.supabase_key
    )
    background = BackgroundRunner(max_queue=200, workers=2)

    classifier = HeuristicClassifier()
    evaluator_impl = HeuristicEvaluator(classifier)
    semaphore = asyncio.Semaphore(settings.max_concurrent_provider_calls)

    async def db_logger(resp: GatewayResponse, query: str) -> None:
        await repository.log_request(RequestRow(
            request_id=resp.request_id, query=query, complexity=resp.complexity,
            confidence=resp.confidence, classifier_reason=resp.classifier_reason,
            chosen_model=resp.chosen_model, provider=resp.provider, success=resp.success,
            fallback_occurred=resp.fallback_occurred, cache_hit=resp.cache_hit,
            latency_ms=resp.latency_ms, prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            modeled_cost_usd=resp.modeled_cost_usd, attempts=resp.attempts,
            error=resp.error,
        ))

    async def evaluator_cb(resp: GatewayResponse, query: str) -> None:
        verdict = await evaluator_impl.evaluate(resp.complexity, query, resp.answer)
        await repository.log_verdict(VerdictRow(
            request_id=resp.request_id, routing_correct=verdict.routing_correct,
            suggested_complexity=verdict.suggested_complexity, score=verdict.score,
            reason=verdict.reason, used_fallback=resp.fallback_occurred,
        ))

    orchestrator = Orchestrator(
        classifier=classifier, breakers=breakers, cache=cache, metrics=metrics,
        call_provider=hub.call, semaphore=semaphore,
        deadline_seconds=settings.request_deadline_seconds,
        evaluator_sample_rate=settings.evaluator_sample_rate,
        scheduler=background.schedule, db_logger=db_logger, evaluator=evaluator_cb,
    )

    return AppContainer(
        settings=settings, http_client=http_client, breakers=breakers, cache=cache,
        metrics=metrics, background=background, orchestrator=orchestrator,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging()
    logger.info("starting NeuralRouter", extra={"data": {
        "provider_mode": settings.provider_mode, "tokenizer": TOKENIZER_BACKEND,
        "supabase": settings.use_supabase}})

    container = build_container(settings)
    container.background.start()
    app.state.container = container
    try:
        yield
    finally:
        await container.background.stop()
        if container.http_client is not None:
            await container.http_client.aclose()
        logger.info("NeuralRouter shut down")
