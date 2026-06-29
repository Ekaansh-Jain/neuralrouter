from _helpers import MutableClock, run

from app.resilience.circuit_breaker import CircuitBreaker, CircuitState


def test_opens_after_threshold_and_rejects():
    async def scenario():
        cb = CircuitBreaker("m", failure_threshold=3, reset_seconds=30)
        assert await cb.allow() is True
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # While open, calls are rejected immediately.
        assert await cb.allow() is False

    run(scenario())


def test_half_open_after_reset_then_closes_on_success():
    async def scenario():
        clock = MutableClock()
        cb = CircuitBreaker("m", failure_threshold=2, reset_seconds=10, clock=clock)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert await cb.allow() is False  # still cooling

        clock.advance(11)
        assert await cb.allow() is True  # admitted as the probe
        assert cb.state == CircuitState.HALF_OPEN
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    run(scenario())


def test_half_open_admits_only_one_probe():
    async def scenario():
        clock = MutableClock()
        cb = CircuitBreaker("m", failure_threshold=1, reset_seconds=5, clock=clock)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        clock.advance(6)
        # Two near-simultaneous attempts: exactly one becomes the probe.
        first = await cb.allow()
        second = await cb.allow()
        assert (first, second) == (True, False)

    run(scenario())


def test_failed_probe_reopens():
    async def scenario():
        clock = MutableClock()
        cb = CircuitBreaker("m", failure_threshold=1, reset_seconds=5, clock=clock)
        await cb.record_failure()
        clock.advance(6)
        assert await cb.allow() is True
        await cb.record_failure()  # probe failed
        assert cb.state == CircuitState.OPEN

    run(scenario())
