"""Expectation proof evaluation; visual change alone is never success."""

from __future__ import annotations

from typing import Protocol

from siro.services.computer_use.interface import Decider, StepRecord, VerifyResult
from siro.services.computer_use.observe import _screen_changed
from siro.services.computer_use.perception import Observation


class VerificationContext(Protocol):
    phase: str

    async def _verify_expect(
        self, expect: str, before_seen: str, observation: Observation
    ) -> VerifyResult: ...


async def verify_expect(
    decider: Decider, expect: str, before_seen: str, observation: Observation
) -> VerifyResult:
    verify = getattr(decider, "verify", None)
    if verify is None:
        return VerifyResult("unknown", "尚未確認: no verifier")
    try:
        result = await verify(expect, before_seen, observation)
    except Exception as error:  # — verify must never crash the run
        return VerifyResult("unknown", f"尚未確認: {type(error).__name__}")
    if isinstance(result, VerifyResult):
        return result
    return VerifyResult("unknown", "尚未確認: bad verify result")


async def verify_step(
    context: VerificationContext, before: Observation, observation: Observation, prev: StepRecord
) -> tuple[StepRecord, bool]:
    changed = _screen_changed(before, observation)
    scene = prev.scene
    seen = prev.seen
    if changed is False:
        outcome = "ineffective"
        detail = f"no visual_change after expect={prev.expect or '-'}"
        unresolved = True
    elif changed is True:
        # Fingerprint only proves pixels moved — confirm expect on this frame.
        outcome = "visual_change"
        detail = "visual_change; verifying expect"
        context.phase = "verifying"
        verify = await context._verify_expect(prev.expect, prev.seen, observation)
        scene = verify.scene or scene
        seen = verify.seen or seen
        if verify.status == "confirmed":
            outcome = "effective"
            detail = verify.detail or f"expect confirmed: {prev.expect}"
            unresolved = False
        elif verify.status == "denied":
            outcome = "ineffective"
            detail = verify.detail or f"expect not met: {prev.expect}"
            unresolved = True
        else:
            outcome = "unconfirmed"
            detail = verify.detail or "尚未確認"
            unresolved = True
    else:
        outcome = "unconfirmed"
        detail = prev.detail or "尚未確認"
        unresolved = True
    updated = StepRecord(
        prev.step,
        prev.action,
        prev.expect,
        outcome,
        changed,
        seen,
        scene,
        detail,
    )
    return updated, unresolved
