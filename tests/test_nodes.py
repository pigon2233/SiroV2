from datetime import UTC, datetime, timedelta

import pytest

from siro.contracts.events import Privacy
from siro.core.nodes import NodeHeartbeat, NodeProfile, NodeRegistry, NodeStatus


def test_t36_paired_trust_heartbeat_privacy_and_revocation() -> None:
    now = datetime(2026, 9, 26, 15, tzinfo=UTC)
    registry = NodeRegistry()
    node = NodeProfile(
        node_id="lan-worker",
        paired_key_id="key-12345",
        privacy_ceiling=Privacy.TRUSTED_LAN,
        models=("small",),
    )
    registry.pair(node)
    with pytest.raises(PermissionError):
        registry.heartbeat("unknown", "key-12345", now=now)
    registry.heartbeat("lan-worker", "key-12345", now=now)
    assert registry.status("lan-worker", now=now) is NodeStatus.ONLINE
    assert registry.routeable(privacy=Privacy.LOCAL_ONLY, now=now) == (node,)
    assert registry.routeable(privacy=Privacy.CLOUD_ALLOWED, now=now) == ()
    assert registry.status("lan-worker", now=now + timedelta(seconds=30)) is NodeStatus.OFFLINE
    registry.heartbeat("lan-worker", "key-12345", now=now)
    registry.revoke("lan-worker")
    assert registry.status("lan-worker", now=now) is NodeStatus.REVOKED
    with pytest.raises(PermissionError):
        registry.heartbeat("lan-worker", "key-12345", now=now)


def test_t36_persistent_config_and_resource_advertisement(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "nodes.json"
    registry = NodeRegistry()
    registry.pair(
        NodeProfile(
            node_id="worker-one",
            paired_key_id="key-12345",
            privacy_ceiling=Privacy.TRUSTED_LAN,
            models=("small",),
            location="lan",
            hardware="synthetic-cpu",
        )
    )
    registry.save(path)
    restored = NodeRegistry.load(path)
    heartbeat = NodeHeartbeat(version="1.0", available_memory_bytes=1024, queue_depth=2)
    restored.heartbeat("worker-one", "key-12345", now=datetime.now(UTC), advertisement=heartbeat)
    assert restored.heartbeat_details("worker-one") == heartbeat
