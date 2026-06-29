"""Middleware that assigns a correlation id to every request.

Reuses an incoming `X-Request-ID` if present, otherwise generates one. The id is
put into a contextvar (so logs pick it up) and echoed back in the response
header for client-side correlation.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
