from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.openai_compatible import _TOOL_INTENT_EMITTED, OpenAICompatibleAdapter
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
)


def limited(
    retry_after: str | None = None,
    *,
    host: str = "api.groq.com",
    daily_remaining: str | None = None,
) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", f"https://{host}/openai/v1/chat/completions")
    headers = {}
    if retry_after is not None:
        headers["retry-after"] = retry_after
    if daily_remaining is not None:
        headers["x-ratelimit-remaining-requests"] = daily_remaining
    response = httpx.Response(429, request=request, headers=headers)
    return httpx.HTTPStatusError("synthetic limited", request=request, response=response)


class LimitedModel:
    name = "selected-provider"

    def __init__(
        self,
        error: Exception,
        *,
        always_fail: bool = False,
        before: tuple[ModelChunk, ...] = (),
    ) -> None:
        self.error = error
        self.always_fail = always_fail
        self.before = before
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if len(self.requests) == 1 or self.always_fail:
            for chunk in self.before:
                yield chunk
            raise self.error
        yield ModelChunk("text", "confirmed")
        yield ModelChunk("finished")


async def collect(
    model: FailoverModel, request: ModelRequest, token: CancellationToken | None = None
) -> list[ModelChunk]:
    return [chunk async for chunk in model.stream(request, token or CancellationToken())]


@pytest.mark.asyncio
async def test_enabled_rate_limit_wait_retries_same_provider_and_preserves_completed_pair() -> None:
    primary = LimitedModel(limited("0.015"))
    alternate = LimitedModel(ValueError("must not dispatch"))
    notices: list[tuple[ModelRequest, float]] = []

    async def notice(request: ModelRequest, delay: float) -> None:
        notices.append((request, delay))

    request = ModelRequest(
        "unchanged goal",
        "original-generation",
        Privacy.CLOUD_ALLOWED,
        max_output_tokens=24,
        messages=(
            ModelMessage("user", "unchanged goal"),
            ModelMessage(
                "assistant", tool_calls=(ToolCall("completed", "computer.execute", {"x": 1}),)
            ),
            ModelMessage("tool", "already executed once", tool_call_id="completed"),
        ),
    )
    model = FailoverModel(
        (primary, alternate),
        cloud_indices=frozenset({0}),
        cloud_request_budget=1,
        rate_limit_max_wait_seconds=1,
        on_retry=notice,
    )
    started = asyncio.get_running_loop().time()
    chunks = await collect(model, request)
    assert asyncio.get_running_loop().time() - started >= 0.015
    assert chunks[0].text == "confirmed"
    assert len(primary.requests) == 2 and not alternate.requests
    assert notices == [(request, 0.015)]
    assert primary.requests[0] is request
    retried = primary.requests[1]
    assert retried.generation_id != request.generation_id
    assert retried.messages == request.messages and retried.tools == request.tools
    assert retried.privacy is request.privacy and retried.max_output_tokens == 24
    assert model.name == "selected-provider"


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds", [7, 0, -7])
async def test_http_date_uses_injected_clock_and_past_date_does_not_wait(seconds: int) -> None:
    now = datetime(2026, 10, 16, 12, tzinfo=UTC)
    primary = LimitedModel(limited(format_datetime(now + timedelta(seconds=seconds), usegmt=True)))
    token = CancellationToken()
    delays = []

    async def notice(request: ModelRequest, delay: float) -> None:
        delays.append(delay)
        token.cancel()

    model = FailoverModel(
        (primary,), rate_limit_max_wait_seconds=10, clock=lambda: now, on_retry=notice
    )
    assert await collect(model, ModelRequest("goal", "g"), token) == []
    assert delays == [max(0, seconds)] and len(primary.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [None, "invalid", "nan", "inf", "-1"])
async def test_missing_or_invalid_header_uses_finite_configured_backoff(header: str | None) -> None:
    primary = LimitedModel(limited(header))
    delays = []

    async def notice(request: ModelRequest, delay: float) -> None:
        delays.append(delay)

    model = FailoverModel(
        (primary,), backoff_seconds=0.001, rate_limit_max_wait_seconds=1, on_retry=notice
    )
    assert (await collect(model, ModelRequest("goal", "g")))[0].text == "confirmed"
    assert delays == [0.001] and len(primary.requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["61", "86400", "99999999999999999999999999999"])
async def test_server_wait_over_cap_preserves_error_without_retry_or_notification(
    header: str,
) -> None:
    error = limited(header)
    primary = LimitedModel(error)

    async def notice(request: ModelRequest, delay: float) -> None:
        raise AssertionError("a refused retry must not be announced")

    model = FailoverModel((primary,), rate_limit_max_wait_seconds=60, on_retry=notice)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        await collect(model, ModelRequest("goal", "g"))
    assert caught.value is error and len(primary.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["text", "tool_request", "finished", "buffered_tool"])
async def test_enabled_policy_cannot_retry_after_any_emission_or_buffered_tool(kind: str) -> None:
    error = limited("0")
    before: tuple[ModelChunk, ...] = ()
    if kind == "buffered_tool":
        error.add_note(_TOOL_INTENT_EMITTED)
    else:
        before = (ModelChunk(kind, "partial" if kind == "text" else ""),)
    primary = LimitedModel(error, before=before)

    async def notice(request: ModelRequest, delay: float) -> None:
        raise AssertionError("emission must fence retry")

    model = FailoverModel((primary,), rate_limit_max_wait_seconds=1, on_retry=notice)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        await collect(model, ModelRequest("goal", "g"))
    assert caught.value is error and len(primary.requests) == 1


