from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import siro.adapters.skill_worker as worker_module
import siro.core.skills as skills_module
from siro.adapters.skill_worker import SkillDisabled, SkillDispatcher, WorkerSupervisor
from siro.core.skills import InstalledSkill, load_skill
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore


def package(root: Path) -> InstalledSkill:
    root.mkdir()
    values = {
        "id": "fixture.package",
        "version": "1.0.0",
        "contract_version": 1,
        "description": "Synthetic package identity fixture",
        "entrypoint": "python:plugin:run",
        "input_schema": "input.json",
        "output_schema": "output.json",
        "permissions": [],
        "risk": "observe",
        "timeout_ms": 1000,
        "concurrency": 1,
        "resource_limits": {"memory_mb": 64, "output_bytes": 1024, "cpu_seconds": 1},
        "network": "denied",
        "idempotency": "read_only",
        "cancellation": "process",
        "compensation": "none",
    }
    (root / "manifest.json").write_text(json.dumps(values))
    schema = {"type": "object", "properties": {"text": {"type": "string"}}}
    for name in ("input.json", "output.json"):
        (root / name).write_text(json.dumps(schema))
    (root / "plugin.py").write_text(
        "def run(arguments):\n    import helper\n    assert helper.VALUE == 'approved'\n"
        "    return arguments\n"
    )
    (root / "helper.py").write_text("VALUE = 'approved'\n")
    (root / "requirements.txt").write_text("# synthetic dependency metadata\n")
    (root / "data.txt").write_text("approved data")
    return load_skill(root)


class RecordingSupervisor(WorkerSupervisor):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[InstalledSkill] = []

    async def execute(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        self.calls.append(skill)
        return {"text": (skill.root / "plugin.py").read_text()}


async def approved(
    tmp_path: Path,
) -> tuple[InstalledSkill, SQLiteSkillRegistry, SQLiteStore, RecordingSupervisor, SkillDispatcher]:
    skill = package(tmp_path / "package")
    store = SQLiteStore(tmp_path / "synthetic.sqlite3")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    await registry.install(skill, enabled=True)
    supervisor = RecordingSupervisor()
    return skill, registry, store, supervisor, SkillDispatcher(registry, supervisor)


@pytest.mark.parametrize("name", ["plugin.py", "helper.py", "requirements.txt", "data.txt"])
def test_digest_binds_all_package_content(tmp_path: Path, name: str) -> None:
    skill = package(tmp_path / "package")
    (skill.root / name).write_text("unapproved replacement")
    assert load_skill(skill.root).manifest_hash != skill.manifest_hash


@pytest.mark.parametrize("change", ["add", "delete", "rename", "executable"])
def test_file_set_paths_and_executable_bits_are_bound(tmp_path: Path, change: str) -> None:
    skill = package(tmp_path / "package")
    helper = skill.root / "helper.py"
    if change == "add":
        (skill.root / "extra.py").write_text("VALUE = 'new'\n")
    elif change == "delete":
        helper.unlink()
    elif change == "rename":
        helper.rename(skill.root / "renamed.py")
    else:
        helper.chmod(helper.stat().st_mode | 0o100)
    assert load_skill(skill.root).manifest_hash != skill.manifest_hash


def test_digest_is_stable_versioned_and_transient_cache_is_not_delivered(tmp_path: Path) -> None:
    skill = package(tmp_path / "package")
    assert skill.manifest_hash.startswith("siro-skill-package-v1:")
    assert load_skill(skill.root).manifest_hash == skill.manifest_hash
    cache = skill.root / "__pycache__"
    cache.mkdir()
    (cache / "plugin.cpython-314.pyc").write_bytes(b"untrusted transient cache")
    assert load_skill(skill.root).manifest_hash == skill.manifest_hash
    other = tmp_path / "other"
    shutil.copytree(skill.root, other)
    assert load_skill(other).manifest_hash == skill.manifest_hash


@pytest.mark.parametrize("kind", ["file", "directory", "root", "hardlink", "fifo"])
def test_package_aliases_and_nonregular_files_are_rejected(tmp_path: Path, kind: str) -> None:
    skill = package(tmp_path / "package")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("synthetic host marker")
    root = skill.root
    if kind == "file":
        (root / "helper.py").unlink()
        (root / "helper.py").symlink_to(outside / "secret.txt")
    elif kind == "directory":
        (root / "linked").symlink_to(outside, target_is_directory=True)
    elif kind == "root":
        root = tmp_path / "alias"
        root.symlink_to(skill.root, target_is_directory=True)
    elif kind == "hardlink":
        os.link(outside / "secret.txt", root / "linked.txt")
    else:
        os.mkfifo(root / "pipe")
    with pytest.raises(ValueError):
        load_skill(root)


@pytest.mark.parametrize("name", ["extra.pyc", "native.so", "native.pyd"])
def test_unsupported_executable_formats_reject_instead_of_being_ignored(
    tmp_path: Path, name: str
) -> None:
    skill = package(tmp_path / "package")
    (skill.root / name).write_bytes(b"synthetic unsupported executable")
    with pytest.raises(ValueError):
        load_skill(skill.root)


@pytest.mark.parametrize("relative", ["./input.json", "../input.json", "input\\.json"])
def test_schema_references_must_be_canonical_package_paths(tmp_path: Path, relative: str) -> None:
    skill = package(tmp_path / "package")
    path = skill.root / "manifest.json"
    values = json.loads(path.read_text())
    values["input_schema"] = relative
    path.write_text(json.dumps(values))
    with pytest.raises(ValueError):
        load_skill(skill.root)


def test_entrypoint_requires_package_source(tmp_path: Path) -> None:
    skill = package(tmp_path / "package")
    (skill.root / "plugin.py").unlink()
    with pytest.raises(ValueError):
        load_skill(skill.root)


@pytest.mark.parametrize(
    "limit", ["SKILL_PACKAGE_MAX_FILES", "SKILL_PACKAGE_MAX_BYTES", "SKILL_FILE_MAX_BYTES"]
)
def test_package_resource_limits_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    skill = package(tmp_path / "package")
    monkeypatch.setattr(skills_module, limit, 1)
    with pytest.raises(ValueError):
        load_skill(skill.root)


@pytest.mark.asyncio
@pytest.mark.parametrize("caller", ["stale", "reloaded", "forged_hash"])
async def test_changed_code_never_reaches_supervisor(tmp_path: Path, caller: str) -> None:
    skill, _, _, supervisor, dispatcher = await approved(tmp_path)
    (skill.root / "plugin.py").write_text(
        "def run(arguments):\n    raise RuntimeError('changed')\n"
    )
    supplied = skill if caller == "stale" else load_skill(skill.root)
    if caller == "forged_hash":
        supplied = replace(supplied, manifest_hash=skill.manifest_hash)
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(supplied, {"text": "blocked"})
    assert supervisor.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["manifest", "input_schema", "output_schema"])
