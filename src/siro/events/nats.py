"""NATS JetStream adapter and SQLite outbox dispatcher."""

from __future__ import annotations

from dataclasses import dataclass

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.errors import NotFoundError

from siro.persistence.sqlite import SQLiteStore


class NatsJetStream:
    def __init__(self, url: str = "nats://127.0.0.1:4222") -> None:
        self._url = url
        self._client: NATS | None = None
        self._jetstream: JetStreamContext | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect(self) -> None:
        self._client = await nats.connect(
            self._url,
            connect_timeout=1,
            max_reconnect_attempts=2,
            reconnect_time_wait=0.1,
        )
        self._jetstream = self._client.jetstream()

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.close()
        self._client = None
        self._jetstream = None

    async def ensure_stream(self, name: str, subjects: list[str]) -> None:
        jetstream = self._required()
        try:
            await jetstream.stream_info(name)
        except NotFoundError:
            await jetstream.add_stream(name=name, subjects=subjects)

    async def publish(self, subject: str, payload: bytes) -> None:
        await self._required().publish(subject, payload)

    def jetstream(self) -> JetStreamContext:
        return self._required()

    def _required(self) -> JetStreamContext:
        if self._jetstream is None or not self.connected:
            raise ConnectionError("NATS JetStream is not connected")
        return self._jetstream


@dataclass(frozen=True, slots=True)
class DispatchReport:
    sent: int
    failed: int
    quarantined: int


class OutboxDispatcher:
    def __init__(
        self,
        store: SQLiteStore,
        broker: NatsJetStream,
        *,
        max_attempts: int = 5,
    ) -> None:
        self._store = store
        self._broker = broker
        self._max_attempts = max_attempts

    async def dispatch_once(self, *, limit: int = 100) -> DispatchReport:
        sent = failed = quarantined = 0
        for record in await self._store.pending_outbox(limit=limit):
            try:
                await self._broker.publish(record.subject, record.payload)
            except Exception as exception:
                failed += 1
                state = await self._store.mark_outbox_failed(
                    record.event_id,
                    type(exception).__name__,
                    max_attempts=self._max_attempts,
                )
                if state == "quarantined":
                    quarantined += 1
            else:
                if await self._store.mark_outbox_sent(record.event_id):
                    sent += 1
        return DispatchReport(sent, failed, quarantined)
