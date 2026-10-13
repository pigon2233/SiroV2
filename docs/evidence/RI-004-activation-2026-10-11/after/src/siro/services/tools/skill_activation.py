"""Explicit owner approval for one fixed, verified pasted-text capability."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from siro.adapters.skill_worker import SkillDispatcher, SkillExecutionError, WorkerSupervisor
from siro.core.skills import InstalledSkill, capture_skill
from siro.persistence.skills import SQLiteSkillRegistry
from siro.ports.models import ToolDefinition
from siro.services.tools.execution import (
    ExecutionCancelled,
    ExecutionCleanupError,
    ExecutionContext,
)
from siro.services.tools.orchestrator import ToolCatalog, ToolDescriptor, ToolMetadata
from siro.services.tools.skill_candidates import _TESTS, CAPABILITY, PROFILE, _package_files


class SkillActivationError(RuntimeError):
    """Fail closed; callers publish only a fixed safe message."""


def _now() -> float:
    return asyncio.get_running_loop().time()


async def _join[T](task: asyncio.Task[T]) -> T:
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


@dataclass(frozen=True, slots=True)
class _Review:
    review_id: str
    package_hash: str
    files: tuple[tuple[str, str], ...]
    expires: float
    epoch: int


def _verify_package(path: Path, package_hash: str) -> InstalledSkill:
    skill, files = capture_skill(path)
    expected = _package_files()
    if (
        skill.manifest_hash != package_hash
        or set(files) != set(expected)
        or any(
            data != expected[name].encode("utf-8") or mode != 0
            for name, (data, mode) in files.items()
        )
    ):
        raise SkillActivationError("managed package identity mismatch")
    return skill


def _template_hash() -> str:
    with tempfile.TemporaryDirectory(prefix="siro-fixed-review-") as name:
        root = Path(name)
        for filename, text in _package_files().items():
            (root / filename).write_text(text, encoding="utf-8")
        return capture_skill(root)[0].manifest_hash


def _receipt(package_hash: str) -> dict[str, object]:
    return {
        "version": 1,
        "profile": PROFILE,
        "package_hash": package_hash,
        "tests_sha256": hashlib.sha256(_TESTS.encode()).hexdigest(),
        "owner_approved": True,
    }


def _read_receipt(root: Path) -> str | None:
    target = root / "approval.json"
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4096:
            raise SkillActivationError("invalid approval receipt")
        data = stream.read(4097)
    value = json.loads(data)
    if not isinstance(value, dict) or not isinstance(value.get("package_hash"), str):
        raise SkillActivationError("invalid approval receipt")
    package_hash = value["package_hash"]
    # JSON equality alone would confuse bool/integer receipt fields.
    if json.dumps(value, sort_keys=True) != json.dumps(_receipt(package_hash), sort_keys=True):
        raise SkillActivationError("invalid approval receipt")
    _package_path(root, package_hash)
    return str(package_hash)


def _package_path(root: Path, package_hash: str) -> Path:
    import re

    if re.fullmatch(r"siro-skill-package-v1:[0-9a-f]{64}", package_hash) is None:
        raise SkillActivationError("invalid package identity")
    return root / ("1.0.0-" + package_hash.split(":")[1])


def _root(root: Path) -> None:
    if root.resolve() != root:
        raise SkillActivationError("managed root cannot contain symlinks")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.resolve() != root or not root.is_dir():
        raise SkillActivationError("invalid managed root")


def _materialize(root: Path, review: _Review) -> InstalledSkill:
    _root(root)
    previous = _read_receipt(root)
    if previous is not None and previous != review.package_hash:
        raise SkillActivationError("different approved package already exists")
    path = _package_path(root, review.package_hash)
    if not path.exists():
        path.mkdir(mode=0o700)
        for name, text in review.files:
            with (path / name).open("x", encoding="utf-8") as stream:
                stream.write(text)
            (path / name).chmod(0o400)
    return _verify_package(path, review.package_hash)


def _persist_receipt(root: Path, package_hash: str) -> None:
    _root(root)
    temporary = root / ("approval-" + str(uuid4()) + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(_receipt(package_hash), stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / "approval.json")
    finally:
        temporary.unlink(missing_ok=True)


def _restored(root: Path) -> InstalledSkill | None:
    if not root.exists():
        return None
    _root(root)
    package_hash = _read_receipt(root)
    if package_hash is None:
        return None
    return _verify_package(_package_path(root, package_hash), package_hash)


def _input(arguments: dict[str, object]) -> None:
    text = arguments.get("text")
    if set(arguments) != {"text"} or not isinstance(text, str):
        raise SkillActivationError("only pasted text is accepted")
    if len(text.encode("utf-8")) > 16384 or len(text.splitlines()) > 256:
        raise SkillActivationError("pasted text exceeds bounds")


def _output(result: dict[str, object]) -> None:
    if set(result) != {"pending", "completed", "pending_count", "completed_count"}:
        raise SkillActivationError("invalid checklist output")
    total = 0
    for key in ("pending", "completed"):
        items = result[key]
        count = result[key + "_count"]
        if not isinstance(items, list) or type(count) is not int or count != len(items):
            raise SkillActivationError("invalid checklist counts")
        if any(not isinstance(item, str) or not item or len(item) > 256 for item in items):
            raise SkillActivationError("invalid checklist item")
        total += len(items)
    if total > 128:
        raise SkillActivationError("checklist output exceeds bounds")


class SkillActivationOwner:
    def __init__(
        self,
        catalog: ToolCatalog,
        registry: SQLiteSkillRegistry,
        dispatcher: SkillDispatcher,
        managed_root: Path,
    ) -> None:
        self._catalog = catalog
        self._registry = registry
        self._dispatcher = dispatcher
        self._verification = WorkerSupervisor(profile="python-stdlib-single")
        self._root = managed_root.absolute()
        self._review: _Review | None = None
        self._skill: InstalledSkill | None = None
        self._available = False
        self._registered = False
        self._closed = False
        self._epoch = 0
        self._lock = asyncio.Lock()
        self._slot = asyncio.Semaphore(1)
        self._jobs: set[asyncio.Task[dict[str, object]]] = set()
        self._operations: set[asyncio.Task[dict[str, object]]] = set()

    def snapshot(self) -> dict[str, object]:
        return {
            "available": not self._closed,
            "installed": self._skill is not None,
            "enabled": self._available and not self._closed,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "package_hash": self._skill.manifest_hash if self._skill else None,
            "busy": bool(self._operations),
            "authorizes_execution": False,
        }

    def _invalidate(self) -> None:
        self._available = False
        self._epoch += 1
        self._review = None

    async def _control(
        self, operation: Callable[[], Awaitable[dict[str, object]]]
    ) -> dict[str, object]:
        async def invoke() -> dict[str, object]:
            async with self._lock:
                return await operation()

        task = asyncio.create_task(invoke())
        self._operations.add(task)
        try:
            result = await asyncio.shield(task)
            self._operations.discard(task)
            return {**result, "busy": bool(self._operations)} if "busy" in result else result
        except asyncio.CancelledError:
            self._invalidate()
            # Do not cancel a transaction already in to_thread: join and fence late enable.
            try:
                await _join(task)
            except ExecutionCleanupError:
                raise
            except Exception:
                pass
            raise
        finally:
            self._operations.discard(task)

    async def initialize(self) -> None:
        epoch = self._epoch

        async def initialize() -> dict[str, object]:
            if self._closed:
                raise SkillActivationError("owner closed")
            try:
                skill = await asyncio.to_thread(_restored, self._root)
                if skill is not None:
                    # Register only an exact receipt/registry identity, even when disabled.
                    if not await self._registry.is_installed(
                        skill.manifest.id, skill.manifest.version, identity=skill
                    ):
                        raise SkillActivationError("approved registry identity missing")
                    self._skill = skill
                    self._register()
                    enabled = await self._registry.is_enabled(
                        skill.manifest.id, skill.manifest.version, identity=skill
                    )
                    if enabled:
                        try:
                            _output(await self._verification.execute(skill, {"text": ""}))
                        except SkillExecutionError:
                            enabled = False
                    self._available = enabled and epoch == self._epoch and not self._closed
            except (OSError, ValueError, KeyError, SkillActivationError):
                self._skill = None
                self._available = False
            return self.snapshot()

        await self._control(initialize)

    async def remember(self, result: dict[str, object]) -> dict[str, object]:
        epoch = self._epoch
        captured = deepcopy(result)
        return await self._control(lambda: self._remember(captured, epoch))

    async def _remember(self, result: dict[str, object], epoch: int) -> dict[str, object]:
        if self._closed or epoch != self._epoch:
            raise SkillActivationError("owner closed")
        self._review = None
        if result.get("status") != "awaiting_review":
            return result
        # Legacy compatibility fixtures have no package marker and gain no review authority.
        if all(key not in result for key in ("source", "profile", "files", "package_hash")):
            return result
        try:
            expected = _package_files()
            verification = result["verification"]
            proposal_id = result["proposal_id"]
            UUID(str(proposal_id))
            lines = expected["plugin.py"].splitlines(keepends=True)
            diff = (
                "diff --git a/src/plugin.py b/src/plugin.py\nnew file mode 100644\n"
                "--- /dev/null\n+++ b/src/plugin.py\n"
                f"@@ -0,0 +1,{len(lines)} @@\n" + "".join("+" + line for line in lines)
            )
            valid = (
                result.get("files") == expected
                and result.get("profile") == PROFILE
                and result.get("source") == f"siro_builtin_template:{PROFILE}"
                and result.get("installed") is False
                and result.get("enabled") is False
                and result.get("authorizes_execution") is False
                and result.get("tests_sha256") == hashlib.sha256(_TESTS.encode()).hexdigest()
                and result.get("source_sha256")
                == hashlib.sha256(expected["plugin.py"].encode()).hexdigest()
                and result.get("proposal_sha256") == hashlib.sha256(diff.encode()).hexdigest()
                and isinstance(verification, dict)
                and verification.get("proposal_id") == proposal_id
                and verification.get("status") == "passed"
                and verification.get("changed_paths") == ["src/plugin.py"]
                and verification.get("workspace_removed") is True
            )
            if not valid:
                raise SkillActivationError("review binding mismatch")
            package_hash = result["package_hash"]
            if not isinstance(package_hash, str):
                raise SkillActivationError("invalid package identity")
            _package_path(self._root, package_hash)
        except (KeyError, ValueError, TypeError) as error:
            raise SkillActivationError("invalid review") from error
        expected_hash = await self._control_hash()
        if package_hash != expected_hash:
            raise SkillActivationError("review package hash mismatch")
        if epoch != self._epoch or self._closed:
            raise SkillActivationError("review preparation was stopped")
        review_id = str(uuid4())
        self._review = _Review(
            review_id, package_hash, tuple(sorted(expected.items())), _now() + 900, self._epoch
        )
        return {**deepcopy(result), "review_id": review_id}

    async def _control_hash(self) -> str:
        task = asyncio.create_task(asyncio.to_thread(_template_hash))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await _join(task)
            raise

    async def install(self, review_id: str, package_hash: str) -> dict[str, object]:
        captured = self._review

        async def install() -> dict[str, object]:
            if (
                self._closed
                or captured is None
                or self._review is not captured
                or captured.epoch != self._epoch
                or captured.expires <= _now()
                or captured.review_id != review_id
                or captured.package_hash != package_hash
            ):
                raise SkillActivationError("review is stale or missing")
            if self._skill is not None or any(
                row["name"] in {CAPABILITY, "siro.text.checklist", "skill.siro.text.checklist"}
                for row in self._catalog.snapshot()
            ):
                raise SkillActivationError("capability already exists")
            skill = await asyncio.to_thread(_materialize, self._root, captured)
            if not await self._registry.install_if_absent(skill, enabled=False):
                raise SkillActivationError("installed version conflicts")
            # An interrupted receipt write leaves an unavailable disabled row, never enabled.
            await asyncio.to_thread(_persist_receipt, self._root, package_hash)
            self._skill = skill
            self._review = None
            self._register()
            return self.snapshot()

        return await self._control(install)

    async def enable(self, package_hash: str) -> dict[str, object]:
        epoch = self._epoch

        async def enable() -> dict[str, object]:
            skill = self._require(package_hash)
            self._available = False
            current = await asyncio.to_thread(_restored, self._root)
            if (
                current is None
                or current.root != skill.root
                or current.manifest_hash != skill.manifest_hash
            ):
                raise SkillActivationError("approved package changed")
            # Approved but disabled package: verify the actual strict runtime before enabling.
            _output(await self._verification.execute(current, {"text": ""}))
            if epoch != self._epoch:
                raise SkillActivationError("activation was revoked")
            try:
                if not await self._registry.set_enabled(
                    skill.manifest.id, skill.manifest.version, enabled=True, identity=skill
                ):
                    raise SkillActivationError("approved registry identity changed")
            finally:
                if epoch != self._epoch or self._closed:
                    await self._registry.set_enabled(
                        skill.manifest.id, skill.manifest.version, enabled=False, identity=skill
                    )
            if epoch != self._epoch or self._closed:
                raise SkillActivationError("activation was revoked")
            self._available = True
            return self.snapshot()

        try:
            return await self._control(enable)
        except (OSError, ValueError, SkillExecutionError) as error:
            raise SkillActivationError("approved package verification failed") from error

    def _require(self, package_hash: str) -> InstalledSkill:
        if self._closed or self._skill is None or self._skill.manifest_hash != package_hash:
            raise SkillActivationError("approved package not found")
        return self._skill

    async def _drain(self) -> None:
        jobs = tuple(self._jobs)
        for job in jobs:
            job.cancel()
        failure: ExecutionCleanupError | None = None
        for job in jobs:
            try:
                await _join(job)
            except (asyncio.CancelledError, ExecutionCancelled):
                pass
            except ExecutionCleanupError as error:
                if failure is None:
                    failure = error
            except Exception:
                # Ordinary failed results carry no surviving owned work.
                pass
        if failure is not None:
            raise failure

    async def _disable(self, *, persistent: bool) -> dict[str, object]:
        failure: Exception | None = None
        try:
            await self._drain()
        except Exception as error:
            failure = error
        skill = self._skill
        try:
            if (
                persistent
                and skill is not None
                and not await self._registry.set_enabled(
                    skill.manifest.id, skill.manifest.version, enabled=False, identity=skill
                )
            ):
                raise SkillActivationError("approved registry identity changed")
        except Exception:
            if failure is None:
                raise
        if failure is not None:
            raise failure
        return self.snapshot()

    async def revoke(self, package_hash: str) -> dict[str, object]:
        self._require(package_hash)
        self._invalidate()
        return await self._control(lambda: self._disable(persistent=True))

    async def suspend(self) -> None:
        self._invalidate()
        await self._control(lambda: self._disable(persistent=True))

    async def close(self) -> None:
        self._closed = True
        self._invalidate()
        await self._control(lambda: self._disable(persistent=False))

    def _register(self) -> None:
        if self._registered:
            return
        assert self._skill is not None

        async def unauthorized(_arguments: dict[str, object]) -> object:
            raise PermissionError("approved tool execution context required")

        self._catalog.register(
            ToolDescriptor(
                CAPABILITY,
                ToolDefinition(
                    CAPABILITY,
                    "Parse a pasted Markdown checklist into pending/completed tasks. "
                    "Text only; no files or network.",
                    deepcopy(self._skill.input_schema),
                ),
                unauthorized,
                lambda: self._available and not self._closed,
                "python-stdlib-single",
                "read",
                contextual_executor=self.execute,
                metadata=ToolMetadata(
                    display_name="整理貼上的待辦清單",
                    output_contract="pending/completed text items with exact counts; max128 tasks",
                    required_permissions=(),
                    risk_level="observe",
                    version="1.0.0",
                    provenance=f"siro_builtin_template:{PROFILE}",
                    timeout_seconds=1,
                    failure_behavior="Fail closed; no host fallback or automatic retry.",
                ),
            )
        )
        self._registered = True

    async def execute(
        self, arguments: dict[str, object], context: ExecutionContext
    ) -> dict[str, object]:
        if not context.authorized:
            raise PermissionError("approved tool execution context required")
        context.check()
        caller = asyncio.current_task()
        assert caller is not None
        cancellation_count = caller.cancelling()
        _input(arguments)
        if not self._available or self._closed or self._skill is None:
            raise SkillActivationError("skill unavailable")
        if len(self._jobs) >= 8:
            raise SkillActivationError("skill queue full")
        skill = self._skill
        epoch = self._epoch

        async def invoke() -> dict[str, object]:
            async with self._slot:
                context.check()
                if not self._available or epoch != self._epoch:
                    raise ExecutionCancelled("skill revoked")
                result = await self._dispatcher.execute(skill, deepcopy(arguments))
                context.check()
                if not self._available or epoch != self._epoch:
                    raise ExecutionCancelled("skill revoked")
                _output(result)
                return result

        job = asyncio.create_task(invoke())
        self._jobs.add(job)
        watcher = asyncio.create_task(context.cancellation.wait())
        try:
            remaining = None if context.deadline is None else max(0, context.deadline - _now())
            async with asyncio.timeout(remaining):
                await asyncio.wait((job, watcher), return_when=asyncio.FIRST_COMPLETED)
                context.check()
                result = job.result()
        finally:
            watcher.cancel()
            if not job.done():
                job.cancel()
            try:
                with suppress(asyncio.CancelledError, ExecutionCancelled):
                    await _join(job)
            finally:
                self._jobs.discard(job)
                with suppress(asyncio.CancelledError):
                    await _join(watcher)

        if caller.cancelling() > cancellation_count:
            raise asyncio.CancelledError
        context.check()
        if not self._available or self._closed or epoch != self._epoch:
            raise ExecutionCancelled("skill revoked")
        return result