async def test_caller_cannot_forge_non_hash_metadata(tmp_path: Path, field: str) -> None:
    skill, _, _, supervisor, dispatcher = await approved(tmp_path)
    value: Any = {"type": "object", "properties": {}}
    if field == "manifest":
        value = skill.manifest.model_copy(update={"timeout_ms": 120000})
    supplied = replace(skill, **{field: value})
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(supplied, {"text": "blocked"})
    assert supervisor.calls == []


@pytest.mark.asyncio
async def test_identical_other_root_cannot_borrow_enable_identity(tmp_path: Path) -> None:
    skill, _, _, supervisor, dispatcher = await approved(tmp_path)
    other = tmp_path / "other"
    shutil.copytree(skill.root, other)
    same_content = load_skill(other)
    assert same_content.manifest_hash == skill.manifest_hash
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(same_content, {"text": "blocked"})
    assert supervisor.calls == []


@pytest.mark.asyncio
async def test_legacy_approval_row_is_preserved_but_cannot_enable_or_dispatch(
    tmp_path: Path,
) -> None:
    skill, registry, store, supervisor, dispatcher = await approved(tmp_path)
    legacy = hashlib.sha256(
        b"".join(
            (skill.root / name).read_bytes()
            for name in ("manifest.json", "input.json", "output.json")
        )
    ).hexdigest()
    await store.run_transaction(lambda c: c.execute("UPDATE skills SET manifest_hash=?", (legacy,)))
    assert not await registry.is_enabled(skill.manifest.id, skill.manifest.version)
    with pytest.raises(ValueError, match="approval"):
        await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=True)
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(skill, {})
    row = await store.run_transaction(lambda c: dict(c.execute("SELECT * FROM skills").fetchone()))
    assert row["manifest_hash"] == legacy and row["state"] == "enabled"
    assert supervisor.calls == []
    await registry.install(load_skill(skill.root))
    assert not await registry.is_enabled(skill.manifest.id, skill.manifest.version)
    assert await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=True)
    assert await dispatcher.execute(load_skill(skill.root), {})


