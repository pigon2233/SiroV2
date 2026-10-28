"""How SIRO reacts to the ESP32 node: she decides for herself whether a change is worth a word.

Pure rules over already-validated sensor events. They only say *when* a trigger may reach her
(cooldowns, rate limit, quiet hours, dark room); the model decides *whether* and *what* to say.
"""

# ruff: noqa: RUF001
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from siro.config import ProactivitySettings
from siro.core.touch import clean_touch_line

DARK_LUX = 5.0
# Hysteresis: a dim room that flickers around the threshold must not toggle quiet mode.
BRIGHT_LUX = 15.0
AWAY_AFTER = timedelta(minutes=15)
LONG_ACTIVE_AFTER = timedelta(hours=3)
GLOBAL_GAP = timedelta(minutes=10)
COOLDOWNS = {
    "arrival": timedelta(minutes=30),
    "departure": timedelta(hours=1),
    "dark": timedelta(hours=1),
    "long_active": timedelta(hours=3),
}
FALLBACK_LINES = {"arrival": ("早安，今天也請多指教。", "歡迎回來。")}
_SILENT = re.compile(r"^\W*(silent|沉默|不說話|不用說)", re.IGNORECASE)


def parse_quiet_hours(value: str | None) -> tuple[int, int] | None:
    """`23:00-07:00` as minutes of the day; empty or None means no quiet hours."""

    if not value:
        return None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", value.strip())
    if match is None:
        raise ValueError("SIRO_SENSOR_QUIET_HOURS must look like 23:00-07:00")
    a, b, c, d = (int(part) for part in match.groups())
    if a > 23 or c > 23 or b > 59 or d > 59:
        raise ValueError("SIRO_SENSOR_QUIET_HOURS must look like 23:00-07:00")
    start, end = a * 60 + b, c * 60 + d
    return None if start == end else (start, end)


