#!/usr/bin/env python3
"""Send one authorized LED command and require applied ack plus fresh MQTT readback."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import aiomqtt

from siro.contracts.events import Privacy
from siro.core.devices import DeviceAction, DeviceDescriptor, DeviceProperty, DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository
from siro.services.devices.mqtt import (
    CommandTracker,
    DeliveryState,
    DeviceCommand,
    MqttStateProjector,
    command_message,
)


class ProbeFailure(RuntimeError):
    def __init__(self, report: dict[str, object]) -> None:
        super().__init__(str(report["reason"]))
        self.report = report


def state_observed_at(parsed: dict[str, object]) -> datetime:
    """Check wire time before projection; the real projector still consumes the payload."""

    iso_time = parsed.get("observed_at")
    epoch = parsed.get("observed_at_epoch")
    if "observed_at" in parsed:
        if not isinstance(iso_time, str):
            raise ValueError("ISO observation time must be a string")
        observed_at = datetime.fromisoformat(iso_time)
    elif isinstance(epoch, (int, float)) and not isinstance(epoch, bool):
        observed_at = datetime.fromtimestamp(epoch, tz=UTC)
    else:
        raise ValueError("missing observation time")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observation time needs timezone")
    return observed_at


async def verify(
    *,
    host: str = "127.0.0.1",
    port: int = 1883,
    device_id: str = "esp32-lab-01",
    timeout: float = 3.0,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, object]:
    """One publish, bounded wait, no retry, and no access to the product database."""

    if not re.fullmatch(r"[a-zA-Z0-9._:-]{1,128}", device_id):
        raise ValueError("invalid device id")
    if not math.isfinite(timeout) or not 0.1 <= timeout <= 60:
        raise ValueError("timeout must be between 0.1 and 60 seconds")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    host = "127.0.0.1" if host == "0.0.0.0" else host
    prefix = f"siro/devices/{device_id}"
    command_id = f"verify-{uuid4()}"
    tracker = CommandTracker()
    ignored_messages = 0
    latest_state_at: datetime | None = None
    latest_state_power: bool | None = None
    state_ambiguous = False
    report: dict[str, object] = {
        "result": "unknown",
        "device_id": device_id,
        "command_id": command_id,
        "command_topic": f"{prefix}/command",
        "publish_attempts": 0,
        "ack_applied": False,
        "state_power": None,
        "state_ambiguous": False,
        "delivery_state": DeliveryState.PENDING.value,
        "ignored_messages": 0,
        "hardware_verified": False,
    }
    with tempfile.TemporaryDirectory(prefix="siro-esp32-mqtt-") as temporary:
        store = SQLiteStore(Path(temporary) / "probe.sqlite3")
        await store.initialize()
        world = WorldModel(SQLiteWorldRepository(store))
        registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
        await registry.register(
            DeviceDescriptor(
                device_id=device_id,
                adapter="esp32_mqtt",
                properties={"power": DeviceProperty(type="boolean")},
                actions={"light.set": DeviceAction(input_schema="light_set.v1")},
                availability_ttl_ms=60_000,
                privacy=Privacy.TRUSTED_LAN,
            )
        )
        projector = MqttStateProjector(registry)
        try:
            async with asyncio.timeout(timeout):
                async with aiomqtt.Client(
                    host,
                    port,
                    username=username,
                    password=password,
                    timeout=timeout,
                    max_queued_incoming_messages=32,
                ) as client:
                    await client.subscribe([(f"{prefix}/ack", 1), (f"{prefix}/state", 1)])
                    issued_at = datetime.now(UTC)
                    command = DeviceCommand(
                        command_id=command_id,
                        action="light.set",
                        desired_state={"power": True},
                        expires_at=issued_at + timedelta(seconds=timeout),
                    )
                    tracker.issue(device_id, command)
                    payload, retained = command_message(command)
                    report["publish_attempts"] = 1
                    await client.publish(f"{prefix}/command", payload, qos=1, retain=retained)
                    async for message in client.messages:
                        try:
                            if message.retain or len(message.payload) > 4096:
                                raise ValueError("retained or oversized response")
                            parsed = json.loads(message.payload)
                            if not isinstance(parsed, dict):
                                raise ValueError("response must be an object")
                            topic = str(message.topic)
                            if topic == f"{prefix}/ack":
                                if parsed.get("command_id") != command_id:
                                    raise ValueError("ack belongs to another command")
                                status = parsed.get("status")
                                if not isinstance(status, str):
                                    raise ValueError("ack status must be a string")
                                delivery = tracker.acknowledge(command_id, status=status)
                                if delivery is not None:
                                    report["delivery_state"] = delivery.value
                                if (
                                    status == "duplicate"
                                    and report["ack_applied"]
                                    and delivery is DeliveryState.ACKNOWLEDGED
                                ):
                                    continue
                                if status != "applied":
                                    report["reason"] = "device_did_not_apply_command"
                                    raise ProbeFailure(report)
                                if not report["ack_applied"]:
                                    report["ack_applied"] = True
                            elif topic == f"{prefix}/state":
                                observed_at = state_observed_at(parsed)
                                # Firmware epoch values have one-second resolution.
                                if not (
                                    issued_at.replace(microsecond=0)
                                    <= observed_at
                                    <= min(
                                        datetime.now(UTC) + timedelta(seconds=1),
                                        command.expires_at,
                                    )
                                ):
                                    raise ValueError("state is stale or from the future")
                                properties = parsed.get("properties")
                                if (
                                    not isinstance(properties, dict)
                                    or set(properties) != {"power"}
                                    or not isinstance(properties.get("power"), bool)
                                ):
                                    raise ValueError("power must be a boolean")
                                power = properties["power"]
                                if latest_state_at is not None and observed_at < latest_state_at:
                                    raise ValueError("state is older than the latest readback")
                                if observed_at == latest_state_at:
                                    if power is not latest_state_power:
                                        state_ambiguous = True
                                else:
                                    state_ambiguous = False
                                latest_state_at = observed_at
                                latest_state_power = power
                                report["state_power"] = power
                                report["state_ambiguous"] = state_ambiguous
                                report["observed_at"] = observed_at.isoformat()
                                await projector.handle_state(device_id, message.payload)
                            else:
                                raise ValueError("unrelated topic")
                        except (ValueError, OverflowError, OSError):
                            ignored_messages += 1
                            report["ignored_messages"] = ignored_messages
                            continue
                        report["delivery_state"] = tracker.state(command_id).value
                        current = await world.current(device_id, "power", now=datetime.now(UTC))
                        if current.status is WorldStatus.KNOWN and current.observation is not None:
                            report["source_id"] = current.observation.source_id
                            if (
                                report["ack_applied"]
                                and not state_ambiguous
                                and latest_state_power is True
                                and current.observation.value is True
                                and current.observation.observed_at == latest_state_at
                            ):
                                tracker.observe_state(device_id, {"power": True})
                                report["delivery_state"] = tracker.state(command_id).value
                                if tracker.state(command_id) is DeliveryState.CONFIRMED:
                                    report["result"] = "confirmed"
                                    return report
        except TimeoutError:
            report["reason"] = "timeout_unknown_do_not_retry_automatically"
            raise ProbeFailure(report) from None
        except aiomqtt.MqttError:
            report["reason"] = "mqtt_error_unknown_do_not_retry_automatically"
            raise ProbeFailure(report) from None
    report["reason"] = "connection_ended_without_confirmation"
    raise ProbeFailure(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--device-id", default="esp32-lab-01")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    try:
        report = asyncio.run(
            verify(
                host=args.host,
                port=args.port,
                device_id=args.device_id,
                timeout=args.timeout,
                username=os.environ.get("SIRO_MQTT_USERNAME"),
                password=os.environ.get("SIRO_MQTT_PASSWORD"),
            )
        )
    except ValueError as error:
        parser.error(str(error))
    except ProbeFailure as error:
        print(json.dumps(error.report, ensure_ascii=False, indent=2))
        return 1
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
