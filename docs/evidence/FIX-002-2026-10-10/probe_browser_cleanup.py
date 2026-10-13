"""One real public BrowserSessions cleanup probe; no provider or private data.

Own descendants are proved by the probe parent chain plus /proc start ticks.
No command lines or environment values are read, stored, or printed.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

from siro.adapters.browser import ScopedBrowserDriver
from siro.services.tools.browser_session import BrowserSessions
from siro.services.tools.execution import ExecutionContext

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
PUBLIC_URL = "https://html.duckduckgo.com/html/?q=Python+asyncio+documentation"
SOURCE_FILES = ("src/siro/adapters/browser.py", "src/siro/services/tools/browser_session.py")


def hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def process_stat(pid: int) -> dict[str, object] | None:
    try:
        data = (Path("/proc") / str(pid) / "stat").read_text()
        fields = data[data.rfind(")") + 2 :].split()
        return {
            "pid": pid,
            "ppid": int(fields[1]),
            "start_ticks": int(fields[19]),
            "state": fields[0],
        }
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
        return None


def descendants(root_pid: int) -> list[dict[str, object]]:
    rows = {}
    for item in Path("/proc").iterdir():
        if item.name.isdecimal():
            row = process_stat(int(item.name))
            if row is not None:
                rows[int(item.name)] = row
    owned = {root_pid}
    while True:
        extra = {pid for pid, row in rows.items() if row["ppid"] in owned} - owned
        if not extra:
            break
        owned.update(extra)
    return [rows[pid] for pid in sorted(owned - {root_pid}) if pid in rows]


def safe_error(error: BaseException) -> dict[str, object]:
    chain = []
    current: BaseException | None = error
    while current is not None and len(chain) < 4:
        chain.append(type(current).__name__)
        current = current.__cause__
    return {"error": type(error).__name__, "cause_classes": chain}


async def main() -> bool:
    if "--run-public-cleanup" not in sys.argv:
        raise SystemExit("Explicit --run-public-cleanup required")
    start = time.monotonic()
    root_pid = os.getpid()
    ledger: dict[tuple[int, int], dict[str, object]] = {}
    phases: list[dict[str, object]] = []
    before = hashes()
    driver_exits: list[dict[str, object]] = []
    result: dict[str, object] = {
        "one_fresh_browser_only": True,
        "actual_chromium": True,
        "provider_calls": 0,
        "private_inputs": False,
        "target": PUBLIC_URL,
        "navigate_limit_seconds": 30,
        "production_close_limit_seconds": 4,
        "probe_limit_seconds": 60,
        "previous_probe_descendant_cleanup": "UNKNOWN — no PID/start-time proof was recorded",
        "probe_pid": root_pid,
        "probe_start_ticks": (process_stat(root_pid) or {}).get("start_ticks"),
        "source_sha256_before": before,
    }

    def capture(phase: str, *, record: bool = True) -> None:
        rows = descendants(root_pid)
        for row in rows:
            ledger[(int(str(row["pid"])), int(str(row["start_ticks"])))] = row
        if record:
            phases.append(
                {"phase": phase, "seconds": round(time.monotonic() - start, 3), "descendants": rows}
            )

    async def monitor() -> None:
        while True:
            capture("monitor", record=False)
            await asyncio.sleep(0.1)

    class TrackedDriver(ScopedBrowserDriver):
        async def __aenter__(self) -> ScopedBrowserDriver:
            value = await super().__aenter__()
            capture("browser_started")
            return value

        async def __aexit__(self, *error: object) -> None:
            began = time.monotonic()
            row: dict[str, object] = {}
            try:
                await super().__aexit__(*error)
                row["completed"] = True
            except BaseException as failure:
                row.update(safe_error(failure))
                raise
            finally:
                row["seconds"] = round(time.monotonic() - began, 3)
                driver_exits.append(row)

    sessions = BrowserSessions(TrackedDriver, timeout=30, capacity=1)
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
                        "synthetic-cleanup-fix002",
                        "synthetic-cleanup-fix002",
                        "synthetic-cleanup-fix002",
                        deadline=asyncio.get_running_loop().time() + 30,
                        authorized=True,
                    ),
                )
                result["navigate"] = {
                    "completed": True,
                    "title": observation.get("title"),
                    "url": observation.get("url"),
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
            capture("after_production_close")
            # Numeric identity must still match the recorded own-child birth before signalling.
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
    result["owned_identity_ledger"] = list(ledger.values())
    result["phase_snapshots"] = phases
    result["driver_exit_timings"] = driver_exits
    result["source_sha256_after"] = hashes()
    result["source_unchanged"] = before == result["source_sha256_after"]
    result["seconds"] = round(time.monotonic() - start, 3)
    result["cleanup_gate"] = bool(
        isinstance(result.get("close"), dict)
        and result["close"].get("completed")
        and not result.get("own_live_after_close")
        and not result.get("emergency_owned_cleanup")
        and result["source_unchanged"]
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    (EVIDENCE / "public-browser-cleanup.json").write_text(text + "\n")
    print(text)
    return bool(result["cleanup_gate"])


if __name__ == "__main__":
    raise SystemExit(not asyncio.run(main()))
