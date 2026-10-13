"""Conservative room automation with traceable, readback-confirmed light control."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from siro.config import RoomAutomationSettings
from siro.core.authorization import (
    AuthorizationRequest,
    AuthorizationService,
    PermissionDecision,
)
from siro.core.devices import DeviceAvailability, DeviceRegistry
from siro.core.outcomes import ActionOutcome, ActionOutcomeReporter
from siro.core.proactivity import ProactivityContext, ProactivityRules


class LightReadbackStatus(StrEnum):
    CONFIRMED = "confirmed"
    UNAVAILABLE = "unavailable"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class LightReadback:
    status: LightReadbackStatus
    power: bool | None


class RoomLightActuator(Protocol):
    async def set_power(self, action_id: str, device_id: str, desired: bool) -> LightReadback: ...


@dataclass(frozen=True, slots=True)
class RoomTraceStep:
    stage: str
    detail: str


@dataclass(frozen=True, slots=True)
class RoomSceneResult:
    greeted: bool
    light_status: LightReadbackStatus | None
    trace: tuple[RoomTraceStep, ...]


class RoomAutomation:
    """Turns genuine room-entry edges into at most one greeting and light action.

    State originating from an actuator is accepted as a readback only; it can never
    be treated as another presence edge. A brief false/true sensor bounce retains
    the current occupancy session, so it cannot repeatedly greet or toggle a light.
    """

    def __init__(
        self,
        registry: DeviceRegistry,
        proactivity: ProactivityRules,
        authorization: AuthorizationService,
        actuator: RoomLightActuator,
        settings: RoomAutomationSettings,
        *,
        departure_rearm: timedelta = timedelta(minutes=5),
        outcome_reporter: ActionOutcomeReporter | None = None,
    ) -> None:
        self._registry = registry
        self._proactivity = proactivity
        self._authorization = authorization
        self._actuator = actuator
        self._settings = settings
        self._departure_rearm = departure_rearm
        self._outcomes = outcome_reporter
        self._occupied: set[str] = set()
        self._absent_since: dict[str, datetime] = {}
        self._last_social_at: datetime | None = None
        self._social_count_by_day: dict[str, int] = {}

    async def ingest_presence(
        self,
        device_id: str,
        *,
        present: bool,
        observed_at: datetime,
        busy: bool = False,
        speaking: bool = False,
    ) -> RoomSceneResult:
        record = await self._registry.available(device_id, now=observed_at)
        if record is None or record.descriptor.location is None:
            return RoomSceneResult(
                False, None, (RoomTraceStep("sensor", "unknown_device_or_room"),)
            )
        location = record.descriptor.location
        if record.availability is not DeviceAvailability.ONLINE:
            return RoomSceneResult(False, None, (RoomTraceStep("sensor", "device_unavailable"),))
        await self._registry.record_property(
            device_id, "presence", present, observed_at=observed_at
        )
        trace = [RoomTraceStep("sensor", f"presence={str(present).lower()}:{device_id}")]
        if not present:
            self._absent_since.setdefault(location, observed_at)
            trace.append(RoomTraceStep("salience", "departure_observed"))
            return RoomSceneResult(False, None, tuple(trace))

        absent_at = self._absent_since.pop(location, None)
        if location in self._occupied:
            if absent_at is None or observed_at - absent_at < self._departure_rearm:
                trace.append(RoomTraceStep("salience", "presence_bounce_suppressed"))
                return RoomSceneResult(False, None, tuple(trace))
            self._occupied.remove(location)
        self._occupied.add(location)
        trace.append(RoomTraceStep("salience", "home_arrival_edge"))

        day_key = observed_at.astimezone().date().isoformat()
        choice = self._proactivity.choose(
            ProactivityContext(
                now=observed_at,
                home_arrival=True,
                busy=busy,
                speaking=speaking,
                last_social_at=self._last_social_at,
                social_count_today=self._social_count_by_day.get(day_key, 0),
            )
        )
        trace.append(RoomTraceStep("candidate", choice.action))
        greeted = choice.should_speak
        if greeted:
            self._last_social_at = observed_at
            self._social_count_by_day[day_key] = self._social_count_by_day.get(day_key, 0) + 1
            trace.append(RoomTraceStep("policy", "greeting_allowed"))
        else:
            trace.append(RoomTraceStep("policy", f"greeting_suppressed:{choice.reason}"))

        light_status = await self._turn_on_location_light(location, observed_at, trace)
        return RoomSceneResult(greeted, light_status, tuple(trace))

    async def ingest_light_readback(
        self, device_id: str, *, power: bool, observed_at: datetime, source: str
    ) -> tuple[RoomTraceStep, ...]:
        """Accept manual or actuator state without feeding it back into automation."""

        await self._registry.record_property(device_id, "power", power, observed_at=observed_at)
        return (
            RoomTraceStep("state", f"power={str(power).lower()}:{device_id}"),
            RoomTraceStep("feedback", f"readback_only:{source}"),
        )

    async def _turn_on_location_light(
        self, location: str, observed_at: datetime, trace: list[RoomTraceStep]
    ) -> LightReadbackStatus | None:
        if not self._settings.enabled:
            trace.append(RoomTraceStep("policy", "light_automation_disabled"))
            return None
        light = next(
            (
                item
                for item in await self._registry.devices_for_action("light.set", now=observed_at)
                if item.descriptor.location == location
            ),
            None,
        )
        if light is None:
            trace.append(RoomTraceStep("device", "no_available_light"))
            return LightReadbackStatus.UNAVAILABLE
        action_id = f"room-light:{uuid4()}"
        arguments = {"device_id": light.descriptor.device_id, "power": True}
        outcome = self._authorization.authorize(
            AuthorizationRequest(
                action_id=action_id,
                actor="room_automation",
                capability="device.light.set",
                arguments=arguments,
                scope={"device_id": (light.descriptor.device_id,)},
            )
        )
        if outcome.decision is not PermissionDecision.ALLOW:
            trace.append(RoomTraceStep("policy", f"light_{outcome.reason}"))
            if self._outcomes is not None:
                await self._outcomes.report_action(
                    action_id,
                    "denied",
                    occurred_at=observed_at,
                    importance=0.35,
                    controllability=0.8,
                    expected=True,
                )
            return None
        trace.append(RoomTraceStep("policy", "light_allowed"))
        readback = await self._actuator.set_power(action_id, light.descriptor.device_id, True)
        trace.append(RoomTraceStep("device", f"light_{readback.status}"))
        if self._outcomes is not None:
            status: ActionOutcome
            if readback.status is LightReadbackStatus.CONFIRMED:
                status = "confirmed"
            elif readback.status is LightReadbackStatus.MISMATCH:
                status = "mismatch"
            else:
                status = "unavailable"
            await self._outcomes.report_action(
                action_id,
                status,
                occurred_at=observed_at,
                importance=0.35,
                controllability=0.8,
                expected=True,
                observed=readback.power,
            )
        if readback.status is LightReadbackStatus.CONFIRMED and readback.power is True:
            await self.ingest_light_readback(
                light.descriptor.device_id,
                power=True,
                observed_at=observed_at,
                source=f"automation:{action_id}",
            )
            return LightReadbackStatus.CONFIRMED
        return readback.status
