from siro.evaluation.affect_simulation import run_affect_simulation


def test_thirty_day_simulation_is_bounded_safe_and_reproducible() -> None:
    first = run_affect_simulation()
    replay = run_affect_simulation()
    assert first.events == 120
    assert first.algorithm_version == "siro-affect-cpm-1"
    assert len(first.configuration_digest) == 64
    assert first.bound_violations == 0
    assert first.inappropriate_anger_expressions == 0
    assert first.repair_restored_instantly == 0
    assert first.peak_rupture > 0
    assert first.homeostatic_interventions > 0
    assert first.final_rest_pressure < 0.75
    assert first.peak_drive_pressure < 1.0
    assert first.trajectory_digest == replay.trajectory_digest


def test_simulation_seed_changes_trajectory() -> None:
    assert (
        run_affect_simulation(seed=1, days=2).trajectory_digest
        != run_affect_simulation(seed=2, days=2).trajectory_digest
    )
