"""D57 owner API, lifecycle composition and additive-schema compatibility gates."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from siro.core.releases import ReleaseLaunchError, ReleaseManager
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations
from siro.services.agent.goal_tasks import ReadTaskOwner
from siro.services.presentation.gateway import GatewayState, create_app
from siro.services.tools.execution import ExecutionContext
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

ORIGIN = "http://testserver"
TASK_ROUTE = "/v1/goal-tasks/browser"
AUTH_ROUTES = (
    ("GET", TASK_ROUTE, None),
    ("POST", TASK_ROUTE, {"paths": ["notes.md"]}),
    ("POST", TASK_ROUTE + "/unknown/approve", {"revision": 1}),
    ("POST", TASK_ROUTE + "/unknown/resume", {"revision": 1}),
    ("POST", TASK_ROUTE + "/unknown/pause", {"revision": 1}),
    ("POST", TASK_ROUTE + "/unknown/cancel", {"revision": 1}),
    ("DELETE", TASK_ROUTE + "/unknown", {"revision": 1}),
)


class Workspace:
    """Owned synthetic document IO with a controllable cancellation/join boundary."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        (root / "notes.md").write_text("unmatched SYNTHETIC_PRIVATE_LINE\nTODO verify source\n")
        self.available = True
        self.calls: list[ExecutionContext] = []
        self.gated = False
        self.suppress_cancel = False
        self.entered = Event()
        self.cancelled = Event()
        self.finished = Event()
        self.release = asyncio.Event()

    async def execute(
        self, capability: str, arguments: dict[str, object], context: ExecutionContext
    ) -> object:
        assert capability == "filesystem.read" and set(arguments) == {"path"}
        assert context.authorized and context.deadline is not None
        context.check()
        self.calls.append(context)
        self.entered.set()
        try:
            if self.gated:
                try:
                    await self.release.wait()
                except asyncio.CancelledError:
                    self.cancelled.set()
                    if not self.suppress_cancel:
                        raise
                    await self.release.wait()
            raw = arguments["path"]
            assert isinstance(raw, str)
            path = (self.root / raw).resolve(strict=True)
            if not path.is_relative_to(self.root):
                raise PermissionError("SYNTHETIC_OUTSIDE_CANARY")
            return {"text": path.read_text()}
        finally:
            self.finished.set()


@dataclass
class Rig:
    client: TestClient
    owner: ReadTaskOwner
    workspace: Workspace
    state: GatewayState
    store: SQLiteStore
    headers: dict[str, str] = field(repr=False)


def token_headers(client: TestClient, origin: str = ORIGIN) -> dict[str, str]:
    response = client.post("/v1/session", headers={"origin": origin})
    assert response.status_code == 200
    return {"origin": origin, "authorization": f"Bearer {response.json()['token']}"}


def uncached(response: Response, status: int) -> Any:
    assert response.status_code == status, response.text
    assert response.headers.get("cache-control") == "no-store"
    return response.json()


@contextmanager
def rig(
    tmp_path: Path,
    *,
    profile: str = "candidate",
    on_turn: Callable[..., Any] | None = None,
    on_shutdown: Callable[..., Any] | None = None,
    legacy_shortcuts: bool = False,
    raise_server_exceptions: bool = True,
) -> Iterator[Rig]:
    store = SQLiteStore(tmp_path / "goals.sqlite3")
    asyncio.run(store.initialize())
    workspace = Workspace(tmp_path / "documents")
    state = GatewayState(authorization_mode="full")
    owner = ReadTaskOwner(
        store, workspace, busy=lambda: False, allowed=lambda: state.kill_switches["tools"]
    )
    options: dict[str, Any] = {}
    if on_turn is not None:
        options["on_turn"] = on_turn
    if on_shutdown is not None:
        options["on_shutdown"] = on_shutdown
    if legacy_shortcuts:

        async def forbidden_execute(arguments: dict[str, object]) -> object:
            raise AssertionError("this test proposes a shortcut, never executes it")

        options["legacy_shortcuts"] = True
        options["tool_orchestrator"] = ToolOrchestrator(
            SQLiteToolProposalRepository(store), {"process.start": forbidden_execute}
        )
    app = create_app(
        state=state,
        runtime_profile=profile,
        allowed_origins={ORIGIN},
        read_task_owner=owner,
        **options,
    )
    with TestClient(app, raise_server_exceptions=raise_server_exceptions) as client:
        yield Rig(client, owner, workspace, state, store, token_headers(client))


