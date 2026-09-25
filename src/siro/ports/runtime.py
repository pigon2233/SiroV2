"""Fail-closed boundary between Core and the privileged local Runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GrantToken:
    claims_json: tuple[int, ...]
    signature_hex: str


@dataclass(frozen=True, slots=True)
class RuntimeRequest:
    action_id: str
    capability: str
    arguments: dict[str, object]
    scope_key: str
    scope_value: str
    grant: GrantToken


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    result: object


class RuntimeUnavailable(RuntimeError):
    """The isolated executor cannot be reached or violates its protocol."""


class RuntimeRejected(RuntimeError):
    """The Runtime rejected an unauthorized or invalid request."""


class RuntimePort(Protocol):
    async def health(self) -> dict[str, object]: ...

    async def execute(self, request: RuntimeRequest) -> RuntimeResult: ...
