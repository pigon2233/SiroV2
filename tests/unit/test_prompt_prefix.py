"""P0-6 prompt snapshots: a byte-identical stable prefix and a deduplicated capability block.

Ollama reuses its KV cache only for the identical leading part of a prompt. Everything that
changes per turn (time, memories, affect, observations, dialogue) must therefore follow
TURN_CONTEXT_MARKER. If a deliberate prompt edit changes the locked hash, update
STABLE_PREFIX_SHA256 in the same commit and re-check that nothing per-turn moved above the marker.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

import siro.core.memory as memory_module
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.core.context import START as CONTEXT_START
from siro.core.context import render_context
from siro.core.identity import IdentityState, ImmutableCore
from siro.core.memory import (
    TURN_CONTEXT_MARKER,
    Memory,
    WorkingMessage,
    assemble_prompt,
    stable_prompt_prefix,
)
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelRequest,
    Privacy,
    ToolDefinition,
)
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import (
    BROWSER_SESSION_TOOLS,
    DEFAULT_MODEL_TOOLS,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolDescriptor,
    ToolMetadata,
    ToolOrchestrator,
)

TAIPEI = ZoneInfo("Asia/Taipei")
CAPABILITY_START = "[SIRO_TOOL_CAPABILITIES_V1]"
CAPABILITY_END = "[/SIRO_TOOL_CAPABILITIES_V1]"
# Locked snapshot of the synthetic identity's stable prefix (motion cues on, context policy on).
STABLE_PREFIX_SHA256 = "f8376d121aee7289d6b357ff9e8b20e2f91ca787b06ebbe86f7ee20ba17aa1a8"
# Budgets = measured size + ~5% (2026-11-16, P0-6): prefix 5,032 chars, capability block 3,027.
# With scripts/bench_ttft.py's catalogue, main's capability block was 5,971 chars, now 3,404.
STABLE_PREFIX_CHAR_BUDGET = 5_300
CAPABILITY_BLOCK_CHAR_BUDGET = 3_200


def _identity() -> IdentityState:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return IdentityState(
        identity_id="siro",
        core=ImmutableCore(
            name="SIRO",
            baseline_identity="persistent companion",
            core_values=("honesty", "owner control"),
            creator_relationship="owner",
        ),
        created_at=now,
        updated_at=now,
    )


def _memory(text: str) -> Memory:
    return Memory(uuid4(), "siro", text, (uuid4(),), datetime(2026, 11, 1, tzinfo=UTC))


def _turn(now: datetime, memories: list[Memory], observations: tuple[str, ...], text: str) -> str:
    return assemble_prompt(
        _identity(),
        text,
        memories,
        (WorkingMessage("user", "上一句"), WorkingMessage("assistant", "好")),
        observations,
        context_evidence=render_context("s", "siro", memories, None),
        native_dialogue=False,
        now=now,
        motion_cues=True,
    )


def test_stable_prefix_is_byte_identical_across_turns_and_locked() -> None:
    first = _turn(
        datetime(2026, 11, 16, 9, 5, tzinfo=TAIPEI),
        [_memory("我最喜歡冬天的海邊")],
        ("SIRO internal affect: calm intensity=0.20",),
        "早安",
    )
    second = _turn(
        datetime(2026, 11, 17, 23, 58, tzinfo=TAIPEI),
        [_memory("我的貓叫做麻糬"), _memory("週三晚上要上日文課")],
        ("Relationship with owner: trust=0.61", "Current user input arrived through typed text"),
        "晚安",
    )
    head_one, marker_one, tail_one = first.partition(TURN_CONTEXT_MARKER)
    head_two, marker_two, tail_two = second.partition(TURN_CONTEXT_MARKER)
    assert marker_one == marker_two == TURN_CONTEXT_MARKER
    assert head_one.encode() == head_two.encode()
    assert tail_one != tail_two
    # The prefix is exactly the turn-invariant builder output; nothing per turn leaks into it.
    from siro.core.context import POLICY

    expected = stable_prompt_prefix(
        _identity(),
        motion_cues=True,
        context_policy="Context interpretation policy:\n" + POLICY + "\n",
    )
    assert head_one == expected
    for per_turn in (
        "2026-11-16",
        "09:05",
        "海邊",
        "麻糬",
        "calm",
        "trust=",
        "早安",
        CONTEXT_START,
    ):
        assert per_turn not in head_one
    assert "2026-11-16 09:05 星期一" in tail_one and "2026-11-17 23:58 星期二" in tail_two
    assert "海邊" in tail_one and "麻糬" in tail_two
    assert tail_one.endswith("User: 早安") and tail_two.endswith("User: 晚安")
    assert len(head_one) <= STABLE_PREFIX_CHAR_BUDGET
    assert hashlib.sha256(head_one.encode()).hexdigest() == STABLE_PREFIX_SHA256


def test_date_rule_stays_in_policy_while_the_value_is_per_turn() -> None:
    prompt = assemble_prompt(
        _identity(), "颱風", (), now=datetime(2026, 10, 23, 17, 30, tzinfo=TAIPEI)
    )
    head, _, tail = prompt.partition(TURN_CONTEXT_MARKER)
    assert "never assume another date" in head
    assert "2026-10-23 17:30 星期五" in tail
    for section in ("Verified memories:", "Verified preferences:", "Recent conversation:"):
        assert section in tail and section not in head


def _definition(name: str) -> ToolDefinition:
    return ToolDefinition(name, f"synthetic {name}", {"type": "object", "properties": {}})


_FAILURE = (
    "Failures produce failed observations. Unknown effects are not automatically repeated. "
    "Availability is not proof of successful execution."
)


def _catalog(available: dict[str, bool] | None = None) -> ToolCatalog:
    """Production-shaped catalogue: 11 model tools sharing the gateway's metadata defaults."""
    definitions = [
        *DEFAULT_MODEL_TOOLS,
        *BROWSER_SESSION_TOOLS,
        *(
            _definition(name)
            for name in (
                "claude.ask",
                "computer.play",
                "computer.status",
                "filesystem.read",
                "filesystem.list",
            )
        ),
    ]
    flags = available or {}

    async def never(arguments: dict[str, object]) -> object:
        raise AssertionError("snapshot tests never execute tools")

    return ToolCatalog(
        tuple(
            ToolDescriptor(
                d.name,
                d,
                never,
                lambda name=d.name: flags.get(name, True),
                "playwright" if d.name.startswith("browser.") else "python.argv",
                "read" if d.name.endswith(("read", "list", "status", "ask")) else "computer",
                metadata=ToolMetadata(
                    display_name=f"顯示 {d.name}",
                    required_permissions=("tool_approval",),
                    risk_level="observe/read-only" if d.name.endswith("read") else "computer",
                    version="siro-tool-contract-v1",
                    provenance="siro_builtin",
                    timeout_seconds=30 if d.name.startswith("browser.") else None,
                    failure_behavior=_FAILURE,
                ),
            )
            for d in definitions
        )
    )


