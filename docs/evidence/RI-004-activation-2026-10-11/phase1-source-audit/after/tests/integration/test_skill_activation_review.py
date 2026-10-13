from __future__ import annotations

import asyncio
import json
import platform
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from siro.adapters.skill_worker import SkillDispatcher, WorkerSupervisor
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken
from siro.services.tools import skill_activation as activation
from siro.services.tools.execution import (
    ExecutionCancelled,
    ExecutionCleanupError,
    ExecutionContext,
)
from siro.services.tools.orchestrator import ToolCatalog
from siro.services.tools.skill_candidates import CAPABILITY, SkillCandidatePreparer


async def fixture(
    tmp_path: Path, *, enabled: bool = True
) -> tuple[Any, SQLiteSkillRegistry, ToolCatalog, str]:
    store = SQLiteStore(tmp_path / "synthetic.sqlite3")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    catalog = ToolCatalog(())
    owner = activation.SkillActivationOwner(
        catalog,
        registry,
        SkillDispatcher(registry, WorkerSupervisor(profile="python-stdlib-single")),
        tmp_path / "managed",
    )
    await owner.initialize()
    preparer = SkillCandidatePreparer(catalog)
    try:
        report = await preparer.prepare(CAPABILITY)
    finally:
        await preparer.close()
    item = await owner.remember(report)
    review_id, package_hash = item["review_id"], item["package_hash"]
    assert isinstance(review_id, str) and isinstance(package_hash, str)
    await owner.install(review_id, package_hash)
    if enabled:
        await owner.enable(package_hash)
    return owner, registry, catalog, package_hash


def fresh_owner(tmp_path: Path, registry: SQLiteSkillRegistry) -> Any:
    return activation.SkillActivationOwner(
        ToolCatalog(()),
        registry,
        SkillDispatcher(registry, WorkerSupervisor(profile="python-stdlib-single")),
        tmp_path / "managed",
    )


@pytest.mark.asyncio
async def test_revoke_cleanup_failure_still_durably_disables_restart(tmp_path: Path) -> None:
    owner, registry, _, package_hash = await fixture(tmp_path)
    entered = asyncio.Event()

    async def fail_cleanup(*_args: object) -> dict[str, object]:
        entered.set()
        try:
            return await asyncio.Future[dict[str, object]]()
        except asyncio.CancelledError:
            raise ExecutionCleanupError("synthetic owned worker cleanup failure") from None

    owner._dispatcher.execute = fail_cleanup
    job = asyncio.create_task(
        owner.execute({"text": "synthetic"}, ExecutionContext("r", "s", "e", authorized=True))
    )
    other = fresh_owner(tmp_path, registry)
    try:
        await asyncio.wait_for(entered.wait(), 2)
        with pytest.raises(ExecutionCleanupError, match="synthetic owned worker cleanup"):
            await owner.revoke(package_hash)
        await asyncio.gather(job, return_exceptions=True)
        assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
        assert owner.snapshot()["enabled"] is False
        await other.initialize()
        assert other.snapshot()["enabled"] is False
        assert not other._catalog.definitions()
    finally:
        if not job.done():
            job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        await other.close()
        await owner.close()


@pytest.mark.asyncio
async def test_cancelled_restore_cannot_publish_late_enabled_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, registry, _, _ = await fixture(tmp_path)
    other = fresh_owner(tmp_path, registry)
    original = activation._restored
    entered, release = threading.Event(), threading.Event()

    def blocked(path: Path) -> Any:
        result = original(path)
        entered.set()
        assert release.wait(3)
        return result

    monkeypatch.setattr(activation, "_restored", blocked)
    job = asyncio.create_task(other.initialize())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        job.cancel()
        await asyncio.sleep(0.01)
        job.cancel()
        assert not job.done(), "restored IO must remain owned until joined"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(job, 2)
        assert other.snapshot()["enabled"] is False
        assert not other._catalog.definitions()
        # Cancelling a read does not revoke a previously explicit durable approval.
        assert await registry.is_enabled("siro.text.checklist", "1.0.0")
    finally:
        release.set()
        await asyncio.gather(job, return_exceptions=True)
        await other.close()
        await owner.close()


