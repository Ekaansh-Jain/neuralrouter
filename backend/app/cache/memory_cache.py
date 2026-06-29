"""In-memory TTL cache for identical queries.

If the same prompt arrives within the TTL we return the stored answer instantly,
skipping classification, routing, and the provider call -- saving latency and
precious free-tier rate-limit budget.

Per-process (documented limitation): with one worker this is correct; to share
across workers you would swap this for Redis behind the same tiny interface.
Pure-Python and clock-injectable for deterministic tests.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def make_key(query: str, **options: Any) -> str:
    """Stable hash of the query plus any options that change the answer."""
    payload = query.strip().lower()
    if options:
        parts = sorted(f"{k}={v}" for k, v in options.items())
        payload = payload + "|" + "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(
        self,
        ttl_seconds: float = 3600,
        max_entries: int = 5000,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._store: OrderedDict[str, _Entry] = OrderedDict()

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._clock() >= entry.expires_at:
            # Expired: drop it.
            self._store.pop(key, None)
            return None
        # Mark as recently used.
        self._store.move_to_end(key)
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = _Entry(value=value, expires_at=self._clock() + self.ttl)
        self._store.move_to_end(key)
        # Evict oldest entries beyond capacity (LRU).
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def __len__(self) -> int:
        return len(self._store)
