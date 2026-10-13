"""Bounded session ownership around the existing scoped browser driver."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

from siro.adapters.browser import (
    BrowserObservation,
    BrowserRole,
    BrowserTarget,
    ScopedBrowserDriver,
)
from siro.adapters.computer import ComputerActionError
from siro.services.tools.execution import (
    ExecutionCancelled,
    ExecutionCleanupError,
    ExecutionContext,
)


@dataclass
class _Session:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    driver: ScopedBrowserDriver | None = None
    origin: str = ""
    epoch: str = field(default_factory=lambda: uuid4().hex)
    touched: float = 0
    active: asyncio.Task[dict[str, str]] | None = None


class BrowserSessions:
    def __init__(
        self,
        factory: Callable[[tuple[str, ...]], ScopedBrowserDriver],
        *,
        ttl: float = 300,
        capacity: int = 8,
        timeout: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl <= 0 or capacity < 1 or timeout <= 0:
            raise ValueError("invalid browser session limits")
        self._factory, self._ttl, self._capacity = factory, ttl, capacity
        self._timeout, self._clock = timeout, clock
        self._sessions: dict[str, _Session] = {}
        self._reaper: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("browser sessions closed")
        if self._reaper is None:
            self._reaper = asyncio.create_task(self._reap())

    async def _reap(self) -> None:
        while True:
            await asyncio.sleep(min(self._ttl, 30))
            await self.expire()

    async def _drop(self, key: str, entry: _Session) -> None:
        # Keep ownership until bounded cleanup completes, despite repeated cancellation.
        async def cleanup() -> None:
            try:
                if entry.driver is not None:
                    async with asyncio.timeout(4):
                        await entry.driver.__aexit__()
                    entry.driver = None
            except Exception as error:
                # Retain failed cleanup ownership; never replace an uncertain driver.
                self._closed = True
                raise ExecutionCleanupError("browser session cleanup failed") from error
            if self._sessions.get(key) is entry:
                del self._sessions[key]

        task = asyncio.create_task(cleanup())
        interrupted = False
        while True:
            try:
                await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                interrupted = True
                if task.done():
                    task.result()
                    break
        if interrupted:
            raise asyncio.CancelledError

    async def expire(self) -> None:
        for key, entry in tuple(self._sessions.items()):
            if not entry.lock.locked() and self._clock() - entry.touched >= self._ttl:
                async with entry.lock:
                    if self._clock() - entry.touched >= self._ttl:
                        await self._drop(key, entry)

    async def close_session(self, session_id: str) -> None:
        entry = self._sessions.get(session_id)
        if entry is not None:
            if entry.active is not None and entry.active is not asyncio.current_task():
                entry.active.cancel()
            async with entry.lock:
                await self._drop(session_id, entry)

    async def clear(self) -> None:
        results = await asyncio.gather(
            *(self.close_session(k) for k in tuple(self._sessions)), return_exceptions=True
        )
        if any(isinstance(result, BaseException) for result in results):
            raise ExecutionCleanupError("browser pool cleanup failed")

    async def close(self) -> None:
        self._closed = True
        reaper, self._reaper = self._reaper, None
        if reaper is not None:
            reaper.cancel()
            await asyncio.gather(reaper, return_exceptions=True)
        await self.clear()

    async def execute(
        self, action: str, arguments: dict[str, object], context: ExecutionContext
    ) -> dict[str, str]:
        context.check()
        operation = asyncio.create_task(self._execute(action, arguments, context))
        cancelled = asyncio.create_task(context.cancellation.wait())

        async def stop() -> None:
            operation.cancel()
            outcome = (await asyncio.gather(operation, return_exceptions=True))[0]
            if isinstance(outcome, ExecutionCleanupError):
                raise outcome

        try:
            await asyncio.wait({operation, cancelled}, return_when=asyncio.FIRST_COMPLETED)
            if context.cancellation.cancelled:
                await stop()
                raise ExecutionCancelled("browser run cancelled")
            return operation.result()
        except asyncio.CancelledError:
            cleanup = asyncio.create_task(stop())
            while True:
                try:
                    await asyncio.shield(cleanup)
                    break
                except asyncio.CancelledError:
                    if cleanup.done():
                        cleanup.result()
                        break
            raise
        finally:
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions=True)

    async def _execute(
        self, action: str, arguments: dict[str, object], context: ExecutionContext
    ) -> dict[str, str]:
        context.check()
        if not context.authorized or not context.session_id:
            raise PermissionError("browser requires authorized session context")
        if self._closed:
            raise RuntimeError("browser sessions unavailable")
        await self.expire()
        key = context.session_id
        if action == "close":
            await self.close_session(key)
            context.check()
            return {"state": "closed"}
        entry = self._sessions.get(key)
        if entry is None:
            if action != "navigate+read":
                raise ComputerActionError("browser session missing; navigate first")
            if len(self._sessions) >= self._capacity:
                raise ComputerActionError("browser session capacity reached")
            entry = _Session(touched=self._clock())
            self._sessions[key] = entry
        async with entry.lock:
            context.check()
            if self._closed or self._sessions.get(key) is not entry:
                raise ComputerActionError("browser session expired; navigate again")
            entry.active = asyncio.current_task()
            try:
                timeout = self._timeout
                if context.deadline is not None:
                    timeout = min(
                        timeout, max(0, context.deadline - asyncio.get_running_loop().time())
                    )
                async with asyncio.timeout(timeout):
                    if action == "navigate+read":
                        url = str(arguments["url"])
                        parsed = urlsplit(url)
                        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                            raise ValueError("browser requires HTTP/HTTPS URL")
                        origin = f"{parsed.scheme}://{parsed.netloc}"
                        if entry.driver is not None and entry.origin != origin:
                            await entry.driver.__aexit__()
                            entry.driver = None
                            entry.epoch = uuid4().hex
                        if entry.driver is None:
                            entry.driver = self._factory((origin,))
                            entry.origin = origin
                            await entry.driver.__aenter__()
                        observation = await entry.driver.navigate(url)
                    elif entry.driver is None:
                        raise ComputerActionError("browser session missing; navigate first")
                    elif action == "read":
                        observation = await entry.driver.observe()
                    elif action in {"fill", "click"}:
                        version = str(arguments["screen_version"])
                        if not version.startswith(entry.epoch + ":"):
                            raise ComputerActionError("screen changed; observe the session again")
                        role = cast(BrowserRole, arguments["role"])
                        target = BrowserTarget(
                            role, str(arguments["name"]), version[len(entry.epoch) + 1 :]
                        )
                        observation = (
                            await entry.driver.fill(target, str(arguments["value"]))
                            if action == "fill"
                            else await entry.driver.click(target)
                        )
                    else:
                        raise ValueError("unsupported browser action")
                    context.check()
                    entry.touched = self._clock()
                    return self._observation(entry, observation)
            except BaseException:
                await self._drop(key, entry)
                raise
            finally:
                entry.active = None

    @staticmethod
    def _observation(entry: _Session, value: BrowserObservation) -> dict[str, str]:
        result = {
            "url": value.url,
            "title": value.title,
            "text": value.text[:4000],
            "screen_version": entry.epoch + ":" + value.screen_version,
        }
        if value.blocked_resources:
            result.update(load_status="partial", reason="subresource_denied")
        return result
