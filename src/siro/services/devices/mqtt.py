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
    FAILED = "failed"


class CommandTracker:
    def __init__(self, *, max_commands: int = 1024) -> None:
        if type(max_commands) is not int or not 1 <= max_commands <= 10000:
            raise ValueError("command capacity must be between 1 and 10000")
        self._max_commands = max_commands
        self._commands: dict[str, tuple[str, dict[str, object], DeliveryState, datetime]] = {}

    def issue(self, device_id: str, command: DeviceCommand) -> None:
        if command.command_id in self._commands:
            raise ValueError("command id already exists")
        self.prune()
        if len(self._commands) >= self._max_commands:
            raise ValueError("command tracker capacity reached")
        self._commands[command.command_id] = (
            device_id,
            command.desired_state,
            DeliveryState.PENDING,
            command.expires_at,
        )

    def acknowledge(self, command_id: str, status: str = "applied") -> DeliveryState | None:
        command = self._commands.get(command_id)
        if command is None:
            return None
        device_id, desired, state, expires_at = command
        if state is not DeliveryState.PENDING:
            return state
        state = DeliveryState.ACKNOWLEDGED if status == "applied" else DeliveryState.FAILED
        self._commands[command_id] = (device_id, desired, state, expires_at)
        return state

    def observe_state(self, device_id: str, properties: dict[str, object]) -> tuple[str, ...]:
        confirmed: list[str] = []
        for command_id, (target, desired, state, expires_at) in tuple(self._commands.items()):
            if target != device_id or state is not DeliveryState.ACKNOWLEDGED:
                continue
            if all(properties.get(name) == value for name, value in desired.items()):
                self._commands[command_id] = (target, desired, DeliveryState.CONFIRMED, expires_at)
                confirmed.append(command_id)
        return tuple(confirmed)

    def state(self, command_id: str) -> DeliveryState:
        return self._commands[command_id][2]

    def prune(self, *, now: datetime | None = None) -> int:
        """Reclaim terminal/expired RAM entries; delivery history belongs to the caller."""
        observed_at = now or datetime.now(UTC)
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("prune time must include a timezone")
        stale = [
            identifier
            for identifier, (_, _, state, expires_at) in self._commands.items()
            if state in {DeliveryState.CONFIRMED, DeliveryState.FAILED} or expires_at <= observed_at
        ]
        for identifier in stale:
            del self._commands[identifier]
        return len(stale)


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
