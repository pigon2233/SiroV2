"""Wire, cache, cancellation and failure tests; no fake semantic quality claims."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from siro.adapters.models.ollama_memory_relevance import OllamaMemoryRelevance
from siro.ports.embeddings import RetrievalUnavailable
from siro.ports.memory_relevance import RelevanceCandidate

MODEL = "qwen3:4b-instruct"
DIGEST = "a" * 64
ITEMS = (RelevanceCandidate("scope/revision/hash-1", "synthetic tea"),)
YES = '{"decisions":{"0":{"match":true,"quote":"synthetic tea"}}}'
NO = '{"decisions":{"0":{"match":false,"quote":""}}}'


def tags(digest: str = DIGEST) -> httpx.Response:
    return httpx.Response(200, json={"models": [{"name": MODEL, "digest": digest}]})


def response(content: str, **updates: Any) -> httpx.Response:
    result = {
        "model": MODEL,
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": 100,
        "eval_count": 20,
    }
    result.update(updates)
    return httpx.Response(200, json=result)


def transport(content: str, **updates: Any) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return tags()
        body = json.loads(request.content)
        assert body["think"] is False and body["stream"] is False
        count = len(json.loads(body["messages"][1]["content"])["memories"])
        assert count == 1 and body["options"]["num_predict"] == 768
        assert body["format"]["properties"]["decisions"]["required"] == ["0"]
        return response(content, **updates)

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_exact_quotes_cache_and_source_key_isolation() -> None:
    adapter = OllamaMemoryRelevance(MODEL, DIGEST, transport=transport(YES))
    assert await adapter.select("drink", ITEMS) == (0,)
    assert await adapter.select("drink", ITEMS) == (0,)
    assert adapter.usage.calls == 1 and adapter.usage.cache_hits == 1
    assert adapter.usage.input_tokens == 100 and adapter.usage.output_tokens == 20
    assert await adapter.select(
        "drink", (RelevanceCandidate("changed-source", "synthetic tea"),)
    ) == (0,)
    assert adapter.usage.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"decisions":{},"decisions":{}}',
        '{"decisions":{"0":{"match":true,"quote":"tea"},"0":{"match":false,"quote":""}}}',
        '{"decisions":{"true":{"match":true,"quote":"tea"}}}',
        '{"decisions":{"1":{"match":true,"quote":"tea"}}}',
        '{"decisions":{"0":{"match":true,"quote":"invented"}}}',
        '{"decisions":{},"authorize":true}',
        '{"decisions":{"0":{"match":true,"quote":""}}}',
        '{"decisions":{"0":{"match":true,"quote":" tea "}}}',
        '{"decisions":{"0":{"match":false,"quote":"tea"}}}',
        '{"decisions":{}}',
        '{"decisions":[]}',
        '{"decisions":{"0":{"match":"false","quote":""}}}',
        '{"decisions":{"0":{"match":1,"quote":"tea"}}}',
    ],
)
async def test_malformed_or_invented_selection_fails_closed(content: str) -> None:
    adapter = OllamaMemoryRelevance(MODEL, DIGEST, transport=transport(content))
    with pytest.raises(RetrievalUnavailable) as error:
        await adapter.select("PRIVATE query", ITEMS)
    assert "PRIVATE" not in str(error.value) and adapter.usage.cache_hits == 0
    # Invalid semantic packets still cost real model work; do not omit their usage.
    assert adapter.usage.input_tokens == 100 and adapter.usage.output_tokens == 20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates",
    [
        {"done_reason": "length"},
        {"done": False},
        {"model": "other"},
        {"message": {"role": "tool", "content": YES}},
        {"message": {"role": "assistant", "content": YES, "tool_calls": [{}]}},
    ],
)
async def test_incomplete_wrong_model_or_tool_calls_cannot_select(
    updates: dict[str, object],
) -> None:
    with pytest.raises(RetrievalUnavailable):
        await OllamaMemoryRelevance(MODEL, DIGEST, transport=transport(NO, **updates)).select(
            "query", ITEMS
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "https://127.0.0.1",
        "http://example.com",
        "http://127.0.0.1/x",
        "http://u:p@127.0.0.1",
        "http://127.0.0.1?x=y",
        "http://127.0.0.1#x",
        "http://127.0.0.1:0",
        "http://127.0.0.1:99999",
        "http://127.0.0.1:invalid",
    ],
)
def test_loopback_only(url: str) -> None:
    with pytest.raises(ValueError):
        OllamaMemoryRelevance(MODEL, DIGEST, base_url=url)


@pytest.mark.asyncio
async def test_cancel_during_inference_does_not_cache_late_result() -> None:
    started, closed = asyncio.Event(), asyncio.Event()

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return tags()
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            closed.set()
        raise AssertionError("unreachable")

    adapter = OllamaMemoryRelevance(MODEL, DIGEST, transport=httpx.MockTransport(handle))
    task = asyncio.create_task(adapter.select("query", ITEMS))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set() and adapter.usage.cache_hits == 0
    assert adapter.usage.calls == adapter.usage.unmeasured_calls == 1


@pytest.mark.asyncio
async def test_rejection_checks_each_candidate_independently() -> None:
    adapter = OllamaMemoryRelevance(MODEL, DIGEST, transport=transport(NO))
    assert await adapter.select("query", ITEMS) == ()
    assert (
        await adapter.select("query", (*ITEMS, RelevanceCandidate("second", "another source")))
        == ()
    )
    assert adapter.usage.calls == 2 and adapter.usage.cache_hits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("when", ["before", "after", "cached"])
async def test_digest_change_rejects_even_cached_results(when: str) -> None:
    reads = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal reads
        if request.url.path == "/api/tags":
            reads += 1
            limit = {"before": 0, "after": 1, "cached": 2}[when]
            return tags(DIGEST if reads <= limit else "b" * 64)
        return response(YES)

    adapter = OllamaMemoryRelevance(MODEL, DIGEST, transport=httpx.MockTransport(handle))
    if when == "cached":
        assert await adapter.select("query", ITEMS) == (0,)
    with pytest.raises(RetrievalUnavailable, match="digest"):
        await adapter.select("query", ITEMS)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 400, 500])
async def test_http_failures_are_sanitized_and_never_redirected(status: int) -> None:
    adapter = OllamaMemoryRelevance(
        MODEL,
        DIGEST,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                status, text="PRIVATE body", headers={"Location": "https://evil"}
            )
        ),
    )
    with pytest.raises(RetrievalUnavailable) as error:
        await adapter.select("PRIVATE", ITEMS)
    assert "PRIVATE" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,candidates",
    [
        ("", ITEMS),
        ("x" * 8193, ITEMS),
        ("query", ()),
        ("query", ITEMS * 9),
        ("query", (RelevanceCandidate("key", "x" * 4097),)),
        ("query", (RelevanceCandidate("x" * 257, "text"),)),
    ],
)
async def test_input_bounds_fail_before_http(
    query: str, candidates: tuple[RelevanceCandidate, ...]
) -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not send out-of-bound input")

    with pytest.raises(RetrievalUnavailable):
        await OllamaMemoryRelevance(MODEL, DIGEST, transport=httpx.MockTransport(forbidden)).select(
            query, candidates
        )


@pytest.mark.asyncio
async def test_lru_is_bounded_and_disabled_cache_does_not_hide_cost() -> None:
    adapter = OllamaMemoryRelevance(MODEL, DIGEST, cache_size=1, transport=transport(YES))
    for query in ("one", "two", "one"):
        await adapter.select(query, ITEMS)
    assert adapter.usage.calls == 3 and len(adapter._cache) == 1
    disabled = OllamaMemoryRelevance(MODEL, DIGEST, cache_size=0, transport=transport(NO))
    await disabled.select("query", ITEMS)
    await disabled.select("query", ITEMS)
    assert disabled.usage.calls == 2 and disabled.usage.cache_hits == 0


@pytest.mark.asyncio
async def test_oversized_later_pair_rejects_complete_operation_before_http() -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("all pairs must fit before sending any request")

    candidates = (
        RelevanceCandidate("small", "short source"),
        RelevanceCandidate("large", "y" * 3000, tuple(f"{i:03d}" + "z" * 97 for i in range(80))),
    )
    adapter = OllamaMemoryRelevance(MODEL, DIGEST, transport=httpx.MockTransport(forbidden))
    with pytest.raises(RetrievalUnavailable, match="context"):
        await adapter.select("x" * 6000, candidates)
    assert adapter.usage.calls == 0


@pytest.mark.asyncio
async def test_event_category_is_not_inferred_from_text_or_reused_across_categories() -> None:
    seen: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return tags()
        data = json.loads(json.loads(request.content)["messages"][1]["content"])
        seen.append(data["memories"][0])
        return response(NO)

    adapter = OllamaMemoryRelevance(MODEL, DIGEST, transport=httpx.MockTransport(handle))
    for category in ("conversation.user_text.v1", "conversation.text_delta.v1"):
        await adapter.select(
            "query", (RelevanceCandidate("same-key", "synthetic tea", (category,)),)
        )
    assert adapter.usage.calls == 2
    assert seen[0]["source_event_types"] == ["conversation.user_text.v1"]
    assert seen[1]["source_event_types"] == ["conversation.text_delta.v1"]
    assert all(m["speaker_identity_verified"] is False for m in seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [None, [], "PRIVATE body", {}, {"message": None}])
async def test_malformed_provider_shapes_fail_without_echoing_body(body: Any) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return tags() if request.url.path == "/api/tags" else httpx.Response(200, json=body)

    with pytest.raises(RetrievalUnavailable) as error:
        await OllamaMemoryRelevance(MODEL, DIGEST, transport=httpx.MockTransport(handle)).select(
            "query", ITEMS
        )
    assert "PRIVATE" not in str(error.value)
