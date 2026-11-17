from __future__ import annotations

from dataclasses import replace

import httpx
import pytest

from siro.services.tools.web_search import BRAVE_URL, WebSearch, WebSearchError


def test_from_env_is_off_by_default_and_rejects_half_configuration() -> None:
    assert WebSearch.from_env({}) is None
    assert WebSearch.from_env({"SIRO_WEB_SEARCH": "off"}) is None
    for env in (
        {"SIRO_WEB_SEARCH": "brave"},
        {"SIRO_WEB_SEARCH": "searxng", "SIRO_SEARXNG_URL": "localhost"},
        {"SIRO_WEB_SEARCH": "duckduckgo"},
    ):
        with pytest.raises(ValueError):
            WebSearch.from_env(env)
    search = WebSearch.from_env({"SIRO_WEB_SEARCH": "searxng", "SIRO_SEARXNG_URL": "http://x/"})
    assert search is not None and search.url == "http://x/search"


@pytest.mark.asyncio
async def test_brave_results_are_bounded_and_filtered() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), token=request.headers["X-Subscription-Token"])
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"title": "A", "url": "https://a.example/", "description": "x" * 900},
                        {"title": "bad", "url": "javascript:alert(1)"},
                        {"title": "B", "url": "https://b.example/"},
                        {"title": "C", "url": "https://c.example/"},
                    ]
                }
            },
        )

    search = replace(
        WebSearch("brave", BRAVE_URL, "synthetic-key"), transport=httpx.MockTransport(handler)
    )
    out = await search.execute({"query": " 台北 天氣 ", "count": 2})
    assert isinstance(out, dict) and out["query"] == "台北 天氣"
    assert [r["url"] for r in out["results"]] == ["https://a.example/", "https://b.example/"]
    assert len(out["results"][0]["snippet"]) == 300
    assert seen["token"] == "synthetic-key" and "count=2" in str(seen["url"])
    for bad in ({}, {"query": ""}, {"query": "x", "count": 99}, {"query": "x", "count": True}):
        with pytest.raises(ValueError):
            await search.execute(bad)


@pytest.mark.asyncio
async def test_searxng_shape_and_failures() -> None:
    def ok(request: httpx.Request) -> httpx.Response:
        assert request.url.params["format"] == "json"
        return httpx.Response(
            200, json={"results": [{"title": "T", "url": "http://t.example", "content": "c"}]}
        )

    search = WebSearch("searxng", "http://x/search", transport=httpx.MockTransport(ok))
    assert await search.search("q") == [{"title": "T", "url": "http://t.example", "snippet": "c"}]

    def denied(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    with pytest.raises(WebSearchError, match="search_http_429"):
        await replace(search, transport=httpx.MockTransport(denied)).search("q")

    def garbage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>")

    with pytest.raises(WebSearchError, match="search_unavailable"):
        await replace(search, transport=httpx.MockTransport(garbage)).search("q")
