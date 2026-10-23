"""Protocol and failure tests; fake vectors are not semantic quality evidence."""

import asyncio
from typing import Any

import httpx
import pytest

from siro.adapters.models.ollama_embeddings import OllamaEmbedder
from siro.ports.embeddings import EmbeddingProfile, RetrievalUnavailable

PROFILE = EmbeddingProfile("qwen3-embedding:0.6b", "a" * 64, 32)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434",
        "http://localhost:11434",
        "http://example.com",
        "http://127.0.0.1.evil",
        "http://u:p@127.0.0.1",
        "http://127.0.0.1/x",
        "http://127.0.0.1?x=y",
        "http://127.0.0.1#x",
    ],
)
def test_rejects_nonlocal_or_ambiguous_url(url: str) -> None:
    with pytest.raises(ValueError):
        OllamaEmbedder(PROFILE, base_url=url)


@pytest.mark.asyncio
async def test_query_instruction_document_bytes_and_digest_verification() -> None:
    import json

    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": PROFILE.model, "digest": PROFILE.digest}]}
            )
        body = json.loads(request.content)
        assert body["truncate"] is False and body["dimensions"] == 32
        return httpx.Response(200, json={"model": PROFILE.model, "embeddings": [[1.0] * 32]})

    adapter = OllamaEmbedder(PROFILE, transport=httpx.MockTransport(handle))
    vector = await adapter.embed(("合成記憶",), query=False)
    assert len(vector[0]) == 32
    await adapter.embed(("合成問題",), query=True)
    payloads = [json.loads(r.content)["input"][0] for r in requests if r.method == "POST"]
    assert payloads == [
        "合成記憶",
        "Instruct: Retrieve personal memories relevant to the user's question.\nQuery:合成問題",
    ]
    assert len([r for r in requests if r.method == "GET"]) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [[], [0.0] * 32, [float("nan")] * 32, [True] * 32, ["x"] * 32])
async def test_invalid_vectors_fail_without_echoing_input(bad: list[Any]) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": PROFILE.model, "digest": PROFILE.digest}]}
            )
        # httpx JSON correctly forbids NaN; use explicit invalid JSON for that case.
        import json

        return httpx.Response(
            200, content=json.dumps({"model": PROFILE.model, "embeddings": [bad]})
        )

    with pytest.raises(RetrievalUnavailable) as error:
        await OllamaEmbedder(PROFILE, transport=httpx.MockTransport(handle)).embed(
            ("PRIVATE",), query=False
        )
    assert "PRIVATE" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("after", [False, True])
async def test_digest_change_prevents_return(after: bool) -> None:
    count = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal count
        if request.url.path == "/api/tags":
            count += 1
            digest = PROFILE.digest if after and count == 1 else "b" * 64
            return httpx.Response(200, json={"models": [{"name": PROFILE.model, "digest": digest}]})
        return httpx.Response(200, json={"model": PROFILE.model, "embeddings": [[1.0] * 32]})

    with pytest.raises(RetrievalUnavailable, match="digest"):
        await OllamaEmbedder(PROFILE, transport=httpx.MockTransport(handle)).embed(
            ("synthetic",), query=False
        )


@pytest.mark.asyncio
async def test_task_cancellation_closes_pending_request() -> None:
    started = asyncio.Event()
    closed = asyncio.Event()

    async def handle(request: httpx.Request) -> httpx.Response:
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            closed.set()
        raise AssertionError("unreachable")

    adapter = OllamaEmbedder(PROFILE, transport=httpx.MockTransport(handle))
    task = asyncio.create_task(adapter.embed(("synthetic",), query=False))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 400, 500])
async def test_provider_errors_are_sanitized(status: int) -> None:
    adapter = OllamaEmbedder(
        PROFILE,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                status, text="PRIVATE provider body", headers={"Location": "http://evil"}
            )
        ),
    )
    with pytest.raises(RetrievalUnavailable) as error:
        await adapter.embed(("PRIVATE input",), query=False)
    assert "PRIVATE" not in str(error.value)
