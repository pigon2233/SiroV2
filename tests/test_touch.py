import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.mock import MockModel
from siro.core.touch import Touch, TouchMemory, TouchReplies, clean_touch_line, touch_prompt
from siro.ports.models import Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion

NOON = datetime(2026, 10, 20, 4, 0, tzinfo=UTC)  # 12:00 in Taipei


def test_touch_speech_is_rare_never_busy_and_bounded_per_day() -> None:
    rules = TouchReplies(daily_limit=3)
    assert rules.choose("pat", NOON, busy=True).reason == "busy"
    assert rules.choose("pat", NOON, busy=False).speak
    rules.spoke("pat", NOON)
    # Any touch waits a minute after a spoken one; the same kind waits longer.
    assert rules.choose("poke", NOON + timedelta(seconds=30), busy=False).reason == "cooldown"
    assert rules.choose("poke", NOON + timedelta(seconds=61), busy=False).speak
    later = NOON + timedelta(seconds=90)
    assert rules.choose("pat", later, busy=False).reason == "repeat_cooldown"
    rules.spoke("poke", later)
    carried = NOON + timedelta(minutes=5)
    rules.spoke("carry", carried)
    assert rules.choose("carry", carried + timedelta(minutes=5), busy=False).reason == (
        "daily_limit"
    )
    # A new local day starts the count again; moving the window still waits its ten minutes.
    tomorrow = NOON + timedelta(days=1)
    assert rules.choose("pat", tomorrow, busy=False).speak
    assert not TouchReplies(enabled=False).choose("pat", NOON, busy=False).speak


def test_model_lines_are_cut_to_one_short_spoken_sentence() -> None:
    assert clean_touch_line("「嘿嘿，好舒服喔！」") == "嘿嘿，好舒服喔！"  # noqa: RUF001
    assert clean_touch_line("（歪頭）別戳啦～我在忙。😊") == "別戳啦～"  # noqa: RUF001
    assert clean_touch_line("哇！要去哪裡？\n我好期待。") == "哇！"  # noqa: RUF001
    assert clean_touch_line("") is None
    assert clean_touch_line("As an AI I cannot feel touch.") is None
    assert clean_touch_line("這是一段非常非常非常非常非常非常非常長而且沒有標點的回答內容") is None


def test_prompt_and_context_describe_the_touch() -> None:
    zone = ZoneInfo("Asia/Taipei")
    prompt = touch_prompt("poke", 5, NOON, zone)
    assert "連續戳了你5下" in prompt and "不耐煩" in prompt and "12點00分" in prompt
    memory = TouchMemory()
    assert memory.context(NOON, zone) is None
    memory.add(Touch("pat", 1, NOON, "嘿嘿。"))
    memory.add(Touch("carry", 1, NOON + timedelta(minutes=1)))
    context = memory.context(NOON + timedelta(minutes=2), zone)
    assert context is not None
    assert "patted her head at 12:00 (SIRO said: 嘿嘿。)" in context
    assert "moved her across the screen at 12:01" in context
    assert memory.context(NOON + timedelta(minutes=12), zone) is None


class _RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[dict[str, object]] = []

    async def broadcast(self, message: dict[str, object], *, urgent: bool = False) -> None:
        self.sent.append(dict(message))
        await super().broadcast(message, urgent=urgent)


@pytest.mark.asyncio
async def test_touch_line_waits_until_the_open_reply_finishes(tmp_path: Path) -> None:
    hub = _RecordingHub()
    controller = IntegratedCompanion(
        tmp_path,
        MockModel(()),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
    )

    async def line(_kind: str, _count: int, _now: datetime) -> str:
        controller._active_sessions.add("browser")
        return "嘿嘿好舒服"

    controller._touch_line = line  # type: ignore[assignment]
    pending = asyncio.create_task(controller.react_to_touch("pat", 1))
    await asyncio.sleep(0.12)
    assert not any(item.get("type") == "assistant_started" for item in hub.sent)
    controller._active_sessions.discard("browser")
    await pending
    assert [item["type"] for item in hub.sent] == [
        "assistant_started",
        "assistant_delta",
        "assistant_terminal",
    ]
    assert hub.sent[1]["text"] == "嘿嘿好舒服"
    assert isinstance(hub.sent[0]["stream_id"], str)
