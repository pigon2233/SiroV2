from __future__ import annotations

import asyncio
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiomqtt
import pytest
from amqtt.broker import Broker  # type: ignore[import-untyped]
from argon2 import PasswordHasher

from siro.adapters.devices import SimulatedLight
from siro.services.devices.mqtt import (
    CommandResult,
    CommandTracker,
    DeliveryState,
    DeviceCommand,
    MqttLightCommandProcessor,
    command_message,
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_t27_ack_is_not_success_until_matching_state_readback() -> None:
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    command = DeviceCommand(
        command_id="command-readback",
        action="light.set",
        desired_state={"power": True},
        expires_at=now + timedelta(seconds=3),
    )
    tracker = CommandTracker()
    tracker.issue("light-01", command)
    assert tracker.acknowledge(command.command_id) is DeliveryState.ACKNOWLEDGED
    assert tracker.state(command.command_id) is DeliveryState.ACKNOWLEDGED
    assert tracker.observe_state("light-01", {"power": False}) == ()
    assert tracker.state(command.command_id) is DeliveryState.ACKNOWLEDGED
    assert tracker.observe_state("light-01", {"power": True}) == (command.command_id,)
    assert tracker.state(command.command_id) is DeliveryState.CONFIRMED


@pytest.mark.asyncio
async def test_t27_authenticated_broker_lwt_retained_expired_and_duplicate_commands(
    tmp_path: Path,
) -> None:
    port = free_port()
    username, password = "siro-device", "fixture-password"  # pragma: allowlist secret
    password_file = tmp_path / "passwords"
    password_file.write_text(f"{username}:{PasswordHasher().hash(password)}\n")
    broker = Broker(
        {
            "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
            "plugins": {
                "amqtt.plugins.authentication.FileAuthPlugin": {"password_file": str(password_file)}
            },
        }
    )
    await broker.start()
    try:
        with pytest.raises(aiomqtt.MqttError):
            async with aiomqtt.Client(
                "127.0.0.1",
                port,
                username=username,
                password="wrong",  # pragma: allowlist secret
                timeout=1,
            ):
                pass

        availability = "siro/devices/light-01/availability"
        command_topic = "siro/devices/light-01/command"
        async with aiomqtt.Client(
            "127.0.0.1", port, username=username, password=password
        ) as observer:
            await observer.subscribe([(availability, 1), (command_topic, 1)])
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "tests/helpers/mqtt_crash_client.py",
                "127.0.0.1",
                str(port),
                username,
                password,
                availability,
                stdout=asyncio.subprocess.PIPE,
            )
            assert child.stdout is not None
            assert await asyncio.wait_for(child.stdout.readline(), 3) == b"ready\n"
            child.terminate()
            await child.wait()
            lwt = await asyncio.wait_for(observer.messages.__anext__(), 3)
            assert str(lwt.topic) == availability and bytes(lwt.payload) == b"offline"

            light = SimulatedLight("light-01", "esp32_sim", "lab")
            processor = MqttLightCommandProcessor(light)
            now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
            command = DeviceCommand(
                command_id="command-1",
                action="light.set",
                desired_state={"power": True},
                expires_at=now + timedelta(seconds=3),
            )
            payload, retain = command_message(command)
            assert retain is False
            await observer.publish(command_topic, payload, qos=1, retain=True)

        async with aiomqtt.Client(
            "127.0.0.1", port, username=username, password=password
        ) as device:
            await device.subscribe(command_topic, qos=1)
            retained = await asyncio.wait_for(device.messages.__anext__(), 3)
            assert retained.retain is True
            assert (
                processor.handle(bytes(retained.payload), retained=True, now=now)
                is CommandResult.RETAINED_REJECTED
            )
            await device.publish(command_topic, b"", qos=1, retain=True)
            await device.publish(command_topic, payload, qos=1, retain=False)
            live = await asyncio.wait_for(device.messages.__anext__(), 3)
            if not live.payload:
                live = await asyncio.wait_for(device.messages.__anext__(), 3)
            assert (
                processor.handle(bytes(live.payload), retained=False, now=now)
                is CommandResult.ACCEPTED
            )
            assert light.power is True
            assert processor.handle(payload, retained=False, now=now) is CommandResult.DUPLICATE
            expired = command.model_copy(
                update={"command_id": "expired", "expires_at": now - timedelta(seconds=1)}
            )
            assert (
                processor.handle(expired.model_dump_json().encode(), retained=False, now=now)
                is CommandResult.EXPIRED
            )
    finally:
        await broker.shutdown()
