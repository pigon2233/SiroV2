"""Single immutable computer-use decision/verification boundary; no backend dependencies."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import InputAction

CLOUD_SCREEN_FLAG = "SIRO_COMPUTER_CLOUD_SCREEN"


class DecisionError(ValueError):
    """The model reply is not an acceptable decision."""


@dataclass(frozen=True, slots=True)
class Decision:
    kind: str  # act | done | stuck | ask | wait
    action: InputAction | None = None
    expect: str = ""  # what should visibly change if the action works
    reason: str = ""
    confidence: float = 0.0
    evidence: str = ""  # for done: what on screen proves the goal is met
    seen: str = ""  # one short sentence: what the screenshot shows now (kept in the history)
    strategy: str = ""  # optional short plan update; empty keeps the previous plan
    scene: str = ""  # map|combat|shop|event|reward|pause|defeat|menu|unknown
    energy: str = ""  # e.g. "3/3", "0", "n/a"
    targets: str = ""  # actionable controls visible now
    uncertainty: str = ""  # unreadable bits; empty if clear


@dataclass(frozen=True, slots=True)
class StepRecord:
    step: int
    action: str
    expect: str
    outcome: str  # sent | visual_change | effective | unconfirmed | ineffective | ...
    screen_changed: bool | None
    seen: str = ""  # what the screen showed before this step
    scene: str = ""
    detail: str = ""  # verification note or failure reason


@dataclass(frozen=True, slots=True)
class VerifyResult:
    status: str  # confirmed | denied | unknown
    detail: str = ""
    seen: str = ""
    scene: str = ""


class Decider(Protocol):
    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision: ...

    async def verify(
        self,
        expect: str,
        before_seen: str,
        observation: Observation,
    ) -> VerifyResult: ...


class CloudScreenNotAllowed(RuntimeError):
    """The owner has not allowed screenshots to leave the machine."""


def cloud_screen_allowed(env: dict[str, str] | None = None) -> bool:
    return (os.environ if env is None else env).get(CLOUD_SCREEN_FLAG, "0") == "1"
