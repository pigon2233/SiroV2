"""Bounded, privacy-aware provider attempts before any generation emission."""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from uuid import uuid4

import httpx

from siro.adapters.models.openai_compatible import _TOOL_INTENT_EMITTED, OpenAICompatibleAdapter
from siro.ports.models import CancellationToken, LanguageModel, ModelChunk, ModelRequest, Privacy


def _retryable(error: Exception) -> bool:
    if _TOOL_INTENT_EMITTED in getattr(error, "__notes__", ()):
        return False
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {429, 502, 503, 504}
    return isinstance(error, (ConnectionError, TimeoutError, httpx.TransportError))


def _rate_limit_delay(
    error: httpx.HTTPStatusError,
    *,
    fallback: float,
    maximum: float,
    clock: Callable[[], datetime],
) -> float | None:
    # Groq documents this header as requests *per day*, not the minute limit.
    if error.request.url.host == "api.groq.com":
        remaining = error.response.headers.get("x-ratelimit-remaining-requests")
        try:
            if remaining is not None and int(remaining) <= 0:
                return None
        except ValueError:
            pass
    value = error.response.headers.get("retry-after", "").strip()
    delay = fallback
    try:
        seconds = float(value)
        if math.isfinite(seconds) and seconds >= 0:
            delay = seconds
    except ValueError:
        try:
            deadline = parsedate_to_datetime(value)
            now = clock()
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            if now.tzinfo is None:
                now = now.replace(tzinfo=UTC)
            delay = max(0.0, (deadline - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    return delay if delay <= maximum else None


class FailoverModel:
    def __init__(
        self,
        models: Sequence[LanguageModel],
        *,
        backoff_seconds: float = 0.25,
        cloud_indices: frozenset[int] = frozenset(),
        cloud_request_budget: int = 0,
        rate_limit_max_wait_seconds: float | None = None,
        clock: Callable[[], datetime] | None = None,
        on_retry: Callable[[ModelRequest, float], Awaitable[None]] | None = None,
    ) -> None:
        if not models:
            raise ValueError("at least one model is required")
        if not 0 <= backoff_seconds <= 5 or cloud_request_budget not in {0, 1}:
            raise ValueError("invalid bounded retry budget")
        if any(i < 0 or i >= len(models) for i in cloud_indices):
            raise ValueError("invalid cloud model index")
        if rate_limit_max_wait_seconds is not None and (
            not math.isfinite(rate_limit_max_wait_seconds)
            or not 0 <= rate_limit_max_wait_seconds <= 60
        ):
            raise ValueError("rate limit wait must be between zero and sixty seconds")
        self._models = tuple(models)
        # Preserve selected-provider provenance for existing journal consumers.
        self.name = self._models[0].name
        self._backoff = backoff_seconds
        self._cloud_indices = cloud_indices | frozenset(
            i for i, model in enumerate(models) if isinstance(model, OpenAICompatibleAdapter)
        )
        self._cloud_budget = cloud_request_budget
        self._rate_limit_max_wait = rate_limit_max_wait_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._on_retry = on_retry

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        index = 0
        for attempt in range(2):
            if cancellation.cancelled:
                return
            if index in self._cloud_indices:
                if request.privacy is not Privacy.CLOUD_ALLOWED:
                    raise PermissionError("cloud egress requires cloud_allowed privacy")
                if attempt and self._cloud_budget == 0:
                    raise PermissionError("additional cloud attempt has no request budget")
            provider_request = (
                request if attempt == 0 else replace(request, generation_id=str(uuid4()))
            )
            emitted = False
            try:
                async for chunk in self._models[index].stream(provider_request, cancellation):
                    if cancellation.cancelled:
                        return
                    if (chunk.kind == "text" and chunk.text) or chunk.kind in {
                        "tool_request",
                        "finished",
                    }:
                        emitted = True
                    yield chunk
                return
            except Exception as error:
                if emitted or cancellation.cancelled or attempt == 1 or not _retryable(error):
                    raise
                rate_limited = (
                    self._rate_limit_max_wait is not None
                    and isinstance(error, httpx.HTTPStatusError)
                    and error.response.status_code == 429
                )
                next_index = index if rate_limited else min(1, len(self._models) - 1)
                # Preserve the original provider failure when policy rules out another request.
                if next_index in self._cloud_indices and (
                    request.privacy is not Privacy.CLOUD_ALLOWED or self._cloud_budget == 0
                ):
                    raise
                delay = self._backoff
                if rate_limited:
                    assert isinstance(error, httpx.HTTPStatusError)
                    assert self._rate_limit_max_wait is not None
                    selected_delay = _rate_limit_delay(
                        error,
                        fallback=self._backoff,
                        maximum=self._rate_limit_max_wait,
                        clock=self._clock,
                    )
                    if selected_delay is None:
                        raise
                    delay = selected_delay
                    if self._on_retry is not None:
                        notification = asyncio.ensure_future(self._on_retry(request, delay))
                        cancelled = asyncio.create_task(cancellation.wait())
                        try:
                            await asyncio.wait(
                                (notification, cancelled), return_when=asyncio.FIRST_COMPLETED
                            )
                            if cancellation.cancelled:
                                return
                            await notification
                        finally:
                            notification.cancel()
                            cancelled.cancel()
                            await asyncio.gather(notification, cancelled, return_exceptions=True)
                    if cancellation.cancelled:
                        return
                try:
                    await asyncio.wait_for(cancellation.wait(), timeout=delay)
                    return
                except TimeoutError:
                    index = next_index
