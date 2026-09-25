"""Language model streaming boundary."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Privacy(StrEnum):
    LOCAL_ONLY = "local_only"
    CLOUD_ALLOWED = "cloud_allowed"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    generation_id: str
    privacy: Privacy = Privacy.LOCAL_ONLY
    max_output_tokens: int = 512
    tools: tuple[ToolDefinition, ...] = ()

    def __post_init__(self) -> None:
        if not self.prompt:
            raise ValueError("model prompt cannot be empty")
        if not 1 <= self.max_output_tokens <= 32_768:
            raise ValueError("max_output_tokens must be between 1 and 32768")


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ModelChunk:
    kind: str
    text: str = ""
    usage_tokens: int = 0
    tool_call: ToolCall | None = None


class CancellationToken:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


class LanguageModel(Protocol):
    name: str

    def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]: ...
