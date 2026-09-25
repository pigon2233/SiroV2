"""Core-side permission policy and argument-bound Runtime grant issuance."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from enum import StrEnum

from siro.ports.runtime import GrantToken


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    action_id: str
    actor: str
    capability: str
    arguments: dict[str, object]
    scope: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class AuthorizationOutcome:
    decision: PermissionDecision
    grant: GrantToken | None = None
    reason: str = ""


class PermissionPolicy:
    def __init__(self, rules: dict[str, PermissionDecision]) -> None:
        self._rules = rules.copy()

    def decide(self, capability: str) -> PermissionDecision:
        return self._rules.get(capability, PermissionDecision.DENY)


class AuthorizationService:
    def __init__(
        self, policy: PermissionPolicy, secret: bytes, *, grant_ttl_seconds: int = 60
    ) -> None:
        if not secret:
            raise ValueError("grant signing secret cannot be empty")
        self._policy = policy
        self._secret = secret
        self._ttl = grant_ttl_seconds
        self._pending: dict[str, AuthorizationRequest] = {}

    def authorize(self, request: AuthorizationRequest) -> AuthorizationOutcome:
        decision = self._policy.decide(request.capability)
        if decision is PermissionDecision.DENY:
            return AuthorizationOutcome(decision, reason="policy_denied")
        if decision is PermissionDecision.ASK:
            self._pending[request.action_id] = request
            return AuthorizationOutcome(decision, reason="user_confirmation_required")
        return AuthorizationOutcome(decision, self._issue(request), "policy_allowed")

    def resolve(
        self, action_id: str, *, approved: bool, arguments: dict[str, object]
    ) -> AuthorizationOutcome:
        request = self._pending.pop(action_id, None)
        if request is None:
            return AuthorizationOutcome(PermissionDecision.DENY, reason="no_pending_request")
        if not approved:
            return AuthorizationOutcome(PermissionDecision.DENY, reason="user_denied")
        if argument_hash(arguments) != argument_hash(request.arguments):
            return AuthorizationOutcome(PermissionDecision.DENY, reason="arguments_changed")
        return AuthorizationOutcome(PermissionDecision.ALLOW, self._issue(request), "user_approved")

    def _issue(self, request: AuthorizationRequest) -> GrantToken:
        claims = {
            "grant_id": f"grant:{request.action_id}",
            "actor": request.actor,
            "capability": request.capability,
            "scope": {key: list(values) for key, values in sorted(request.scope.items())},
            "args_hash": argument_hash(request.arguments),
            "expires_at_unix": int(time.time()) + self._ttl,
            "uses_remaining": 1,
        }
        claims_json = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self._secret, claims_json, hashlib.sha256).hexdigest()
        return GrantToken(tuple(claims_json), signature)


def argument_hash(arguments: dict[str, object]) -> str:
    canonical = json.dumps(arguments, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()
