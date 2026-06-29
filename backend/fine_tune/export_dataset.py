"""Turn logged traffic into a labeled training set for the classifier.

Critical rule: rows where a FALLBACK occurred (or that were cache hits) are
EXCLUDED. A weak answer produced because the primary model was down must not be
treated as a routing label, or the dataset gets poisoned. For rows the evaluator
judged INCORRECT, we relabel using the evaluator's suggested complexity.

Pure-Python (stdlib only). `main()` pulls from Supabase if configured; the core
`build_dataset` function is easily unit-tested with plain dicts.
"""

from __future__ import annotations

import json
from collections.abc import Iterable


def build_dataset(
    requests: Iterable[dict],
    verdicts_by_id: dict[str, dict],
) -> list[dict]:
    """Return a list of {"text", "label"} training examples."""
    dataset: list[dict] = []
    for row in requests:
        if row.get("cache_hit") or row.get("fallback_occurred"):
            continue
        if not row.get("success"):
            continue

        label = row["complexity"]
        verdict = verdicts_by_id.get(row["request_id"])
        if verdict and not verdict.get("routing_correct") and verdict.get("suggested_complexity"):
            # The judge disagreed -> learn from its corrected label.
            label = verdict["suggested_complexity"]

        dataset.append({"text": row["query"], "label": label})
    return dataset


def write_jsonl(rows: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def main() -> None:  # pragma: no cover - requires Supabase + network
    import os

    from supabase import create_client

    url, key = os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"]
    client = create_client(url, key)
    requests = client.table("requests").select("*").execute().data
    verdicts = client.table("verdicts").select("*").execute().data
    verdicts_by_id = {v["request_id"]: v for v in verdicts}

    dataset = build_dataset(requests, verdicts_by_id)
    write_jsonl(dataset, "classifier_dataset.jsonl")
    print(f"wrote {len(dataset)} examples")


if __name__ == "__main__":  # pragma: no cover
    main()
