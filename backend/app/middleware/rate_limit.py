"""Rate limiting via slowapi.

NOTE (documented limitation): slowapi's default store is in-process, so limits
are PER WORKER. With a single worker (our free-tier deployment) this is correct;
to enforce global limits across multiple workers you would back it with Redis.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
