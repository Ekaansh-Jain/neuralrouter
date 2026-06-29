"""Bounded background task runner with backpressure.

FastAPI's built-in BackgroundTasks run with no limit: if requests arrive faster
than background work (DB writes, evaluator calls) drains, tasks pile up until
the process is OOM-killed on a small free-tier box.

This runner uses a BOUNDED queue drained by a fixed pool of workers. When the
queue is full it DROPS the task (and counts it) instead of growing without
limit. Dropping background evaluation under load is an acceptable, deliberate
degradation; crashing is not.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from app.core.logging import get_logger

logger = get_logger("background")


class BackgroundRunner:
    def __init__(self, max_queue: int = 200, workers: int = 2) -> None:
        self._queue: asyncio.Queue[Awaitable[None]] = asyncio.Queue(maxsize=max_queue)
        self._n_workers = workers
        self._tasks: list[asyncio.Task] = []
        self._dropped = 0
        self._running = False

    def start(self) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._worker(i)) for i in range(self._n_workers)
        ]

    async def stop(self) -> None:
        self._running = False
        # Wait for queued work to drain, then cancel idle workers.
        await self._queue.join()
        for task in self._tasks:
            task.cancel()

    def schedule(self, coro: Awaitable[None]) -> None:
        """Enqueue a coroutine; drop it (closing it cleanly) if the queue is full."""
        try:
            self._queue.put_nowait(coro)
        except asyncio.QueueFull:
            self._dropped += 1
            # Close the coroutine so Python doesn't warn about it never running.
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            logger.warning("background queue full; dropped task", extra={"data":
                            {"dropped_total": self._dropped}})

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    async def _worker(self, idx: int) -> None:
        while self._running or not self._queue.empty():
            try:
                coro = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            try:
                await coro
            except Exception:
                logger.exception("background task failed")
            finally:
                self._queue.task_done()
