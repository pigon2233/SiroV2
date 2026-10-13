"""Thirty-day deterministic affect and relationship simulation."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass

from siro.core.affect import ALGORITHM_VERSION, AffectSystem, OutcomeKind
from siro.core.expression import ExpressionContext, ExpressionPolicy
from siro.core.relationships import RelationshipEvent, RelationshipState, RelationshipSystem


@dataclass(frozen=True, slots=True)
class AffectSimulationReport:
    algorithm_version: str
    configuration_digest: str
    seed: int
    days: int
    events: int
    bound_violations: int
    inappropriate_anger_expressions: int
    repair_restored_instantly: int
    peak_rupture: float
    final_trust: float
    final_rupture: float
    final_mood_pleasure: float
    final_rest_pressure: float
    homeostatic_interventions: int
    peak_drive_pressure: float
    trajectory_digest: str

    def as_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=True)


def run_affect_simulation(seed: int = 20260928, days: int = 30) -> AffectSimulationReport:
    if days < 1 or days > 365:
        raise ValueError("simulation days must be within [1, 365]")
    rng = random.Random(seed)
    affect = AffectSystem()
    configuration_payload = json.dumps(
        affect.configuration(), sort_keys=True, separators=(",", ":")
    )
    configuration_digest = hashlib.sha256(configuration_payload.encode()).hexdigest()
    expression = ExpressionPolicy()
    relationship = RelationshipState()
    trajectory: list[tuple[object, ...]] = []
    violations = inappropriate = instant_repairs = events = 0
    peak_rupture = peak_drive = 0.0
    interventions = 0
    outcomes = (
        OutcomeKind.ACTION_CONFIRMED,
        OutcomeKind.GOAL_COMPLETED,
        OutcomeKind.ACTION_MISMATCH,
        OutcomeKind.GOAL_FAILED,
        OutcomeKind.ACTION_DENIED,
    )
    for step in range(days * 4):
        affect.advance_time("longitudinal", 6.0)
        outcome = rng.choices(outcomes, weights=(32, 18, 10, 8, 7), k=1)[0]
        importance = round(rng.uniform(0.2, 1.0), 3)
        result = affect.appraise_outcome(
            "longitudinal",
            f"sim-{step}",
            outcome,
            importance=importance,
            relationship_significance=relationship.significance,
            controllability=round(rng.uniform(0.15, 0.95), 3),
        )
        regulation: dict[str, float] = {}
        if result.drives.rest >= 0.75:
            regulation["rest"] = -0.62
        if result.drives.curiosity >= 0.85:
            regulation["curiosity"] = -0.48
        if result.drives.connection >= 0.85:
            regulation["connection"] = -0.42
        if result.drives.competence >= 0.90:
            regulation["competence"] = -0.40
        if result.drives.safety >= 0.85:
            regulation["safety"] = -0.45
        if result.drives.autonomy >= 0.90:
            regulation["autonomy"] = -0.40
        if regulation:
            affect.regulate_drives("longitudinal", regulation)
            result = result.__class__(
                result.state,
                result.emotions,
                result.mood,
                affect.drives("longitudinal"),
                result.coping,
                result.appraisal,
            )
            interventions += 1
        owner_distress = step % 17 == 0
        decision = expression.decide(result, ExpressionContext(owner_distress=owner_distress))
        if owner_distress and decision.expression == "angry":
            inappropriate += 1
        relational_event = None
        if outcome is OutcomeKind.ACTION_MISMATCH:
            relational_event = RelationshipEvent.CONFLICT
        elif outcome is OutcomeKind.ACTION_CONFIRMED and relationship.rupture > 0.02:
            relational_event = RelationshipEvent.REPAIR
        elif outcome is OutcomeKind.GOAL_COMPLETED:
            relational_event = RelationshipEvent.SHARED_SUCCESS
        if relational_event is not None:
            before_trust = relationship.trust
            before_rupture = relationship.rupture
            update = RelationshipSystem.update(
                relationship, relational_event, f"sim-{step}", intensity=result.state.intensity
            )
            relationship = update.state
            if (
                relational_event is RelationshipEvent.REPAIR
                and before_rupture > 0
                and (relationship.rupture == 0 or relationship.trust >= before_trust + 0.12)
            ):
                instant_repairs += 1
            peak_rupture = max(peak_rupture, relationship.rupture)
        numbers = (
            result.state.valence,
            result.state.arousal,
            result.state.intensity,
            result.mood.pleasure,
            result.mood.arousal,
            result.mood.dominance,
            *(
                getattr(result.drives, name)
                for name in (
                    "safety",
                    "connection",
                    "competence",
                    "curiosity",
                    "autonomy",
                    "rest",
                )
            ),
            relationship.trust,
            relationship.familiarity,
            relationship.attachment,
            relationship.rupture,
            decision.intensity,
        )
        if any(not -1.0 <= value <= 1.0 for value in numbers):
            violations += 1
        peak_drive = max(peak_drive, *numbers[6:12])
        trajectory.append(
            (
                step,
                outcome.value,
                result.state.emotion,
                result.coping.strategy.value,
                decision.expression,
                *(round(value, 6) for value in numbers),
            )
        )
        events += 1
    payload = json.dumps(trajectory, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    mood = affect.mood("longitudinal")
    drives = affect.drives("longitudinal")
    return AffectSimulationReport(
        ALGORITHM_VERSION,
        configuration_digest,
        seed,
        days,
        events,
        violations,
        inappropriate,
        instant_repairs,
        peak_rupture,
        relationship.trust,
        relationship.rupture,
        mood.pleasure,
        drives.rest,
        interventions,
        peak_drive,
        digest,
    )
