import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fine_tune"))

from export_dataset import build_dataset  # noqa: E402


def test_excludes_fallback_and_cache_and_relabels():
    requests = [
        {"request_id": "1", "query": "good simple", "complexity": "SIMPLE",
         "success": True, "fallback_occurred": False, "cache_hit": False},
        {"request_id": "2", "query": "fallback case", "complexity": "COMPLEX",
         "success": True, "fallback_occurred": True, "cache_hit": False},
        {"request_id": "3", "query": "cache case", "complexity": "SIMPLE",
         "success": True, "fallback_occurred": False, "cache_hit": True},
        {"request_id": "4", "query": "misrouted", "complexity": "SIMPLE",
         "success": True, "fallback_occurred": False, "cache_hit": False},
    ]
    verdicts = {
        "4": {"routing_correct": False, "suggested_complexity": "COMPLEX"},
    }
    ds = build_dataset(requests, verdicts)
    texts = {d["text"]: d["label"] for d in ds}

    assert "fallback case" not in texts   # excluded (fallback poisons labels)
    assert "cache case" not in texts      # excluded (cache hit)
    assert texts["good simple"] == "SIMPLE"
    assert texts["misrouted"] == "COMPLEX"  # relabeled by the judge's suggestion
