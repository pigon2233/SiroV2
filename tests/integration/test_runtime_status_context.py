from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Self

import pytest

import siro.services.agent.runs as runs_module
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
)
from siro.services.agent.runs import AgentRunState, SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion


async def failed_run(
    repo: SQLiteAgentRunRepository,
    session: str = "A",
    *,
    privacy: str = "cloud_allowed",
    error: str | None = "HTTPStatusError",
    dispatched: bool = False,
    state: AgentRunState = AgentRunState.FAILED,
) -> str:
    run = await repo.start(
        session, "SECRET-GOAL", runtime_backend="SECRET-BACKEND", privacy=privacy
    )
    await repo.reserve_round(run.run_id)
    await repo.checkpoint(
        run.run_id,
        [
            ModelMessage("system", "SECRET-PROMPT"),
            ModelMessage("user", run.goal),
            ModelMessage(
                "assistant",
                "SECRET-PARTIAL",
                tool_calls=(ToolCall("old-call", "computer.execute", {"argv": ["SECRET-ARGV"]}),),
            ),
        ],
    )
    if dispatched:
        await repo.record_dispatch(run.run_id, "old-call")
    await repo.record_observation(run.run_id, "old-call", {"text": "SECRET-OBSERVATION"})
    await repo.finish_journal(run.run_id)
    await repo.append(run.run_id, "final", {"text": "SECRET-FINAL"}, state=state, error=error)
    return run.run_id


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [AgentRunState.FAILED, AgentRunState.CANCELLED])
@pytest.mark.parametrize("dispatched", [False, True])
@pytest.mark.parametrize("interrupted", [False, True])
async def test_status_is_fixed_readonly_projection(
    tmp_path: Path, state: AgentRunState, dispatched: bool, interrupted: bool
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run_id = await failed_run(repo, state=state, dispatched=dispatched)
    if interrupted:
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE run_journal SET status='interrupted' WHERE run_id=?", (run_id,)
            )
        )
    before = await store.run_transaction(lambda c: tuple(c.iterdump()))
    assert await repo.recent_runtime_status("A", privacy="cloud_allowed") == {
        "source_run_id": run_id,
        "state": state.value,
        "error_class": "HTTPStatusError",
        "tool_dispatch_recorded": dispatched,
        "root_cause": "UNKNOWN",
    }
    assert await store.run_transaction(lambda c: tuple(c.iterdump())) == before
    assert await repo.recent_session_messages("A", privacy="cloud_allowed") == ()
    assert await repo.recent_runtime_status("B", privacy="cloud_allowed") is None
    assert await repo.recent_runtime_status("A", privacy="local_only") is None
    assert await repo.recent_runtime_status("A", privacy="public") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        None,
        "SECRET-CANCEL-REASON",
        "HTTPStatusError: SECRET-KEY",
        "X" * 20000,
        "HTTPStatusError\0" + "SECRET" * 4000,
    ],
    ids=["null", "cancel", "freeform", "oversized", "nul-tail"],
)
async def test_freeform_error_never_leaks(tmp_path: Path, error: str | None) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    await failed_run(repo, error=error)
    status = await repo.recent_runtime_status("A", privacy="cloud_allowed")
    assert status is not None and status["error_class"] == "UNKNOWN"
    assert len(str(status).encode()) < 1024 and "SECRET" not in str(status)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE agent_runs SET state='completed' WHERE run_id=?",
        "UPDATE agent_runs SET state='running' WHERE run_id=?",
        "DELETE FROM run_journal WHERE run_id=?",
        "UPDATE run_journal SET privacy='local_only' WHERE run_id=?",
        "UPDATE run_journal SET runtime_profile='legacy' WHERE run_id=?",
        "UPDATE run_journal SET status='active' WHERE run_id=?",
        "UPDATE agent_runs SET updated_at='bad timestamp' WHERE run_id=?",
        "UPDATE agent_runs SET updated_at='' WHERE run_id=?",
        "UPDATE agent_runs SET updated_at='0000' WHERE run_id=?",
    ],
)
async def test_newer_ineligible_row_masks_old_failure(tmp_path: Path, mutation: str) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    await failed_run(repo)
    newer = await failed_run(repo)
    # A tie is resolved by newest rowid, not by finding an older matching failure.
    timestamp = datetime.now(UTC).isoformat()
    await store.run_transaction(
        lambda c: c.execute("UPDATE agent_runs SET updated_at=?", (timestamp,))
    )
    if mutation.startswith("DELETE"):
        await store.run_transaction(
            lambda c: c.execute("DELETE FROM run_journal_calls WHERE run_id=?", (newer,))
        )
    await store.run_transaction(lambda c: c.execute(mutation, (newer,)))
    assert await repo.recent_runtime_status("A", privacy="cloud_allowed") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "seconds,expected", [(0, True), (899, True), (900, True), (901, False), (-1, False)]
)
async def test_status_age_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seconds: int, expected: bool
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run_id = await failed_run(repo)
    now = datetime.now(UTC)
    timestamp = (now - timedelta(seconds=seconds)).isoformat()
    await store.run_transaction(
        lambda c: c.execute(
            "UPDATE agent_runs SET updated_at=? WHERE run_id=?", (timestamp, run_id)
        )
    )

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> Self:
            return cls.fromtimestamp(now.timestamp(), UTC)

    monkeypatch.setattr(runs_module, "datetime", FixedClock)
    assert (await repo.recent_runtime_status("A", privacy="cloud_allowed") is not None) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timestamp",
    ["2026-10-10T12:00:00", "9999-99-99", "", "X" * 20000],
    ids=["naive", "invalid", "empty", "oversized"],
)
async def test_invalid_timestamps_fail_closed(tmp_path: Path, timestamp: str) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run_id = await failed_run(repo)
    await store.run_transaction(
        lambda c: c.execute(
            "UPDATE agent_runs SET updated_at=? WHERE run_id=?", (timestamp, run_id)
        )
    )
    assert await repo.recent_runtime_status("A", privacy="cloud_allowed") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", ["SECRET-ID", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"])