class SensorReactions:
    """`handle`/`tick` return effects: `speak:<trigger>`, `quiet_on`, `quiet_off` or `listen`."""

    def __init__(
        self,
        *,
        dark_lux: float = DARK_LUX,
        bright_lux: float = BRIGHT_LUX,
        quiet_hours: tuple[int, int] | None = None,
        timezone: str = ProactivitySettings().timezone,
        away_after: timedelta = AWAY_AFTER,
        long_active_after: timedelta = LONG_ACTIVE_AFTER,
        global_gap: timedelta = GLOBAL_GAP,
        cooldowns: dict[str, timedelta] | None = None,
    ) -> None:
        self._dark = dark_lux
        self._bright = max(bright_lux, dark_lux)
        self._quiet_hours = quiet_hours
        self._zone = ZoneInfo(timezone)
        self._away_after = away_after
        self._long_after = long_active_after
        self._global_gap = global_gap
        self._cooldowns = cooldowns or COOLDOWNS
        self._quiet = False
        self._lux: float | None = None
        self._present = False
        self._present_since: datetime | None = None
        self._last_motion: datetime | None = None
        self._left_at: datetime | None = None
        self._last_any: datetime | None = None
        self._last_by: dict[str, datetime] = {}

    @property
    def quiet(self) -> bool:
        return self._quiet

    def facts(self, trigger: str, now: datetime) -> dict[str, object]:
        local = now.astimezone(self._zone)
        facts: dict[str, object] = {"trigger": trigger, "time": local.strftime("%H:%M")}
        if self._lux is not None:
            facts["lux"] = round(self._lux, 1)
        if self._left_at is not None and trigger == "arrival":
            facts["away_minutes"] = int((now - self._left_at).total_seconds() // 60)
        if self._present_since is not None and trigger in {"long_active", "departure"}:
            facts["present_minutes"] = int((now - self._present_since).total_seconds() // 60)
        return facts

    def handle(self, event: str, lux: float | None, now: datetime) -> list[str]:
        if event == "light_update" and lux is not None:
            self._lux = lux
            if not self._quiet and lux <= self._dark:
                effects = ["quiet_on"]
                # The room going dark is itself worth one decision; after it she stays quiet.
                if self._allow("dark", now):
                    effects.append("speak:dark")
                self._quiet = True
                return effects
            if self._quiet and lux >= self._bright:
                self._quiet = False
                return ["quiet_off"]
            return []
        if event == "motion_detected":
            first = not self._present
            self._last_motion = now
            if first:
                self._present, self._present_since = True, now
                if not self._quiet and self._allow("arrival", now):
                    return ["speak:arrival"]
            return []
        if event == "button_pressed":
            return [] if self._quiet else ["listen"]
        return []

    def tick(self, now: datetime) -> list[str]:
        if not self._present or self._last_motion is None or self._present_since is None:
            return []
        if now - self._last_motion >= self._away_after:
            self._present, self._left_at = False, self._last_motion
            if self._quiet:
                return []
            return ["speak:departure"] if self._allow("departure", now) else []
        if (
            now - self._present_since >= self._long_after
            and not self._quiet
            and self._allow("long_active", now)
        ):
            return ["speak:long_active"]
        return []

    def _allow(self, trigger: str, now: datetime) -> bool:
        if self._in_quiet_hours(now):
            return False
        last = self._last_by.get(trigger)
        if last is not None and now - last < self._cooldowns[trigger]:
            return False
        if self._last_any is not None and now - self._last_any < self._global_gap:
            return False
        self._last_by[trigger] = self._last_any = now
        return True

    def _in_quiet_hours(self, now: datetime) -> bool:
        if self._quiet_hours is None:
            return False
        local = now.astimezone(self._zone)
        minute = local.hour * 60 + local.minute
        start, end = self._quiet_hours
        return start <= minute < end if start < end else minute >= start or minute < end


def sensor_prompt(facts: dict[str, object]) -> str:
    """The ask for the model: what changed in the room, and permission to say nothing."""

    what = {
        "arrival": "主人剛走進房間（感測器偵測到有人）",
        "departure": "主人離開房間好一陣子了（感測器很久沒偵測到動靜）",
        "dark": "房間剛剛變暗了（可能主人關燈了）",
        "long_active": "主人已經在房間裡待了很長一段時間沒有離開",
        "late_awake": "主人比平常的就寢時間晚了很久還醒著（背景有平常作息）",
        "unexpected_absence": "平常這個時段主人都在家，現在卻很久沒偵測到人（背景有平常作息）",
        "node_offline": "房間裡的感測節點已經很久沒有回報了（可能斷電或斷線）",
        "node_back": "剛才斷線的感測節點又恢復回報了",
    }[str(facts["trigger"])]
    details = "，".join(f"{key}={value}" for key, value in facts.items() if key != "trigger")
    return (
        "你是希洛（SIRO），住在主人身邊的數位女兒，個性溫暖、有點俏皮。"
        f"現在發生的事：{what}。背景：{details}。"
        "請自己判斷現在要不要開口：如果不打擾比較好，只輸出 SILENT。"
        "要說的話，就用一句繁體中文口語，最多二十個字，只輸出那一句話本身，"
        "不要引號、表情符號、動作描寫、括號或解釋。"
    )


async def decide_sensor_line(
    ask: Callable[[str], Awaitable[str | None]], facts: dict[str, object], spoken: int
) -> str | None:
    """What she says for this trigger, or None to stay silent. A failed model falls back to the
    ready-made arrival greeting; other triggers are simply skipped."""

    fallback = FALLBACK_LINES.get(str(facts["trigger"]))
    fallback_line = fallback[spoken % len(fallback)] if fallback else None
    try:
        raw = await ask(sensor_prompt(facts))
    except Exception:
        return fallback_line
    if raw is None or not raw.strip():
        return fallback_line
    if _SILENT.match(raw.strip()):
        return None
    return clean_touch_line(raw) or fallback_line
