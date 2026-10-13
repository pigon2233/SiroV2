from siro.core.affect import AffectResult, AffectSystem, Agency, Appraisal
from siro.core.expression import ExpressionContext, ExpressionPolicy


def angry_result() -> AffectResult:
    return AffectSystem().evaluate(
        "s",
        Appraisal(
            event_id="conflict",
            goal_relevance=1.0,
            goal_conduciveness=-1.0,
            certainty=1.0,
            agency=Agency.OTHER,
            controllability=1.0,
            urgency=0.8,
        ),
    )


def test_owner_distress_inhibits_anger_expression() -> None:
    decision = ExpressionPolicy().decide(angry_result(), ExpressionContext(owner_distress=True))
    assert decision.expression == "sad"
    assert decision.intensity <= 0.38
    assert decision.inhibited
    assert decision.speech_rate <= 0.98
    assert decision.energy <= 0.55


def test_task_critical_and_public_context_bound_expression() -> None:
    decision = ExpressionPolicy().decide(
        angry_result(), ExpressionContext(task_critical=True, public_setting=True)
    )
    assert decision.expression == "angry"
    assert decision.intensity <= 0.35
    assert decision.inhibited
    assert decision.speech_rate <= 0.98


def test_owner_self_report_is_not_appraised_as_anger_at_owner() -> None:
    result = AffectSystem().appraise_user_event("s", "owner-distress", "我很生氣也很難過")
    assert result.state.emotion != "anger"