async def test_invalid_run_id_not_injected(tmp_path: Path, identity: str) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    await failed_run(repo)
    # Even a paired terminal journal does not make a malformed source identity safe.
    await store.run_transaction(
        lambda c: c.execute(
            "INSERT INTO agent_runs(run_id,session_id,goal,state,step_count,max_steps,"
            "created_at,updated_at) VALUES (?,'A','x','failed',0,8,?,?)",
            (identity, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()),
        )
    )
    await repo.start_journal(identity, backend="synthetic", privacy="cloud_allowed", max_rounds=8)
    await repo.finish_journal(identity)
    assert await repo.recent_runtime_status("A", privacy="cloud_allowed") is None


@pytest.mark.asyncio
async def test_valid_offset_timestamp_is_fresh(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run_id = await failed_run(repo)
    timestamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    await store.run_transaction(
        lambda c: c.execute(
            "UPDATE agent_runs SET updated_at=? WHERE run_id=?", (timestamp, run_id)
        )
    )
    assert await repo.recent_runtime_status("A", privacy="cloud_allowed") is not None


class CaptureModel:
    name = "synthetic-status"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "synthetic final")
        yield ModelChunk("finished")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile,restore,route,prior_route,expected",
    [
        ("candidate", True, Privacy.CLOUD_ALLOWED, "cloud_allowed", True),
        ("candidate", True, Privacy.LOCAL_ONLY, "local_only", True),
        ("candidate", True, Privacy.CLOUD_ALLOWED, "local_only", False),
        ("candidate", False, Privacy.CLOUD_ALLOWED, "cloud_allowed", False),
        ("legacy", True, Privacy.CLOUD_ALLOWED, "cloud_allowed", False),
    ],
)
async def test_status_wiring_before_new_run_start_and_egress_gates(
    tmp_path: Path, profile: str, restore: bool, route: Privacy, prior_route: str, expected: bool
) -> None:
    model = CaptureModel()
    companion = IntegratedCompanion(
        tmp_path,
        model,
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=route,
        runtime_profile=profile,
        session_restore_enabled=restore,
    )
    await companion._ensure_core()
    repo = companion._agent_runs
    assert repo is not None
    prior_id = await failed_run(repo, privacy=prior_route, dispatched=True)
    await companion.respond("A", "剛才是你自己的錯誤嗎?")
    request = model.requests[-1]
    assert ("Own runtime status:" in request.prompt) is expected
    assert "SECRET" not in request.prompt
    assert "every completed reply aloud" not in request.prompt
    assert "complete playback require observations" in request.prompt
    assert request.max_output_tokens == 512
    if expected:
        assert prior_id in request.messages[0].content
        assert '"tool_dispatch_recorded":true' in request.messages[0].content
        assert [(m.role, m.content) for m in request.messages[1:]] == [
            ("user", "剛才是你自己的錯誤嗎?")
        ]
        assert sum(m.role == "system" for m in request.messages) == 1
        assert not any(m.tool_calls or m.role == "tool" for m in request.messages)
        assert await repo.recent_runtime_status("A", privacy=route.value) is None
        await companion.respond("A", "你好")
        assert "Own runtime status:" not in model.requests[-1].prompt
        assert [(m.role, m.content) for m in model.requests[-1].messages[1:]] == [
            ("user", "剛才是你自己的錯誤嗎?"),
            ("assistant", "synthetic final"),
            ("user", "你好"),
        ]


@pytest.mark.asyncio
async def test_direct_command_does_not_read_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = CaptureModel()
    companion = IntegratedCompanion(
        tmp_path,
        model,
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
    )
    await companion._ensure_core()
    repo = companion._agent_runs
    assert repo is not None

    async def forbidden(*args: object, **kwargs: object) -> dict[str, object] | None:
        raise AssertionError("direct command must not read status")

    monkeypatch.setattr(repo, "recent_runtime_status", forbidden)
    await companion.respond("A", "測試聲音")
    assert not model.requests
