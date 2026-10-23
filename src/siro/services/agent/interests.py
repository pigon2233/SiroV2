"""SIRO picks her own next topic, and a scheduler decides when she may look into it.

Interests come from what she already has: recent conversation topics, her own committed
preferences and the open questions left in her earlier notes. The local model chooses one
topic or chooses to wait; nothing here invents a source or retries a failed topic at once.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, LanguageModel, ModelRequest, Privacy
from siro.services.agent.self_activity import SELF_SESSION, SelfActivityOwner

LOGGER = logging.getLogger(__name__)
SOURCES = frozenset({"conversation", "self_preference", "open_question"})
MAX_TOPIC = 80
MAX_WHY = 120
PICK_SECONDS = 60.0
PICK_PROMPT = (
    "你是 SIRO。下面是你最近的生活線索。想想有沒有一件你自己真的想多了解的事，"  # noqa: RUF001
    "可以上網讀資料。如果沒有特別想查的，也可以選擇等待。"  # noqa: RUF001
    "不要重複最近查過的題目。只回一行 JSON："  # noqa: RUF001
    '{"topic": "想查的題目或 null", "why": "一句話說為什麼想查", "source": "conversation"}'
    "。source 只能填一個：conversation（來自聊天）、self_preference（來自你的喜好）、"  # noqa: RUF001
    "open_question（來自筆記的待查）。"  # noqa: RUF001
)


@dataclass(frozen=True, slots=True)
class TopicChoice:
    topic: str
    why: str
    source: str


@dataclass(frozen=True, slots=True)
class InterestClues:
    conversation: tuple[str, ...]
    preferences: tuple[str, ...]
    open_questions: tuple[str, ...]
    recent_topics: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not (self.conversation or self.preferences or self.open_questions)


class InterestPicker:
    def __init__(
        self,
        store: SQLiteStore,
        model: LanguageModel,
        preferences: Callable[[], Awaitable[tuple[str, ...]]],
    ) -> None:
        self._store = store
        self._model = model
        self._preferences = preferences

    async def clues(self, now: datetime) -> InterestClues:
        since = (now - timedelta(days=3)).isoformat()

        def read(c: sqlite3.Connection) -> tuple[list[str], list[tuple[str, object]]]:
            talk = [
                str(row[0])[:200]
                for row in c.execute(
                    "SELECT goal FROM agent_runs WHERE session_id != ? AND created_at >= ? "
                    "ORDER BY created_at DESC LIMIT 12",
                    (SELF_SESSION, since),
                )
            ]
            own = [
                (str(row[0]), row[1])
                for row in c.execute(
                    "SELECT r.goal, s.payload_json FROM agent_runs r LEFT JOIN agent_steps s "
                    "ON s.run_id=r.run_id AND s.kind='final' WHERE r.session_id=? "
                    "ORDER BY r.created_at DESC LIMIT 10",
                    (SELF_SESSION,),
                )
            ]
            return talk, own

        talk, own = await self._store.run_transaction(read)
        questions: list[str] = []
        for _, payload in own:
            text = json.loads(payload).get("text", "") if isinstance(payload, str) else ""
            questions += [line.strip()[:120] for line in str(text).splitlines() if "待查" in line]
        return InterestClues(
            tuple(talk),
            await self._preferences(),
            tuple(questions[:8]),
            tuple(goal for goal, _ in own),
        )

    async def choose(self, now: datetime) -> TopicChoice | None:
        clues = await self.clues(now)
        if clues.empty:
            return None
        sections = {
            "最近和主人聊過的話題": clues.conversation,
            "你自己的喜好": clues.preferences,
            "你筆記裡還沒查清楚的": clues.open_questions,
            "最近查過的題目（不要重複）": clues.recent_topics,  # noqa: RUF001
        }
        prompt = (
            PICK_PROMPT
            + "\n"
            + "\n".join(
                f"{title}：{'；'.join(items) or '（沒有）'}"  # noqa: RUF001
                for title, items in sections.items()
            )
        )
        cancellation = CancellationToken()
        parts: list[str] = []

        async def collect() -> None:
            request = ModelRequest(
                prompt, str(uuid4()), privacy=Privacy.LOCAL_ONLY, max_output_tokens=300
            )
            async for chunk in self._model.stream(request, cancellation):
                if chunk.kind == "text":
                    parts.append(chunk.text)

        try:
            await asyncio.wait_for(collect(), PICK_SECONDS)
        except Exception:  # a slow or failing model means she waits this time
            cancellation.cancel()
            return None
        return parse_choice("".join(parts), clues.recent_topics)


def parse_choice(text: str, recent: tuple[str, ...]) -> TopicChoice | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    topic, why, source = data.get("topic"), data.get("why"), data.get("source")
    if isinstance(source, str) and source not in SOURCES:
        named = [part.strip() for part in source.split("|") if part.strip() in SOURCES]
        source = named[0] if named else source
    if not isinstance(topic, str) or not isinstance(why, str) or source not in SOURCES:
        return None
    topic, why = " ".join(topic.split()), " ".join(why.split())
    if not 2 <= len(topic) <= MAX_TOPIC or not why or topic in recent:
        return None
    return TopicChoice(topic, why[:MAX_WHY], str(source))


class SelfActivityScheduler:
    """Starts at most one of her own runs per tick, only when the owner is away."""

    def __init__(
        self,
        owner: SelfActivityOwner,
        picker: InterestPicker,
        store: SQLiteStore,
        *,
        foreground: Callable[[], bool],
        quiet: Callable[[], bool] = lambda: False,
        share: Callable[[], Awaitable[None]] | None = None,
        interval: float = 600.0,
        owner_quiet: timedelta = timedelta(minutes=10),
        cooldown: timedelta = timedelta(minutes=45),
        daily_limit: int = 6,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._owner = owner
        self._picker = picker
        self._store = store
        self._foreground = foreground
        self._quiet = quiet
        self._share = share
        self._interval = interval
        self._owner_quiet = owner_quiet
        self._cooldown = cooldown
        self._daily_limit = daily_limit
        self._clock = clock
        self._task: asyncio.Task[None] | None = None

    async def tick(self) -> str | None:
        """One decision: the started run id, or None when she waits."""
        decision, run_id = await self._decide()
        LOGGER.info("self activity tick: %s", decision)
        return run_id

    async def _decide(self) -> tuple[str, str | None]:
        # Focus or fullscreen: she keeps to herself, like an owner who should not be disturbed.
        if self._owner.paused or self._owner.busy or self._foreground() or self._quiet():
            return "busy_paused_or_quiet", None
        if self._share is not None:
            # She tells the owner about one finished note per tick, in the chat only (no voice).
            with suppress(Exception):
                await self._share()
        now = self._clock()

        def read(c: sqlite3.Connection) -> tuple[str | None, str | None, int]:
            owner = c.execute(
                "SELECT MAX(updated_at) FROM agent_runs WHERE session_id != ?", (SELF_SESSION,)
            ).fetchone()[0]
            own = c.execute(
                "SELECT MAX(created_at) FROM agent_runs WHERE session_id = ?", (SELF_SESSION,)
            ).fetchone()[0]
            count = c.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE session_id = ? AND created_at >= ?",
                (SELF_SESSION, (now - timedelta(days=1)).isoformat()),
            ).fetchone()[0]
            return owner, own, int(count)

        last_owner, last_own, count = await self._store.run_transaction(read)
        if last_owner is not None and now - datetime.fromisoformat(last_owner) < self._owner_quiet:
            return "owner_recent", None
        # A failed run also counts: the same moment is never retried in a loop.
        if last_own is not None and now - datetime.fromisoformat(last_own) < self._cooldown:
            return "cooldown", None
        if count >= self._daily_limit:
            return "daily_limit", None
        choice = await self._picker.choose(now)
        if choice is None:
            return "no_topic", None
        if self._foreground():
            return "busy_or_paused", None
        run_id = await self._owner.start(choice.topic, choice.why, choice.source)
        return ("started" if run_id else "start_refused"), run_id

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="siro-self-scheduler")

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.tick()
            except Exception:  # one bad tick must not end her own time for good
                LOGGER.exception("self activity tick failed")
