"""Chat-tool surface for desktop control: SIRO's model may ask, the owner's switches decide.

``computer.play`` has effect "computer" (never auto-run by the read-only planner) and is only
available while the owner has switched control on in the tray and the Windows shell is connected.
``computer.status`` is read-only. Both exist only when SIRO_COMPUTER_TOKEN is configured.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from siro.ports.models import ToolDefinition
from siro.services.computer_use.http import ComputerRuns

COMPUTER_PLAY = "computer.play"
COMPUTER_STATUS = "computer.status"
COMPUTER_TOOL_NAMES = frozenset({COMPUTER_PLAY, COMPUTER_STATUS})
READ_ONLY = frozenset({COMPUTER_STATUS})
LABELS = {COMPUTER_PLAY: "操控電腦（看螢幕、鍵盤滑鼠）", COMPUTER_STATUS: "查看電腦操控進度"}  # noqa: RUF001

PLAY_DEFINITION = ToolDefinition(
    COMPUTER_PLAY,
    "Start a bounded run that looks at the owner's foreground window and clicks/types to reach a "
    "goal (for example playing a turn-based game). Only works while the owner has switched "
    "computer control on and allowed that program; it never types passwords or secrets, stops "
    "when stuck, unsure or asked, and the owner can stop it any time with the emergency hotkey. "
    "It runs in the background at several seconds per step: call computer.status afterwards "
    "instead of waiting. Describe the goal concretely in the owner's language.",
    {
        "type": "object",
        "properties": {"goal": {"type": "string", "minLength": 2, "maxLength": 500}},
        "required": ["goal"],
        "additionalProperties": False,
    },
)
STATUS_DEFINITION = ToolDefinition(
    COMPUTER_STATUS,
    "Check the current or last computer-control run: whether control is on, whether it is "
    "running, each step taken, and why it stopped. Read-only.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
DEFINITIONS = {COMPUTER_PLAY: PLAY_DEFINITION, COMPUTER_STATUS: STATUS_DEFINITION}


def computer_ready(runs: ComputerRuns, name: str) -> bool:
    """play needs control on and the shell connected; status is always answerable."""
    if name == COMPUTER_STATUS:
        return True
    return runs.bridge.gate.enabled and runs.bridge.executor_online


def computer_handlers(
    runs: ComputerRuns,
) -> dict[str, Callable[[dict[str, object]], Awaitable[Any]]]:
    async def play(arguments: dict[str, object]) -> object:
        goal = arguments.get("goal")
        if not isinstance(goal, str) or not 2 <= len(goal.strip()) <= 500:
            raise ValueError("computer.play requires a goal of 2-500 characters")
        if not runs.bridge.gate.enabled:
            raise PermissionError("computer control is off; the owner switches it on from the tray")
        if not runs.start(goal.strip()):
            raise RuntimeError("a computer-control run is already in progress")
        return {"started": True, "goal": goal.strip(), "next": "call computer.status to follow it"}

    async def status(arguments: dict[str, object]) -> object:
        return runs.status()

    return {COMPUTER_PLAY: play, COMPUTER_STATUS: status}