def propose(r: Rig, paths: list[str] | None = None) -> dict[str, Any]:
    return dict(
        uncached(
            r.client.post(TASK_ROUTE, headers=r.headers, json={"paths": paths or ["notes.md"]}),
            200,
        )["goal"]
    )


def control(r: Rig, goal: dict[str, Any], action: str, *, revision: int | None = None) -> Response:
    return cast(
        Response,
        r.client.post(
            f"{TASK_ROUTE}/{goal['goal_id']}/{action}",
            headers=r.headers,
            json={"revision": goal["revision"] if revision is None else revision},
        ),
    )


def current(r: Rig, goal_id: str) -> dict[str, Any]:
    return next(
        dict(goal)
        for goal in uncached(r.client.get(TASK_ROUTE, headers=r.headers), 200)["goals"]
        if goal["goal_id"] == goal_id
    )


def wait_state(r: Rig, goal_id: str, state: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while True:
        goal = current(r, goal_id)
        if goal["state"] == state:
            return goal
        assert time.monotonic() < deadline, goal
        time.sleep(0.01)


@pytest.mark.parametrize(("method", "route", "body"), AUTH_ROUTES)
@pytest.mark.parametrize("credential", [None, "Bearer wrong-synthetic-token"])
def test_every_task_route_requires_bearer_and_is_uncached(
    method: str, route: str, body: Any, credential: str | None
) -> None:
    client = TestClient(create_app(runtime_profile="candidate", allowed_origins={ORIGIN}))
    headers = {"origin": ORIGIN}
    if credential is not None:
        headers["authorization"] = credential
    uncached(client.request(method, route, headers=headers, json=body), 401)


@pytest.mark.parametrize(("method", "route", "body"), AUTH_ROUTES)
def test_missing_owner_is_safe_unavailable_without_initialization(
    method: str, route: str, body: Any
) -> None:
    client = TestClient(create_app(runtime_profile="candidate", allowed_origins={ORIGIN}))
    data = uncached(client.request(method, route, headers=token_headers(client), json=body), 503)
    assert data == {"detail": {"code": "unavailable"}}


@pytest.mark.parametrize("profile", ["legacy", "candidate"])
def test_unstarted_or_legacy_owner_get_never_reads_or_initializes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    store = SQLiteStore(tmp_path / "not-created.sqlite3")
    workspace = Workspace(tmp_path / "documents")
    owner = ReadTaskOwner(store, workspace, busy=lambda: False, allowed=lambda: True)
    calls: list[str] = []

    async def forbidden(*args: Any, **kwargs: Any) -> Any:
        calls.append("store")
        raise AssertionError("GET must not initialize or read an unstarted owner")

    monkeypatch.setattr(store, "initialize", forbidden)
    monkeypatch.setattr(store, "run_transaction", forbidden)
    client = TestClient(
        create_app(runtime_profile=profile, allowed_origins={ORIGIN}, read_task_owner=owner)
    )
    uncached(client.get(TASK_ROUTE, headers=token_headers(client)), 503)
    assert calls == [] and not store.path.exists() and workspace.calls == []


@pytest.mark.parametrize(("method", "route", "body"), AUTH_ROUTES[1:])
@pytest.mark.parametrize("origin", [None, "https://evil.invalid"])
def test_task_mutations_require_owner_origin(
    tmp_path: Path, method: str, route: str, body: Any, origin: str | None
) -> None:
    with rig(tmp_path) as r:
        headers = dict(r.headers)
        if origin is None:
            headers.pop("origin")
        else:
            headers["origin"] = origin
        uncached(r.client.request(method, route, headers=headers, json=body), 403)
        assert uncached(r.client.get(TASK_ROUTE, headers=r.headers), 200)["goals"] == []
        assert r.workspace.calls == []


@pytest.mark.parametrize(
    "body",
    [{"paths": []}, {"paths": ["a"] * 6}, {"paths": [1]}, {"paths": ["a"], "approve": True}],
)
def test_proposal_body_is_closed_and_bounded(tmp_path: Path, body: Any) -> None:
    with rig(tmp_path) as r:
        uncached(r.client.post(TASK_ROUTE, headers=r.headers, json=body), 422)
        assert uncached(r.client.get(TASK_ROUTE, headers=r.headers), 200)["goals"] == []
        assert r.workspace.calls == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"revision": True},
        {"revision": "1"},
        {"revision": 0},
        {"revision": 1, "paths": ["other.md"]},
    ],
)
def test_control_revision_is_strict_and_body_cannot_change_scope(tmp_path: Path, body: Any) -> None:
    with rig(tmp_path) as r:
        goal = propose(r)
        uncached(
            r.client.post(f"{TASK_ROUTE}/{goal['goal_id']}/approve", headers=r.headers, json=body),
            422,
        )
        assert current(r, goal["goal_id"])["state"] == "proposed"
        assert r.workspace.calls == []


