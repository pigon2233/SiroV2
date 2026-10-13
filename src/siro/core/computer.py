"""Built-in computer capability catalogue exposed to policy and skill routing."""

from __future__ import annotations

import shutil
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
    browser = linux and bool(shutil.which("google-chrome") or shutil.which("chromium"))
    return (
        BuiltinCapability("filesystem.read", "observe", "read_only", linux),
        BuiltinCapability("filesystem.list", "observe", "read_only", linux),
        BuiltinCapability("filesystem.write", "normal", "action_ledger", linux),
        BuiltinCapability("filesystem.move", "normal", "action_ledger", linux),
        BuiltinCapability("process.list", "observe", "read_only", linux),
        BuiltinCapability("process.run", "normal", "action_ledger", linux),
        BuiltinCapability("process.start", "normal", "action_ledger", linux),
        BuiltinCapability("process.stop", "destructive", "action_ledger", linux),
        BuiltinCapability("browser.navigate", "observe", "read_only", browser),
        BuiltinCapability("browser.read", "observe", "read_only", browser),
        BuiltinCapability("browser.fill", "normal", "screen_version", browser),
        BuiltinCapability("browser.click", "normal", "screen_version", browser),
        BuiltinCapability("browser.key", "normal", "screen_version", browser),
        BuiltinCapability("browser.pointer", "normal", "screen_version", browser),
        BuiltinCapability("browser.screenshot", "observe", "screen_version", browser),
        BuiltinCapability("desktop.window", "normal", "unsupported", False),
        BuiltinCapability("desktop.key", "normal", "unsupported", False),
        BuiltinCapability("desktop.pointer", "normal", "unsupported", False),
        BuiltinCapability("service.status", "observe", "read_only", linux),
        BuiltinCapability("service.start", "normal", "action_ledger", linux),
        BuiltinCapability("service.stop", "destructive", "action_ledger", linux),
        BuiltinCapability("service.install", "critical", "exact_hash_approval", linux),
    )
