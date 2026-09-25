"""Deterministic, user-controlled proactive companionship rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from siro.config import ProactivitySettings


@dataclass(frozen=True, slots=True)
class ProactivityContext:
    now: datetime
    home_arrival: bool = False
    overdue_task: bool = False
    environment_change: bool = False
    busy: bool = False
    speaking: bool = False
    last_social_at: datetime | None = None
    social_count_today: int = 0


@dataclass(frozen=True, slots=True)
class ProactivityChoice:
    action: str
    reason: str

    @property
    def should_speak(self) -> bool:
        return self.action != "do_nothing"


class ProactivityRules:
    def __init__(self, settings: ProactivitySettings, *, cooldown: timedelta = timedelta(hours=2)):
        self._settings = settings
        self._cooldown = cooldown

    def choose(self, context: ProactivityContext) -> ProactivityChoice:
        if not self._settings.enabled:
            return ProactivityChoice("do_nothing", "disabled_by_user")
        if self._quiet(context.now):
            return ProactivityChoice("do_nothing", "quiet_hours")
        if context.busy:
            return ProactivityChoice("do_nothing", "user_busy")
        if context.speaking:
            return ProactivityChoice("do_nothing", "already_speaking")
        if context.social_count_today >= self._settings.daily_social_limit:
            return ProactivityChoice("do_nothing", "daily_limit")
        if (
            context.last_social_at is not None
            and context.now - context.last_social_at < self._cooldown
        ):
            return ProactivityChoice("do_nothing", "cooldown")
        if context.home_arrival:
            return ProactivityChoice("greet_home", "home_arrival")
        if context.overdue_task:
            return ProactivityChoice("mention_overdue_task", "overdue_task")
        if context.environment_change:
            return ProactivityChoice("mention_environment", "environment_change")
        return ProactivityChoice("do_nothing", "no_relevant_trigger")

    def _quiet(self, now: datetime) -> bool:
        local = now.astimezone(ZoneInfo(self._settings.timezone))
        current = local.hour * 60 + local.minute
        start_hour, start_minute = (int(value) for value in self._settings.quiet_start.split(":"))
        end_hour, end_minute = (int(value) for value in self._settings.quiet_end.split(":"))
        start = start_hour * 60 + start_minute
        end = end_hour * 60 + end_minute
        if start == end:
            return False
        if start < end:
            return start <= current < end
        return current >= start or current < end
