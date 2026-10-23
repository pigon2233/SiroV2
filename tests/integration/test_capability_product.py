from __future__ import annotations

import json
import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub, main
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import (
    DEFAULT_MODEL_TOOLS,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolDescriptor,
    ToolMetadata,
    ToolOrchestrator,
)


def test_main_reports_current_safe_reasons_without_running_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_BINARY", str(tmp_path / "private-path-canary"))
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "private-key-canary")
    monkeypatch.setattr("shutil.which", lambda name: None)
    effects: list[object] = []

    async def forbid(*args: object, **kwargs: object) -> None:
        effects.append(args)
        raise AssertionError("inventory attempted a subprocess")

    monkeypatch.setattr("asyncio.create_subprocess_exec", forbid)

    def run(app: FastAPI, **kwargs: object) -> None:
        with TestClient(app) as client:
            assert client.get("/v1/runtime").status_code == 401
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            for _ in range(2):
                response = client.get("/v1/runtime", headers=headers)
                rows = {item["name"]: item for item in response.json()["tools"]}
                assert rows["browser.read"]["reason_code"] == "browser_executable_missing"
                assert rows["filesystem.read"]["reason_code"] == "workspace_unavailable"
                assert rows["computer.execute"]["availability"] == "available"
                assert rows["computer.execute"]["required_permissions"] == ["tool_approval"]
                assert rows["computer.execute"]["output_contract"] is None
                assert rows["process.start"]["model_visible"] is False
                assert "private-path-canary" not in response.text
                assert "private-key-canary" not in response.text
            client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": False})
            rows = client.get("/v1/runtime", headers=headers).json()["tools"]
            assert all(not item["available"] for item in rows)
            assert {item["reason_code"] for item in rows} == {"tools_disabled"}
            client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": True})
            rows = {
                item["name"]: item
                for item in client.get("/v1/runtime", headers=headers).json()["tools"]
            }
            assert rows["computer.execute"]["available"]
            assert rows["browser.read"]["reason_code"] == "browser_executable_missing"

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    assert effects == []


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["candidate", "legacy"])
async def test_model_round_inventory_is_current_and_preserves_native_pairs(
    tmp_path: Path, profile: str
) -> None:
    requests: list[ModelRequest] = []
    enabled = True
    calls = 0

    class Model:
        name = "capability-fixture"

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            if len(requests) == 1:
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall("cap-1", "computer.execute", {"argv": ["synthetic"]}),
                )
            else:
                yield ModelChunk("text", "synthetic completed answer")
            yield ModelChunk("finished")

    async def execute(arguments: dict[str, object]) -> object:
        nonlocal enabled, calls
        enabled = False
        calls += 1
        return {"result": "synthetic-success"}

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
                metadata=ToolMetadata(display_name="電腦任務"),
            ),
        )
    )
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        {"computer.execute": execute},
        catalog=catalog if profile == "candidate" else None,
    )
    hub = GatewayHub()
    controller = IntegratedCompanion(
        tmp_path,
        Model(),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile=profile,
        auto_authorize=lambda: True,
    )
    await controller.respond("synthetic", "synthetic original goal")
    assert calls == 1 and len(requests) == 2
    marker = "[SIRO_TOOL_CAPABILITIES_V1]"
    if profile == "candidate":
        states = []
        for request in requests:
            systems = [message for message in request.messages if message.role == "system"]
            assert len(systems) == 1 and systems[0].content.count(marker) == 1
            payload = (
                systems[0]
                .content.split(marker + "\n")[1]
                .split("\n[/SIRO_TOOL_CAPABILITIES_V1]")[0]
            )
            view = json.loads(payload)
            assert view["authorizes_execution"] is False
            row = view["capabilities"][0]
            assert bool(request.tools) == row["available"]
            states.append(row["availability"])
        assert states == ["available", "unavailable"]
        assert requests[1].tools == ()
        messages = requests[1].messages
        assert [message.role for message in messages] == ["system", "user", "assistant", "tool"]
        assert messages[1].content == "synthetic original goal"
        assert messages[2].tool_calls[0].call_id == messages[3].tool_call_id == "cap-1"
        assert "synthetic-success" in messages[3].content
        # A new request gets a fresh sample; no previous block or state leaks between runs.
        enabled = True
        await controller.respond("synthetic", "synthetic next goal")
        assert len(requests) == 3
        system = requests[2].messages[0].content
        assert system.count(marker) == 1
        assert json.loads(
            system.split(marker + "\n")[1].split("\n[/SIRO_TOOL_CAPABILITIES_V1]")[0]
        )["capabilities"][0]["available"]
    else:
        assert all(marker not in request.prompt for request in requests)
        assert requests[1].tools == DEFAULT_MODEL_TOOLS
    await hub.shutdown()


def test_frontend_inventory_is_read_only_refreshable_and_uses_text_content() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    script = html[
        html.index("      function renderCapabilities(") : html.index("      async function refreshProduct(")
    ]
    assert "renderCapabilities(runtime.tools)" in html
    code = r"""
const assert = require('node:assert/strict');
class Element {
  constructor() { this.children = []; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(c=>c.textContent).join(''); }
  set innerHTML(value) { throw new Error('metadata entered HTML'); }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.children.push(node); }
}
const root = new Element(), button = new Element();
const document = {querySelector: s=>s==='#capability-items'?root:button,
  createElement:()=>new Element()};
let response = {tools:[]}, failure = false; const calls = [];
const productRequest = async url=>{
  calls.push(url); if(failure) throw Error('private-canary'); return response;
};
"""
    checks = r"""
(async()=>{
  renderCapabilities([{name:'computer.execute',display_name:'<img src=x onerror=evil()>',
    availability:'available',risk_level:'computer',model_visible:true}]);
  assert(root.textContent.includes('<img src=x onerror=evil()>'));
  assert(root.textContent.includes('仍需檢查授權'));
  response = {tools:[{name:'browser.read',reason_code:'browser_executable_missing',
    availability:'unavailable'}]};
  await button.onclick(); assert(root.textContent.includes('尚未找到可用的瀏覽器'));
  response = {tools:[{name:'computer.execute',reason_code:'tools_disabled',
    availability:'unavailable'}]};
  await button.onclick(); assert(root.textContent.includes('你已暫停電腦操作'));
  assert(!root.textContent.includes('目前可用'));
  renderCapabilities([{name:'legacy',available:true}]);
  assert(root.textContent.includes('尚未提供即時狀態'));
  failure=true; await button.onclick(); assert(root.textContent.includes('目前無法更新'));
  assert(!root.textContent.includes('private-canary'));
  assert(calls.every(url=>url==='/v1/runtime'));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(
        ["node", "-e", code + script + checks], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
