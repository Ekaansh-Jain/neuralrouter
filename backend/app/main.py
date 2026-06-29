"""FastAPI application factory.

Assembles middleware, routes, and the lifespan-managed resource container.
Run locally with:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import chat, health, metrics
from app.config.settings import get_settings
from app.core.lifespan import lifespan
from app.middleware.rate_limit import limiter
from app.middleware.request_id import RequestIDMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="NeuralRouter",
        description="An intelligent LLM routing gateway with fallback, "
                    "circuit breaking, and live observability.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Rate limiting (slowapi).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # CORS for the dashboard.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Correlation IDs (added last so it runs first on the way in).
    app.add_middleware(RequestIDMiddleware)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(metrics.router)
    return app


app = create_app()
