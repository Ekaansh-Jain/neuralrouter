"""Typed application settings loaded from environment variables.

Uses pydantic-settings so a missing/invalid value fails loudly at startup
instead of surfacing as a confusing error mid-request.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Provider mode: "mock" (no keys, simulated) or "live" (real APIs).
    provider_mode: str = "mock"

    groq_api_key: str = ""
    openrouter_api_key: str = ""

    supabase_url: str = ""
    supabase_key: str = ""

    # Pipeline tuning
    request_deadline_seconds: float = 25.0
    max_concurrent_provider_calls: int = 5
    cache_ttl_seconds: int = 3600
    evaluator_sample_rate: float = 0.1
    circuit_failure_threshold: int = 3
    circuit_reset_seconds: float = 30.0

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()
