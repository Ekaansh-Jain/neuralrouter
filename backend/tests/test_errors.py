from _helpers import ok_result, run, spec

from app.providers.errors import ErrorCategory, ProviderError, classify_status
from app.resilience.circuit_breaker import CircuitBreakerRegistry
from app.resilience.deadline import Deadline
from app.routing.fallback import execute_chain


def test_status_mapping():
    assert classify_status(429) == ErrorCategory.RATE_LIMITED
    assert classify_status(404) == ErrorCategory.PROVIDER_DOWN  # missing model -> fall back
    assert classify_status(401) == ErrorCategory.INVALID_REQUEST  # auth -> stop
    assert classify_status(422) == ErrorCategory.INVALID_REQUEST
    assert classify_status(503) == ErrorCategory.PROVIDER_DOWN


def test_404_category_allows_fallback_but_401_does_not():
    assert classify_status(404) and ProviderError(
        classify_status(404), "gone", provider="groq"
    ).should_try_next_model is True
    assert ProviderError(
        classify_status(401), "bad key", provider="groq"
    ).should_try_next_model is False


def test_decommissioned_model_404_falls_back():
    # Simulates a stale model id (404) as the primary; the chain should recover.
    chain = [spec("groq/old", "groq"), spec("openrouter/c", "openrouter")]

    async def caller(model, prompt, timeout):
        if model.key == "groq/old":
            raise ProviderError(classify_status(404), "model not found",
                                provider="groq", status_code=404)
        return ok_result(model.provider, model.model_id)

    async def scenario():
        out = await execute_chain(
            chain, "hi", deadline=Deadline(10.0),
            breakers=CircuitBreakerRegistry(clock=lambda: 0.0),
            call_provider=caller, retry_attempts=1,
        )
        assert out.success is True
        assert out.chosen_model.key == "openrouter/c"
        assert out.fallback_occurred is True

    run(scenario())
