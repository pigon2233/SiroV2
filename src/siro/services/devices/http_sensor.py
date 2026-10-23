"""Validate the existing ESP32 HTTP events before projecting local observations.

This service is transport-neutral: an authenticated gateway route may call it,
but the standalone Windows receiver does not call it yet.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from siro.contracts.events import Privacy
from siro.core.devices import DeviceDescriptor, DeviceProperty, DeviceRegistry
from siro.core.world import WorldModel, WorldStatus

_EVENTS = {"light_update", "motion_detected", "motion_cleared", "button_pressed"}
_MAX_LUX = 65535 / 1.2


def http_sensor_descriptor(device_id: str, *, location: str | None = None) -> DeviceDescriptor:
    return DeviceDescriptor(
        device_id=device_id,
        adapter="esp32_http",
        location=location,
        properties={
            "motion": DeviceProperty(type="boolean"),
            "illuminance": DeviceProperty(type="number", unit="lx"),
            "last_button_press_at": DeviceProperty(type="string"),
        },
        actions={},
        availability_ttl_ms=20_000,
        privacy=Privacy.LOCAL_ONLY,
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def parse_http_sensor_event(payload: bytes, *, device_id: str) -> tuple[str, float | None]:
    if not payload or len(payload) > 4096:
        raise ValueError("sensor payload size is invalid")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid sensor JSON") from error
    if not isinstance(parsed, dict) or parsed.get("device") != device_id:
        raise ValueError("unknown sensor device")
    event = parsed.get("event")
    if not isinstance(event, str) or event not in _EVENTS:
        raise ValueError("unknown sensor event")
    expected = {"device", "event", "lux"} if event == "light_update" else {"device", "event"}
    if set(parsed) != expected:
        raise ValueError("unexpected or missing sensor fields")
    if event != "light_update":
        return event, None
    lux = parsed["lux"]
    if type(lux) not in (int, float):
        raise ValueError("invalid illuminance")
    try:
        measured = float(lux)
    except OverflowError as error:
        raise ValueError("invalid illuminance") from error
    if not math.isfinite(measured) or not 0 <= measured <= _MAX_LUX:
        raise ValueError("invalid illuminance")
    return event, measured


class Esp32HttpSensorProjector:
    def __init__(self, registry: DeviceRegistry, *, device_id: str) -> None:
        self._registry = registry
        self._device_id = device_id

    async def handle(self, payload: bytes, *, now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("sensor observation time must include a timezone")
        event, lux = parse_http_sensor_event(payload, device_id=self._device_id)
        if event == "light_update":
            assert lux is not None
            await self._registry.record_property(
                self._device_id, "illuminance", lux, observed_at=now
            )
        elif event in {"motion_detected", "motion_cleared"}:
            await self._registry.record_property(
                self._device_id, "motion", event == "motion_detected", observed_at=now
            )
        else:
            await self._registry.record_property(
                self._device_id, "last_button_press_at", now.isoformat(), observed_at=now
            )


async def http_sensor_state_snapshot(
    world: WorldModel, *, device_id: str, now: datetime
) -> dict[str, Any]:
    properties: dict[str, dict[str, object]] = {}
    for name in ("illuminance", "motion", "last_button_press_at"):
        current = await world.current(device_id, name, now=now)
        if current.status is WorldStatus.KNOWN and current.observation is not None:
            properties[name] = {
                "status": "known",
                "value": current.observation.value,
                "observed_at": current.observation.observed_at.isoformat(),
                "source_id": current.observation.source_id,
            }
        else:
            properties[name] = {"status": "unknown", "value": None}
    return {"device_id": device_id, "properties": properties}
