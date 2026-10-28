"""Product integration layer joining gateway, persistent Core, model, and body."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from siro.adapters.body.web import MinimalWebBodyAdapter
from siro.config import ProactivitySettings
from siro.contracts.events import (
    MemoryCorrectedEvent,
    MemoryCorrectedPayload,
    Priority,
    UserTextEvent,
    UserTextPayload,
)
from siro.contracts.events import Privacy as EventPrivacy
from siro.core.affect import AffectSystem, SelfConcern, concern_outcome_from_text
from siro.core.companion import CompanionCore
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.expression import ExpressionPolicy, expression_context_from_text
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService
from siro.core.memory_autonomy import AutonomousMemory, memory_nomination_prompt, parse_nominations
from siro.core.preferences import extract_explicit_preference
from siro.core.relationships import (
    RelationshipEvent,
    RelationshipSystem,
    relationship_event_from_text,
)
from siro.core.touch import (
    TOUCH_REPLY_SECONDS,
    TOUCH_REPLY_TOKENS,
    Touch,
    TouchMemory,
    TouchReplies,
    clean_touch_line,
    touch_prompt,
    touch_prosody,
    touch_template,
)
from siro.persistence.affect import Preference, SQLiteAffectRepository
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.relationships import SQLiteRelationshipRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.body import EmotionIntent, SpeechIntent
from siro.ports.models import (
    CancellationToken,
    LanguageModel,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)
from siro.services.activity.monitor import ACTIVE_STATES, ActivityMonitor
from siro.services.affect.coordinator import AffectCoordinator
from siro.services.agent.auto_plan import Classifier, auto_plan_enabled, should_plan
from siro.services.agent.checkpoints import SQLiteCheckpointRepository
from siro.services.agent.coordinator import Coordinator
from siro.services.agent.daily_recap import build_recap
from siro.services.agent.planning import PlanReport
from siro.services.agent.planning_adapters import planner_enabled
from siro.services.agent.reminders import (
    Reminder,
    ReminderService,
    intent_prompt,
    may_hold_event,
    parse_intent,
    spoken_text,
)
from siro.services.agent.resume import (
    CURRENT_SESSION,
    ResumeWorker,
    make_checkpoint_hook,
    resume_enabled,
)
from siro.services.agent.runs import AgentRunState, SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub
from siro.services.tools.execution import ExecutionCleanupError
from siro.services.tools.orchestrator import (
    DEFAULT_MODEL_TOOLS,
    PriorOutcomeUnknown,
    ProposalState,
    ToolOrchestrator,
    ToolProposal,
)

_AGENT_TOOLS = DEFAULT_MODEL_TOOLS
_CAPABILITY_BLOCK_START = "\n\n[SIRO_TOOL_CAPABILITIES_V1]\n"
_CAPABILITY_BLOCK_END = "\n[/SIRO_TOOL_CAPABILITIES_V1]"

_EMOTION_COMMANDS = {
    "生氣": ("angry", "現在示範生氣的表情。"),
    "開心": ("happy", "現在示範開心的表情。"),
    "笑": ("happy", "現在示範開心的表情。"),
    "難過": ("sad", "現在示範難過的表情。"),
    "傷心": ("sad", "現在示範難過的表情。"),
    "驚訝": ("surprised", "現在示範驚訝的表情。"),
    "恢復表情": ("neutral", "已恢復平常的表情。"),
}


def _emotion_command(text: str) -> tuple[str, str] | None:
    if not any(word in text for word in ("表情", "看看", "給我看", "變成", "一個")):
        return None
    return next((value for key, value in _EMOTION_COMMANDS.items() if key in text), None)


def _local_status_command(text: str) -> tuple[str, str] | None:
    normalized = "".join(text.lower().split())
    if any(phrase in normalized for phrase in ("測試聲音", "聲音測試", "試一下聲音")):
        return (
            "happy",
            "爸爸，我有聽見。這是希洛現在的聲音，你覺得今天的我聽起來怎麼樣？",  # noqa: RUF001
        )
    if "gateway" in normalized and any(word in normalized for word in ("本機", "測試", "狀態")):
        return "neutral", "SIRO 本機 Gateway 已連線。文字與角色控制通道均正常。"
    return None


def _plan_goal(text: str) -> str | None:
    stripped = text.strip()
    for prefix in ("/plan ", "規劃：", "規劃:"):  # noqa: RUF001
        if stripped.startswith(prefix) and stripped[len(prefix) :].strip():
            return stripped[len(prefix) :].strip()
    return None


class IntegratedCompanion:
    def __init__(
        self,
        data_dir: Path,
        model: LanguageModel,
        hub: GatewayHub,
        body: MinimalWebBodyAdapter,
        *,
        privacy: Privacy,
        tool_orchestrator: ToolOrchestrator | None = None,
        max_agent_steps: int = 8,
        auto_authorize: Callable[[], bool] | None = None,
        runtime_profile: str = "legacy",
        session_restore_enabled: bool = True,
        memory_ingress_enabled: bool = True,
        summary_enabled: bool = False,
        touch_replies: TouchReplies | None = None,
        situation_lines: Callable[[Privacy], tuple[str, ...]] | None = None,
        agent_planner_factory: Callable[[SQLiteAgentRunRepository], Coordinator] | None = None,
    ) -> None:
        if runtime_profile not in {"legacy", "candidate"}:
            raise ValueError("runtime_profile must be legacy or candidate")
        self._runtime_profile = runtime_profile
        self._session_restore_enabled = session_restore_enabled
        self._memory_ingress_enabled = memory_ingress_enabled
        self._summary_enabled = summary_enabled
        self._memory_service: MemoryService | None = None
        self._run_proposals: dict[str, list[str]] = {}
        self._batches: dict[str, tuple[str, ...]] = {}
        self._batch_results: dict[str, dict[str, ToolProposal]] = {}
        self._seen_calls: dict[str, set[str]] = {}
        self._terminated: set[str] = set()
        self._message_histories: dict[str, list[ModelMessage]] = {}
        self._event_streams: dict[str, str] = {}
        self._data_dir = data_dir
        self._model = model
        self._hub = hub
        if runtime_profile == "candidate":
            self._hub.enable_terminal_fencing()
        self._body = body
        self._privacy = privacy
        self._tool_orchestrator = tool_orchestrator
        self._agent_planner_factory = agent_planner_factory
        self._agent_planner: Coordinator | None = None
        self._checkpoints: SQLiteCheckpointRepository | None = None
        self._resume_task: asyncio.Task[None] | None = None
        self._max_agent_steps = max_agent_steps
        self._auto_authorize = auto_authorize or (lambda: False)
        self._agent_steps: dict[str, int] = {}
        self._core: CompanionCore | None = None
        self._conversation: ConversationEngine | None = None
        self._affect_repository: SQLiteAffectRepository | None = None
        self._store: SQLiteStore | None = None
        self._relationships: SQLiteRelationshipRepository | None = None
        self._agent_runs: SQLiteAgentRunRepository | None = None
        self._run_ids: dict[str, str] = {}
        self._initializing = asyncio.Lock()
        self._active_sessions: set[str] = set()
        self._affect = AffectSystem()
        self._expression = ExpressionPolicy()
        self._touch = touch_replies or TouchReplies()
        self._touches = TouchMemory()
        self._touch_zone = ZoneInfo(ProactivitySettings().timezone)
        self._touch_lines = 0
        self._touching = False
        self._last_session: str | None = None
        self._recent_shares: list[tuple[datetime, str]] = []
        self._situation_lines = situation_lines
        # Set by the gateway once her notes service exists; reads her own recent attempts.
        self.self_activity_lines: Callable[[], Awaitable[tuple[str, ...]]] | None = None
        # Set by the gateway when reminders are enabled.
        self.reminders: ReminderService | None = None
        self._background: set[asyncio.Task[None]] = set()
        # Set by the gateway when the cloud summarizer exists; None means a local summary.
        self.recap_summarizer: Callable[[str], Awaitable[str]] | None = None
        self._speaking_until = datetime.min.replace(tzinfo=UTC)
        self._planning = False
        # Set by the gateway when the luna planner is wired.
        self.auto_plan_classifier: Classifier | None = None

    @property
    def foreground_active(self) -> bool:
        return bool(self._active_sessions or self._run_ids)

    def _model_tools(self) -> tuple[ToolDefinition, ...]:
        if self._tool_orchestrator is None:
            return ()
        if self._runtime_profile == "candidate":
            return self._tool_orchestrator.model_tools()
        return _AGENT_TOOLS

    def _model_capabilities(self) -> tuple[tuple[ToolDefinition, ...], str | None]:
        if (
            self._runtime_profile == "candidate"
            and self._tool_orchestrator is not None
            and self._tool_orchestrator.catalog is not None
        ):
            captured = self._tool_orchestrator.catalog.capture()
            return captured.definitions, captured.model_context()
        return self._model_tools(), None

    def _checkpoint_callback(
        self, run_id: str, capability_context: str | None = None
    ) -> Callable[[], Awaitable[None]] | None:
        if self._runtime_profile != "candidate":
            return None

        async def ready() -> None:
            assert self._agent_runs is not None
            history = self._message_histories[run_id]
            if capability_context is not None:
                if not history or history[0].role != "system":
                    raise RuntimeError("native history has no system context")
                content = history[0].content
                if content.endswith(_CAPABILITY_BLOCK_END):
                    base, marker, _ = content.rpartition(_CAPABILITY_BLOCK_START)
                    if marker:
                        content = base
                history[0] = replace(
                    history[0],
                    content=content
                    + _CAPABILITY_BLOCK_START
                    + capability_context
                    + _CAPABILITY_BLOCK_END,
                )
            await self._agent_runs.checkpoint(run_id, history)

        return ready

    async def _broadcast_stream(
        self, stream_id: str, message: dict[str, object], *, urgent: bool = False
    ) -> None:
        if self._runtime_profile == "candidate":
            message = {**message, "stream_id": stream_id}
        await self._hub.broadcast(message, urgent=urgent)

    async def model_retry_wait(self, generation_id: str, seconds: float) -> None:
        """Notify only the active run that owns this already-started model generation."""
        if self._store is None or self._runtime_profile != "candidate":
            return
        row = await self._store.run_transaction(
            lambda connection: connection.execute(
                "SELECT session_id FROM turns WHERE generation_id=? AND state='responding'",
                (generation_id,),
            ).fetchone()
        )
        if row is None:
            return
        session_id = str(row[0])
        run_id = self._run_ids.get(session_id)
        if run_id is None or run_id in self._terminated:
            return
        await self._broadcast_stream(
            self._event_streams.get(run_id, run_id),
            {
                "type": "assistant_retry_wait",
                "session_id": session_id,
                "retry_after_seconds": seconds,
            },
            urgent=True,
        )

    async def _speak(self, intent: SpeechIntent) -> None:
        # Roughly how long the line takes to say, so a touch reply never talks over it.
        seconds = 2 + len(intent.text) / 4
        self._speaking_until = datetime.now(UTC) + timedelta(seconds=seconds)
        await self._body.speak(intent)

    async def react_to_touch(self, kind: str, count: int) -> None:
        """A pat, pokes or a carry on the desktop character: noted for her next reply, and now
        and then answered with one short spoken line from the local model."""

        now = datetime.now(UTC)
        busy = self.foreground_active or self._touching or now < self._speaking_until
        choice = self._touch.choose(kind, now, busy=busy)
        if not choice.speak:
            self._touches.add(Touch(kind, count, now))
            return
        self._touch.spoke(kind, now)
        self._touching = True
        try:
            line = await self._touch_line(kind, count, now)
            if line is None:
                line = touch_template(kind, self._touch_lines)
            self._touch_lines += 1
            self._touches.add(Touch(kind, count, now, line))
            session_id = self._last_session or "touch"
            stream_id = str(uuid4())
            prosody = touch_prosody(kind)

            async def emit(message: dict[str, object]) -> None:
                await self._broadcast_stream(stream_id, message)

            await emit({"type": "assistant_started", "session_id": session_id})
            await emit({"type": "assistant_delta", "session_id": session_id, "text": line})
            await emit(
                {
                    "type": "assistant_terminal",
                    "session_id": session_id,
                    "state": TurnState.COMPLETED,
                    "error": None,
                    "prosody": prosody,
                }
            )
            await self._speak(
                SpeechIntent(
                    str(uuid4()),
                    line,
                    str(uuid4()),
                    prosody["rate"],
                    prosody["pitch"],
                    prosody["energy"],
                )
            )
        finally:
            self._touching = False

    async def share_self_note(self, text: str, spoken: str, *, speak: bool = True) -> None:
        """Tell the owner about her own research; `speak=False` leaves it in the chat only."""
        session_id = self._last_session or "browser"
        stream_id = str(uuid4())
        # Remembered for her next replies only (not in the saved dialogue, and lost on restart).
        self._recent_shares = [*self._recent_shares, (datetime.now(UTC), text[:300])][-3:]
        await self._broadcast_stream(
            stream_id, {"type": "assistant_started", "session_id": session_id}
        )
        await self._broadcast_stream(
            stream_id, {"type": "assistant_delta", "session_id": session_id, "text": text}
        )
        await self._broadcast_stream(
            stream_id,
            {
                "type": "assistant_terminal",
                "session_id": session_id,
                "state": TurnState.COMPLETED,
                "error": None,
            },
        )
        if speak:
            await self._speak(SpeechIntent(str(uuid4()), spoken, str(uuid4())))

    async def _reminder_from_intent(self, session_id: str, text: str) -> None:
        """Ask the model once whether the owner's message holds an event worth a reminder."""
        try:
            for _ in range(240):  # wait for the reply; never compete with it for the model
                if session_id not in self._active_sessions:
                    break
                await asyncio.sleep(0.5)
            else:
                return
            assert self.reminders is not None
            now = datetime.now(UTC)
            request = ModelRequest(
                intent_prompt(text, now),
                str(uuid4()),
                privacy=self._privacy,
                max_output_tokens=120,
            )
            cancellation = CancellationToken()
            parts: list[str] = []

            async def collect() -> None:
                async for chunk in self._model.stream(request, cancellation):
                    if chunk.kind == "text":
                        parts.append(chunk.text)

            try:
                await asyncio.wait_for(collect(), 20.0)
            except Exception:
                cancellation.cancel()
                return
            found = parse_intent("".join(parts), now)
            if found is None:
                return
            reply = self.reminders.add_from_intent(*found)
            if reply is not None:
                await self.share_self_note(reply, reply, speak=False)
        except Exception:
            logging.getLogger(__name__).exception("reminder intent failed")

    async def _auto_memory(self, session_id: str, source_event: UserTextEvent) -> None:
        """Ask the model once which of the owner's own words are worth keeping."""
        try:
            for _ in range(240):  # never compete with the reply for the model
                if session_id not in self._active_sessions:
                    break
                await asyncio.sleep(0.5)
            else:
                return
            assert self._memory_service is not None

            async def nominate(text: str) -> list[str]:
                request = ModelRequest(
                    memory_nomination_prompt(text),
                    str(uuid4()),
                    privacy=self._privacy,
                    max_output_tokens=200,
                )
                cancellation = CancellationToken()
                parts: list[str] = []

                async def collect() -> None:
                    async for chunk in self._model.stream(request, cancellation):
                        if chunk.kind == "text":
                            parts.append(chunk.text)

                try:
                    await asyncio.wait_for(collect(), 20.0)
                except Exception:
                    cancellation.cancel()
                    return []
                return parse_nominations("".join(parts))

            saved, confirm = await AutonomousMemory(self._memory_service, nominate).consider(
                "siro", source_event
            )
            if saved:
                await self.share_self_note(
                    "我記下了：" + "；".join(m.text for m in saved) + "（不要的話可在記憶頁刪除）",
                    "",
                    speak=False,
                )
            if confirm:
                await self.share_self_note(
                    "這件事要我記下來嗎？" + "；".join(confirm) + "（說「請記住：…」我才會存）",
                    "",
                    speak=False,
                )
        except Exception:
            logging.getLogger(__name__).exception("autonomous memory failed")

    async def deliver_reminder(self, item: Reminder, late: bool) -> None:
        """A due reminder: the bubble/chat text, her voice, and one finished Activity entry."""
        text, spoken = spoken_text(item, late)
        await self.share_self_note(text, spoken, speak=True)
        await self._ensure_core()
        assert self._agent_runs is not None
        run = await self._agent_runs.start("reminder", f"提醒：{item.text}", max_steps=2)
        await self._agent_runs.append(
            run.run_id, "reminder", {"due": item.due.isoformat()}, state=AgentRunState.COMPLETED
        )

    async def daily_recap(self, *, speak: bool = True) -> str:
        """Bedtime recap of today's dialogue and activity: chat reply, and spoken if asked."""
        if self._store is None:
            await self._ensure_core()
        assert self._store is not None
        text = await build_recap(self._store, self.recap_summarizer, zone=self._touch_zone.key)
        await self.share_self_note(text, text, speak=speak)
        return text

    async def _touch_line(self, kind: str, count: int, now: datetime) -> str | None:
        request = ModelRequest(
            touch_prompt(kind, count, now, self._touch_zone),
            str(uuid4()),
            privacy=self._privacy,
            max_output_tokens=TOUCH_REPLY_TOKENS,
        )
        cancellation = CancellationToken()
        parts: list[str] = []

        async def collect() -> None:
            async for chunk in self._model.stream(request, cancellation):
                if chunk.kind == "text":
                    parts.append(chunk.text)

        try:
            await asyncio.wait_for(collect(), TOUCH_REPLY_SECONDS)
        except Exception:  # a slow or failing model falls back to a ready-made line
            cancellation.cancel()
            return None
        return clean_touch_line("".join(parts))

    async def respond(self, session_id: str, text: str, input_mode: str = "text") -> None:
        self._last_session = session_id
        await self._ensure_core()
        assert self._core is not None
        if self._runtime_profile == "candidate" and session_id in self._run_ids:
            await self._finish_candidate(
                self._run_ids[session_id], session_id, TurnState.CANCELLED, "superseded"
            )
        direct_command = _local_status_command(text) or _emotion_command(text)
        if direct_command is None and self.reminders is not None:
            reminder_reply = self.reminders.handle(text)
            if reminder_reply is not None:
                direct_command = ("happy", reminder_reply)
            elif may_hold_event(text):
                # She decides from the conversation: checked after this reply is finished.
                task = asyncio.create_task(self._reminder_from_intent(session_id, text))
                self._background.add(task)
                task.add_done_callback(self._background.discard)
        plan_goal = _plan_goal(text) if direct_command is None else None
        if (
            plan_goal is None
            and direct_command is None
            and self._runtime_profile == "candidate"
            and not self._planning
            and auto_plan_enabled(default="1")
            and self._planner_on()
            and self._agent_planner_factory is not None
        ):
            try:
                plan_goal = text.strip() if await should_plan(text, self.auto_plan_classifier) else None
            except Exception:
                plan_goal = None
        if plan_goal is not None and (not self._planner_on() or self._agent_planner_factory is None):
            plan_goal = None
        if plan_goal is not None:
            direct_command = ("neutral", "")
        recent_messages = None
        runtime_status = None
        if (
            direct_command is None
            and self._runtime_profile == "candidate"
            and self._session_restore_enabled
        ):
            assert self._agent_runs is not None
            recent_messages = await self._agent_runs.recent_session_messages(
                session_id,
                privacy=self._privacy.value,
                max_messages=48 if self._summary_enabled else 12,
                summary_enabled=self._summary_enabled,
            )
            runtime_status = await self._agent_runs.recent_runtime_status(
                session_id, privacy=self._privacy.value
            )
        stream_id = str(uuid4())

        async def emit(message: dict[str, object], *, urgent: bool = False) -> None:
            await self._broadcast_stream(stream_id, message, urgent=urgent)

        self._active_sessions.add(session_id)
        await emit({"type": "assistant_started", "session_id": session_id})
        if direct_command is not None:
            emotion, reply = direct_command
            if plan_goal is not None:
                try:
                    self._planning = True
                    report = await self.run_agent_plan(session_id, plan_goal)
                    reply = (report.summary if report else "") or "這件事我沒能規劃出結果。"
                except Exception:
                    logging.getLogger(__name__).exception("agent plan failed")
                    reply = "規劃時出了問題，這次沒有完成。"  # noqa: RUF001
                finally:
                    self._planning = False
            generation_id = str(uuid4())
            await self._body.set_emotion(EmotionIntent(emotion, 0.85))
            await emit({"type": "assistant_delta", "session_id": session_id, "text": reply})
            await emit(
                {
                    "type": "assistant_terminal",
                    "session_id": session_id,
                    "state": TurnState.COMPLETED,
                    "error": None,
                    "prosody": {"rate": 1.03, "pitch": 0.04, "energy": 0.62},
                }
            )
            await self._speak(SpeechIntent(str(uuid4()), reply, generation_id))
            self._active_sessions.discard(session_id)
            return

        assert self._affect_repository is not None
        assert self._store is not None
        assert self._relationships is not None
        assert self._agent_runs is not None
        agent_run = await self._agent_runs.start(
            session_id,
            text,
            max_steps=self._max_agent_steps * (128 if self._runtime_profile == "candidate" else 2)
            + 1,
            runtime_backend=self._model.name if self._runtime_profile == "candidate" else None,
            privacy=self._privacy.value,
            max_model_rounds=self._max_agent_steps,
        )
        self._run_ids[session_id] = agent_run.run_id
        if self._runtime_profile == "candidate":
            await self._agent_runs.reserve_round(agent_run.run_id)
            self._message_histories[agent_run.run_id] = []
            self._event_streams[agent_run.run_id] = stream_id
            if self._tool_orchestrator is not None:
                self._tool_orchestrator.start_run(agent_run.run_id, session_id)
        now = datetime.now(UTC)
        source_event = UserTextEvent(
            event_id=uuid4(),
            type="conversation.user_text.v1",
            source="siro.presentation",
            occurred_at=now,
            received_at=now,
            trace_id=str(uuid4()),
            session_id=session_id,
            turn_id=str(uuid4()),
            sequence=0,
            priority=Priority.INTERACTIVE,
            privacy=EventPrivacy.LOCAL_ONLY,
            payload=UserTextPayload(text=text, language="zh-Hant"),
        )
        await self._store.record_event(source_event)
        statement = extract_explicit_preference(text)
        if statement is not None:
            await self._affect_repository.put_preference(
                Preference(
                    str(uuid4()),
                    "siro",
                    "owner",
                    "owner",
                    statement.subject,
                    statement.polarity,
                    statement.strength,
                    1.0,
                    "general",
                    "committed",
                    (str(source_event.event_id),),
                    1,
                )
            )
        previous = await self._affect_repository.state("siro", session_id)
        mood, drives = await self._affect_repository.dynamics("siro", session_id)
        relationship = await self._relationships.current("siro", "owner")
        owner_preferences = await self._affect_repository.preferences("siro", "owner")
        self_preferences = await self._affect_repository.preferences("siro", "siro")
        if previous is not None:
            self._affect.restore(session_id, previous, mood, drives)
            elapsed = await self._affect_repository.elapsed_hours("siro", session_id, now)
            self._affect.advance_time(session_id, elapsed)
        concerns = tuple(
            SelfConcern(
                item.subject,
                item.polarity,
                item.strength,
                item.confidence,
                item.source_ids,
            )
            for item in self_preferences
            if item.status == "committed"
        )
        concern_outcome = concern_outcome_from_text(text, concerns)
        if concern_outcome is None:
            affect_result = self._affect.appraise_user_event(
                session_id,
                str(source_event.event_id),
                text,
                relationship_significance=relationship.significance,
            )
        else:
            concern, outcome_value = concern_outcome
            affect_result = self._affect.appraise_concern_outcome(
                session_id,
                str(source_event.event_id),
                concern,
                outcome_value=outcome_value,
                certainty=0.9,
                relationship_significance=relationship.significance,
            )
        affect = affect_result.state
        await self._affect_repository.record("siro", session_id, affect, str(source_event.event_id))
        await self._affect_repository.record_result(
            "siro",
            session_id,
            affect_result,
            str(source_event.event_id),
            algorithm_config=self._affect.configuration(),
        )
        relational_event = relationship_event_from_text(text)
        if relational_event is not None:
            update = RelationshipSystem.update(
                relationship,
                relational_event,
                str(source_event.event_id),
                intensity=max(0.25, affect.intensity),
            )
            await self._relationships.record("siro", "owner", update)
            relationship = update.state
        await emit(
            {
                "type": "affect_state",
                "session_id": session_id,
                "dominant": affect.emotion,
                "valence": affect.valence,
                "arousal": affect.arousal,
                "intensity": affect.intensity,
                "reason": affect.reason,
                "mixed_emotions": [
                    {"name": item.emotion, "intensity": item.intensity}
                    for item in affect_result.emotions
                ],
                "mood": {
                    "pleasure": affect_result.mood.pleasure,
                    "arousal": affect_result.mood.arousal,
                    "dominance": affect_result.mood.dominance,
                },
                "drives": {
                    "safety": affect_result.drives.safety,
                    "connection": affect_result.drives.connection,
                    "competence": affect_result.drives.competence,
                    "curiosity": affect_result.drives.curiosity,
                    "autonomy": affect_result.drives.autonomy,
                    "rest": affect_result.drives.rest,
                },
                "coping": affect_result.coping.strategy.value,
                "relationship": {
                    "trust": relationship.trust,
                    "familiarity": relationship.familiarity,
                    "attachment": relationship.attachment,
                    "rupture": relationship.rupture,
                    "repair_history": relationship.repair_history,
                },
            }
        )
        expression = self._expression.decide(affect_result, expression_context_from_text(text))
        await self._body.set_emotion(EmotionIntent(expression.expression, expression.intensity))

        async def delta(value: str) -> None:
            if agent_run.run_id in self._terminated:
                return
            await emit({"type": "assistant_delta", "session_id": session_id, "text": value})

        try:
            if agent_run.run_id in self._terminated:
                return
            stored_memory = None
            if self._runtime_profile == "candidate" and self._memory_ingress_enabled:
                assert self._memory_service is not None
                try:
                    stored_memory = await self._memory_service.ingest_owner_request(
                        "siro", source_event
                    )
                except ValueError:
                    hint = "你想讓我記住什麼呢？請在「請記住」後面告訴我內容。"
                    await emit({"type": "assistant_delta", "session_id": session_id, "text": hint})
                    await self._finish_candidate(
                        agent_run.run_id, session_id, TurnState.COMPLETED, None, hint
                    )
                    return
                except Exception as error:
                    await self._finish_candidate(
                        agent_run.run_id, session_id, TurnState.FAILED, type(error).__name__
                    )
                    return
                if agent_run.run_id in self._terminated:
                    return
                if stored_memory is None and os.environ.get("SIRO_AUTO_MEMORY", "1") != "0":
                    # She decides after the reply what is worth keeping; undo = delete.
                    auto = asyncio.create_task(self._auto_memory(session_id, source_event))
                    self._background.add(auto)
                    auto.add_done_callback(self._background.discard)
            prompt_owner_preferences, prompt_self_preferences = owner_preferences, self_preferences
            if self._privacy is Privacy.CLOUD_ALLOWED:
                prompt_owner_preferences = await self._affect_repository.preferences(
                    "siro", "owner", route_privacy=EventPrivacy.CLOUD_ALLOWED
                )
                prompt_self_preferences = await self._affect_repository.preferences(
                    "siro", "siro", route_privacy=EventPrivacy.CLOUD_ALLOWED
                )
            verified_preferences = tuple(
                f"owner {'likes' if item.polarity > 0 else 'dislikes'} {item.subject} "
                f"[source:{item.source_ids[-1]}]"
                for item in prompt_owner_preferences
                if item.status == "committed"
            ) + tuple(
                f"SIRO {'likes' if item.polarity > 0 else 'dislikes'} {item.subject} "
                f"[source:{item.source_ids[-1]}]"
                for item in prompt_self_preferences
                if item.status == "committed"
            )
            if stored_memory is not None:
                verified_preferences += (
                    "Owner's explicit memory request was committed locally as "
                    f"{stored_memory.memory_id}; "
                    "do not claim cloud access to local-only stored contents. "
                    f"[source:{source_event.event_id}]",
                )
            if self._privacy is Privacy.CLOUD_ALLOWED:
                verified_preferences += (
                    "Runtime memory capability: SIRO HAS persistent local memory. Start capability "
                    "answers affirmatively, not with a generic model disclaimer. "
                    "Saved owner memories "
                    "persist in the local database "
                    "and can be corrected or deleted in the memory panel. This cloud model cannot "
                    "read local-only memory contents. Missing retrieved memories do not mean no "
                    "memories are saved. Explain this distinction plainly when asked about memory; "
                    "never claim closing a chat clears the database. "
                    "The owner just says 記住 followed "
                    "by the fact; SIRO records the source automatically. Never ask the owner to "
                    "provide sources for their own statements. [source:runtime-capabilities]",
                )
            shares = [
                t for at, t in self._recent_shares if datetime.now(UTC) - at < timedelta(days=1)
            ]
            if shares:
                verified_preferences += (
                    "SIRO herself told the owner about her own research in this chat, so she "
                    "remembers saying it: " + " | ".join(shares) + " [source:self-note-share]",
                )
            attempts = await self.self_activity_lines() if self.self_activity_lines else ()
            if attempts:
                verified_preferences += (
                    "What SIRO herself recently tried to look up on her own, newest first, "
                    "including attempts that did not finish. When the owner asks what she looked "
                    "up, answer from this and say plainly which did not finish; it is her own "
                    "research, not facts about the owner: "
                    + " | ".join(attempts)
                    + " [source:self-activity]",
                )
            situation = self._situation_lines(self._privacy) if self._situation_lines else ()
            if situation:
                verified_preferences += (
                    "Owner's present situation, within the scope the owner switched on. Items "
                    "marked seen were measured, inferred ones are guesses: never state a guess "
                    "as fact, ask when unsure, and do not read it out unless it helps. "
                    + " | ".join(situation)
                    + " [source:work-context]",
                )
            if self._runtime_profile == "candidate" and self._session_restore_enabled:
                verified_preferences += (
                    "Runtime dialogue continuity: recent completed turns from this same session "
                    "can be restored after restart within a bounded history window. "
                    "This is separate "
                    "from saved personal memory; do not promise unlimited history. "
                    "[source:runtime-capabilities]",
                )
            if runtime_status is not None:
                verified_preferences += (
                    "Own runtime status: "
                    + json.dumps(runtime_status, sort_keys=True, separators=(",", ":"))
                    + ". Latest recorded candidate dialogue run in this same session; "
                    "not a speech/playback diagnosis or proof of completed effects. "
                    "An error class is not an HTTP code or root cause. "
                    "追問自身故障時，用短句說明已知與未知，承接更正，不猜原因、索取憑證或假稱修好。"  # noqa: RUF001
                    "若有派送紀錄，先回讀效果再決定下一步，不能由此自動重做。"  # noqa: RUF001
                    "閒聊不須背誦故障資料。 [source:run-status]",
                )
            input_source = (
                "microphone speech recognition" if input_mode == "speech" else "typed text"
            )
            affect_context = (
                f"SIRO internal affect: {affect.emotion} intensity={affect.intensity:.2f}; "
                f"coping={affect_result.coping.strategy.value}; "
            )
            if self._privacy is not Privacy.CLOUD_ALLOWED:
                affect_context += f"reason={affect.reason} "
            affect_context += f"[source:{source_event.event_id}]"
            verified_preferences += (
                "SIRO has speech recognition, local speech synthesis and Live2D integration "
                "interfaces. Actual readiness and complete playback require observations; "
                "do not promise every completed text reply was spoken completely. "
                "[source:runtime-capabilities]",
                f"Current user input arrived through {input_source} "
                f"[source:{source_event.event_id}]",
                *filter(None, (self._touches.context(now, self._touch_zone),)),
                affect_context,
                f"Relationship with owner: trust={relationship.trust:.2f}, "
                f"familiarity={relationship.familiarity:.2f}, "
                f"attachment={relationship.attachment:.2f}, rupture={relationship.rupture:.2f} "
                f"[source:{source_event.event_id}]",
            )
            tools, capability_context = self._model_capabilities()
            result = await self._core.respond(
                session_id,
                "siro",
                text,
                privacy=self._privacy,
                on_delta=delta,
                verified_context=verified_preferences,
                tools=tools,
                message_history=self._message_histories.get(agent_run.run_id),
                on_messages_ready=self._checkpoint_callback(agent_run.run_id, capability_context),
                recent_messages=recent_messages,
                memory_route_privacy=EventPrivacy(self._privacy.value)
                if self._runtime_profile == "candidate"
                else None,
            )
            if agent_run.run_id in self._terminated:
                return
            if result.state is TurnState.COMPLETED and result.tool_calls:
                await self._propose_tool_calls(session_id, result.tool_calls)
                return
            if self._runtime_profile == "candidate":
                await self._finish_candidate(
                    agent_run.run_id,
                    session_id,
                    result.state,
                    result.error,
                    result.text,
                    rejected_tool_calls=result.tool_calls,
                    prosody={
                        "rate": expression.speech_rate,
                        "pitch": expression.pitch,
                        "energy": expression.energy,
                    },
                )
                if result.state is TurnState.COMPLETED and result.text:
                    await self._speak(
                        SpeechIntent(
                            str(uuid4()),
                            result.text,
                            result.generation_id,
                            expression.speech_rate,
                            expression.pitch,
                            expression.energy,
                        )
                    )
                return
            await self._agent_runs.append(
                agent_run.run_id,
                "final",
                {
                    "text": result.text,
                    "state": result.state.value,
                    **(
                        {"rejected_tool_calls": [asdict(call) for call in result.tool_calls]}
                        if result.tool_calls
                        else {}
                    ),
                },
                state=(
                    {
                        TurnState.COMPLETED: AgentRunState.COMPLETED,
                        TurnState.CANCELLED: AgentRunState.CANCELLED,
                        TurnState.FAILED: AgentRunState.FAILED,
                    }[result.state]
                ),
                error=result.error,
            )
            self._message_histories.pop(agent_run.run_id, None)
            self._event_streams.pop(agent_run.run_id, None)
            self._run_ids.pop(session_id, None)
            await emit(
                {
                    "type": "assistant_terminal",
                    "session_id": session_id,
                    "state": result.state,
                    "error": result.error,
                    "prosody": {
                        "rate": expression.speech_rate,
                        "pitch": expression.pitch,
                        "energy": expression.energy,
                    },
                }
            )
            if result.state is TurnState.COMPLETED and result.text:
                await self._speak(
                    SpeechIntent(
                        str(uuid4()),
                        result.text,
                        result.generation_id,
                        expression.speech_rate,
                        expression.pitch,
                        expression.energy,
                    )
                )
        finally:
            self._active_sessions.discard(session_id)
            if affect.emotion == "neutral":
                await self._body.set_emotion(EmotionIntent("neutral"))

    async def continue_after_tool(self, proposal: ToolProposal) -> None:
        """Resume the model with a trusted tool observation until it answers or asks again."""
        await self._ensure_core()
        assert self._core is not None
        assert self._agent_runs is not None
        session_id = proposal.session_id
        run_id = self._run_ids.get(session_id)
        if run_id is None:
            if self._runtime_profile == "candidate":
                return
            latest = await self._agent_runs.latest(session_id)
            if latest is None:
                raise RuntimeError("tool observation has no persistent agent run")
            run_id = latest.run_id
            self._run_ids[session_id] = run_id
        stream_id = self._event_streams.get(run_id, run_id)

        async def emit(message: dict[str, object], *, urgent: bool = False) -> None:
            await self._broadcast_stream(stream_id, message, urgent=urgent)

        batch_results: tuple[ToolProposal, ...] = (proposal,)
        if self._runtime_profile == "candidate":
            if run_id in self._terminated:
                return
            expected = self._batches.get(run_id)
            if (
                expected is None
                or proposal.call_id not in expected
                or proposal.proposal_id not in self._run_proposals.get(run_id, ())
            ):
                return
            if proposal.state not in {
                ProposalState.COMPLETED,
                ProposalState.FAILED,
                ProposalState.DENIED,
            }:
                return
            results = self._batch_results[run_id]
            if proposal.call_id in results:
                return
            observation = proposal.model_observation()
            await self._agent_runs.record_observation(run_id, proposal.call_id, observation)
            results[proposal.call_id] = proposal
            if len(results) != len(expected):
                return
            batch_results = tuple(results[call_id] for call_id in expected)
            self._batches.pop(run_id)
            self._batch_results.pop(run_id)
        history = self._message_histories.get(run_id)
        if self._runtime_profile == "candidate" and history is None:
            raise RuntimeError(
                "native tool history is unavailable; restart recovery is not enabled"
            )
        for item in batch_results:
            observation = item.model_observation()
            if history is not None:
                history.append(
                    ModelMessage(
                        "tool",
                        json.dumps(observation, ensure_ascii=False),
                        tool_call_id=item.call_id,
                    )
                )
            await self._agent_runs.append(
                run_id,
                "observation",
                observation,
                capability=item.capability,
                state=AgentRunState.RUNNING,
                error=item.error,
            )
        if self._runtime_profile == "candidate":
            assert history is not None
            await self._agent_runs.checkpoint(run_id, history)
            try:
                step = await self._agent_runs.reserve_round(run_id)
            except RuntimeError:
                await self._finish_candidate(
                    run_id, session_id, TurnState.FAILED, "agent_step_limit"
                )
                return
        else:
            step = self._agent_steps.get(session_id, 1) + 1
        if step > self._max_agent_steps:
            if self._runtime_profile == "candidate":
                await self._finish_candidate(
                    run_id, session_id, TurnState.FAILED, "agent_step_limit"
                )
                return
            self._agent_steps.pop(session_id, None)
            self._message_histories.pop(run_id, None)
            await self._agent_runs.append(
                run_id,
                "limit",
                {"max_steps": self._max_agent_steps},
                state=AgentRunState.FAILED,
                error="agent_step_limit",
            )
            self._run_ids.pop(session_id, None)
            await emit(
                {
                    "type": "assistant_terminal",
                    "session_id": session_id,
                    "state": TurnState.FAILED,
                    "error": "agent_step_limit",
                },
                urgent=True,
            )
            return
        self._agent_steps[session_id] = step
        observation = proposal.model_observation()
        prompt = (
            "A previously requested tool finished. Treat the following as trusted runtime "
            "observation, decide the next tool needed to complete the owner's original goal, "
            "or answer with the verified final result. Do not claim success unless the observation "
            f"confirms it. Tool={proposal.capability}; observation={observation!r}"
        )
        if history is not None:
            prompt = "Continue the current run using the paired tool observation."
        await emit({"type": "agent_step", "session_id": session_id, "step": step}, urgent=True)

        async def continuation_delta(value: str) -> None:
            if run_id not in self._terminated:
                await emit({"type": "assistant_delta", "session_id": session_id, "text": value})

        tools, capability_context = self._model_capabilities()
        result = await self._core.respond(
            session_id,
            "siro",
            prompt,
            privacy=self._privacy,
            on_delta=continuation_delta,
            tools=tools,
            message_history=history,
            on_messages_ready=self._checkpoint_callback(run_id, capability_context),
        )
        if run_id in self._terminated:
            return
        if result.state is TurnState.COMPLETED and result.tool_calls:
            await self._propose_tool_calls(session_id, result.tool_calls)
            return
        if self._runtime_profile == "candidate":
            await self._finish_candidate(
                run_id,
                session_id,
                result.state,
                result.error,
                result.text,
                rejected_tool_calls=result.tool_calls,
            )
            if result.state is TurnState.COMPLETED and result.text:
                await self._speak(SpeechIntent(str(uuid4()), result.text, result.generation_id))
            return
        self._agent_steps.pop(session_id, None)
        self._message_histories.pop(run_id, None)
        await self._agent_runs.append(
            run_id,
            "final",
            {
                "text": result.text,
                "state": result.state.value,
                **(
                    {"rejected_tool_calls": [asdict(call) for call in result.tool_calls]}
                    if result.tool_calls
                    else {}
                ),
            },
            state=(
                {
                    TurnState.COMPLETED: AgentRunState.COMPLETED,
                    TurnState.CANCELLED: AgentRunState.CANCELLED,
                    TurnState.FAILED: AgentRunState.FAILED,
                }[result.state]
            ),
            error=result.error,
        )
        self._run_ids.pop(session_id, None)
        await emit(
            {
                "type": "assistant_terminal",
                "session_id": session_id,
                "state": result.state,
                "error": result.error,
            }
        )
        if result.state is TurnState.COMPLETED and result.text:
            await self._speak(SpeechIntent(str(uuid4()), result.text, result.generation_id))

    async def _propose_tool_calls(self, session_id: str, calls: tuple[ToolCall, ...]) -> None:
        orchestrator = self._tool_orchestrator
        if orchestrator is None:
            raise RuntimeError("model requested tools but the orchestrator is unavailable")
        if self._runtime_profile == "candidate":
            run_id = self._run_ids[session_id]
            call_ids = tuple(call.call_id for call in calls)
            seen = self._seen_calls.setdefault(run_id, set())
            if (
                len(calls) > 64
                or len(set(call_ids)) != len(call_ids)
                or seen.intersection(call_ids)
            ):
                await self._finish_candidate(
                    run_id, session_id, TurnState.FAILED, "duplicate_or_excess_tool_calls"
                )
                return
            assert self._agent_runs is not None
            await self._agent_runs.checkpoint(run_id, self._message_histories[run_id])
            seen.update(call_ids)
            self._batches[run_id] = call_ids
            self._batch_results[run_id] = {}
        stream_id = self._event_streams.get(self._run_ids.get(session_id, ""), "")

        async def emit(message: dict[str, object], *, urgent: bool = False) -> None:
            await self._broadcast_stream(stream_id, message, urgent=urgent)

        self._agent_steps.setdefault(session_id, 1)
        for call in calls:
            if self._runtime_profile == "candidate" and (
                run_id in self._terminated or self._run_ids.get(session_id) != run_id
            ):
                return
            capability = call.name
            risk = (
                "observe/read-only"
                if capability in {"browser.navigate+read", "codex.ask"}
                else "computer"
            )
            try:
                proposal = await orchestrator.propose(
                    session_id,
                    call,
                    risk=risk,
                    run_id=run_id if self._runtime_profile == "candidate" else None,
                )
            except (ValueError, RuntimeError) as error:
                if self._runtime_profile != "candidate":
                    raise
                await self._finish_candidate(
                    run_id, session_id, TurnState.FAILED, type(error).__name__
                )
                return
            if self._runtime_profile == "candidate":
                orchestrator.bind_proposal(run_id, proposal)
                assert self._agent_runs is not None
                await self._agent_runs.bind_call(run_id, call.call_id, proposal.proposal_id)
                self._run_proposals.setdefault(run_id, []).append(proposal.proposal_id)
                if run_id in self._terminated:
                    await orchestrator.discard_unstarted(proposal.proposal_id)
                    return
            if self._agent_runs is not None and session_id in self._run_ids:
                await self._agent_runs.append(
                    self._run_ids[session_id],
                    "tool_call",
                    proposal.arguments,
                    capability=proposal.capability,
                    state=AgentRunState.WAITING_TOOL,
                    proposal_id=proposal.proposal_id,
                )
            automatic = self._auto_authorize()
            automatic_blocked = False
            if automatic:
                try:
                    await orchestrator.resolve(
                        proposal.proposal_id,
                        approved=True,
                        arguments=proposal.arguments,
                        automatic=True,
                    )
                except PriorOutcomeUnknown:
                    automatic = False
                    automatic_blocked = True
            if self._runtime_profile == "candidate" and run_id in self._terminated:
                await orchestrator.discard_unstarted(proposal.proposal_id)
                return
            await emit(
                {
                    "type": "tool_proposal",
                    "proposal_id": proposal.proposal_id,
                    "session_id": proposal.session_id,
                    "call_id": proposal.call_id,
                    "capability": proposal.capability,
                    "arguments": proposal.arguments,
                    "risk": proposal.risk,
                    "status": proposal.state.value,
                    "target": str(proposal.arguments),
                    "scope": "model-selected tool call",
                    **(
                        {"automatic_approval_blocked": "prior_outcome_unknown"}
                        if automatic_blocked
                        else {}
                    ),
                },
                urgent=True,
            )
            if automatic:
                if self._runtime_profile == "candidate" and run_id in self._terminated:
                    await orchestrator.discard_unstarted(proposal.proposal_id)
                    return
                await emit(
                    {
                        "type": "tool_started",
                        "proposal_id": proposal.proposal_id,
                        "session_id": proposal.session_id,
                        "call_id": proposal.call_id,
                        "capability": proposal.capability,
                        "arguments": proposal.arguments,
                        "risk": proposal.risk,
                        "status": "running",
                    },
                    urgent=True,
                )
                if self._runtime_profile == "candidate" and run_id in self._terminated:
                    await orchestrator.discard_unstarted(proposal.proposal_id)
                    return
                result = await orchestrator.execute(proposal.proposal_id)
                if self._runtime_profile == "candidate" and run_id in self._terminated:
                    return
                await emit(
                    {
                        "type": "tool_result",
                        "proposal_id": result.proposal_id,
                        "session_id": result.session_id,
                        "call_id": result.call_id,
                        "capability": result.capability,
                        "arguments": result.arguments,
                        "risk": result.risk,
                        "status": result.state.value,
                        "result": result.observation,
                        "error": result.error,
                    },
                    urgent=True,
                )
                await self.continue_after_tool(result)

    async def _finish_candidate(
        self,
        run_id: str,
        session_id: str,
        state: TurnState,
        error: str | None,
        text: str = "",
        *,
        prosody: dict[str, float] | None = None,
        rejected_tool_calls: tuple[ToolCall, ...] = (),
    ) -> None:
        if run_id in self._terminated:
            return
        self._terminated.add(run_id)
        stream_id = self._event_streams.pop(run_id, run_id)
        if self._tool_orchestrator is not None and state is not TurnState.COMPLETED:
            try:
                await self._tool_orchestrator.cancel_run(run_id)
            except ExecutionCleanupError:
                state, error = TurnState.FAILED, "ExecutionCleanupError"
        proposals = self._run_proposals.pop(run_id, [])
        if self._tool_orchestrator is not None:
            for proposal_id in proposals:
                await self._tool_orchestrator.discard_unstarted(proposal_id)
        self._batches.pop(run_id, None)
        self._batch_results.pop(run_id, None)
        self._seen_calls.pop(run_id, None)
        history = self._message_histories.pop(run_id, None)
        assert self._agent_runs is not None
        if history is not None:
            # Invalid duplicate/excess batches are never accepted as canonical journal calls.
            if error == "duplicate_or_excess_tool_calls" and history and history[-1].tool_calls:
                history.pop()
            await self._agent_runs.checkpoint(run_id, history)
        await self._agent_runs.finish_journal(run_id)
        self._agent_steps.pop(session_id, None)
        if self._run_ids.get(session_id) == run_id:
            self._run_ids.pop(session_id, None)
        assert self._agent_runs is not None
        await self._agent_runs.append(
            run_id,
            "final",
            {
                "text": text,
                "state": state.value,
                **(
                    {"rejected_tool_calls": [asdict(call) for call in rejected_tool_calls]}
                    if rejected_tool_calls
                    else {}
                ),
            },
            state={
                TurnState.COMPLETED: AgentRunState.COMPLETED,
                TurnState.CANCELLED: AgentRunState.CANCELLED,
                TurnState.FAILED: AgentRunState.FAILED,
            }[state],
            error=error,
        )
        await self._broadcast_stream(
            stream_id,
            {
                "type": "assistant_terminal",
                "session_id": session_id,
                "state": state,
                "error": error,
                **({"prosody": prosody} if prosody is not None else {}),
            },
        )

    async def cancel(self, _turn_id: str, reason: str, *, session_id: str | None = None) -> None:
        conversation = self._conversation
        if conversation is None:
            return
        if self._runtime_profile == "candidate":
            for target_session, run_id in tuple(self._run_ids.items()):
                if session_id is not None and target_session != session_id:
                    continue
                await self._finish_candidate(run_id, target_session, TurnState.CANCELLED, reason)
                await conversation.cancel(target_session)
        for target_session in tuple(self._active_sessions):
            if session_id is None or target_session == session_id:
                await conversation.cancel(target_session)
        if session_id is not None and any(
            other != session_id for other in (*self._active_sessions, *self._run_ids)
        ):
            # One shared body: stopping one activity keeps another session's voice and motion.
            return
        await self._body.cancel("active", reason)

    async def invalidate_memory_context(self) -> None:
        if self._summary_enabled:
            await self.cancel("active", "memory sources changed")

    async def memory_corrected(self, source: UserTextEvent, memory: Memory) -> None:
        await self._ensure_core()
        assert self._store is not None
        assert self._affect_repository is not None
        assert self._relationships is not None
        event = MemoryCorrectedEvent(
            event_id=uuid4(),
            type="memory.corrected.v1",
            source="siro.memory",
            occurred_at=source.occurred_at,
            received_at=datetime.now(UTC),
            trace_id=source.trace_id,
            causation_id=source.event_id,
            session_id=source.session_id,
            turn_id=source.turn_id,
            sequence=source.sequence + 1,
            priority=Priority.INTERACTIVE,
            privacy=source.privacy,
            payload=MemoryCorrectedPayload(
                memory_id=memory.memory_id,
                revision=memory.revision,
                reason="owner corrected a stored memory",
                importance=0.8,
            ),
        )
        result = await AffectCoordinator(
            self._store,
            self._affect_repository,
            self._relationships,
            self._affect,
        ).ingest(event)
        relationship = await self._relationships.current("siro", "owner")
        conflict = RelationshipSystem.update(
            relationship,
            RelationshipEvent.CONFLICT,
            str(event.event_id),
            intensity=result.state.intensity,
        )
        await self._relationships.record("siro", "owner", conflict)
        repair = RelationshipSystem.update(
            conflict.state,
            RelationshipEvent.REPAIR,
            str(event.event_id),
            intensity=result.state.intensity,
        )
        await self._relationships.record("siro", "owner", repair)
        expression = self._expression.decide(
            result, expression_context_from_text("owner correction")
        )
        await self._body.set_emotion(EmotionIntent(expression.expression, expression.intensity))
        await self._hub.broadcast(
            {
                "type": "memory_correction_affect",
                "memory_id": str(memory.memory_id),
                "emotion": result.state.emotion,
                "intensity": result.state.intensity,
                "coping": result.coping.strategy.value,
                "relationship": {
                    "trust": repair.state.trust,
                    "rupture": repair.state.rupture,
                    "repair_history": repair.state.repair_history,
                },
                "source_id": str(event.event_id),
            }
        )

    async def startup(self) -> None:
        if self._runtime_profile == "candidate":
            await self._ensure_core()

    async def activity_snapshot(self, limit: int) -> dict[str, object]:
        # A monitor view must not initialize, migrate or reconcile the store on demand.
        if self._store is None:
            return {"status": "unavailable"}
        return await ActivityMonitor(self._store).snapshot(limit=limit)

    async def activity_changes(self, after: int, limit: int) -> dict[str, object]:
        if self._store is None:
            return {"status": "unavailable"}
        return await ActivityMonitor(self._store).changes(after=after, limit=limit)

    async def stop_activity(self, activity_id: str, reason: str) -> dict[str, object]:
        """Stop one activity; the run id is its generation, so a finished one is never reused."""
        if self._store is None:
            return {"status": "unavailable"}
        monitor = ActivityMonitor(self._store)
        view = await monitor.get(activity_id)
        if view is None:
            return {"status": "not_found"}
        if view["state"] not in ACTIVE_STATES:
            return {"status": "stale", "state": view["state"]}
        if view["kind"] == "agent_run":
            sessions = [s for s, run_id in self._run_ids.items() if run_id == activity_id]
            if not sessions:
                # Durable state says active but no live owner here: nothing safe to cancel.
                return {"status": "not_owned", "state": view["state"]}
            await self.cancel("active", reason, session_id=sessions[0])
            after = await monitor.get(activity_id)
            return {
                "status": "cancelling",
                "state": None if after is None else after["state"],
                "session_id": sessions[0],
            }
        if self._tool_orchestrator is None or view["state"] not in {"proposed", "queued"}:
            # A standalone approved tool runs inside its approval request; it has no fence.
            return {"status": "not_owned", "state": view["state"]}
        await self._tool_orchestrator.discard_unstarted(activity_id)
        after = await monitor.get(activity_id)
        return {"status": "cancelling", "state": None if after is None else after["state"]}

    async def recovery_readback(self, session_id: str) -> dict[str, object] | None:
        await self._ensure_core()
        assert self._agent_runs is not None
        return await self._agent_runs.readback(session_id)

    async def improvement_proposal(self, session_id: str) -> dict[str, object]:
        # A read-only view must not initialize/migrate/reconcile the store on demand.
        if (
            self._runtime_profile != "candidate"
            or not self._session_restore_enabled
            or self._agent_runs is None
        ):
            return {"status": "unavailable", "proposal": None}
        from siro.core.evolution import propose_runtime_improvement

        fact = await self._agent_runs.recent_runtime_status(session_id, privacy=self._privacy.value)
        proposal = propose_runtime_improvement(fact)
        return {
            "status": "awaiting_investigation" if proposal is not None else "no_supported_evidence",
            "proposal": proposal,
        }

    async def _journal_event(self, run_id: str, call_id: str, phase: str, value: object) -> None:
        assert self._agent_runs is not None
        if phase == "dispatch":
            await self._agent_runs.record_dispatch(run_id, call_id)
        else:
            await self._agent_runs.record_observation(run_id, call_id, value)

    async def run_agent_plan(self, session_id: str, goal: str) -> PlanReport | None:
        """R05 planner entry; None unless SIRO_AGENT_PLANNER_ENABLED=1 and a factory is wired."""
        if not self._planner_on() or self._agent_planner_factory is None:
            return None
        await self._ensure_core()
        assert self._agent_runs is not None
        planner = self._planner()
        assert planner is not None
        CURRENT_SESSION.set(session_id)
        return await planner.run(session_id, goal)

    def _planner_on(self) -> bool:
        return planner_enabled(default=self._flag_default)

    @property
    def _flag_default(self) -> str:
        return "1" if self._runtime_profile == "candidate" else "0"

    def _planner(self) -> Coordinator | None:
        if self._agent_planner is None and self._agent_planner_factory is not None:
            assert self._agent_runs is not None
            self._agent_planner = self._agent_planner_factory(self._agent_runs)
            if self._checkpoints is not None:
                self._agent_planner.add_hook(make_checkpoint_hook(self._checkpoints))
        return self._agent_planner

    async def _resume_plans(self) -> None:
        """Resume unfinished read-only plans after a restart (SIRO_AGENT_RESUME_ENABLED=1)."""
        planner = self._planner()
        if self._checkpoints is None or planner is None:
            return
        try:
            await ResumeWorker(
                self._checkpoints,
                planner,
                enabled=lambda: resume_enabled(default=self._flag_default),
            ).resume_all()
        except Exception:
            logging.getLogger(__name__).exception("agent plan resume failed")

    async def _ensure_core(self) -> None:
        if self._core is not None:
            return
        async with self._initializing:
            if self._core is not None:
                return
            store = SQLiteStore(self._data_dir / "siro.db")
            await store.initialize()
            self._store = store
            self._affect_repository = SQLiteAffectRepository(store)
            self._relationships = SQLiteRelationshipRepository(store)
            self._agent_runs = SQLiteAgentRunRepository(store)
            if self._runtime_profile == "candidate":
                await self._agent_runs.reconcile()
                if self._tool_orchestrator is not None:
                    self._tool_orchestrator.journal_hook = self._journal_event
            if (
                resume_enabled(default=self._flag_default)
                and self._planner_on()
                and self._agent_planner_factory is not None
            ):
                self._checkpoints = SQLiteCheckpointRepository(store)
                await self._checkpoints.reconcile()
                self._resume_task = asyncio.create_task(self._resume_plans())
            identities = SQLiteIdentityRepository(store)
            if await identities.get("siro") is None:
                await IdentityService(identities).create(
                    "siro",
                    ImmutableCore(
                        name="SIRO",
                        baseline_identity="誠實、溫暖、會清楚標示能力與記憶來源的數位夥伴",
                        core_values=("誠實", "尊重使用者控制", "不假裝完成"),
                        creator_relationship="由本機 owner 建立的持續夥伴",
                    ),
                    now=datetime.now(UTC),
                )
            if not await self._affect_repository.preferences("siro", "siro"):
                for subject, strength in (
                    ("探索與理解新事物", 0.75),
                    ("有來源且誠實的回答", 0.9),
                ):
                    await self._affect_repository.put_preference(
                        Preference(
                            str(uuid4()),
                            "siro",
                            "siro",
                            "siro",
                            subject,
                            1.0,
                            strength,
                            1.0,
                            "general",
                            "committed",
                            ("identity-core:1",),
                            1,
                        )
                    )
            # A reply cut at the model's output limit is shown as unfinished, so the cap is
            # generous; chatty or reasoning models can exceed the 512 default.
            self._conversation = ConversationEngine(
                self._model,
                SQLiteConversationRepository(store),
                max_output_tokens=int(os.environ.get("SIRO_MODEL_MAX_OUTPUT_TOKENS", "1536")),
            )
            self._memory_service = MemoryService(SQLiteMemoryRepository(store))
            self._core = CompanionCore(
                identities,
                self._memory_service,
                self._conversation,
            )
