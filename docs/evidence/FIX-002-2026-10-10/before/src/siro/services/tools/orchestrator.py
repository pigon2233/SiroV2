"""Persistent, argument-bound lifecycle for model-proposed tool calls."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

from siro.core.authorization import argument_hash
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ToolCall, ToolDefinition
from siro.services.tools.execution import (
    ExecutionCancelled,
    ExecutionCleanupError,
    ExecutionContext,
)

ContextToolExecutor = Callable[[dict[str, object], ExecutionContext], Awaitable[object]]

ToolExecutor = Callable[[dict[str, object]], Awaitable[object]]


DEFAULT_MODEL_TOOLS = (
    ToolDefinition(
        "browser.navigate+read",
        "Open an HTTP or HTTPS URL and return its title and visible text.",
        {
            "type": "object",
            "properties": {"url": {"type": "string", "format": "uri"}},
            "required": ["url"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        "computer.execute",
        "Run a program directly with an argv array. Use this for general Linux computer tasks, "
        "including inspecting the system, downloading, installing, and launching applications. "
        "Never wrap the command in sh -c or another shell. Omit cwd unless the owner or a prior "
        "observation gave an exact directory. Set detach=true when launching a GUI application.",
        {
            "type": "object",
            "properties": {
                "argv": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "cwd": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
                "detach": {"type": "boolean"},
            },
            "required": ["argv"],
            "additionalProperties": False,
        },
    ),
)


# Candidate-only definitions; legacy DEFAULT_MODEL_TOOLS remains unchanged.
BROWSER_SESSION_TOOLS = (
    ToolDefinition(
        "browser.read",
        "Read the current session page and fresh screen_version.",
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    *(
        ToolDefinition(
            "browser." + action,
            "Use an exact semantic target and screen_version from the latest session readback. "
            "Returns fresh page readback; never reuse a stale version.",
            {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["button", "checkbox", "combobox", "heading", "link", "textbox"],
                    },
                    "name": {"type": "string"},
                    "screen_version": {"type": "string"},
                    **({"value": {"type": "string"}} if action == "fill" else {}),
                },
                "required": ["role", "name", "screen_version"]
                + (["value"] if action == "fill" else []),
                "additionalProperties": False,
            },
        )
        for action in ("fill", "click")
    ),
    ToolDefinition(
        "browser.close",
        "Close the session browser and discard its in-memory state.",
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
)


class ToolUnavailableError(RuntimeError):
    """An explicitly registered tool is not currently available."""


def _valid_arguments(value: object, schema: dict[str, object]) -> bool:
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return False
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            return False
        if any(key not in value for key in required):
            return False
        if schema.get("additionalProperties") is False and any(k not in properties for k in value):
            return False
        return all(
            k not in properties or _valid_arguments(v, properties[k]) for k, v in value.items()
        )
    if kind == "array":
        if not isinstance(value, list) or len(value) < int(str(schema.get("minItems", 0))):
            return False
        items = schema.get("items", {})
        return isinstance(items, dict) and all(_valid_arguments(v, items) for v in value)
    if kind == "string":
        if not isinstance(value, str):
            return False
        choices = schema.get("enum")
        if isinstance(choices, list) and value not in choices:
            return False
        if schema.get("format") == "uri":
            parsed = urlsplit(value)
            return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        return True
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return type(value) is int and int(str(schema.get("minimum", value))) <= value <= int(
            str(schema.get("maximum", value))
        )
    return kind is None


class AvailabilityState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class AvailabilityReason(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"
    TOOLS_DISABLED = "tools_disabled"
    BROWSER_EXECUTABLE_MISSING = "browser_executable_missing"
    WORKSPACE_UNAVAILABLE = "workspace_unavailable"
    AVAILABILITY_CHECK_FAILED = "availability_check_failed"


@dataclass(frozen=True, slots=True)
class ToolAvailability:
    state: AvailabilityState
    reason: AvailabilityReason


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    display_name: str | None = None
    output_contract: str | None = None
    required_permissions: tuple[str, ...] | None = None
    risk_level: str | None = None
    version: str | None = None
    provenance: str | None = None
    timeout_seconds: float | None = None
    failure_behavior: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCatalogSnapshot:
    definitions: tuple[ToolDefinition, ...]
    inventory: tuple[dict[str, object], ...]
    checked_at: str

    def model_context(self) -> str:
        # Schemas already travel as tools. Hidden compatibility handlers are not model tools.
        rows = [
            {k: v for k, v in row.items() if k not in {"input_schema", "checked_at"}}
            for row in self.inventory
            if row["model_visible"]
        ]
        return json.dumps(
            {
                "authorizes_execution": False,
                "instruction": "Registered capabilities for this request, not proof of success. "
                "Use only current request tool definitions; null means unknown. "
                "Unavailable tools must not be bypassed with another capability.",
                "capabilities": rows,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    name: str
    definition: ToolDefinition | None
    executor: ToolExecutor
    available: Callable[[], bool | ToolAvailability]
    backend: str
    effect: str
    contextual_executor: ContextToolExecutor | None = None
    metadata: ToolMetadata | None = None


class ToolCatalog:
    """A small facade over the existing registered capabilities, not a skill registry."""

    def __init__(self, descriptors: tuple[ToolDescriptor, ...]) -> None:
        self._descriptors: dict[str, ToolDescriptor] = {}
        for descriptor in descriptors:
            if descriptor.name in self._descriptors:
                raise ValueError("duplicate tool descriptor")
            if descriptor.definition is not None and descriptor.definition.name != descriptor.name:
                raise ValueError("tool descriptor name differs from schema")
            self._descriptors[descriptor.name] = replace(
                descriptor,
                definition=deepcopy(descriptor.definition),
                metadata=deepcopy(descriptor.metadata),
            )

    @staticmethod
    def _availability(descriptor: ToolDescriptor) -> ToolAvailability:
        try:
            result = descriptor.available()
        except Exception:
            # Readiness is descriptive. Never publish exception payloads or enable on failure.
            return ToolAvailability(
                AvailabilityState.UNKNOWN, AvailabilityReason.AVAILABILITY_CHECK_FAILED
            )
        if isinstance(result, ToolAvailability):
            return result
        if result is True:
            return ToolAvailability(AvailabilityState.AVAILABLE, AvailabilityReason.READY)
        if result is False:
            return ToolAvailability(AvailabilityState.UNAVAILABLE, AvailabilityReason.NOT_READY)
        return ToolAvailability(
            AvailabilityState.UNKNOWN, AvailabilityReason.AVAILABILITY_CHECK_FAILED
        )

    def require(self, name: str, arguments: dict[str, object]) -> ToolDescriptor:
        descriptor = self._descriptors.get(name)
        if descriptor is None:
            raise ValueError("unsupported tool capability")
        if self._availability(descriptor).state is not AvailabilityState.AVAILABLE:
            raise ToolUnavailableError("tool is unavailable")
        if descriptor.definition is not None and not _valid_arguments(
            arguments, descriptor.definition.input_schema
        ):
            raise ValueError("invalid tool arguments")
        return descriptor

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return self.capture().definitions

    def snapshot(self) -> list[dict[str, object]]:
        return list(self.capture().inventory)

    def capture(self) -> ToolCatalogSnapshot:
        checked_at = datetime.now(UTC).isoformat()
        definitions: list[ToolDefinition] = []
        inventory: list[dict[str, object]] = []
        for d in self._descriptors.values():
            status = self._availability(d)
            available = status.state is AvailabilityState.AVAILABLE
            definition = deepcopy(d.definition)
            if available and definition is not None:
                definitions.append(definition)
            inventory.append(
                {
                    "name": d.name,
                    "available": available,
                    "backend": d.backend,
                    "effect": d.effect,
                    "model_visible": d.definition is not None,
                    "availability": status.state.value,
                    "reason_code": status.reason.value,
                    "checked_at": checked_at,
                    "description": definition.description if definition is not None else None,
                    "input_schema": deepcopy(definition.input_schema) if definition else None,
                    **asdict(d.metadata or ToolMetadata()),
                }
            )
        return ToolCatalogSnapshot(tuple(definitions), tuple(inventory), checked_at)


class ProposalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class ToolProposal:
    proposal_id: str
    session_id: str
    call_id: str
    capability: str
    arguments: dict[str, object]
    arguments_hash: str
    risk: str
    state: ProposalState
    observation: object | None = None
    error: str | None = None


class SQLiteToolProposalRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def put(self, proposal: ToolProposal, *, run_id: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()

        def write(connection: sqlite3.Connection) -> None:
            connection.execute(
                "INSERT INTO tool_proposals(proposal_id, session_id, call_id, capability, "
                "arguments_json, arguments_hash, risk, state, observation_json, error, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal.proposal_id,
                    proposal.session_id,
                    proposal.proposal_id if run_id is not None else proposal.call_id,
                    proposal.capability,
                    json.dumps(proposal.arguments, separators=(",", ":"), sort_keys=True),
                    proposal.arguments_hash,
                    proposal.risk,
                    proposal.state.value,
                    None,
                    None,
                    now,
                    now,
                ),
            )

            if run_id is not None:
                call = connection.execute(
                    "SELECT j.* FROM run_journal_calls j JOIN agent_runs r ON r.run_id=j.run_id "
                    "JOIN run_journal n ON n.run_id=j.run_id "
                    "WHERE j.run_id=? AND j.call_id=? AND r.session_id=? AND n.status='active'",
                    (run_id, proposal.call_id, proposal.session_id),
                ).fetchone()
                if (
                    call is None
                    or call["proposal_id"] is not None
                    or call["capability"] != proposal.capability
                    or json.loads(call["arguments_json"]) != proposal.arguments
                ):
                    raise ValueError("proposal has no unbound matching journal call")
                connection.execute(
                    "UPDATE run_journal_calls SET proposal_id=? WHERE run_id=? AND call_id=?",
                    (proposal.proposal_id, run_id, proposal.call_id),
                )

        await self._store.run_transaction(write)

    @staticmethod
    def _read_row(connection: sqlite3.Connection, proposal_id: str) -> sqlite3.Row | None:
        row = connection.execute(
            "SELECT * FROM tool_proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            return None
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='run_journal_calls'"
        ).fetchone():
            bindings = connection.execute(
                "SELECT j.call_id FROM run_journal_calls j JOIN agent_runs r ON r.run_id=j.run_id "
                "WHERE j.proposal_id=? AND r.session_id=?",
                (proposal_id, row["session_id"]),
            ).fetchall()
            if len(bindings) > 1:
                raise ValueError("ambiguous proposal ownership")
            if bindings:
                return cast(
                    sqlite3.Row,
                    connection.execute(
                        "SELECT p.*, ? AS provider_call_id FROM tool_proposals p "
                        "WHERE proposal_id=?",
                        (bindings[0][0], proposal_id),
                    ).fetchone(),
                )
        return cast(sqlite3.Row, row)

    async def get(self, proposal_id: str) -> ToolProposal | None:
        def read(connection: sqlite3.Connection) -> sqlite3.Row | None:
            return self._read_row(connection, proposal_id)

        row = await self._store.run_transaction(read)
        return None if row is None else self._from_row(row)

    async def journal_owner(self, proposal: ToolProposal) -> str | None:
        def read(c: sqlite3.Connection) -> str | None:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE name='run_journal'").fetchone():
                return None
            rows = c.execute(
                "SELECT j.run_id,j.capability,j.arguments_json FROM run_journal_calls j "
                "JOIN agent_runs r ON r.run_id=j.run_id "
                "WHERE j.proposal_id=? AND r.session_id=?",
                (proposal.proposal_id, proposal.session_id),
            ).fetchall()
            if not rows:
                # Old insert-before-bind rows only: never guess an owner among multiple runs.
                rows = c.execute(
                    "SELECT j.run_id,j.capability,j.arguments_json FROM run_journal_calls j "
                    "JOIN agent_runs r ON r.run_id=j.run_id WHERE r.session_id=? "
                    "AND j.call_id=? AND j.proposal_id IS NULL",
                    (proposal.session_id, proposal.call_id),
                ).fetchall()
            if len(rows) > 1:
                raise ValueError("ambiguous proposal ownership")
            if rows:
                if (
                    rows[0]["capability"] != proposal.capability
                    or json.loads(rows[0]["arguments_json"]) != proposal.arguments
                ):
                    raise ValueError("proposal ownership payload mismatch")
                return str(rows[0]["run_id"])
            return None

        return await self._store.run_transaction(read)

    async def transition(
        self,
        proposal_id: str,
        expected: ProposalState,
        target: ProposalState,
        *,
        observation: object | None = None,
        error: str | None = None,
    ) -> ToolProposal:
        observation_json = (
            json.dumps(observation, separators=(",", ":"), sort_keys=True)
            if observation is not None
            else None
        )

        def write(connection: sqlite3.Connection) -> sqlite3.Row:
            cursor = connection.execute(
                "UPDATE tool_proposals SET state = ?, observation_json = ?, error = ?, "
                "updated_at = ? WHERE proposal_id = ? AND state = ?",
                (
                    target.value,
                    observation_json,
                    error,
                    datetime.now(UTC).isoformat(),
                    proposal_id,
                    expected.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("tool proposal state changed or does not exist")
            row = self._read_row(connection, proposal_id)
            assert row is not None
            return row

        return self._from_row(await self._store.run_transaction(write))

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ToolProposal:
        raw_observation = row["observation_json"]
        return ToolProposal(
            str(row["proposal_id"]),
            str(row["session_id"]),
            str(
                row["provider_call_id"]
                if "provider_call_id" in tuple(row.keys())
                else row["call_id"]
            ),
            str(row["capability"]),
            json.loads(row["arguments_json"]),
            str(row["arguments_hash"]),
            str(row["risk"]),
            ProposalState(row["state"]),
            json.loads(raw_observation) if raw_observation else None,
            str(row["error"]) if row["error"] is not None else None,
        )


class ToolOrchestrator:
    def __init__(
        self,
        repository: SQLiteToolProposalRepository,
        executors: dict[str, ToolExecutor],
        *,
        contextual_executors: dict[str, ContextToolExecutor] | None = None,
        catalog: ToolCatalog | None = None,
    ) -> None:
        self.journal_hook: Callable[[str, str, str, object], Awaitable[None]] | None = None
        self._repository = repository
        self.catalog = catalog
        self._executors = executors.copy()
        self._contextual_executors = (contextual_executors or {}).copy()
        self._run_contexts: dict[str, ExecutionContext] = {}
        self._proposal_contexts: dict[str, ExecutionContext] = {}
        self._active: dict[str, set[asyncio.Task[object]]] = {}
        self._argument_tasks: set[asyncio.Task[object]] = set()

    def model_tools(self) -> tuple[ToolDefinition, ...]:
        if self.catalog is not None:
            return self.catalog.definitions()
        return tuple(deepcopy(d) for d in DEFAULT_MODEL_TOOLS if d.name in self._executors)

    def tool_status(self) -> list[dict[str, object]]:
        if self.catalog is not None:
            return self.catalog.snapshot()
        visible = {d.name for d in DEFAULT_MODEL_TOOLS}
        return [
            {
                "name": name,
                "available": True,
                "backend": "legacy",
                "effect": "legacy",
                "model_visible": name in visible,
            }
            for name in self._executors
        ]

    def start_run(self, run_id: str, session_id: str) -> None:
        self._run_contexts[run_id] = ExecutionContext(run_id, session_id, run_id)

    def bind_proposal(self, run_id: str, proposal: ToolProposal) -> None:
        context = self._run_contexts[run_id]
        if context.session_id != proposal.session_id:
            raise ValueError("proposal belongs to another session")
        self._proposal_contexts[proposal.proposal_id] = replace(
            context, proposal_id=proposal.proposal_id, call_id=proposal.call_id
        )

    def is_fenced(self, proposal_id: str) -> bool:
        context = self._proposal_contexts.get(proposal_id)
        return context is not None and context.cancellation.cancelled

    async def cancel_run(self, run_id: str) -> None:
        context = self._run_contexts.get(run_id)
        if context is None:
            return
        context.cancellation.cancel()  # fence new dispatch before the first await
        active = tuple(self._active.get(run_id, ()))
        argument_tasks = {task for task in active if task in self._argument_tasks}
        for task in argument_tasks:
            if not task.done() and not task.cancelling():
                task.cancel()
        if active:
            try:
                async with asyncio.timeout(4.75):
                    outcomes = await asyncio.shield(asyncio.gather(*active, return_exceptions=True))
            except TimeoutError as error:
                raise ExecutionCleanupError("run cleanup exceeded its deadline") from error
            if any(
                isinstance(outcome, ExecutionCleanupError)
                or (
                    task in argument_tasks
                    and isinstance(outcome, Exception)
                    and not isinstance(outcome, ExecutionCancelled)
                )
                for task, outcome in zip(active, outcomes, strict=True)
            ):
                raise ExecutionCleanupError("run handler cleanup failed")

    async def get(self, proposal_id: str) -> ToolProposal | None:
        return await self._repository.get(proposal_id)

    async def propose(
        self, session_id: str, call: ToolCall, *, risk: str, run_id: str | None = None
    ) -> ToolProposal:
        if self.catalog is not None:
            self.catalog.require(call.name, call.arguments)
        elif call.name not in self._executors:
            raise ValueError(f"unsupported tool capability: {call.name}")
        proposal = ToolProposal(
            str(uuid4()),
            session_id,
            call.call_id,
            call.name,
            call.arguments,
            argument_hash(call.arguments),
            risk,
            ProposalState.PENDING,
        )
        if run_id is not None and self._run_contexts[run_id].session_id != session_id:
            raise ValueError("proposal belongs to another session")
        await self._repository.put(proposal, run_id=run_id)
        return proposal

    async def resolve(
        self,
        proposal_id: str,
        *,
        approved: bool,
        arguments: dict[str, object],
    ) -> ToolProposal:
        proposal = await self._repository.get(proposal_id)
        if proposal is None or proposal.state is not ProposalState.PENDING:
            raise ValueError("pending tool proposal was not found")
        if argument_hash(arguments) != proposal.arguments_hash:
            raise PermissionError("tool arguments changed after proposal")
        if not approved:
            return await self._repository.transition(
                proposal_id, ProposalState.PENDING, ProposalState.DENIED
            )
        return await self._repository.transition(
            proposal_id, ProposalState.PENDING, ProposalState.APPROVED
        )

    async def discard_unstarted(self, proposal_id: str) -> None:
        """Fence a queued proposal; running effects are owned by the execution backend."""
        proposal = await self._repository.get(proposal_id)
        if proposal is None or proposal.state not in {
            ProposalState.PENDING,
            ProposalState.APPROVED,
        }:
            return
        try:
            await self._repository.transition(proposal_id, proposal.state, ProposalState.DENIED)
        except ValueError:
            # A concurrent execute won the state transition; do not claim it was stopped.
            return

    async def execute(self, proposal_id: str) -> ToolProposal:
        original = await self._repository.get(proposal_id)
        if original is None:
            raise ValueError("tool proposal was not found")
        owner = await self._repository.journal_owner(original)
        context = self._proposal_contexts.get(proposal_id)
        if owner is not None and (
            context is None or context.run_id != owner or self.journal_hook is None
        ):
            raise ValueError("recovered proposal cannot be replayed")
        proposal = await self._repository.transition(
            proposal_id, ProposalState.APPROVED, ProposalState.RUNNING
        )
        context = self._proposal_contexts.get(proposal_id)
        try:
            descriptor = (
                self.catalog.require(proposal.capability, proposal.arguments)
                if self.catalog is not None
                else None
            )
            executor = (
                descriptor.executor
                if descriptor is not None
                else self._executors[proposal.capability]
            )
            if context is not None:
                context.check()
            contextual = (
                descriptor.contextual_executor
                if descriptor is not None
                else self._contextual_executors.get(proposal.capability)
            )
            if context is not None:

                async def invoke() -> object:
                    if self.catalog is not None:
                        self.catalog.require(proposal.capability, proposal.arguments)
                    context.check()
                    if self.journal_hook is not None:
                        await self.journal_hook(context.run_id, proposal.call_id, "dispatch", None)
                    context.check()
                    if contextual is not None:
                        return await contextual(
                            proposal.arguments, replace(context, authorized=True)
                        )
                    result = await executor(proposal.arguments)
                    context.check()  # A handler suppressing cancellation cannot report success.
                    return result

                task = asyncio.create_task(invoke())
                active = self._active.setdefault(context.run_id, set())
                active.add(task)
                if contextual is None:
                    self._argument_tasks.add(task)
                # Keep ownership even when a waiting request is cancelled or cleanup times out.
                task.add_done_callback(active.discard)
                task.add_done_callback(self._argument_tasks.discard)
                try:
                    observation = await asyncio.shield(task)
                except asyncio.CancelledError:
                    if context.cancellation.cancelled:
                        raise ExecutionCancelled("run cancelled") from None
                    raise
            else:
                if context is not None and self.journal_hook is not None:
                    await self.journal_hook(context.run_id, proposal.call_id, "dispatch", None)
                    context.check()
                observation = await executor(proposal.arguments)
        except asyncio.CancelledError:
            if context is not None:
                await self.cancel_run(context.run_id)
                await self._repository.transition(
                    proposal_id,
                    ProposalState.RUNNING,
                    ProposalState.FAILED,
                    error="ExecutionCancelled",
                )
            raise
        except Exception as error:
            if (
                context is not None
                and self.journal_hook is not None
                and not context.cancellation.cancelled
            ):
                await self.journal_hook(
                    context.run_id, proposal.call_id, "observation", {"error": type(error).__name__}
                )
            return await self._repository.transition(
                proposal_id,
                ProposalState.RUNNING,
                ProposalState.FAILED,
                error=type(error).__name__,
            )
        if (
            context is not None
            and self.journal_hook is not None
            and not context.cancellation.cancelled
        ):
            await self.journal_hook(context.run_id, proposal.call_id, "observation", observation)
        return await self._repository.transition(
            proposal_id,
            ProposalState.RUNNING,
            ProposalState.COMPLETED,
            observation=observation,
        )
