from __future__ import annotations

import asyncio
import importlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.services.presentation import gateway
from siro.services.tools.execution import ExecutionCancelled, ExecutionCleanupError
from siro.services.tools.orchestrator import ToolCatalog

ORIGIN = "http://testserver"
CAPABILITY = "text.checklist.parse"
PROFILE = "markdown-checklist-v1"
REVIEW = {
    "status": "awaiting_review",
    "enabled": False,
    "installed": False,
    "authorizes_execution": False,
    "approval_required": True,
}


class PreparedService:
    def __init__(self, catalog: object = None) -> None:
        self.catalog = catalog
        self.busy = False
        self.calls: list[str] = []
        self.cancel_calls = 0
        self.close_calls = 0
        self.error: BaseException | None = None
        self.cancel_error: BaseException | None = None
        self.close_error: BaseException | None = None

    async def prepare(self, capability: str) -> dict[str, object]:
        self.calls.append(capability)
        if self.error is not None:
            raise self.error
        return dict(REVIEW)

    async def cancel(self) -> bool:
        self.cancel_calls += 1
        if self.cancel_error is not None:
            raise self.cancel_error
        return self.busy

    async def close(self) -> None:
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


def application(service: PreparedService | None, **kwargs: Any) -> FastAPI:
    return gateway.create_app(
        allowed_origins={ORIGIN},
        runtime_profile="candidate",
        skill_candidates=cast(Any, service),
        **kwargs,
    )


def authenticated(client: TestClient, origin: str = ORIGIN) -> dict[str, str]:
    result = client.post("/v1/session", headers={"origin": origin})
    assert result.status_code == 200
    return {"origin": origin, "authorization": f"Bearer {result.json()['token']}"}


def candidate_exception(name: str) -> BaseException:
    module = importlib.import_module("siro.services.tools.skill_candidates")
    exception: Callable[[str], BaseException] = getattr(module, name)
    return exception("private-path-or-key-canary")


def test_explicit_owner_prepares_review_without_an_approval_or_enable_action() -> None:
    service = PreparedService()
    with TestClient(application(service)) as client:
        headers = authenticated(client)
        result = client.post(
            "/v1/skills/candidates", headers=headers, json={"capability": CAPABILITY}
        )
        assert result.status_code == 200
        assert result.json() == REVIEW
        assert service.calls == [CAPABILITY]
        assert client.post("/v1/skills/candidates/enable", headers=headers).status_code == 404
        assert client.post("/v1/skills/candidates/approve", headers=headers).status_code == 404
    assert service.close_calls == 1


@pytest.mark.parametrize(
    "profile,inject", [("candidate", False), ("legacy", False), ("legacy", True)]
)
def test_missing_or_legacy_service_is_unavailable(profile: str, inject: bool) -> None:
    service = PreparedService()
    app = gateway.create_app(
        allowed_origins={ORIGIN},
        runtime_profile=profile,
        skill_candidates=cast(Any, service) if inject else None,
    )
    with TestClient(app) as client:
        headers = authenticated(client)
        for path in ("/v1/skills/candidates", "/v1/skills/candidates/cancel"):
            result = client.post(path, headers=headers, json={"capability": CAPABILITY})
            assert result.status_code == 503
            assert result.json() == {"detail": "skill candidates are unavailable"}
        view = client.get("/v1/runtime", headers=headers).json()["skill_candidates"]
        assert view == {
            "available": False,
            "busy": False,
            "profile": PROFILE,
            "authorizes_execution": False,
        }
    assert service.calls == [] and service.cancel_calls == 0 and service.close_calls == 0


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"capability": ""},
        {"capability": "x" * 129},
        {"capability": 1},
        {"capability": True},
        {"capability": None},
        {"capability": []},
        {"capability": CAPABILITY, "code": "private-source-canary"},
        {"capability": CAPABILITY, "enabled": True},
        {"capability": CAPABILITY, "profile": "host"},
        {"capability": CAPABILITY, "path": "/private"},
    ],
)
def test_candidate_input_is_only_a_bounded_strict_capability(body: dict[str, object]) -> None:
    service = PreparedService()
    with TestClient(application(service)) as client:
        result = client.post("/v1/skills/candidates", headers=authenticated(client), json=body)
        assert result.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize("path", ["/v1/skills/candidates", "/v1/skills/candidates/cancel"])
def test_candidate_controls_require_session_and_same_origin(path: str) -> None:
    service = PreparedService()
    with TestClient(application(service)) as client:
        headers = authenticated(client)
        checks = [
            ({"origin": ORIGIN}, 401),
            ({"origin": ORIGIN, "authorization": "Bearer invalid"}, 401),
            ({"authorization": headers["authorization"]}, 403),
            ({**headers, "origin": "https://evil.invalid"}, 403),
        ]
        for request_headers, expected in checks:
            assert (
                client.post(
                    path, headers=request_headers, json={"capability": CAPABILITY}
                ).status_code
                == expected
            )
    assert service.calls == [] and service.cancel_calls == 0


