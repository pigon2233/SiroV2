"""Language model streaming boundary."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol


class Privacy(StrEnum):
    LOCAL_ONLY = "local_only"
    CLOUD_ALLOWED = "cloud_allowed"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("tool messages require tool_call_id")
        if self.tool_calls and self.role != "assistant":
            raise ValueError("only assistant messages can carry tool calls")
        if self.role != "tool" and self.tool_call_id is not None:
            raise ValueError("tool_call_id is only valid on tool messages")


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    generation_id: str
    privacy: Privacy = Privacy.LOCAL_ONLY
    max_output_tokens: int = 512
    tools: tuple[ToolDefinition, ...] = ()
    messages: tuple[ModelMessage, ...] = ()

    def __post_init__(self) -> None:
        if not self.prompt and not self.messages:
            raise ValueError("model request requires a prompt or messages")
        if not 1 <= self.max_output_tokens <= 32_768:
            raise ValueError("max_output_tokens must be between 1 and 32768")


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
