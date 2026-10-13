from __future__ import annotations

import asyncio
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_skill_candidate_product import CAPABILITY, ORIGIN, PreparedService, authenticated

from siro.services.presentation import gateway
from siro.services.tools.execution import ExecutionCancelled, ExecutionCleanupError
from siro.services.tools.skill_activation import SkillActivationError

HASH = "siro-skill-package-v1:" + "a" * 64
REVIEW_ID = "621f1ee2-8092-4ccb-8794-cf52683e1405"
BASE = {
    "available": True,
    "installed": False,
    "enabled": False,
    "package_hash": None,
    "profile": "markdown-checklist-v1",
    "capability": CAPABILITY,
    "authorizes_execution": False,
    "busy": False,
}


class ActivationService:
    def __init__(self) -> None:
        self.view = dict(BASE)
        self.calls: list[tuple[str, object]] = []
        self.error: BaseException | None = None
        self.close_error: BaseException | None = None

    async def initialize(self) -> None:
        self.calls.append(("initialize", None))

    async def remember(self, result: dict[str, object]) -> dict[str, object]:
        self.calls.append(("remember", dict(result)))
        if self.error is not None:
            raise self.error
        return {**result, "review_id": REVIEW_ID, "package_hash": HASH}

    async def install(self, review_id: str, package_hash: str) -> dict[str, object]:
        self.calls.append(("install", (review_id, package_hash)))
        if self.error is not None:
            raise self.error
        self.view.update(installed=True, enabled=False, package_hash=package_hash)
        return self.snapshot()

    async def enable(self, package_hash: str) -> dict[str, object]:
        self.calls.append(("enable", package_hash))
        if self.error is not None:
            raise self.error
        self.view.update(installed=True, enabled=True, package_hash=package_hash)
        return self.snapshot()

    async def revoke(self, package_hash: str) -> dict[str, object]:
        self.calls.append(("revoke", package_hash))
        if self.error is not None:
            raise self.error
        self.view.update(enabled=False)
        return self.snapshot()

    async def suspend(self) -> None:
        self.calls.append(("suspend", None))
        self.view.update(enabled=False)

    async def close(self) -> None:
        self.calls.append(("close", None))
        self.view.update(available=False, enabled=False)
        if self.close_error is not None:
            raise self.close_error

    def snapshot(self) -> dict[str, object]:
        return dict(self.view)


def application(owner: ActivationService | None, **kwargs: Any) -> FastAPI:
    return gateway.create_app(
        allowed_origins={ORIGIN},
        runtime_profile="candidate",
        skill_activation=cast(Any, owner),
        **kwargs,
    )


def body(action: str) -> dict[str, object]:
    return {"package_hash": HASH, **({"review_id": REVIEW_ID} if action == "install" else {})}


def test_explicit_actions_prepare_install_disabled_enable_and_revoke_are_separate() -> None:
    owner = ActivationService()
    candidate = PreparedService()
    with TestClient(application(owner, skill_candidates=cast(Any, candidate))) as client:
        headers = authenticated(client)
        review = client.post(
            "/v1/skills/candidates", headers=headers, json={"capability": CAPABILITY}
        )
        assert review.json()["review_id"] == REVIEW_ID
        assert owner.calls[1][0] == "remember"
        assert all(action != "install" for action, _ in owner.calls)
        installed = client.post(
            "/v1/skills/activation/install", headers=headers, json=body("install")
        )
        assert installed.status_code == 200
        assert installed.json()["installed"] is True and installed.json()["enabled"] is False
        enabled = client.post("/v1/skills/activation/enable", headers=headers, json=body("enable"))
        assert enabled.status_code == 200 and enabled.json()["enabled"] is True
        revoked = client.post("/v1/skills/activation/revoke", headers=headers, json=body("revoke"))
        assert revoked.status_code == 200 and revoked.json()["enabled"] is False
        assert client.post("/v1/skills/activation/execute", headers=headers).status_code == 404
    assert [action for action, _ in owner.calls] == [
        "initialize",
        "remember",
        "install",
        "enable",
        "revoke",
        "close",
    ]
    assert owner.calls[2][1] == (REVIEW_ID, HASH)


@pytest.mark.parametrize("action", ["install", "enable", "revoke"])
def test_controls_require_session_and_same_origin_without_owner_effects(action: str) -> None:
    owner = ActivationService()
    with TestClient(application(owner)) as client:
        headers = authenticated(client)
        for request_headers, expected in [
            ({"origin": ORIGIN}, 401),
            ({"origin": ORIGIN, "authorization": "Bearer invalid"}, 401),
            ({"authorization": headers["authorization"]}, 403),
            ({**headers, "origin": "https://evil.invalid"}, 403),
        ]:
            result = client.post(
                f"/v1/skills/activation/{action}", headers=request_headers, json=body(action)
            )
            assert result.status_code == expected
    assert [action for action, _ in owner.calls] == ["initialize", "close"]