def test_runtime_metadata_is_read_only_and_tools_off_still_allows_cancel() -> None:
    service = PreparedService()
    state = gateway.GatewayState()
    with TestClient(application(service, state=state)) as client:
        headers = authenticated(client)
        assert client.get("/v1/runtime").status_code == 401
        for busy in (False, True):
            service.busy = busy
            result = client.get("/v1/runtime", headers=headers).json()["skill_candidates"]
            assert result == {
                "available": True,
                "busy": busy,
                "profile": PROFILE,
                "authorizes_execution": False,
            }
        state.kill_switches["tools"] = False
        assert not client.get("/v1/runtime", headers=headers).json()["skill_candidates"][
            "available"
        ]
        assert (
            client.post(
                "/v1/skills/candidates", headers=headers, json={"capability": CAPABILITY}
            ).status_code
            == 403
        )
        assert client.post("/v1/skills/candidates/cancel", headers=headers).json() == {
            "cancelled": True
        }
    assert service.calls == [] and service.cancel_calls == 1


def test_authenticated_control_snapshot_reports_current_candidate_metadata() -> None:
    service = PreparedService()
    service.busy = True
    with TestClient(application(service)) as client:
        headers = authenticated(client)
        token = headers["authorization"].removeprefix("Bearer ")
        view = client.get("/v1/snapshot", headers=headers).json()
        assert view["runtime_profile"] == "candidate"
        assert view["skill_candidates"] == {
            "available": True,
            "busy": True,
            "profile": PROFILE,
            "authorizes_execution": False,
        }
        with client.websocket_connect("/ws/control", headers={"origin": ORIGIN}) as socket:
            socket.send_json({"type": "authenticate", "token": token})
            snapshot = socket.receive_json()
            assert snapshot["type"] == "snapshot"
            assert snapshot["runtime_profile"] == "candidate"
            assert snapshot["skill_candidates"] == view["skill_candidates"]
    assert service.calls == [] and service.cancel_calls == 0


@pytest.mark.parametrize(
    "error_name,status,detail",
    [
        ("SkillCandidateBusy", 409, "skill candidate preparation is busy"),
        ("SkillCandidateClosed", 503, "skill candidates are unavailable"),
        ("CancelledError", 409, "skill candidate preparation was cancelled"),
        ("ExecutionCancelled", 409, "skill candidate preparation was cancelled"),
        ("ExecutionCleanupError", 503, "skill candidate cleanup failed"),
    ],
)
def test_candidate_failures_have_fixed_public_details(
    error_name: str, status: int, detail: str
) -> None:
    service = PreparedService()
    if error_name == "CancelledError":
        service.error = asyncio.CancelledError("private-path-or-key-canary")
    elif error_name == "ExecutionCancelled":
        service.error = ExecutionCancelled("private-path-or-key-canary")
    elif error_name == "ExecutionCleanupError":
        service.error = ExecutionCleanupError("private-path-or-key-canary")
    else:
        service.error = candidate_exception(error_name)
    with TestClient(application(service)) as client:
        result = client.post(
            "/v1/skills/candidates", headers=authenticated(client), json={"capability": CAPABILITY}
        )
        assert result.status_code == status
        assert result.json() == {"detail": detail}
        assert "private-path-or-key-canary" not in result.text


def test_tools_switch_cancels_only_candidate_work_and_keeps_other_switches() -> None:
    service = PreparedService()
    with TestClient(application(service)) as client:
        headers = authenticated(client)
        for name, enabled in (("cloud", False), ("tools", True), ("microphone", False)):
            assert (
                client.put(
                    f"/v1/kill-switches/{name}", headers=headers, json={"enabled": enabled}
                ).status_code
                == 200
            )
        assert service.cancel_calls == 0
        assert (
            client.put(
                "/v1/kill-switches/tools", headers=headers, json={"enabled": False}
            ).status_code
            == 200
        )
        assert service.cancel_calls == 1


@pytest.mark.parametrize("action", ["cancel", "kill"])
def test_cancel_cleanup_failure_is_public_and_tools_remain_disabled(action: str) -> None:
    service = PreparedService()
    service.cancel_error = ExecutionCleanupError("private-path-or-key-canary")
    with TestClient(application(service)) as client:
        headers = authenticated(client)
        if action == "cancel":
            result = client.post("/v1/skills/candidates/cancel", headers=headers)
        else:
            result = client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": False})
            assert (
                client.get("/v1/runtime", headers=headers).json()["kill_switches"]["tools"] is False
            )
        assert result.status_code == 503
        assert result.json() == {"detail": "skill candidate cleanup failed"}
        assert "private-path-or-key-canary" not in result.text


@pytest.mark.parametrize("failure", ["service", "controller"])
def test_shutdown_closes_candidate_and_preserves_remaining_cleanup(failure: str) -> None:
    service = PreparedService()
    hub = gateway.GatewayHub()
    cleaned: list[str] = []

    async def controller_close() -> None:
        cleaned.append("controller")
        if failure == "controller":
            raise RuntimeError("synthetic controller close")

    async def hub_close() -> None:
        cleaned.append("hub")

    hub.shutdown = hub_close  # type: ignore[method-assign]
    if failure == "service":
        service.close_error = ExecutionCleanupError("synthetic candidate cleanup")
    with (
        pytest.raises(ExecutionCleanupError if failure == "service" else RuntimeError),
        TestClient(application(service, hub=hub, on_shutdown=controller_close)),
    ):
        pass
    assert service.close_calls == 1
    assert cleaned == ["controller", "hub"]


