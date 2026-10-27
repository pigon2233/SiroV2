"""Adapters binding the R05 coordinator to the existing orchestrator, journal and models."""

from __future__ import annotations

import os
from uuid import uuid4

from siro.ports.models import (
    CancellationToken,
    LanguageModel,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
)
from siro.services.agent.planning import ModelReply, Subtask, ToolRunResult
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.tools.orchestrator import PriorOutcomeUnknown, ProposalState, ToolOrchestrator

PLANNER_FLAG = "SIRO_AGENT_PLANNER_ENABLED"


def planner_enabled(env: dict[str, str] | None = None) -> bool:
    return (os.environ if env is None else env).get(PLANNER_FLAG, "0").strip() == "1"


class CloudPlannerModel:
    """Runs planner/verifier/reporter on the cloud model; reports the model that answered.

    `actual_model` is read from the model after the stream (a failover wrapper may expose
    `last_model_name`); otherwise the configured name is reported.
    """

    def __init__(self, model: LanguageModel, *, max_output_tokens: int = 1536) -> None:
        self._model = model
        self._max = max_output_tokens

    async def complete(self, role: str, prompt: str) -> ModelReply:
        request = ModelRequest(
            prompt=prompt,
            generation_id=str(uuid4()),
            privacy=Privacy.CLOUD_ALLOWED,
            max_output_tokens=self._max,
        )
        parts: list[str] = []
        async for chunk in self._model.stream(request, CancellationToken()):
            if chunk.kind == "text":
                parts.append(chunk.text)
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError(f"{role}_empty_reply")
        return ModelReply(text, str(getattr(self._model, "last_model_name", self._model.name)))


class OrchestratorToolPort:
    """One child journal run per subtask; tools go through propose -> resolve -> execute."""

    def __init__(
        self,
        orchestrator: ToolOrchestrator,
        runs: SQLiteAgentRunRepository,
        *,
        backend: str,
        privacy: str = "cloud_allowed",
    ) -> None:
        self._orch, self._runs = orchestrator, runs
        self._backend, self._privacy = backend, privacy
        self._plan_runs: dict[str, list[str]] = {}
        if orchestrator.journal_hook is None:
            orchestrator.journal_hook = self._journal

    async def _journal(self, run_id: str, call_id: str, phase: str, value: object) -> None:
        if phase == "dispatch":
            await self._runs.record_dispatch(run_id, call_id)
        else:
            await self._runs.record_observation(run_id, call_id, value)

    async def run_read(self, plan_id: str, subtask: Subtask, session_id: str) -> ToolRunResult:
        run = await self._runs.start(
            session_id,
            f"plan {plan_id} {subtask.subtask_id}: {subtask.title}",
            max_steps=2,
            runtime_backend=self._backend,
            privacy=self._privacy,
            max_model_rounds=1,
        )
        run_id = run.run_id
        self._plan_runs.setdefault(plan_id, []).append(run_id)
        call = ToolCall(f"{plan_id}:{subtask.subtask_id}", subtask.capability, subtask.arguments)
        proposal_id: str | None = None
        try:
            await self._runs.reserve_round(run_id)
            self._orch.start_run(run_id, session_id)
            await self._runs.checkpoint(run_id, [ModelMessage("assistant", tool_calls=(call,))])
            proposal = await self._orch.propose(
                session_id, call, risk="observe/read-only", run_id=run_id
            )
            proposal_id = proposal.proposal_id
            self._orch.bind_proposal(run_id, proposal)
            await self._runs.bind_call(run_id, call.call_id, proposal_id)
            await self._orch.resolve(
                proposal_id, approved=True, arguments=proposal.arguments, automatic=True
            )
            done = await self._orch.execute(proposal_id)
            if done.state is ProposalState.COMPLETED:
                return ToolRunResult(run_id, proposal_id, done.observation)
            return ToolRunResult(run_id, proposal_id, None, done.error or done.state.value)
        except PriorOutcomeUnknown:
            return ToolRunResult(run_id, proposal_id, None, "prior_outcome_unknown")
        except Exception as error:
            return ToolRunResult(run_id, proposal_id, None, type(error).__name__)
        finally:
            await self._runs.finish_journal(run_id)

    async def cancel(self, plan_id: str) -> None:
        for run_id in self._plan_runs.get(plan_id, ()):
            await self._orch.cancel_run(run_id)
