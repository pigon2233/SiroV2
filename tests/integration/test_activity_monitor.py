"""CP-P02: durable activity/network records read back through the monitor projection."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import subprocess
import sys
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.activity_events import prune
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.activity.monitor import ActivityMonitor
from siro.services.presentation.gateway import GatewayHub, create_app
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.execution import ExecutionContext
from siro.services.tools.orchestrator import (
    ProposalState,
    SQLiteToolProposalRepository,
    ToolOrchestrator,
)

pytestmark = pytest.mark.asyncio
Executor = Callable[[dict[str, object], ExecutionContext], Awaitable[object]]


class ScriptedModel:
    """Each request plays the next round: a list of tool calls, or final text."""

    name = "scripted-activity"

    def __init__(self, rounds: list[list[ToolCall] | str]) -> None:
        self.rounds = rounds
        self.requests = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        del request, cancellation
        step = self.rounds[min(self.requests, len(self.rounds) - 1)]
        self.requests += 1
        if isinstance(step, str):
            yield ModelChunk("text", step)
        else:
            for call in step:
                yield ModelChunk("tool_request", tool_call=call)
        yield ModelChunk("finished")


async def companion(
    tmp_path: Path, model: ScriptedModel, executors: dict[str, Executor]
) -> tuple[IntegratedCompanion, SQLiteStore]:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()

    async def legacy(arguments: dict[str, object]) -> object:
        raise AssertionError("legacy executor bypassed the journal")

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        dict.fromkeys(executors, legacy),
        contextual_executors=executors,
    )
    controller = IntegratedCompanion(
        tmp_path,
        model,
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    await controller._ensure_core()
    return controller, store


def dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


async def all_changes(monitor: ActivityMonitor, *, limit: int = 100) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    after = 0
    while True:
        page = await monitor.changes(after=after, limit=limit)
        assert not page["gap"]
        events += page["events"]  # type: ignore[arg-type]
        after = int(page["cursor"])  # type: ignore[call-overload]
        if not page["has_more"]:
            return events


def activities_of(snapshot: dict[str, object]) -> list[dict[str, Any]]:
    value = snapshot["activities"]
    assert isinstance(value, list)
    return value


TERMINAL = {"completed", "failed", "denied", "cancelled"}


def assert_terminal_monotonic(events: list[dict[str, Any]]) -> None:
    """No entity re-enters a running state after a terminal state (no resurrection)."""
    final: dict[tuple[str, str], str] = {}
    for event in events:
        key = (event["entity"], event["entity_id"])
        if key in final:
            raise AssertionError(f"{key} changed after terminal {final[key]}: {event}")
        if event["raw_state"] in TERMINAL:
            final[key] = event["raw_state"]


async def test_shell_tool_is_redacted_and_network_marked_unobserved(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object], context: ExecutionContext) -> object:
        calls.append(arguments)
        return {"exit_code": 0, "stdout": "ok"}

    model = ScriptedModel(
        [
            [
                ToolCall(
                    "c1",
                    "computer.execute",
                    {
                        "argv": [
                            "/usr/bin/curl",
                            "https://user:pw@example.test/?t=SECRET1",  # pragma: allowlist secret
                        ]
                    },
                )
            ],
            "done",
        ]
    )
    controller, store = await companion(tmp_path, model, {"computer.execute": execute})
    await controller.respond("s1", "check the network for me")
    monitor = ActivityMonitor(store)
    snapshot = await monitor.snapshot()
    [activity] = activities_of(snapshot)
    assert (activity["state"], activity["origin"]) == ("completed", "owner_request")
    assert activity["reason"] == "check the network for me"
    [tool] = activity["tools"]
    assert (tool["state"], tool["dispatched"]) == ("completed", True)
    assert tool["target"] == {"program": "curl", "argument_count": 1}
    assert tool["network"] == {
        "coverage": "unobserved",
        "requests": [],
        "gaps": ["subprocess_network_not_monitored"],
    }
    assert activity["coverage"] == {"tools": "journal", "network": ["unobserved"]}
    assert "SECRET1" not in dump(snapshot) and "pw@" not in dump(snapshot)
    events = await all_changes(monitor)
    assert [(e["entity"], e["raw_state"], e["phase"]) for e in events] == [
        ("run", "running", None),
        ("tool", "pending", None),
        ("run", "waiting_tool", None),
        ("tool", "approved", None),
        ("tool", "running", None),
        # The handler boundary is separate from the state change that precedes it.
        ("tool", "running", "dispatched"),
        ("tool", "completed", None),
        ("run", "running", None),
        ("run", "completed", None),
    ]
    assert len(calls) == 1


async def test_stop_race_keeps_dispatched_outcome_unknown(tmp_path: Path) -> None:
    entered = asyncio.Event()
    started: list[object] = []

    async def execute(arguments: dict[str, object], context: ExecutionContext) -> object:
        started.append(arguments["n"])
        entered.set()
        await context.cancellation.wait()
        context.check()
        return arguments

    model = ScriptedModel(
        [
            [
                ToolCall("c1", "computer.execute", {"argv": ["sleep", "9"], "n": 1}),
                ToolCall("c2", "computer.execute", {"argv": ["sleep", "9"], "n": 2}),
            ],
            "never",
        ]
    )
    controller, store = await companion(tmp_path, model, {"computer.execute": execute})
    task = asyncio.create_task(controller.respond("s1", "run two commands"))
    await asyncio.wait_for(entered.wait(), 10)
    await asyncio.wait_for(controller.cancel("active", "owner stop"), 5)
    await asyncio.wait_for(task, 5)
    monitor = ActivityMonitor(store)
    [activity] = activities_of(await monitor.snapshot())
    states = {tool["dispatched"]: tool["state"] for tool in activity["tools"]}
    # The dispatched call may have had side effects: never shown as a clean cancellation.
    assert states[True] == "unknown"
    assert started == [1]
    if False in states:
        assert states[False] == "cancelled"
    assert activity["state"] in {"cancelled", "unknown", "failed"}
    events = await all_changes(monitor)
    assert_terminal_monotonic(events)
    assert [e["seq"] for e in events] == sorted({e["seq"] for e in events})


@pytest.fixture
def http_origin() -> Any:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", "/landing?session=SECRET2")
                self.end_headers()
                return
            status = 500 if self.path.startswith("/broken") else 200
            self.send_response(status)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            with contextlib.suppress(BrokenPipeError):
                self.wfile.write(f"<title>synthetic {status}</title><p>page</p>".encode())

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(2)


def closed_origin() -> str:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}"


async def test_real_browser_http_outcomes_are_recorded_honestly(
    tmp_path: Path, http_origin: str
) -> None:
    from siro.adapters.browser import ScopedBrowserDriver
    from siro.services.tools.browser_session import BrowserSessions

    pool = BrowserSessions(ScopedBrowserDriver)

    async def browse(arguments: dict[str, object], context: ExecutionContext) -> object:
        return await pool.execute("navigate+read", arguments, context)

    refused = closed_origin()
    model = ScriptedModel(
        [
            [ToolCall("r", "browser.navigate+read", {"url": f"{http_origin}/redirect?q=SECRET3"})],
            [ToolCall("b", "browser.navigate+read", {"url": f"{http_origin}/broken"})],
            [ToolCall("x", "browser.navigate+read", {"url": f"{refused}/nothing"})],
            [ToolCall("y", "browser.navigate+read", {"url": f"{http_origin}/landing"})],
            "summarised",
        ]
    )
    controller, store = await companion(tmp_path, model, {"browser.navigate+read": browse})
    try:
        await controller.respond("s1", "look these pages up")
    finally:
        await pool.close()
    snapshot = await ActivityMonitor(store).snapshot()
    [activity] = activities_of(snapshot)
    redirect, broken, offline, recovered = activity["tools"]
    [hop] = redirect["network"]["requests"]
    assert redirect["state"] == "completed"
    assert hop["requested"] == {"url": f"{http_origin}/redirect", "redacted": True}
    assert hop["final"] == {"url": f"{http_origin}/landing", "redacted": True}
    assert (hop["redirected"], hop["status"]) == (True, "unknown")
    # An HTTP 500 page still loads in the browser; the adapter has no status, so none is invented.
    assert broken["network"]["requests"][0]["status"] == "unknown"
    assert broken["state"] == "completed"
    assert offline["state"] == "failed" and offline["error"] != "ExecutionCleanupError"
    from datetime import datetime

    took = datetime.fromisoformat(offline["updated_at"]) - datetime.fromisoformat(
        offline["created_at"]
    )
    # A refused connection used to stall until the 30 s browser session timeout.
    assert took.total_seconds() < 10
    assert offline["network"]["requests"][0]["requested"] == {"url": f"{refused}/nothing"}
    assert offline["network"]["requests"][0]["final"] is None
    # One unreachable site must not close the browser pool for later work.
    assert recovered["state"] == "completed"
    assert activity["coverage"]["network"] == ["browser_adapter"]
    text = dump(snapshot)
    assert "SECRET2" not in text and "SECRET3" not in text


async def ok_execute(arguments: dict[str, object], context: ExecutionContext) -> object:
    return {"exit_code": 0}


async def test_cursor_pages_resume_without_duplicates_and_report_gaps(tmp_path: Path) -> None:
    model = ScriptedModel([[ToolCall("c1", "computer.execute", {"argv": ["true"]})], "ok"])
    controller, store = await companion(tmp_path, model, {"computer.execute": ok_execute})
    await controller.respond("s1", "first")
    model.requests = 0
    await controller.respond("s1", "second")
    monitor = ActivityMonitor(store)
    full = await all_changes(monitor)
    paged = await all_changes(monitor, limit=3)
    assert [e["seq"] for e in paged] == [e["seq"] for e in full]
    assert len({e["seq"] for e in full}) == len(full) == 18
    # A client that reconnects with an older cursor re-reads an overlap; seq makes it idempotent.
    middle = int(full[7]["seq"])
    again = await monitor.changes(after=middle, limit=100)
    assert [e["seq"] for e in again["events"]] == [e["seq"] for e in full[8:]]  # type: ignore[attr-defined]
    assert again["activities"]
    caught_up = await monitor.changes(after=int(full[-1]["seq"]))
    assert (caught_up["events"], caught_up["gap"], caught_up["cursor"]) == (
        [],
        False,
        full[-1]["seq"],
    )
    ahead = await monitor.changes(after=int(full[-1]["seq"]) + 50)
    assert ahead["gap"] is True  # e.g. a restored older database: take a new snapshot

    from datetime import UTC, datetime, timedelta

    await store.run_transaction(lambda c: prune(c, now=datetime.now(UTC) + timedelta(days=8)))
    await controller.respond("s1", "third")
    pruned = await monitor.changes(after=1)
    assert pruned["gap"] is True
    snapshot = await monitor.snapshot()
    # Pruning the feed never drops the activities themselves.
    assert len(snapshot["activities"]) == 3  # type: ignore[arg-type]
    assert snapshot["retained_from"] == pruned["events"][0]["seq"]  # type: ignore[index]


async def test_resent_transitions_and_dispatches_add_no_events(tmp_path: Path) -> None:
    model = ScriptedModel([[ToolCall("c1", "computer.execute", {"argv": ["true"]})], "ok"])
    controller, store = await companion(tmp_path, model, {"computer.execute": ok_execute})
    await controller.respond("s1", "once")
    monitor = ActivityMonitor(store)
    before = await all_changes(monitor)
    [activity] = activities_of(await monitor.snapshot())
    proposal_id = activity["tools"][0]["proposal_id"]
    repository = SQLiteToolProposalRepository(store)
    with pytest.raises(ValueError, match="state changed"):
        await repository.transition(proposal_id, ProposalState.RUNNING, ProposalState.COMPLETED)
    runs = controller._agent_runs
    assert runs is not None
    with pytest.raises(ValueError, match="duplicate or fenced"):
        await runs.record_dispatch(activity["activity_id"], "c1")
    with pytest.raises(ValueError, match="terminal"):
        await runs.append(activity["activity_id"], "late", {}, state=None)
    assert await all_changes(monitor) == before


async def test_audit_write_failure_blocks_the_dispatch(tmp_path: Path) -> None:
    calls: list[object] = []

    async def execute(arguments: dict[str, object], context: ExecutionContext) -> object:
        calls.append(arguments)
        return {"exit_code": 0}

    model = ScriptedModel([[ToolCall("c1", "computer.execute", {"argv": ["rm", "x"]})], "ok"])
    controller, store = await companion(tmp_path, model, {"computer.execute": execute})

    def break_audit(c: Any) -> None:
        # Test-only fault: the audit row for the real dispatch boundary cannot be written.
        c.execute(
            "CREATE TRIGGER audit_down BEFORE INSERT ON activity_events "
            "WHEN NEW.phase = 'dispatched' BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END"
        )

    await store.run_transaction(break_audit)
    await controller.respond("s1", "delete x")
    assert calls == []  # the handler never ran without its audit record
    [activity] = activities_of(await ActivityMonitor(store).snapshot())
    [tool] = activity["tools"]
    assert tool["dispatched"] is False
    assert tool["state"] in {"failed", "cancelled"}


async def test_new_feed_table_keeps_the_previous_schema_readable(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    migrations = load_migrations()
    assert migrations[-1].name == "activity_events"

    def previous_release(c: Any) -> int:
        # An older build applies only the migrations it knows and ignores the newer table.
        apply_migrations(c, migrations[:-1])
        c.execute(
            "INSERT INTO tool_proposals VALUES "
            "('p','s','c','computer.execute','{}','h','high','pending',NULL,NULL,'t','t')"
        )
        return int(c.execute("SELECT COUNT(*) FROM activity_events").fetchone()[0])

    assert await store.run_transaction(previous_release) == 0
    snapshot = await ActivityMonitor(store).snapshot()
    [activity] = activities_of(snapshot)
    # Writes by an older build have no feed rows, but the snapshot still shows them.
    assert (activity["kind"], activity["state"]) == ("tool", "proposed")


async def test_pages_are_bounded_and_reasons_truncated(tmp_path: Path) -> None:
    model = ScriptedModel(["ok"])
    controller, store = await companion(tmp_path, model, {"computer.execute": ok_execute})
    for index in range(103):
        await controller.respond("s1", f"{index} " + "長" * 300)
    monitor = ActivityMonitor(store)
    snapshot = await monitor.snapshot(limit=1000)
    activities = snapshot["activities"]
    assert len(activities) == 100 and snapshot["truncated"] is True  # type: ignore[arg-type]
    assert (await monitor.snapshot(limit=3))["truncated"] is True
    first = activities[0]  # type: ignore[index]
    assert first["reason_truncated"] is True and len(first["reason"]) == 200
    page = await monitor.changes(after=0, limit=1000)
    assert len(page["events"]) == 100 and page["has_more"] is True  # type: ignore[arg-type]


def test_gateway_routes_require_a_session_and_report_unavailable() -> None:
    origin = "http://testserver"

    async def snapshot(limit: int) -> dict[str, object]:
        return {"status": "ok", "limit": limit}

    async def changes(after: int, limit: int) -> dict[str, object]:
        return {"status": "ok", "after": after, "limit": limit}

    app = create_app(
        allowed_origins={origin},
        on_activity_snapshot=snapshot,
        on_activity_changes=changes,
    )
    with TestClient(app) as client:
        assert client.get("/v1/activities").status_code == 401
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        auth = {"authorization": f"Bearer {token}"}
        response = client.get("/v1/activities?limit=7", headers=auth)
        assert response.json() == {"status": "ok", "limit": 7}
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/v1/activities?limit=101", headers=auth).status_code == 422
        assert client.get("/v1/activities/changes", headers=auth).status_code == 422
        assert client.get("/v1/activities/changes?after=-1", headers=auth).status_code == 422
        assert client.get("/v1/activities/changes?after=5", headers=auth).json() == {
            "status": "ok",
            "after": 5,
            "limit": 100,
        }
    with TestClient(create_app(allowed_origins={origin})) as client:
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        response = client.get("/v1/activities", headers={"authorization": f"Bearer {token}"})
        assert response.json() == {"status": "unavailable"}


async def test_controller_does_not_open_the_store_for_a_monitor_read(tmp_path: Path) -> None:
    controller = IntegratedCompanion(
        tmp_path,
        ScriptedModel(["ok"]),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
    )
    assert await controller.activity_snapshot(10) == {"status": "unavailable"}
    assert await controller.activity_changes(0, 10) == {"status": "unavailable"}
    assert not (tmp_path / "siro.db").exists()


CRASHING_CHILD = r"""
import asyncio, sys
from pathlib import Path
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