@pytest.mark.parametrize("action", ["install", "enable", "revoke"])
@pytest.mark.parametrize(
    "change",
    [
        {"package_hash": 1},
        {"package_hash": True},
        {"package_hash": "forged"},
        {"package_hash": "siro-skill-package-v1:" + "a" * 65},
        {"package_hash": "siro-skill-package-v1:" + "A" * 64},
        {"files": {"plugin.py": "private-source-canary"}},
        {"profile": "trusted-local"},
        {"enabled": True},
        {"path": "/private"},
    ],
)
def test_controls_accept_only_exact_bounded_server_identity(
    action: str, change: dict[str, object]
) -> None:
    owner = ActivationService()
    with TestClient(application(owner)) as client:
        result = client.post(
            f"/v1/skills/activation/{action}",
            headers=authenticated(client),
            json={**body(action), **change},
        )
        assert result.status_code == 422
    assert [action for action, _ in owner.calls] == ["initialize", "close"]


@pytest.mark.parametrize("review_id", [1, True, "", "forged", REVIEW_ID + "x"])
def test_install_requires_strict_review_id(review_id: object) -> None:
    owner = ActivationService()
    with TestClient(application(owner)) as client:
        result = client.post(
            "/v1/skills/activation/install",
            headers=authenticated(client),
            json={"package_hash": HASH, "review_id": review_id},
        )
        assert result.status_code == 422
    assert [action for action, _ in owner.calls] == ["initialize", "close"]


@pytest.mark.parametrize(
    "action,payload",
    [
        ("install", {}),
        ("install", {"review_id": REVIEW_ID}),
        ("install", {"package_hash": HASH}),
        ("enable", {}),
        ("revoke", {}),
        ("enable", {"package_hash": HASH, "review_id": REVIEW_ID}),
        ("revoke", {"package_hash": HASH, "review_id": REVIEW_ID}),
    ],
)
def test_required_body_fields_and_no_review_id_on_enable_or_revoke(
    action: str, payload: dict[str, object]
) -> None:
    owner = ActivationService()
    with TestClient(application(owner)) as client:
        assert (
            client.post(
                f"/v1/skills/activation/{action}", headers=authenticated(client), json=payload
            ).status_code
            == 422
        )
    assert [action for action, _ in owner.calls] == ["initialize", "close"]


def test_startup_with_tools_off_suspends_restored_activation_before_serving_requests() -> None:
    owner = ActivationService()
    owner.view.update(installed=True, enabled=True, package_hash=HASH)
    state = gateway.GatewayState()
    state.kill_switches["tools"] = False
    with TestClient(application(owner, state=state)) as client:
        assert [action for action, _ in owner.calls] == ["initialize", "suspend"]
        view = client.get("/v1/runtime", headers=authenticated(client)).json()["skill_activation"]
        assert view["installed"] is True and view["enabled"] is False
    assert [action for action, _ in owner.calls] == ["initialize", "suspend", "close"]


@pytest.mark.parametrize(
    "profile,inject", [("candidate", False), ("legacy", False), ("legacy", True)]
)
def test_missing_or_legacy_owner_is_inert(profile: str, inject: bool) -> None:
    owner = ActivationService()
    app = gateway.create_app(
        allowed_origins={ORIGIN},
        runtime_profile=profile,
        skill_activation=cast(Any, owner) if inject else None,
    )
    with TestClient(app) as client:
        headers = authenticated(client)
        for action in ("install", "enable", "revoke"):
            result = client.post(
                f"/v1/skills/activation/{action}", headers=headers, json=body(action)
            )
            assert result.status_code == 503
            assert result.json() == {"detail": "skill activation is unavailable"}
        view = client.get("/v1/runtime", headers=headers).json()["skill_activation"]
        assert view == {**BASE, "available": False}
    assert owner.calls == []


def test_runtime_and_control_snapshot_only_read_activation_metadata() -> None:
    owner = ActivationService()
    with TestClient(application(owner)) as client:
        headers = authenticated(client)
        assert client.get("/v1/runtime").status_code == 401
        assert client.get("/v1/runtime", headers=headers).json()["skill_activation"] == BASE
        assert client.get("/v1/snapshot", headers=headers).json()["skill_activation"] == BASE
        token = headers["authorization"].removeprefix("Bearer ")
        with client.websocket_connect("/ws/control", headers={"origin": ORIGIN}) as socket:
            socket.send_json({"type": "authenticate", "token": token})
            assert socket.receive_json()["skill_activation"] == BASE
    assert [action for action, _ in owner.calls] == ["initialize", "close"]


