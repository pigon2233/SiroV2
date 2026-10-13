from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from siro.adapters.skill_worker import (
    SkillDisabled,
    SkillDispatcher,
    SkillExecutionError,
    WorkerSupervisor,
)
from siro.core.skills import InstalledSkill, load_skill
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore


def make_skill(tmp_path: Path, function_body: str, **overrides: object) -> InstalledSkill:
    root = tmp_path / f"skill-{len(list(tmp_path.iterdir()))}"
    root.mkdir()
    manifest: dict[str, object] = {
        "id": "test.sample",
        "version": "1.0.0",
        "contract_version": 1,
        "description": "A bounded test skill",
        "entrypoint": "python:plugin:run",
        "input_schema": "input.json",
        "output_schema": "output.json",
        "permissions": [{"capability": "test.run", "scope_required": "fixture"}],
        "risk": "observe",
        "timeout_ms": 1000,
        "concurrency": 1,
        "resource_limits": {"memory_mb": 64, "output_bytes": 1024, "cpu_seconds": 1},
        "network": "denied",
        "idempotency": "read_only",
        "cancellation": "process",
        "compensation": "none",
    }
    manifest.update(overrides)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    (root / "input.json").write_text(json.dumps(schema), encoding="utf-8")
    (root / "output.json").write_text(json.dumps(schema), encoding="utf-8")
    (root / "plugin.py").write_text(f"def run(arguments):\n    {function_body}\n", encoding="utf-8")
    return load_skill(root)


@pytest.mark.asyncio
async def test_manifest_registry_versions_and_disable_block_new_jobs(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        make_skill(tmp_path, "return arguments", network="allowed")
    skill = make_skill(tmp_path, "return arguments")
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    dispatcher = SkillDispatcher(registry, WorkerSupervisor())
    await registry.install(skill)
    assert not await registry.is_enabled(skill.manifest.id, skill.manifest.version)
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(skill, {"text": "blocked"})
    assert await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=True)
    assert await registry.is_enabled(skill.manifest.id, skill.manifest.version)
    assert await dispatcher.execute(skill, {"text": "allowed"}) == {"text": "allowed"}
    assert await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=False)
    assert not await registry.is_enabled(skill.manifest.id, skill.manifest.version)
    with pytest.raises(SkillDisabled):
        await dispatcher.execute(skill, {"text": "blocked again"})


@pytest.mark.asyncio
async def test_a15_worker_validation_limits_timeout_and_cancel(tmp_path: Path) -> None:
    supervisor = WorkerSupervisor()
    echo = make_skill(tmp_path, "return arguments")
    assert await supervisor.execute(echo, {"text": "bounded"}) == {"text": "bounded"}
    with pytest.raises(ValueError, match="unknown fields"):
        await supervisor.execute(echo, {"text": "ok", "escape": True})

    flood = make_skill(
        tmp_path,
        "return {'text': 'x' * 100000}",
        resource_limits={"memory_mb": 64, "output_bytes": 128, "cpu_seconds": 1},
    )
    with pytest.raises(SkillExecutionError, match="output exceeded"):
        await supervisor.execute(flood, {"text": "go"})

    cpu_hog = make_skill(
        tmp_path,
        "\n    while True: pass",
        timeout_ms=100,
    )
    with pytest.raises(SkillExecutionError, match="timed out"):
        await supervisor.execute(cpu_hog, {"text": "go"})

    cancellable = make_skill(tmp_path, "\n    while True: pass", timeout_ms=5000)
    task = asyncio.create_task(supervisor.execute(cancellable, {"text": "go"}))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    memory_hog = make_skill(tmp_path, "return {'text': 'x' * 100000000}")
    with pytest.raises(SkillExecutionError, match="worker failed"):
        await supervisor.execute(memory_hog, {"text": "go"})


@pytest.mark.asyncio
async def test_worker_honors_manifest_concurrency(tmp_path: Path) -> None:
    supervisor = WorkerSupervisor()
    serial = make_skill(
        tmp_path,
        "import time; time.sleep(0.15); return arguments",
        concurrency=1,
    )
    started = time.monotonic()
    await asyncio.gather(
        supervisor.execute(serial, {"text": "one"}),
        supervisor.execute(serial, {"text": "two"}),
    )
    assert time.monotonic() - started >= 0.25


@pytest.mark.asyncio
async def test_a15_sandbox_denies_network_host_files_and_secret_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host_secret = tmp_path / "host-secret.txt"
    host_secret.write_text("must-not-be-visible", encoding="utf-8")
    monkeypatch.setenv("SIRO_TEST_SECRET", "must-not-be-inherited")
    body = (
        "import os, pathlib, socket\n"
        "    try:\n"
        "        socket.create_connection(('127.0.0.1', 9), timeout=0.1)\n"
        "        network = 'open'\n"
        "    except OSError:\n"
        "        network = 'blocked'\n"
        f"    visible = pathlib.Path({str(host_secret)!r}).exists()\n"
        "    inherited = os.environ.get('SIRO_TEST_SECRET', 'none')\n"
        "    return {'text': f'{network}:{visible}:{inherited}'}"
    )
    skill = make_skill(tmp_path, body)
    assert await WorkerSupervisor().execute(skill, {"text": "probe"}) == {
        "text": "blocked:False:none"
    }


@pytest.mark.asyncio
async def test_a15_cpu_hog_does_not_block_core_event_loop(tmp_path: Path) -> None:
    skill = make_skill(tmp_path, "\n    while True: pass", timeout_ms=150)
    ticks = 0

    async def core_heartbeat() -> None:
        nonlocal ticks
        for _ in range(10):
            await asyncio.sleep(0.01)
            ticks += 1

    results = await asyncio.gather(
        WorkerSupervisor().execute(skill, {"text": "go"}),
        core_heartbeat(),
        return_exceptions=True,
    )
    assert isinstance(results[0], SkillExecutionError)
    assert ticks == 10
