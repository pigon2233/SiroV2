from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import threading
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

import pytest

from siro.core.evolution import VerificationReport
from siro.core.skills import capture_skill
from siro.ports.models import ToolDefinition
from siro.services.tools.execution import ExecutionCleanupError
from siro.services.tools.orchestrator import ToolCatalog, ToolDescriptor


def backend() -> ModuleType:
    return importlib.import_module("siro.services.tools.skill_candidates")


async def forbidden_executor(arguments: dict[str, object]) -> object:
    raise AssertionError("candidate discovery must never execute a registered tool")


def catalog(
    name: str | None = None, *, state: str = "available", hidden: bool = False
) -> ToolCatalog:
    def available() -> bool:
        if state == "unknown":
            raise RuntimeError("synthetic readiness error")
        return state == "available"

    rows = (
        ()
        if name is None
        else (
            ToolDescriptor(
                name=name,
                definition=None
                if hidden
                else ToolDefinition(name, "synthetic", {"type": "object"}),
                executor=forbidden_executor,
                available=available,
                backend="synthetic",
                effect="read_only",
            ),
        )
    )
    return ToolCatalog(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", ["text.checklist.parse", "siro.text.checklist", "skill.siro.text.checklist"]
)
@pytest.mark.parametrize("state", ["available", "unavailable", "unknown"])
async def test_registered_hidden_alias_is_not_a_gap(
    monkeypatch: pytest.MonkeyPatch, name: str, state: str
) -> None:
    module = backend()
    monkeypatch.setattr(
        module, "_build_workspace", lambda: pytest.fail("existing tools cannot build")
    )
    service = module.SkillCandidatePreparer(catalog(name, state=state, hidden=True))
    result = await service.prepare("text.checklist.parse")
    assert result["status"] == "existing_" + state
    assert result["existing"]["name"] == name
    assert result["authorizes_execution"] is False
    assert not service.busy
    await service.close()


@pytest.mark.asyncio
async def test_unsupported_and_general_alternative_have_no_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = backend()
    monkeypatch.setattr(module, "_build_workspace", lambda: pytest.fail("unsupported cannot build"))
    service = module.SkillCandidatePreparer(catalog("computer.execute"))
    result = await service.prepare("arbitrary generated code")
    assert result["status"] == "unsupported_capability"
    assert result["general_alternative"]["name"] == "computer.execute"
    assert "files" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_general_alternative_does_not_depend_on_catalog_order(reverse: bool) -> None:
    rows = [
        ToolDescriptor(
            name=name,
            definition=None,
            executor=forbidden_executor,
            available=lambda: True,
            backend="synthetic",
            effect="read_only",
        )
        for name in ("text.checklist.parse", "computer.execute")
    ]
    if reverse:
        rows.reverse()
    service = backend().SkillCandidatePreparer(ToolCatalog(tuple(rows)))
    result = await service.prepare("text.checklist.parse")
    assert result["status"] == "existing_available"
    assert result["general_alternative"]["name"] == "computer.execute"


