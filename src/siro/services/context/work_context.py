"""What SIRO may know about the owner's present situation, and only inside a scope.

Three sources, enabled separately and all off by default: what the owner told her
(always allowed, it is their own words), app metadata (app name and coarse category,
never the window title) and a selected screen look. Every observation carries its
source, time, expiry, privacy and the permission revision it was taken under; turning
a source off or bumping the revision makes older observations unusable at once.
What is seen is kept apart from what is guessed, and an unknown stays unknown.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from siro.ports.models import Privacy
from siro.ports.vision import VisionModel

SOURCES = ("user_shared", "app_metadata", "screen")
GATED = ("app_metadata", "screen")
MAX_KEPT = 32
MAX_TEXT = 200
APP_TTL = timedelta(minutes=2)
SCREEN_TTL = timedelta(minutes=1)
SHARED_TTL = timedelta(hours=4)
MAX_SHARED_TTL = timedelta(hours=12)
EDITORS = ("code", "vscode", "visual studio", "pycharm", "idea", "vim", "nvim", "sublime", "cursor")
TERMINALS = ("terminal", "powershell", "cmd.exe", "wsl", "bash", "konsole", "iterm")
BROWSERS = ("chrome", "firefox", "edge", "safari", "brave")
MEDIA = ("vlc", "spotify", "netflix", "youtube", "mpv")
SENSITIVE = (
    "password",
    "密碼",
    "bank",
    "銀行",
    "1password",
    "bitwarden",
    "keepass",
    "incognito",
    "private browsing",
    "無痕",
    "登入",
    "sign in",
    "otp",
    "wallet",
)


@dataclass(frozen=True, slots=True)
class AppSnapshot:
    """What an adapter reports about the foreground app; the title is only inspected."""

    app_name: str
    window_title: str = ""
    locked: bool = False
    fullscreen: bool = False
    focus_mode: bool = False


@dataclass(frozen=True, slots=True)
class ContextObservation:
    observation_id: str
    source: str
    kind: str  # stated (owner said) | seen (measured) | inferred (a guess)
    subject: str
    detail: str
    confidence: float
    observed_at: datetime
    expires_at: datetime
    privacy: str
    permission_revision: int
    quiet: bool = False

    def public(self) -> dict[str, object]:
        return {
            "id": self.observation_id,
            "source": self.source,
            "kind": self.kind,
            "subject": self.subject,
            "detail": self.detail,
            "confidence": self.confidence,
            "observed_at": self.observed_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "privacy": self.privacy,
            "permission_revision": self.permission_revision,
        }


@dataclass(frozen=True, slots=True)
class Situation:
    status: str  # unknown | known
    quiet: bool
    hint: str | None
    question: str | None
    observations: tuple[ContextObservation, ...]


def classify(app_name: str) -> str:
    name = app_name.lower()
    for category, words in (
        ("editor", EDITORS),
        ("terminal", TERMINALS),
        ("browser", BROWSERS),
        ("media", MEDIA),
    ):
        if any(word in name for word in words):
            return category
    return "other"


def is_sensitive(snapshot: AppSnapshot) -> bool:
    text = f"{snapshot.app_name} {snapshot.window_title}".lower()
    return any(word in text for word in SENSITIVE)


class ScopeStore:
    """The owner's switches. A restart keeps them; a missing or damaged file means all off."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self.enabled = {"app_metadata": False, "screen": False}
        self.revision = 1
        self._load()

    def _load(self) -> None:
        if self._path is None:
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for source in GATED:
                self.enabled[source] = data.get(source) is True
            revision = data.get("revision")
            if isinstance(revision, int) and not isinstance(revision, bool) and revision >= 1:
                self.revision = revision
        except (OSError, ValueError, AttributeError):
            self.enabled = {"app_metadata": False, "screen": False}

    def _save(self) -> None:
        if self._path is None:
            return
        temporary = self._path.with_suffix(".tmp")
        with suppress(OSError):
            temporary.write_text(
                json.dumps({**self.enabled, "revision": self.revision}), encoding="utf-8"
            )
            os.replace(temporary, self._path)

    def update(self, changes: dict[str, bool]) -> list[str]:
        """Apply switches; any real change bumps the revision. Returns the sources turned off."""
        turned_off = [s for s, on in changes.items() if s in GATED and self.enabled[s] and not on]
        changed = any(s in GATED and self.enabled[s] != on for s, on in changes.items())
        for source, on in changes.items():
            if source in GATED:
                self.enabled[source] = on
        if changed:
            self.revision += 1
            self._save()
        return turned_off


