"""Deliberately small W3C WoT TD to SIRO descriptor translator."""

from __future__ import annotations

from siro.contracts.events import Privacy
from siro.core.devices import DeviceAction, DeviceDescriptor, DeviceProperty


def translate_thing_description(td: dict[str, object]) -> DeviceDescriptor:
    if "securityDefinitions" in td or "security" in td:
        raise ValueError("WoT security declarations require an explicit adapter")
    title = td.get("title")
    properties = td.get("properties", {})
    actions = td.get("actions", {})
    events = td.get("events", {})
    if (
        not isinstance(title, str)
        or not isinstance(properties, dict)
        or not isinstance(actions, dict)
        or not isinstance(events, dict)
    ):
        raise ValueError("unsupported Thing Description shape")
    converted_properties: dict[str, DeviceProperty] = {}
    for name, schema in properties.items():
        if (
            not isinstance(name, str)
            or not isinstance(schema, dict)
            or schema.get("type") not in {"boolean", "number", "string", "object"}
        ):
            raise ValueError("unsupported property schema")
        converted_properties[name] = DeviceProperty(
            type=schema["type"],
            unit=schema.get("unit") if isinstance(schema.get("unit"), str) else None,
        )
    converted_actions = {str(name): DeviceAction(input_schema="wot.v1") for name in actions}
    return DeviceDescriptor(
        device_id=f"wot:{title}",
        adapter="wot_td",
        location=None,
        properties=converted_properties,
        actions=converted_actions,
        events=tuple(str(name) for name in events),
        availability_ttl_ms=30_000,
        privacy=Privacy.TRUSTED_LAN,
    )
