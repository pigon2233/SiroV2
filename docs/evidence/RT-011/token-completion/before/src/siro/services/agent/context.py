"""Hard logical request size limit; never trim goals or pending tool pairs."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from siro.ports.models import CancellationToken, LanguageModel, ModelChunk, ModelRequest


class ContextBudgetExceeded(ValueError):
    """Request is too large for the configured logical UTF-8 byte budget."""


def request_size_bytes(request: ModelRequest) -> int:
    """Measure complete logical request JSON, without estimating provider tokens."""
    return sum(
        len(part.encode("utf-8"))
        for part in json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).iterencode(
            asdict(request)
        )
    )


class ContextBudgetModel:
    def __init__(self, model: LanguageModel, *, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError("context max_bytes must be positive")
        self.name = model.name
        self._model = model
        self._max_bytes = max_bytes

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if cancellation.cancelled:
            return
        size = request_size_bytes(request)
        if size > self._max_bytes:
            raise ContextBudgetExceeded(f"logical request bytes {size} exceed {self._max_bytes}")
        async for chunk in self._model.stream(request, cancellation):
            yield chunk
