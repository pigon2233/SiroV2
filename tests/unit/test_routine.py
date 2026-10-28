from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from siro.services.agent.routine import MIN_DAYS, build_profile, detect

ZONE = "Asia/Taipei"
TZ = ZoneInfo(ZONE)


def _day(offset: int) -> list[datetime]:
    """Motion every 30 minutes from 08:00 to 23:30 local, `offset` days before the 20th."""

    base = datetime(2026, 5, 20, tzinfo=TZ) - timedelta(days=offset)
    return [base + timedelta(hours=8, minutes=30 * i) for i in range(32)]


def _history(days: int = 7) -> list[datetime]:
    return [moment.astimezone(UTC) for offset in range(1, days + 1) for moment in _day(offset)]


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 20, hour, minute, tzinfo=TZ).astimezone(UTC)


def test_profile_needs_enough_days() -> None:
    assert build_profile(_history(MIN_DAYS - 1), _at(12), ZONE) is None


def test_profile_learns_wake_and_bedtime() -> None:
    profile = build_profile(_history(), _at(12), ZONE)
    assert profile is not None
    assert (profile.wake_minute, profile.bed_minute) == (4 * 60, 19 * 60 + 30)
    assert profile.home_ratio[10] == pytest.approx(1.0)
    assert profile.home_ratio[3] == 0.0


def test_today_is_not_its_own_baseline() -> None:
    today = [moment.astimezone(UTC) for moment in _day(0)]
    assert build_profile(today, _at(12), ZONE) is None


def test_late_awake_fires_only_with_recent_motion_and_light() -> None:
    profile = build_profile(_history(), _at(12), ZONE)
    assert profile is not None
    now = _at(2)
    kwargs = {"now": now, "zone": ZONE, "last_seen": now}
    found = detect(profile, last_motion=now - timedelta(minutes=5), last_lux=80.0, **kwargs)
    assert found is not None and found["trigger"] == "late_awake"
    assert detect(profile, last_motion=now - timedelta(hours=2), last_lux=80.0, **kwargs) is None
    assert detect(profile, last_motion=now - timedelta(minutes=5), last_lux=1.0, **kwargs) is None
    assert (
        detect(profile, last_motion=_at(23, 30) - timedelta(days=1), last_lux=80.0, **kwargs)
        is None
    )


def test_unexpected_absence_needs_a_live_sensor() -> None:
    profile = build_profile(_history(), _at(12), ZONE)
    assert profile is not None
    now = _at(15)
    quiet_since = now - timedelta(hours=4)
    found = detect(
        profile, now=now, zone=ZONE, last_motion=quiet_since, last_lux=90.0, last_seen=now
    )
    assert found is not None and found["trigger"] == "unexpected_absence"
    assert found["quiet_minutes"] == 240
    offline = now - timedelta(hours=2)
    assert (
        detect(
            profile, now=now, zone=ZONE, last_motion=quiet_since, last_lux=90.0, last_seen=offline
        )
        is None
    )


def test_sleeping_hours_are_not_absence() -> None:
    profile = build_profile(_history(), _at(12), ZONE)
    assert profile is not None
    now = _at(5)
    found = detect(
        profile,
        now=now,
        zone=ZONE,
        last_motion=now - timedelta(hours=6),
        last_lux=1.0,
        last_seen=now,
    )
    assert found is None
