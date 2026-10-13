from siro.core.self_preferences import develop_self_preference


def test_self_preference_requires_repeated_experience_and_clamps_change() -> None:
    candidate = develop_self_preference("爵士樂", 1.0, ("e1",))
    assert candidate.status == "candidate"
    assert candidate.confidence < 1
    committed = develop_self_preference("爵士樂", 1.0, ("e1", "e2", "e3"))
    assert committed.status == "committed"
    assert committed.strength == 0.6
    assert committed.confidence == 1.0
