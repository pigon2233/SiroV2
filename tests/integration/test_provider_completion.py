from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.core.conversation import MAX_CONTINUATIONS
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import Privacy
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

_PARTIAL = "synthetic unfinished reply"
_COMPLETE = "synthetic complete reply"
_GOAL = "synthetic provider completion goal"
_FOLLOW_UP = "synthetic follow-up goal"
_PRIOR_ARGUMENTS: dict[str, object] = {"argv": ["synthetic-prior-effect"]}
_OBSERVATION = {"confirmed": "synthetic prior effect"}


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload)


def _sse(*events: dict[str, object] | str) -> bytes:
    return "".join(
        "data: " + (event if isinstance(event, str) else json.dumps(event)) + "\n\n"
        for event in events
    ).encode()


def _delta(value: dict[str, object]) -> dict[str, object]:
    return {"choices": [{"delta": value}]}


def _tool(index: int, call_id: str, arguments: str) -> dict[str, object]:
    return {
        "index": index,
        "id": call_id,
        "function": {"name": "computer.execute", "arguments": arguments},
    }


def _incomplete_response(ending: str) -> bytes:
    events: list[dict[str, object] | str] = [
        _delta({"content": _PARTIAL}),
        _delta(
            {
                "tool_calls": [
                    _tool(0, "new-complete", '{"argv":["must-not-execute"]}'),
                    _tool(1, "new-partial", '{"argv":['),
                ]
            }
        ),
    ]
    if ending == "length":
        events.extend(({"choices": [{"finish_reason": "length"}]}, "[DONE]"))
    return _sse(*events)


