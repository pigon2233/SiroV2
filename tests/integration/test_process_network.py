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


@pytest.mark.asyncio
async def test_bounded_execution_reports_sampled_connection(server, tmp_path):
    from siro.adapters.process_execution import execute_bounded_argv
    from siro.services.activity.monitor import describe_tool

    port = server.getsockname()[1]
    code = _HOLD.replace("print('up',flush=True);", "") + ";"
    result = await execute_bounded_argv(
        (sys.executable, "-c", code, str(port), "1"),
        cwd=tmp_path,
        environment={},
        timeout=10,
        sample_network=True,
    )
    sample = result["network_sample"]
    assert sample["status"] == "sampled"
    assert {"protocol": "tcp", "remote": "127.0.0.1", "port": port} in sample["connections"]
    network = describe_tool("computer.execute", {"argv": ["x"]}, result)["network"]
    assert network["coverage"] == "process_sampled"
    assert network["requests"][0]["kind"] == "connection"
    assert "short_connections_may_be_missed" in network["gaps"]
    # Off by default: the model-facing result keeps its old shape.
    plain = await execute_bounded_argv(
        (sys.executable, "-c", "pass"), cwd=tmp_path, environment={}, timeout=10
    )
    assert "network_sample" not in plain
