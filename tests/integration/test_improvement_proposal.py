from __future__ import annotations

import json
import subprocess
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from test_runtime_status_context import CaptureModel, failed_run

import siro.core.evolution as evolution
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.ports.models import Privacy
from siro.services.agent.runs import AgentRunState
from siro.services.presentation.gateway import GatewayHub, create_app
from siro.services.presentation.integrated import IntegratedCompanion


def fact(**changes: object) -> dict[str, object]:
    return {
        "source_run_id": str(uuid4()),
        "state": "failed",
        "error_class": "HTTPStatusError",
        "tool_dispatch_recorded": False,
        "root_cause": "UNKNOWN",
        **changes,
    }


def test_pure_proposal_is_bound_bounded_and_does_not_invent_patch() -> None:
    source = fact()
    proposal = evolution.propose_runtime_improvement(source)
    assert proposal is not None
    assert proposal == evolution.propose_runtime_improvement(source)
    assert proposal["proposal_id"] == f"RI-006:{source['source_run_id']}:http-status-v1"
    assert proposal["evidence"] == source and proposal["evidence"] is not source
    assert proposal["classification"] == "DEFER"
    assert proposal["root_cause"] == "UNKNOWN — NEEDS INVESTIGATION"
    assert proposal["patch"] is None and proposal["files_expected_to_change"] == []
    assert proposal["authorizes_execution"] is False and proposal["approval_required"] is True
    assert proposal["source_task"] == "RI-006"
    assert len(json.dumps(proposal, ensure_ascii=False).encode()) < 8192
    for field in ("tests_required", "regression_tests", "acceptance_criteria"):
        assert isinstance(proposal[field], list) and proposal[field]


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "cancelled"},
        {"state": "completed"},
        {"error_class": "UNKNOWN"},
        {"error_class": "HTTPStatusError: SECRET"},
        {"error_class": "HTTPStatusError\0SECRET"},
        {"error_class": "ReadTimeout"},
        {"root_cause": "the model guessed an API key problem"},
        {"tool_dispatch_recorded": 1},
        {"source_run_id": "not-a-uuid"},
        {"source_run_id": str(uuid4()).upper()},
        {"goal": "SECRET-GOAL"},
    ],
)
def test_unknown_or_malformed_facts_produce_no_proposal(changes: dict[str, object]) -> None:
    assert evolution.propose_runtime_improvement(fact(**changes)) is None
    assert evolution.propose_runtime_improvement(None) is None


@pytest_asyncio.fixture
async def controller(tmp_path: Path) -> AsyncIterator[IntegratedCompanion]:
    model = CaptureModel()
    result = IntegratedCompanion(
        tmp_path,
        model,
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.CLOUD_ALLOWED,
        runtime_profile="candidate",
    )
    await result.startup()
    yield result
    assert not model.requests