@asynccontextmanager
async def _provider(
    responses: list[bytes],
) -> AsyncIterator[tuple[str, list[dict[str, object]]]]:
    """Valid HTTP framing makes bare EOF a semantic SSE failure, not a wire error."""
    requests: list[dict[str, object]] = []
    errors: list[Exception] = []
    handlers: set[asyncio.Task[None]] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        handlers.add(task)
        try:
            async with asyncio.timeout(3):
                headers = await reader.readuntil(b"\r\n\r\n")
                assert headers.startswith(b"POST /v1/chat/completions HTTP/1.1\r\n")
                length = next(
                    int(line.split(b":", 1)[1])
                    for line in headers.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                )
                payload = json.loads(await reader.readexactly(length))
                assert isinstance(payload, dict) and payload["stream"] is True
                requests.append(payload)
                index = len(requests) - 1
                if index >= len(responses):
                    raise AssertionError("unexpected provider retry or restart replay")
                body = responses[index]
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
        except Exception as error:
            errors.append(error)
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", requests
    finally:
        server.close()
        await server.wait_closed()
        for handler in tuple(handlers):
            handler.cancel()
        await asyncio.gather(*tuple(handlers), return_exceptions=True)
    assert not errors, errors


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["legacy", "candidate"])
@pytest.mark.parametrize("continuation", [False, True])
@pytest.mark.parametrize("ending", ["length", "bare_eof"])
async def test_provider_incomplete_generation_never_dispatches_or_replays(
    tmp_path: Path, profile: str, continuation: bool, ending: str
) -> None:
    responses = []
    if continuation:
        responses.append(
            _sse(
                _delta({"tool_calls": [_tool(0, "prior", json.dumps(_PRIOR_ARGUMENTS))]}),
                {"choices": [{"finish_reason": "tool_calls"}]},
                "[DONE]",
            )
        )
    # A reply cut at the output limit is continued up to MAX_CONTINUATIONS times, so the provider
    # keeps cutting it; a bare EOF is not a length cut and gets no continuation request.
    extra = MAX_CONTINUATIONS if ending == "length" else 0
    responses.extend(
        (
            *(_incomplete_response(ending) for _ in range(1 + extra)),
            _sse(
                _delta({"content": _COMPLETE}), {"choices": [{"finish_reason": "stop"}]}, "[DONE]"
            ),
        )
    )
    expected_error = "ProviderOutputTruncated" if ending == "length" else "ProviderOutputIncomplete"
    effects: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        effects.append(arguments)
        return _OBSERVATION

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repository = SQLiteAgentRunRepository(store)
    hub = RecordingHub()
    async with _provider(responses) as (base_url, requests):
        # Permit a second attempt so a hidden automatic retry cannot pass by policy denial.
        model = FailoverModel(
            (
                OpenAICompatibleAdapter(
                    base_url=base_url,
                    api_key="synthetic",  # pragma: allowlist secret
                    model="synthetic",
                ),
            ),
            backoff_seconds=0,
            cloud_request_budget=1,
        )
        controller = IntegratedCompanion(
            tmp_path,
            model,
            hub,
            MinimalWebBodyAdapter(WebSocketBodyTransport()),
            privacy=Privacy.CLOUD_ALLOWED,
            tool_orchestrator=ToolOrchestrator(
                SQLiteToolProposalRepository(store), {"computer.execute": execute}
            ),
            runtime_profile=profile,
            auto_authorize=lambda: True,
        )
        await asyncio.wait_for(controller.respond("session", _GOAL), 10)
        assert len(requests) == 1 + int(continuation) + extra
        assert effects == ([_PRIOR_ARGUMENTS] if continuation else [])
        proposals = [event for event in hub.events if event["type"] == "tool_proposal"]
        assert [event["call_id"] for event in proposals] == (["prior"] if continuation else [])
        terminals = [event for event in hub.events if event["type"] == "assistant_terminal"]
        assert len(terminals) == 1
        assert terminals[0]["state"] == "failed"
        assert terminals[0]["error"] == expected_error
        assert [event["text"] for event in hub.events if event["type"] == "assistant_delta"] == (
            [_PARTIAL] * (1 + extra)
        )
        assert hub.events[-1] is terminals[0]
        readback = await controller.recovery_readback("session")
        assert readback is not None and readback["state"] == "failed"
        assert readback["error"] == expected_error
        proposal_rows = await store.run_transaction(
            lambda c: c.execute(
                "SELECT proposal_id,call_id,state,arguments_json,observation_json "
                "FROM tool_proposals"
            ).fetchall()
        )
        assert len(proposal_rows) == int(continuation)
        if continuation:
            proposal = proposal_rows[0]
            assert proposal["proposal_id"] == proposals[0]["proposal_id"]
            # Candidate stores a run-scoped private identity; the journal owns native IDs.
            assert proposal["call_id"] == (
                proposal["proposal_id"] if profile == "candidate" else "prior"
            )
            assert proposal["state"] == "completed"
            assert json.loads(proposal["arguments_json"]) == _PRIOR_ARGUMENTS
            assert json.loads(proposal["observation_json"]) == _OBSERVATION
        steps = await repository.steps(str(readback["run_id"]))
        assert [step.payload for step in steps if step.kind == "observation"] == (
            [_OBSERVATION] if continuation else []
        )
        finals = [step.payload for step in steps if step.kind == "final"]
        assert len(finals) == 1
        assert cast(dict[str, object], finals[0])["text"] == _PARTIAL * (1 + extra)
        turns = await store.run_transaction(
            lambda c: c.execute("SELECT state FROM turns ORDER BY rowid").fetchall()
        )
        assert [row[0] for row in turns] == (
            ["completed", "failed"] if continuation else ["failed"]
        )
        if profile == "candidate":
            assert readback["recovery_status"] == "terminal"
            assert readback["tool_calls"] == int(continuation)
            messages = cast(list[dict[str, object]], readback["messages"])
            assert messages[-1]["content"] == _PARTIAL * (1 + extra)
            assert messages[-1]["tool_calls"] == []
            calls = cast(list[dict[str, object]], readback["calls"])
            assert [call["call_id"] for call in calls] == (["prior"] if continuation else [])
            observations = [message for message in messages if message["role"] == "tool"]
            assert len(observations) == int(continuation)
            if continuation:
                assert calls[0]["run_id"] == readback["run_id"]
                assert calls[0]["proposal_id"] == proposals[0]["proposal_id"]
                assert observations[0]["tool_call_id"] == "prior"
                assert json.loads(str(observations[0]["content"])) == _OBSERVATION
                # The request right after the tool ran, before any length continuation.
                provider_messages = cast(list[dict[str, object]], requests[1]["messages"])
                assert provider_messages[-1]["role"] == "tool"
                assert json.loads(str(provider_messages[-1]["content"])) == _OBSERVATION

        # Reopen the actual persistent runtime with the same live HTTP provider and executor.
        restarted_hub = RecordingHub()
        restarted = IntegratedCompanion(
            tmp_path,
            model,
            restarted_hub,
            MinimalWebBodyAdapter(WebSocketBodyTransport()),
            privacy=Privacy.CLOUD_ALLOWED,
            tool_orchestrator=ToolOrchestrator(
                SQLiteToolProposalRepository(store), {"computer.execute": execute}
            ),
            runtime_profile=profile,
            auto_authorize=lambda: True,
        )
        await restarted.startup()
        assert await restarted.recovery_readback("session") == readback
        assert len(requests) == 1 + int(continuation) + extra
        assert effects == ([_PRIOR_ARGUMENTS] if continuation else [])
        assert restarted_hub.events == []
        assert await repository.recent_session_messages("session", privacy="cloud_allowed") == ()

        # A real stop after restart proves failure does not poison later turns or hydration.
        await asyncio.wait_for(restarted.respond("session", _FOLLOW_UP), 10)
        assert len(requests) == 2 + int(continuation) + extra
        assert effects == ([_PRIOR_ARGUMENTS] if continuation else [])
        next_terminals = [
            event for event in restarted_hub.events if event["type"] == "assistant_terminal"
        ]
        assert len(next_terminals) == 1
        assert next_terminals[0]["state"] == "completed"
        assert next_terminals[0]["error"] is None
        hydrated = await repository.recent_session_messages("session", privacy="cloud_allowed")
        if profile == "candidate":
            provider_messages = cast(list[dict[str, object]], requests[-1]["messages"])
            assert [(message["role"], message["content"]) for message in provider_messages[1:]] == [
                ("user", _FOLLOW_UP)
            ]
            assert [(message.role, message.content) for message in hydrated] == [
                ("user", _FOLLOW_UP),
                ("assistant", _COMPLETE),
            ]
        else:
            assert hydrated == ()
