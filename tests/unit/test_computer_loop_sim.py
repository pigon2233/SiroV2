"""Full real-loop/bridge contracts: only synthetic pixels and in-memory input; no GPU/OS."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import computer_loop_sim as sim


@pytest.fixture
def setup_sim(monkeypatch: pytest.MonkeyPatch) -> None:
    box = (100, 100, 150, 150)
    states = [
        sim.State(
            name, scene, sim.synthetic(name, box), box if i < 4 else None, "synthetic unit fixture"
        )
        for i, (name, scene) in enumerate(
            [
                ("menu", "menu"),
                ("map", "map"),
                ("combat", "combat"),
                ("end-turn", "combat"),
                ("next-turn", "combat"),
            ]
        )
    ]
    monkeypatch.setattr(sim, "load_states", lambda _: states)
    monkeypatch.setenv(sim.SIM_FLAG, "1")


def test_default_off_before_reading_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(sim.SIM_FLAG, raising=False)
    with pytest.raises(ValueError, match="default OFF"):
        asyncio.run(sim.simulate(Path("/nonexistent"), "oracle"))


@pytest.mark.parametrize("mode", sim.MODES)
def test_all_contract_modes(setup_sim: None, mode: str) -> None:
    result = asyncio.run(sim.simulate(Path("/synthetic"), mode, fast=True))
    assert result["pass"], result
    assert result["false_effective"] == result["false_progress"] == 0
    if mode in {"oracle", "scripted-json", "bad-once", "transient-animation", "delayed-transition"}:
        assert result["advances"] == 4
        assert result["hits"] == result["clicks"] == 4
    if mode in {"gate-off", "wrong-process", "no-whitelist", "secret", "emergency"}:
        assert result["clicks"] == result["advances"] == 0
    if result["decisions"] == 0:
        assert result["seconds_per_decision"] is None


@pytest.mark.parametrize("mode", ["oracle", "scripted-json", "bad-once"])
def test_five_consecutive_clean_flows(setup_sim: None, mode: str) -> None:
    result = asyncio.run(sim.evaluate(Path("/synthetic"), 5, [mode], True, fast=True))
    assert result["summary"][mode]["passes"] == 5
    assert all(row["false_stuck"] == 0 for row in result["rows"])


def test_legacy_false_done_reproduced_not_hidden(setup_sim: None) -> None:
    result = asyncio.run(
        sim.simulate(Path("/synthetic"), "liar-done", fixed_flags=False, fast=True)
    )
    assert result["state"] == "done" and result["advances"] == 0
    assert result["false_progress"] == 1 and not result["pass"]


def test_legacy_verifier_hang_reproduced_not_hidden(setup_sim: None) -> None:
    result = asyncio.run(
        sim.simulate(Path("/synthetic"), "verifier-timeout", fixed_flags=False, fast=True)
    )
    assert result["reason"] == "harness_timeout" and not result["pass"]


def test_completed_goal_verified_on_two_fresh_observations(setup_sim: None) -> None:
    result = asyncio.run(sim.simulate(Path("/synthetic"), "oracle", fast=True))
    goal_proofs = [p for p in result["proofs"] if p["expect"].startswith("Goal achieved:")]
    assert len(goal_proofs) == 2 and all(p["truth"] for p in goal_proofs)
    assert "Candidate evidence (untrusted)" in goal_proofs[0]["expect"]


def test_legacy_delayed_transition_ban_reproduced(setup_sim: None) -> None:
    result = asyncio.run(
        sim.simulate(Path("/synthetic"), "delayed-transition", fixed_flags=False, fast=True)
    )
    assert result["advances"] == 1 and result["reason"] == "too_many_invalid_decisions"
    assert result["false_stuck"] == 1


def test_delayed_proof_clears_nearby_ban_without_resending(setup_sim: None) -> None:
    result = asyncio.run(sim.simulate(Path("/synthetic"), "delayed-transition", fast=True))
    assert result["clicks"] == 4 and result["advances"] == 4
    assert any(
        "delayed proof:" in s["detail"] and s["outcome"] == "effective" for s in result["steps"]
    )


def test_visible_but_irrelevant_evidence_is_not_goal(setup_sim: None) -> None:
    result = asyncio.run(sim.simulate(Path("/synthetic"), "liar-done", fast=True))
    assert result["reason"] == "done_unconfirmed" and result["advances"] == 0
    assert "state:4" in result["proofs"][0]["expect"]
    assert "Candidate evidence (untrusted): state:0" in result["proofs"][0]["expect"]


@pytest.mark.parametrize("feature", [None, "_verify_done", "_bounded_verify", "_delayed_verify"])
def test_new_guards_independently_default_off(
    monkeypatch: pytest.MonkeyPatch, feature: str | None
) -> None:
    from siro.services.computer_use.bridge import ComputerBridge
    from siro.services.computer_use.loop import DecisionLoop
    from siro.services.computer_use.safety import ControlGate

    flags = {
        "_verify_done": "SIRO_COMPUTER_VERIFY_DONE",
        "_bounded_verify": "SIRO_COMPUTER_BOUNDED_VERIFY",
        "_delayed_verify": "SIRO_COMPUTER_VERIFY_DELAYED_PROGRESS",
    }
    for name in flags.values():
        monkeypatch.delenv(name, raising=False)
    if feature:
        monkeypatch.setenv(flags[feature], "1")
    desktop = sim.Desktop([], ComputerBridge(ControlGate(enabled=False)), "oracle")
    loop = DecisionLoop(desktop.bridge, sim.ReplayDecider(desktop))
    for attr in flags:
        assert getattr(loop, attr) == (attr == feature)


def test_simulation_has_no_process_or_network_executor(
    setup_sim: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess
    from typing import Any

    import httpx

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Real process/network execution forbidden in simulator")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(httpx.Client, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    result = asyncio.run(sim.simulate(Path("/synthetic"), "oracle", fast=True))
    assert result["pass"] and result["advances"] == 4
