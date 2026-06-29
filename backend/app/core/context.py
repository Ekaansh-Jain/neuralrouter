"""Request correlation ID.

Stored in a contextvar so every log line emitted while handling a request can
include the same id WITHOUT threading it through every function signature.
"""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def set_request_id(value: str) -> None:
    request_id_var.set(value)


def get_request_id() -> str:
    return request_id_var.get()
