from __future__ import annotations

import argparse
import asyncio
import signal
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import current_thread, main_thread
from types import FrameType

import pytest

import siro.cli as cli


def _previous_handler(signum: int, frame: FrameType | None) -> None:
    raise AssertionError("the backup must finish its owned cleanup before propagating SIGINT")


@pytest.mark.parametrize("outcome", ["success", "cancelled", "primary_error", "late_success"])
def test_backup_restores_existing_handler_and_preserves_primary_result(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    original = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _previous_handler)
    problem = sqlite3.DatabaseError("synthetic backup failure")
    loops: list[asyncio.AbstractEventLoop] = []

    def loop_factory() -> asyncio.AbstractEventLoop:
        loop = asyncio.new_event_loop()
        loops.append(loop)
        return loop

    async def backup(arguments: argparse.Namespace) -> int:
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler) and handler is not _previous_handler
        if outcome == "cancelled":
            raise asyncio.CancelledError
        if outcome in {"primary_error", "late_success"}:
            handler(signal.SIGINT, None)
            try:
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                if outcome == "primary_error":
                    raise problem from None
        return 7

    monkeypatch.setattr(cli, "_backup_data", backup)
    arguments = argparse.Namespace(_data_loop_factory=loop_factory)
    try:
        if outcome == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                cli._backup(arguments)
        elif outcome == "primary_error":
            with pytest.raises(sqlite3.DatabaseError) as error:
                cli._backup(arguments)
            assert error.value is problem
        elif outcome == "late_success":
            with pytest.raises(KeyboardInterrupt):
                cli._backup(arguments)
        else:
            assert cli._backup(arguments) == 7
        assert signal.getsignal(signal.SIGINT) is _previous_handler
        assert len(loops) == 1 and loops[0].is_closed()
    finally:
        signal.signal(signal.SIGINT, original)


def test_repeated_backup_interrupts_wait_for_cleanup_before_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _previous_handler)
    cancellations: list[int] = []
    completed: list[str] = []

    async def backup(arguments: argparse.Namespace) -> int:
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler) and handler is not _previous_handler
        for number in range(3):
            handler(signal.SIGINT, None)
            try:
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                cancellations.append(number)
        await asyncio.sleep(0)
        completed.append("owned cleanup resolved")
        raise asyncio.CancelledError

    monkeypatch.setattr(cli, "_backup_data", backup)
    try:
        with pytest.raises(KeyboardInterrupt):
            cli._backup(argparse.Namespace())
        assert cancellations == [0, 1, 2]
        assert completed == ["owned cleanup resolved"]
        assert signal.getsignal(signal.SIGINT) is _previous_handler
    finally:
        signal.signal(signal.SIGINT, original)


def test_backup_off_main_thread_preserves_process_signal_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = signal.getsignal(signal.SIGINT)

    async def backup(arguments: argparse.Namespace) -> int:
        assert current_thread() is not main_thread()
        assert signal.getsignal(signal.SIGINT) is original
        return 9

    monkeypatch.setattr(cli, "_backup_data", backup)
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(cli._backup, argparse.Namespace()).result(timeout=3) == 9
    assert signal.getsignal(signal.SIGINT) is original