@pytest.mark.parametrize(
    ("method", "route"), [("PUT", TASK_ROUTE), ("POST", TASK_ROUTE + "/unknown/execute")]
)
def test_wrong_method_or_unknown_action_remains_uncached(method: str, route: str) -> None:
    client = TestClient(create_app(runtime_profile="candidate", allowed_origins={ORIGIN}))
    uncached(
        client.request(method, route, headers=token_headers(client), json={"revision": 1}),
        405 if method == "PUT" else 422,
    )


def test_full_mode_still_requires_approval_and_exposes_only_source_matches(tmp_path: Path) -> None:
    with rig(tmp_path) as r:
        goal = propose(r)
        assert goal["state"] == "proposed" and goal["task"]["approved_at"] is None
        assert goal["task"]["paths"] == ["notes.md"]
        time.sleep(0.02)
        assert r.workspace.calls == [] and not r.owner.busy
        uncached(control(r, goal, "approve", revision=goal["revision"] + 1), 409)
        assert r.workspace.calls == []
        uncached(control(r, goal, "approve"), 200)
        complete = wait_state(r, goal["goal_id"], "completed")
        evidence = complete["task"]["observations"][0]
        text = (r.workspace.root / "notes.md").read_text()
        assert evidence["sha256"] == hashlib.sha256(text.encode()).hexdigest()
        assert evidence["matches"] == [{"line": 2, "text": "TODO verify source"}]
        assert evidence["status"] == "completed" and evidence["read_at"]
        assert complete["steps_used"] == 1 and len(r.workspace.calls) == 1
        payload = r.client.get(TASK_ROUTE, headers=r.headers).text
        assert "SYNTHETIC_PRIVATE_LINE" not in payload
        assert str(r.workspace.root) not in payload and "owner_session_id" not in payload
        removed = uncached(
            r.client.request(
                "DELETE",
                f"{TASK_ROUTE}/{goal['goal_id']}",
                headers=r.headers,
                json={"revision": complete["revision"]},
            ),
            200,
        )
        assert removed == {"removed": True}
        assert uncached(r.client.get(TASK_ROUTE, headers=r.headers), 200)["goals"] == []


def test_cross_session_cannot_read_active_identity_or_mutate_owner_task(tmp_path: Path) -> None:
    with rig(tmp_path) as r:
        r.workspace.gated = True
        goal = propose(r)
        uncached(control(r, goal, "approve"), 200)
        assert r.workspace.entered.wait(2)
        other = uncached(r.client.get("/v1/goal-tasks/other", headers=r.headers), 200)
        assert other["goals"] == [] and other["active_goal_id"] is None
        for action in ("approve", "resume", "pause", "cancel"):
            uncached(
                r.client.post(
                    f"/v1/goal-tasks/other/{goal['goal_id']}/{action}",
                    headers=r.headers,
                    json={"revision": 1},
                ),
                404,
            )
        uncached(
            r.client.request(
                "DELETE",
                f"/v1/goal-tasks/other/{goal['goal_id']}",
                headers=r.headers,
                json={"revision": 1},
            ),
            404,
        )
        assert r.owner.busy and not r.workspace.cancelled.is_set()
        uncached(control(r, goal, "cancel"), 200)
        assert r.workspace.finished.is_set() and not r.owner.busy