def test_capability_block_states_shared_metadata_once_without_losing_facts() -> None:
    capture = _catalog({"browser.fill": False}).capture()
    text = capture.model_context()
    view = json.loads(text)
    assert view["authorizes_execution"] is False
    assert text.count(_FAILURE) == 1 and text.count("siro-tool-contract-v1") == 1
    assert len(text) <= CAPABILITY_BLOCK_CHAR_BUDGET
    # Every row, expanded with the shared fields, equals the full inventory row (minus schema,
    # description and probe time, which already travel as tool definitions).
    expanded = {row["name"]: {**view["shared"], **row} for row in view["capabilities"]}
    for row in capture.inventory:
        expected = {
            k: v for k, v in row.items() if k not in {"input_schema", "checked_at", "description"}
        }
        assert expanded[str(row["name"])] == json.loads(json.dumps(expected))
    # Current state is never hoisted: each tool states its own availability.
    for row in view["capabilities"]:
        assert {"name", "available", "availability", "reason_code"} <= row.keys()
    assert expanded["browser.fill"]["available"] is False


class _Recorder:
    name = "prefix-recorder"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "好呀")
        yield ModelChunk("finished")


@pytest.mark.asyncio
async def test_product_path_keeps_system_prefix_identical_between_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_AUTO_MEMORY", "0")
    real_datetime = memory_module.datetime
    offset = [timedelta()]

    class Clock(real_datetime):  # type: ignore[misc, valid-type]
        @classmethod
        def now(cls, tz: Any = None) -> Any:
            return real_datetime.now(tz) + offset[0]

    monkeypatch.setattr(memory_module, "datetime", Clock)
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    model = _Recorder()
    hub = GatewayHub()
    companion = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=ToolOrchestrator(
            SQLiteToolProposalRepository(store), {}, catalog=_catalog()
        ),
        runtime_profile="candidate",
    )
    try:
        await companion.respond("s", "請記住我最喜歡冬天的海邊")
        offset[0] = timedelta(hours=7, minutes=13)
        await companion.respond("s", "你記得我最喜歡冬天的哪裡嗎")
    finally:
        await hub.shutdown()
    systems = [request.messages[0].content for request in model.requests]
    assert [request.messages[0].role for request in model.requests] == ["system", "system"]
    heads = [system.partition(TURN_CONTEXT_MARKER)[0] for system in systems]
    tails = [system.partition(TURN_CONTEXT_MARKER)[2] for system in systems]
    assert heads[0].encode() == heads[1].encode()
    assert tails[0] != tails[1]
    # The capability block is part of the stable prefix, once; per-turn data is not.
    assert heads[0].count(CAPABILITY_START) == 1 and heads[0].count(CAPABILITY_END) == 1
    assert CAPABILITY_START not in tails[0]
    assert CONTEXT_START.strip() in tails[1] and CONTEXT_START.strip() not in heads[1]
    assert "海邊" in tails[1] and "海邊" not in heads[1]
    assert "Current local date and time" in tails[1]


def test_capability_refresh_never_cuts_quoted_per_turn_data() -> None:
    from siro.services.presentation.integrated import _with_capability_block

    quoted = f"memory text quoting {CAPABILITY_START} and {CAPABILITY_END} markers"
    system = "stable rules\n" + TURN_CONTEXT_MARKER + quoted
    once = _with_capability_block(system, '{"v":1}')
    twice = _with_capability_block(once, '{"v":2}')
    head, _, tail = twice.partition(TURN_CONTEXT_MARKER)
    assert tail == quoted
    assert head.count(CAPABILITY_START) == 1 and '{"v":2}' in head and '{"v":1}' not in head
    # Prompts without the marker (older checkpoints) still get exactly one trailing block.
    legacy = _with_capability_block(_with_capability_block("old prompt", "a"), "b")
    assert legacy.count(CAPABILITY_START) == 1 and legacy.endswith(CAPABILITY_END)
