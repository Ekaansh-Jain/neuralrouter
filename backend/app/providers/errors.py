"""Provider error taxonomy.

Raw HTTP failures are messy and inconsistent across providers. Every provider
wrapper normalizes its failures into a `ProviderError` carrying an
`ErrorCategory`. Downstream layers (retry, circuit breaker, fallback) then make
*correct* decisions based on the category instead of guessing from status codes:

    TRANSIENT       -> a blip (network hiccup, 5xx). Retry same model, then fall back.
    PROVIDER_DOWN   -> repeated/structural failure. Counts toward the circuit breaker.
    RATE_LIMITED    -> 429. Do NOT hammer; cool the whole provider down and skip it.
    CONTENT_REFUSAL -> model refused on policy grounds. Falling back won't help; stop.
    INVALID_REQUEST -> our fault (bad params/auth). Not retryable; stop.
    UNKNOWN         -> unclassified; treated conservatively as transient-once.

This module is pure-Python (stdlib only) so it can be unit-tested offline.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    TRANSIENT = "TRANSIENT"
    PROVIDER_DOWN = "PROVIDER_DOWN"
    RATE_LIMITED = "RATE_LIMITED"
    CONTENT_REFUSAL = "CONTENT_REFUSAL"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN = "UNKNOWN"


class ProviderError(Exception):
    """Normalized error raised by every provider wrapper."""

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        *,
        provider: str,
        model_key: str | None = None,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.provider = provider
        self.model_key = model_key
        self.status_code = status_code
        self.retry_after = retry_after

    @property
    def is_retryable(self) -> bool:
        """Whether retrying the SAME model could plausibly help."""
        return self.category in (ErrorCategory.TRANSIENT, ErrorCategory.UNKNOWN)

    @property
    def should_try_next_model(self) -> bool:
        """Whether falling back to a DIFFERENT model could help."""
        # A policy refusal or a bad request will fail the same way everywhere.
        return self.category not in (
            ErrorCategory.CONTENT_REFUSAL,
            ErrorCategory.INVALID_REQUEST,
        )

    @property
    def trips_breaker(self) -> bool:
        """Whether this failure should count toward opening the circuit."""
        return self.category in (ErrorCategory.TRANSIENT, ErrorCategory.PROVIDER_DOWN)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"ProviderError(category={self.category.value}, provider={self.provider!r}, "
            f"model={self.model_key!r}, status={self.status_code})"
        )


def classify_status(status_code: int) -> ErrorCategory:
    """Map an HTTP status code to an error category."""
    if status_code == 429:
        return ErrorCategory.RATE_LIMITED
    # 404 = model/endpoint not found (e.g. a decommissioned model id). A
    # *different* model in the chain may still work, so fall back rather than
    # stop. Treated as provider-down so a permanently-gone model trips its
    # breaker and gets skipped on later requests.
    if status_code == 404:
        return ErrorCategory.PROVIDER_DOWN
    # 400/401/403/422 = malformed request or auth. These fail identically on
    # every model, so stop the chain.
    if status_code in (400, 401, 403, 422):
        return ErrorCategory.INVALID_REQUEST
    if status_code >= 500:
        return ErrorCategory.PROVIDER_DOWN
    return ErrorCategory.UNKNOWN
