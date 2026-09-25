from datetime import UTC, datetime, timedelta

from siro.config import ProactivitySettings
from siro.core.proactivity import ProactivityContext, ProactivityRules


def test_a13_all_hard_gates_and_normal_home_choice_have_reasons() -> None:
    now = datetime(2026, 9, 25, 10, tzinfo=UTC)
    disabled = ProactivityRules(ProactivitySettings())
    assert disabled.choose(ProactivityContext(now, home_arrival=True)).reason == "disabled_by_user"

    rules = ProactivityRules(
        ProactivitySettings(enabled=True, timezone="UTC", quiet_start="23:00", quiet_end="08:00")
    )
    cases = (
        (
            ProactivityContext(datetime(2026, 9, 25, 23, 30, tzinfo=UTC), home_arrival=True),
            "quiet_hours",
        ),
        (ProactivityContext(now, home_arrival=True, busy=True), "user_busy"),
        (ProactivityContext(now, home_arrival=True, speaking=True), "already_speaking"),
        (ProactivityContext(now, home_arrival=True, social_count_today=6), "daily_limit"),
        (
            ProactivityContext(now, home_arrival=True, last_social_at=now - timedelta(minutes=10)),
            "cooldown",
        ),
    )
    for context, reason in cases:
        choice = rules.choose(context)
        assert not choice.should_speak
        assert choice.reason == reason
    normal = rules.choose(ProactivityContext(now, home_arrival=True))
    assert normal.should_speak
    assert normal.action == "greet_home"
    assert normal.reason == "home_arrival"


def test_a13_seven_day_replay_never_speaks_during_hard_gates() -> None:
    rules = ProactivityRules(ProactivitySettings(enabled=True, timezone="UTC"))
    start = datetime(2026, 9, 21, tzinfo=UTC)
    choices = []
    for quarter_hour in range(7 * 24 * 4):
        now = start + timedelta(minutes=15 * quarter_hour)
        local_hour = now.astimezone(UTC).hour
        context = ProactivityContext(
            now,
            home_arrival=quarter_hour % 17 == 0,
            overdue_task=quarter_hour % 29 == 0,
            environment_change=quarter_hour % 41 == 0,
            busy=local_hour in {9, 10, 11},
            speaking=quarter_hour % 13 == 0,
            last_social_at=now - timedelta(minutes=30) if quarter_hour % 7 == 0 else None,
            social_count_today=6 if quarter_hour % 31 == 0 else 0,
        )
        choice = rules.choose(context)
        choices.append((context, choice))
    for context, choice in choices:
        if context.busy or context.speaking or context.social_count_today >= 6:
            assert not choice.should_speak
        local_hour = context.now.hour
        if local_hour >= 23 or local_hour < 8:
            assert not choice.should_speak
    assert any(choice.should_speak for _, choice in choices)
