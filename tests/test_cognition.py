from datetime import UTC, datetime
from pathlib import Path

import pytest

from siro.core.cognition import (
    ActionCandidate,
    AttentionSignal,
    Drive,
    Goal,
    GoalState,
    Planner,
    Workspace,
    select_action,
    select_attention,
)
from siro.persistence.planning import SQLitePlanningRepository
from siro.persistence.sqlite import SQLiteStore


def candidate(candidate_id: str, score: float, **gates: bool) -> ActionCandidate:
    return ActionCandidate(
        candidate_id,
        "test",
        {},
        "result",
        0,
        None,
        score,
        ("fixture",),
        **gates,
    )


def test_attention_formula_user_and_cancel_priority_are_deterministic() -> None:
    low_user = AttentionSignal("user", 0, 0, 0, 0, 0, explicit_user_input=True)
    normal = AttentionSignal("normal", 1, 1, 1, 1, 1)
    cancel = AttentionSignal("cancel", 0, 0, 0, 0, 0, control="cancel")
    assert normal.score == 1
    assert select_attention((low_user,)) == low_user
    assert select_attention((normal, low_user)) == normal
    assert select_attention((normal, cancel)) == cancel


def test_hard_gates_reject_before_scoring_and_do_nothing_remains() -> None:
    denied = candidate("denied", 1, permission_allowed=False)
    quiet = candidate("quiet", 0.9, quiet_allowed=False)
    allowed = candidate("allowed", 0.7)
    nothing = candidate("nothing", 0.1)
    selection = select_action((denied, quiet, allowed), nothing)
    assert selection.candidate == allowed
    assert selection.rejected == (("denied", "permission"), ("quiet", "quiet"))

    blocked = select_action((denied, quiet), nothing)
    assert blocked.candidate == nothing


def test_workspace_and_goal_budgets_are_bounded() -> None:
    now = datetime.now(UTC)
    goals = tuple(Goal(str(index), GoalState.READY, "next", now) for index in range(5))
    workspace = Workspace()
    workspace.update(
        foreground="turn-1", goals=goals, events=tuple(f"event-{index}" for index in range(30))
    )
    assert len(workspace.goals) == 3
    assert len(workspace.events) == 20
    assert Goal("g", GoalState.RUNNING, "next", now, steps_used=7).budget_available
    assert not Goal("g", GoalState.RUNNING, "next", now, steps_used=8).budget_available


def test_noise_replay_never_overrides_explicit_user_input() -> None:
    noise = tuple(
        AttentionSignal(
            f"noise-{index:04d}",
            urgency=0.1,
            user_relevance=0,
            novelty=0.2,
            goal_relevance=0,
            drive_relevance=0.1,
        )
        for index in range(1_000)
    )
    user = AttentionSignal("user", 0, 0, 0, 0, 0, explicit_user_input=True)
    first = select_attention((*noise, user))
    replay = select_attention(tuple(reversed((*noise, user))))
    assert first == replay == user

    nothing = candidate("nothing", 0)
    noisy_actions = tuple(
        candidate(f"noise-{index:04d}", 1, permission_allowed=False) for index in range(1_000)
    )
    selection = select_action(noisy_actions, nothing)
    assert selection.candidate == nothing
    assert len(selection.rejected) == 1_000


def test_drive_is_explicit_bounded_and_can_be_disabled() -> None:
    drive = Drive("social", 0.8, "no interaction today")
    signal = drive.attention_signal()
    assert signal is not None
    assert signal.signal_id == "drive:social"
    assert signal.drive_relevance == 0.8
    assert Drive("social", 0.8, "muted", enabled=False).attention_signal() is None


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


@pytest.mark.asyncio
async def test_structured_planner_persists_selection_rejections_and_reasons(tmp_path: Path) -> None:
    path = tmp_path / "planning.sqlite3"
    store = SQLiteStore(path)
    await store.initialize()
    allowed = candidate("allowed", 0.8)
    denied = candidate("denied", 1.0, permission_allowed=False)
    nothing = ActionCandidate("nothing", "none", {}, "wait", 0, None, 0, ("no action",))
    now = datetime.now(UTC)
    decision = await Planner(SQLitePlanningRepository(store), FixedClock(now)).plan(
        "trace-plan", (denied, allowed), nothing
    )
    assert decision.selected_candidate_id == "allowed"
    assert decision.rejected == (("denied", "permission"),)
    row = await store.run_transaction(
        lambda connection: connection.execute(
            "SELECT trace_id,selected_candidate_id,rejected_json,reasons_json "
            "FROM planning_decisions"
        ).fetchone()
    )
    assert tuple(row[:2]) == ("trace-plan", "allowed")
    assert "permission" in str(row[2])
    assert "fixture" in str(row[3])
