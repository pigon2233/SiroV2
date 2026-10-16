"""Exercise the real aiomqtt CLI against an isolated broker and synthetic firmware peer."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import tempfile
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiomqtt
import pytest
import pytest_asyncio
from amqtt.broker import Broker  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "siro/devices/esp32-lab-01"


@pytest_asyncio.fixture
async def mqtt_port() -> AsyncIterator[int]:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
    broker = Broker(
        {
            "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
            "plugins": {
                "amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True}
            },
        }
    )
    await broker.start()
    try:
        yield port
    finally:
        await broker.shutdown()


async def run_probe(port: int, timeout: float = 0.8) -> tuple[int, dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="siro-mqtt-probe-test-") as temporary:
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            str(ROOT / "scripts/verify_esp32_mqtt.py"),
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--timeout",
            str(timeout),
            cwd=ROOT,
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if key not in {"SIRO_MQTT_USERNAME", "SIRO_MQTT_PASSWORD"}
                },
                "TMPDIR": temporary,
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(child.communicate(), timeout + 10)
            assert not stderr, stderr.decode()
            parsed = json.loads(stdout)
            assert isinstance(parsed, dict)
            assert child.returncode is not None
            assert not tuple(Path(temporary).iterdir()), "probe must clean its temporary database"
            return child.returncode, parsed
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()


@pytest.mark.asyncio
@pytest.mark.parametrize("state_first", [False, True])
@pytest.mark.parametrize("epoch_time", [False, True])
async def test_probe_confirms_only_applied_ack_plus_fresh_state(
    mqtt_port: int, state_first: bool, epoch_time: bool
) -> None:
    commands: list[dict[str, object]] = []
    async with aiomqtt.Client("127.0.0.1", mqtt_port) as peer:
        await peer.subscribe(f"{PREFIX}/command", qos=1)
        # A broker's retained snapshot must never satisfy the readback requirement.
        await peer.publish(
            f"{PREFIX}/state",
            json.dumps(
                {
                    "observed_at_epoch": int(datetime.now(UTC).timestamp()),
                    "properties": {"power": True},
                }
            ),
            qos=1,
            retain=True,
        )

        async def firmware() -> None:
            async for message in peer.messages:
                assert str(message.topic) == f"{PREFIX}/command"
                assert not message.retain
                command = json.loads(message.payload)
                commands.append(command)
                assert command["action"] == "light.set"
                assert command["desired_state"] == {"power": True}
                assert command["expires_at_epoch"] == int(
                    datetime.fromisoformat(command["expires_at"]).timestamp()
                )
                now = datetime.now(UTC)
                state: dict[str, object] = (
                    {"observed_at_epoch": now.timestamp()}
                    if epoch_time
                    else {"observed_at": now.isoformat()}
                )
                state["properties"] = {"power": True}
                ack = {"command_id": command["command_id"], "status": "applied"}
                responses = [("state", state), ("ack", ack)]
                if not state_first:
                    responses.reverse()
                for suffix, response in responses:
                    await peer.publish(f"{PREFIX}/{suffix}", json.dumps(response), qos=1)

        task = asyncio.create_task(firmware())
        try:
            status, report = await run_probe(mqtt_port, timeout=2)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    assert status == 0
    assert report["result"] == "confirmed"
    assert report["delivery_state"] == "confirmed"
    assert report["ack_applied"] is True
    assert report["state_power"] is True
    assert report["source_id"] == "device:esp32-lab-01:esp32_mqtt"
    assert report["hardware_verified"] is False
    assert report["publish_attempts"] == len(commands) == 1
    assert isinstance(report["ignored_messages"], int) and report["ignored_messages"] >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("statuses", "expected_delivery"),
    [
        (("applied", "duplicate"), "confirmed"),
        (("duplicate",), "failed"),
        (("applied", "unsupported"), "acknowledged"),
        (("applied", "expired_or_invalid"), "acknowledged"),
    ],
)
async def test_probe_duplicate_ack_only_preserves_prior_applied_evidence(
    mqtt_port: int, statuses: tuple[str, ...], expected_delivery: str
) -> None:
    command_count = 0
    async with aiomqtt.Client("127.0.0.1", mqtt_port) as peer:
        await peer.subscribe(f"{PREFIX}/command", qos=1)

        async def firmware() -> None:
            nonlocal command_count
            async for message in peer.messages:
                command_count += 1
                command = json.loads(message.payload)
                for status in statuses:
                    await peer.publish(
                        f"{PREFIX}/ack",
                        json.dumps({"command_id": command["command_id"], "status": status}),
                        qos=1,
                    )
                await peer.publish(
                    f"{PREFIX}/state",
                    json.dumps(
                        {
                            "observed_at_epoch": datetime.now(UTC).timestamp(),
                            "properties": {"power": True},
                        }
                    ),
                    qos=1,
                )

        task = asyncio.create_task(firmware())
        try:
            status, report = await run_probe(mqtt_port, timeout=2)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    assert report["publish_attempts"] == command_count == 1
    assert report["delivery_state"] == expected_delivery
    assert report["ack_applied"] is (statuses[0] == "applied")
    assert report["hardware_verified"] is False
    if expected_delivery == "confirmed":
        assert status == 0
        assert report["result"] == "confirmed"
        assert report["state_power"] is True
    else:
        assert status == 1
        assert report["result"] == "unknown"
        assert report["reason"] == "device_did_not_apply_command"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "ack_only",
        "state_only",
        "wrong_ack",
        "rejected_ack",
        "retained_only",
        "stale_state",
        "future_state",
        "nonboolean_power",
        "invalid_epoch",
        "wrong_state_topic",
        "extra_property_then_ack",
        "invalid_iso_with_valid_epoch",
    ],
)
async def test_probe_does_not_confirm_unsafe_or_incomplete_responses(
    mqtt_port: int, scenario: str
) -> None:
    command_count = 0
    async with aiomqtt.Client("127.0.0.1", mqtt_port) as peer:
        await peer.subscribe(f"{PREFIX}/command", qos=1)
        if scenario == "retained_only":
            await peer.publish(
                f"{PREFIX}/state",
                json.dumps(
                    {
                        "observed_at_epoch": int(datetime.now(UTC).timestamp()),
                        "properties": {"power": True},
                    }
                ),
                qos=1,
                retain=True,
            )

        async def firmware() -> None:
            nonlocal command_count
            async for message in peer.messages:
                command_count += 1
                command = json.loads(message.payload)
                if scenario == "extra_property_then_ack":
                    await peer.publish(
                        f"{PREFIX}/state",
                        json.dumps(
                            {
                                "observed_at_epoch": datetime.now(UTC).timestamp(),
                                "properties": {"power": True, "undeclared_property": True},
                            }
                        ),
                        qos=1,
                    )
                    await peer.publish(
                        f"{PREFIX}/ack",
                        json.dumps({"command_id": command["command_id"], "status": "applied"}),
                        qos=1,
                    )
                    continue
                ack_id = "other-command" if scenario == "wrong_ack" else command["command_id"]
                if scenario != "state_only":
                    await peer.publish(
                        f"{PREFIX}/ack",
                        json.dumps(
                            {
                                "command_id": ack_id,
                                "status": "unsupported"
                                if scenario == "rejected_ack"
                                else "applied",
                            }
                        ),
                        qos=1,
                    )
                if scenario in {"ack_only", "retained_only"}:
                    continue
                now = datetime.now(UTC)
                if scenario == "stale_state":
                    now -= timedelta(seconds=30)
                elif scenario == "future_state":
                    now += timedelta(seconds=30)
                epoch: object = True if scenario == "invalid_epoch" else now.timestamp()
                power: object = 1 if scenario == "nonboolean_power" else True
                topic = f"{PREFIX}/state"
                if scenario == "wrong_state_topic":
                    topic = "siro/devices/another-device/state"
                state: dict[str, object] = {
                    "observed_at_epoch": epoch,
                    "properties": {"power": power},
                }
                if scenario == "invalid_iso_with_valid_epoch":
                    state["observed_at"] = None
                await peer.publish(
                    topic,
                    json.dumps(state),
                    qos=1,
                )

        task = asyncio.create_task(firmware())
        try:
            status, report = await run_probe(mqtt_port)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    assert status == 1
    assert report["result"] == "unknown"
    assert report["delivery_state"] != "confirmed"
    if scenario == "ack_only":
        assert report["delivery_state"] == "acknowledged"
    elif scenario == "rejected_ack":
        assert report["delivery_state"] == "failed"
    elif scenario == "state_only":
        assert report["delivery_state"] == "pending"
    assert report["publish_attempts"] == command_count == 1
    assert report["reason"] == (
        "device_did_not_apply_command"
        if scenario == "rejected_ack"
        else "timeout_unknown_do_not_retry_automatically"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "confirmed"),
    [
        ("same_epoch_true_false", False),
        ("same_epoch_false_true", False),
        ("newer_true", True),
        ("newer_true_clears_ambiguity", True),
        ("older_false_ignored", True),
    ],
)
async def test_probe_requires_unambiguous_latest_wire_state_and_matching_projection(
    mqtt_port: int, scenario: str, confirmed: bool
) -> None:
    command_count = 0
    async with aiomqtt.Client("127.0.0.1", mqtt_port) as peer:
        await peer.subscribe(f"{PREFIX}/command", qos=1)

        async def firmware() -> None:
            nonlocal command_count
            async for message in peer.messages:
                command_count += 1
                command = json.loads(message.payload)
                now = datetime.now(UTC).timestamp()
                epoch = int(now)
                states: list[tuple[int | float, bool]]
                if scenario == "same_epoch_true_false":
                    states = [(epoch, True), (epoch, False)]
                elif scenario == "same_epoch_false_true":
                    states = [(epoch, False), (epoch, True)]
                elif scenario == "newer_true":
                    states = [(epoch, False), (now + 0.01, True)]
                elif scenario == "newer_true_clears_ambiguity":
                    states = [(epoch, True), (epoch, False), (now + 0.01, True)]
                else:
                    states = [(now + 0.01, True), (epoch, False)]
                for observed_at, power in states:
                    await peer.publish(
                        f"{PREFIX}/state",
                        json.dumps(
                            {"observed_at_epoch": observed_at, "properties": {"power": power}}
                        ),
                        qos=1,
                    )
                await peer.publish(
                    f"{PREFIX}/ack",
                    json.dumps({"command_id": command["command_id"], "status": "applied"}),
                    qos=1,
                )

        task = asyncio.create_task(firmware())
        try:
            status, report = await run_probe(mqtt_port)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    assert report["publish_attempts"] == command_count == 1
    assert report["ack_applied"] is True
    if confirmed:
        assert status == 0
        assert report["result"] == report["delivery_state"] == "confirmed"
        assert report["state_ambiguous"] is False
        assert report["state_power"] is True
    else:
        assert status == 1
        assert report["result"] == "unknown"
        assert report["delivery_state"] == "acknowledged"
        assert report["state_ambiguous"] is True


@pytest.mark.asyncio
async def test_probe_missing_broker_is_nonzero_without_retry() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
        status, report = await run_probe(port)
    assert status == 1
    assert report["publish_attempts"] == 0
    assert report["result"] == "unknown"
    assert report["reason"] == "mqtt_error_unknown_do_not_retry_automatically"