@pytest.mark.asyncio
async def test_concurrent_request_busy_and_explicit_cancel_return_without_review() -> None:
    entered = asyncio.Event()
    service = PreparedService()
    active: asyncio.Task[dict[str, object]] | None = None

    async def prepare(capability: str) -> dict[str, object]:
        nonlocal active
        if service.busy:
            raise candidate_exception("SkillCandidateBusy")
        active = asyncio.current_task()
        service.busy = True
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            service.busy = False
        return dict(REVIEW)

    async def cancel() -> bool:
        if active is None or active.done():
            return False
        active.cancel()
        return True

    service.prepare = prepare  # type: ignore[method-assign]
    service.cancel = cancel  # type: ignore[method-assign]
    app = application(service)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client,
    ):
        token = (await client.post("/v1/session", headers={"origin": ORIGIN})).json()["token"]
        headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
        request = asyncio.create_task(
            client.post("/v1/skills/candidates", headers=headers, json={"capability": CAPABILITY})
        )
        await asyncio.wait_for(entered.wait(), 2)
        assert (await client.get("/v1/runtime", headers=headers)).json()["skill_candidates"]["busy"]
        busy = await client.post(
            "/v1/skills/candidates", headers=headers, json={"capability": CAPABILITY}
        )
        assert busy.status_code == 409
        assert (await client.post("/v1/skills/candidates/cancel", headers=headers)).json() == {
            "cancelled": True
        }
        cancelled = await asyncio.wait_for(request, 2)
        assert cancelled.status_code == 409 and "awaiting_review" not in cancelled.text
        assert not service.busy


@pytest.mark.parametrize("profile", ["candidate", "legacy"])
def test_main_composes_one_live_catalog_owner_without_model_tool_or_registry_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_CONTEXT_SUMMARY_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_BINARY", str(tmp_path / "missing-runtime"))
    monkeypatch.setattr("shutil.which", lambda name: None)
    effects: list[str] = []

    async def forbid(*args: object, **kwargs: object) -> None:
        effects.append("external execution")
        raise AssertionError("candidate control invoked an external effect")

    monkeypatch.setattr("asyncio.create_subprocess_exec", forbid)
    from siro.adapters.models.mock import OfflineDemoModel
    from siro.persistence.skills import SQLiteSkillRegistry

    monkeypatch.setattr(OfflineDemoModel, "stream", forbid)
    monkeypatch.setattr(SQLiteSkillRegistry, "install", forbid)
    monkeypatch.setattr(SQLiteSkillRegistry, "set_enabled", forbid)
    services: list[PreparedService] = []

    def preparer(catalog: object) -> PreparedService:
        service = PreparedService(catalog)
        services.append(service)
        return service

    module = importlib.import_module("siro.services.tools.skill_candidates")
    monkeypatch.setattr(module, "SkillCandidatePreparer", preparer)
    monkeypatch.setattr(gateway, "SkillCandidatePreparer", preparer, raising=False)
    original_create_app = gateway.create_app

    def composed_app(**kwargs: Any) -> FastAPI:
        owner = kwargs["skill_candidates"]
        if profile == "candidate":
            assert owner.catalog is kwargs["tool_orchestrator"].catalog
        else:
            assert owner is None
        return original_create_app(**kwargs)

    monkeypatch.setattr(gateway, "create_app", composed_app)

    def run(app: FastAPI, **kwargs: object) -> None:
        origin = "http://127.0.0.1:8000"
        with TestClient(app) as client:
            headers = authenticated(client, origin)
            runtime = client.get("/v1/runtime", headers=headers).json()
            assert runtime["routes"]["model"] == "offline"
            assert runtime["skill_candidates"]["available"] is (profile == "candidate")
            result = client.post(
                "/v1/skills/candidates", headers=headers, json={"capability": CAPABILITY}
            )
            if profile == "candidate":
                assert len(services) == 1
                service = services[0]
                assert service.catalog is not None
                catalog = cast(ToolCatalog, service.catalog)
                assert json.loads(
                    json.dumps(
                        [
                            {key: value for key, value in row.items() if key != "checked_at"}
                            for row in catalog.snapshot()
                        ]
                    )
                ) == [
                    {key: value for key, value in row.items() if key != "checked_at"}
                    for row in runtime["tools"]
                ]
                assert result.status_code == 200 and result.json() == REVIEW
                assert service.calls == [CAPABILITY]
                assert all(row["name"] != CAPABILITY for row in runtime["tools"])
            else:
                assert services == [] and result.status_code == 503

    monkeypatch.setattr(uvicorn, "run", run)
    gateway.main()
    assert effects == []
    if services:
        assert services[0].close_calls == 1
