"""Liveness / readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_container
from app.core.lifespan import AppContainer
from app.observability.tokens import TOKENIZER_BACKEND

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(container: AppContainer = Depends(get_container)) -> dict:
    return {
        "status": "ok",
        "provider_mode": container.settings.provider_mode,
        "tokenizer": TOKENIZER_BACKEND,
        "use_supabase": container.settings.use_supabase,
    }


@router.get("/ready")
async def ready() -> dict:
    return {"ready": True}
