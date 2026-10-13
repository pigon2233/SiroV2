"""Minimal persistent companion application service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from siro.contracts.events import Privacy as EventPrivacy
from siro.core.conversation import ConversationEngine, DeltaHandler, TurnResult, TurnState
from siro.core.identity import IdentityRepository
from siro.core.memory import MemoryService, WorkingMemory, assemble_prompt
from siro.ports.models import ModelMessage, Privacy, ToolDefinition


class CompanionCore:
    def __init__(
        self,
        identity_repository: IdentityRepository,
        memory: MemoryService,
        conversation: ConversationEngine,
        working_memory: WorkingMemory | None = None,
    ) -> None:
        self._identities = identity_repository
        self._memory = memory
        self._conversation = conversation
        self._working = working_memory or WorkingMemory()

    async def respond(
        self,
        session_id: str,
        identity_id: str,
        user_text: str,
        *,
        privacy: Privacy = Privacy.LOCAL_ONLY,
        on_delta: DeltaHandler | None = None,
        verified_context: Sequence[str] = (),
        tools: tuple[ToolDefinition, ...] = (),
        message_history: list[ModelMessage] | None = None,
        on_messages_ready: Callable[[], Awaitable[None]] | None = None,
        recent_messages: tuple[ModelMessage, ...] | None = None,
        memory_route_privacy: EventPrivacy | None = None,
    ) -> TurnResult:
        if message_history is None or not message_history:
            identity = await self._identities.get(identity_id)
            if identity is None:
                raise KeyError(identity_id)
            memories = await self._memory.recall(
                identity_id, user_text, route_privacy=memory_route_privacy
            )
            prompt = assemble_prompt(
                identity,
                user_text if message_history is None else "",
                memories,
                self._working.recent(session_id) if recent_messages is None else (),
                verified_context,
            )
            self._working.append(session_id, "user", user_text)
            if message_history is not None:
                message_history.extend(
                    (
                        ModelMessage("system", prompt),
                        *(recent_messages or ()),
                        ModelMessage("user", user_text),
                    )
                )
        else:
            # A tool continuation is not a new user utterance or memory query.
            prompt = user_text
        if on_messages_ready is not None:
            await on_messages_ready()
        result = await self._conversation.respond(
            session_id,
            identity_id,
            prompt,
            privacy=privacy,
            on_delta=on_delta,
            tools=tools,
            messages=tuple(message_history) if message_history is not None else (),
        )
        if message_history is not None:
            # Partial intent from a failed/cancelled generation is not an accepted batch.
            calls = result.tool_calls if result.state is TurnState.COMPLETED else ()
            message_history.append(ModelMessage("assistant", result.text, calls))
        if result.text:
            self._working.append(session_id, "assistant", result.text)
        return result
