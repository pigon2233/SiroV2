"""Hard-gated compute routing over paired node profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from siro.contracts.events import Privacy
from siro.core.nodes import NodeRegistry


@dataclass(frozen=True, slots=True)
class RouteDecision:
    node_id: str | None
    reason: str
    estimated_cost: float | None
    estimated_latency_ms: float | None = None
    trace: tuple[str, ...] = ()


class ComputeRouter:
    def __init__(
        self,
        registry: NodeRegistry,
        costs: dict[tuple[str, str], float],
        latencies_ms: dict[tuple[str, str], float] | None = None,
    ) -> None:
        self._registry = registry
        self._costs = costs.copy()
        self._latencies = (latencies_ms or {}).copy()

    def calibrate(self, node_id: str, model: str, *, latency_ms: float) -> None:
        key = (node_id, model)
        previous = self._latencies.get(key, latency_ms)
        self._latencies[key] = previous * 0.8 + latency_ms * 0.2

    def route(
        self, model: str, *, privacy: Privacy, budget_remaining: float, now: datetime
    ) -> RouteDecision:
        if budget_remaining <= 0:
            return RouteDecision(None, "budget_exhausted", None, trace=("budget:rejected",))
        trace: list[str] = []
        candidates = []
        for node in self._registry.routeable(privacy=privacy, now=now):
            if privacy is Privacy.LOCAL_ONLY and node.location != "local":
                trace.append(f"{node.node_id}:privacy")
            elif model not in node.models:
                trace.append(f"{node.node_id}:model")
            elif (node.node_id, model) not in self._costs:
                trace.append(f"{node.node_id}:uncalibrated")
            else:
                candidates.append(node)
        if not candidates:
            return RouteDecision(None, "no_compatible_node", None, trace=tuple(trace))
        selected = min(
            candidates,
            key=lambda node: (
                self._costs[(node.node_id, model)]
                + self._latencies.get((node.node_id, model), 1000) / 1000
            ),
        )
        cost = self._costs[(selected.node_id, model)]
        if cost > budget_remaining:
            return RouteDecision(
                None, "budget_insufficient", None, trace=tuple((*trace, "cost:rejected"))
            )
        latency = self._latencies.get((selected.node_id, model))
        return RouteDecision(
            selected.node_id,
            "selected",
            cost,
            latency,
            tuple((*trace, f"{selected.node_id}:selected")),
        )
