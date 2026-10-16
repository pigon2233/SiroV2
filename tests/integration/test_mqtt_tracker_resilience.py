from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from siro.services.devices.mqtt import CommandTracker, DeliveryState, DeviceCommand


def command(identifier: str, expires_at: datetime | None = None) -> DeviceCommand:
    return DeviceCommand(
        command_id=identifier,
        action="light.set",
        desired_state={"power": True},
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.mark.parametrize(
    "status", ["expired_or_invalid", "unsupported", "duplicate", "accepted", ""]
)
def test_rejected_ack_never_confirms_even_with_matching_readback(status: str) -> None:
    tracker = CommandTracker()
    tracker.issue("esp32-lab-01", command("rejected"))
    result = tracker.acknowledge("rejected", status=status)
    assert result is not None and result.value == "failed"
    assert tracker.state("rejected").value == "failed"
    assert tracker.observe_state("esp32-lab-01", {"power": True}) == ()
    assert tracker.acknowledge("rejected", status="applied") is result


@pytest.mark.parametrize("status", ["applied", "unsupported"])
def test_foreign_ack_is_ignored_without_key_error(status: str) -> None:
    tracker = CommandTracker()
    assert tracker.acknowledge("not-owned", status=status) is None


def test_legacy_one_argument_ack_ignores_unknown_id_and_accepts_known_id() -> None:
    tracker = CommandTracker()
    assert tracker.acknowledge("not-owned") is None
    tracker.issue("esp32-lab-01", command("trusted"))
    assert tracker.acknowledge("trusted") is DeliveryState.ACKNOWLEDGED


def test_readback_without_accepted_ack_does_not_confirm_pending_command() -> None:
    tracker = CommandTracker()
    tracker.issue("esp32-lab-01", command("pending"))
    assert tracker.observe_state("esp32-lab-01", {"power": True}) == ()
    assert tracker.state("pending") is DeliveryState.PENDING


def test_late_or_duplicate_ack_does_not_regress_accepted_or_confirmed_delivery() -> None:
    tracker = CommandTracker()
    tracker.issue("esp32-lab-01", command("applied"))
    assert tracker.acknowledge("applied", status="applied") is DeliveryState.ACKNOWLEDGED
    assert tracker.acknowledge("applied", status="duplicate") is DeliveryState.ACKNOWLEDGED
    assert tracker.observe_state("another-device", {"power": True}) == ()
    assert tracker.observe_state("esp32-lab-01", {"power": False}) == ()
    assert tracker.observe_state("esp32-lab-01", {"power": True}) == ("applied",)
    for status in ("applied", "duplicate", "unsupported"):
        assert tracker.acknowledge("applied", status=status) is DeliveryState.CONFIRMED


def test_active_capacity_refuses_new_work_without_losing_owned_commands() -> None:
    tracker = CommandTracker(max_commands=2)
    tracker.issue("esp32-lab-01", command("one"))
    tracker.issue("esp32-lab-01", command("two"))
    with pytest.raises(ValueError, match="capacity"):
        tracker.issue("esp32-lab-01", command("three"))
    assert tracker.state("one") is tracker.state("two") is DeliveryState.PENDING
    tracker.acknowledge("one", status="unsupported")
    tracker.issue("esp32-lab-01", command("three"))
    assert tracker.state("two") is tracker.state("three") is DeliveryState.PENDING
    assert tracker.acknowledge("one", status="applied") is None


def test_completed_history_is_reclaimed_during_long_running_issue_sequence() -> None:
    tracker = CommandTracker(max_commands=2)
    for index in range(1000):
        identifier = f"command-{index}"
        tracker.issue("esp32-lab-01", command(identifier))
        tracker.acknowledge(identifier, status="applied")
        assert tracker.observe_state("esp32-lab-01", {"power": True}) == (identifier,)
    assert tracker.prune() == 1
    assert tracker.acknowledge("command-999", status="applied") is None


def test_explicit_prune_removes_expired_but_keeps_unexpired_active_commands() -> None:
    now = datetime.now(UTC)
    tracker = CommandTracker(max_commands=2)
    tracker.issue("esp32-lab-01", command("soon", now + timedelta(seconds=1)))
    tracker.issue("esp32-lab-01", command("later", now + timedelta(hours=1)))
    assert tracker.prune(now=now + timedelta(seconds=2)) == 1
    assert tracker.acknowledge("soon", status="applied") is None
    assert tracker.state("later") is DeliveryState.PENDING
    with pytest.raises(ValueError, match="timezone"):
        tracker.prune(now=now.replace(tzinfo=None))
    assert tracker.state("later") is DeliveryState.PENDING


@pytest.mark.parametrize("limit", [0, -1, 10001])
def test_tracker_capacity_is_bounded(limit: int) -> None:
    with pytest.raises(ValueError):
        CommandTracker(max_commands=limit)
