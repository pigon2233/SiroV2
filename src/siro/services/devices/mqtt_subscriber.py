"""Optional MQTT subscriber that projects ESP32 sensor state into the device registry."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import aiomqtt

from siro.contracts.events import Privacy
from siro.core.devices import (
    DeviceAvailability,
    DeviceDescriptor,
    DeviceProperty,
    DeviceRegistry,
)
from siro.services.devices.mqtt import MqttStateProjector

_LOGGER = logging.getLogger(__name__)
_TTL_MS = 20_000


def mqtt_sensor_descriptor(device_id: str, *, location: str | None = None) -> DeviceDescriptor:
    return DeviceDescriptor(
        device_id=device_id,
        adapter="esp32_mqtt",
        location=location,
        properties={
            "motion": DeviceProperty(type="boolean"),
            "illuminance": DeviceProperty(type="number", unit="lx"),
            "button_down": DeviceProperty(type="boolean"),
            "button_press_count": DeviceProperty(type="number"),
        },
        actions={},
        availability_ttl_ms=_TTL_MS,
        privacy=Privacy.LOCAL_ONLY,
    )


class Esp32MqttSubscriber:
    """Subscribes to one device's state and availability topics; reconnects with backoff."""

    def __init__(
        self,
        registry: DeviceRegistry,
        *,
        host: str,
        port: int,
        device_id: str,
        username: str | None = None,
        password: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_backoff: float = 30.0,
    ) -> None:
        self._registry = registry
        self._projector = MqttStateProjector(registry)
        self._host = host
        self._port = port
        self._device_id = device_id
        self._username = username
        self._password = password
        self._clock = clock
        self._max_backoff = max_backoff
        self._task: asyncio.Task[None] | None = None
        self.connected = asyncio.Event()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _run(self) -> None:
        delay = 1.0
        while True:
            try:
                async with aiomqtt.Client(
                    self._host, self._port, username=self._username, password=self._password
                ) as client:
                    prefix = f"siro/devices/{self._device_id}/"
                    await client.subscribe([(prefix + "state", 1), (prefix + "availability", 1)])
                    self.connected.set()
                    delay = 1.0
                    async for message in client.messages:
                        await self._handle(
                            str(message.topic),
                            bytes(message.payload),
                            retained=message.retain,
                        )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                _LOGGER.warning("ESP32 MQTT subscriber disconnected: %s", type(error).__name__)
            self.connected.clear()
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._max_backoff)

    async def _handle(self, topic: str, payload: bytes, *, retained: bool = False) -> None:
        kind = topic.rsplit("/", 1)[-1]
        now = self._clock()
        try:
            if kind == "state":
                if retained:  # Replayed state may be stale; the node republishes every 10 s.
                    return
                await self._projector.handle_state(self._device_id, payload)
            elif kind == "availability":
                text = payload.decode("utf-8", "replace")
                if text == "online":
                    availability = DeviceAvailability.ONLINE
                elif text == "offline":
                    availability = DeviceAvailability.OFFLINE
                else:
                    return
                await self._registry.set_availability(
                    self._device_id, availability, observed_at=now
                )
        except (ValueError, KeyError) as error:
            _LOGGER.warning("ESP32 MQTT message rejected: %s", type(error).__name__)


__all__ = ["Esp32MqttSubscriber", "mqtt_sensor_descriptor"]