@pytest.mark.asyncio
async def test_valid_format_wrong_review_package_hash_is_rejected(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "synthetic.sqlite3")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    owner = fresh_owner(tmp_path, registry)
    preparer = SkillCandidatePreparer(ToolCatalog(()))
    try:
        await owner.initialize()
        item = await preparer.prepare(CAPABILITY)
        wrong = "siro-skill-package-v1:" + "f" * 64
        assert item["package_hash"] != wrong
        item["package_hash"] = wrong
        with pytest.raises(activation.SkillActivationError):
            await owner.remember(item)
        assert owner._review is None
        assert owner._skill is None
        rows = await registry._store.run_transaction(
            lambda connection: connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        )
        assert rows == 0
        assert not list((tmp_path / "managed").glob("*/plugin.py"))
    finally:
        await preparer.close()
        await owner.close()


@pytest.mark.asyncio
async def test_delayed_remember_cannot_revive_review_after_suspend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStore(tmp_path / "synthetic.sqlite3")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    owner = fresh_owner(tmp_path, registry)
    await owner.initialize()
    preparer = SkillCandidatePreparer(ToolCatalog(()))
    try:
        item = await preparer.prepare(CAPABILITY)
    finally:
        await preparer.close()
    original = activation._template_hash
    entered, release = threading.Event(), threading.Event()

    def blocked() -> str:
        result = original()
        entered.set()
        assert release.wait(3)
        return result

    monkeypatch.setattr(activation, "_template_hash", blocked)
    job = asyncio.create_task(owner.remember(item))
    suspend: asyncio.Task[None] | None = None
    epoch = owner._epoch
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        suspend = asyncio.create_task(owner.suspend())
        async with asyncio.timeout(2):
            while owner._epoch == epoch:
                await asyncio.sleep(0)
        release.set()
        with pytest.raises((activation.SkillActivationError, asyncio.CancelledError)):
            await asyncio.wait_for(job, 2)
        await asyncio.wait_for(suspend, 2)
        assert owner._review is None
        assert owner.snapshot()["enabled"] is False
    finally:
        release.set()
        await asyncio.gather(job, return_exceptions=True)
        if suspend is not None:
            await asyncio.gather(suspend, return_exceptions=True)
        await owner.close()


