"""Allowlisted user-systemd service control and exact-hash critical installation."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from siro.adapters.computer import ComputerActionError, ScopeViolation
from siro.core.outcomes import ActionOutcomeReporter


@dataclass(frozen=True, slots=True)
class ServiceStatus:
    unit: str
    active_state: str
    sub_state: str
    main_pid: int


@dataclass(frozen=True, slots=True)
class CriticalInstallApproval:
    action_id: str
    unit: str
    content_sha256: str
    approved_by: str


class SystemdUserServiceDriver:
    def __init__(
        self,
        allowed_units: frozenset[str],
        *,
        outcome_reporter: ActionOutcomeReporter | None = None,
    ) -> None:
        if not allowed_units:
            raise ValueError("at least one systemd unit must be allowlisted")
        self._allowed_units = allowed_units
        self._outcomes = outcome_reporter
        self._ledger: dict[str, tuple[str, str, ServiceStatus]] = {}

    async def status(self, unit: str) -> ServiceStatus:
        self._require_unit(unit)
        output = await self._run(
            "show",
            unit,
            "--property=ActiveState,SubState,MainPID",
            "--value",
        )
        values = output.splitlines()
        if len(values) != 3:
            raise ComputerActionError("systemd returned an invalid service status")
        active_state, sub_state, pid = values
        return ServiceStatus(unit, active_state, sub_state, int(pid or "0"))

    async def start(self, action_id: str, unit: str) -> ServiceStatus:
        return await self._change(action_id, "start", unit)

    async def stop(self, action_id: str, unit: str) -> ServiceStatus:
        return await self._change(action_id, "stop", unit)

    async def reload(self) -> None:
        await self._run("daemon-reload")

    async def _change(self, action_id: str, operation: str, unit: str) -> ServiceStatus:
        self._require_unit(unit)
        previous = self._ledger.get(action_id)
        if previous is not None:
            if previous[:2] != (operation, unit):
                raise ComputerActionError("service action id was reused with different arguments")
            return previous[2]
        await self._run(operation, unit)
        status = await self.status(unit)
        expected = "active" if operation == "start" else "inactive"
        if status.active_state != expected:
            if self._outcomes is not None:
                await self._outcomes.report_action(
                    action_id,
                    "mismatch",
                    occurred_at=datetime.now(UTC),
                    importance=0.65,
                    controllability=0.8,
                    expected=expected,
                    observed=status.active_state,
                )
            raise ComputerActionError(
                f"service readback mismatch: expected {expected}, got {status.active_state}"
            )
        self._ledger[action_id] = (operation, unit, status)
        if self._outcomes is not None:
            await self._outcomes.report_action(
                action_id,
                "confirmed",
                occurred_at=datetime.now(UTC),
                importance=0.65,
                controllability=0.8,
                expected=expected,
                observed=status.active_state,
            )
        return status

    def _require_unit(self, unit: str) -> None:
        if unit not in self._allowed_units:
            raise ScopeViolation(f"systemd unit is not allowlisted: {unit}")

    async def _run(self, *arguments: str) -> str:
        process = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "--no-pager",
            *arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise ComputerActionError("systemd operation timed out") from error
        if process.returncode:
            reason = stderr.decode(errors="replace").strip()[:512]
            raise ComputerActionError(f"systemd operation failed: {reason}")
        return stdout.decode().strip()


class SystemdUserUnitInstaller:
    def __init__(self, unit_directory: Path, driver: SystemdUserServiceDriver) -> None:
        self._unit_directory = unit_directory.resolve()
        self._driver = driver
        self._ledger: dict[str, str] = {}

    @staticmethod
    def approval_request(action_id: str, unit: str, content: str) -> CriticalInstallApproval:
        return CriticalInstallApproval(
            action_id=action_id,
            unit=unit,
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            approved_by="PENDING",
        )

    async def install(
        self,
        action_id: str,
        unit: str,
        content: str,
        approval: CriticalInstallApproval,
    ) -> Path:
        self._driver._require_unit(unit)
        if "/" in unit or not unit.endswith(".service"):
            raise ValueError("only simple .service unit names are accepted")
        digest = hashlib.sha256(content.encode()).hexdigest()
        if (
            approval.action_id != action_id
            or approval.unit != unit
            or approval.content_sha256 != digest
            or approval.approved_by == "PENDING"
        ):
            raise ScopeViolation("critical install approval does not match the exact unit content")
        previous = self._ledger.get(action_id)
        if previous is not None:
            if previous != digest:
                raise ComputerActionError("install action id was reused with different content")
            return self._unit_directory / unit
        self._unit_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination = self._unit_directory / unit
        descriptor, temporary = tempfile.mkstemp(prefix=".siro-unit-", dir=self._unit_directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        await self._driver.reload()
        self._ledger[action_id] = digest
        return destination
