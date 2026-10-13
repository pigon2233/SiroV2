from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from siro.contracts.events import Privacy
from siro.core.nodes import NodeProfile, NodeRegistry
from siro.core.router import ComputeRouter
from siro.services.compute.worker import ComputeWorkerServer, run_job


@pytest.mark.asyncio
async def test_t36_t38_fake_dual_node_transport_faults_and_a23() -> None:
    now = datetime(2026, 9, 26, 18, tzinfo=UTC)
    registry = NodeRegistry()
    for node_id, location, key in (
        ("local-worker", "local", "local-key"),
        ("lan-worker", "lan", "lan-key-1"),
    ):
        registry.pair(
            NodeProfile(
                node_id=node_id,
                paired_key_id=key,
                privacy_ceiling=Privacy.TRUSTED_LAN,
                models=("echo",),
                location=location,  # type: ignore[arg-type]
            )
        )
        registry.heartbeat(node_id, key, now=now)
    router = ComputeRouter(
        registry,
        {("local-worker", "echo"): 2, ("lan-worker", "echo"): 1},
        {("local-worker", "echo"): 5, ("lan-worker", "echo"): 10},
    )
    assert (
        router.route("echo", privacy=Privacy.LOCAL_ONLY, budget_remaining=10, now=now).node_id
        == "local-worker"
    )
    assert (
        router.route("echo", privacy=Privacy.TRUSTED_LAN, budget_remaining=10, now=now).node_id
        == "lan-worker"
    )

    worker = ComputeWorkerServer(max_input_bytes=32)
    server = await asyncio.start_server(worker.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        result = await run_job("127.0.0.1", port, job_id="job-1", epoch=1, payload=b"hello world")
    assert result.chunks == ("hello", "world")
    assert not worker.artifacts

    broken = ComputeWorkerServer(fault="crash_after_chunk")
    crash_server = await asyncio.start_server(broken.handle, "127.0.0.1", 0)
    crash_port = crash_server.sockets[0].getsockname()[1]
    async with crash_server:
        with pytest.raises(ConnectionError):
            await run_job("127.0.0.1", crash_port, job_id="job-2", epoch=1, payload=b"crash me")
    assert not broken.artifacts
