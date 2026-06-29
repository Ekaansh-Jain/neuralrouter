from _helpers import MutableClock

from app.resilience.deadline import Deadline


def test_remaining_and_expiry():
    clock = MutableClock()
    d = Deadline(10.0, clock=clock)
    assert d.remaining == 10.0
    assert d.expired is False
    clock.advance(7)
    assert d.remaining == 3.0
    clock.advance(5)
    assert d.remaining == 0.0
    assert d.expired is True


def test_slice_caps_to_remaining():
    clock = MutableClock()
    d = Deadline(10.0, clock=clock)
    assert d.slice_for_attempt(20.0) == 10.0  # capped by remaining budget
    clock.advance(8)
    assert d.slice_for_attempt(20.0) == 2.0
    assert d.slice_for_attempt(1.0) == 1.0    # capped by per-call cap
