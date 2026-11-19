"""Builds the candidate-profile tool catalog: readiness, metadata and descriptors per tool."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from functools import partial
from typing import Any

from siro.services.computer_use import tool as computer_tool
from siro.services.tools.claude import CLAUDE_TOOL
from siro.services.tools.claude import TIMEOUT_SECONDS as CLAUDE_TIMEOUT_SECONDS
from siro.services.tools.orchestrator import (
    AvailabilityReason,
    AvailabilityState,
    ToolAvailability,
    ToolCatalog,
    ToolDescriptor,
    ToolExecutor,
    ToolMetadata,
)
from siro.services.tools.web_search import WEB_SEARCH_TOOL

_READ_TOOLS = frozenset(
    {
        CLAUDE_TOOL,
        WEB_SEARCH_TOOL,
        "browser.navigate+read",
        "browser.read",
        "filesystem.read",
        "filesystem.list",
    }
)


def _ready(ready: bool, missing: AvailabilityReason) -> ToolAvailability:
    return ToolAvailability(
        AvailabilityState.AVAILABLE if ready else AvailabilityState.UNAVAILABLE,
        AvailabilityReason.READY if ready else missing,
    )


def tool_readiness(
    name: str,
    *,
    kill_switch: Callable[[str], bool],
    computer_runs: Any,
    workspace: Any,
    claude_ready: Callable[[], bool],
) -> ToolAvailability:
    if not kill_switch("tools"):
        return ToolAvailability(AvailabilityState.UNAVAILABLE, AvailabilityReason.TOOLS_DISABLED)
    if name in computer_tool.COMPUTER_TOOL_NAMES:
        ready = computer_runs is not None and computer_tool.computer_ready(computer_runs, name)
        return _ready(ready, AvailabilityReason.NOT_READY)
    if name == WEB_SEARCH_TOOL:  # the query leaves this machine
        return _ready(kill_switch("cloud"), AvailabilityReason.NOT_READY)
    if name == CLAUDE_TOOL:
        return _ready(kill_switch("cloud") and claude_ready(), AvailabilityReason.NOT_READY)
    if name.startswith("filesystem."):
        ready = workspace is not None and workspace.available
        return _ready(ready, AvailabilityReason.WORKSPACE_UNAVAILABLE)
    if name.startswith("browser."):
        ready = bool(shutil.which("google-chrome") or shutil.which("chromium"))
        return _ready(ready, AvailabilityReason.BROWSER_EXECUTABLE_MISSING)
    # Target checks remain in existing handlers; this is not a successful action probe.
    return ToolAvailability(AvailabilityState.AVAILABLE, AvailabilityReason.READY)


def tool_metadata(name: str, *, browser_sessions_enabled: bool) -> ToolMetadata:
    labels = {
        "computer.execute": "執行電腦任務",
        "process.start": "啟動應用程式",
        "browser.navigate+read": "開啟並閱讀網頁",
        "browser.read": "閱讀目前網頁",
        "browser.fill": "填寫網頁欄位",
        "browser.click": "操作網頁按鈕",
        "browser.close": "關閉目前網頁",
        "filesystem.read": "讀取工作目錄文字檔",
        "filesystem.list": "查看工作目錄檔案",
        CLAUDE_TOOL: "請 Claude 幫忙查",
        WEB_SEARCH_TOOL: "搜尋網路",
        **computer_tool.LABELS,
    }
    read_only = name in computer_tool.READ_ONLY or name in _READ_TOOLS
    return ToolMetadata(
        display_name=labels.get(name),
        required_permissions=("tool_approval", "workspace_path_grant")
        if name.startswith("filesystem.")
        else ("tool_approval",),
        risk_level="observe/read-only" if read_only else "computer",
        version="siro-tool-contract-v1",
        provenance="siro_builtin",
        timeout_seconds=120
        if name == "computer.execute"
        else CLAUDE_TIMEOUT_SECONDS
        if name == CLAUDE_TOOL
        else (30 if name.startswith("browser.") and browser_sessions_enabled else None),
        failure_behavior="Failures produce failed observations. Unknown effects are not "
        "automatically repeated. Availability is not proof of successful execution.",
    )


def _backend(name: str) -> str:
    if name.startswith("filesystem."):
        return "rust.scoped"
    if name.startswith("browser."):
        return "playwright"
    return "anthropic.api" if name == CLAUDE_TOOL else "python.argv"


def build_tool_catalog(
    *,
    handlers: Mapping[str, ToolExecutor],
    definitions: Mapping[str, Any],
    execute_computer: Any,
    contextual: tuple[Mapping[str, Any], ...],
    readiness: Callable[[str], ToolAvailability],
    browser_sessions_enabled: bool,
) -> ToolCatalog:
    """`contextual` maps are searched in order; first match wins (keys are disjoint today)."""

    def contextual_for(name: str) -> Any:
        if name == "computer.execute":
            return execute_computer
        for executors in contextual:
            if found := executors.get(name):
                return found
        return None

    return ToolCatalog(
        tuple(
            ToolDescriptor(
                name,
                definitions.get(name),
                handler,
                available=partial(readiness, name),
                backend=_backend(name),
                effect="read"
                if name in computer_tool.READ_ONLY or name in _READ_TOOLS
                else "computer",
                contextual_executor=contextual_for(name),
                metadata=tool_metadata(name, browser_sessions_enabled=browser_sessions_enabled),
            )
            for name, handler in handlers.items()
        )
    )
