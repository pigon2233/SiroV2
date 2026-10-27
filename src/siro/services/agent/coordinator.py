"""Bounded plan -> read-only subtasks -> verified results -> report, cancellable."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from dataclasses import replace
from uuid import uuid4

from siro.services.agent.planning import (
    MAX_SUBTASKS,
    CheckpointHook,
    CheckpointPoint,
    Plan,
    PlanCheckpoint,
    PlanError,
    PlannerModel,
    PlanReport,
    PlanState,
    Source,
    Subtask,
    SubtaskResult,
    SubtaskState,
    SubtaskToolPort,
    Verdict,
)

MAX_OBSERVATION_CHARS = 6000

PLAN_PROMPT = (
    "Split the goal into 1-{max} read-only subtasks. Reply with JSON only: "
    '{{"subtasks":[{{"title":"..","capability":"<one of {tools}>",'
    '"arguments":{{...}},"depends_on":["s1"],"expect":"what evidence proves it"}}]}}\n'
    "Subtasks are named s1, s2, s3 in order; depends_on may only name earlier ones.\n"
    "Tool schemas: {schemas}\nGoal: {goal}"
)
VERIFY_PROMPT = (
    "Check the subtask result against its expectation using ONLY the observation. "
    'Reply with JSON only: {{"verified":true|false,"reason":"..","quotes":["verbatim '
    'snippets copied from the observation"]}}\n'
    "Expectation: {expect}\nObservation: {observation}"
)
REPORT_PROMPT = (
    "Write a short final report in the goal's language. Mention failed or blocked subtasks "
    "honestly; claim only what verified results support.\nGoal: {goal}\nResults: {results}"
)

_FINAL = frozenset({SubtaskState.VERIFIED, SubtaskState.FAILED, SubtaskState.BLOCKED})


def _json(text: str) -> dict[str, object]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        value = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        value = None
    if not isinstance(value, dict):
        raise PlanError("model_reply_not_json")
    return value


def _text(observation: object) -> str:
    if isinstance(observation, str):
        return observation
    return json.dumps(observation, ensure_ascii=False, sort_keys=True)


def _ref(subtask: Subtask) -> str:
    for key in ("url", "path"):
        value = subtask.arguments.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(subtask.arguments, ensure_ascii=False, sort_keys=True)


class Coordinator:
    def __init__(
        self,
        planner: PlannerModel,
        tools: SubtaskToolPort,
        *,
        read_tools: dict[str, dict[str, object]],
        expected_models: frozenset[str] = frozenset(),
        hook: CheckpointHook | None = None,
        max_subtasks: int = MAX_SUBTASKS,
    ) -> None:
        if not 1 <= max_subtasks <= MAX_SUBTASKS:
            raise ValueError("max_subtasks must be 1..3")
        self._planner, self._tools, self._hook = planner, tools, hook
        self._read_tools = dict(read_tools)  # capability -> input schema (read-only only)
        self._expected = expected_models
        self._max = max_subtasks
        self._cancelled: set[str] = set()
        self._active: dict[str, asyncio.Task[PlanReport]] = {}
        self._partial: dict[str, tuple[SubtaskResult, ...]] = {}

    def add_hook(self, hook: CheckpointHook) -> None:
        """Chain another checkpoint hook after the existing one (R06 durable checkpoints)."""
        previous = self._hook
        if previous is None:
            self._hook = hook
            return

        async def both(cp: PlanCheckpoint) -> None:
            await previous(cp)
            await hook(cp)

        self._hook = both

    def _degraded(self, model: str) -> bool:
        return bool(self._expected) and model not in self._expected

    async def _emit(
        self,
        plan_id: str,
        point: CheckpointPoint,
        state: PlanState,
        plan: Plan | None,
        results: Iterable[SubtaskResult],
        subtask_id: str | None = None,
    ) -> None:
        if self._hook is not None:
            await self._hook(
                PlanCheckpoint(plan_id, point, state, plan, tuple(results), subtask_id)
            )

    async def cancel(self, plan_id: str) -> None:
        self._cancelled.add(plan_id)  # fence new dispatch before the first await
        task = self._active.get(plan_id)
        await self._tools.cancel(plan_id)
        if task is not None and not task.done():
            task.cancel()

    async def run(
        self, session_id: str, goal: str, *, resume: PlanCheckpoint | None = None
    ) -> PlanReport:
        plan_id = resume.plan_id if resume is not None else str(uuid4())
        task = asyncio.ensure_future(self._run(plan_id, session_id, goal, resume))
        self._active[plan_id] = task
        try:
            return await task
        except asyncio.CancelledError:
            if plan_id not in self._cancelled:
                raise
            return await self._cancelled_report(plan_id)
        finally:
            self._active.pop(plan_id, None)
            self._partial.pop(plan_id, None)

    async def _cancelled_report(self, plan_id: str) -> PlanReport:
        final = tuple(
            r if r.state in _FINAL else replace(r, state=SubtaskState.CANCELLED)
            for r in self._partial.get(plan_id, ())
        )
        await self._emit(plan_id, CheckpointPoint.PLAN_FINISHED, PlanState.CANCELLED, None, final)
        return PlanReport(plan_id, PlanState.CANCELLED, final, "cancelled", (), False)

    async def _plan(self, plan_id: str, goal: str) -> Plan:
        reply = await self._planner.complete(
            "planner",
            PLAN_PROMPT.format(
                max=self._max,
                tools=", ".join(self._read_tools),
                schemas=json.dumps(self._read_tools, ensure_ascii=False),
                goal=goal,
            ),
        )
        raw = _json(reply.text).get("subtasks")
        if not isinstance(raw, list) or not 1 <= len(raw) <= self._max:
            raise PlanError("subtask_count")
        subtasks: list[Subtask] = []
        for index, item in enumerate(raw, 1):
            if not isinstance(item, dict):
                raise PlanError("subtask_shape")
            capability, args = item.get("capability"), item.get("arguments", {})
            if capability not in self._read_tools:
                raise PlanError("capability_not_read_only")
            if not isinstance(args, dict):
                raise PlanError("arguments_shape")
            deps = tuple(str(d) for d in item.get("depends_on") or [])
            if any(d not in {s.subtask_id for s in subtasks} for d in deps):
                raise PlanError("bad_dependency")
            subtasks.append(
                Subtask(
                    f"s{index}",
                    str(item.get("title", f"s{index}")),
                    str(capability),
                    args,
                    deps,
                    str(item.get("expect", "")),
                )
            )
        return Plan(
            plan_id, goal, tuple(subtasks), reply.model_name, self._degraded(reply.model_name)
        )

    async def _run(
        self, plan_id: str, session_id: str, goal: str, resume: PlanCheckpoint | None
    ) -> PlanReport:
        if resume is not None and resume.plan is not None:
            plan = resume.plan
            done = {r.subtask_id: r for r in resume.results}
        else:
            try:
                plan = await self._plan(plan_id, goal)
            except asyncio.CancelledError:
                raise
            except Exception as error:  # a planner failure is a visible terminal state
                await self._emit(plan_id, CheckpointPoint.PLAN_FINISHED, PlanState.FAILED, None, ())
                return PlanReport(plan_id, PlanState.FAILED, (), type(error).__name__, (), False)
            done = {}
            await self._emit(plan_id, CheckpointPoint.PLAN_CREATED, PlanState.RUNNING, plan, ())
        models = [plan.planner_model]
        degraded = plan.degraded
        results: dict[str, SubtaskResult] = {}
        for subtask in plan.subtasks:
            self._partial[plan_id] = tuple(results.values())
            if plan_id in self._cancelled:
                raise asyncio.CancelledError
            result = await self._execute(
                plan, subtask, session_id, results, done.get(subtask.subtask_id)
            )
            results[subtask.subtask_id] = result
            if result.verdict is not None:
                models.append(result.verdict.verifier_model)
                degraded = degraded or result.verdict.degraded
        self._partial[plan_id] = tuple(results.values())
        ordered = tuple(results[s.subtask_id] for s in plan.subtasks)
        state = (
            PlanState.COMPLETED
            if all(r.state is SubtaskState.VERIFIED for r in ordered)
            else PlanState.FAILED
        )
        summary, report_model = await self._summarize(plan, ordered)
        models.append(report_model)
        degraded = degraded or self._degraded(report_model)
        await self._emit(plan_id, CheckpointPoint.PLAN_FINISHED, state, plan, ordered)
        return PlanReport(plan_id, state, ordered, summary, tuple(dict.fromkeys(models)), degraded)

    async def _execute(
        self,
        plan: Plan,
        subtask: Subtask,
        session_id: str,
        results: dict[str, SubtaskResult],
        prior: SubtaskResult | None,
    ) -> SubtaskResult:
        pid, sid = plan.plan_id, subtask.subtask_id

        async def finish(result: SubtaskResult, point: CheckpointPoint) -> SubtaskResult:
            await self._emit(
                pid, point, PlanState.RUNNING, plan, [*results.values(), result], result.subtask_id
            )
            return result

        if prior is not None and prior.state is SubtaskState.VERIFIED:
            return prior
        bad = [d for d in subtask.depends_on if results[d].state is not SubtaskState.VERIFIED]
        if bad:
            blocked = SubtaskResult(
                sid, SubtaskState.BLOCKED, error="dependency_failed:" + ",".join(bad)
            )
            return await finish(blocked, CheckpointPoint.SUBTASK_BLOCKED)
        if prior is not None and prior.observation is None and prior.run_id is not None:
            # Dispatched earlier with no recorded observation: unknown, never silently resent.
            unknown = replace(prior, state=SubtaskState.FAILED, error="outcome_unknown")
            return await finish(unknown, CheckpointPoint.SUBTASK_VERIFIED)
        if prior is not None and prior.observation is not None:
            observed = prior  # tool already ran; only verification remains
        else:
            await self._emit(
                pid,
                CheckpointPoint.SUBTASK_DISPATCH,
                PlanState.RUNNING,
                plan,
                results.values(),
                sid,
            )
            if pid in self._cancelled:
                raise asyncio.CancelledError
            ran = await self._tools.run_read(pid, subtask, session_id)
            observed = SubtaskResult(
                sid, SubtaskState.RUNNING, ran.run_id, ran.proposal_id, ran.observation
            )
            if ran.error is not None or ran.observation is None:
                failed = replace(
                    observed, state=SubtaskState.FAILED, error=ran.error or "no_observation"
                )
                return await finish(failed, CheckpointPoint.SUBTASK_VERIFIED)
            await finish(observed, CheckpointPoint.SUBTASK_OBSERVED)
        return await finish(await self._verify(subtask, observed), CheckpointPoint.SUBTASK_VERIFIED)

    async def _verify(self, subtask: Subtask, run: SubtaskResult) -> SubtaskResult:
        raw = _text(run.observation)
        try:
            reply = await self._planner.complete(
                "verifier",
                VERIFY_PROMPT.format(
                    expect=subtask.expect, observation=raw[:MAX_OBSERVATION_CHARS]
                ),
            )
            body = _json(reply.text)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return replace(
                run, state=SubtaskState.FAILED, error="verifier_failed:" + type(error).__name__
            )
        listed = body.get("quotes")
        quotes = (
            tuple(q for q in listed if isinstance(q, str) and q) if isinstance(listed, list) else ()
        )
        claimed = body.get("verified") is True
        grounded = bool(quotes) and all(q in raw for q in quotes)  # citations must exist verbatim
        ok = claimed and grounded
        reason = str(body.get("reason", ""))
        if claimed and not grounded:
            reason = "quotes_not_in_observation"
        verdict = Verdict(ok, reason, quotes, reply.model_name, self._degraded(reply.model_name))
        return replace(
            run,
            state=SubtaskState.VERIFIED if ok else SubtaskState.FAILED,
            verdict=verdict,
            sources=tuple(Source(subtask.capability, _ref(subtask), q) for q in quotes)
            if ok
            else (),
            error=None if ok else (reason or "not_verified"),
        )

    async def _summarize(self, plan: Plan, results: tuple[SubtaskResult, ...]) -> tuple[str, str]:
        view = [
            {
                "id": r.subtask_id,
                "state": r.state.value,
                "error": r.error,
                "evidence": [s.excerpt for s in r.sources],
            }
            for r in results
        ]
        try:
            reply = await self._planner.complete(
                "reporter",
                REPORT_PROMPT.format(goal=plan.goal, results=json.dumps(view, ensure_ascii=False)),
            )
            return reply.text, reply.model_name
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return "report_unavailable:" + type(error).__name__, plan.planner_model
