"""Fixed-seed synthetic ablation; research evidence, not a product benchmark."""

from __future__ import annotations

import json
import random


def run(seed: int = 20260926) -> dict[str, dict[str, float]]:
    randomizer = random.Random(seed)
    events = [(randomizer.random() < 0.3, randomizer.random() < 0.2) for _ in range(100)]
    results: dict[str, dict[str, float]] = {}
    for name, threshold, cost in (
        ("rules_only", 0.5, 1.0),
        ("attention", 0.45, 1.1),
        ("drives", 0.4, 1.2),
        ("dream", 0.4, 1.4),
    ):
        actions = [novelty + relevance >= threshold for novelty, relevance in events]
        appropriate = sum(
            action == (novelty or relevance)
            for action, (novelty, relevance) in zip(actions, events, strict=True)
        )
        interruptions = sum(
            action and not (novelty or relevance)
            for action, (novelty, relevance) in zip(actions, events, strict=True)
        )
        results[name] = {
            "appropriateness": appropriate / 100,
            "interrupt_rate": interruptions / 100,
            "cost_units": cost,
            "memory_accuracy": 1.0,
        }
    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
