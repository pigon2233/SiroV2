"""Deterministic simulated device adapters for registry and transport development."""

from __future__ import annotations

from dataclasses import dataclass, field

from siro.contracts.events import Privacy
from siro.core.devices import DeviceAction, DeviceDescriptor, DeviceProperty
from siro.core.rooms import LightReadback, LightReadbackStatus


@dataclass(slots=True)
class SimulatedLight:
    device_id: str
    brand_adapter: str
    location: str | None
    power: bool = False
    _commands: dict[str, bool] = field(default_factory=dict)

    @property
    def descriptor(self) -> DeviceDescriptor:
        return DeviceDescriptor(
            device_id=self.device_id,
            adapter=self.brand_adapter,
            location=self.location,
            properties={"power": DeviceProperty(type="boolean")},
            actions={"light.set": DeviceAction(input_schema="light_set.v1")},
            events=("device.state_changed.v1",),
            availability_ttl_ms=30_000,
            privacy=Privacy.TRUSTED_LAN,
        )

    def set_power(self, command_id: str, desired: bool) -> bool:
        previous = self._commands.get(command_id)
        if previous is not None and previous != desired:
            raise ValueError("command id was reused with another desired state")
        if previous is None:
            self.power = desired
            self._commands[command_id] = desired
        return self.power


@dataclass(slots=True)
class SimulatedRoomLightActuator:
    """Readback-producing bridge for T29's deterministic room scenes."""

    light: SimulatedLight
    confirm_commands: bool = True

    async def set_power(self, action_id: str, device_id: str, desired: bool) -> LightReadback:
        if device_id != self.light.device_id:
            return LightReadback(LightReadbackStatus.UNAVAILABLE, None)
        observed = (
            self.light.set_power(action_id, desired) if self.confirm_commands else self.light.power
        )
        status = (
            LightReadbackStatus.CONFIRMED if observed == desired else LightReadbackStatus.MISMATCH
        )
        return LightReadback(status, observed)


@dataclass(frozen=True, slots=True)
class SimulatedSensor:
    device_id: str
    adapter: str
    property_name: str
    property_type: str
    location: str | None
    unit: str | None = None

    @property
    def descriptor(self) -> DeviceDescriptor:
        if self.property_type not in {"boolean", "number"}:
            raise ValueError("simulated sensor supports boolean or number")
        return DeviceDescriptor.model_validate(
            {
                "device_id": self.device_id,
                "adapter": self.adapter,
                "location": self.location,
                "properties": {
                    self.property_name: {
                        "type": self.property_type,
                        "readable": True,
                        "unit": self.unit,
                    }
                },
                "actions": {},
                "events": ["device.state_changed.v1"],
                "availability_ttl_ms": 30_000,
                "privacy": Privacy.TRUSTED_LAN,
            }
        )


@dataclass(slots=True)
class SimulatedCamera:
    device_id: str
    location: str | None
    owner_enabled: bool = False
    capture_count: int = 0

    @property
    def descriptor(self) -> DeviceDescriptor:
        return DeviceDescriptor(
            device_id=self.device_id,
            adapter="simulated_camera",
            location=self.location,
            properties={},
            actions={"camera.capture": DeviceAction(input_schema="camera_capture.v1")},
            events=(),
            availability_ttl_ms=30_000,
            privacy=Privacy.LOCAL_ONLY,
        )

    def capture(self) -> bytes:
        if not self.owner_enabled:
            raise PermissionError("camera capture requires owner enablement")
        self.capture_count += 1
        return b"simulated-on-demand-frame"
