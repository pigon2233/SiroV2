from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelMessage, ModelRequest, ToolCall
from siro.services.agent.runs import AgentRunState, SQLiteAgentRunRepository


@pytest.mark.parametrize(
    "profile,enabled", [("candidate", True), ("candidate", False), ("legacy", True)]
)
def test_main_three_restarts_restore_only_canonical_session_dialogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, enabled: bool
) -> None:
    import siro.adapters.models.ollama as ollama
    from siro.services.presentation.gateway import main

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic providers have no native tokenizer; preserve this fixture scope.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic-session")
    requests: list[ModelRequest] = []
    boot = 0

    class Model:
        name = "synthetic-session"

        def __init__(
            self, *, model: str, thinking: bool | None = None, context_length: int | None = None
        ) -> None:
            pass

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            yield ModelChunk("text", f"answer-{boot}")
            yield ModelChunk("finished")

    monkeypatch.setattr(ollama, "OllamaAdapter", Model)

    def run(app: object, **kwargs: object) -> None:
        # Startup captures the feature; flipping env cannot change this owner.
        monkeypatch.setenv("SIRO_SESSION_RESTORE_ENABLED", "0" if enabled else "1")
        with TestClient(cast(FastAPI, app)) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            session = "B" if boot == 2 else "A"
            goal = f" raw-goal-{boot} "
            assert (
                client.post(
                    f"/v1/conversations/{session}/turns", headers=headers, json={"text": goal}
                ).status_code
                == 200
            )
            if profile == "candidate":
                readback = client.get(f"/v1/agent-runs/{session}", headers=headers).json()
                assert readback["backend"] == "synthetic-session"
                assert readback["goal"] == goal.strip()
                assert readback["model_rounds"] == 1
                messages = requests[-1].messages
                expected_prior = []
                if enabled and boot in {1, 3}:
                    for old in [0] if boot == 1 else [0, 1]:
                        expected_prior.extend(
                            [("user", f" raw-goal-{old} "), ("assistant", f"answer-{old}")]
                        )
                assert [(m.role, m.content) for m in messages[1:]] == [
                    *expected_prior,
                    ("user", goal),
                ]
                assert messages[0].role == "system"
                assert "raw-goal-2" not in messages[0].content
                assert sum(m.role == "system" for m in messages) == 1
                assert readback["messages"][-1]["content"] == f"answer-{boot}"
            else:
                assert not requests[-1].messages

    monkeypatch.setattr(uvicorn, "run", run)
    for index in range(4):
        boot = index
        monkeypatch.setenv("SIRO_SESSION_RESTORE_ENABLED", "1" if enabled else "0")
        main()
    assert len(requests) == 4
    with sqlite3.connect(tmp_path / "siro.db") as c:
        assert c.execute("SELECT COUNT(*) FROM agent_runs").fetchone() == (4,)


@pytest.mark.asyncio
async def test_recent_dialogue_bounds_provenance_privacy_and_legacy(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    for index in range(9):
        run = await repo.start("A", f"goal-{index}", runtime_backend="local")
        await repo.checkpoint(
            run.run_id,
            [
                ModelMessage("system", "OLD ASSEMBLED SECRET PROMPT"),
                ModelMessage("user", run.goal),
                ModelMessage("assistant", f"answer-{index}"),
            ],
        )
        await repo.finish_journal(run.run_id)
        await repo.append(run.run_id, "final", {}, state=AgentRunState.COMPLETED)
    restored = await repo.recent_session_messages("A", privacy="local_only")
    assert len(restored) == 12
    assert [m.content for m in restored] == [
        value for i in range(3, 9) for value in (f"goal-{i}", f"answer-{i}")
    ]
    assert await repo.recent_session_messages("B", privacy="local_only") == ()
    assert await repo.recent_session_messages("A", privacy="cloud_allowed") == ()
    with pytest.raises(ValueError, match="complete dialogue pair"):
        await repo.recent_session_messages("A", privacy="local_only", max_messages=1)
    legacy = await repo.start("legacy", "ASSEMBLED PROMPT must not become user")
    await repo.append(legacy.run_id, "final", {}, state=AgentRunState.COMPLETED)
    assert await repo.recent_session_messages("legacy", privacy="local_only") == ()
    readback = await repo.readback("legacy")
    assert readback is not None and readback["recovery_status"] == "legacy_unrestorable"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [AgentRunState.FAILED, AgentRunState.CANCELLED])
async def test_partial_and_interrupted_runs_are_readback_only(
    tmp_path: Path, state: AgentRunState
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run = await repo.start("A", "unknown effect", runtime_backend="local")
    await repo.checkpoint(
        run.run_id, [ModelMessage("user", run.goal), ModelMessage("assistant", "partial")]
    )
    assert await repo.recent_session_messages("A", privacy="local_only") == ()
    await repo.finish_journal(run.run_id, interrupted=True)
    await repo.append(run.run_id, "final", {}, state=state)
    assert await repo.recent_session_messages("A", privacy="local_only") == ()
    readback = await repo.readback("A")
    assert readback is not None and readback["recovery_status"] == "interrupted"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["{}", '[{"role":"user","content":"assembled"}]'])
async def test_invalid_canonical_dialogue_is_not_silently_restored(
    tmp_path: Path, payload: str
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run = await repo.start("A", "raw goal", runtime_backend="local")
    await repo.append(run.run_id, "final", {}, state=AgentRunState.COMPLETED)
    await store.run_transaction(
        lambda c: c.execute(
            "UPDATE run_journal SET messages_json=?,status='terminal' WHERE run_id=?",
            (payload, run.run_id),
        )
    )
    with pytest.raises(ValueError, match="invalid canonical session dialogue"):
        await repo.recent_session_messages("A", privacy="local_only")


def test_completed_tool_run_restores_dialogue_without_replaying_intents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import siro.adapters.models.ollama as ollama
    from siro.services.presentation.gateway import main

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic providers have no native tokenizer; preserve this fixture scope.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic-session")
    requests: list[ModelRequest] = []
    marker = tmp_path / "effect.txt"

    class Model:
        name = "synthetic-tool-session"

        def __init__(
            self, *, model: str, thinking: bool | None = None, context_length: int | None = None
        ) -> None:
            pass

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            if len(requests) == 1:
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        "historical-call",
                        "computer.execute",
                        {
                            "argv": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; "
                                f"Path({str(marker)!r}).write_text('once')",
                            ]
                        },
                    ),
                )
            else:
                yield ModelChunk("text", "verified final")
            yield ModelChunk("finished")

    monkeypatch.setattr(ollama, "OllamaAdapter", Model)
    boot = 0

    def run(app: object, **kwargs: object) -> None:
        with TestClient(cast(FastAPI, app)) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            goal = "first goal" if boot == 0 else "new goal"
            assert (
                client.post(
                    "/v1/conversations/A/turns", headers=headers, json={"text": goal}
                ).status_code
                == 200
            )
            assert client.get("/v1/agent-runs/A", headers=headers).json()["state"] == "completed"

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    assert marker.read_text() == "once"
    marker.unlink()
    boot = 1
    main()
    assert len(requests) == 3 and not marker.exists()
    assert [(m.role, m.content) for m in requests[-1].messages[1:]] == [
        ("user", "first goal"),
        ("assistant", "verified final"),
        ("user", "new goal"),
    ]
    assert not any(m.tool_calls or m.role == "tool" for m in requests[-1].messages)
