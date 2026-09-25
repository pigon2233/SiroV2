"""Ports for event publication and isolated subscriptions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from siro.contracts.events import Event

EventHandler = Callable[[Event], Awaitable[None]]


class Clock(Protocol):
    """Wall clock port used only for TTL and externally meaningful time."""

    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class DeliveryStats:
    delivered: int
    rejected: int
    evicted: int
    handler_failures: int
    pending: int
    capacity: int


@dataclass(frozen=True, slots=True)
class PublishResult:
    matched: int
    enqueued: int
    rejected: int
    evicted: int
    duplicate: bool = False
    expired: bool = False


@dataclass(frozen=True, slots=True)
class BusSnapshot:
    started: bool
    subscriptions: int
    worker_tasks: int
    total_pending: int
    dedup_entries: int


class Subscription(Protocol):
    @property
    def subscription_id(self) -> int: ...

    @property
    def pattern(self) -> str: ...

    def stats(self) -> DeliveryStats: ...

    async def unsubscribe(self) -> None: ...


class EventBus(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def publish(self, event: Event) -> PublishResult: ...

    async def subscribe(
        self,
        pattern: str,
        handler: EventHandler,
        *,
        capacity: int = 256,
    ) -> Subscription: ...

    def snapshot(self) -> BusSnapshot: ...
