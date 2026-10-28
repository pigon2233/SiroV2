# ruff: noqa: RUF001
"""Bedtime recap: today's runs are summarized, with a local fallback and a relay-token hook."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.daily_recap import build_recap, is_recap_command
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.presentation.gateway import create_app

TOKEN = "test-only-esp32-relay-token-with-32-bytes"


async def seeded(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await SQLiteAgentRunRepository(store).start("s1", "今天天氣如何")
    return store


def test_commands() -> None:
    assert is_recap_command(" /recap ") and is_recap_command("每日回顧")
    assert not is_recap_command("幫我回顧一下程式")


@pytest.mark.asyncio
async def test_summarizer_gets_today_log_and_failure_falls_back(tmp_path: Path) -> None:
    store = await seeded(tmp_path)
    prompts: list[str] = []

    async def summarize(prompt: str) -> str:
        prompts.append(prompt)
        return " 今天聊了天氣，晚安。 "

    assert await build_recap(store, summarize) == "今天聊了天氣，晚安。"
    assert "今天天氣如何" in prompts[0]

    async def broken(_: str) -> str:
        raise RuntimeError("offline")

    assert "1 件事" in await build_recap(store, broken)
    assert "1 件事" in await build_recap(store, None)
    far = datetime(2020, 1, 1, tzinfo=UTC)
    assert "還沒有聊" in await build_recap(store, summarize, now=far)


@pytest.mark.asyncio
async def test_endpoint_accepts_relay_token_only_from_loopback() -> None:
    calls: list[int] = []

    async def recap() -> str:
        calls.append(1)
        return "晚安"

    app = create_app(on_recap=recap, esp32_relay_token=TOKEN)
    headers = {"X-SIRO-ESP32-Relay-Token": TOKEN}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)),
        base_url="http://127.0.0.1:8000",
    ) as client:
        assert (await client.post("/v1/recap")).status_code == 401
        assert (await client.post("/v1/recap", headers=headers)).json() == {"text": "晚安"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("10.0.0.5", 1)),
        base_url="http://127.0.0.1:8000",
    ) as client:
        assert (await client.post("/v1/recap", headers=headers)).status_code == 401
    assert calls == [1]
