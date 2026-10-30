# ruff: noqa: RUF001
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
LABELS = {COMPUTER_PLAY: "操控電腦（看螢幕、鍵盤滑鼠）", COMPUTER_STATUS: "查看電腦操控進度"}

# Short, imperative Chinese on purpose: the local chat model (gemma4:e4b) made no call with a long
# English description on "幫我玩UNDERTALE" (0/2) and called this one every time (2/2, direct probe).
PLAY_DEFINITION = ToolDefinition(
    COMPUTER_PLAY,
    "玩遊戲或操作電腦：看目前前景視窗的畫面，用鍵盤滑鼠一步步完成目標（例如玩 Undertale）。"
    "使用者要你玩遊戲、開始遊玩或操作電腦時，直接呼叫此工具，goal 用一句話寫要完成的事。"
    "不要先詢問許可：電腦操控是否開啟、程式是否允許，系統會自己檢查；不會輸入密碼，"
    "卡住或不確定就停下，主人可隨時急停。背景執行，之後可用 computer.status 查進度。",
    {
        "type": "object",
        "properties": {"goal": {"type": "string", "minLength": 2, "maxLength": 500}},
        "required": ["goal"],
        "additionalProperties": False,
    },
)
STATUS_DEFINITION = ToolDefinition(
    COMPUTER_STATUS,
    "查看電腦操控目前或上一次任務的進度與結果（每步做了什麼、為什麼停下）。"
    "使用者問玩得如何、成功了嗎、進度時，直接呼叫此工具。",
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
        return {
            "started": True,
            "goal": goal.strip(),
            "reply_with": "已經開始操作電腦了，每步大約 7 到 10 秒；要停就按 Ctrl+Alt+Shift+Esc。",
        }

    async def status(arguments: dict[str, object]) -> object:
        return runs.status()

    return {COMPUTER_PLAY: play, COMPUTER_STATUS: status}
