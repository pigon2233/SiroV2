from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, ToolCall
from siro.services.agent.runs import SQLiteAgentRunRepository


class RecordingSocket:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.retry, self.terminal, self.barrier = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def send_json(self, data: object) -> None:
        assert isinstance(data, dict)
        self.events.append(data)
        if data.get("type") == "assistant_retry_wait":
            self.retry.set()
        elif data.get("type") == "assistant_terminal":
            self.terminal.set()
        elif data.get("type") == "synthetic_barrier":
            self.barrier.set()

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["completed", "cancelled", "disabled"])
async def test_main_tool_once_rate_limit_notice_recovery_cancel_and_writer_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from siro.adapters.models import openai_compatible
    from siro.services.presentation import gateway

    for name in tuple(os.environ):
        if name.startswith("SIRO_") or name == "GROQ_API_KEY":
            monkeypatch.delenv(name)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_OPENAI_MODEL", "synthetic-rate-limit")
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "synthetic")
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_WORKSPACE_ENABLED", "0")
    monkeypatch.setenv("SIRO_RATE_LIMIT_RECOVERY_ENABLED", "0" if mode == "disabled" else "1")
    monkeypatch.setenv("SIRO_RATE_LIMIT_MAX_WAIT_SECONDS", "60")
    marker = tmp_path / "effects.txt"
    requests: list[ModelRequest] = []

    class Cloud:
        name = "synthetic-selected-provider"

        def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
            pass

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            if len(requests) == 1:
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        "completed-effect",
                        "computer.execute",
                        {
                            "argv": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; "
                                f"p=Path({str(marker)!r}); "
                                "p.open('a').write('effect\\n'); print('confirmed')",
                            ]
                        },
                    ),
                )
            elif len(requests) == 2:
                raw = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
                response = httpx.Response(
                    429,
                    request=raw,
                    headers={"retry-after": "60" if mode == "cancelled" else "0.01"},
                )
                raise httpx.HTTPStatusError("synthetic limited", request=raw, response=response)
            else:
                yield ModelChunk("text", "confirmed once without repeating the tool")
            yield ModelChunk("finished")

    monkeypatch.setattr(openai_compatible, "OpenAICompatibleAdapter", Cloud)
    apps: list[FastAPI] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: apps.append(app))
    await asyncio.to_thread(gateway.main)
    app = apps[0]
    owner = "rate-limit-owner"
    socket = RecordingSocket()
    expected = "failed" if mode == "disabled" else mode
    async with app.router.lifespan_context(app):
        hub = app.state.gateway_hub
        channel = await hub.connect(socket, {"type": "snapshot"})
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
            ) as client:
                token = (
                    await client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"})
                ).json()["token"]
                headers = {"authorization": f"Bearer {token}"}
                turn = asyncio.create_task(
                    client.post(
                        f"/v1/conversations/{owner}/turns",
                        headers=headers,
                        json={"text": "synthetic goal with exactly one tool effect"},
                    )
                )
                try:
                    if mode == "cancelled":
                        await asyncio.wait_for(socket.retry.wait(), 5)
                        snapshot = (await client.get("/v1/snapshot", headers=headers)).json()
                        turn_id = snapshot["active_turns"][owner]["turn_id"]
                        response = await client.post(
                            f"/v1/turns/{turn_id}/cancel",
                            headers=headers,
                            json={"reason": "stop during rate limit wait"},
                        )
                        assert response.status_code == 200
                    assert (await asyncio.wait_for(turn, 5)).status_code == 200
                    await asyncio.wait_for(socket.terminal.wait(), 1)
                    readback = (await client.get(f"/v1/agent-runs/{owner}", headers=headers)).json()
                    assert readback["state"] == expected
                    assert readback["tool_calls"] == 1 and readback["model_rounds"] == 2
                    assert readback["backend"] == "synthetic-selected-provider"
                    tools = [
                        message for message in readback["messages"] if message["role"] == "tool"
                    ]
                    assert len(tools) == 1 and tools[0]["tool_call_id"] == "completed-effect"
                    notices = [e for e in socket.events if e["type"] == "assistant_retry_wait"]
                    assert len(notices) == (0 if mode == "disabled" else 1)
                    if notices:
                        assert set(notices[0]) == {
                            "type",
                            "session_id",
                            "stream_id",
                            "retry_after_seconds",
                        }
                        assert notices[0]["session_id"] == owner
                        assert notices[0]["retry_after_seconds"] == (
                            60 if mode == "cancelled" else 0.01
                        )
                    terminal = [e for e in socket.events if e["type"] == "assistant_terminal"]
                    assert len(terminal) == 1 and terminal[0]["state"] == expected
                    # Use the actual Gateway writer to prove a queued/late notice cannot revive it.
                    await hub.broadcast(
                        {
                            "type": "assistant_retry_wait",
                            "session_id": owner,
                            "stream_id": terminal[0]["stream_id"],
                            "retry_after_seconds": 1,
                        },
                        urgent=True,
                    )
                    await hub.broadcast({"type": "synthetic_barrier"}, urgent=True)
                    await asyncio.wait_for(socket.barrier.wait(), 1)
                    assert len(
                        [e for e in socket.events if e["type"] == "assistant_retry_wait"]
                    ) == len(notices)
                finally:
                    if not turn.done():
                        await client.post(
                            "/v1/turns/active/cancel", headers=headers, json={"reason": "cleanup"}
                        )
                    await asyncio.gather(turn, return_exceptions=True)
        finally:
            await hub.disconnect(channel)
    assert marker.read_text().splitlines() == ["effect"]
    assert len(requests) == (3 if mode == "completed" else 2)
    if mode == "completed":
        assert requests[1].messages == requests[2].messages
        assert requests[1].generation_id != requests[2].generation_id
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    persisted = await SQLiteAgentRunRepository(store).readback(owner)
    assert persisted is not None and persisted["state"] == expected
    assert persisted["backend"] == "synthetic-selected-provider"
