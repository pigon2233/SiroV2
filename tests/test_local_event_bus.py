from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from siro.contracts.events import Event, Priority, SystemHealthEvent
from siro.events.local import LocalEventBus


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def now(self) -> datetime:
        return self.value


def make_event(
    number: int,
    *,
    priority: Priority = Priority.INTERACTIVE,
    received_at: datetime | None = None,
    ttl_ms: int | None = 30_000,
) -> SystemHealthEvent:
    timestamp = received_at or datetime(2026, 9, 23, 7, 0, tzinfo=UTC)
    return SystemHealthEvent.model_validate(
        {
            "schema_version": 1,
            "event_id": str(UUID(int=number + 1)),
            "type": "system.health.v1",
            "source": "test.publisher",
            "occurred_at": timestamp,
            "received_at": timestamp,
            "trace_id": f"trace-{number}",
            "sequence": number,
            "priority": priority,
            "ttl_ms": ttl_ms,
            "privacy": "local_only",
            "payload": {
                "component": f"component-{number}",
                "state": "healthy",
                "observed_at": timestamp,
            },
        }
    )


@pytest.mark.asyncio
async def test_duplicate_and_expired_events_are_not_delivered() -> None:
    clock = FakeClock(datetime(2026, 9, 23, 7, 0, tzinfo=UTC))
    bus = LocalEventBus(clock=clock)
    received: list[int] = []
    await bus.start()
    await bus.subscribe("system.*", lambda event: _record(received, event.sequence))
    event = make_event(1, received_at=clock.now())

    first = await bus.publish(event)
    duplicate = await bus.publish(event)
    clock.value += timedelta(seconds=31)
    expired = await bus.publish(make_event(2, received_at=event.received_at))
    await _wait_until(lambda: received == [1])

    assert first.enqueued == 1
    assert duplicate.duplicate is True
    assert expired.expired is True
    await bus.stop()


@pytest.mark.asyncio
async def test_slow_subscriber_does_not_block_fast_subscriber() -> None:
    bus = LocalEventBus()
    slow_gate = asyncio.Event()
    fast_done = asyncio.Event()
    fast_received: list[int] = []

    async def slow_handler(_event: object) -> None:
        await slow_gate.wait()

    async def fast_handler(event: Event) -> None:
        fast_received.append(event.sequence)
        if len(fast_received) == 20:
            fast_done.set()

    await bus.start()
    slow = await bus.subscribe("system.health.v1", slow_handler, capacity=1)
    await bus.subscribe("system.health.v1", fast_handler, capacity=32)
    results = [await bus.publish(make_event(index, ttl_ms=None)) for index in range(20)]

    await asyncio.wait_for(fast_done.wait(), timeout=1)
    assert fast_received == list(range(20))
    assert any(result.rejected == 1 for result in results)
    assert slow.stats().pending <= 1
    slow_gate.set()
    await bus.stop()


@pytest.mark.asyncio
async def test_priority_order_and_bounded_eviction() -> None:
    bus = LocalEventBus()
    gate = asyncio.Event()
    started = asyncio.Event()
    received: list[Priority] = []

    async def handler(event: Event) -> None:
        received.append(event.priority)
        if len(received) == 1:
            started.set()
            await gate.wait()

    await bus.start()
    subscription = await bus.subscribe("system.*", handler, capacity=3)
    await bus.publish(make_event(1, priority=Priority.BACKGROUND, ttl_ms=None))
    await asyncio.wait_for(started.wait(), timeout=1)
    await bus.publish(make_event(2, priority=Priority.BACKGROUND, ttl_ms=None))
    await bus.publish(make_event(3, priority=Priority.TELEMETRY, ttl_ms=None))
    await bus.publish(make_event(4, priority=Priority.INTERACTIVE, ttl_ms=None))
    urgent_result = await bus.publish(make_event(5, priority=Priority.URGENT, ttl_ms=None))

    assert subscription.stats().pending == 3
    assert urgent_result.evicted == 1
    gate.set()
    await _wait_until(lambda: subscription.stats().pending == 0)
    assert received == [
        Priority.BACKGROUND,
        Priority.URGENT,
        Priority.INTERACTIVE,
        Priority.BACKGROUND,
    ]
    await bus.stop()


@pytest.mark.asyncio
async def test_ten_thousand_events_remain_memory_bounded() -> None:
    bus = LocalEventBus(dedup_capacity=128)
    gate = asyncio.Event()

    async def blocked_handler(_event: object) -> None:
        await gate.wait()

    await bus.start()
    subscription = await bus.subscribe("system.*", blocked_handler, capacity=32)
    evictions = 0
    for index in range(10_000):
        result = await bus.publish(make_event(index, priority=Priority.TELEMETRY, ttl_ms=None))
        evictions += result.evicted

    snapshot = bus.snapshot()
    assert subscription.stats().pending <= 32
    assert snapshot.total_pending <= 32
    assert snapshot.dedup_entries == 128
    assert evictions > 0
    gate.set()
    await bus.stop()


@pytest.mark.asyncio
async def test_urgent_burst_still_allows_normal_progress() -> None:
    bus = LocalEventBus()
    gate = asyncio.Event()
    started = asyncio.Event()
    received: list[int] = []

    async def handler(event: Event) -> None:
        received.append(event.sequence)
        if event.sequence == 0:
            started.set()
            await gate.wait()

    await bus.start()
    subscription = await bus.subscribe("system.*", handler, capacity=16)
    await bus.publish(make_event(0, priority=Priority.INTERACTIVE, ttl_ms=None))
    await asyncio.wait_for(started.wait(), timeout=1)
    await bus.publish(make_event(100, priority=Priority.BACKGROUND, ttl_ms=None))
    for index in range(1, 11):
        await bus.publish(make_event(index, priority=Priority.URGENT, ttl_ms=None))

    gate.set()
    await _wait_until(lambda: subscription.stats().pending == 0)
    assert received == [0, *range(1, 9), 100, 9, 10]
    await bus.stop()


@pytest.mark.asyncio
async def test_handler_failure_does_not_kill_subscription() -> None:
    bus = LocalEventBus()
    delivered = asyncio.Event()
    attempts = 0

    async def handler(_event: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic failure")
        delivered.set()

    await bus.start()
    subscription = await bus.subscribe("system.*", handler)
    await bus.publish(make_event(1, ttl_ms=None))
    await bus.publish(make_event(2, ttl_ms=None))
    await asyncio.wait_for(delivered.wait(), timeout=1)

    assert subscription.stats().handler_failures == 1
    assert subscription.stats().delivered == 1
    await bus.stop()


@pytest.mark.asyncio
async def test_unsubscribe_and_stop_leave_no_workers() -> None:
    bus = LocalEventBus()

    async def handler(_event: object) -> None:
        return

    await bus.start()
    first = await bus.subscribe("system.*", handler)
    await bus.subscribe("conversation.*", handler)
    assert bus.snapshot().worker_tasks == 2

    await first.unsubscribe()
    assert bus.snapshot().worker_tasks == 1
    await bus.stop()
    assert bus.snapshot().started is False
    assert bus.snapshot().subscriptions == 0
    assert bus.snapshot().worker_tasks == 0


async def _record(destination: list[int], value: int) -> None:
    destination.append(value)


async def _wait_until(predicate: Callable[[], bool], *, timeout: float = 1.0) -> None:
    async def wait_loop() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_loop(), timeout=timeout)
