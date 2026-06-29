"""Persistence layer with a pluggable backend.

Two backends behind one interface:
  - InMemoryBackend: default; zero setup, data resets on restart. Great for
    demos and local dev.
  - SupabaseBackend: used when SUPABASE_URL/KEY are set. The supabase-py client
    is SYNCHRONOUS, so every call is pushed to a worker thread with
    `asyncio.to_thread` -- otherwise it would block the event loop and defeat
    the whole point of doing DB writes in the background.

The repository is the ONLY place that talks to the database.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Protocol

from app.core.logging import get_logger
from app.db.schemas import RequestRow, VerdictRow

logger = get_logger("db")


class Backend(Protocol):
    async def insert_request(self, row: RequestRow) -> None: ...
    async def insert_verdict(self, row: VerdictRow) -> None: ...


class InMemoryBackend:
    def __init__(self, maxlen: int = 2000) -> None:
        self.requests: deque[dict] = deque(maxlen=maxlen)
        self.verdicts: deque[dict] = deque(maxlen=maxlen)

    async def insert_request(self, row: RequestRow) -> None:
        self.requests.append(row.to_dict())

    async def insert_verdict(self, row: VerdictRow) -> None:
        self.verdicts.append(row.to_dict())


class SupabaseBackend:
    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client  # lazy import; optional dependency

        self._client = create_client(url, key)

    async def insert_request(self, row: RequestRow) -> None:
        await asyncio.to_thread(
            lambda: self._client.table("requests").insert(row.to_dict()).execute()
        )

    async def insert_verdict(self, row: VerdictRow) -> None:
        await asyncio.to_thread(
            lambda: self._client.table("verdicts").insert(row.to_dict()).execute()
        )


class Repository:
    def __init__(self, backend: Backend) -> None:
        self._backend = backend

    async def log_request(self, row: RequestRow) -> None:
        try:
            await self._backend.insert_request(row)
        except Exception:  # never let a logging failure affect the request path
            logger.exception("failed to persist request row")

    async def log_verdict(self, row: VerdictRow) -> None:
        try:
            await self._backend.insert_verdict(row)
        except Exception:
            logger.exception("failed to persist verdict row")


def build_repository(use_supabase: bool, url: str, key: str) -> Repository:
    if use_supabase:
        logger.info("using Supabase backend")
        return Repository(SupabaseBackend(url, key))
    logger.info("using in-memory backend (data resets on restart)")
    return Repository(InMemoryBackend())
