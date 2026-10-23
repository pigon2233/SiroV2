from __future__ import annotations

from pathlib import Path

import pytest

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ToolCall
from siro.services.tools.orchestrator import (
    DEFAULT_MODEL_TOOLS,
    ProposalState,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolDescriptor,
    ToolOrchestrator,
    ToolUnavailableError,
)


@pytest.mark.asyncio
async def test_catalog_is_dispatch_source_and_checks_revoked_readiness(tmp_path: Path) -> None:
    enabled = True
    calls: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        calls.append(arguments)
        return {"ok": True}

    async def wrong(arguments: dict[str, object]) -> object:
        raise AssertionError("candidate bypassed descriptor")

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "computer.execute",
                DEFAULT_MODEL_TOOLS[1],
                execute,
                lambda: enabled,
                "python.argv",
                "computer",
            ),
        )
    )
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    subject = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": wrong}, catalog=catalog
    )
    assert [t.name for t in subject.model_tools()] == ["computer.execute"]
    for index in range(2):
        proposal = await subject.propose(
            "s", ToolCall(str(index), "computer.execute", {"argv": ["synthetic"]}), risk="computer"
        )
        await subject.resolve(proposal.proposal_id, approved=True, arguments=proposal.arguments)
        if index == 1:
            enabled = False
        result = await subject.execute(proposal.proposal_id)
        assert result.state == (ProposalState.COMPLETED if index == 0 else ProposalState.FAILED)
        if index == 1:
            assert result.error == "ToolUnavailableError"
    assert len(calls) == 1
    assert subject.model_tools() == ()
    with pytest.raises(ToolUnavailableError):
        await subject.propose(
            "s", ToolCall("3", "computer.execute", {"argv": ["synthetic"]}), risk="computer"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"argv": []},
        {"argv": [2]},
        {"argv": "x"},
        {"argv": ["x"], "detach": "yes"},
        {"argv": ["x"], "timeout_seconds": True},
        {"argv": ["x"], "timeout_seconds": 121},
        {"argv": ["x"], "extra": "x"},
    ],
)
async def test_catalog_rejects_wrong_schema_before_proposal(
    tmp_path: Path, arguments: dict[str, object]
) -> None:
    async def execute(args: dict[str, object]) -> object:
        raise AssertionError("invalid arguments dispatched")

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "computer.execute",
                DEFAULT_MODEL_TOOLS[1],
                execute,
                lambda: True,
                "python.argv",
                "computer",
            ),
        )
    )
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    subject = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    with pytest.raises(ValueError, match="invalid tool arguments"):
        await subject.propose("s", ToolCall("bad", "computer.execute", arguments), risk="computer")


def test_definition_snapshot_cannot_change_canonical_schema() -> None:
    async def execute(arguments: dict[str, object]) -> object:
        return arguments

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "computer.execute",
                DEFAULT_MODEL_TOOLS[1],
                execute,
                lambda: True,
                "python.argv",
                "computer",
            ),
        )
    )
    catalog.definitions()[0].input_schema["required"] = []
    with pytest.raises(ValueError):
        catalog.require("computer.execute", {})


@pytest.mark.parametrize("profile", ["legacy", "candidate"])
def test_real_main_effective_config_and_live_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    import os

    import uvicorn
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from siro.services.presentation.gateway import main

    for key in list(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic providers have no native tokenizer; preserve this fixture scope.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "local-test-model")
    monkeypatch.setenv("SIRO_OPENAI_MODEL", "unused-cloud-model")
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "test-private-canary")
    # Current browser backend uses the same executable discovery.
    monkeypatch.setattr("shutil.which", lambda name: None)

    def run(app: FastAPI, **kwargs: object) -> None:
        monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "changed-after-startup")
        with TestClient(app) as client:
            assert client.get("/v1/runtime").status_code == 401
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            response = client.get("/v1/runtime", headers=headers)
            assert response.status_code == 200
            snapshot = response.json()
            assert snapshot["runtime_profile"] == profile
            assert snapshot["routes"]["model"] == "ollama:local-test-model"
            assert snapshot["authorization_mode"] == "full"
            assert snapshot["json_settings_applied"] is False
            assert "test-private-canary" not in response.text
            assert "API_KEY" not in response.text
            assert "unused-cloud-model" not in response.text
            tools = {item["name"]: item for item in snapshot["tools"]}
            expected = {"computer.execute", "browser.navigate+read", "process.start"}
            if profile == "candidate":
                expected |= {
                    "browser.read",
                    "browser.fill",
                    "browser.click",
                    "browser.close",
                    "filesystem.read",
                    "filesystem.list",
                    "codex.ask",
                }
            assert set(tools) == expected
            assert tools["process.start"]["model_visible"] is False
            if profile == "candidate":
                assert tools["browser.navigate+read"]["available"] is False
                assert tools["computer.execute"]["available"] is True
            client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": False})
            disabled = client.get("/v1/runtime", headers=headers).json()
            assert disabled["kill_switches"]["tools"] is False
            if profile == "candidate":
                assert not any(item["available"] for item in disabled["tools"])

    monkeypatch.setattr(uvicorn, "run", run)
    main()


