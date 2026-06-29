"""Read-only metrics endpoints powering the dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.config.model_registry import FALLBACK_CHAINS, MODEL_POOL
from app.core.deps import get_container
from app.core.lifespan import AppContainer

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
async def summary(container: AppContainer = Depends(get_container)) -> dict:
    data = container.metrics.summary(container.breakers.snapshot())
    data["background_queue_depth"] = container.background.depth
    data["background_dropped"] = container.background.dropped
    return data


@router.get("/recent")
async def recent(
    limit: int = Query(50, ge=1, le=200),
    container: AppContainer = Depends(get_container),
) -> dict:
    return {"items": container.metrics.recent(limit)}


@router.get("/models")
async def models() -> dict:
    return {
        "pool": {
            key: {
                "label": m.label,
                "provider": m.provider,
                "prompt_usd_per_1m": m.prompt_usd_per_1m,
                "completion_usd_per_1m": m.completion_usd_per_1m,
            }
            for key, m in MODEL_POOL.items()
        },
        "chains": FALLBACK_CHAINS,
    }
