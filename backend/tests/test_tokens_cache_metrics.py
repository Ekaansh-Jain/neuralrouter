from _helpers import MutableClock

from app.cache.memory_cache import TTLCache, make_key
from app.config.model_registry import get_model
from app.observability.metrics import MetricsStore, new_sample
from app.observability.tokens import count_tokens, modeled_cost_usd


def test_count_tokens_positive():
    assert count_tokens("") == 0
    assert count_tokens("hello world this is a test") > 0


def test_modeled_cost_scales_with_tokens():
    model = get_model("groq/llama-3.3-70b")
    cheap = modeled_cost_usd(model, 100, 100)
    pricey = modeled_cost_usd(model, 10_000, 10_000)
    assert pricey > cheap > 0


def test_cache_set_get_and_expiry():
    clock = MutableClock()
    cache = TTLCache(ttl_seconds=10, clock=clock)
    k = make_key("Hello There")
    # Key is normalized (case/whitespace insensitive).
    assert k == make_key("  hello there ")
    cache.set(k, {"answer": 42})
    assert cache.get(k) == {"answer": 42}
    clock.advance(11)
    assert cache.get(k) is None  # expired


def test_cache_lru_eviction():
    cache = TTLCache(ttl_seconds=100, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # evicts "a"
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_metrics_summary_percentiles():
    store = MetricsStore()
    for ms in (100, 200, 300, 400, 500):
        store.record(new_sample(
            complexity="SIMPLE", chosen_model="groq/a", success=True,
            fallback_occurred=False, cache_hit=False, latency_ms=ms,
            prompt_tokens=1, completion_tokens=1, cost_usd=0.0, attempts=1,
        ))
    summary = store.summary()
    assert summary["total_requests"] == 5
    assert summary["success_rate"] == 1.0
    assert summary["latency_ms"]["p50"] == 300
    assert summary["usage_by_model"]["groq/a"] == 5
