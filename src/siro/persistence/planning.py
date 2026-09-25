"""Durable structured planning decisions and explanations."""

from __future__ import annotations

import json

from siro.core.cognition import PlanningDecision
from siro.persistence.sqlite import SQLiteStore


class SQLitePlanningRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def record(self, decision: PlanningDecision) -> None:
        candidates = [
            {
                "candidate_id": candidate.candidate_id,
                "capability": candidate.capability,
                "arguments": candidate.arguments,
                "expected_result": candidate.expected_result,
                "cost": candidate.cost,
                "deadline": candidate.deadline.isoformat() if candidate.deadline else None,
                "score": candidate.score,
                "reasons": candidate.reasons,
                "allowed": candidate.allowed,
            }
            for candidate in decision.candidates
        ]
        await self._store.run_transaction(
            lambda connection: connection.execute(
                "INSERT INTO planning_decisions(decision_id,trace_id,selected_candidate_id,"
                "candidates_json,rejected_json,reasons_json,decided_at) VALUES (?,?,?,?,?,?,?)",
                (
                    decision.decision_id,
                    decision.trace_id,
                    decision.selected_candidate_id,
                    json.dumps(candidates, separators=(",", ":")),
                    json.dumps(decision.rejected, separators=(",", ":")),
                    json.dumps(decision.reasons, separators=(",", ":")),
                    decision.decided_at.isoformat(),
                ),
            )
        )