class WorkContext:
    def __init__(
        self,
        scope: ScopeStore,
        *,
        clock: Callable[[], datetime],
        vision: VisionModel | None = None,
    ) -> None:
        self._scope = scope
        self._clock = clock
        self._vision = vision
        self._kept: list[ContextObservation] = []
        self._retracted: set[str] = set()
        self._corrected: dict[str, datetime] = {}  # subject the owner said was wrong -> until

    @property
    def scope(self) -> ScopeStore:
        return self._scope

    def source_enabled(self, source: str) -> bool:
        return source == "user_shared" or self._scope.enabled.get(source, False)

    def _keep(self, observation: ContextObservation) -> ContextObservation:
        # One live observation per source: a newer one replaces the older.
        self._kept = [o for o in self._kept if o.source != observation.source or o.kind == "stated"]
        self._kept.append(observation)
        del self._kept[:-MAX_KEPT]
        return observation

    def share(self, text: str, ttl: timedelta | None = None) -> ContextObservation:
        """The owner's own statement of what they are doing; it needs no extra permission."""
        text = " ".join(text.split())[:MAX_TEXT]
        if not text:
            raise ValueError("shared context is empty")
        now = self._clock()
        life = min(ttl or SHARED_TTL, MAX_SHARED_TTL)
        if life <= timedelta(0):
            raise ValueError("shared context must last a while")
        return self._keep(
            ContextObservation(
                uuid4().hex, "user_shared", "stated", "task", text, 1.0, now, now + life,
                Privacy.LOCAL_ONLY.value, self._scope.revision,
            )
        )  # fmt: skip

    def ingest_app(self, snapshot: AppSnapshot) -> ContextObservation | None:
        """Take one app report; refused (None) when off, locked or sensitive. Nothing is stored."""
        if not self.source_enabled("app_metadata"):
            return None
        if snapshot.locked or is_sensitive(snapshot):
            # Whatever was known a moment ago is no longer true of this window.
            self._drop_source("app_metadata")
            return None
        category = classify(snapshot.app_name)
        now = self._clock()
        quiet = snapshot.focus_mode or snapshot.fullscreen
        return self._keep(
            ContextObservation(
                uuid4().hex, "app_metadata", "seen", category, snapshot.app_name[:64], 1.0, now,
                now + APP_TTL, Privacy.LOCAL_ONLY.value, self._scope.revision, quiet,
            )
        )  # fmt: skip

    async def observe_screen(self, capture: Callable[[], Awaitable[bytes | None]]) -> bool:
        """One selected-screen look. It reports only what the analyzer measured."""
        if not self.source_enabled("screen") or self._vision is None:
            return False
        revision = self._scope.revision
        image = await capture()
        # The owner may have switched it off while the picture was being taken.
        if image is None or not self.source_enabled("screen") or revision != self._scope.revision:
            return False
        seen = await self._vision.analyze(image)
        if not self.source_enabled("screen") or revision != self._scope.revision:
            return False
        now = self._clock()
        self._keep(
            ContextObservation(
                uuid4().hex, "screen", "seen", "screen", seen.description[:MAX_TEXT],
                seen.confidence, now, now + SCREEN_TTL, Privacy.LOCAL_ONLY.value, revision,
            )
        )  # fmt: skip
        return True

    def update_scope(self, changes: dict[str, bool]) -> None:
        for source in self._scope.update(changes):
            self._drop_source(source)

    def _drop_source(self, source: str) -> None:
        self._kept = [o for o in self._kept if o.source != source]

    def retract(self, observation_id: str) -> bool:
        """The source of this observation is gone or was wrong: it is no longer used."""
        before = len(self._kept)
        self._kept = [o for o in self._kept if o.observation_id != observation_id]
        self._retracted.add(observation_id)
        return len(self._kept) != before

    def correct(self, observation_id: str) -> bool:
        """The owner says a guess was wrong; that subject is not guessed again for a while."""
        wrong = next((o for o in self._kept if o.observation_id == observation_id), None)
        if wrong is None:
            return False
        self._corrected[wrong.subject] = self._clock() + SHARED_TTL
        self.retract(observation_id)
        return True

    def usable(self) -> tuple[ContextObservation, ...]:
        now = self._clock()
        self._kept = [
            o
            for o in self._kept
            if now < o.expires_at
            and o.observation_id not in self._retracted
            and (o.source == "user_shared" or self.source_enabled(o.source))
            and (o.source == "user_shared" or o.permission_revision == self._scope.revision)
        ]
        return tuple(self._kept)

    def situation(self) -> Situation:
        live = self.usable()
        if not live:
            return Situation("unknown", False, None, None, ())
        now = self._clock()
        quiet = any(o.quiet for o in live)
        hint: str | None = None
        question: str | None = None
        stated = next((o for o in reversed(live) if o.kind == "stated"), None)
        app = next((o for o in live if o.source == "app_metadata"), None)
        if stated is not None:
            hint = f"主人說：{stated.detail}"  # noqa: RUF001
        elif app is not None and app.subject in {"editor", "terminal"}:
            if self._corrected.get(app.subject, now) > now:
                hint = None  # the owner said this guess was wrong
            else:
                hint = "看到的是編輯器；推測可能在寫程式（只是推測）"  # noqa: RUF001
                question = "你是在寫程式嗎？"  # noqa: RUF001
        elif app is not None:
            hint = f"看到的是 {app.subject} 類的應用程式（沒有更多資訊）"  # noqa: RUF001
        return Situation("known", quiet, hint, question, live)

    def may_interrupt(self) -> bool:
        """Focus, fullscreen and unknown-but-locked moments are left alone."""
        return not self.situation().quiet

    def prompt_lines(self, privacy: Privacy) -> tuple[str, ...]:
        """Context for a model request; screen and app context never go to a cloud model."""
        if privacy is not Privacy.LOCAL_ONLY:
            return ()
        return tuple(
            f"[{o.kind}:{o.source}] {o.subject}：{o.detail}"  # noqa: RUF001
            for o in self.usable()
        )

    def status(self) -> dict[str, object]:
        situation = self.situation()
        return {
            "scope": {**self._scope.enabled, "revision": self._scope.revision},
            "status": situation.status,
            "quiet": situation.quiet,
            "hint": situation.hint,
            "question": situation.question,
            "observations": [o.public() for o in situation.observations],
        }


class ScreenObserver:
    """Polls the selected screen only while the owner keeps that switch on."""

    def __init__(
        self,
        context: WorkContext,
        capture: Callable[[], Awaitable[bytes | None]],
        *,
        interval: float = 30.0,
    ) -> None:
        self._context = context
        self._capture = capture
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="siro-screen-observer")

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            if self._context.source_enabled("screen"):
                with suppress(Exception):  # one failed capture is simply no observation
                    await self._context.observe_screen(self._capture)
