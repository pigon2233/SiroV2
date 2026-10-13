"""Home Assistant REST/WebSocket adapter with explicit state confirmation."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from websockets.asyncio.client import connect

from siro.contracts.events import Privacy
from siro.core.devices import (
    DeviceAction,
    DeviceAvailability,
    DeviceDescriptor,
    DeviceProperty,
    DeviceRegistry,
)
from siro.core.rooms import LightReadback, LightReadbackStatus


class HomeAssistantError(RuntimeError):
    """Base adapter failure that is safe to expose without credentials."""


class HomeAssistantAuthError(HomeAssistantError):
    """The configured Home Assistant credential was rejected."""


class HomeAssistantProtocolError(HomeAssistantError):
    """Home Assistant returned an unexpected protocol message."""


class HomeAssistantEntityMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(pattern=r"^[a-z0-9_]+\.[a-z0-9_]+$")
    kind: Literal["light", "presence", "temperature"]
    location: str | None = Field(default=None, min_length=1, max_length=128)
    availability_ttl_ms: int = Field(default=30_000, gt=0, le=86_400_000)


class HomeAssistantConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(min_length=1)
    token: SecretStr = Field(repr=False)
    entities: tuple[HomeAssistantEntityMapping, ...]
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)


class HomeAssistantFileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(min_length=1)
    token_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    entities: tuple[HomeAssistantEntityMapping, ...]
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)


def load_home_assistant_config(
    path: Path, *, environ: dict[str, str] | None = None
) -> HomeAssistantConfig:
    file_config = HomeAssistantFileConfig.model_validate_json(path.read_text(encoding="utf-8"))
    source = os.environ if environ is None else environ
    token = source.get(file_config.token_env)
    if not token:
        raise ValueError(f"required environment variable is missing: {file_config.token_env}")
    return HomeAssistantConfig(
        base_url=file_config.base_url,
        token=SecretStr(token),
        entities=file_config.entities,
        timeout_seconds=file_config.timeout_seconds,
    )


class HomeAssistantState(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    entity_id: str
    state: str
    attributes: dict[str, object] = Field(default_factory=dict)
    last_changed: datetime | None = None
    last_updated: datetime | None = None


class HomeAssistantStateChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str
    old_state: HomeAssistantState | None
    new_state: HomeAssistantState | None
    occurred_at: datetime


class LightActionStatus(StrEnum):
    CONFIRMED = "confirmed"
    STATE_UNCHANGED = "state_unchanged"
    UNAVAILABLE = "unavailable"
    AUTH_REVOKED = "auth_revoked"
    NOT_FOUND = "not_found"
    TRANSPORT_ERROR = "transport_error"


class LightActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str
    entity_id: str
    desired: bool
    status: LightActionStatus
    observed_state: str | None = None


def descriptor_for(mapping: HomeAssistantEntityMapping) -> DeviceDescriptor:
    properties: dict[str, DeviceProperty]
    actions: dict[str, DeviceAction]
    if mapping.kind == "light":
        properties = {"power": DeviceProperty(type="boolean")}
        actions = {"light.set": DeviceAction(input_schema="light_set.v1")}
    elif mapping.kind == "presence":
        properties = {"presence": DeviceProperty(type="boolean")}
        actions = {}
    else:
        properties = {"temperature": DeviceProperty(type="number")}
        actions = {}
    return DeviceDescriptor(
        device_id=f"ha:{mapping.entity_id}",
        adapter="home_assistant",
        location=mapping.location,
        properties=properties,
        actions=actions,
        events=("device.state_changed.v1",),
        availability_ttl_ms=mapping.availability_ttl_ms,
        privacy=Privacy.TRUSTED_LAN,
    )


def state_value(
    mapping: HomeAssistantEntityMapping, state: HomeAssistantState
) -> tuple[DeviceAvailability, object | None]:
    if state.state in {"unavailable", "unknown"}:
        return DeviceAvailability.UNKNOWN, None
    if mapping.kind == "light":
        if state.state not in {"on", "off"}:
            return DeviceAvailability.UNKNOWN, None
        return DeviceAvailability.ONLINE, state.state == "on"
    if mapping.kind == "presence":
        if state.state not in {"on", "off"}:
            return DeviceAvailability.UNKNOWN, None
        return DeviceAvailability.ONLINE, state.state == "on"
    try:
        return DeviceAvailability.ONLINE, float(state.state)
    except ValueError:
        return DeviceAvailability.UNKNOWN, None


def parse_state_changed(message: str | bytes) -> HomeAssistantStateChange | None:
    payload = json.loads(message)
    if not isinstance(payload, dict) or payload.get("type") != "event":
        return None
    event = payload.get("event")
    if not isinstance(event, dict) or event.get("event_type") != "state_changed":
        return None
    data = event.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("entity_id"), str):
        raise HomeAssistantProtocolError("invalid state_changed event")
    return HomeAssistantStateChange(
        entity_id=data["entity_id"],
        old_state=(
            HomeAssistantState.model_validate(data["old_state"])
            if data.get("old_state") is not None
            else None
        ),
        new_state=(
            HomeAssistantState.model_validate(data["new_state"])
            if data.get("new_state") is not None
            else None
        ),
        occurred_at=datetime.fromisoformat(str(event["time_fired"]).replace("Z", "+00:00")),
    )


class HomeAssistantAdapter:
    def __init__(
        self, config: HomeAssistantConfig, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {config.token.get_secret_value()}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout_seconds,
            transport=transport,
        )
        self._ledger: dict[str, LightActionResult] = {}

    async def __aenter__(self) -> HomeAssistantAdapter:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def descriptors(self) -> tuple[DeviceDescriptor, ...]:
        return tuple(descriptor_for(mapping) for mapping in self._config.entities)

    async def states(self) -> tuple[HomeAssistantState, ...]:
        response = await self._client.get("/api/states")
        self._raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, list):
            raise HomeAssistantProtocolError("states response is not a list")
        return tuple(HomeAssistantState.model_validate(item) for item in payload)

    async def state(self, entity_id: str) -> HomeAssistantState:
        response = await self._client.get(f"/api/states/{entity_id}")
        self._raise_for_status(response)
        return HomeAssistantState.model_validate(response.json())

    async def sync_registry(self, registry: DeviceRegistry) -> None:
        """Register configured entities and project one authoritative REST snapshot."""

        mappings = {item.entity_id: item for item in self._config.entities}
        for mapping in mappings.values():
            await registry.register(descriptor_for(mapping))
        for state in await self.states():
            state_mapping = mappings.get(state.entity_id)
            if state_mapping is not None:
                await self.project_state(registry, state_mapping, state)

    async def project_change(
        self, registry: DeviceRegistry, change: HomeAssistantStateChange
    ) -> None:
        mapping = self.mapping_for(change.entity_id, self._config.entities)
        if mapping is None or change.new_state is None:
            return
        await self.project_state(
            registry, mapping, change.new_state, observed_at=change.occurred_at
        )

    @staticmethod
    async def project_state(
        registry: DeviceRegistry,
        mapping: HomeAssistantEntityMapping,
        state: HomeAssistantState,
        *,
        observed_at: datetime | None = None,
    ) -> None:
        when = observed_at or state.last_updated or state.last_changed or datetime.now(UTC)
        availability, value = state_value(mapping, state)
        device_id = f"ha:{mapping.entity_id}"
        if availability is not DeviceAvailability.ONLINE or value is None:
            await registry.set_availability(device_id, availability, observed_at=when)
            return
        property_name = {
            "light": "power",
            "presence": "presence",
            "temperature": "temperature",
        }[mapping.kind]
        await registry.record_property(device_id, property_name, value, observed_at=when)

    async def set_light(self, action_id: str, entity_id: str, desired: bool) -> LightActionResult:
        previous = self._ledger.get(action_id)
        if previous is not None:
            if previous.entity_id != entity_id or previous.desired != desired:
                raise ValueError("action id was reused with different arguments")
            return previous
        if not any(
            item.entity_id == entity_id and item.kind == "light" for item in self._config.entities
        ):
            raise ValueError("entity is not an allowlisted light")

        status = LightActionStatus.TRANSPORT_ERROR
        observed: str | None = None
        try:
            service = "turn_on" if desired else "turn_off"
            response = await self._client.post(
                f"/api/services/light/{service}", json={"entity_id": entity_id}
            )
            self._raise_for_status(response)
            readback = await self.state(entity_id)
            observed = readback.state
            if observed in {"unavailable", "unknown"}:
                status = LightActionStatus.UNAVAILABLE
            elif observed == ("on" if desired else "off"):
                status = LightActionStatus.CONFIRMED
            else:
                status = LightActionStatus.STATE_UNCHANGED
        except HomeAssistantAuthError:
            status = LightActionStatus.AUTH_REVOKED
        except httpx.HTTPStatusError as exc:
            status = (
                LightActionStatus.NOT_FOUND
                if exc.response.status_code == 404
                else LightActionStatus.TRANSPORT_ERROR
            )
        except httpx.HTTPError:
            status = LightActionStatus.TRANSPORT_ERROR

        result = LightActionResult(
            action_id=action_id,
            entity_id=entity_id,
            desired=desired,
            status=status,
            observed_state=observed,
        )
        self._ledger[action_id] = result
        return result

    async def state_changes(self) -> AsyncIterator[HomeAssistantStateChange]:
        parsed = urlparse(self._config.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_url = urlunparse((scheme, parsed.netloc, "/api/websocket", "", "", ""))
        async with connect(ws_url, open_timeout=self._config.timeout_seconds) as websocket:
            greeting = json.loads(await websocket.recv())
            if not isinstance(greeting, dict) or greeting.get("type") != "auth_required":
                raise HomeAssistantProtocolError("expected auth_required")
            await websocket.send(
                json.dumps({"type": "auth", "access_token": self._config.token.get_secret_value()})
            )
            auth = json.loads(await websocket.recv())
            if isinstance(auth, dict) and auth.get("type") == "auth_invalid":
                raise HomeAssistantAuthError("Home Assistant credential was rejected")
            if not isinstance(auth, dict) or auth.get("type") != "auth_ok":
                raise HomeAssistantProtocolError("expected auth_ok")
            await websocket.send(
                json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
            )
            subscribed = json.loads(await websocket.recv())
            if not (
                isinstance(subscribed, dict)
                and subscribed.get("id") == 1
                and subscribed.get("type") == "result"
                and subscribed.get("success") is True
            ):
                raise HomeAssistantProtocolError("state_changed subscription was rejected")
            async for message in websocket:
                event = parse_state_changed(message)
                if event is not None:
                    yield event

    @staticmethod
    def mapping_for(
        entity_id: str, mappings: Iterable[HomeAssistantEntityMapping]
    ) -> HomeAssistantEntityMapping | None:
        return next((item for item in mappings if item.entity_id == entity_id), None)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 401:
            raise HomeAssistantAuthError("Home Assistant credential was rejected")
        response.raise_for_status()


class HomeAssistantLightActuator:
    """T29 bridge that converts Home Assistant's readback result to its light port."""

    def __init__(self, adapter: HomeAssistantAdapter, entity_by_device_id: dict[str, str]) -> None:
        self._adapter = adapter
        self._entity_by_device_id = entity_by_device_id.copy()

    async def set_power(self, action_id: str, device_id: str, desired: bool) -> LightReadback:
        entity_id = self._entity_by_device_id.get(device_id)
        if entity_id is None:
            return LightReadback(LightReadbackStatus.UNAVAILABLE, None)
        result = await self._adapter.set_light(action_id, entity_id, desired)
        if result.status is LightActionStatus.CONFIRMED:
            return LightReadback(LightReadbackStatus.CONFIRMED, desired)
        if result.status is LightActionStatus.UNAVAILABLE:
            return LightReadback(LightReadbackStatus.UNAVAILABLE, None)
        return LightReadback(LightReadbackStatus.MISMATCH, None)