@pytest.mark.asyncio
async def test_db_to_authenticated_http_is_readonly_and_revocable(
    controller: IntegratedCompanion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert controller._agent_runs is not None and controller._store is not None
    run_id = await failed_run(controller._agent_runs, session="browser", dispatched=True)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("proposal must not execute checks or access raw recovery data")

    monkeypatch.setattr(evolution.PatchVerifier, "verify", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(controller._agent_runs, "readback", forbidden)
    app = create_app(
        allowed_origins={"http://testserver"},
        runtime_profile="candidate",
        on_improvement_proposal=controller.improvement_proposal,
    )
    before = await controller._store.run_transaction(lambda c: tuple(c.iterdump()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://testserver"
    ) as client:
        token = (await client.post("/v1/session", headers={"origin": "http://testserver"})).json()[
            "token"
        ]
        headers = {"authorization": f"Bearer {token}"}
        response = await client.get(
            "/v1/conversations/browser/improvement-proposal", headers=headers
        )
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert "SECRET" not in response.text and len(response.content) < 8192
        body = response.json()
        assert body["status"] == "awaiting_investigation"
        assert body["proposal"]["evidence"]["source_run_id"] == run_id
        assert "先回讀" in body["proposal"]["risk"]
        assert await controller._store.run_transaction(lambda c: tuple(c.iterdump())) == before
        wrong_session = await client.get(
            "/v1/conversations/other/improvement-proposal", headers=headers
        )
        assert wrong_session.json() == {"status": "no_supported_evidence", "proposal": None}
        await controller._store.run_transaction(
            lambda c: c.execute(
                "UPDATE agent_runs SET error='ReadTimeout' WHERE run_id=?", (run_id,)
            )
        )
        corrected = await client.get(
            "/v1/conversations/browser/improvement-proposal", headers=headers
        )
        assert corrected.json() == {"status": "no_supported_evidence", "proposal": None}


@pytest.mark.asyncio
async def test_restore_off_after_startup_does_not_read_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = IntegratedCompanion(
        tmp_path,
        CaptureModel(),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
        session_restore_enabled=False,
    )
    await result.startup()
    assert result._agent_runs is not None

    async def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("disabled projection must not read a fact")

    monkeypatch.setattr(result._agent_runs, "recent_runtime_status", forbidden)
    assert await result.improvement_proposal("browser") == {
        "status": "unavailable",
        "proposal": None,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["newer", "stale", "future", "deleted", "wrong_route"])
async def test_ineligible_canonical_source_cannot_reuse_old_proposal(
    controller: IntegratedCompanion,
    mutation: str,
) -> None:
    assert controller._agent_runs is not None and controller._store is not None
    repo, store = controller._agent_runs, controller._store
    run_id = await failed_run(repo)
    assert (await controller.improvement_proposal("A"))["proposal"] is not None
    if mutation == "newer":
        await failed_run(repo, error="ReadTimeout", state=AgentRunState.FAILED)
    elif mutation in {"stale", "future"}:
        stamp = datetime.now(UTC) + timedelta(seconds=-901 if mutation == "stale" else 20)
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE agent_runs SET updated_at=? WHERE run_id=?",
                (stamp.isoformat(), run_id),
            )
        )
    elif mutation == "deleted":
        await store.run_transaction(
            lambda c: c.execute(
                "DELETE FROM run_journal_calls WHERE run_id=?",
                (run_id,),
            )
        )
        await store.run_transaction(
            lambda c: c.execute(
                "DELETE FROM run_journal WHERE run_id=?",
                (run_id,),
            )
        )
    else:
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE run_journal SET privacy='local_only' WHERE run_id=?",
                (run_id,),
            )
        )
    assert await controller.improvement_proposal("A") == {
        "status": "no_supported_evidence",
        "proposal": None,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile,restore", [("legacy", True), ("candidate", False), ("candidate", True)]
)
async def test_unavailable_controller_does_not_initialize_or_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    restore: bool,
) -> None:
    result = IntegratedCompanion(
        tmp_path,
        CaptureModel(),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile=profile,
        session_restore_enabled=restore,
    )

    async def forbidden() -> None:
        raise AssertionError("a read-only proposal must not initialize or reconcile storage")

    monkeypatch.setattr(result, "_ensure_core", forbidden)
    assert await result.improvement_proposal("A") == {"status": "unavailable", "proposal": None}
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_auth_and_profile_gate_precede_callback() -> None:
    calls: list[str] = []

    async def source(session: str) -> dict[str, object]:
        calls.append(session)
        return {"status": "no_supported_evidence", "proposal": None}

    for profile in ("candidate", "legacy"):
        app = create_app(
            allowed_origins={"http://testserver"},
            runtime_profile=profile,
            on_improvement_proposal=source,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://testserver"
        ) as client:
            url = "/v1/conversations/browser/improvement-proposal"
            response = await client.get(url)
            assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
            assert not calls
            token = (
                await client.post("/v1/session", headers={"origin": "http://testserver"})
            ).json()["token"]
            headers = {"authorization": f"Bearer {token}"}
            response = await client.get(
                "/v1/conversations/" + "x" * 129 + "/improvement-proposal", headers=headers
            )
            assert response.status_code == 400 and response.headers["cache-control"] == "no-store"
            assert not calls
            response = await client.get(url, headers=headers)
            assert response.status_code == (200 if profile == "candidate" else 503)
            assert response.headers["cache-control"] == "no-store"
            assert calls == (["browser"] if profile == "candidate" else [])
        calls.clear()


@pytest.mark.asyncio
async def test_error_and_wrong_method_response_are_uncached_and_redacted() -> None:
    calls: list[str] = []

    async def failed_source(session: str) -> dict[str, object]:
        calls.append(session)
        raise RuntimeError("SECRET-SOURCE-DIAGNOSTIC")

    app = create_app(
        allowed_origins={"http://testserver"},
        runtime_profile="candidate",
        on_improvement_proposal=failed_source,
    )
    transport = httpx.ASGITransport(app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = (await client.post("/v1/session", headers={"origin": "http://testserver"})).json()[
            "token"
        ]
        url = "/v1/conversations/browser/improvement-proposal"
        headers = {"authorization": f"Bearer {token}"}
        wrong_method = await client.post(url, headers=headers)
        assert wrong_method.status_code == 405 and not calls
        assert wrong_method.headers["cache-control"] == "no-store"
        failed = await client.get(url, headers=headers)
        assert failed.status_code == 503 and calls == ["browser"]
        assert failed.headers["cache-control"] == "no-store" and "SECRET" not in failed.text
