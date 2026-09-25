"""Deterministic offline streaming model."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from siro.ports.models import CancellationToken, ModelChunk, ModelRequest


class MockModel:
    name = "mock"

    def __init__(
        self,
        chunks: Sequence[str] = ("我在這裡。",),
        *,
        delay: float = 0,
        ignore_cancellation: bool = False,
    ) -> None:
        self._chunks = tuple(chunks)
        self._delay = delay
        self._ignore_cancellation = ignore_cancellation

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        del request
        for text in self._chunks:
            if self._delay:
                await asyncio.sleep(self._delay)
            if cancellation.cancelled and not self._ignore_cancellation:
                return
            yield ModelChunk("text", text)
        yield ModelChunk("finished")


class OfflineDemoModel:
    """Network-free demo behavior; clearly identified as deterministic."""

    name = "offline-demo"

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if cancellation.cancelled:
            return
        if "NO_SOURCE" in request.prompt:
            text = "我沒有可追溯的記憶來源, 所以目前不知道。"
        else:
            text = "我記得這段有來源的共同經歷。"
        yield ModelChunk("text", text)
        yield ModelChunk("finished")