@pytest.mark.asyncio
async def test_second_429_is_terminal_and_total_attempts_remain_two() -> None:
    error = limited("0")
    primary = LimitedModel(error, always_fail=True)
    delays = []

    async def notice(request: ModelRequest, delay: float) -> None:
        delays.append(delay)

    with pytest.raises(httpx.HTTPStatusError) as caught:
        await collect(
            FailoverModel((primary,), rate_limit_max_wait_seconds=1, on_retry=notice),
            ModelRequest("goal", "g"),
        )
    assert caught.value is error and len(primary.requests) == 2 and delays == [0]


@pytest.mark.asyncio
@pytest.mark.parametrize("task_cancel", [False, True])
async def test_token_or_task_cancel_interrupts_wait_and_never_dispatches_again(
    task_cancel: bool,
) -> None:
    primary = LimitedModel(limited("60"))
    token = CancellationToken()
    waiting = asyncio.Event()

    async def notice(request: ModelRequest, delay: float) -> None:
        assert delay == 60
        waiting.set()

    task = asyncio.create_task(
        collect(
            FailoverModel((primary,), rate_limit_max_wait_seconds=60, on_retry=notice),
            ModelRequest("goal", "g"),
            token,
        )
    )
    await asyncio.wait_for(waiting.wait(), 1)
    if task_cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.5)
    else:
        token.cancel()
        assert await asyncio.wait_for(task, 0.5) == []
    assert len(primary.requests) == 1


@pytest.mark.asyncio
async def test_additional_cloud_request_still_requires_explicit_budget_and_privacy() -> None:
    primary = LimitedModel(limited("0"))
    model = FailoverModel((primary,), cloud_indices=frozenset({0}), rate_limit_max_wait_seconds=1)
    with pytest.raises(httpx.HTTPStatusError):
        await collect(model, ModelRequest("goal", "g", Privacy.CLOUD_ALLOWED))
    with pytest.raises(PermissionError):
        await collect(model, ModelRequest("private", "g2"))
    assert len(primary.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("groq", [True, False])
async def test_groq_daily_request_exhaustion_refuses_retry_without_guessing_other_hosts(
    groq: bool,
) -> None:
    error = limited("0", host="api.groq.com" if groq else "synthetic.invalid", daily_remaining="0")
    primary = LimitedModel(error)
    model = FailoverModel((primary,), rate_limit_max_wait_seconds=1)
    if groq:
        with pytest.raises(httpx.HTTPStatusError) as caught:
            await collect(model, ModelRequest("goal", "g"))
        assert caught.value is error and len(primary.requests) == 1
    else:
        assert (await collect(model, ModelRequest("goal", "g")))[0].text == "confirmed"
        assert len(primary.requests) == 2


@pytest.mark.parametrize("maximum", [-1, 61, float("nan"), float("inf")])
def test_recovery_wait_cap_must_be_finite_and_at_most_sixty_seconds(maximum: float) -> None:
    with pytest.raises(ValueError):
        FailoverModel((LimitedModel(limited()),), rate_limit_max_wait_seconds=maximum)


@pytest.mark.asyncio
async def test_default_policy_does_not_enable_server_wait_or_notification() -> None:
    primary = LimitedModel(limited("86400"))

    async def notice(request: ModelRequest, delay: float) -> None:
        raise AssertionError("unconfigured recovery remains disabled")

    assert (
        await collect(
            FailoverModel((primary,), backoff_seconds=0, on_retry=notice), ModelRequest("goal", "g")
        )
    )[0].text == "confirmed"
    assert len(primary.requests) == 2


@pytest.mark.asyncio
async def test_cancel_during_wait_notification_joins_callback_without_second_request() -> None:
    primary = LimitedModel(limited("1"))
    token = CancellationToken()
    entered, closed = asyncio.Event(), asyncio.Event()

    async def notice(request: ModelRequest, delay: float) -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            closed.set()

    task = asyncio.create_task(
        collect(
            FailoverModel((primary,), rate_limit_max_wait_seconds=1, on_retry=notice),
            ModelRequest("goal", "g"),
            token,
        )
    )
    await asyncio.wait_for(entered.wait(), 1)
    token.cancel()
    assert await asyncio.wait_for(task, 0.5) == []
    assert closed.is_set() and len(primary.requests) == 1


@pytest.mark.asyncio
async def test_actual_http_429_wait_and_same_adapter_payload_retry() -> None:
    bodies: list[bytes] = []
    arrivals: list[float] = []
    handlers: set[asyncio.Task[None]] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        handlers.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            bodies.append(await reader.readexactly(length))
            arrivals.append(asyncio.get_running_loop().time())
            if len(bodies) == 1:
                body = b"{}"
                response = (
                    b"HTTP/1.1 429 Too Many Requests\r\nRetry-After: 0.015\r\n"
                    b"Content-Length: 2\r\nConnection: close\r\n\r\n" + body
                )
            else:
                body = (
                    b'data: {"choices":[{"delta":{"content":"confirmed"},'
                    b'"finish_reason":"stop"}]}\n\n'
                )
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        adapter = OpenAICompatibleAdapter(
            base_url=f"http://127.0.0.1:{port}",
            api_key="synthetic",  # pragma: allowlist secret
            model="synthetic",
        )
        chunks = await collect(
            FailoverModel((adapter,), cloud_request_budget=1, rate_limit_max_wait_seconds=1),
            ModelRequest("synthetic goal", "g", Privacy.CLOUD_ALLOWED),
        )
        assert any(chunk.text == "confirmed" for chunk in chunks)
        assert len(bodies) == 2 and bodies[0] == bodies[1]
        assert arrivals[1] - arrivals[0] >= 0.015
    finally:
        server.close()
        await server.wait_closed()
        await asyncio.gather(*tuple(handlers), return_exceptions=True)
