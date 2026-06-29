"""Shared OpenAI-compatible provider implementation.

Groq and OpenRouter both expose an OpenAI-style `/chat/completions` endpoint, so
they share one implementation differing only in base URL, auth, and headers.

Every failure is normalized into a `ProviderError` with the right category so
the resilience layer can react correctly. Uses a SHARED httpx.AsyncClient passed
in from the app lifespan (never creates a client per request).
"""

from __future__ import annotations

import httpx

from app.providers.base import ProviderResult
from app.providers.errors import ErrorCategory, ProviderError, classify_status


class OpenAICompatProvider:
    def __init__(
        self,
        name: str,
        *,
        base_url: str,
        api_key: str,
        client: httpx.AsyncClient,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = client
        self.extra_headers = extra_headers or {}

    async def complete(self, model_id: str, prompt: str, *, timeout: float) -> ProviderResult:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        try:
            resp = await self.client.post(url, json=payload, headers=headers, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                ErrorCategory.TRANSIENT, "request timed out", provider=self.name
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                ErrorCategory.TRANSIENT, f"network error: {exc}", provider=self.name
            ) from exc

        if resp.status_code != 200:
            retry_after = _parse_retry_after(resp.headers.get("retry-after"))
            raise ProviderError(
                classify_status(resp.status_code),
                f"{self.name} returned HTTP {resp.status_code}: {resp.text[:200]}",
                provider=self.name,
                status_code=resp.status_code,
                retry_after=retry_after,
            )

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        finish_reason = choice.get("finish_reason")
        if finish_reason == "content_filter":
            raise ProviderError(
                ErrorCategory.CONTENT_REFUSAL,
                "model refused on content-policy grounds",
                provider=self.name,
                model_key=model_id,
            )

        text = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage") or {}
        return ProviderResult(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            provider=self.name,
            model_id=model_id,
        )


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
