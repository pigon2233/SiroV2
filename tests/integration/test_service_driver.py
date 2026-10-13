from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from siro.adapters.computer import ComputerActionError, ScopeViolation
from siro.adapters.services import (
    CriticalInstallApproval,
    SystemdUserServiceDriver,
    SystemdUserUnitInstaller,
)
from siro.core.outcomes import ActionOutcome


class CapturingOutcomes:
    def __init__(self) -> None:
        self.values: list[tuple[str, ActionOutcome, object | None, object | None]] = []

    async def report_action(
        self,
        action_id: str,
        outcome: ActionOutcome,
        *,
        occurred_at: datetime,
        importance: float,
        controllability: float,
        expected: object | None = None,
        observed: object | None = None,
    ) -> None:
        del occurred_at, importance, controllability
        self.values.append((action_id, outcome, expected, observed))


@pytest.mark.asyncio
async def test_t25_service_scope_readback_idempotency_and_critical_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit = "siro-test.service"
    outcomes = CapturingOutcomes()
    driver = SystemdUserServiceDriver(frozenset({unit}), outcome_reporter=outcomes)
    state = {"active": False, "reloads": 0, "changes": 0}

    async def fake_run(*arguments: str) -> str:
        if arguments[0] == "show":
            active = "active" if state["active"] else "inactive"
            return f"{active}\n{'running' if state['active'] else 'dead'}\n123"
        if arguments[0] == "daemon-reload":
            state["reloads"] += 1
            return ""
        state["active"] = arguments[0] == "start"
        state["changes"] += 1
        return ""

    monkeypatch.setattr(driver, "_run", fake_run)
    with pytest.raises(ScopeViolation):
        await driver.status("ssh.service")
    assert (await driver.start("start-1", unit)).active_state == "active"
    assert (await driver.start("start-1", unit)).active_state == "active"
    assert state["changes"] == 1
    with pytest.raises(ComputerActionError, match="different arguments"):
        await driver.stop("start-1", unit)
    assert (await driver.stop("stop-1", unit)).active_state == "inactive"
    assert outcomes.values == [
        ("start-1", "confirmed", "active", "active"),
        ("stop-1", "confirmed", "inactive", "inactive"),
    ]

    content = "[Service]\nExecStart=/usr/bin/true\n"
    installer = SystemdUserUnitInstaller(tmp_path / "units", driver)
    pending = installer.approval_request("install-1", unit, content)
    with pytest.raises(ScopeViolation, match="approval"):
        await installer.install("install-1", unit, content, pending)
    approval = CriticalInstallApproval(
        pending.action_id, pending.unit, pending.content_sha256, "owner"
    )
    path = await installer.install("install-1", unit, content, approval)
    assert path.read_text() == content
    assert path.stat().st_mode & 0o777 == 0o600
    assert state["reloads"] == 1
    assert await installer.install("install-1", unit, content, approval) == path
    with pytest.raises(ScopeViolation):
        await installer.install("install-2", unit, content + "# changed", approval)
