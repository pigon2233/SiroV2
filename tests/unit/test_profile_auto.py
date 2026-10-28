from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.services.agent.profile_auto import ProfileAuto


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def message(text: str = "我喜歡茶") -> UserTextEvent:
    now = datetime.now(UTC)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="siro.presentation",
        occurred_at=now,
        received_at=now,
        trace_id="synthetic",
        session_id="A",
        turn_id="t",
        sequence=0,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.CLOUD_ALLOWED,
        payload=UserTextPayload(text=text, language="zh"),
    )


class Source:
    def __init__(self) -> None:
        self.events: list[UserTextEvent] = []

    async def unseen_user_events(self) -> list[UserTextEvent]:
        return list(self.events)


class Service:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.fail = False

    async def build(self, events: list[UserTextEvent]) -> list[object]:
        self.calls.append(len(events))
        if self.fail:
            raise RuntimeError("codex down")
        return []


def make(busy: bool = False) -> tuple[ProfileAuto, Clock, Source, Service, list[bool]]:
    clock, source, service, flag = Clock(), Source(), Service(), [busy]
    auto = ProfileAuto(service, source, lambda: flag[0], clock=clock)
    return auto, clock, source, service, flag


@pytest.mark.asyncio
async def test_waits_for_idle_and_threshold() -> None:
    auto, clock, source, service, _ = make()
    source.events = [message() for _ in range(10)]
    await auto.tick()
    assert service.calls == []  # not idle for 60s yet
    clock.now += 61
    await auto.tick()
    assert service.calls == [10] and auto.last_run is not None and auto.state == "waiting"


@pytest.mark.asyncio
async def test_few_messages_wait_for_age_then_cooldown_applies() -> None:
    auto, clock, source, service, _ = make()
    source.events = [message()]
    clock.now += 3600
    await auto.tick()
    assert service.calls == []  # 1 message, only 1h since start
    clock.now += 6 * 3600
    await auto.tick()
    assert service.calls == [1]
    source.events = [message() for _ in range(12)]
    clock.now += 60
    await auto.tick()
    assert service.calls == [1]  # 30 minute cooldown
    clock.now += 1800
    await auto.tick()
    assert service.calls == [1, 12]


@pytest.mark.asyncio
async def test_processed_messages_are_not_retried() -> None:
    auto, clock, source, service, _ = make()
    source.events = [message() for _ in range(10)]
    clock.now += 61
    await auto.tick()
    clock.now += 6 * 3600 + 1800
    await auto.tick()  # same 10 still "unseen" by the store but already processed
    assert service.calls == [10]


@pytest.mark.asyncio
async def test_busy_blocks_and_resets_idle() -> None:
    auto, clock, source, service, flag = make(busy=True)
    source.events = [message() for _ in range(10)]
    clock.now += 600
    await auto.tick()
    assert service.calls == [] and auto.state == "foreground"
    flag[0] = False
    clock.now += 30
    await auto.tick()
    assert service.calls == []  # idle clock restarted by the busy tick
    clock.now += 31
    await auto.tick()
    assert service.calls == [10]


@pytest.mark.asyncio
async def test_failure_logs_backs_off_and_never_raises() -> None:
    auto, clock, source, service, _ = make()
    service.fail = True
    source.events = [message() for _ in range(10)]
    clock.now += 61
    await auto.tick()
    assert service.calls == [10] and auto.state == "backoff" and auto.last_run is None
    clock.now += 1800
    await auto.tick()
    assert service.calls == [10]  # backoff doubled to 1h
    service.fail = False
    clock.now += 1800
    await auto.tick()
    assert service.calls == [10, 10] and auto.state == "waiting"


@pytest.mark.asyncio
async def test_disabled_never_runs() -> None:
    clock, source, service = Clock(), Source(), Service()
    source.events = [message() for _ in range(10)]
    auto = ProfileAuto(service, source, lambda: False, enabled=False, clock=clock)
    clock.now += 600
    await auto.tick()
    assert service.calls == [] and auto.snapshot()["state"] == "disabled"
