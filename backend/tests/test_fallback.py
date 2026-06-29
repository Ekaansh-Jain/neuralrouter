from _helpers import MutableClock, ok_result, run, spec

from app.providers.errors import ErrorCategory, ProviderError
from app.resilience.circuit_breaker import CircuitBreakerRegistry
from app.resilience.deadline import Deadline
from app.routing.fallback import execute_chain


def _registry(clock=None):
    return CircuitBreakerRegistry(failure_threshold=3, reset_seconds=30,
                                  clock=clock or (lambda: 0.0))


def test_success_on_primary():
    chain = [spec("groq/a", "groq"), spec("groq/b", "groq")]

    async def caller(model, prompt, timeout):
        return ok_result(model.provider, model.model_id)

    async def scenario():
        out = await execute_chain(
            chain, "hi", deadline=Deadline(10.0), breakers=_registry(),
            call_provider=caller, retry_attempts=1,
        )
        assert out.success is True
        assert out.chosen_model.key == "groq/a"
        assert out.fallback_occurred is False

    run(scenario())


def test_falls_back_on_transient():
    chain = [spec("groq/a", "groq"), spec("openrouter/c", "openrouter")]

    async def caller(model, prompt, timeout):
        if model.key == "groq/a":
            raise ProviderError(ErrorCategory.TRANSIENT, "blip", provider="groq")
        return ok_result(model.provider, model.model_id)

    async def scenario():
        out = await execute_chain(
            chain, "hi", deadline=Deadline(10.0), breakers=_registry(),
            call_provider=caller, retry_attempts=1,
        )
        assert out.success is True
        assert out.chosen_model.key == "openrouter/c"
        assert out.fallback_occurred is True

    run(scenario())


def test_content_refusal_stops_chain():
    chain = [spec("groq/a", "groq"), spec("openrouter/c", "openrouter")]
    calls = []

    async def caller(model, prompt, timeout):
        calls.append(model.key)
        raise ProviderError(ErrorCategory.CONTENT_REFUSAL, "no", provider="groq")

    async def scenario():
        out = await execute_chain(
            chain, "hi", deadline=Deadline(10.0), breakers=_registry(),
            call_provider=caller, retry_attempts=1,
        )
        assert out.success is False
        assert calls == ["groq/a"]  # never tried the second model

    run(scenario())


def test_rate_limit_cools_whole_provider():
    chain = [spec("groq/a", "groq"), spec("groq/b", "groq"), spec("openrouter/c", "openrouter")]
    calls = []

    async def caller(model, prompt, timeout):
        calls.append(model.key)
        if model.provider == "groq":
            raise ProviderError(ErrorCategory.RATE_LIMITED, "429", provider="groq",
                                retry_after=5.0)
        return ok_result(model.provider, model.model_id)

    async def scenario():
        out = await execute_chain(
            chain, "hi", deadline=Deadline(10.0), breakers=_registry(),
            call_provider=caller, retry_attempts=1,
        )
        assert out.success is True
        assert out.chosen_model.key == "openrouter/c"
        # groq/b skipped because the provider was cooled down after groq/a's 429.
        assert "groq/b" not in calls

    run(scenario())


def test_global_deadline_prevents_stacking():
    chain = [spec("groq/a", "groq"), spec("groq/b", "groq"), spec("openrouter/c", "openrouter")]
    clock = MutableClock()
    calls = []

    async def caller(model, prompt, timeout):
        calls.append(model.key)
        clock.advance(0.6)  # each call "takes" 0.6s of the budget
        raise ProviderError(ErrorCategory.TRANSIENT, "blip", provider=model.provider)

    async def scenario():
        out = await execute_chain(
            chain, "hi",
            deadline=Deadline(1.0, clock=clock),
            breakers=_registry(clock=clock),
            call_provider=caller, retry_attempts=1,
        )
        assert out.success is False
        # Budget (1.0s) exhausted after two 0.6s calls -> third never attempted.
        assert calls == ["groq/a", "groq/b"]

    run(scenario())