@pytest.mark.asyncio
async def test_enable_does_not_approve_changed_code_implicitly(tmp_path: Path) -> None:
    skill, registry, store, _, _ = await approved(tmp_path)
    await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=False)
    (skill.root / "helper.py").write_text("VALUE = 'unapproved'\n")
    with pytest.raises(ValueError, match="approval"):
        await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=True)
    row = await store.run_transaction(lambda c: dict(c.execute("SELECT * FROM skills").fetchone()))
    assert row["manifest_hash"] == skill.manifest_hash and row["state"] == "disabled"


@pytest.mark.asyncio
async def test_install_cannot_trust_a_forged_hash_or_schema(tmp_path: Path) -> None:
    skill, registry, store, _, _ = await approved(tmp_path)
    with pytest.raises(ValueError, match="approval"):
        await registry.install(replace(skill, manifest_hash="0" * 64), enabled=True)
    row = await store.run_transaction(lambda c: dict(c.execute("SELECT * FROM skills").fetchone()))
    assert row["manifest_hash"] == skill.manifest_hash


@pytest.mark.asyncio
async def test_snapshot_is_same_verified_bytes_and_removed_after_execution(tmp_path: Path) -> None:
    skill, _, _, supervisor, dispatcher = await approved(tmp_path)
    cache = skill.root / "__pycache__"
    cache.mkdir()
    (cache / "plugin.cpython-314.pyc").write_bytes(b"ignored cache")
    source_bytes = (skill.root / "plugin.py").read_text()
    result = await dispatcher.execute(skill, {})
    assert result["text"] == source_bytes
    snapshot = supervisor.calls[0]
    assert snapshot.root != skill.root
    assert snapshot.manifest_hash == skill.manifest_hash
    assert not snapshot.root.exists()
    assert (skill.root / "plugin.py").read_text() == source_bytes


@pytest.mark.asyncio
async def test_change_during_capture_rejects_before_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill, _, _, supervisor, dispatcher = await approved(tmp_path)
    original = skills_module.capture_skill

    def changed(root: Path) -> Any:
        captured = original(root)
        (root / "helper.py").write_text("VALUE = 'changed during preparation'\n")
        return captured

    monkeypatch.setattr(worker_module, "capture_skill", changed)
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(skill, {})
    assert supervisor.calls == []


@pytest.mark.asyncio
async def test_frozen_handoff_cannot_execute_later_source_mutation(tmp_path: Path) -> None:
    skill, registry, _, _, _ = await approved(tmp_path)
    before = (skill.root / "plugin.py").read_bytes()

    class MutatingSupervisor(WorkerSupervisor):
        async def execute(self, snapshot: InstalledSkill, arguments: object) -> dict[str, object]:
            (skill.root / "plugin.py").write_text(
                "def run(arguments):\n    return {'text': 'wrong'}\n"
            )
            (skill.root / "helper.py").write_text("VALUE = 'wrong'\n")
            assert (snapshot.root / "plugin.py").read_bytes() == before
            assert not (snapshot.root / "__pycache__").exists()
            return await super().execute(snapshot, arguments)

    dispatcher = SkillDispatcher(registry, MutatingSupervisor())
    assert await dispatcher.execute(skill, {"text": "approved"}) == {"text": "approved"}
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(skill, {"text": "new invocation blocked"})


@pytest.mark.asyncio
async def test_revoke_during_preparation_prevents_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill, registry, _, supervisor, dispatcher = await approved(tmp_path)
    original = registry.is_enabled
    queries = 0

    async def revoked(*args: Any, **kwargs: Any) -> bool:
        nonlocal queries
        queries += 1
        if queries == 2:
            await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=False)
        return await original(*args, **kwargs)

    monkeypatch.setattr(registry, "is_enabled", revoked)
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(skill, {})
    assert supervisor.calls == []


