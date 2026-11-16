"""Process-wide rolling budget and rate-limit cooldown for the Claude CLI.

Every guarded caller in this process shares one ``ClaudeBudget`` per data-directory
file (``claude-budget.json``). The file is the counter, so a restart does not reset
it. A path-keyed lock makes reserves thread-safe and safe across tasks on the event
loop: the critical section does not await. Computer-use call sites are not wired
here; see ``docs/patches/claude-budget-computer-use.patch``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

_LOG = logging.getLogger(__name__)
WINDOW = timedelta(hours=5)
DEFAULT_BUDGET = 10
DEFAULT_COOLDOWN_SECONDS = 900
DEFAULT_TIMEOUT_SECONDS = 120
_CALLER_MAX = 64
BudgetReason = Literal["ok", "budget", "rate_limit", "unreadable", "disabled"]

_shared_guard = threading.Lock()
_path_guards = threading.Lock()
_path_locks: dict[str, threading.Lock] = {}


def bounded_int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def cooldown_seconds(env: Mapping[str, str] | None = None) -> int:
    values = os.environ if env is None else env
    return bounded_int(
        values,
        "SIRO_CLAUDE_RATE_LIMIT_COOLDOWN_SECONDS",
        DEFAULT_COOLDOWN_SECONDS,
        0,
        5 * 60 * 60,
    )


def claude_timeout_seconds(env: Mapping[str, str] | None = None) -> int:
    """``SIRO_CLAUDE_TIMEOUT_SECONDS`` (default 120, allowed 10-240)."""
    values = os.environ if env is None else env
    return bounded_int(values, "SIRO_CLAUDE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, 10, 240)


def _caller_label(caller: str | None) -> str:
    if caller is None or not caller.strip():
        return "unlabeled"
    cleaned = "".join(ch if ch.isalnum() or ch in "._:-" else "_" for ch in caller.strip())
    return (cleaned or "unlabeled")[:_CALLER_MAX]


def _thread_lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _path_guards:
        lock = _path_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _path_locks[key] = lock
        return lock


@dataclass(frozen=True, slots=True)
class BudgetView:
    allowed: bool
    remaining: int
    limit: int
    available_at: datetime | None
    reason: BudgetReason


def block_message(view: BudgetView) -> str:
    """Short English result callers already treat as 'Claude did not answer'."""
    if view.reason == "budget":
        when = ""
        if view.available_at is not None:
            when = f" until {view.available_at.astimezone(UTC).isoformat()}"
        return f"claude unavailable: rolling 5h budget exhausted (limit {view.limit}){when}"
    if view.reason == "rate_limit":
        when = ""
        if view.available_at is not None:
            when = f" until {view.available_at.astimezone(UTC).isoformat()}"
        return f"claude unavailable: rate limit cooldown{when}"
    if view.reason == "unreadable":
        return "claude unavailable: budget record unreadable"
    if view.reason == "disabled":
        return "claude unavailable: budget is 0"
    return "claude unavailable"


class ClaudeBudget:
    """Rolling 5-hour Claude call count, persisted so a restart does not reset it."""

    def __init__(
        self,
        path: Path,
        *,
        limit: int = DEFAULT_BUDGET,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not 0 <= limit <= 200:
            raise ValueError("Claude budget must be between 0 and 200 calls")
        self._path = path
        self._limit = limit
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def limit(self) -> int:
        return self._limit

    def set_limit(self, limit: int) -> None:
        if not 0 <= limit <= 200:
            raise ValueError("Claude budget must be between 0 and 200 calls")
        self._limit = limit

    def now(self) -> datetime:
        return self._clock()

    def peek(self) -> BudgetView:
        with _exclusive(self._path):
            return self._view(self._clock())

    async def snapshot(self) -> BudgetView:
        return self.peek()

    async def try_reserve(self, caller: str | None = None) -> BudgetView:
        """Count one Claude attempt. A refused view does not consume a slot."""
        return self._try_reserve(caller)

    def _try_reserve(self, caller: str | None) -> BudgetView:
        with _exclusive(self._path):
            view = self._view(self._clock())
            if not view.allowed:
                return view
            now = self._clock()
            calls, labels, rate_until, _problem = self._load(now)
            label = _caller_label(caller)
            self._write([*calls, now], [*labels, label], rate_until)
            updated = self._view(now)
            _LOG.info(
                "claude budget reserved caller=%s remaining=%s limit=%s",
                label,
                updated.remaining,
                self._limit,
            )
            # The slot just taken still counts as allowed for this caller, even when it
            # was the last one in the window.
            return BudgetView(True, updated.remaining, self._limit, None, "ok")

    async def note_rate_limit(self, until: datetime) -> None:
        with _exclusive(self._path):
            now = self._clock()
            calls, labels, current, problem = self._load(now)
            if problem == "unreadable":
                return
            later = until if current is None or until > current else current
            self._write(calls, labels, later)
            _LOG.info("claude rate limit cooldown until %s", later.astimezone(UTC).isoformat())

    def _view(self, now: datetime) -> BudgetView:
        calls, _labels, rate_until, problem = self._load(now)
        if problem == "unreadable":
            return BudgetView(False, 0, self._limit, None, "unreadable")
        if self._limit == 0:
            return BudgetView(False, 0, 0, None, "disabled")
        remaining = self._limit - len(calls)
        blockers: list[tuple[BudgetReason, datetime]] = []
        if remaining <= 0 and calls:
            blockers.append(("budget", min(calls) + WINDOW))
        if rate_until is not None and rate_until > now:
            blockers.append(("rate_limit", rate_until))
        if not blockers:
            return BudgetView(True, remaining, self._limit, None, "ok")
        reason, when = max(blockers, key=lambda item: item[1])
        return BudgetView(False, max(0, remaining), self._limit, when, reason)

    def _load(self, now: datetime) -> tuple[list[datetime], list[str], datetime | None, str]:
        if not self._path.is_file():
            return [], [], None, ""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return [], [], None, "unreadable"
        if not isinstance(raw, dict):
            return [], [], None, "unreadable"
        stored = raw.get("calls")
        if not isinstance(stored, list):
            return [], [], None, "unreadable"
        calls: list[datetime] = []
        for item in stored:
            if not isinstance(item, str):
                return [], [], None, "unreadable"
            try:
                parsed = datetime.fromisoformat(item)
            except ValueError:
                return [], [], None, "unreadable"
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            calls.append(parsed.astimezone(UTC))
        labels = _labels(raw.get("callers"), len(calls))
        rate_raw = raw.get("rate_limited_until")
        rate_until: datetime | None = None
        if rate_raw is not None:
            if not isinstance(rate_raw, str):
                return [], [], None, "unreadable"
            try:
                rate_until = datetime.fromisoformat(rate_raw)
            except ValueError:
                return [], [], None, "unreadable"
            if rate_until.tzinfo is None:
                rate_until = rate_until.replace(tzinfo=UTC)
            rate_until = rate_until.astimezone(UTC)
        active_calls: list[datetime] = []
        active_labels: list[str] = []
        for call, label in zip(calls, labels, strict=True):
            if now < call + WINDOW:
                active_calls.append(call)
                active_labels.append(label)
        return active_calls, active_labels, rate_until, ""

    def _write(self, calls: list[datetime], labels: list[str], rate_until: datetime | None) -> None:
        payload = {
            "version": 1,
            "calls": [call.astimezone(UTC).isoformat() for call in calls],
            "callers": labels,
            "rate_limited_until": None
            if rate_until is None
            else rate_until.astimezone(UTC).isoformat(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, self._path)


def _labels(stored: object, count: int) -> list[str]:
    """Optional per-call labels. A missing or mismatched list does not make the file unreadable."""
    if (
        not isinstance(stored, list)
        or len(stored) != count
        or not all(isinstance(item, str) for item in stored)
    ):
        return [""] * count
    return [item[:_CALLER_MAX] for item in stored]


@contextmanager
def _exclusive(path: Path) -> Iterator[None]:
    """One lock per budget file, shared by every instance and every thread in this process."""
    lock = _thread_lock_for(path)
    with lock:
        yield


_shared: dict[str, ClaudeBudget] = {}


def shared_claude_budget(
    env: Mapping[str, str] | None = None,
    *,
    data_dir: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ClaudeBudget:
    """The one budget object for this data directory. Later calls reuse it.

    ``clock`` is kept from the first construction. Tests that need a fresh clock call
    ``reset_shared_claude_budget`` first. The limit is refreshed from the environment
    on every lookup so ``SIRO_CLAUDE_BUDGET_CALLS`` stays the source of the cap.
    """
    values = os.environ if env is None else env
    root = data_dir if data_dir is not None else Path(values.get("SIRO_DATA_DIR", ".siro-data"))
    path = (root / "claude-budget.json").resolve()
    limit = bounded_int(values, "SIRO_CLAUDE_BUDGET_CALLS", DEFAULT_BUDGET, 0, 200)
    key = str(path)
    with _shared_guard:
        existing = _shared.get(key)
        if existing is None:
            existing = ClaudeBudget(path, limit=limit, clock=clock)
            _shared[key] = existing
            return existing
        existing.set_limit(limit)
        return existing


def reset_shared_claude_budget() -> None:
    """Drop the process cache. The JSON file is left in place. Tests use this."""
    with _shared_guard:
        _shared.clear()


async def reserve_claude_call(
    caller: str,
    *,
    env: Mapping[str, str] | None = None,
    data_dir: Path | None = None,
) -> BudgetView:
    """Reserve one Claude CLI attempt on the shared budget, or return a refusal."""
    return await shared_claude_budget(env, data_dir=data_dir).try_reserve(caller)


async def note_shared_rate_limit(
    retry_at: datetime | None = None,
    *,
    env: Mapping[str, str] | None = None,
    budget: ClaudeBudget | None = None,
    now: datetime | None = None,
) -> datetime:
    """Start or extend the shared cooldown. Uses the CLI reset time when it is still ahead."""
    target = budget if budget is not None else shared_claude_budget(env)
    moment = now if now is not None else target.now()
    until = (
        retry_at
        if retry_at is not None and retry_at > moment
        else moment + timedelta(seconds=cooldown_seconds(env))
    )
    await target.note_rate_limit(until)
    return until


def cli_rate_limited(
    result: Mapping[str, object], *, now: datetime
) -> tuple[bool, datetime | None]:
    """Whether a CLI result is a provider rate limit, and the parsed reset time if any."""
    from siro.adapters.models.claude_cli import (
        ClaudeCliError,
        ClaudeRateLimited,
        interpret_cli_result,
    )

    try:
        interpret_cli_result(result, now=now)
    except ClaudeRateLimited as error:
        return True, error.retry_at
    except ClaudeCliError:
        return False, None
    return False, None


async def observe_cli_rate_limit(
    result: Mapping[str, object],
    *,
    env: Mapping[str, str] | None = None,
    budget: ClaudeBudget | None = None,
    now: datetime | None = None,
) -> bool:
    """If ``result`` is a rate limit, start the shared cooldown and return True."""
    target = budget if budget is not None else shared_claude_budget(env)
    moment = now if now is not None else target.now()
    limited, retry_at = cli_rate_limited(result, now=moment)
    if not limited:
        return False
    await note_shared_rate_limit(retry_at, env=env, budget=target, now=moment)
    return True