class Model:
    name = "crash"
    async def stream(self, request, cancellation):
        yield ModelChunk("tool_request", tool_call=ToolCall("c1", "computer.execute",
            {"argv": ["touch", "/tmp/side-effect"]}))
        yield ModelChunk("finished")

async def main():
    root = Path(sys.argv[1])
    store = SQLiteStore(root / "siro.db")
    await store.initialize()
    async def legacy(arguments):
        raise AssertionError
    async def execute(arguments, context):
        print("DISPATCHED", flush=True)
        await asyncio.sleep(3600)
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store),
        {"computer.execute": legacy}, contextual_executors={"computer.execute": execute})
    controller = IntegratedCompanion(root, Model(), GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()), privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator, runtime_profile="candidate", auto_authorize=lambda: True)
    await controller._ensure_core()
    await controller.respond("s1", "touch a file")

asyncio.run(main())
"""


async def test_killed_process_restarts_with_unknown_outcome_and_no_replay(tmp_path: Path) -> None:
    child = subprocess.Popen(
        [sys.executable, "-c", CRASHING_CHILD, str(tmp_path)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        line = await asyncio.wait_for(asyncio.to_thread(child.stdout.readline), 30)
        assert line.strip() == "DISPATCHED"
    finally:
        child.kill()  # SIGKILL: no cleanup, cancellation or journal finish runs
        child.wait(10)
    replays: list[object] = []

    async def must_not_run(arguments: dict[str, object], context: ExecutionContext) -> object:
        replays.append(arguments)
        return {}

    controller, store = await companion(
        tmp_path, ScriptedModel(["after restart"]), {"computer.execute": must_not_run}
    )
    monitor = ActivityMonitor(store)
    [activity] = activities_of(await monitor.snapshot())
    [tool] = activity["tools"]
    assert (activity["state"], activity["error"]) == ("unknown", "outcome_unknown")
    assert (tool["state"], tool["dispatched"], tool["error"]) == (
        "unknown",
        True,
        "interrupted_restart",
    )
    events = await all_changes(monitor)
    assert [(e["entity"], e["raw_state"], e["phase"]) for e in events[-2:]] == [
        ("run", "failed", "outcome_unknown"),
        ("tool", "failed", "interrupted_restart"),
    ]
    assert_terminal_monotonic(events)
    await controller.respond("s1", "are you there")
    assert replays == []


async def test_stop_one_activity_by_id_and_reject_stale_controls(tmp_path: Path) -> None:
    entered = asyncio.Event()

    async def execute(arguments: dict[str, object], context: ExecutionContext) -> object:
        entered.set()
        await context.cancellation.wait()
        context.check()
        return arguments

    model = ScriptedModel([[ToolCall("c1", "computer.execute", {"argv": ["sleep", "9"]})], "never"])
    controller, store = await companion(tmp_path, model, {"computer.execute": execute})
    task = asyncio.create_task(controller.respond("s1", "wait for a while"))
    await asyncio.wait_for(entered.wait(), 10)
    [running] = activities_of(await ActivityMonitor(store).snapshot())
    assert running["state"] == "running"
    stopped = await asyncio.wait_for(
        controller.stop_activity(str(running["activity_id"]), "owner stop"), 5
    )
    await asyncio.wait_for(task, 5)
    assert (stopped["status"], stopped["session_id"]) == ("cancelling", "s1")
    [after] = activities_of(await ActivityMonitor(store).snapshot())
    assert after["state"] in {"cancelled", "unknown", "failed"}
    # A dispatched tool may have acted: the stop never claims a clean cancellation.
    assert [tool["state"] for tool in after["tools"]] == ["unknown"]
    again = await controller.stop_activity(str(running["activity_id"]), "owner stop")
    assert again == {"status": "stale", "state": after["state"]}
    assert await controller.stop_activity("missing", "owner stop") == {"status": "not_found"}
    # The next foreground turn is untouched by the old stop.
    model.rounds = ["fresh reply"]
    model.requests = 0
    await asyncio.wait_for(controller.respond("s1", "hello again"), 5)
    latest = activities_of(await ActivityMonitor(store).snapshot())[0]
    assert latest["state"] == "completed"


async def test_stop_a_pending_standalone_tool_never_runs_it(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    ran: list[object] = []

    async def legacy(arguments: dict[str, object]) -> object:
        ran.append(arguments)
        return arguments

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": legacy}
    )
    proposal = await orchestrator.propose(
        "s1", ToolCall("c1", "computer.execute", {"argv": ["ls"]}), risk="low"
    )
    controller = IntegratedCompanion(
        tmp_path,
        ScriptedModel(["unused"]),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
    )
    controller._store = store
    result = await controller.stop_activity(proposal.proposal_id, "owner stop")
    assert result == {"status": "cancelling", "state": "cancelled"}
    stored = await orchestrator.get(proposal.proposal_id)
    assert stored is not None and stored.state is ProposalState.DENIED
    assert ran == []


def test_gateway_stop_route_maps_outcomes() -> None:
    origin = "http://testserver"
    outcomes = {
        "a": {"status": "cancelling", "state": "cancelled"},
        "b": {"status": "stale", "state": "completed"},
        "c": {"status": "not_found"},
    }

    async def stop(activity_id: str) -> dict[str, object]:
        return outcomes[activity_id]

    app = create_app(allowed_origins={origin}, on_activity_stop=stop)
    with TestClient(app) as client:
        assert client.post("/v1/activities/a/stop").status_code == 401
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        auth = {"authorization": f"Bearer {token}"}
        ok = client.post("/v1/activities/a/stop", headers=auth)
        assert (ok.status_code, ok.json()) == (200, outcomes["a"])
        assert client.post("/v1/activities/b/stop", headers=auth).status_code == 409
        assert client.post("/v1/activities/c/stop", headers=auth).status_code == 404
        assert client.post(f"/v1/activities/{'x' * 129}/stop", headers=auth).status_code == 400
    with TestClient(create_app(allowed_origins={origin})) as client:
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        response = client.post(
            "/v1/activities/a/stop", headers={"authorization": f"Bearer {token}"}
        )
        assert response.status_code == 503
