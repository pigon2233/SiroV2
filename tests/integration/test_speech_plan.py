from __future__ import annotations

import runpy
from pathlib import Path

import httpx
import pytest

from siro.services.audio.tts import plan_speech, prepare_spoken_text
from siro.services.presentation.gateway import SessionTokens, create_app

ORIGIN = "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_plan_covers_long_canonical_text_without_generating_audio() -> None:
    class Speech:
        async def render(self, text: str, *, rate: float, pitch: float, energy: float) -> bytes:
            raise AssertionError("Planning must not generate audio")

    tokens = SessionTokens()
    token, _ = tokens.issue()
    app = create_app(tokens=tokens, text_to_speech=Speech())
    transport = httpx.ASGITransport(app=app)
    text = "合成長文完整朗讀驗收,保留每一個段落。" * 250 + "最後一句也必須保留。"
    assert len(text) > 4000
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        response = await client.post(
            "/v1/audio/speech/plan",
            headers={"origin": ORIGIN, "authorization": f"Bearer {token}"},
            json={"text": text},
        )
    assert response.status_code == 200
    plan = response.json()
    assert plan["spoken_text"] == prepare_spoken_text(text)
    assert "".join(plan["segments"]) == plan["spoken_text"]
    assert plan["segments"][-1].endswith("最後一句也必須保留。")
    assert all(0 < len(segment) <= 80 for segment in plan["segments"])
    assert len(plan["segments"]) <= 128
    assert plan["version"] == "sentence-v2-first24-rest80"
    assert 0 < len(plan["segments"][0]) <= 24
    assert plan["max_chars"] == 80 and plan["max_total_chars"] == 8000
    assert plan["deadline_seconds"] == 1200


@pytest.mark.parametrize(
    ("text", "first"),
    [
        ("短句。", "短句。"),
        ("先把第一句說完整。" + "後面的內容依照既有上限完整保留。" * 8, "先把第一句說完整。"),
        (
            "這是一個比較長的合成驗收句子,後面還有內容需要讀完。" * 8,
            "這是一個比較長的合成驗收句子,",
        ),
        ("甲" * 30 + "。" + "乙" * 100, "甲" * 24),
        ("synthetic first sentence continues with later words. " * 8, "synthetic first"),
    ],
)
def test_first_segment_is_bounded_and_does_not_absorb_following_text(text: str, first: str) -> None:
    plan = plan_speech(text)
    segments = plan["segments"]
    assert isinstance(segments, list)
    assert segments[0] == first
    assert "".join(segments) == plan["spoken_text"]
    assert 0 < len(segments[0]) <= 24
    assert all(0 < len(segment) <= 80 and segment.strip() for segment in segments)
    if len(str(plan["spoken_text"])) > 80:
        assert any(len(segment) > 24 for segment in segments[1:])


def test_plan_and_owned_worker_bind_the_same_segment_cache_version() -> None:
    worker = runpy.run_path(str(Path(__file__).parents[2] / "scripts/qwen_tts_worker.py"))
    assert plan_speech("合成測試。字串保持完整。")["version"] == worker["SEGMENT_VERSION"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "status"),
    [
        (" ", 422),
        ("{" + '"machine":true' + "}", 422),
        ("甲" * 8001, 413),
        ("甲" * 16001, 422),
    ],
)
async def test_speech_plan_rejects_excess_or_empty_without_silent_truncation(
    text: str, status: int
) -> None:
    tokens = SessionTokens()
    token, _ = tokens.issue()
    transport = httpx.ASGITransport(app=create_app(tokens=tokens))
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        response = await client.post(
            "/v1/audio/speech/plan",
            headers={"origin": ORIGIN, "authorization": f"Bearer {token}"},
            json={"text": text},
        )
    assert response.status_code == status
    assert "segments" not in response.json()


@pytest.mark.asyncio
async def test_speech_plan_uses_fenced_source_before_dom_formatting() -> None:
    tokens = SessionTokens()
    token, _ = tokens.issue()
    transport = httpx.ASGITransport(app=create_app(tokens=tokens))
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        response = await client.post(
            "/v1/audio/speech/plan",
            headers={"origin": ORIGIN, "authorization": f"Bearer {token}"},
            json={"text": "**先說明**\n```python\nraise PRIVATE_FREE_CANARY\n```\n最後一句。"},
        )
    assert response.status_code == 200
    text = response.json()["spoken_text"]
    assert "程式碼內容先不念" in text
    assert "PRIVATE_FREE_CANARY" not in text and "最後一句" in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("origin", "bearer", "status"),
    [(ORIGIN, "", 401), (ORIGIN, "Bearer invalid", 401), ("null", "valid", 403)],
)
async def test_speech_plan_retains_origin_and_bearer_checks(
    origin: str, bearer: str, status: int
) -> None:
    tokens = SessionTokens()
    token, _ = tokens.issue()
    transport = httpx.ASGITransport(app=create_app(tokens=tokens))
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        response = await client.post(
            "/v1/audio/speech/plan",
            headers={
                "origin": origin,
                "authorization": f"Bearer {token}" if bearer == "valid" else bearer,
            },
            json={"text": "合成驗收。"},
        )
    assert response.status_code == status
