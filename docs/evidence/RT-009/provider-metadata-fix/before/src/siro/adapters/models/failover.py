"""Bounded, privacy-aware provider attempts before any generation emission."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
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


class FailoverModel:
    name = "failover"

    def __init__(
        self,
        models: Sequence[LanguageModel],
        *,
        backoff_seconds: float = 0.25,
        cloud_indices: frozenset[int] = frozenset(),
        cloud_request_budget: int = 0,
    ) -> None:
        if not models:
            raise ValueError("at least one model is required")
        if not 0 <= backoff_seconds <= 5 or cloud_request_budget not in {0, 1}:
            raise ValueError("invalid bounded retry budget")
        if any(i < 0 or i >= len(models) for i in cloud_indices):
            raise ValueError("invalid cloud model index")
        self._models = tuple(models)
        self._backoff = backoff_seconds
        self._cloud_indices = cloud_indices | frozenset(
            i for i, model in enumerate(models) if isinstance(model, OpenAICompatibleAdapter)
        )
        self._cloud_budget = cloud_request_budget

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        for attempt in range(2):
            if cancellation.cancelled:
                return
            index = min(attempt, len(self._models) - 1)
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
                next_index = min(1, len(self._models) - 1)
                # Preserve the original provider failure when policy rules out another request.
                if next_index in self._cloud_indices and (
                    request.privacy is not Privacy.CLOUD_ALLOWED or self._cloud_budget == 0
                ):
                    raise
                try:
                    await asyncio.wait_for(cancellation.wait(), timeout=self._backoff)
                    return
                except TimeoutError:
                    pass
