"""Bounded, subscriber-isolated in-process event bus."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from siro.contracts.events import Event, Priority
from siro.ports.events import (
    BusSnapshot,
    Clock,
    DeliveryStats,
    EventHandler,
    PublishResult,
)

_PRIORITIES = (
    Priority.URGENT,
    Priority.INTERACTIVE,
    Priority.BACKGROUND,
    Priority.TELEMETRY,
)
_MAX_URGENT_BURST = 8


class UtcClock:
    """Production TTL clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class _EnqueueOutcome(StrEnum):
    ENQUEUED = "enqueued"
    EVICTED = "evicted"
    REJECTED = "rejected"


class _BufferClosedError(RuntimeError):
    pass


class _BoundedPriorityBuffer:
    """A non-blocking bounded buffer with priority and starvation protection."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("subscription capacity must be positive")
        self.capacity = capacity
        self._queues = {priority: deque[Event]() for priority in _PRIORITIES}
        self._size = 0
        self._available = asyncio.Event()
        self._closed = False
        self._urgent_streak = 0

    @property
    def size(self) -> int:
        return self._size

    def put_nowait(self, event: Event) -> _EnqueueOutcome:
        if self._closed:
            return _EnqueueOutcome.REJECTED
        outcome = _EnqueueOutcome.ENQUEUED
        if self._size >= self.capacity:
            incoming_index = _PRIORITIES.index(event.priority)
            evicted = False
            for lower_priority in reversed(_PRIORITIES[incoming_index + 1 :]):
                queue = self._queues[lower_priority]
                if queue:
                    queue.popleft()
                    self._size -= 1
                    evicted = True
                    break
            if not evicted and event.priority in (Priority.BACKGROUND, Priority.TELEMETRY):
                same_priority = self._queues[event.priority]
                if same_priority:
                    same_priority.popleft()
                    self._size -= 1
                    evicted = True
            if not evicted:
                return _EnqueueOutcome.REJECTED
            outcome = _EnqueueOutcome.EVICTED
        self._queues[event.priority].append(event)
        self._size += 1
        self._available.set()
        return outcome

    async def get(self) -> Event:
        while True:
            event = self._pop_next()
            if event is not None:
                return event
            if self._closed:
                raise _BufferClosedError
            self._available.clear()
            if self._size:
                continue
            await self._available.wait()

    def _pop_next(self) -> Event | None:
        if self._size == 0:
            return None
        urgent = self._queues[Priority.URGENT]
        has_normal = any(self._queues[priority] for priority in _PRIORITIES[1:])
        if urgent and (self._urgent_streak < _MAX_URGENT_BURST or not has_normal):
            self._urgent_streak += 1
            self._size -= 1
            return urgent.popleft()
        for priority in _PRIORITIES[1:]:
            queue = self._queues[priority]
            if queue:
                self._urgent_streak = 0
                self._size -= 1
                return queue.popleft()
        self._urgent_streak += 1
        self._size -= 1
        return urgent.popleft()

    def close(self) -> None:
        self._closed = True
        self._available.set()


@dataclass(slots=True)
class _MutableStats:
    delivered: int = 0
    rejected: int = 0
    evicted: int = 0
    handler_failures: int = 0


class LocalSubscription:
    """Handle and worker for one isolated subscriber."""

    def __init__(
        self,
        bus: LocalEventBus,
        subscription_id: int,
        pattern: str,
        handler: EventHandler,
        capacity: int,
    ) -> None:
        self._bus = bus
        self._subscription_id = subscription_id
        self._pattern = pattern
        self._handler = handler
        self._buffer = _BoundedPriorityBuffer(capacity)
        self._stats = _MutableStats()
        self._task = asyncio.create_task(
            self._run(), name=f"siro-event-subscription-{subscription_id}"
        )
        self._closed = False

    @property
    def subscription_id(self) -> int:
        return self._subscription_id

    @property
    def pattern(self) -> str:
        return self._pattern

    @property
    def pending(self) -> int:
        return self._buffer.size

    @property
    def worker_running(self) -> bool:
        return not self._task.done()

    def matches(self, event_type: str) -> bool:
        if self._pattern.endswith(".*"):
            return event_type.startswith(self._pattern[:-1])
        return event_type == self._pattern

    def enqueue(self, event: Event) -> _EnqueueOutcome:
        outcome = self._buffer.put_nowait(event)
        if outcome is _EnqueueOutcome.REJECTED:
            self._stats.rejected += 1
        elif outcome is _EnqueueOutcome.EVICTED:
            self._stats.evicted += 1
        return outcome

    def stats(self) -> DeliveryStats:
        return DeliveryStats(
            delivered=self._stats.delivered,
            rejected=self._stats.rejected,
            evicted=self._stats.evicted,
            handler_failures=self._stats.handler_failures,
            pending=self.pending,
            capacity=self._buffer.capacity,
        )

    async def _run(self) -> None:
        try:
            while True:
                event = await self._buffer.get()
                try:
                    await self._handler(event)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._stats.handler_failures += 1
                else:
                    self._stats.delivered += 1
        except (_BufferClosedError, asyncio.CancelledError):
            return

    async def unsubscribe(self) -> None:
        await self._bus._unsubscribe(self._subscription_id)

    async def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._buffer.close()
        self._task.cancel()
        if self._task is asyncio.current_task():
            return
        await asyncio.gather(self._task, return_exceptions=True)


class LocalEventBus:
    """In-process bus that never waits for subscriber handlers during publish."""

    def __init__(self, *, clock: Clock | None = None, dedup_capacity: int = 4096) -> None:
        if dedup_capacity < 1:
            raise ValueError("dedup_capacity must be positive")
        self._clock = UtcClock() if clock is None else clock
        self._dedup_capacity = dedup_capacity
        self._seen_order: deque[object] = deque()
        self._seen: set[object] = set()
        self._subscriptions: dict[int, LocalSubscription] = {}
        self._next_subscription_id = 1
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            self._started = True

    async def stop(self) -> None:
        async with self._lock:
            if not self._started and not self._subscriptions:
                return
            self._started = False
            subscriptions = list(self._subscriptions.values())
            self._subscriptions.clear()
        await asyncio.gather(*(subscription._close() for subscription in subscriptions))

    async def subscribe(
        self,
        pattern: str,
        handler: EventHandler,
        *,
        capacity: int = 256,
    ) -> LocalSubscription:
        self._validate_pattern(pattern)
        async with self._lock:
            if not self._started:
                raise RuntimeError("event bus is not started")
            subscription_id = self._next_subscription_id
            self._next_subscription_id += 1
            subscription = LocalSubscription(self, subscription_id, pattern, handler, capacity)
            self._subscriptions[subscription_id] = subscription
            return subscription

    async def publish(self, event: Event) -> PublishResult:
        async with self._lock:
            if not self._started:
                raise RuntimeError("event bus is not started")
            if self._is_expired(event):
                return PublishResult(0, 0, 0, 0, expired=True)
            if event.event_id in self._seen:
                return PublishResult(0, 0, 0, 0, duplicate=True)
            self._remember(event.event_id)
            subscriptions = [
                subscription
                for subscription in self._subscriptions.values()
                if subscription.matches(event.type)
            ]
            enqueued = 0
            rejected = 0
            evicted = 0
            for subscription in subscriptions:
                outcome = subscription.enqueue(event)
                if outcome is _EnqueueOutcome.REJECTED:
                    rejected += 1
                else:
                    enqueued += 1
                    if outcome is _EnqueueOutcome.EVICTED:
                        evicted += 1
            return PublishResult(len(subscriptions), enqueued, rejected, evicted)

    async def _unsubscribe(self, subscription_id: int) -> None:
        async with self._lock:
            subscription = self._subscriptions.pop(subscription_id, None)
        if subscription is not None:
            await subscription._close()

    def snapshot(self) -> BusSnapshot:
        subscriptions = list(self._subscriptions.values())
        return BusSnapshot(
            started=self._started,
            subscriptions=len(subscriptions),
            worker_tasks=sum(subscription.worker_running for subscription in subscriptions),
            total_pending=sum(subscription.pending for subscription in subscriptions),
            dedup_entries=len(self._seen),
        )

    def _is_expired(self, event: Event) -> bool:
        if event.ttl_ms is None:
            return False
        expires_at = event.received_at + timedelta(milliseconds=event.ttl_ms)
        return self._clock.now() >= expires_at

    def _remember(self, event_id: object) -> None:
        if len(self._seen_order) >= self._dedup_capacity:
            oldest = self._seen_order.popleft()
            self._seen.remove(oldest)
        self._seen_order.append(event_id)
        self._seen.add(event_id)

    @staticmethod
    def _validate_pattern(pattern: str) -> None:
        if not pattern or pattern == "*":
            raise ValueError("pattern must be an exact type or a namespaced prefix ending in .* ")
        if "*" in pattern and not pattern.endswith(".*"):
            raise ValueError("wildcard is only allowed as a final .* suffix")