@pytest.mark.asyncio
async def test_queued_remember_cannot_adopt_post_suspend_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStore(tmp_path / "synthetic.sqlite3")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    owner = fresh_owner(tmp_path, registry)
    preparer = SkillCandidatePreparer(ToolCatalog(()))
    try:
        item = await preparer.prepare(CAPABILITY)
    finally:
        await preparer.close()
    original = activation._restored
    entered, release = threading.Event(), threading.Event()

    def blocked(path: Path) -> Any:
        result = original(path)
        entered.set()
        assert release.wait(3)
        return result

    monkeypatch.setattr(activation, "_restored", blocked)
    initialize = asyncio.create_task(owner.initialize())
    remember: asyncio.Task[dict[str, object]] | None = None
    suspend: asyncio.Task[None] | None = None
    epoch = owner._epoch
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        remember = asyncio.create_task(owner.remember(item))
        async with asyncio.timeout(2):
            while len(owner._operations) < 2:
                await asyncio.sleep(0)
        suspend = asyncio.create_task(owner.suspend())
        async with asyncio.timeout(2):
            while owner._epoch == epoch:
                await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(initialize, 2)
        with pytest.raises(activation.SkillActivationError):
            await asyncio.wait_for(remember, 2)
        await asyncio.wait_for(suspend, 2)
        assert owner._review is None
        assert owner.snapshot()["enabled"] is False
    finally:
        release.set()
        await asyncio.gather(
            *(task for task in (initialize, remember, suspend) if task is not None),
            return_exceptions=True,
        )
        await owner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "source",
        "source_alias",
        "source_mode",
        "missing_receipt",
        "receipt_type",
        "receipt_alias",
        "row_hash",
        "row_path",
    ],
)
async def test_actual_restart_rejects_receipt_source_or_row_tamper(
    tmp_path: Path, change: str
) -> None:
    owner, registry, _, _ = await fixture(tmp_path)
    other = fresh_owner(tmp_path, registry)
    managed = tmp_path / "managed"
    package = next(managed.glob("*/plugin.py"))
    receipt = managed / "approval.json"
    if change == "source":
        package.chmod(0o600)
        package.write_text("raise SystemExit('synthetic changed source')\n")
    elif change == "source_alias":
        outside = tmp_path / "synthetic-copy.py"
        outside.write_bytes(package.read_bytes())
        package.unlink()
        package.symlink_to(outside)
    elif change == "source_mode":
        package.chmod(0o500)
    elif change == "missing_receipt":
        receipt.unlink()
    elif change == "receipt_type":
        value = json.loads(receipt.read_text())
        value["owner_approved"] = 1
        receipt.write_text(json.dumps(value))
    elif change == "receipt_alias":
        outside = tmp_path / "synthetic-receipt.json"
        outside.write_bytes(receipt.read_bytes())
        receipt.unlink()
        receipt.symlink_to(outside)
    elif change == "row_hash":
        await registry._store.run_transaction(
            lambda connection: connection.execute(
                "UPDATE skills SET manifest_hash='legacy-synthetic'"
            )
        )
    else:
        await registry._store.run_transaction(
            lambda connection: connection.execute(
                "UPDATE skills SET path_ref=?", (str(tmp_path / "synthetic-unmanaged"),)
            )
        )
    try:
        await other.initialize()
        assert other.snapshot()["enabled"] is False
        assert not other._catalog.definitions()
    finally:
        await other.close()
        await owner.close()


@pytest.mark.asyncio
async def test_unsupported_strict_runtime_cannot_enable_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, registry, _, package_hash = await fixture(tmp_path, enabled=False)
    monkeypatch.setattr(platform, "machine", lambda: "synthetic-unsupported")
    try:
        with pytest.raises(activation.SkillActivationError):
            await owner.enable(package_hash)
        assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
        assert owner.snapshot()["enabled"] is False
    finally:
        await owner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["caller", "token", "deadline", "revoke", "primary_cleanup"])
async def test_result_publication_after_watcher_cleanup_preserves_cancellation_and_failure(
    tmp_path: Path, trigger: str
) -> None:
    owner, _, _, package_hash = await fixture(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()

    class DelayedToken(CancellationToken):
        async def wait(self) -> None:
            try:
                await super().wait()
            finally:
                entered.set()
                await release.wait()

    token = DelayedToken()
    context = ExecutionContext(
        "r",
        "s",
        "e",
        authorized=True,
        cancellation=token,
        deadline=asyncio.get_running_loop().time() + 0.2 if trigger == "deadline" else None,
    )

    async def result(*_args: object) -> dict[str, object]:
        if trigger == "primary_cleanup":
            raise ExecutionCleanupError("synthetic primary cleanup failure")
        return {"pending": ["synthetic"], "completed": [], "pending_count": 1, "completed_count": 0}

    owner._dispatcher.execute = result
    job = asyncio.create_task(owner.execute({"text": "synthetic"}, context))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if trigger in {"caller", "primary_cleanup"}:
            job.cancel()
            await asyncio.sleep(0.01)
            job.cancel()
        elif trigger == "token":
            token.cancel()
        elif trigger == "deadline":
            await asyncio.sleep(0.21)
        else:
            await owner.revoke(package_hash)
        release.set()
        expected = {
            "primary_cleanup": ExecutionCleanupError,
            "caller": asyncio.CancelledError,
            "deadline": TimeoutError,
            "token": ExecutionCancelled,
            "revoke": ExecutionCancelled,
        }[trigger]
        with pytest.raises(expected):
            await asyncio.wait_for(job, 2)
        assert not owner._jobs
    finally:
        release.set()
        if not job.done():
            job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        with suppress(activation.SkillActivationError):
            await owner.revoke(package_hash)
        await owner.close()
