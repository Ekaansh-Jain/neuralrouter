"""Public API request models (the input contract)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000,
                       description="The user prompt to route and answer.")
