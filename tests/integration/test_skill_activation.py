from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, cast

import pytest

from siro.adapters.skill_worker import SkillDispatcher, WorkerSupervisor
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ToolCall
from siro.services.tools.execution import ExecutionContext
from siro.services.tools.orchestrator import (
    ProposalState,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolOrchestrator,
    ToolUnavailableError,
)


def activation_module() -> Any:
    from siro.services.tools import skill_activation

    return skill_activation


async def owner_fixture(
    tmp_path: Path,
) -> tuple[Any, SQLiteStore, SQLiteSkillRegistry, ToolCatalog]:
    store = SQLiteStore(tmp_path / "synthetic.sqlite3")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    catalog = ToolCatalog(())
    owner = activation_module().SkillActivationOwner(
        catalog,
        registry,
        SkillDispatcher(registry, WorkerSupervisor(profile="python-stdlib-single")),
        tmp_path / "managed",
    )
    await owner.initialize()
    return owner, store, registry, catalog


async def review(owner: Any, catalog: ToolCatalog) -> dict[str, Any]:
    from siro.services.tools.skill_candidates import CAPABILITY, SkillCandidatePreparer

    prepared = await SkillCandidatePreparer(catalog).prepare(CAPABILITY)
    result = await owner.remember(prepared)
    assert result["review_id"] and result["installed"] is False
    return cast(dict[str, Any], result)


async def installed(
    tmp_path: Path,
) -> tuple[Any, SQLiteStore, SQLiteSkillRegistry, ToolCatalog, str]:
    owner, store, registry, catalog = await owner_fixture(tmp_path)
    item = await review(owner, catalog)
    state = await owner.install(item["review_id"], item["package_hash"])
    assert state["installed"] is True and state["enabled"] is False
    return owner, store, registry, catalog, item["package_hash"]


@pytest.mark.asyncio
async def test_real_prepare_owner_approval_disabled_enable_normal_tool_revoke(
    tmp_path: Path,
) -> None:
    owner, store, registry, catalog, package_hash = await installed(tmp_path)
    assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
    subject = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    assert not subject.model_tools()
    await owner.enable(package_hash)
    assert subject.model_tools()[0].name == "text.checklist.parse"
    subject.start_run("run", "synthetic")
    args: dict[str, object] = {"text": "- [ ] 買牛奶\n* [x] 完成\n```\n- [ ] hidden\n```"}
    proposal = await subject.propose(
        "synthetic", ToolCall("one", "text.checklist.parse", args), risk="observe"
    )
    subject.bind_proposal("run", proposal)
    assert proposal.state is ProposalState.PENDING
    await subject.resolve(proposal.proposal_id, approved=True, arguments=args)
    done = await subject.execute(proposal.proposal_id)
    assert done.state is ProposalState.COMPLETED
    assert done.observation == {
        "pending": ["買牛奶"],
        "completed": ["完成"],
        "pending_count": 1,
        "completed_count": 1,
    }
    await owner.revoke(package_hash)
    assert not subject.model_tools()
    with pytest.raises(ToolUnavailableError):
        catalog.require("text.checklist.parse", args)
    assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
    await owner.close()


@pytest.mark.asyncio
async def test_runtime_restart_restores_only_exact_approved_managed_package(tmp_path: Path) -> None:
    owner, _store, registry, _catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)
    # Simulate ended owner without revoke mutation: new process must match persisted receipt.
    new_catalog = ToolCatalog(())
    other = activation_module().SkillActivationOwner(
        new_catalog,
        registry,
        SkillDispatcher(registry, WorkerSupervisor(profile="python-stdlib-single")),
        tmp_path / "managed",
    )
    await other.initialize()
    assert other.snapshot()["enabled"] is True
    assert len(new_catalog.definitions()) == 1
    await other.close()
    await owner.close()


@pytest.mark.asyncio
async def test_changed_package_refuses_enable_but_can_still_revoke(tmp_path: Path) -> None:
    owner, _store, registry, _catalog, package_hash = await installed(tmp_path)
    path = next((tmp_path / "managed").glob("*/plugin.py"))
    path.chmod(0o600)
    path.write_text('raise RuntimeError("tampered")\n')
    with pytest.raises(activation_module().SkillActivationError):
        await owner.enable(package_hash)
    await owner.revoke(package_hash)
    assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
    await owner.close()


@pytest.mark.parametrize(
    "field",
    [
        "package_hash",
        "source_sha256",
        "tests_sha256",
        "proposal_sha256",
        "proposal_id",
        "files",
        "verification",
    ],
)
@pytest.mark.asyncio
async def test_tampered_review_cannot_be_approved(tmp_path: Path, field: str) -> None:
    from siro.services.tools.skill_candidates import CAPABILITY, SkillCandidatePreparer

    owner, _store, _registry, catalog = await owner_fixture(tmp_path)
    item = await SkillCandidatePreparer(catalog).prepare(CAPABILITY)
    item[field] = "forged"
    with pytest.raises(activation_module().SkillActivationError):
        await owner.remember(item)
    assert not list((tmp_path / "managed").glob("*/plugin.py"))
    await owner.close()


@pytest.mark.asyncio
async def test_single_review_expiry_stale_identity_and_client_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _store, _registry, catalog = await owner_fixture(tmp_path)
    item = await review(owner, catalog)
    stale = item["review_id"]
    newer = await review(owner, catalog)
    with pytest.raises(activation_module().SkillActivationError):
        await owner.install(stale, newer["package_hash"])
    newer["files"]["plugin.py"] = "raise SystemExit(0)"
    await owner.install(newer["review_id"], newer["package_hash"])
    assert "raise SystemExit" not in next((tmp_path / "managed").glob("*/plugin.py")).read_text()
    await owner.close()
    owner, _, _, catalog = await owner_fixture(tmp_path / "other")
    item = await review(owner, catalog)
    monkeypatch.setattr(activation_module(), "_now", lambda: 1e50)
    with pytest.raises(activation_module().SkillActivationError):
        await owner.install(item["review_id"], item["package_hash"])
    await owner.close()


