from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from siro.services.tools.execution import restricted_environment

CANARIES = {
    "SIRO_OPENAI_API_KEY": "canary-openai",  # pragma: allowlist secret
    "GROQ_API_KEY": "canary-groq",  # pragma: allowlist secret
    "SIRO_ESP32_RELAY_TOKEN": "canary-relay-" + "x" * 32,
    "MY_SECRET_TOKEN": "canary-generic",
}


def test_restricted_environment_keeps_only_the_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in CANARIES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("PATH", "/synthetic/bin")
    monkeypatch.setenv("CODEX_HOME", "/synthetic/codex")
    plain = restricted_environment()
    assert plain["PATH"] == "/synthetic/bin"
    assert not set(CANARIES) & set(plain) and "CODEX_HOME" not in plain
    assert restricted_environment(("CODEX_HOME",))["CODEX_HOME"] == "/synthetic/codex"


@pytest.mark.asyncio
async def test_codex_child_gets_no_secrets_but_keeps_codex_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from siro.services.tools.codex import ask_codex

    for name, value in CANARIES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("CODEX_HOME", "/synthetic/codex")
    monkeypatch.setenv("SIRO_CODEX_BIN", "/synthetic/codex-bin")
    seen: dict[str, object] = {}

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        seen.update(options)
        Path(argv[argv.index("-o") + 1]).write_text("answer", encoding="utf-8")
        return {"returncode": 0}

    await ask_codex({"task": "synthetic task"}, binary=Path("/opt/codex"), run=run)
    environment = seen["environment"]
    assert isinstance(environment, dict)
    assert not set(CANARIES) & set(environment)
    assert environment["CODEX_HOME"] == "/synthetic/codex"
    assert environment["SIRO_CODEX_BIN"] == "/synthetic/codex-bin"
    assert environment["PATH"] == os.environ["PATH"]


@pytest.mark.parametrize("profile", ["legacy", "candidate"])
def test_gateway_computer_execute_child_gets_no_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    from collections.abc import AsyncIterator

    import uvicorn
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from siro.adapters.models import ollama
    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, ToolCall
    from siro.services.presentation.gateway import main

    class Model:
        name = "synthetic-main-provider"

        def __init__(self) -> None:
            self.requests: list[ModelRequest] = []

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            self.requests.append(request)
            if len(self.requests) == 1:
                script = "import json, os; print(json.dumps(sorted(os.environ)))"
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        "env-call",
                        "computer.execute",
                        {"argv": [sys.executable, "-c", script], "cwd": str(tmp_path)},
                    ),
                )
            else:
                yield ModelChunk("text", "done")
            yield ModelChunk("finished")

    model = Model()
    for name in tuple(os.environ):
        if name.startswith("SIRO_") or name == "GROQ_API_KEY":
            monkeypatch.delenv(name)
    for name, value in CANARIES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setattr(ollama, "OllamaAdapter", lambda **kwargs: model)

    def run(app: FastAPI, **kwargs: object) -> None:
        with TestClient(app) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            response = client.post(
                "/v1/conversations/main/turns",
                headers={"Authorization": f"Bearer {token}"},
                json={"text": "print the child environment"},
            )
            assert response.status_code == 200

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    assert len(model.requests) == 2
    observed = (
        model.requests[1].messages[-1].content
        if profile == "candidate"
        else (model.requests[1].prompt)
    )
    assert "PATH" in observed
    for name in CANARIES:
        assert name not in observed