@pytest.mark.asyncio
async def test_real_controller_uses_catalog_each_model_round(tmp_path: Path) -> None:
    from collections.abc import AsyncIterator

    from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy
    from siro.services.presentation.gateway import GatewayHub
    from siro.services.presentation.integrated import IntegratedCompanion

    requests: list[ModelRequest] = []
    enabled = True
    calls = 0

    class Model:
        name = "synthetic-catalog"

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            if len(requests) == 1:
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall("a", "computer.execute", {"argv": ["synthetic"]}),
                )
            else:
                yield ModelChunk("text", "done")
            yield ModelChunk("finished")

    async def execute(arguments: dict[str, object]) -> object:
        nonlocal enabled, calls
        calls += 1
        enabled = False
        return {"ok": True}

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "computer.execute",
                DEFAULT_MODEL_TOOLS[1],
                execute,
                lambda: enabled,
                "python.argv",
                "computer",
            ),
        )
    )
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    hub = GatewayHub()
    controller = IntegratedCompanion(
        tmp_path,
        Model(),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    await controller.respond("s", "synthetic goal")
    assert calls == 1
    assert [t.name for t in requests[0].tools] == ["computer.execute"]
    assert requests[1].tools == ()
    await hub.shutdown()


@pytest.mark.parametrize("capability", ["computer.execute", "browser.navigate+read"])
def test_main_model_catalog_routes_every_visible_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capability: str
) -> None:
    import os
    import sys
    import time
    from collections.abc import AsyncIterator

    import uvicorn
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from siro.adapters.browser import BrowserObservation
    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest
    from siro.services.presentation.gateway import main

    requests: list[ModelRequest] = []
    observations: list[str] = []

    class Model:
        name = "main-catalog-fixture"

        def __init__(self, **kwargs: object) -> None:
            pass

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            if len(requests) == 1:
                args: dict[str, object] = (
                    {"argv": [sys.executable, "-c", "print('catalog-route-ok')"]}
                    if capability == "computer.execute"
                    else {"url": "https://synthetic.example/"}
                )
                yield ModelChunk("tool_request", tool_call=ToolCall("route", capability, args))
            else:
                yield ModelChunk("text", "done")
            yield ModelChunk("finished")

    class Browser:
        def __init__(self, origins: tuple[str, ...]) -> None:
            pass

        async def __aenter__(self) -> Browser:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def navigate(self, url: str) -> BrowserObservation:
            observations.append(url)
            return BrowserObservation(url, "synthetic", "synthetic visible text", "v1")

    for key in list(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic providers have no native tokenizer; preserve this fixture scope.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic")
    monkeypatch.setattr("siro.adapters.models.ollama.OllamaAdapter", Model)
    monkeypatch.setattr("siro.adapters.browser.ScopedBrowserDriver", Browser)
    monkeypatch.setattr("shutil.which", lambda name: "/synthetic/browser")

    def run(app: FastAPI, **kwargs: object) -> None:
        with TestClient(app) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            status = client.get("/v1/runtime", headers=headers).json()
            assert status["catalog_enabled"] is True
            assert status["configuration_source"] == "gateway_env_and_defaults"
            client.post(
                "/v1/conversations/catalog/turns", headers=headers, json={"text": "synthetic goal"}
            )
            deadline = time.monotonic() + 10
            while len(requests) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            assert len(requests) == 2
            assert {tool.name for tool in requests[0].tools} == {
                "computer.execute",
                "browser.navigate+read",
                "browser.read",
                "browser.fill",
                "browser.click",
                "browser.close",
                "filesystem.read",
                "filesystem.list",
                "codex.ask",
            }
            tool_message = next(m for m in requests[1].messages if m.role == "tool")
            assert tool_message.tool_call_id == "route"
            assert (
                "catalog-route-ok" if capability == "computer.execute" else "synthetic visible text"
            ) in tool_message.content

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    assert len(observations) == (1 if capability == "browser.navigate+read" else 0)


@pytest.mark.asyncio
async def test_contextual_dispatch_rechecks_after_scheduling(tmp_path: Path) -> None:
    from siro.services.tools.execution import ExecutionContext

    checks = 0
    dispatched = False

    def readiness() -> bool:
        nonlocal checks
        checks += 1
        return checks < 3  # propose, outer execute, then scheduled invocation

    async def execute(arguments: dict[str, object]) -> object:
        raise AssertionError("legacy handler bypass")

    async def contextual(arguments: dict[str, object], context: ExecutionContext) -> object:
        nonlocal dispatched
        dispatched = True
        return {}

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "computer.execute",
                DEFAULT_MODEL_TOOLS[1],
                execute,
                readiness,
                "python.argv",
                "computer",
                contextual,
            ),
        )
    )
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    subject = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    subject.start_run("r", "s")
    proposal = await subject.propose(
        "s", ToolCall("a", "computer.execute", {"argv": ["x"]}), risk="computer"
    )
    subject.bind_proposal("r", proposal)
    await subject.resolve(proposal.proposal_id, approved=True, arguments=proposal.arguments)
    result = await subject.execute(proposal.proposal_id)
    assert result.state is ProposalState.FAILED
    assert result.error == "ToolUnavailableError"
    assert not dispatched
