"""FastAPI dependency helpers to pull shared resources off app.state."""

from __future__ import annotations

from fastapi import Request

from app.core.lifespan import AppContainer
from app.pipeline.orchestrator import Orchestrator


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.container.orchestrator
