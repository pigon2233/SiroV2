"""Legacy facade and canonical decision interface stay import-compatible."""

from siro.services.computer_use import decision, execute, interface, loop, observe, stuck


def test_canonical_decision_identity_and_legacy_imports() -> None:
    for name in (
        "Decision",
        "StepRecord",
        "VerifyResult",
        "Decider",
        "DecisionError",
        "CloudScreenNotAllowed",
    ):
        assert getattr(decision, name) is getattr(interface, name)
    assert loop.Decision is interface.Decision
    assert loop.Decider is interface.Decider


def test_helper_reexports_are_exact_functions() -> None:
    assert loop._pixel_digest is observe._pixel_digest
    assert loop._same_target is observe._same_target
    assert loop._history_action is execute._history_action
    assert loop._click_ineffective_same_spot is stuck._click_ineffective_same_spot


def test_default_factory_still_optional_local_backend() -> None:
    assert isinstance(decision.make_decider({}), decision.OllamaVisionDecider)
