"""Daily-routine learning: when the owner usually wakes, sleeps and is home, from PIR/light history.

Pure statistics over `world_observations`; `RoutineWatcher.check` only says *when* an anomaly
(still awake very late, nobody home at a usual home time) may reach SIRO. She decides whether and
what to say through the same sensor-reaction path (`react_to_sensor`), and may stay silent.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from siro.persistence.sqlite import SQLiteStore

HISTORY_DAYS = 21
MIN_DAYS = 5
MIN_EVENTS_PER_DAY = 10
DAY_START_HOUR = 4  # a "day" runs 04:00-04:00 so a night owl's evening stays on one day
LATE_AFTER = timedelta(hours=2)
LATE_ACTIVE_WITHIN = timedelta(minutes=20)
ABSENT_AFTER = timedelta(hours=3)
ALIVE_WITHIN = timedelta(minutes=30)
HOME_RATIO = 0.7
DARK_LUX = 5.0
COOLDOWNS = {"late_awake": timedelta(hours=12), "unexpected_absence": timedelta(hours=6)}


@dataclass(frozen=True)
class RoutineProfile:
    wake_minute: int  # minutes after 04:00 of the usual first motion
    bed_minute: int  # minutes after 04:00 of the usual last motion
    home_ratio: tuple[float, ...]  # per local hour: share of days with motion in that hour
    days: int


def _shifted(moment: datetime, zone: ZoneInfo) -> datetime:
    return moment.astimezone(zone) - timedelta(hours=DAY_START_HOUR)


def _minutes(shifted: datetime) -> int:
    return shifted.hour * 60 + shifted.minute


def build_profile(motion: list[datetime], now: datetime, zone: str) -> RoutineProfile | None:
    """None until enough complete past days exist; today is never part of its own baseline."""

    tz = ZoneInfo(zone)
    today = _shifted(now, tz).date()
    by_day: dict[object, list[datetime]] = {}
    for moment in motion:
        local = _shifted(moment, tz)
        if local.date() != today:
            by_day.setdefault(local.date(), []).append(local)
    days = [events for events in by_day.values() if len(events) >= MIN_EVENTS_PER_DAY]
    if len(days) < MIN_DAYS:
        return None
    wake = statistics.median(_minutes(min(events)) for events in days)
    bed = statistics.median(_minutes(max(events)) for events in days)
    hours = [0.0] * 24
    for events in days:
        for hour in {(event.hour + DAY_START_HOUR) % 24 for event in events}:
            hours[hour] += 1 / len(days)
    return RoutineProfile(int(wake), int(bed), tuple(hours), len(days))


def _clock(minute_after_start: int) -> str:
    total = (minute_after_start + DAY_START_HOUR * 60) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def detect(
    profile: RoutineProfile,
    *,
    now: datetime,
    zone: str,
    last_motion: datetime | None,
    last_lux: float | None,
    last_seen: datetime | None,
) -> dict[str, object] | None:
    """One anomaly's facts for the sensor prompt, or None when today looks ordinary."""

    local = now.astimezone(ZoneInfo(zone))
    minute = _minutes(_shifted(now, ZoneInfo(zone)))
    usual = {"usual_wake": _clock(profile.wake_minute), "usual_bedtime": _clock(profile.bed_minute)}
    base: dict[str, object] = {"time": local.strftime("%H:%M"), **usual}
    if (
        minute >= profile.bed_minute + LATE_AFTER.total_seconds() // 60
        and last_motion is not None
        and now - last_motion <= LATE_ACTIVE_WITHIN
        and (last_lux is None or last_lux > DARK_LUX)
    ):
        return {"trigger": "late_awake", **base}
    if (
        last_seen is not None
        and now - last_seen <= ALIVE_WITHIN  # a silent sensor means "unknown", not "away"
        and profile.wake_minute < minute < profile.bed_minute
        and (last_motion is None or now - last_motion >= ABSENT_AFTER)
    ):
        window = [(local.hour - back) % 24 for back in range(3)]
        if all(profile.home_ratio[hour] >= HOME_RATIO for hour in window):
            quiet = int((now - last_motion).total_seconds() // 60) if last_motion else None
            return {
                "trigger": "unexpected_absence",
                **base,
                **({"quiet_minutes": quiet} if quiet is not None else {}),
            }
    return None


@dataclass(frozen=True)
class RoutineView:
    profile: RoutineProfile | None
    last_motion: datetime | None
    last_lux: float | None
    last_seen: datetime | None


class RoutineWatcher:
    def __init__(self, store: SQLiteStore, *, zone: str = "Asia/Taipei") -> None:
        self._store = store
        self._zone = zone
        self._last_by: dict[str, datetime] = {}

    async def check(self, now: datetime | None = None) -> dict[str, object] | None:
        """Facts of an anomaly that may be raised now (cooldown applied), else None."""

        now = now or datetime.now(UTC)
        view = await self.view(now)
        if view.profile is None:
            return None
        found = detect(
            view.profile,
            now=now,
            zone=self._zone,
            last_motion=view.last_motion,
            last_lux=view.last_lux,
            last_seen=view.last_seen,
        )
        if found is None:
            return None
        trigger = str(found["trigger"])
        last = self._last_by.get(trigger)
        if last is not None and now - last < COOLDOWNS[trigger]:
            return None
        self._last_by[trigger] = now
        return found

    async def view(self, now: datetime) -> RoutineView:
        """What the sensors and history say right now; shared by anomaly detection and scenes."""

        motion, last_lux, last_seen = await self._read(now)
        return RoutineView(
            build_profile(motion, now, self._zone),
            max(motion) if motion else None,
            last_lux,
            last_seen,
        )

    async def _read(self, now: datetime) -> tuple[list[datetime], float | None, datetime | None]:
        since = (now - timedelta(days=HISTORY_DAYS)).isoformat()

        def read(c: sqlite3.Connection) -> tuple[list[datetime], float | None, datetime | None]:
            rows = c.execute(
                "SELECT value_json, observed_at FROM world_observations "
                "WHERE property='motion' AND observed_at>=? ORDER BY observed_at",
                (since,),
            ).fetchall()
            motion = [datetime.fromisoformat(r["observed_at"]) for r in rows if _truthy(r)]
            lux_row = c.execute(
                "SELECT value_json FROM world_observations WHERE property='illuminance' "
                "ORDER BY observed_at DESC LIMIT 1"
            ).fetchone()
            seen_row = c.execute(
                "SELECT observed_at FROM world_observations "
                "WHERE property IN ('motion','illuminance') ORDER BY observed_at DESC LIMIT 1"
            ).fetchone()
            lux = _number(lux_row["value_json"]) if lux_row else None
            seen = datetime.fromisoformat(seen_row["observed_at"]) if seen_row else None
            return motion, lux, seen

        return await self._store.run_transaction(read)


def _truthy(row: sqlite3.Row) -> bool:
    try:
        return json.loads(row["value_json"]) is True
    except ValueError:
        return False


def _number(raw: str) -> float | None:
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return float(value) if type(value) in (int, float) else None
