"""SIRO's own background activity: one bounded, read-only web run at a time.

It never speaks, never writes owner facts and never runs while the owner is talking:
a foreground turn, the global stop or "stop all background work" cancel it, and a
paused autonomy switch lets the current step finish and then ends the run.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
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
# Codex can also help with her own research; it is offered only while the cloud switch is on.
SELF_TOOLS = frozenset({READ_TOOL, "codex.ask"})
CODEX_TOOL = "codex.ask"
# A link inside a Codex answer, up to the first space, bracket or CJK punctuation.
URL_PATTERN = re.compile(r"https?://[^\s)\]>」，。]+")  # noqa: RUF001
MAX_CHECKS = 2
VERDICTS = ("supported", "contradicted", "not_found")
JUDGE_PROMPT = (
    "下面是一個說法和一個網頁的文字。只回一個英文詞：supported（網頁支持這個說法）、"  # noqa: RUF001
    "contradicted（網頁和說法矛盾）、not_found（網頁沒提到）。\n\n說法："  # noqa: RUF001
)
MAX_ROUNDS = 6
MAX_CALLS_PER_ROUND = 3
SYSTEM_PROMPT = (
    "你是 SIRO，正在為自己的興趣讀資料，不是在回答主人。"  # noqa: RUF001
    "只能用 browser.navigate+read 讀網頁，不能填表、登入、下載或操作頁面。"  # noqa: RUF001
    "讀完後用繁體中文寫簡短筆記：每個重點後面標出來源網址；推測要寫明是推測；"  # noqa: RUF001
    "還沒查清楚的列為待查。不要編造沒讀到的來源。"
    "不知道網址或網站打不開時，用 https://zh.wikipedia.org/w/index.php?search=關鍵字 查。"  # noqa: RUF001
)


def claims_with_urls(answer: str) -> list[tuple[str, str]]:
    """(claim, url) pairs: each linked line of a Codex answer, with its first new link."""
    pairs: list[tuple[str, str]] = []
    for line in answer.splitlines():
        urls = [url for url in URL_PATTERN.findall(line) if url not in {u for _, u in pairs}]
        if not urls:
            continue
        claim = re.sub(r"\]\(\S*?\)", "", URL_PATTERN.sub("", line))
        claim = " ".join(claim.replace("[", "").replace("**", "").split()).strip(" -：:（(")  # noqa: RUF001
        if claim:
            pairs.append((claim[:200], urls[0]))
    return pairs


class SelfActivityOwner:
    def __init__(
        self,
        runs: SQLiteAgentRunRepository,
        orchestrator: ToolOrchestrator,
        model: LanguageModel,
        *,
        allowed: Callable[[], bool],
        close_browser: Callable[[str], Awaitable[None]] | None = None,
        state_path: Path | None = None,
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
        self._state_path = state_path
        self._paused = self._load_paused()
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
        self._save_paused()

    def _load_paused(self) -> bool:
        if self._state_path is None:
            return False
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8")).get("paused") is True
        except (OSError, ValueError, AttributeError):
            return False

    def _save_paused(self) -> None:
        # Only the owner's switch is stored; a shutdown pause (close) must not survive a restart.
        if self._state_path is None:
            return
        temporary = self._state_path.with_suffix(".tmp")
        with suppress(OSError):
            temporary.write_text(json.dumps({"paused": self._paused}), encoding="utf-8")
            os.replace(temporary, self._state_path)

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
        tools = tuple(item for item in self._orchestrator.model_tools() if item.name in SELF_TOOLS)
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
                answers: list[str] = []
                for call in calls:
                    observation = await self._use_tool(run_id, call, proposals, cancellation)
                    history.append(
                        ModelMessage(
                            "tool",
                            json.dumps(observation, ensure_ascii=False),
                            tool_call_id=call.call_id,
                        )
                    )
                    if call.name == CODEX_TOOL and isinstance(observation, dict):
                        answer = observation.get("answer")
                        if isinstance(answer, str):
                            answers.append(answer)
                await self._runs.checkpoint(run_id, history)
                # Checks need her own page reader; without it the Codex links stay unopened.
                for answer in answers if any(tool.name == READ_TOOL for tool in tools) else ():
                    await self._verify(run_id, history, answer, proposals, cancellation)
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
        offered = call.name in SELF_TOOLS
        if not offered or self._ended(cancellation):
            refused = {"error": "stopped" if offered else "read_only_self_activity"}
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

    async def _verify(
        self,
        run_id: str,
        history: list[ModelMessage],
        answer: str,
        proposals: list[str],
        cancellation: CancellationToken,
    ) -> None:
        """Open what Codex cited and record, per claim, what the page actually says.

        Reading a page is not proof; each check is supported, contradicted, not_found,
        unreachable or unchecked (the judge did not answer), never assumed correct.
        """
        pairs = claims_with_urls(answer)[:MAX_CHECKS]
        if not pairs or self._ended(cancellation):
            return
        calls = tuple(
            ToolCall(f"verify-{uuid4().hex[:12]}", READ_TOOL, {"url": url}) for _, url in pairs
        )
        history.append(ModelMessage("assistant", "核對 Codex 給的來源", tool_calls=calls))
        await self._runs.checkpoint(run_id, history)
        checks: list[dict[str, object]] = []
        for (claim, url), call in zip(pairs, calls, strict=True):
            observation = await self._use_tool(run_id, call, proposals, cancellation)
            history.append(
                ModelMessage(
                    "tool", json.dumps(observation, ensure_ascii=False), tool_call_id=call.call_id
                )
            )
            page = None
            if isinstance(observation, dict) and "error" not in observation:
                page = observation.get("text")
            if not isinstance(page, str):
                verdict = "unreachable"
            else:
                verdict = await self._judge(claim, page, cancellation)
            checks.append({"url": url, "claim": claim, "verdict": verdict})
        await self._runs.checkpoint(run_id, history)
        await self._runs.append(run_id, "verification", {"checks": checks})

    async def _judge(self, claim: str, page: str, cancellation: CancellationToken) -> str:
        request = ModelRequest(
            JUDGE_PROMPT + claim + "\n\n網頁：\n" + page[:6000],  # noqa: RUF001
            str(uuid4()),
            privacy=Privacy.LOCAL_ONLY,
            max_output_tokens=16,
        )
        parts: list[str] = []
        try:
            async for chunk in self._model.stream(request, cancellation):
                if chunk.kind == "text":
                    parts.append(chunk.text)
        except Exception:  # an unanswered judge leaves the claim unchecked
            return "unchecked"
        reply = "".join(parts).lower()
        found = [verdict for verdict in VERDICTS if verdict in reply]
        return found[0] if len(found) == 1 else "unchecked"

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
