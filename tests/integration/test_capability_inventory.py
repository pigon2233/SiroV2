from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ToolCall, ToolDefinition
from siro.services.tools.orchestrator import (
    AvailabilityReason,
    AvailabilityState,
    ProposalState,
    SQLiteToolProposalRepository,
    ToolAvailability,
    ToolCatalog,
    ToolDescriptor,
    ToolMetadata,
    ToolOrchestrator,
    ToolUnavailableError,
)


def _definition(name: str = "fixture.read") -> ToolDefinition:
    return ToolDefinition(
        name,
        "Read a synthetic owner-approved text file.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )


async def _never_execute(arguments: dict[str, object]) -> object:
    raise AssertionError("capability discovery invoked an executor")


def _json_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_json_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_json_keys(item) for item in value))
    return set()


def test_capture_uses_one_readiness_result_for_inventory_and_model_tools() -> None:
    reads: dict[str, int] = {"fixture.read": 0, "fixture.hidden": 0}

    def readiness(name: str) -> bool:
        reads[name] += 1
        # A second read would contradict the first result within the same capture.
        return reads[name] % 2 == 1

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "fixture.read",
                _definition(),
                _never_execute,
                lambda: readiness("fixture.read"),
                "synthetic",
                "read",
            ),
            ToolDescriptor(
                "fixture.hidden",
                None,
                _never_execute,
                lambda: readiness("fixture.hidden"),
                "synthetic",
                "computer",
            ),
        )
    )

    first = catalog.capture()
    assert reads == {"fixture.read": 1, "fixture.hidden": 1}
    assert (
        tuple(item.name for item in first.definitions)
        == tuple(
            item["name"] for item in first.inventory if item["model_visible"] and item["available"]
        )
        == ("fixture.read",)
    )
    assert isinstance(first.inventory, tuple)
    assert isinstance(first.definitions, tuple)
    assert datetime.fromisoformat(first.checked_at).tzinfo is not None
    assert all(item["checked_at"] == first.checked_at for item in first.inventory)
    # Generating model context must consume this capture, not probe again.
    first.model_context()
    assert reads == {"fixture.read": 1, "fixture.hidden": 1}

    second = catalog.capture()
    assert reads == {"fixture.read": 2, "fixture.hidden": 2}
    assert second.definitions == ()
    assert not any(item["available"] for item in second.inventory)
    assert all(item["available"] for item in first.inventory)


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (AvailabilityState.UNAVAILABLE, AvailabilityReason.TOOLS_DISABLED),
        (AvailabilityState.UNKNOWN, AvailabilityReason.AVAILABILITY_CHECK_FAILED),
    ],
)
def test_nonavailable_typed_results_are_omitted_and_cannot_authorize(
    state: AvailabilityState, reason: AvailabilityReason
) -> None:
    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "fixture.read",
                _definition(),
                _never_execute,
                lambda: ToolAvailability(state, reason),
                "synthetic",
                "read",
            ),
        )
    )

    capture = catalog.capture()
    assert capture.definitions == ()
    row = capture.inventory[0]
    assert row["available"] is False
    assert row["availability"] == state.value
    assert row["reason_code"] == reason.value
    # Compatibility: model_visible still describes registration, not readiness.
    assert row["model_visible"] is True
    with pytest.raises(ToolUnavailableError):
        catalog.require("fixture.read", {"path": "synthetic.txt"})


def test_readiness_exception_is_unknown_without_private_error_content() -> None:
    canary = "synthetic-private-canary:https://private.invalid/?secret=fixture-only"
    reads = 0

    def readiness() -> bool:
        nonlocal reads
        reads += 1
        raise RuntimeError(canary)

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "fixture.read", _definition(), _never_execute, readiness, "synthetic", "read"
            ),
        )
    )
    capture = catalog.capture()
    assert reads == 1
    assert capture.definitions == ()
    assert capture.inventory[0]["availability"] == "unknown"
    assert capture.inventory[0]["reason_code"] == "availability_check_failed"
    assert canary not in json.dumps(capture.inventory)
    assert canary not in capture.model_context()
    assert reads == 1
    with pytest.raises(ToolUnavailableError) as raised:
        catalog.require("fixture.read", {"path": "synthetic.txt"})
    assert canary not in str(raised.value)
    assert reads == 2


def test_returned_schema_and_metadata_cannot_mutate_canonical_contract() -> None:
    definition = _definition()
    metadata = ToolMetadata(
        display_name="Synthetic text read",
        output_contract="UTF-8 text with bounded output; no write operation.",
        required_permissions=("owner approval", "synthetic read scope"),
        risk_level="observe/read-only",
        version="fixture-v1",
        provenance="synthetic test adapter",
        timeout_seconds=5,
        failure_behavior="No automatic retry after unknown outcome.",
    )
    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "fixture.read",
                definition,
                _never_execute,
                lambda: True,
                "synthetic",
                "read",
                metadata=metadata,
            ),
        )
    )
    capture = catalog.capture()
    row = capture.inventory[0]
    assert row["description"] == definition.description
    assert row["display_name"] == metadata.display_name
    permissions = row["required_permissions"]
    assert isinstance(permissions, (tuple, list))
    assert tuple(permissions) == metadata.required_permissions
    assert row["timeout_seconds"] == metadata.timeout_seconds
    assert row["output_contract"] == metadata.output_contract

    row["required_permissions"] = ["arbitrary host access"]
    row["risk_level"] = "no approval needed"
    schema = row["input_schema"]
    assert isinstance(schema, dict)
    schema["required"] = []
    capture.definitions[0].input_schema["required"] = []
    definition.input_schema["required"] = []

    fresh = catalog.capture().inventory[0]
    fresh_permissions = fresh["required_permissions"]
    assert isinstance(fresh_permissions, (tuple, list))
    assert tuple(fresh_permissions) == metadata.required_permissions
    assert fresh["risk_level"] == "observe/read-only"
    fresh_schema = fresh["input_schema"]
    assert isinstance(fresh_schema, dict)
    assert fresh_schema["required"] == ["path"]
    with pytest.raises(ValueError, match="invalid tool arguments"):
        catalog.require("fixture.read", {})
    catalog.require("fixture.read", {"path": "synthetic.txt"})


