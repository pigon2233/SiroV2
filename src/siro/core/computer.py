"""Built-in computer capability catalogue exposed to policy and skill routing."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BuiltinCapability:
    capability: str
    risk: str
    idempotency: str
    available: bool


def platform_capabilities() -> tuple[BuiltinCapability, ...]:
    linux = sys.platform.startswith("linux")
    return (
        BuiltinCapability("filesystem.read", "observe", "read_only", linux),
        BuiltinCapability("filesystem.list", "observe", "read_only", linux),
        BuiltinCapability("filesystem.write", "normal", "action_ledger", linux),
        BuiltinCapability("filesystem.move", "normal", "action_ledger", linux),
        BuiltinCapability("process.list", "observe", "read_only", linux),
        BuiltinCapability("process.run", "normal", "action_ledger", linux),
        BuiltinCapability("process.start", "normal", "action_ledger", linux),
        BuiltinCapability("process.stop", "destructive", "action_ledger", linux),
    )
