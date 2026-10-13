import pytest

from siro.core.affect import (
    ALGORITHM_VERSION,
    AffectParameters,
    AffectSystem,
    Agency,
    Appraisal,
    CopingStrategy,
    OutcomeKind,
    SelfConcern,
)


def test_affect_appraises_salient_events_and_decays() -> None:
    affect = AffectSystem()
    assert affect.appraise("s", "你又亂做真的讓人生氣").emotion == "angry"
    decayed = affect.appraise("s", "現在繼續工作")
    assert decayed.emotion == "angry"
    assert decayed.intensity < 0.7
    assert affect.appraise("s", "太棒了做得好").emotion == "happy"


def test_affect_distinguishes_user_distress() -> None:
    state = AffectSystem().appraise("s", "我今天很難過")
    assert state.emotion == "sad"
    assert state.valence < 0


def _negative(**changes: object) -> Appraisal:
    values: dict[str, object] = {
        "event_id": "event-1",
        "goal_relevance": 1.0,
        "goal_conduciveness": -1.0,
        "certainty": 0.9,
        "agency": Agency.CIRCUMSTANCE,
        "controllability": 0.2,
        "relationship_significance": 0.8,
        "urgency": 0.7,
    }
    values.update(changes)
    return Appraisal(**values)  # type: ignore[arg-type]


def test_context_changes_emotion_and_coping_for_same_bad_outcome() -> None:
    angry = AffectSystem().evaluate("anger", _negative(agency=Agency.OTHER, controllability=0.9))
    sad = AffectSystem().evaluate("sad", _negative(controllability=0.05))
    afraid = AffectSystem().evaluate(
        "fear", _negative(certainty=0.15, controllability=0.05, urgency=1.0)
    )
    guilty = AffectSystem().evaluate(
        "guilt", _negative(agency=Agency.SELF, norm_compatibility=-1.0)
    )

    assert angry.state.emotion == "anger"
    assert angry.coping.strategy is CopingStrategy.PROBLEM_SOLVE
    assert sad.state.emotion == "sadness"
    assert sad.coping.strategy is CopingStrategy.SEEK_SUPPORT
    assert afraid.state.emotion == "fear"
    assert afraid.coping.strategy is CopingStrategy.SEEK_INFORMATION
    assert guilty.state.emotion == "guilt"
    assert guilty.coping.strategy is CopingStrategy.REPAIR


def test_agency_distinguishes_pride_from_gratitude() -> None:
    def success(agency: Agency) -> Appraisal:
        return Appraisal(
            event_id="success",
            goal_relevance=1.0,
            goal_conduciveness=1.0,
            certainty=1.0,
            relationship_significance=1.0,
            agency=agency,
        )

    pride = AffectSystem().evaluate("self", success(Agency.SELF))
    gratitude = AffectSystem().evaluate("other", success(Agency.OTHER))
    assert pride.state.emotion == "pride"
    assert gratitude.state.emotion == "gratitude"


def test_mixed_emotions_mood_and_drives_persist_between_events() -> None:
    system = AffectSystem()
    result = system.evaluate(
        "s",
        Appraisal(
            event_id="novel-success",
            novelty=1.0,
            goal_relevance=1.0,
            goal_conduciveness=0.8,
            certainty=0.3,
            drive_changes={"curiosity": -0.2, "competence": -0.1},
        ),
    )
    assert len(result.emotions) >= 2
    assert result.mood.pleasure > 0
    assert result.drives.curiosity == pytest.approx(0.2)
    assert system.mood("s") == result.mood
    assert system.drives("s") == result.drives


def test_appraisal_rejects_invalid_values_and_unknown_drives() -> None:
    with pytest.raises(ValueError):
        Appraisal(event_id="bad", certainty=2.0)
    with pytest.raises(ValueError):
        Appraisal(event_id="bad", drive_changes={"hunger": 0.2})


def test_verified_outcomes_create_pride_or_guilt_and_change_competence() -> None:
    system = AffectSystem()
    success = system.appraise_outcome(
        "success", "goal-1", OutcomeKind.GOAL_COMPLETED, importance=1.0
    )
    mismatch = system.appraise_outcome(
        "failure",
        "action-1",
        OutcomeKind.ACTION_MISMATCH,
        importance=1.0,
        relationship_significance=0.8,
        controllability=0.8,
    )
    assert success.state.emotion == "pride"
    assert success.drives.competence < 0.3
    assert mismatch.state.emotion == "guilt"
    assert mismatch.coping.strategy is CopingStrategy.REPAIR
    assert mismatch.drives.competence > 0.3


def test_elapsed_time_decays_episode_and_mood_while_needs_accumulate() -> None:
    system = AffectSystem()
    event = system.appraise_outcome("s", "failure", OutcomeKind.GOAL_FAILED, importance=1.0)
    system.advance_time("s", 12.0)
    assert system.state("s").intensity < event.state.intensity
    assert abs(system.mood("s").pleasure) < abs(event.mood.pleasure)
    assert system.drives("s").rest > event.drives.rest
    assert system.drives("s").curiosity > event.drives.curiosity
    assert system.drives("s").safety <= event.drives.safety


def test_elapsed_time_rejects_negative_and_caps_extreme_gaps() -> None:
    system = AffectSystem()
    with pytest.raises(ValueError):
        system.advance_time("s", -1)
    system.advance_time("s", 24 * 365)
    assert system.drives("s").rest == 1.0
    assert 0 <= system.mood("s").arousal <= 1


def test_verified_regulation_satisfies_needs_without_leaving_bounds() -> None:
    system = AffectSystem()
    system.advance_time("s", 24)
    before = system.drives("s")
    after = system.regulate_drives("s", {"rest": -0.5, "curiosity": -0.25})
    assert after.rest < before.rest
    assert after.curiosity < before.curiosity
    assert system.regulate_drives("s", {"rest": -100}).rest == 0


def test_versioned_parameters_are_validated_and_exported() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        AffectParameters(activation_threshold=0.5, coping_threshold=0.1)
    with pytest.raises(ValueError, match="positive"):
        AffectParameters(episode_tau_hours=0)
    system = AffectSystem(parameters=AffectParameters(episode_tau_hours=2.0))
    config = system.configuration()
    assert config["version"] == ALGORITHM_VERSION
    parameters = config["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["episode_tau_hours"] == 2.0


def test_siro_own_preference_reverses_appraisal_of_same_outcome() -> None:
    likes_exploration = SelfConcern("探索", 1.0, 0.9, 1.0, ("identity-core:1",))
    dislikes_noise = SelfConcern("噪音", -1.0, 0.9, 1.0, ("experience:1",))
    system = AffectSystem()
    exploration = system.appraise_concern_outcome(
        "likes", "event-1", likes_exploration, outcome_value=1.0, certainty=1.0
    )
    noise_stopped = system.appraise_concern_outcome(
        "dislikes", "event-2", dislikes_noise, outcome_value=-1.0, certainty=1.0
    )
    noise_started = system.appraise_concern_outcome(
        "bad", "event-3", dislikes_noise, outcome_value=1.0, certainty=1.0
    )
    assert exploration.state.valence > 0
    assert noise_stopped.state.valence > 0
    assert noise_started.state.valence < 0
    assert noise_started.appraisal.goal_relevance == pytest.approx(0.9)


def test_self_concern_requires_bounds_and_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        SelfConcern("探索", 1.0, 0.5, 0.5, ())
    with pytest.raises(ValueError, match="polarity"):
        SelfConcern("探索", 2.0, 0.5, 0.5, ("source",))
