"""Hard logical request size limit; never trim goals or pending tool pairs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict, replace
from typing import Protocol

from siro.ports.models import CancellationToken, LanguageModel, ModelChunk, ModelRequest


class ContextBudgetExceeded(ValueError):
    """Request is too large for the configured logical UTF-8 byte budget."""


class ContextBudgetUnavailable(ValueError):
    """Selected provider cannot be safely token-counted with available local assets."""


class TokenBudget(Protocol):
    def validate(self, request: ModelRequest) -> int: ...


class UnavailableTokenBudget:
    def validate(self, request: ModelRequest) -> int:
        raise ContextBudgetUnavailable("selected provider token policy is unavailable")


def request_size_bytes(request: ModelRequest) -> int:
    """Measure complete logical request JSON, without estimating provider tokens."""
    return sum(
        len(part.encode("utf-8"))
        for part in json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).iterencode(
            asdict(request)
        )
    )


class ContextBudgetModel:
    def __init__(
        self,
        model: LanguageModel,
        *,
        max_bytes: int | None,
        token_budget: TokenBudget | None = None,
        summary_enabled: bool = False,
        max_output_tokens: int | None = None,
    ) -> None:
        if max_bytes is not None and max_bytes < 1:
            raise ValueError("context max_bytes must be positive")
        if max_bytes is None and token_budget is None:
            raise ValueError("at least one context budget is required")
        if max_output_tokens is not None and (
            type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 32768
        ):
            raise ValueError("max_output_tokens must be an integer between 1 and 32768")
        self.name = model.name
        self._model = model
        self._max_bytes = max_bytes
        self._token_budget = token_budget
        self.summary_enabled = summary_enabled
        self.summarized_requests = 0
        self._max_output_tokens = max_output_tokens

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if cancellation.cancelled:
            return
        if self._max_output_tokens is not None:
            request = replace(request, max_output_tokens=self._max_output_tokens)
        try:
            await self._validate(request)
        except ContextBudgetExceeded:
            if not self.summary_enabled:
                raise
            from siro.services.agent.summary import summarize_completed

            compacted = replace(request, messages=summarize_completed(request.messages))
            if compacted == request:
                raise
            await self._validate(compacted)
            request = compacted
            self.summarized_requests += 1
        if cancellation.cancelled:
            return
        async for chunk in self._model.stream(request, cancellation):
            yield chunk

    async def _validate(self, request: ModelRequest) -> None:
        if self._max_bytes is not None:
            size = request_size_bytes(request)
            if size > self._max_bytes:
                raise ContextBudgetExceeded(
                    f"logical request bytes {size} exceed {self._max_bytes}"
                )
        if self._token_budget is not None:
            await asyncio.to_thread(self._token_budget.validate, request)
