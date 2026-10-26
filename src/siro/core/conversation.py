"""Single-foreground-turn conversation state machine."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from siro.ports.models import (
    CancellationToken,
    LanguageModel,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)


class TurnState(StrEnum):
    RESPONDING = "responding"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TurnResult:
    turn_id: str
    generation_id: str
    state: TurnState
    text: str
    error: str | None = None
    trace_id: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ConversationSignal:
    kind: str
    trace_id: str
    turn_id: str
    generation_id: str
    index: int | None = None
    text: str = ""
    state: TurnState | None = None


class ConversationRepository(Protocol):
    async def start_turn(
        self, session_id: str, identity_id: str, turn_id: str, generation_id: str, user_text: str
    ) -> None: ...

    async def finish_turn(self, result: TurnResult) -> None: ...


DeltaHandler = Callable[[str], Awaitable[None]]
SignalHandler = Callable[[ConversationSignal], Awaitable[None]]


async def _ignore_signal(_signal: ConversationSignal) -> None:
    return None


@dataclass(slots=True)
class _ActiveTurn:
    generation_id: str
    token: CancellationToken


class ConversationEngine:
    def __init__(
        self,
        model: LanguageModel,
        repository: ConversationRepository,
        *,
        timeout_seconds: float = 120,
        on_signal: SignalHandler = _ignore_signal,
        max_output_tokens: int = 512,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._repository = repository
        self._timeout = timeout_seconds
        self._on_signal = on_signal
        self._active: dict[str, _ActiveTurn] = {}
        self._lock = asyncio.Lock()

    async def respond(
        self,
        session_id: str,
        identity_id: str,
        prompt: str,
        *,
        privacy: Privacy = Privacy.LOCAL_ONLY,
        on_delta: DeltaHandler | None = None,
        tools: tuple[ToolDefinition, ...] = (),
        messages: tuple[ModelMessage, ...] = (),
        on_before_request: Callable[[], Awaitable[None]] | None = None,
    ) -> TurnResult:
        turn_id, generation_id, trace_id = str(uuid4()), str(uuid4()), str(uuid4())
        token = CancellationToken()
        async with self._lock:
            previous = self._active.get(session_id)
            if previous is not None:
                previous.token.cancel()
            self._active[session_id] = _ActiveTurn(generation_id, token)
        await self._repository.start_turn(session_id, identity_id, turn_id, generation_id, prompt)
        await self._on_signal(ConversationSignal("started", trace_id, turn_id, generation_id))
        pieces: list[str] = []
        tool_calls: list[ToolCall] = []
        state = TurnState.COMPLETED
        error: str | None = None
        try:
            async with asyncio.timeout(self._timeout):
                request = ModelRequest(
                    prompt,
                    generation_id,
                    privacy,
                    max_output_tokens=self._max_output_tokens,
                    tools=tools,
                    messages=messages,
                )
                if on_before_request is not None:
                    await on_before_request()
                if token.cancelled:
                    state = TurnState.CANCELLED
                else:
                    async for chunk in self._model.stream(request, token):
                        if token.cancelled or not await self._is_current(session_id, generation_id):
                            state = TurnState.CANCELLED
                            break
                        if chunk.kind == "text" and chunk.text:
                            pieces.append(chunk.text)
                            await self._on_signal(
                                ConversationSignal(
                                    "text_delta",
                                    trace_id,
                                    turn_id,
                                    generation_id,
                                    index=len(pieces) - 1,
                                    text=chunk.text,
                                )
                            )
                            if on_delta is not None:
                                await on_delta(chunk.text)
                        elif chunk.kind == "tool_request" and chunk.tool_call is not None:
                            tool_calls.append(chunk.tool_call)
        except TimeoutError:
            token.cancel()
            state, error = TurnState.FAILED, "timeout"
        except Exception as exception:  # provider boundary
            state, error = TurnState.FAILED, type(exception).__name__
        if token.cancelled and state is TurnState.COMPLETED:
            state = TurnState.CANCELLED
        result = TurnResult(
            turn_id,
            generation_id,
            state,
            "".join(pieces),
            error,
            trace_id,
            tuple(tool_calls),
        )
        await self._repository.finish_turn(result)
        await self._on_signal(
            ConversationSignal("terminal", trace_id, turn_id, generation_id, state=state)
        )
        async with self._lock:
            active = self._active.get(session_id)
            if active is not None and active.generation_id == generation_id:
                self._active.pop(session_id)
        return result

    async def cancel(self, session_id: str) -> bool:
        async with self._lock:
            active = self._active.get(session_id)
            if active is None:
                return False
            active.token.cancel()
            return True

    async def _is_current(self, session_id: str, generation_id: str) -> bool:
        async with self._lock:
            active = self._active.get(session_id)
            return active is not None and active.generation_id == generation_id
