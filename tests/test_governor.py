import asyncio

import pytest

from siro.core.governor import Admission, ComputeGovernor, ResourceSnapshot


def snapshot(available: int, slots: int = 0) -> ResourceSnapshot:
    return ResourceSnapshot(1000, available, slots)


def test_t33_hysteresis_slots_and_cloud_budget_are_hard_gates() -> None:
    governor = ComputeGovernor(high_water=0.15, low_water=0.25, max_slots=1)
    assert governor.admit(snapshot(500), cloud=False, cloud_budget=1) is Admission.ALLOW
    assert not governor.background_paused
    assert governor.admit(snapshot(100), cloud=False, cloud_budget=1) is Admission.DENY_MEMORY
    assert governor.background_paused
    assert governor.admit(snapshot(200), cloud=False, cloud_budget=1) is Admission.ALLOW
    assert governor.background_paused  # Hysteresis holds pause between water marks.
    assert governor.admit(snapshot(300), cloud=False, cloud_budget=1) is Admission.ALLOW
    assert not governor.background_paused
    assert (
        governor.admit(snapshot(500, slots=1), cloud=False, cloud_budget=1) is Admission.DENY_SLOTS
    )
    assert governor.admit(snapshot(500), cloud=True, cloud_budget=0) is Admission.DENY_CLOUD_BUDGET


@pytest.mark.asyncio
async def test_t33_pressure_pauses_background_without_blocking_control_or_cancel() -> None:
    governor = ComputeGovernor()
    cancelled = asyncio.Event()
    control_ticks = 0

    async def background() -> None:
        while not cancelled.is_set():
            assert (
                governor.admit(snapshot(100), cloud=False, cloud_budget=1) is Admission.DENY_MEMORY
            )
            await asyncio.sleep(0)

    async def control() -> None:
        nonlocal control_ticks
        for _ in range(20):
            control_ticks += 1
            await asyncio.sleep(0)
        cancelled.set()

    await asyncio.gather(background(), control())
    assert governor.background_paused
    assert control_ticks == 20
