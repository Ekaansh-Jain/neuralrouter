"""The main gateway endpoint: classify -> route -> answer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.schemas.requests import ChatRequest
from app.api.schemas.responses import ChatResponse
from app.core.deps import get_orchestrator
from app.middleware.rate_limit import limiter
from app.pipeline.orchestrator import Orchestrator

router = APIRouter(tags=["chat"])


@router.post("/v1/chat", response_model=ChatResponse)
@limiter.limit("60/minute")
async def chat(
    request: Request,  # required by slowapi to read the client address
    body: ChatRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    result = await orchestrator.handle(body.query)
    return ChatResponse.from_gateway(result)