@pytest.mark.asyncio
async def test_revoke_drains_active_and_queued_jobs_before_ack(tmp_path: Path) -> None:
    owner, _, registry, catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)
    entered = asyncio.Event()
    exited = asyncio.Event()
    calls = 0

    async def controlled(*_args: Any) -> dict[str, object]:
        nonlocal calls
        calls += 1
        entered.set()
        try:
            return await asyncio.Future[dict[str, object]]()
        finally:
            await asyncio.sleep(0.02)
            exited.set()

    owner._dispatcher.execute = controlled
    d = catalog.require("text.checklist.parse", {"text": ""})
    assert d.contextual_executor is not None
    first = asyncio.create_task(
        owner.execute({"text": ""}, ExecutionContext("r", "s", "e", authorized=True))
    )
    await entered.wait()
    second = asyncio.create_task(
        owner.execute({"text": ""}, ExecutionContext("r2", "s", "e", authorized=True))
    )
    await asyncio.sleep(0)
    await owner.revoke(package_hash)
    result = await asyncio.gather(first, second, return_exceptions=True)
    assert calls == 1
    assert exited.is_set() and all(isinstance(x, BaseException) for x in result)
    assert not owner.snapshot()["enabled"] and not owner._jobs
    assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
    await owner.close()


@pytest.mark.parametrize("action", ["token", "deadline", "caller", "suspend", "close"])
@pytest.mark.asyncio
async def test_foreground_cancellation_and_disable_join_owned_jobs(
    tmp_path: Path, action: str
) -> None:
    owner, _, _, catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)
    entered = asyncio.Event()
    exited = asyncio.Event()

    async def controlled(*_args: Any) -> dict[str, object]:
        entered.set()
        try:
            return await asyncio.Future[dict[str, object]]()
        finally:
            await asyncio.sleep(0.02)
            exited.set()

    owner._dispatcher.execute = controlled
    d = catalog.require("text.checklist.parse", {"text": ""})
    assert d.contextual_executor
    context = ExecutionContext(
        "r",
        "s",
        "e",
        authorized=True,
        deadline=asyncio.get_running_loop().time() + 0.05 if action == "deadline" else None,
    )
    job = asyncio.create_task(owner.execute({"text": ""}, context))
    await entered.wait()
    if action == "token":
        context.cancellation.cancel()
    elif action == "caller":
        job.cancel()
        job.cancel()
    elif action == "suspend":
        await owner.suspend()
    elif action == "close":
        await owner.close()
    outcome = await asyncio.gather(job, return_exceptions=True)
    assert isinstance(outcome[0], BaseException) and exited.is_set() and not owner._jobs
    await owner.close()


@pytest.mark.asyncio
async def test_late_cancel_enable_transaction_is_joined_and_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _store, registry, _catalog, package_hash = await installed(tmp_path)
    started = threading.Event()
    release = threading.Event()
    original = registry.set_enabled

    async def delayed(*args: Any, **kwargs: Any) -> bool:
        if kwargs["enabled"]:

            def wait() -> None:
                started.set()
                release.wait(3)

            await asyncio.to_thread(wait)
        return await original(*args, **kwargs)

    monkeypatch.setattr(registry, "set_enabled", delayed)
    job = asyncio.create_task(owner.enable(package_hash))
    assert await asyncio.to_thread(started.wait, 2)
    job.cancel()
    await asyncio.sleep(0.01)
    job.cancel()
    assert not job.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await job
    assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
    assert owner.snapshot()["enabled"] is False
    await owner.close()


@pytest.mark.parametrize(
    "args",
    [
        {"text": True},
        {"text": "a" * 16385},
        {"text": "界" * 5462},
        {"text": "\n" * 257},
        {"text": "", "path": "/private"},
    ],
)
@pytest.mark.asyncio
async def test_product_input_bounds_before_dispatch(tmp_path: Path, args: dict[str, Any]) -> None:
    owner, _, _, _catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)
    with pytest.raises((ValueError, activation_module().SkillActivationError)):
        await owner.execute(args, ExecutionContext("r", "s", "e", authorized=True))
    await owner.close()


@pytest.mark.asyncio
async def test_no_authority_from_argument_executor_or_unapproved_context(tmp_path: Path) -> None:
    owner, _, _, catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)
    d = catalog.require("text.checklist.parse", {"text": ""})
    with pytest.raises(PermissionError):
        await d.executor({"text": ""})
    with pytest.raises(PermissionError):
        await owner.execute({"text": ""}, ExecutionContext("r", "s", "e"))
    await owner.close()


@pytest.mark.parametrize("invalid", [True, 2, -1, "1"])
@pytest.mark.asyncio
async def test_output_counts_are_exact_integer_and_consistent(
    tmp_path: Path, invalid: object
) -> None:
    owner, _, _, _catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)

    async def malformed(*_args: Any) -> dict[str, object]:
        return {"pending": ["a"], "completed": [], "pending_count": invalid, "completed_count": 0}

    owner._dispatcher.execute = malformed
    with pytest.raises(activation_module().SkillActivationError):
        await owner.execute({"text": ""}, ExecutionContext("r", "s", "e", authorized=True))
    await owner.close()