@pytest.mark.asyncio
async def test_actual_fixed_candidate_verification_hashes_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = backend()
    monkeypatch.setattr(module.tempfile, "tempdir", str(tmp_path))
    service = module.SkillCandidatePreparer(catalog())
    result = await service.prepare("text.checklist.parse")
    assert result["status"] == "awaiting_review", result
    assert result["verification"]["status"] == "passed"
    assert result["verification"]["workspace_removed"] is True
    assert result["verification"]["changed_paths"] == ["src/plugin.py"]
    assert result["trust_level"] == "unreviewed"
    assert result["enabled"] is False and result["installed"] is False
    assert result["approval_required"] is True and result["authorizes_execution"] is False
    assert result["source"] == "siro_builtin_template:markdown-checklist-v1"
    files = result["files"]
    assert set(files) == {"manifest.json", "input.json", "output.json", "plugin.py"}
    package = tmp_path / "reconstructed"
    package.mkdir()
    for name, data in files.items():
        (package / name).write_text(data, encoding="utf-8")
    skill, _ = capture_skill(package)
    assert skill.manifest_hash == result["package_hash"]
    assert skill.manifest.permissions == () and skill.manifest.network == "denied"
    assert skill.manifest.idempotency == "read_only" and skill.manifest.concurrency == 1
    assert result["source_sha256"] == hashlib.sha256(files["plugin.py"].encode()).hexdigest()
    assert result["tests_sha256"] == hashlib.sha256(module._TESTS.encode()).hexdigest()
    assert json.loads(files["input.json"])["additionalProperties"] is False
    assert "Ran " in "".join(result["verification"]["outputs"])
    assert not list(tmp_path.glob("siro-skill-candidate-*"))
    assert not service.busy


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [
        "failed_checks",
        "unsupported_sandbox",
        "wrong_id",
        "wrong_path",
        "not_removed",
        "oversized_output",
    ],
)
async def test_invalid_verification_never_authorizes(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    module = backend()

    async def fake(root: Path, proposal: Any, **kwargs: Any) -> VerificationReport:
        return VerificationReport(
            uuid4() if fault == "wrong_id" else proposal.proposal_id,
            fault if fault in {"failed_checks", "unsupported_sandbox"} else "passed",
            ("src/other.py",) if fault == "wrong_path" else ("src/plugin.py",),
            ("x" * 65537,) if fault == "oversized_output" else ("synthetic verifier output",),
            fault != "not_removed",
        )

    monkeypatch.setattr(module, "verify_isolated_patch", fake)
    service = module.SkillCandidatePreparer(catalog())
    result = await service.prepare("text.checklist.parse")
    assert result["status"] == "verification_failed"
    assert result["enabled"] is False and result["authorizes_execution"] is False


@pytest.mark.asyncio
async def test_busy_cancel_close_and_no_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    module = backend()
    entered = asyncio.Event()
    cleaned = asyncio.Event()

    async def wait(root: Path, proposal: Any, **kwargs: Any) -> VerificationReport:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()
        raise AssertionError("unreachable")

    monkeypatch.setattr(module, "verify_isolated_patch", wait)
    service = module.SkillCandidatePreparer(catalog())
    preparation = asyncio.create_task(service.prepare("text.checklist.parse"))
    await asyncio.wait_for(entered.wait(), 2)
    assert service.busy
    with pytest.raises(module.SkillCandidateBusy):
        await service.prepare("text.checklist.parse")
    assert await service.cancel() is True
    with pytest.raises(asyncio.CancelledError):
        await preparation
    assert cleaned.is_set() and not service.busy
    assert await service.cancel() is False
    await service.close()
    with pytest.raises(module.SkillCandidateClosed):
        await service.prepare("text.checklist.parse")


@pytest.mark.asyncio
async def test_repeated_cancel_joins_blocking_preparation_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = backend()
    original = module._build_workspace
    entered = threading.Event()
    released = threading.Event()
    monkeypatch.setattr(module.tempfile, "tempdir", str(tmp_path))

    def slow() -> Any:
        entered.set()
        assert released.wait(3)
        return original()

    monkeypatch.setattr(module, "_build_workspace", slow)
    service = module.SkillCandidatePreparer(catalog())
    task = asyncio.create_task(service.prepare("text.checklist.parse"))
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert service.busy
    released.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert not service.busy and not list(tmp_path.glob("siro-skill-candidate-*"))


@pytest.mark.asyncio
async def test_cleanup_failure_is_typed_and_does_not_return_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = backend()
    original = module._remove_workspace
    roots: list[Path] = []

    def fail(root: Path) -> None:
        roots.append(root)
        raise ExecutionCleanupError("synthetic cleanup failure")

    async def passed(root: Path, proposal: Any, **kwargs: Any) -> VerificationReport:
        return VerificationReport(proposal.proposal_id, "passed", ("src/plugin.py",), (), True)

    monkeypatch.setattr(module, "_remove_workspace", fail)
    monkeypatch.setattr(module, "verify_isolated_patch", passed)
    service = module.SkillCandidatePreparer(catalog())
    try:
        with pytest.raises(ExecutionCleanupError):
            await service.prepare("text.checklist.parse")
        assert not service.busy
    finally:
        for root in roots:
            original(root)


@pytest.mark.asyncio
async def test_late_cancel_during_cleanup_cannot_return_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = backend()
    original = module._remove_workspace
    entered = threading.Event()
    release = threading.Event()

    def slow(root: Path) -> None:
        entered.set()
        assert release.wait(3)
        original(root)

    async def passed(root: Path, proposal: Any, **kwargs: Any) -> VerificationReport:
        return VerificationReport(proposal.proposal_id, "passed", ("src/plugin.py",), (), True)

    monkeypatch.setattr(module, "_remove_workspace", slow)
    monkeypatch.setattr(module, "verify_isolated_patch", passed)
    service = module.SkillCandidatePreparer(catalog())
    task = asyncio.create_task(service.prepare("text.checklist.parse"))
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert not service.busy
