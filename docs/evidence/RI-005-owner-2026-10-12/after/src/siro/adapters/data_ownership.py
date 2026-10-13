"""Local Linux coordination for managed data operations and their blocking IO."""

from __future__ import annotations

import asyncio
import hashlib
import os
import stat
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path


class DataOwnerBusyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SIRO data is already in use")


class DataOwnerUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SIRO data ownership is unavailable")


def _owner_directory() -> Path:
    import pwd

    return Path(pwd.getpwuid(os.geteuid()).pw_dir) / ".local/state/siro/data-owners"


class _DataOwner:
    def __init__(self, descriptors: list[int]) -> None:
        self._descriptors = descriptors
        self._executors: list[ThreadPoolExecutor] = []
        self._closed = False

    def loop_factory(self) -> asyncio.AbstractEventLoop:
        if self._closed:
            raise DataOwnerUnavailableError
        loop = asyncio.new_event_loop()
        executor = ThreadPoolExecutor(thread_name_prefix="siro-owned-data")
        try:
            loop.set_default_executor(executor)
        except BaseException:
            executor.shutdown(wait=True)
            loop.close()
            raise
        self._executors.append(executor)
        asyncio.set_event_loop(loop)
        return loop

    def _finish(self) -> bool:
        if self._closed:
            return False
        interrupted = False
        if self._executors:
            done = threading.Event()
            failures: list[BaseException] = []

            def join_io() -> None:
                try:
                    for executor in self._executors:
                        executor.shutdown(wait=True, cancel_futures=True)
                except BaseException as error:
                    failures.append(error)
                finally:
                    done.set()

            worker = threading.Thread(target=join_io, name="siro-data-io-join")
            worker.start()
            while not done.is_set():
                try:
                    done.wait()
                except KeyboardInterrupt:
                    interrupted = True
            while True:
                try:
                    worker.join()
                    break
                except KeyboardInterrupt:
                    interrupted = True
            if failures:
                # Unknown IO completion keeps the fd held until this process exits.
                raise DataOwnerUnavailableError from failures[0]
            asyncio.set_event_loop(None)
        close_failures: list[OSError] = []
        for descriptor in self._descriptors:
            try:
                os.close(descriptor)
            except OSError as error:
                close_failures.append(error)
        if close_failures:
            raise DataOwnerUnavailableError from close_failures[0]
        self._closed = True
        return interrupted


@contextmanager
def exclusive_data_owner(
    database: Path,
    *,
    write_target: Path | None = None,
    temporary_write_target: Path | None = None,
) -> Iterator[_DataOwner]:
    """Hold one operation's stable advisory keys until all its blocking IO joins."""
    if sys.platform != "linux":
        raise DataOwnerUnavailableError
    import fcntl

    try:
        requested = [database]
        if write_target is not None:
            requested.append(write_target)
        if temporary_write_target is not None:
            requested.append(temporary_write_target)
        canonical_paths = sorted({path.resolve() for path in requested}, key=os.fsencode)
        directory = _owner_directory()
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise DataOwnerUnavailableError
    except (OSError, KeyError) as error:
        raise DataOwnerUnavailableError from error
    descriptors: list[int] = []
    owner = _DataOwner(descriptors)
    try:
        for canonical in canonical_paths:
            try:
                info = canonical.stat()
            except FileNotFoundError:
                pass
            else:
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise DataOwnerUnavailableError
            key = hashlib.sha256(os.fsencode(canonical)).hexdigest() + ".lock"
            lock = directory / key
            descriptor = os.open(
                lock, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
            )
            descriptors.append(descriptor)
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise DataOwnerUnavailableError
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise DataOwnerBusyError from error
            current = lock.lstat()
            if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                raise DataOwnerUnavailableError
    except BaseException as error:
        try:
            owner._finish()
        except BaseException as cleanup_error:
            error.add_note(f"data owner cleanup failed: {type(cleanup_error).__name__}")
        if isinstance(error, OSError):
            raise DataOwnerUnavailableError from error
        raise
    try:
        yield owner
    except BaseException as error:
        try:
            owner._finish()
        except BaseException as cleanup_error:
            error.add_note(f"data owner cleanup failed: {type(cleanup_error).__name__}")
        raise
    else:
        if owner._finish():
            raise KeyboardInterrupt
