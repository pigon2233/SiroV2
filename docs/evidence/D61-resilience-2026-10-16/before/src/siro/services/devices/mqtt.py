"""MQTT device command validation and state projection."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from siro.adapters.devices import SimulatedLight
from siro.core.devices import DeviceRegistry


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeviceCommand(StrictModel):
    command_id: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=128)
    desired_state: dict[str, object]
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("command expiry must include a timezone")
        return value


class CommandResult(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    EXPIRED = "expired"
    RETAINED_REJECTED = "retained_rejected"
    UNSUPPORTED = "unsupported"


class DeliveryState(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    CONFIRMED = "confirmed"


class CommandTracker:
    def __init__(self) -> None:
        self._commands: dict[str, tuple[str, dict[str, object], DeliveryState]] = {}

    def issue(self, device_id: str, command: DeviceCommand) -> None:
        if command.command_id in self._commands:
            raise ValueError("command id already exists")
        self._commands[command.command_id] = (
            device_id,
            command.desired_state,
            DeliveryState.PENDING,
        )

    def acknowledge(self, command_id: str) -> DeliveryState:
        device_id, desired, _ = self._commands[command_id]
        self._commands[command_id] = (device_id, desired, DeliveryState.ACKNOWLEDGED)
        return DeliveryState.ACKNOWLEDGED

    def observe_state(self, device_id: str, properties: dict[str, object]) -> tuple[str, ...]:
        confirmed: list[str] = []
        for command_id, (target, desired, state) in tuple(self._commands.items()):
            if target != device_id or state is DeliveryState.CONFIRMED:
                continue
            if all(properties.get(name) == value for name, value in desired.items()):
                self._commands[command_id] = (target, desired, DeliveryState.CONFIRMED)
                confirmed.append(command_id)
        return tuple(confirmed)

    def state(self, command_id: str) -> DeliveryState:
        return self._commands[command_id][2]


class MqttLightCommandProcessor:
    def __init__(self, light: SimulatedLight) -> None:
        self._light = light
        self._seen: set[str] = set()

    def handle(self, payload: bytes, *, retained: bool, now: datetime) -> CommandResult:
        if retained:
            return CommandResult.RETAINED_REJECTED
        parsed = json.loads(payload)
        has_epoch = isinstance(parsed, dict) and "expires_at_epoch" in parsed
        epoch = parsed.pop("expires_at_epoch") if has_epoch else None
        command = DeviceCommand.model_validate(parsed)
        if has_epoch and (type(epoch) is not int or epoch != int(command.expires_at.timestamp())):
            raise ValueError("command expiry epoch must match expires_at")
        if now >= command.expires_at:
            return CommandResult.EXPIRED
        if command.command_id in self._seen:
            return CommandResult.DUPLICATE
        if command.action != "light.set" or not isinstance(
            command.desired_state.get("power"), bool
        ):
            return CommandResult.UNSUPPORTED
        self._light.set_power(command.command_id, bool(command.desired_state["power"]))
        self._seen.add(command.command_id)
        return CommandResult.ACCEPTED


class MqttStateProjector:
    def __init__(self, registry: DeviceRegistry) -> None:
        self._registry = registry

    async def handle_state(self, device_id: str, payload: bytes) -> None:
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("invalid MQTT state payload")
        properties = parsed.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("invalid MQTT state properties")
        if "observed_at" in parsed:
            if not isinstance(parsed["observed_at"], str):
                raise ValueError("invalid MQTT state timestamp")
            observed_at = datetime.fromisoformat(parsed["observed_at"])
        elif type(parsed.get("observed_at_epoch")) in (int, float):
            try:
                observed_at = datetime.fromtimestamp(parsed["observed_at_epoch"], tz=UTC)
            except (ValueError, OverflowError, OSError) as error:
                raise ValueError("invalid MQTT state timestamp") from error
        else:
            raise ValueError("invalid MQTT state timestamp")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("MQTT state timestamp must include a timezone")
        for name, value in properties.items():
            await self._registry.record_property(
                device_id, str(name), value, observed_at=observed_at
            )


def command_message(command: DeviceCommand) -> tuple[bytes, bool]:
    """Commands are never retained; callers must preserve the returned retain flag."""

    payload = command.model_dump(mode="json")
    payload["expires_at_epoch"] = int(command.expires_at.timestamp())
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(), False