@pytest.mark.asyncio
async def test_cancel_preparation_joins_and_removes_owned_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill, _, _, supervisor, dispatcher = await approved(tmp_path)
    original = worker_module._prepare_skill
    started, release = threading.Event(), threading.Event()
    snapshots: list[Path] = []

    def slow(value: InstalledSkill) -> Any:
        started.set()
        assert release.wait(2)
        prepared = original(value)
        snapshots.append(prepared.snapshot.root)
        return prepared

    monkeypatch.setattr(worker_module, "_prepare_skill", slow)
    task = asyncio.create_task(dispatcher.execute(skill, {}))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert snapshots and all(not p.exists() for p in snapshots)
    assert supervisor.calls == []


@pytest.mark.asyncio
async def test_cancel_worker_removes_owned_snapshot(tmp_path: Path) -> None:
    skill, registry, _, _, _ = await approved(tmp_path)
    started = asyncio.Event()
    roots: list[Path] = []

    class WaitingSupervisor(WorkerSupervisor):
        async def execute(self, snapshot: InstalledSkill, arguments: object) -> dict[str, object]:
            roots.append(snapshot.root)
            started.set()
            await asyncio.Event().wait()
            return {}

    task = asyncio.create_task(SkillDispatcher(registry, WaitingSupervisor()).execute(skill, {}))
    await asyncio.wait_for(started.wait(), 2)
    assert roots[0].exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not roots[0].exists()


@pytest.mark.asyncio
async def test_cancel_during_cleanup_cannot_resurrect_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill, _, _, _, dispatcher = await approved(tmp_path)
    original = tempfile.TemporaryDirectory.cleanup
    started, release = threading.Event(), threading.Event()
    roots: list[Path] = []

    def slow_cleanup(directory: Any) -> None:
        roots.append(Path(directory.name))
        started.set()
        assert release.wait(2)
        original(directory)

    monkeypatch.setattr(tempfile.TemporaryDirectory, "cleanup", slow_cleanup)
    task = asyncio.create_task(dispatcher.execute(skill, {}))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert roots and all(not p.exists() for p in roots)


@pytest.mark.asyncio
async def test_snapshot_admission_is_bounded_and_waiter_cancel_creates_no_copy(
    tmp_path: Path,
) -> None:
    skill, registry, _, _, _ = await approved(tmp_path)
    eight_started = asyncio.Event()
    roots: list[Path] = []

    class WaitingSupervisor(WorkerSupervisor):
        async def execute(self, snapshot: InstalledSkill, arguments: object) -> dict[str, object]:
            roots.append(snapshot.root)
            if len(roots) >= 8:
                eight_started.set()
            await asyncio.Event().wait()
            return {}

    dispatcher = SkillDispatcher(registry, WaitingSupervisor())
    tasks = [asyncio.create_task(dispatcher.execute(skill, {})) for _ in range(9)]
    try:
        await asyncio.wait_for(eight_started.wait(), 3)
        await asyncio.sleep(0.05)
        assert len(roots) == 8
        tasks[-1].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[-1]
        assert len(roots) == 8
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert all(not p.exists() for p in roots)


@pytest.mark.asyncio
async def test_reapproved_package_cannot_inherit_previous_concurrency_limit(tmp_path: Path) -> None:
    skill, registry, _, _, _ = await approved(tmp_path)
    manifest_path = skill.root / "manifest.json"
    values = json.loads(manifest_path.read_text())
    values["concurrency"] = 2
    manifest_path.write_text(json.dumps(values))
    old = load_skill(skill.root)
    await registry.install(old, enabled=True)

    class CountingSupervisor(WorkerSupervisor):
        active = 0
        peak = 0

        async def _execute_one(
            self, snapshot: InstalledSkill, arguments: object
        ) -> dict[str, object]:
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                await asyncio.sleep(0.05)
                return {"text": "synthetic admission probe"}
            finally:
                self.active -= 1

    supervisor = CountingSupervisor()
    dispatcher = SkillDispatcher(registry, supervisor)
    await dispatcher.execute(old, {})
    values["concurrency"] = 1
    manifest_path.write_text(json.dumps(values))
    current = load_skill(skill.root)
    await registry.install(current, enabled=True)
    supervisor.peak = 0
    await asyncio.gather(dispatcher.execute(current, {}), dispatcher.execute(current, {}))
    assert supervisor.peak == 1
