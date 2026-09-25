"""Generation-safe model failover before any text becomes visible."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
from uuid import uuid4

from siro.ports.models import CancellationToken, LanguageModel, ModelChunk, ModelRequest


class FailoverModel:
    name = "failover"

    def __init__(self, models: Sequence[LanguageModel]) -> None:
        if not models:
            raise ValueError("at least one model is required")
        self._models = tuple(models)

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        last_error: Exception | None = None
        for index, model in enumerate(self._models):
            emitted = False
            provider_request = request
            if index:
                provider_request = replace(request, generation_id=str(uuid4()))
            try:
                async for chunk in model.stream(provider_request, cancellation):
                    if chunk.kind == "text" and chunk.text:
                        emitted = True
                    yield chunk
                return
            except Exception as exception:
                if emitted or cancellation.cancelled:
                    raise
                last_error = exception
        if last_error is not None:
            raise last_error
