from datetime import UTC, datetime

from siro.contracts.events import Privacy
from siro.core.nodes import NodeProfile, NodeRegistry
from siro.core.router import ComputeRouter


def test_t38_hard_filters_precede_cost_selection() -> None:
    now = datetime(2026, 9, 26, 17, tzinfo=UTC)
    nodes = NodeRegistry()
    lan = NodeProfile(
        node_id="lan-node",
        paired_key_id="key-12345",
        privacy_ceiling=Privacy.TRUSTED_LAN,
        models=("m",),
        location="lan",
    )
    cloud = NodeProfile(
        node_id="cloud-node",
        paired_key_id="key-67890",
        privacy_ceiling=Privacy.CLOUD_ALLOWED,
        models=("m",),
        location="cloud",
    )
    nodes.pair(lan)
    nodes.pair(cloud)
    nodes.heartbeat("lan-node", "key-12345", now=now)
    nodes.heartbeat("cloud-node", "key-67890", now=now)
    router = ComputeRouter(nodes, {("lan-node", "m"): 2, ("cloud-node", "m"): 1})
    local_only = router.route("m", privacy=Privacy.LOCAL_ONLY, budget_remaining=10, now=now)
    assert local_only.reason == "no_compatible_node"
    assert "lan-node:privacy" in local_only.trace
    assert (
        router.route("m", privacy=Privacy.LOCAL_ONLY, budget_remaining=0, now=now).reason
        == "budget_exhausted"
    )
    assert (
        router.route("absent", privacy=Privacy.TRUSTED_LAN, budget_remaining=10, now=now).reason
        == "no_compatible_node"
    )
    assert (
        router.route("m", privacy=Privacy.CLOUD_ALLOWED, budget_remaining=0.5, now=now).reason
        == "budget_insufficient"
    )
