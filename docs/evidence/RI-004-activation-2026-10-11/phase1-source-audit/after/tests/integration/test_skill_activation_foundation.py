from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from dataclasses import replace
from pathlib import Path

import pytest

import siro.persistence.skills as registry_module
from siro.core.skills import InstalledSkill, SkillApprovalRequired, load_skill
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ToolCall, ToolDefinition
from siro.services.tools.orchestrator import (
    ProposalState,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolDescriptor,
    ToolMetadata,
    ToolOrchestrator,
    ToolUnavailableError,
)
from siro.services.tools.skill_candidates import SkillCandidatePreparer


def package(root: Path, *, suffix: str = "original") -> InstalledSkill:
    root.mkdir()
    manifest = {
        "id": "fixture.activation",
        "version": "1.0.0",
        "contract_version": 1,
        "description": "Synthetic activation foundation fixture",
        "entrypoint": "python:plugin:run",
        "input_schema": "input.json",
        "output_schema": "output.json",
        "permissions": [],
        "risk": "observe",
        "timeout_ms": 1000,
        "concurrency": 1,
        "resource_limits": {"memory_mb": 64, "output_bytes": 4096, "cpu_seconds": 1},
        "network": "denied",
        "idempotency": "read_only",
        "cancellation": "process",
        "compensation": "none",
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    for name in ("input.json", "output.json"):
        (root / name).write_text(json.dumps(schema), encoding="utf-8")
    (root / "plugin.py").write_text(
        f"# {suffix}\ndef run(arguments):\n    return arguments\n", encoding="utf-8"
    )
    return load_skill(root)


async def registry_at(tmp_path: Path) -> tuple[SQLiteSkillRegistry, SQLiteStore]:
    store = SQLiteStore(tmp_path / "synthetic.sqlite3")
    await store.initialize()
    return SQLiteSkillRegistry(store), store


async def rows(store: SQLiteStore) -> list[tuple[object, ...]]:
    return await store.run_transaction(
        lambda connection: [
            tuple(row)
            for row in connection.execute(
                "SELECT skill_id, version, manifest_hash, state, path_ref FROM skills "
                "ORDER BY skill_id, version"
            ).fetchall()
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_absent_install_records_exact_identity_and_requested_state(
    tmp_path: Path, enabled: bool
) -> None:
    skill = package(tmp_path / "package")
    registry, store = await registry_at(tmp_path)
    assert await registry.install_if_absent(skill, enabled=enabled) is True
    assert await rows(store) == [
        (
            skill.manifest.id,
            skill.manifest.version,
            skill.manifest_hash,
            "enabled" if enabled else "disabled",
            str(skill.root),
        )
    ]
    assert (
        await registry.is_enabled(skill.manifest.id, skill.manifest.version, identity=skill)
        is enabled
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("conflict", ["identical", "other-root", "other-bytes"])
async def test_install_conflict_preserves_entire_existing_row(
    tmp_path: Path, enabled: bool, conflict: str
) -> None:
    original = package(tmp_path / "original")
    replacement = (
        original
        if conflict == "identical"
        else package(
            tmp_path / "replacement", suffix="changed" if conflict == "other-bytes" else "original"
        )
    )
    registry, store = await registry_at(tmp_path)
    await registry.install(original, enabled=enabled)
    before = await rows(store)
    assert await registry.install_if_absent(replacement, enabled=not enabled) is False
    assert await rows(store) == before


@pytest.mark.asyncio
async def test_concurrent_absent_installs_have_one_exact_winner(tmp_path: Path) -> None:
    first = package(tmp_path / "first")
    second = package(tmp_path / "second", suffix="different")
    registry, store = await registry_at(tmp_path)
    results = await asyncio.gather(
        registry.install_if_absent(first), registry.install_if_absent(second, enabled=True)
    )
    assert sorted(results) == [False, True]
    winner = first if results[0] else second
    assert await rows(store) == [
        (
            winner.manifest.id,
            winner.manifest.version,
            winner.manifest_hash,
            "disabled" if results[0] else "enabled",
            str(winner.root),
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("forgery", ["hash", "input", "output", "manifest", "changed-source"])
async def test_absent_install_rejects_unverified_or_type_ambiguous_metadata(
    tmp_path: Path, forgery: str
) -> None:
    skill = package(tmp_path / "package")
    if forgery == "hash":
        skill = replace(skill, manifest_hash="siro-skill-package-v1:" + "0" * 64)
    elif forgery == "input":
        skill = replace(skill, input_schema={**skill.input_schema, "additionalProperties": 0})
    elif forgery == "output":
        skill = replace(skill, output_schema={**skill.output_schema, "additionalProperties": 0})
    elif forgery == "manifest":
        skill = replace(skill, manifest=skill.manifest.model_copy(update={"concurrency": True}))
    else:
        (skill.root / "plugin.py").write_text("def run(arguments): return {}\n")
    registry, store = await registry_at(tmp_path)
    with pytest.raises(SkillApprovalRequired, match="package verification and approval"):
        await registry.install_if_absent(skill)
    assert await rows(store) == []


@pytest.mark.asyncio
async def test_absent_install_verification_runs_off_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill = package(tmp_path / "package")
    registry, _ = await registry_at(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    verifier_threads: list[int] = []
    original_load = load_skill

    def blocked_load(root: Path) -> InstalledSkill:
        verifier_threads.append(threading.get_ident())
        entered.set()
        if not release.wait(2):
            raise AssertionError("synthetic verifier release missing")
        return original_load(root)

    monkeypatch.setattr(registry_module, "load_skill", blocked_load)
    task = asyncio.create_task(registry.install_if_absent(skill))
    try:
        async with asyncio.timeout(1):
            while not entered.is_set():
                await asyncio.sleep(0.001)
            assert not task.done()
            assert verifier_threads != [threading.get_ident()]
    finally:
        release.set()
        await task


@pytest.mark.asyncio
async def test_legacy_install_retains_explicit_upsert_compatibility(tmp_path: Path) -> None:
    original = package(tmp_path / "original")
    replacement = package(tmp_path / "replacement", suffix="legacy replacement")
    registry, store = await registry_at(tmp_path)
    await registry.install(original, enabled=True)
    await registry.install(replacement)
    assert await rows(store) == [
        (
            replacement.manifest.id,
            replacement.manifest.version,
            replacement.manifest_hash,
            "disabled",
            str(replacement.root),
        )
    ]
    assert await registry.set_enabled(
        replacement.manifest.id, replacement.manifest.version, enabled=True
    )


@pytest.mark.asyncio
async def test_expected_identity_can_enable_then_disable_exact_row(tmp_path: Path) -> None:
    skill = package(tmp_path / "package")
    registry, _ = await registry_at(tmp_path)
    await registry.install(skill)
    for enabled in (True, False):
        assert await registry.set_enabled(
            skill.manifest.id, skill.manifest.version, enabled=enabled, identity=skill
        )
        assert (
            await registry.is_enabled(skill.manifest.id, skill.manifest.version, identity=skill)
            is enabled
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_installed_identity_is_independent_of_enabled_state_and_source_io(
    tmp_path: Path, enabled: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill = package(tmp_path / "package")
    registry, _ = await registry_at(tmp_path)
    await registry.install(skill, enabled=enabled)

    def forbidden(root: Path) -> InstalledSkill:
        raise AssertionError("registry identity query performed source verification")

    monkeypatch.setattr(registry_module, "load_skill", forbidden)
    (skill.root / "plugin.py").unlink()
    assert await registry.is_installed(skill.manifest.id, skill.manifest.version, identity=skill)


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["id", "version", "hash", "root", "missing"])
async def test_installed_identity_rejects_mismatched_or_missing_row(
    tmp_path: Path, mismatch: str
) -> None:
    skill = package(tmp_path / "package")
    registry, _ = await registry_at(tmp_path)
    await registry.install(skill)
    identity = skill
    query_id = skill.manifest.id
    if mismatch in {"id", "version"}:
        identity = replace(
            skill,
            manifest=skill.manifest.model_copy(
                update={mismatch: "fixture.other" if mismatch == "id" else "2.0.0"}
            ),
        )
    elif mismatch == "hash":
        identity = replace(skill, manifest_hash="siro-skill-package-v1:" + "0" * 64)
    elif mismatch == "root":
        identity = replace(skill, root=tmp_path / "other-root")
    else:
        query_id = "fixture.missing"
    assert not await registry.is_installed(query_id, skill.manifest.version, identity=identity)


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("mismatch", ["id", "version", "hash", "root"])
async def test_expected_identity_mismatch_cannot_enable_or_disable_current_row(
    tmp_path: Path, enabled: bool, mismatch: str
) -> None:
    skill = package(tmp_path / "package")
    identity = skill
    if mismatch in {"id", "version"}:
        identity = replace(
            skill,
            manifest=skill.manifest.model_copy(
                update={mismatch: "fixture.other" if mismatch == "id" else "2.0.0"}
            ),
        )
    elif mismatch == "hash":
        identity = replace(skill, manifest_hash="siro-skill-package-v1:" + "0" * 64)
    else:
        identity = replace(skill, root=tmp_path / "other-root")
    registry, store = await registry_at(tmp_path)
    await registry.install(skill, enabled=not enabled)
    before = await rows(store)
    assert not await registry.set_enabled(
        skill.manifest.id, skill.manifest.version, enabled=enabled, identity=identity
    )
    assert await rows(store) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_old_approval_cannot_change_same_version_replacement(
    tmp_path: Path, enabled: bool
) -> None:
    old = package(tmp_path / "old")
    current = package(tmp_path / "current", suffix="replacement")
    registry, store = await registry_at(tmp_path)
    await registry.install(old, enabled=enabled)
    await registry.install(current, enabled=not enabled)
    before = await rows(store)
    assert not await registry.set_enabled(
        old.manifest.id, old.manifest.version, enabled=enabled, identity=old
    )
    assert await rows(store) == before


@pytest.mark.asyncio
async def test_matching_disable_remains_possible_after_package_corruption(tmp_path: Path) -> None:
    skill = package(tmp_path / "package")
    registry, _ = await registry_at(tmp_path)
    await registry.install(skill, enabled=True)
    (skill.root / "plugin.py").unlink()
    assert await registry.set_enabled(
        skill.manifest.id, skill.manifest.version, enabled=False, identity=skill
    )
    with pytest.raises(SkillApprovalRequired):
        await registry.set_enabled(
            skill.manifest.id, skill.manifest.version, enabled=True, identity=skill
        )


@pytest.mark.asyncio
async def test_expected_enable_cas_rejects_replacement_during_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = package(tmp_path / "old")
    current = package(tmp_path / "current", suffix="replacement")
    registry, store = await registry_at(tmp_path)
    await registry.install(old)
    original_load = load_skill

    def replace_while_verifying(root: Path) -> InstalledSkill:
        verified = original_load(root)
        with sqlite3.connect(store.path) as connection:
            connection.execute(
                "UPDATE skills SET manifest_hash=?, path_ref=?, state='disabled' "
                "WHERE skill_id=? AND version=?",
                (current.manifest_hash, str(current.root), old.manifest.id, old.manifest.version),
            )
        return verified

    monkeypatch.setattr(registry_module, "load_skill", replace_while_verifying)
    assert not await registry.set_enabled(
        old.manifest.id, old.manifest.version, enabled=True, identity=old
    )
    assert await rows(store) == [
        (
            current.manifest.id,
            current.manifest.version,
            current.manifest_hash,
            "disabled",
            str(current.root),
        )
    ]


async def echo(arguments: dict[str, object]) -> object:
    return arguments


def descriptor(name: str = "text.checklist.parse", *, enabled: bool = True) -> ToolDescriptor:
    return ToolDescriptor(
        name,
        ToolDefinition(
            name,
            "Synthetic read-only activation fixture",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        ),
        echo,
        lambda: enabled,
        "python-stdlib-single",
        "read",
        metadata=ToolMetadata(provenance="synthetic-only"),
    )


@pytest.mark.asyncio
async def test_registration_reaches_existing_orchestrator_without_fallback(tmp_path: Path) -> None:
    catalog = ToolCatalog(())
    old_snapshot = catalog.capture()
    store = SQLiteStore(tmp_path / "catalog.sqlite3")
    await store.initialize()

    async def forbidden(arguments: dict[str, object]) -> object:
        raise AssertionError("legacy executor bypassed registered descriptor")

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"text.checklist.parse": forbidden}, catalog=catalog
    )
    assert orchestrator.model_tools() == ()
    catalog.register(descriptor())
    assert old_snapshot.definitions == ()
    assert old_snapshot.inventory == ()
    assert [item.name for item in orchestrator.model_tools()] == ["text.checklist.parse"]
    proposal = await orchestrator.propose(
        "synthetic-session",
        ToolCall("synthetic-call", "text.checklist.parse", {"text": "hello"}),
        risk="observe",
    )
    await orchestrator.resolve(proposal.proposal_id, approved=True, arguments=proposal.arguments)
    result = await orchestrator.execute(proposal.proposal_id)
    assert result.state == ProposalState.COMPLETED
    assert result.observation == {"text": "hello"}


@pytest.mark.parametrize("duplicate", ["identical", "different"])
def test_registration_refuses_duplicates_without_replacing_executor_or_readiness(
    duplicate: str,
) -> None:
    original = descriptor()
    catalog = ToolCatalog((original,))
    with pytest.raises(ValueError, match="duplicate tool descriptor"):
        catalog.register(original if duplicate == "identical" else descriptor(enabled=False))
    assert catalog.require(original.name, {"text": "kept"}).executor is echo
    assert catalog.snapshot()[0]["available"] is True


def test_registration_refuses_schema_name_mismatch_without_partial_addition() -> None:
    catalog = ToolCatalog((descriptor("original.tool"),))
    invalid = replace(descriptor(), definition=descriptor("other.name").definition)
    with pytest.raises(ValueError, match="tool descriptor name differs from schema"):
        catalog.register(invalid)
    assert [item["name"] for item in catalog.snapshot()] == ["original.tool"]


def test_registration_copies_mutable_schema_and_snapshot_payloads() -> None:
    candidate = descriptor()
    assert candidate.definition is not None
    catalog = ToolCatalog(())
    catalog.register(candidate)
    candidate.definition.input_schema["required"] = []
    catalog.definitions()[0].input_schema["required"] = []
    catalog.snapshot()[0]["input_schema"] = {}
    with pytest.raises(ValueError, match="invalid tool arguments"):
        catalog.require(candidate.name, {})


def test_registration_is_copy_on_write_during_synchronous_capture() -> None:
    added = False
    catalog = ToolCatalog(())

    def available() -> bool:
        nonlocal added
        if not added:
            added = True
            catalog.register(descriptor("second.tool"))
        return True

    catalog.register(replace(descriptor("first.tool"), available=available))
    first = catalog.capture()
    assert [row["name"] for row in first.inventory] == ["first.tool"]
    assert [row["name"] for row in catalog.capture().inventory] == ["first.tool", "second.tool"]


@pytest.mark.asyncio
async def test_disabled_registration_remains_known_and_cannot_trigger_regeneration() -> None:
    catalog = ToolCatalog(())
    catalog.register(descriptor(enabled=False))
    assert catalog.definitions() == ()
    with pytest.raises(ToolUnavailableError):
        catalog.require("text.checklist.parse", {"text": "blocked"})
    preparer = SkillCandidatePreparer(catalog)
    try:
        result = await preparer.prepare("text.checklist.parse")
        assert result["status"] == "existing_unavailable"
        assert result["installed"] is False
        assert result["enabled"] is False
    finally:
        await preparer.close()