def test_tools_off_suspends_even_if_candidate_cancel_fails_and_revoke_remains_available() -> None:
    owner = ActivationService()
    owner.view.update(installed=True, enabled=True, package_hash=HASH)
    candidate = PreparedService()
    candidate.cancel_error = ExecutionCleanupError("private-cleanup-canary")
    with TestClient(application(owner, skill_candidates=cast(Any, candidate))) as client:
        headers = authenticated(client)
        result = client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": False})
        assert result.status_code == 503
        assert ("suspend", None) in owner.calls
        assert owner.view["enabled"] is False
        for action in ("install", "enable"):
            assert (
                client.post(
                    f"/v1/skills/activation/{action}", headers=headers, json=body(action)
                ).status_code
                == 403
            )
        assert (
            client.post(
                "/v1/skills/activation/revoke", headers=headers, json=body("revoke")
            ).status_code
            == 200
        )
        client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": True})
        assert not owner.view["enabled"]
    assert sum(action == "enable" for action, _ in owner.calls) == 0


@pytest.mark.asyncio
async def test_tools_off_blocks_skill_owner_before_waiting_for_candidate_cancel() -> None:
    owner = ActivationService()
    owner.view.update(installed=True, enabled=True, package_hash=HASH)
    candidate = PreparedService()
    started, release = asyncio.Event(), asyncio.Event()

    async def cancel() -> bool:
        started.set()
        await release.wait()
        return True

    candidate.cancel = cancel  # type: ignore[method-assign]
    app = application(owner, skill_candidates=cast(Any, candidate))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client:
        token = (await client.post("/v1/session", headers={"origin": ORIGIN})).json()["token"]
        headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
        stopping = asyncio.create_task(
            client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": False})
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        try:
            assert owner.view["enabled"] is False
            assert ("suspend", None) in owner.calls
        finally:
            release.set()
            result = await stopping
        assert result.status_code == 200


@pytest.mark.parametrize("action", ["install", "enable", "revoke"])
@pytest.mark.parametrize(
    "error,status,detail",
    [
        (
            SkillActivationError("private-path-canary"),
            409,
            "skill activation could not be completed",
        ),
        (ExecutionCancelled("private-path-canary"), 409, "skill activation was cancelled"),
        (asyncio.CancelledError("private-path-canary"), 409, "skill activation was cancelled"),
        (
            ExecutionCleanupError("private-path-canary"),
            503,
            "skill activation cleanup could not be confirmed",
        ),
    ],
)
def test_activation_failures_have_fixed_public_messages(
    action: str, error: BaseException, status: int, detail: str
) -> None:
    owner = ActivationService()
    owner.error = error
    with TestClient(application(owner)) as client:
        result = client.post(
            f"/v1/skills/activation/{action}", headers=authenticated(client), json=body(action)
        )
        assert result.status_code == status
        assert result.json() == {"detail": detail}
        assert "private" not in result.text


def test_prepare_remember_failure_is_fixed_safe_and_never_installs() -> None:
    owner = ActivationService()
    owner.error = SkillActivationError("private-path-canary")
    with TestClient(application(owner, skill_candidates=cast(Any, PreparedService()))) as client:
        result = client.post(
            "/v1/skills/candidates", headers=authenticated(client), json={"capability": CAPABILITY}
        )
        assert result.status_code == 409
        assert result.json() == {"detail": "skill activation could not be completed"}
    assert [action for action, _ in owner.calls] == ["initialize", "remember", "close"]


def test_candidate_close_failure_still_closes_activation_and_later_cleanup() -> None:
    owner = ActivationService()
    candidate = PreparedService()
    candidate.close_error = ExecutionCleanupError("private-cleanup-canary")
    stopped: list[str] = []

    async def shutdown() -> None:
        stopped.append("controller")

    with (
        pytest.raises(ExecutionCleanupError),
        TestClient(application(owner, skill_candidates=cast(Any, candidate), on_shutdown=shutdown)),
    ):
        pass
    assert [action for action, _ in owner.calls] == ["initialize", "close"]
    assert stopped == ["controller"]


def test_activation_close_failure_still_finishes_controller_and_hub_cleanup() -> None:
    owner = ActivationService()
    owner.close_error = ExecutionCleanupError("private-cleanup-canary")
    stopped: list[str] = []
    hub = gateway.GatewayHub()
    original_shutdown = hub.shutdown

    async def controller_shutdown() -> None:
        stopped.append("controller")

    async def hub_shutdown() -> None:
        await original_shutdown()
        stopped.append("hub")

    hub.shutdown = hub_shutdown  # type: ignore[method-assign]
    with (
        pytest.raises(ExecutionCleanupError),
        TestClient(application(owner, hub=hub, on_shutdown=controller_shutdown)),
    ):
        pass
    assert stopped == ["controller", "hub"]
