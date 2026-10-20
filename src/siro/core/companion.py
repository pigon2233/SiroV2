"""Minimal persistent companion application service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from siro.contracts.events import Privacy as EventPrivacy
from siro.core.context import ContextSourceChanged, read_context_snapshot, render_context
from siro.core.conversation import ConversationEngine, DeltaHandler, TurnResult, TurnState
from siro.core.identity import IdentityRepository
from siro.core.memory import MemoryService, WorkingMemory, WorkingMessage, assemble_prompt
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
        route = (
            EventPrivacy.CLOUD_ALLOWED
            if privacy is Privacy.CLOUD_ALLOWED
            else (memory_route_privacy or EventPrivacy.LOCAL_ONLY)
        )
        snapshot = None
        if message_history is None or not message_history:
            identity = await self._identities.get(identity_id)
            if identity is None:
                raise KeyError(identity_id)
            if recent_messages and any(
                m.role not in ("user", "assistant") or m.tool_calls for m in recent_messages
            ):
                raise ValueError("restored dialogue must be canonical user/assistant statements")
            working = (
                self._working.recent(session_id, route_privacy=route)
                if recent_messages is None
                else ()
            )
            recent_users = (
                tuple(m.content for m in (recent_messages or ()) if m.role == "user")
                if recent_messages is not None
                else tuple(m.text for m in working if m.role == "user")
            )
            if message_history is None and recent_messages is not None:
                working = tuple(WorkingMessage(m.role, m.content, route) for m in recent_messages)
            memories = await self._memory.recall_context(
                identity_id, user_text, recent_users=recent_users, route_privacy=route
            )
            snapshot = await self._memory.context_snapshot(
                identity_id, memories, route_privacy=route
            )
            context = render_context(
                session_id,
                identity_id,
                memories,
                snapshot,
                route_privacy=route,
                dialogue_messages=recent_messages if message_history is not None else None,
            )
            prompt = assemble_prompt(
                identity,
                user_text if message_history is None else "",
                memories,
                working,
                verified_context,
                cloud_route=route is EventPrivacy.CLOUD_ALLOWED,
                context_evidence=context,
                native_dialogue=message_history is not None,
            )
            self._working.append(session_id, "user", user_text, privacy=route)
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
            snapshot = read_context_snapshot(
                message_history[0].content, session_id, identity_id, route
            )
        if on_messages_ready is not None:
            await on_messages_ready()

        async def preflight() -> None:
            if snapshot is not None and (
                snapshot.route_privacy is not route
                or not await self._memory.context_sources_current(snapshot)
            ):
                raise ContextSourceChanged("selected context sources changed before dispatch")

        result = await self._conversation.respond(
            session_id,
            identity_id,
            prompt,
            privacy=privacy,
            on_delta=on_delta,
            tools=tools,
            messages=tuple(message_history) if message_history is not None else (),
            on_before_request=preflight,
        )
        if message_history is not None:
            # Partial intent from a failed/cancelled generation is not an accepted batch.
            calls = result.tool_calls if result.state is TurnState.COMPLETED else ()
            message_history.append(ModelMessage("assistant", result.text, calls))
        if result.text:
            self._working.append(session_id, "assistant", result.text, privacy=route)
        return result