def test_approved_filename_none_is_not_confused_with_planner_do_nothing(tmp_path: Path) -> None:
    with rig(tmp_path) as r:
        (r.workspace.root / "none").write_text("TODO legitimate owner-selected file\n")
        goal = propose(r, ["none"])
        uncached(control(r, goal, "approve"), 200)
        completed = wait_state(r, goal["goal_id"], "completed")
        assert completed["task"]["observations"][0]["path"] == "none"
        assert completed["steps_used"] == 1 and len(r.workspace.calls) == 1


def test_pause_can_stop_progress_with_stale_revision_but_resume_requires_fresh_revision(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.workspace.gated = True
        goal = propose(r)
        uncached(control(r, goal, "approve"), 200)
        assert r.workspace.entered.wait(2)
        paused = uncached(control(r, goal, "pause"), 200)["goal"]
        assert paused["state"] == "waiting_external" and r.workspace.finished.is_set()
        assert paused["task"]["intent_path"] == "notes.md"
        assert paused["task"]["observations"] == []
        uncached(control(r, goal, "resume"), 409)
        r.workspace.gated = False
        uncached(control(r, paused, "resume"), 200)
        completed = wait_state(r, goal["goal_id"], "completed")
        assert completed["steps_used"] == 2 and len(r.workspace.calls) == 2
        uncached(control(r, completed, "resume"), 409)


@pytest.mark.parametrize("method", ["snapshot", "propose"])
def test_unexpected_producer_errors_are_safe_503_without_raw_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    with rig(tmp_path) as r:
        canary = str(r.workspace.root) + " SYNTHETIC_KEY_DO_NOT_ECHO"

        async def fail(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(canary)

        monkeypatch.setattr(r.owner, method, fail)
        response = (
            r.client.get(TASK_ROUTE, headers=r.headers)
            if method == "snapshot"
            else r.client.post(TASK_ROUTE, headers=r.headers, json={"paths": ["notes.md"]})
        )
        assert uncached(response, 503) == {"detail": {"code": "unavailable"}}
        assert canary not in response.text and "RuntimeError" not in response.text
        assert r.workspace.calls == []


@pytest.mark.parametrize("trigger", ["foreground", "tools_disabled", "pause", "cancel"])
def test_controls_join_noncooperative_read_before_response_and_ignore_late_result(
    tmp_path: Path, trigger: str
) -> None:
    turn_seen: list[str] = []

    async def on_turn(session: str, text: str, input_mode: str) -> None:
        assert r.workspace.finished.is_set() and not r.owner.busy
        turn_seen.append(text)

    with rig(tmp_path, on_turn=on_turn) as r:
        r.workspace.gated = r.workspace.suppress_cancel = True
        goal = propose(r)
        uncached(control(r, goal, "approve"), 200)
        assert r.workspace.entered.wait(2)

        def stop() -> Response:
            if trigger == "foreground":
                return cast(
                    Response,
                    r.client.post(
                        "/v1/conversations/browser/turns", headers=r.headers, json={"text": "hello"}
                    ),
                )
            if trigger == "tools_disabled":
                return cast(
                    Response,
                    r.client.put(
                        "/v1/kill-switches/tools", headers=r.headers, json={"enabled": False}
                    ),
                )
            return control(r, goal, trigger)

        with ThreadPoolExecutor(max_workers=1) as pool:
            stopping = pool.submit(stop)
            try:
                assert r.workspace.cancelled.wait(2)
                assert not stopping.done() and not r.workspace.finished.is_set()
                assert r.client.portal is not None
                r.client.portal.call(r.workspace.release.set)
                response = stopping.result(timeout=3)
                assert response.status_code == 200, response.text
            finally:
                assert r.client.portal is not None
                r.client.portal.call(r.workspace.release.set)
        stopped = current(r, goal["goal_id"])
        assert stopped["state"] == ("cancelled" if trigger == "cancel" else "waiting_external")
        assert stopped["task"]["observations"] == [] and len(r.workspace.calls) == 1
        assert r.workspace.finished.is_set() and not r.owner.busy
        assert turn_seen == (["hello"] if trigger == "foreground" else [])
        if trigger == "tools_disabled":
            uncached(control(r, stopped, "resume"), 403)


def test_shutdown_closes_task_before_workspace_and_persists_pause(tmp_path: Path) -> None:
    stopped: list[str] = []

    async def close_workspace() -> None:
        assert r.workspace.finished.is_set() and not r.owner.busy and not r.owner._started
        stopped.append("workspace closed after task join")

    with rig(tmp_path, on_shutdown=close_workspace) as r:
        r.workspace.gated = True
        goal = propose(r)
        uncached(control(r, goal, "approve"), 200)
        assert r.workspace.entered.wait(2)
    assert stopped == ["workspace closed after task join"]
    with closing(sqlite3.connect(r.store.path)) as connection:
        state, task_json = connection.execute(
            "SELECT state,task_json FROM goals WHERE goal_id=?", (goal["goal_id"],)
        ).fetchone()
    assert state == "waiting_external"
    assert json.loads(task_json)["pause_reason"] == "shutdown"


def test_opted_in_shortcut_turn_pauses_and_joins_existing_read_before_return(
    tmp_path: Path,
) -> None:
    with rig(tmp_path, legacy_shortcuts=True) as r:
        r.workspace.gated = True
        goal = propose(r)
        uncached(control(r, goal, "approve"), 200)
        assert r.workspace.entered.wait(2)
        response = r.client.post(
            "/v1/conversations/browser/turns",
            headers=r.headers,
            json={"text": "幫我打開計算機"},
        )
        assert response.status_code == 200
        assert r.state.active_turns["browser"]["state"] == "awaiting_approval"
        assert r.workspace.cancelled.is_set() and r.workspace.finished.is_set()
        assert not r.owner.busy
        paused = current(r, goal["goal_id"])
        assert paused["state"] == "waiting_external"
        assert paused["task"]["pause_reason"] == "foreground"
        assert paused["task"]["observations"] == []


@pytest.mark.parametrize("late_outcome", ["error", "success"])
def test_old_turn_callback_cannot_terminate_newer_same_session_foreground(
    tmp_path: Path, late_outcome: str
) -> None:
    entered_first, entered_second = Event(), Event()
    release_first, release_second = asyncio.Event(), asyncio.Event()

    async def controlled_turn(session: str, text: str, input_mode: str) -> None:
        assert session == "browser" and input_mode == "text"
        if text == "first":
            entered_first.set()
            await release_first.wait()
            if late_outcome == "error":
                raise RuntimeError("SYNTHETIC_OLD_TURN_CALLBACK_ERROR")
        else:
            assert text == "second"
            entered_second.set()
            await release_second.wait()

    with (
        rig(tmp_path, on_turn=controlled_turn, raise_server_exceptions=False) as r,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        first = pool.submit(
            r.client.post,
            "/v1/conversations/browser/turns",
            headers=r.headers,
            json={"text": "first"},
        )
        second = None
        try:
            assert entered_first.wait(2)
            first_turn_id = r.state.active_turns["browser"]["turn_id"]
            second = pool.submit(
                r.client.post,
                "/v1/conversations/browser/turns",
                headers=r.headers,
                json={"text": "second"},
            )
            assert entered_second.wait(2)
            second_turn_id = r.state.active_turns["browser"]["turn_id"]
            assert first_turn_id != second_turn_id
            assert r.client.portal is not None
            r.client.portal.call(release_first.set)
            assert first.result(timeout=3).status_code == (500 if late_outcome == "error" else 200)
            assert r.state.active_turns["browser"] == {
                "turn_id": second_turn_id,
                "state": "responding",
            }
            r.client.portal.call(release_second.set)
            assert second.result(timeout=3).status_code == 200
            assert r.state.active_turns["browser"] == {
                "turn_id": second_turn_id,
                "state": "completed",
            }
        finally:
            assert r.client.portal is not None
            r.client.portal.call(release_first.set)
            r.client.portal.call(release_second.set)
            first.result(timeout=3)
            if second is not None:
                second.result(timeout=3)


@pytest.mark.parametrize(
    ("profile", "enabled", "foreground_window", "callback_error"),
    [
        ("candidate", "1", False, False),
        ("candidate", "0", False, False),
        ("legacy", "1", False, False),
        ("candidate", "1", True, False),
        ("candidate", "1", False, True),
    ],
)
def test_actual_main_composition_owner_feature_flag_and_real_rust(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    enabled: str,
    foreground_window: bool,
    callback_error: bool,
) -> None:
    import uvicorn

    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    documents = tmp_path / "documents"
    documents.mkdir()
    text = "# Owner-approved synthetic task\n- [ ] verify actual source\nTODO still pending\n"
    (documents / "notes.md").write_text(text)
    binary = Path(__file__).parents[2] / "target/debug/siro-runtime"
    assert binary.is_file(), "build the existing Rust runtime before this integration gate"
    origin = "http://127.0.0.1:38131"
    for key, value in {
        "SIRO_DATA_DIR": str(tmp_path / "data"),
        "SIRO_WORKSPACE_DIR": str(documents),
        "SIRO_RUNTIME_BINARY": str(binary),
        "SIRO_RUNTIME_PROFILE": profile,
        "SIRO_GOAL_TASKS_ENABLED": enabled,
        "SIRO_GATEWAY_PORT": "38131",
    }.items():
        monkeypatch.setenv(key, value)
    captured: dict[str, Any] = {}
    original_factory = gateway.create_app

    def factory(**kwargs: Any) -> Any:
        if callback_error:

            async def failed_turn(*args: Any, **kwargs: Any) -> None:
                raise RuntimeError("synthetic controlled turn callback failure")

            kwargs["on_turn"] = failed_turn
        captured.update(kwargs)
        return original_factory(**kwargs)

    def serve(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=origin, raise_server_exceptions=not callback_error) as client:
            headers = token_headers(client, origin)
            assert client.get("/v1/snapshot", headers=headers).status_code == 200
            owner = captured["read_task_owner"]
            if profile != "candidate" or enabled == "0":
                assert owner is None
                uncached(client.get(TASK_ROUTE, headers=headers), 503)
                return
            assert isinstance(owner, ReadTaskOwner)
            assert owner.available and not owner.busy
            proposed = uncached(
                client.post(TASK_ROUTE, headers=headers, json={"paths": ["notes.md"]}), 200
            )["goal"]
            assert proposed["state"] == "proposed" and not owner.busy
            if callback_error:
                failed = client.post(
                    "/v1/conversations/browser/turns",
                    headers=headers,
                    json={"text": "synthetic callback error"},
                )
                assert failed.status_code == 500

            def approve() -> None:
                uncached(
                    client.post(
                        f"{TASK_ROUTE}/{proposed['goal_id']}/approve",
                        headers=headers,
                        json={"revision": proposed["revision"]},
                    ),
                    200,
                )

            if foreground_window:
                controller = captured["on_turn"].__self__
                repository = controller._agent_runs
                original_recent = repository.recent_session_messages
                entered, release = Event(), asyncio.Event()

                async def held_recent(*args: Any, **kwargs: Any) -> Any:
                    entered.set()
                    await release.wait()
                    return await original_recent(*args, **kwargs)

                monkeypatch.setattr(repository, "recent_session_messages", held_recent)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    foreground = pool.submit(
                        client.post,
                        "/v1/conversations/browser/turns",
                        headers=headers,
                        json={"text": "hello synthetic foreground"},
                    )
                    try:
                        assert entered.wait(2)
                        assert not controller.foreground_active
                        assert captured["state"].active_turns["browser"]["state"] == "responding"
                        approve()
                        deadline = time.monotonic() + 3
                        while True:
                            paused = uncached(client.get(TASK_ROUTE, headers=headers), 200)[
                                "goals"
                            ][0]
                            if paused["state"] in {"waiting_external", "completed", "failed"}:
                                break
                            assert time.monotonic() < deadline, paused
                            time.sleep(0.01)
                        assert paused["state"] == "waiting_external", paused
                        assert paused["task"]["pause_reason"] == "foreground"
                        assert paused["steps_used"] == 0 and paused["task"]["observations"] == []
                    finally:
                        assert client.portal is not None
                        client.portal.call(release.set)
                        assert foreground.result(timeout=3).status_code == 200
                return
            approve()
            deadline = time.monotonic() + 3
            while True:
                complete = uncached(client.get(TASK_ROUTE, headers=headers), 200)["goals"][0]
                if complete["state"] == "completed":
                    break
                assert time.monotonic() < deadline, complete
                time.sleep(0.01)
            observation = complete["task"]["observations"][0]
            assert observation["sha256"] == hashlib.sha256(text.encode()).hexdigest()
            assert [line["line"] for line in observation["matches"]] == [2, 3]
            assert complete["steps_used"] == 1
            if callback_error:
                assert captured["state"].active_turns["browser"]["state"] == "failed"
        if captured["read_task_owner"] is not None:
            assert not captured["read_task_owner"]._started and not captured["read_task_owner"].busy
        workspace = captured["workspace_service"]
        if workspace is not None:
            assert workspace._process is None and workspace._temporary is None

    monkeypatch.setattr(gateway, "create_app", factory)
    monkeypatch.setattr(uvicorn, "run", serve)
    gateway.main()


def test_schema13_upgrade_preserves_legacy_goal_and_refuses_old_release_approval(
    tmp_path: Path,
) -> None:
    database = tmp_path / "synthetic-schema13.sqlite3"
    old_goal = (
        "legacy-owner-goal",
        "running",
        "untouched",
        None,
        '{"steps_used":1,"max_steps":3,"cost_used":0,"max_cost":0}',
        7,
    )
    with closing(sqlite3.connect(database)) as connection:
        apply_migrations(connection, load_migrations()[:13])
        connection.execute("INSERT INTO goals VALUES (?,?,?,?,?,?)", old_goal)
        connection.commit()
        migrations_before = connection.execute(
            "SELECT * FROM schema_migrations ORDER BY version"
        ).fetchall()
    root = tmp_path / "synthetic-approved-source"
    release = root / "releases/1.0.0"
    for name in (
        "src/siro/__init__.py",
        "src/siro/core/releases.py",
        "src/siro/services/presentation/gateway.py",
    ):
        path = release / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic source identity; never imported or executed\n")
    files = sorted(path for path in release.rglob("*") if path.is_file())
    wire = bytearray(b"siro-release-source-v2\0")
    wire.extend(len(files).to_bytes(8, "big"))
    for path in files:
        relative, content = path.relative_to(release).as_posix().encode(), path.read_bytes()
        wire.extend(len(relative).to_bytes(8, "big"))
        wire.extend(relative)
        wire.extend(len(content).to_bytes(8, "big"))
        wire.extend(content)
    unsigned = {
        "version": "1.0.0",
        "source_sha256": hashlib.sha256(wire).hexdigest(),
        "min_schema": 13,
        "max_schema": 13,
        "signing_format": "siro-release-manifest-v2",
    }
    key = b"synthetic-schema-transition-key"  # pragma: allowlist secret
    signature = hmac.new(
        key, json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256
    ).hexdigest()
    (root / "manifests").mkdir()
    (root / "manifests/1.0.0.json").write_text(json.dumps({**unsigned, "signature": signature}))
    (root / "active.json").write_text('{"version":"1.0.0"}')
    assert (
        ReleaseManager(root, key, current_schema=13, database=database)
        .resolve_launch_target()
        .schema_version
        == 13
    )
    asyncio.run(SQLiteStore(database).initialize())
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute(
            "SELECT goal_id,state,next_step,deadline,budget_json,revision FROM goals"
        ).fetchall() == [old_goal]
        assert connection.execute("SELECT task_json FROM goals").fetchone() == (None,)
        assert (
            connection.execute(
                "SELECT * FROM schema_migrations WHERE version<=13 ORDER BY version"
            ).fetchall()
            == migrations_before
        )
        assert connection.execute("SELECT max(version) FROM schema_migrations").fetchone() == (14,)
        before = tuple(connection.iterdump())
    for maximum in (13, 14):
        with pytest.raises(ReleaseLaunchError) as error:
            ReleaseManager(
                root, key, current_schema=maximum, database=database
            ).resolve_launch_target()
        assert error.value.status == "incompatible_schema"
    with closing(sqlite3.connect(database)) as connection:
        assert tuple(connection.iterdump()) == before
    assert (root / "active.json").read_text() == '{"version":"1.0.0"}'
