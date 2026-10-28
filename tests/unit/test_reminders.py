# ruff: noqa: RUF001
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from siro.services.agent.reminders import Reminder, ReminderService, parse_reminder

TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime(2026, 10, 28, 15, 0, tzinfo=TAIPEI).astimezone(UTC)


def local(due: datetime) -> tuple[int, int, int, int]:
    d = due.astimezone(TAIPEI)
    return d.day, d.hour, d.minute, d.second


@pytest.mark.parametrize(
    ("text", "expected", "what"),
    [
        ("30分鐘後提醒我倒垃圾", (28, 15, 30, 0), "倒垃圾"),
        ("提醒我半小時後喝水", (28, 15, 30, 0), "喝水"),
        ("兩個小時後提醒我開會", (28, 17, 0, 0), "開會"),
        ("一個半小時後提醒我煮飯", (28, 16, 30, 0), "煮飯"),
        ("明天八點提醒我交報告", (29, 8, 0, 0), "交報告"),
        ("明天下午三點半提醒我看牙醫", (29, 15, 30, 0), "看牙醫"),
        ("今晚九點提醒我吃藥", (28, 21, 0, 0), "吃藥"),
        ("後天早上7:45提醒我搭車", (30, 7, 45, 0), "搭車"),
        ("提醒我 18點 打電話", (28, 18, 0, 0), "打電話"),
        ("八點提醒我睡覺", (28, 20, 0, 0), "睡覺"),
    ],
)
def test_parse(text: str, expected: tuple[int, int, int, int], what: str) -> None:
    parsed = parse_reminder(text, NOW)
    assert parsed is not None
    assert local(parsed[0]) == expected
    assert parsed[1] == what


def test_parse_without_time_is_not_a_reminder() -> None:
    assert parse_reminder("你有提醒功能嗎", NOW) is None


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def make(tmp_path: Path, clock: Clock, fired: list[tuple[str, bool]]) -> ReminderService:
    async def fire(item: Reminder, late: bool) -> None:
        fired.append((item.text, late))

    return ReminderService(tmp_path / "reminders.json", fire, clock=clock)


def test_add_list_cancel_and_persist(tmp_path: Path) -> None:
    clock, fired = Clock(), []
    service = make(tmp_path, clock, fired)
    assert "我會提醒你" in (service.handle("30分鐘後提醒我倒垃圾") or "")
    assert "我會提醒你" in (service.handle("明天八點提醒我交報告") or "")
    assert service.handle("今天天氣如何") is None
    reply = service.handle("我有哪些提醒") or ""
    assert "倒垃圾" in reply
    assert "交報告" in reply
    # A restart keeps what is still pending.
    assert len(make(tmp_path, clock, fired).pending()) == 2
    assert "已取消提醒：倒垃圾" in (service.handle("取消倒垃圾的提醒") or "")
    assert [i.text for i in service.pending()] == ["交報告"]
    assert "已取消全部" in (service.handle("取消全部提醒") or "")
    assert service.pending() == []
    assert len(make(tmp_path, clock, fired).pending()) == 0


def test_past_time_is_refused(tmp_path: Path) -> None:
    service = make(tmp_path, Clock(), [])
    assert "已經過了" in (service.handle("今天下午兩點提醒我開會") or "")
    assert service.pending() == []


def test_fires_once_when_due_and_flags_late(tmp_path: Path) -> None:
    clock, fired = Clock(), []
    service = make(tmp_path, clock, fired)
    service.handle("10分鐘後提醒我喝水")
    assert asyncio.run(service.fire_due()) == 0
    clock.now = NOW + timedelta(minutes=10, seconds=1)
    assert asyncio.run(service.fire_due()) == 1
    assert asyncio.run(service.fire_due()) == 0
    assert fired == [("喝水", False)]
    service.handle("5分鐘後提醒我伸展")
    clock.now += timedelta(minutes=30)  # app was closed past the due time
    assert asyncio.run(service.fire_due()) == 1
    assert fired[-1] == ("伸展", True)


def test_overdue_by_more_than_a_day_is_dropped(tmp_path: Path) -> None:
    clock, fired = Clock(), []
    service = make(tmp_path, clock, fired)
    service.handle("5分鐘後提醒我伸展")
    clock.now += timedelta(days=2)
    assert asyncio.run(service.fire_due()) == 0
    assert fired == []
    assert service.pending() == []


def test_intent_parsing_and_filter(tmp_path: Path) -> None:
    from siro.services.agent.reminders import may_hold_event, parse_intent

    assert may_hold_event("我明天早上有面試")
    assert not may_hold_event("你好嗎")
    due, text = parse_intent(
        '好的 {"remind":true,"when":"2026-10-29 07:30","text":"面試"}', NOW
    ) or (
        None,
        "",
    )
    assert due is not None
    assert local(due) == (29, 7, 30, 0)
    assert text == "面試"
    assert parse_intent('{"remind":false}', NOW) is None
    assert parse_intent('{"remind":true,"when":"2026-10-28 08:00","text":"x"}', NOW) is None
    assert parse_intent("not json", NOW) is None
    service = make(tmp_path, Clock(), [])
    assert service.add_from_intent(due, text) is not None
    assert service.add_from_intent(due, text) is None  # no duplicate
