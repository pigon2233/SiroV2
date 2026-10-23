"""CP-O01: can a directly spawned subprocess's outbound socket be attributed to its owner?"""

from __future__ import annotations

import socket
import subprocess
import sys
import time

import pytest

from siro.adapters.process_network import Connection, probe_capability, sample_group

pytestmark = pytest.mark.skipif(
    probe_capability().status != "sampled", reason="unsupported platform: reported, not faked"
)

_HOLD = (
    "import socket,sys,time;s=socket.create_connection(('127.0.0.1',int(sys.argv[1])));"
    "print('up',flush=True);time.sleep(float(sys.argv[2]))"
)
_BLINK = (
    "import socket,sys;s=socket.create_connection(('127.0.0.1',int(sys.argv[1])));s.close();"
    "print('done',flush=True)"
)


def _spawn(code: str, *args: object) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", code, *map(str, args)],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,  # same ownership rule as process_execution
    )


def _sample_until(pgid: int, want: bool, timeout: float = 5.0) -> list[Connection]:
    end = time.monotonic() + timeout
    while True:
        got = sample_group(pgid)
        if bool(got) == want or time.monotonic() > end:
            return got
        time.sleep(0.05)


@pytest.fixture
def server():
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        yield srv


def test_held_connection_is_attributed_to_the_spawned_group(server):
    port = server.getsockname()[1]
    child = _spawn(_HOLD, port, 3)
    try:
        assert child.stdout.readline().strip() == "up"
        got = _sample_until(child.pid, True)
        assert [(c.pid, c.remote, c.port, c.protocol) for c in got] == [
            (child.pid, "127.0.0.1", port, "tcp")
        ]
        # Attribution is by group: another group's sockets never leak in.
        assert sample_group(child.pid + 1_000_000) == []
    finally:
        child.kill()
        child.wait()


def test_short_lived_connection_between_samples_is_not_seen(server):
    # Documents the limit that keeps this "sampled", never a complete audit.
    child = _spawn(_BLINK, server.getsockname()[1])
    child.wait(timeout=5)
    assert sample_group(child.pid) == []
    assert server.accept()[0] is not None  # the connection really happened


def test_capability_is_unsupported_without_proc(tmp_path, monkeypatch):
    assert probe_capability(tmp_path).status == "unsupported"
    monkeypatch.setattr(sys, "platform", "win32")
    assert probe_capability().status == "unsupported"
