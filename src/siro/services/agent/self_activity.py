"""SIRO's own background activity: one bounded, read-only web run at a time.

It never speaks, never writes owner facts and never runs while the owner is talking:
a foreground turn, the global stop or "stop all background work" cancel it, and a
paused autonomy switch lets the current step finish and then ends the run.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
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
from siro.services.agent.runs import AgentRunState, SQLiteAgentRunRepository
from siro.services.tools.execution import ExecutionCleanupError
from siro.services.tools.orchestrator import PriorOutcomeUnknown, ToolOrchestrator

SELF_SESSION = "siro.self"
READ_TOOL = "browser.navigate+read"
MAX_ROUNDS = 6
MAX_CALLS_PER_ROUND = 3
SYSTEM_PROMPT = (
    "你是 SIRO，正在為自己的興趣讀資料，不是在回答主人。"  # noqa: RUF001
    "只能用 browser.navigate+read 讀網頁，不能填表、登入、下載或操作頁面。"  # noqa: RUF001
    "讀完後用繁體中文寫簡短筆記：每個重點後面標出來源網址；推測要寫明是推測；"  # noqa: RUF001
    "還沒查清楚的列為待查。不要編造沒讀到的來源。"
    "不知道網址或網站打不開時，用 https://zh.wikipedia.org/w/index.php?search=關鍵字 查。"  # noqa: RUF001
)


class SelfActivityOwner:
    def __init__(
        self,
        runs: SQLiteAgentRunRepository,
        orchestrator: ToolOrchestrator,
        model: LanguageModel,
        *,
        allowed: Callable[[], bool],
        close_browser: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._runs = runs
        self._orchestrator = orchestrator
        self._model = model
        self._allowed = allowed
        self._close_browser = close_browser
        self._work: asyncio.Task[None] | None = None
        self._run_id: str | None = None
        self._cancellation: CancellationToken | None = None
        self._stop_reason: str | None = None
        self._paused = False
        self._control = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._work is not None and not self._work.done()

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def active_run(self) -> str | None:
        return self._run_id if self.busy else None

    async def start(
        self, goal: str, why: str | None = None, source: str | None = None
    ) -> str | None:
        """Start one run for a goal SIRO chose; refused while paused, busy or not allowed."""
        async with self._control:
            # Without the journal hook a dispatch could not be audited, so nothing starts.
            if (
                self._paused
                or self.busy
                or not self._allowed()
                or self._orchestrator.journal_hook is None
            ):
                return None
            run = await self._runs.start(
                SELF_SESSION,
                goal,
                max_steps=MAX_ROUNDS * (MAX_CALLS_PER_ROUND + 2) + 1,
                runtime_backend=self._model.name,
                privacy=Privacy.LOCAL_ONLY.value,
                max_model_rounds=MAX_ROUNDS,
            )
            # Why she chose it is shown on the activity page next to "SIRO 自己想做的".
            await self._runs.append(run.run_id, "self_topic", {"why": why, "source": source})
            self._run_id, self._stop_reason = run.run_id, None
            self._cancellation = CancellationToken()
            self._orchestrator.start_run(run.run_id, SELF_SESSION)
            self._work = asyncio.create_task(
                self._run(run.run_id, goal, self._cancellation), name="siro-self-activity"
            )
            return run.run_id

    async def set_paused(self, paused: bool) -> None:
        # Pausing stops new work; the running step finishes, then the run ends (explicit policy).
        self._paused = paused

    async def stop(self, reason: str, run_id: str | None = None) -> bool:
        """Cancel the current run (or only `run_id`); returns whether something was stopped."""
        work = self._work
        if work is None or work.done() or (run_id is not None and run_id != self._run_id):
            return False
        self._stop_reason = reason
        if self._cancellation is not None:
            self._cancellation.cancel()
        if self._run_id is not None:
            with suppress(ExecutionCleanupError):
                await self._orchestrator.cancel_run(self._run_id)
        await asyncio.gather(work, return_exceptions=True)
        return True

    async def foreground(self, reason: str = "foreground") -> None:
        await self.stop(reason)

    async def close(self) -> None:
        self._paused = True
        await self.stop("shutdown")

    async def _run(self, run_id: str, goal: str, cancellation: CancellationToken) -> None:
        history = [ModelMessage("system", SYSTEM_PROMPT), ModelMessage("user", goal)]
        proposals: list[str] = []
        state, text = AgentRunState.FAILED, ""
        error: str | None = "agent_step_limit"
        tools = tuple(item for item in self._orchestrator.model_tools() if item.name == READ_TOOL)
        try:
            for _ in range(MAX_ROUNDS):
                if self._ended(cancellation):
                    break
                try:
                    await self._runs.reserve_round(run_id)
                except RuntimeError:
                    break
                text, calls = await self._think(history, tools, cancellation)
                if self._ended(cancellation):
                    break
                history.append(ModelMessage("assistant", text, tool_calls=calls))
                await self._runs.checkpoint(run_id, history)
                if not calls:
                    state, error = AgentRunState.COMPLETED, None
                    break
                for call in calls:
                    observation = await self._use_tool(run_id, call, proposals, cancellation)
                    history.append(
                        ModelMessage(
                            "tool",
                            json.dumps(observation, ensure_ascii=False),
                            tool_call_id=call.call_id,
                        )
                    )
                await self._runs.checkpoint(run_id, history)
            if self._ended(cancellation) and state is not AgentRunState.COMPLETED:
                paused = "autonomy_paused" if self._paused else "tools_disabled"
                state, error = AgentRunState.CANCELLED, self._stop_reason or paused
        except asyncio.CancelledError:
            state, error = AgentRunState.CANCELLED, self._stop_reason or "cancelled"
        except Exception as failure:
            state, error = AgentRunState.FAILED, type(failure).__name__
        finally:
            await self._finish(run_id, state, error, text, proposals)

    def _ended(self, cancellation: CancellationToken) -> bool:
        return cancellation.cancelled or self._paused or not self._allowed()

    async def _think(
        self,
        history: list[ModelMessage],
        tools: tuple[ToolDefinition, ...],
        cancellation: CancellationToken,
    ) -> tuple[str, tuple[ToolCall, ...]]:
        request = ModelRequest(
            "",
            str(uuid4()),
            privacy=Privacy.LOCAL_ONLY,
            max_output_tokens=1024,
            tools=tools,
            messages=tuple(history),
        )
        parts: list[str] = []
        calls: list[ToolCall] = []
        async for chunk in self._model.stream(request, cancellation):
            if chunk.kind == "text":
                parts.append(chunk.text)
            elif chunk.kind == "tool_request" and chunk.tool_call is not None:
                calls.append(chunk.tool_call)
        return "".join(parts), tuple(calls[:MAX_CALLS_PER_ROUND])

    async def _use_tool(
        self,
        run_id: str,
        call: ToolCall,
        proposals: list[str],
        cancellation: CancellationToken,
    ) -> object:
        if call.name != READ_TOOL or self._ended(cancellation):
            refused = {"error": "stopped" if call.name == READ_TOOL else "read_only_self_activity"}
            await self._runs.record_observation(run_id, call.call_id, refused)
            return refused
        proposal = await self._orchestrator.propose(
            SELF_SESSION, call, risk="observe/read-only", run_id=run_id
        )
        self._orchestrator.bind_proposal(run_id, proposal)
        await self._runs.bind_call(run_id, call.call_id, proposal.proposal_id)
        proposals.append(proposal.proposal_id)
        try:
            await self._orchestrator.resolve(
                proposal.proposal_id, approved=True, arguments=proposal.arguments, automatic=True
            )
        except PriorOutcomeUnknown:
            await self._orchestrator.discard_unstarted(proposal.proposal_id)
            return {"error": "prior_outcome_unknown"}
        if self._ended(cancellation):
            await self._orchestrator.discard_unstarted(proposal.proposal_id)
            return {"error": "stopped"}
        result = await self._orchestrator.execute(proposal.proposal_id)
        observation = result.model_observation()
        await self._runs.record_observation(run_id, call.call_id, observation)
        return observation

    async def _finish(
        self,
        run_id: str,
        state: AgentRunState,
        error: str | None,
        text: str,
        proposals: list[str],
    ) -> None:
        if state is not AgentRunState.COMPLETED:
            with suppress(ExecutionCleanupError):
                await self._orchestrator.cancel_run(run_id)
        for proposal_id in proposals:
            await self._orchestrator.discard_unstarted(proposal_id)
        await self._runs.finish_journal(run_id)
        await self._runs.append(
            run_id,
            "final",
            {"text": text if state is AgentRunState.COMPLETED else "", "state": state.value},
            state=state,
            error=error,
        )
        if self._close_browser is not None:
            with suppress(Exception):
                await self._close_browser(SELF_SESSION)
        if self._run_id == run_id:
            self._run_id, self._cancellation = None, None