@pytest.mark.parametrize("enabled", [False, True])
def test_legacy_positional_descriptor_preserves_boolean_readiness_and_unknown_metadata(
    enabled: bool,
) -> None:
    async def contextual(arguments: dict[str, object], context: object) -> object:
        raise AssertionError("inventory invoked the contextual executor")

    # The seventh positional argument remains the existing contextual executor.
    descriptor = ToolDescriptor(
        "fixture.read",
        _definition(),
        _never_execute,
        lambda: enabled,
        "synthetic",
        "read",
        contextual,
    )
    catalog = ToolCatalog((descriptor,))
    capture = catalog.capture()
    row = capture.inventory[0]
    assert row["name"] == "fixture.read"
    assert row["available"] is enabled
    assert row["backend"] == "synthetic"
    assert row["effect"] == "read"
    assert row["model_visible"] is True
    assert row["availability"] == ("available" if enabled else "unavailable")
    assert row["reason_code"] == ("ready" if enabled else "not_ready")
    for field in (
        "display_name",
        "output_contract",
        "required_permissions",
        "risk_level",
        "version",
        "provenance",
        "timeout_seconds",
        "failure_behavior",
    ):
        assert row[field] is None
    assert bool(capture.definitions) is enabled
    if enabled:
        assert catalog.require("fixture.read", {"path": "synthetic.txt"}).contextual_executor is (
            contextual
        )


def test_model_context_excludes_hidden_and_schemas_and_is_not_a_grant() -> None:
    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "fixture.read",
                _definition(),
                _never_execute,
                lambda: ToolAvailability(
                    AvailabilityState.UNAVAILABLE, AvailabilityReason.BROWSER_EXECUTABLE_MISSING
                ),
                "synthetic",
                "read",
            ),
            ToolDescriptor(
                "fixture.hidden",
                None,
                _never_execute,
                lambda: True,
                "synthetic",
                "computer",
                metadata=ToolMetadata(display_name="hidden-private-canary"),
            ),
        )
    )
    capture = catalog.capture()
    text = capture.model_context()
    context = json.loads(text)
    assert context["authorizes_execution"] is False
    assert "fixture.read" in text
    assert "browser_executable_missing" in text
    assert "fixture.hidden" not in text
    assert "hidden-private-canary" not in text
    assert "input_schema" not in _json_keys(context)
    assert "output_contract" in _json_keys(context)
    assert capture.definitions == ()
    assert len(capture.inventory) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke_after_approval", [False, True])
async def test_stale_capture_cannot_bypass_revocation(
    tmp_path: Path, revoke_after_approval: bool
) -> None:
    enabled = True
    executed: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(arguments)
        return {"text": "synthetic"}

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "fixture.read", _definition(), execute, lambda: enabled, "synthetic", "read"
            ),
        )
    )
    store = SQLiteStore(tmp_path / "inventory.sqlite3")
    await store.initialize()
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    old_capture = catalog.capture()
    assert old_capture.inventory[0]["available"] is True
    call = ToolCall("synthetic-call", "fixture.read", {"path": "synthetic.txt"})

    if revoke_after_approval:
        proposal = await orchestrator.propose("synthetic-session", call, risk="observe/read-only")
        await orchestrator.resolve(
            proposal.proposal_id, approved=True, arguments=proposal.arguments
        )
        enabled = False
        result = await orchestrator.execute(proposal.proposal_id)
        assert result.state is ProposalState.FAILED
        assert result.error == "ToolUnavailableError"
    else:
        enabled = False
        with pytest.raises(ToolUnavailableError):
            await orchestrator.propose("synthetic-session", call, risk="observe/read-only")

    assert executed == []
    assert old_capture.inventory[0]["available"] is True
    assert catalog.capture().inventory[0]["available"] is False


@pytest.mark.asyncio
async def test_read_only_metadata_does_not_approve_a_proposal(tmp_path: Path) -> None:
    executed: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(arguments)
        return {"text": "synthetic"}

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "fixture.read",
                _definition(),
                execute,
                lambda: True,
                "synthetic",
                "read",
                metadata=ToolMetadata(
                    risk_level="observe/read-only", required_permissions=("owner approval",)
                ),
            ),
        )
    )
    store = SQLiteStore(tmp_path / "inventory.sqlite3")
    await store.initialize()
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    catalog.capture().model_context()
    proposal = await orchestrator.propose(
        "synthetic-session",
        ToolCall("synthetic-call", "fixture.read", {"path": "synthetic.txt"}),
        risk="observe/read-only",
    )
    assert proposal.state is ProposalState.PENDING
    with pytest.raises(ValueError):
        await orchestrator.execute(proposal.proposal_id)
    assert executed == []
    rejected = await orchestrator.resolve(
        proposal.proposal_id, approved=False, arguments=proposal.arguments
    )
    assert rejected.state is ProposalState.DENIED
    assert executed == []
