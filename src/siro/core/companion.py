"""Minimal persistent companion application service."""

from __future__ import annotations

from siro.core.conversation import ConversationEngine, TurnResult
from siro.core.identity import IdentityRepository
from siro.core.memory import MemoryService, WorkingMemory, assemble_prompt
from siro.ports.models import Privacy


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
    ) -> TurnResult:
        identity = await self._identities.get(identity_id)
        if identity is None:
            raise KeyError(identity_id)
        memories = await self._memory.recall(identity_id, user_text)
        prompt = assemble_prompt(identity, user_text, memories, self._working.recent(session_id))
        self._working.append(session_id, "user", user_text)
        result = await self._conversation.respond(session_id, identity_id, prompt, privacy=privacy)
        if result.text:
            self._working.append(session_id, "assistant", result.text)
        return result
