from _helpers import run

from app.agents.classifier.heuristic import HeuristicClassifier
from app.config.model_registry import COMPLEX, SIMPLE


def test_simple_lookup_query():
    c = HeuristicClassifier()
    result = run(c.classify("What is the capital of France?"))
    assert result.label == SIMPLE
    assert 0.5 <= result.confidence <= 0.95


def test_complex_reasoning_query():
    c = HeuristicClassifier()
    q = (
        "Design a fault-tolerant async pipeline and explain the trade-offs. "
        "Why would you optimize the circuit breaker this way? Compare two "
        "approaches step by step and analyze the algorithmic complexity."
    )
    result = run(c.classify(q))
    assert result.label == COMPLEX


def test_code_query_is_not_simple():
    c = HeuristicClassifier()
    q = "Here is a traceback ```def f(): return 1/0``` why does this error?"
    result = run(c.classify(q))
    assert result.label in ("MODERATE", "COMPLEX")
