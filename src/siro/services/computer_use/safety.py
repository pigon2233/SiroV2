"""Safety floor for desktop input: default OFF, latched kill switch, allowlist, rate limit.

Every input action must pass ``ControlGate.check`` before any Windows-native executor
runs it. The gate is pure (injected clock) so it is testable without a desktop.
"""

from __future__ import annotations

import os
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

ENABLE_FLAG = "SIRO_COMPUTER_CONTROL_ENABLED"
ALLOWED_KINDS = frozenset({"move", "click", "scroll", "key", "type"})
MAX_TYPE_CHARS = 200
MAX_ACTIONS_PER_SECOND = 5
MAX_ACTIONS_PER_MINUTE = 120
# Combos that close, switch away from, or escape the owner's session.
BLOCKED_COMBOS = frozenset(
    {"alt+f4", "ctrl+alt+delete", "ctrl+shift+escape", "win+l", "win+r", "win+x", "ctrl+escape"}
)
_SECRET_TEXT = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.)"
)
_SECRET_ENV_NAME = re.compile(r"(?:key|token|secret|password)", re.I)


class Verdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class InputAction:
    kind: str
    x: int | None = None
    y: int | None = None
    button: str = "left"
    key: str = ""
    text: str = ""
    amount: int = 0
    # Perception says the focused element is a password/secret field.
    focus_is_secret: bool = False


@dataclass(frozen=True, slots=True)
class GateDecision:
    verdict: Verdict
    reason: str

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.ALLOW


def _deny(reason: str) -> GateDecision:
    return GateDecision(Verdict.DENY, reason)


def normalize_combo(key: str) -> str:
    parts = [p.strip().lower() for p in key.split("+") if p.strip()]
    aliases = {"control": "ctrl", "del": "delete", "windows": "win", "esc": "escape"}
    return "+".join(aliases.get(p, p) for p in parts)


class ControlGate:
    """Default OFF. ``trip()`` latches a stop that only ``enable()`` by the owner clears."""

    def __init__(
        self,
        *,
        screen: tuple[int, int, int, int] = (0, 0, 1920, 1080),
        clock: Callable[[], float] = time.monotonic,
        enabled: bool | None = None,
    ) -> None:
        self._clock = clock
        self._screen = screen  # left, top, width, height of the allowed area
        self._enabled = os.environ.get(ENABLE_FLAG, "0") == "1" if enabled is None else enabled
        self._tripped = False
        self._stamps: deque[float] = deque()

    @property
    def enabled(self) -> bool:
        return self._enabled and not self._tripped

    @property
    def tripped(self) -> bool:
        return self._tripped

    def enable(self) -> None:
        self._tripped = False
        self._enabled = True
        self._stamps.clear()

    def disable(self) -> None:
        self._enabled = False

    def trip(self) -> None:
        """Emergency stop (hotkey / UI button). Wins over everything until re-enabled."""
        self._tripped = True

    def check(self, action: InputAction) -> GateDecision:
        if self._tripped:
            return _deny("emergency_stop")
        if not self._enabled:
            return _deny("control_disabled")
        if action.kind not in ALLOWED_KINDS:
            return _deny("action_not_allowed")
        reason = self._content_problem(action)
        if reason:
            return _deny(reason)
        if not self._take_slot():
            return _deny("rate_limited")
        return GateDecision(Verdict.ALLOW, "ok")

    def _content_problem(self, action: InputAction) -> str:
        if action.kind in {"move", "click"} and (action.x is None or action.y is None):
            return "missing_coordinates"
        if action.x is not None and action.y is not None:
            left, top, width, height = self._screen
            if not (left <= action.x < left + width and top <= action.y < top + height):
                return "out_of_bounds"
        if action.kind == "click" and action.button not in {"left", "right"}:
            return "button_not_allowed"
        if action.kind == "key":
            combo = normalize_combo(action.key)
            if not combo or combo in BLOCKED_COMBOS:
                return "key_blocked"
        if action.kind == "type":
            if action.focus_is_secret:
                return "secret_field"
            if not action.text or len(action.text) > MAX_TYPE_CHARS:
                return "text_length"
            if _SECRET_TEXT.search(action.text) or _contains_env_secret(action.text):
                return "secret_text"
        return ""

    def _take_slot(self) -> bool:
        now = self._clock()
        while self._stamps and now - self._stamps[0] >= 60:
            self._stamps.popleft()
        if len(self._stamps) >= MAX_ACTIONS_PER_MINUTE:
            return False
        if sum(1 for t in self._stamps if now - t < 1) >= MAX_ACTIONS_PER_SECOND:
            return False
        self._stamps.append(now)
        return True


def _contains_env_secret(text: str) -> bool:
    """Reject typing a value that appears in any secret-named environment variable."""
    return any(
        len(value) >= 8 and _SECRET_ENV_NAME.search(name) and value in text
        for name, value in os.environ.items()
    )
