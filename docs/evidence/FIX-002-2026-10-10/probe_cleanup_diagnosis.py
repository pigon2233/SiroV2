"""Two bounded public no-model browser loads: current versus trusted pre-card.

Subclass observers time the unchanged cleanup order and route callbacks. They do
not change production sources, close deadlines, navigation permissions, or data.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import signal
import sys
import time
from pathlib import Path
from types import ModuleType

from probe_browser_cleanup import PUBLIC_URL, descendants, process_stat, safe_error

from siro.adapters.browser import ScopedBrowserDriver
from siro.services.tools.browser_session import BrowserSessions
from siro.services.tools.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
FILES = (
    "src/siro/adapters/browser.py",
    "src/siro/services/tools/browser_session.py",
    "docs/evidence/FIX-002-2026-10-10/before/src/siro/adapters/browser.py",
    "docs/evidence/FIX-002-2026-10-10/before/src/siro/services/tools/browser_session.py",
)


def hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}


def load_snapshot(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def case(name: str, driver_base: type, sessions_type: type) -> dict[str, object]:
    start = time.monotonic()
    root_pid = os.getpid()
    ledger: dict[tuple[int, int], dict[str, object]] = {}
    snapshot_events: list[dict[str, object]] = []
    close_steps: list[dict[str, object]] = []
    route_finishes: list[dict[str, object]] = []
    pending_routes: dict[int, dict[str, object]] = {}
    route_sequence = 0
    result: dict[str, object] = {
        "case": name,
        "probe_pid": root_pid,
        "one_fresh_browser": True,
        "provider_calls": 0,
        "close_limit_seconds": 4,
        "navigate_limit_seconds": 30,
        "probe_limit_seconds": 60,
    }

    def capture(phase: str, *, record: bool = True) -> None:
        rows = descendants(root_pid)
        for row in rows:
            ledger[(int(str(row["pid"])), int(str(row["start_ticks"])))] = row
        if record:
            snapshot_events.append(
                {
                    "phase": phase,
                    "seconds": round(time.monotonic() - start, 3),
                    "descendants": rows,
                    "pending_route_callbacks": list(pending_routes.values()),
                }
            )

    async def monitor() -> None:
        while True:
            capture("monitor", record=False)
            await asyncio.sleep(0.1)

    class InstrumentedDriver(driver_base):
        async def __aenter__(self):
            value = await super().__aenter__()
            capture("browser_started")
            return value

        async def _route_request(self, route):
            nonlocal route_sequence
            route_sequence += 1
            number = route_sequence
            began = time.monotonic()
            pending_routes[number] = {
                "callback_id": number,
                "resource_type": route.request.resource_type,
                "navigation": route.request.is_navigation_request(),
                "started_seconds": round(began - start, 3),
            }
            row = pending_routes[number].copy()
            try:
                return await super()._route_request(route)
            except BaseException as failure:
                row["error"] = type(failure).__name__
                raise
            finally:
                row["elapsed_seconds"] = round(time.monotonic() - began, 3)
                route_finishes.append(row)
                pending_routes.pop(number, None)

        async def __aexit__(self, *_error: object) -> None:
            # Same two awaits, assignments, try/finally as current and before source.
            # Only record timing and safe ownership/callback observations around them.
            try:
                if self._browser is not None:
                    row: dict[str, object] = {
                        "step": "browser.close",
                        "started_seconds": round(time.monotonic() - start, 3),
                        "pending_at_start": list(pending_routes.values()),
                    }
                    began = time.monotonic()
                    try:
                        await self._browser.close()
                        row["completed"] = True
                        self._browser = None
                        self._page = None
                    except BaseException as failure:
                        row.update(safe_error(failure))
                        raise
                    finally:
                        row["elapsed_seconds"] = round(time.monotonic() - began, 3)
                        row["pending_at_end"] = list(pending_routes.values())
                        close_steps.append(row)
            finally:
                if self._playwright is not None:
                    row = {
                        "step": "playwright.stop",
                        "started_seconds": round(time.monotonic() - start, 3),
                        "pending_at_start": list(pending_routes.values()),
                    }
                    began = time.monotonic()
                    try:
                        await self._playwright.stop()
                        row["completed"] = True
                        self._playwright = None
                    except BaseException as failure:
                        row.update(safe_error(failure))
                        raise
                    finally:
                        row["elapsed_seconds"] = round(time.monotonic() - began, 3)
                        row["pending_at_end"] = list(pending_routes.values())
                        close_steps.append(row)

    sessions = sessions_type(InstrumentedDriver, timeout=30, capacity=1)
    watcher = asyncio.create_task(monitor())
    capture("before")
    try:
        async with asyncio.timeout(60):
            began = time.monotonic()
            try:
                observation = await sessions.execute(
                    "navigate+read",
                    {"url": PUBLIC_URL},
                    ExecutionContext(
                        f"synthetic-cleanup-{name}",
                        f"synthetic-cleanup-{name}",
                        name,
                        deadline=asyncio.get_running_loop().time() + 30,
                        authorized=True,
                    ),
                )
                result["navigate"] = {
                    "completed": True,
                    "title": observation.get("title"),
                    "text_characters": len(observation.get("text", "")),
                    "captcha_visible": "confirm this search was made by a human"
                    in observation.get("text", ""),
                    "load_status": observation.get("load_status"),
                    "reason": observation.get("reason"),
                }
            except BaseException as failure:
                result["navigate"] = safe_error(failure)
            result["navigate"]["seconds"] = round(time.monotonic() - began, 3)
            capture("before_close")
            began = time.monotonic()
            try:
                await sessions.close()
                result["close"] = {"completed": True}
            except BaseException as failure:
                result["close"] = safe_error(failure)
            result["close"]["seconds"] = round(time.monotonic() - began, 3)
            capture("after_close")
            live = []
            for pid, ticks in ledger:
                row = process_stat(pid)
                if row is not None and row["start_ticks"] == ticks and row["state"] != "Z":
                    live.append(row)
            result["own_live_after_close"] = live
            emergency = []
            if live:
                for row in live:
                    pid = int(str(row["pid"]))
                    current = process_stat(pid)
                    if current is not None and current["start_ticks"] == row["start_ticks"]:
                        try:
                            os.kill(pid, signal.SIGTERM)
                            emergency.append(
                                {"pid": pid, "start_ticks": row["start_ticks"], "signal": "SIGTERM"}
                            )
                        except ProcessLookupError:
                            pass
                await asyncio.sleep(1)
                for row in live:
                    pid = int(str(row["pid"]))
                    current = process_stat(pid)
                    if (
                        current is not None
                        and current["start_ticks"] == row["start_ticks"]
                        and current["state"] != "Z"
                    ):
                        try:
                            os.kill(pid, signal.SIGKILL)
                            emergency.append(
                                {"pid": pid, "start_ticks": row["start_ticks"], "signal": "SIGKILL"}
                            )
                        except ProcessLookupError:
                            pass
                await asyncio.sleep(0.1)
            result["emergency_owned_cleanup"] = emergency
    except BaseException as failure:
        result["overall"] = safe_error(failure)
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        capture("final")
    result.update(
        close_steps=close_steps,
        route_callbacks_completed=route_finishes,
        pending_callbacks_at_end=list(pending_routes.values()),
        phase_snapshots=snapshot_events,
        own_identity_ledger=list(ledger.values()),
        total_seconds=round(time.monotonic() - start, 3),
    )
    return result


async def main() -> bool:
    if "--run-public-diagnosis" not in sys.argv:
        raise SystemExit("Explicit --run-public-diagnosis required")
    before = hashes()
    old_driver = load_snapshot("fix002_browser_before", FILES[2])
    old_sessions = load_snapshot("fix002_browser_sessions_before", FILES[3])
    report = {
        "synthetic_public_only": True,
        "provider_calls": 0,
        "source_sha256_before": before,
        "previous_unrecorded_children": "UNKNOWN",
        "cases": [
            await case("current", ScopedBrowserDriver, BrowserSessions),
            await case("before", old_driver.ScopedBrowserDriver, old_sessions.BrowserSessions),
        ],
        "source_sha256_after": hashes(),
    }
    report["source_unchanged"] = report["source_sha256_after"] == before
    text = json.dumps(report, ensure_ascii=False, indent=2)
    (EVIDENCE / "public-browser-cleanup-diagnosis.json").write_text(text + "\n")
    print(text)
    return bool(report["source_unchanged"])


if __name__ == "__main__":
    raise SystemExit(not asyncio.run(main()))
