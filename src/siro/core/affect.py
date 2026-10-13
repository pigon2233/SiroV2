"""Explainable appraisal, emotion, mood, drive, and coping dynamics.

The language model may describe an event, but it does not choose SIRO's
emotion.  This module derives emotion from SIRO's persistent internal state
and an explicit appraisal of what the event means to her.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from math import exp

ALGORITHM_VERSION = "siro-affect-cpm-1"


def _unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _signed(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


class Agency(StrEnum):
    SELF = "self"
    OTHER = "other"
    CIRCUMSTANCE = "circumstance"


class CopingStrategy(StrEnum):
    NONE = "none"
    SAVOR = "savor"
    SEEK_INFORMATION = "seek_information"
    PROBLEM_SOLVE = "problem_solve"
    REPAIR = "repair"
    SEEK_SUPPORT = "seek_support"
    ACCEPT = "accept"
    PAUSE = "pause"


class OutcomeKind(StrEnum):
    GOAL_COMPLETED = "goal_completed"
    GOAL_FAILED = "goal_failed"
    ACTION_CONFIRMED = "action_confirmed"
    ACTION_MISMATCH = "action_mismatch"
    ACTION_DENIED = "action_denied"
    MEMORY_CORRECTED = "memory_corrected"


@dataclass(frozen=True, slots=True)
class SelfConcern:
    subject: str
    polarity: float
    strength: float
    confidence: float
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.subject or not self.source_ids:
            raise ValueError("self concern requires a subject and provenance")
        if not -1.0 <= self.polarity <= 1.0:
            raise ValueError("self concern polarity must be within [-1, 1]")
        if not 0.0 <= self.strength <= 1.0 or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("self concern strength and confidence must be within [0, 1]")


def concern_outcome_from_text(
    text: str, concerns: tuple[SelfConcern, ...]
) -> tuple[SelfConcern, float] | None:
    """Extract only explicit preference outcomes from user language."""
    normalized = "".join(text.casefold().split())
    positive = any(word in normalized for word in ("成功", "完成", "保留", "增加", "繼續"))
    negative = any(word in normalized for word in ("失敗", "停止", "取消", "失去", "破壞"))
    if positive == negative:
        return None
    matched = [
        concern for concern in concerns if "".join(concern.subject.casefold().split()) in normalized
    ]
    if not matched:
        return None
    concern = max(matched, key=lambda item: (item.strength * item.confidence, item.subject))
    return concern, 1.0 if positive else -1.0


@dataclass(frozen=True, slots=True)
class Temperament:
    curiosity: float = 0.70
    sensitivity: float = 0.60
    optimism: float = 0.55
    assertiveness: float = 0.45
    sociability: float = 0.70

    def __post_init__(self) -> None:
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{descriptor.name} must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class AffectParameters:
    activation_threshold: float = 0.08
    coping_threshold: float = 0.18
    mood_update_rate: float = 0.13
    episode_tau_hours: float = 1.5
    pleasure_tau_hours: float = 12.0
    arousal_tau_hours: float = 6.0
    dominance_tau_hours: float = 18.0
    connection_pressure_per_hour: float = 0.004
    competence_pressure_per_hour: float = 0.002
    curiosity_pressure_per_hour: float = 0.006
    autonomy_pressure_per_hour: float = 0.002
    rest_pressure_per_hour: float = 0.018

    def __post_init__(self) -> None:
        if not 0.0 < self.activation_threshold < self.coping_threshold <= 1.0:
            raise ValueError("affect thresholds must be ordered within (0, 1]")
        if not 0.0 < self.mood_update_rate <= 1.0:
            raise ValueError("mood update rate must be within (0, 1]")
        for name in (
            "episode_tau_hours",
            "pleasure_tau_hours",
            "arousal_tau_hours",
            "dominance_tau_hours",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "connection_pressure_per_hour",
            "competence_pressure_per_hour",
            "curiosity_pressure_per_hour",
            "autonomy_pressure_per_hour",
            "rest_pressure_per_hour",
        ):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class DriveState:
    safety: float = 0.20
    connection: float = 0.30
    competence: float = 0.30
    curiosity: float = 0.40
    autonomy: float = 0.30
    rest: float = 0.10

    def __post_init__(self) -> None:
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{descriptor.name} must be within [0, 1]")

    def changed(self, changes: dict[str, float]) -> DriveState:
        values = {
            descriptor.name: _unit(
                getattr(self, descriptor.name) + changes.get(descriptor.name, 0.0)
            )
            for descriptor in fields(self)
        }
        return DriveState(**values)


@dataclass(frozen=True, slots=True)
class MoodState:
    pleasure: float = 0.0
    arousal: float = 0.25
    dominance: float = 0.0

    def __post_init__(self) -> None:
        if not -1.0 <= self.pleasure <= 1.0 or not -1.0 <= self.dominance <= 1.0:
            raise ValueError("pleasure and dominance must be within [-1, 1]")
        if not 0.0 <= self.arousal <= 1.0:
            raise ValueError("arousal must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class Appraisal:
    """SIRO's interpretation of one event, independent of emotion labels."""

    event_id: str
    novelty: float = 0.0
    pleasantness: float = 0.0
    goal_relevance: float = 0.0
    goal_conduciveness: float = 0.0
    certainty: float = 0.5
    agency: Agency = Agency.CIRCUMSTANCE
    controllability: float = 0.5
    power: float = 0.5
    norm_compatibility: float = 0.0
    relationship_significance: float = 0.0
    urgency: float = 0.0
    drive_changes: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        unit_names = (
            "novelty",
            "goal_relevance",
            "certainty",
            "controllability",
            "power",
            "relationship_significance",
            "urgency",
        )
        signed_names = ("pleasantness", "goal_conduciveness", "norm_compatibility")
        if any(not 0 <= getattr(self, name) <= 1 for name in unit_names):
            raise ValueError("unit appraisal values must be within [0, 1]")
        if any(not -1 <= getattr(self, name) <= 1 for name in signed_names):
            raise ValueError("signed appraisal values must be within [-1, 1]")
        unknown = set(self.drive_changes) - {descriptor.name for descriptor in fields(DriveState)}
        if unknown:
            raise ValueError(f"unknown drives: {', '.join(sorted(unknown))}")


@dataclass(frozen=True, slots=True)
class EmotionActivation:
    emotion: str
    intensity: float
    reason: str


@dataclass(frozen=True, slots=True)
class CopingDecision:
    strategy: CopingStrategy
    urgency: float
    reason: str


@dataclass(frozen=True, slots=True)
class AffectState:
    emotion: str
    valence: float
    arousal: float
    intensity: float
    reason: str


@dataclass(frozen=True, slots=True)
class AffectResult:
    state: AffectState
    emotions: tuple[EmotionActivation, ...]
    mood: MoodState
    drives: DriveState
    coping: CopingDecision
    appraisal: Appraisal


class AffectSystem:
    """A deterministic appraisal model with persistent mood and needs."""

    def __init__(
        self,
        temperament: Temperament | None = None,
        parameters: AffectParameters | None = None,
    ) -> None:
        self.temperament = temperament or Temperament()
        self.parameters = parameters or AffectParameters()
        self._states: dict[str, AffectState] = {}
        self._moods: dict[str, MoodState] = {}
        self._drives: dict[str, DriveState] = {}

    def configuration(self) -> dict[str, object]:
        return {
            "version": ALGORITHM_VERSION,
            "temperament": asdict(self.temperament),
            "parameters": asdict(self.parameters),
        }

    def evaluate(self, session_id: str, appraisal: Appraisal) -> AffectResult:
        t = self.temperament
        drives = self._drives.get(session_id, DriveState())
        relevance = appraisal.goal_relevance * (0.65 + 0.35 * t.sensitivity)
        positive = relevance * max(0.0, appraisal.goal_conduciveness)
        negative = relevance * max(0.0, -appraisal.goal_conduciveness)
        uncertain = 1.0 - appraisal.certainty
        self_caused = float(appraisal.agency == Agency.SELF)
        other_caused = float(appraisal.agency == Agency.OTHER)
        norm_bad = max(0.0, -appraisal.norm_compatibility)

        raw = {
            "joy": positive * appraisal.certainty * (0.7 + 0.3 * t.optimism),
            "hope": positive * uncertain * (0.6 + 0.4 * t.optimism),
            "pride": positive * self_caused * appraisal.certainty,
            "gratitude": positive * other_caused * appraisal.relationship_significance,
            "distress": negative
            * appraisal.certainty
            * (0.6 + 0.4 * t.sensitivity)
            * (1.0 - 0.65 * appraisal.controllability),
            "fear": negative * uncertain * appraisal.urgency * (1.0 - appraisal.controllability),
            "anger": negative
            * other_caused
            * appraisal.controllability
            * (0.5 + 0.5 * t.assertiveness),
            "guilt": negative * self_caused * norm_bad * (0.6 + 0.4 * t.sensitivity),
            "sadness": negative
            * appraisal.certainty
            * (1.0 - appraisal.controllability)
            * (0.45 + 0.55 * appraisal.relationship_significance),
            "surprise": appraisal.novelty * uncertain,
            "interest": appraisal.novelty * drives.curiosity * (0.6 + 0.4 * t.curiosity),
        }
        reasons = {
            "joy": "a relevant outcome supports SIRO's goal",
            "hope": "a desired outcome remains uncertain",
            "pride": "SIRO caused a valued outcome",
            "gratitude": "another person supported a valued outcome",
            "distress": "a relevant outcome obstructs SIRO's goal",
            "fear": "an urgent threat is uncertain and difficult to control",
            "anger": "another agent caused a controllable obstruction",
            "guilt": "SIRO caused an outcome that conflicts with her norms",
            "sadness": "a meaningful loss appears certain and uncontrollable",
            "surprise": "the event was novel and unexpected",
            "interest": "the novel event engages SIRO's curiosity",
        }
        emotions = tuple(
            EmotionActivation(name, _unit(score), reasons[name])
            for name, score in sorted(raw.items(), key=lambda item: item[1], reverse=True)
            if score >= self.parameters.activation_threshold
        )
        dominant = (
            emotions[0]
            if emotions
            else EmotionActivation("neutral", 0.20, "no appraisal crossed the activation threshold")
        )
        positive_total = sum(
            raw[name] for name in ("joy", "hope", "pride", "gratitude", "interest")
        )
        negative_total = sum(
            raw[name] for name in ("distress", "fear", "anger", "guilt", "sadness")
        )
        valence = _signed(
            (positive_total - negative_total) / max(1.0, positive_total + negative_total)
        )
        arousal = _unit(0.18 + 0.55 * dominant.intensity + 0.27 * appraisal.urgency)
        state = AffectState(dominant.emotion, valence, arousal, dominant.intensity, dominant.reason)

        previous_mood = self._moods.get(session_id, MoodState())
        alpha = 1.0 - exp(-self.parameters.mood_update_rate)
        target_dominance = _signed(appraisal.power + appraisal.controllability - 1.0)
        mood = MoodState(
            _signed(previous_mood.pleasure * (1 - alpha) + valence * alpha),
            _unit(previous_mood.arousal * (1 - alpha) + arousal * alpha),
            _signed(previous_mood.dominance * (1 - alpha) + target_dominance * alpha),
        )
        drives = drives.changed(appraisal.drive_changes)
        coping = self._choose_coping(dominant, appraisal, self.parameters.coping_threshold)
        self._states[session_id] = state
        self._moods[session_id] = mood
        self._drives[session_id] = drives
        return AffectResult(state, emotions, mood, drives, coping, appraisal)

    def advance_time(self, session_id: str, elapsed_hours: float) -> None:
        """Apply continuous mood decay and homeostatic need accumulation."""
        if elapsed_hours < 0:
            raise ValueError("elapsed time cannot be negative")
        if elapsed_hours == 0:
            return
        hours = min(elapsed_hours, 24.0 * 30.0)
        mood = self._moods.get(session_id, MoodState())
        p = self.parameters
        pleasure_decay = exp(-hours / p.pleasure_tau_hours)
        arousal_decay = exp(-hours / p.arousal_tau_hours)
        dominance_decay = exp(-hours / p.dominance_tau_hours)
        self._moods[session_id] = MoodState(
            _signed(mood.pleasure * pleasure_decay),
            _unit(0.25 + (mood.arousal - 0.25) * arousal_decay),
            _signed(mood.dominance * dominance_decay),
        )
        drives = self._drives.get(session_id, DriveState())
        self._drives[session_id] = DriveState(
            safety=_unit(0.20 + (drives.safety - 0.20) * exp(-hours / 8.0)),
            connection=_unit(drives.connection + p.connection_pressure_per_hour * hours),
            competence=_unit(drives.competence + p.competence_pressure_per_hour * hours),
            curiosity=_unit(drives.curiosity + p.curiosity_pressure_per_hour * hours),
            autonomy=_unit(drives.autonomy + p.autonomy_pressure_per_hour * hours),
            rest=_unit(drives.rest + p.rest_pressure_per_hour * hours),
        )
        state = self._states.get(session_id)
        if state is not None:
            state_decay = exp(-hours / p.episode_tau_hours)
            intensity = state.intensity * state_decay
            self._states[session_id] = AffectState(
                "neutral" if intensity < 0.18 else state.emotion,
                state.valence * state_decay,
                _unit(0.20 + (state.arousal - 0.20) * state_decay),
                intensity,
                f"time decay after {hours:.2f} hours",
            )

    def regulate_drives(self, session_id: str, changes: dict[str, float]) -> DriveState:
        """Apply verified need satisfaction or depletion after an action."""
        current = self._drives.get(session_id, DriveState())
        updated = current.changed(changes)
        self._drives[session_id] = updated
        return updated

    def appraise_user_event(
        self,
        session_id: str,
        event_id: str,
        text: str,
        *,
        relationship_significance: float | None = None,
    ) -> AffectResult:
        """Translate observable language cues into appraisal dimensions.

        This boundary deliberately emits meanings rather than emotion labels.  It
        can later be replaced by a semantic classifier without changing the
        emotion dynamics or letting a generative model choose the answer.
        """
        normalized = text.casefold()
        praise = any(word in normalized for word in ("太棒", "謝謝", "喜歡你", "做得好", "成功"))
        owner_distress = any(
            phrase in normalized
            for phrase in ("我很生氣", "我生氣", "我很難過", "我難過", "我害怕", "我不舒服")
        )
        conflict = any(
            word in normalized for word in ("討厭你", "騙人", "亂做", "你讓我生氣", "對你生氣")
        )
        loss = any(word in normalized for word in ("難過", "傷心", "哭", "失去", "不開心"))
        unexpected = any(word in normalized for word in ("嚇到", "沒想到", "竟然", "驚訝"))
        self_fault = any(word in normalized for word in ("我做錯", "我的錯", "我害", "對不起"))
        salience = praise or conflict or loss or unexpected or self_fault
        negative = conflict or loss or self_fault or owner_distress
        return self.evaluate(
            session_id,
            Appraisal(
                event_id=event_id,
                novelty=0.9 if unexpected else (0.25 if salience else 0.08),
                pleasantness=0.75 if praise else (-0.75 if negative else 0.0),
                goal_relevance=0.9 if salience else 0.15,
                goal_conduciveness=0.8 if praise else (-0.8 if negative else 0.0),
                certainty=0.82 if not unexpected else 0.25,
                agency=(
                    Agency.SELF
                    if self_fault
                    else (Agency.OTHER if conflict else Agency.CIRCUMSTANCE)
                ),
                controllability=0.78 if conflict or self_fault else 0.2,
                power=0.6 if conflict else 0.45,
                norm_compatibility=-0.9 if self_fault else 0.0,
                relationship_significance=(
                    relationship_significance
                    if relationship_significance is not None
                    else (0.8 if any(word in normalized for word in ("你", "我")) else 0.35)
                ),
                urgency=0.75 if conflict or self_fault else (0.55 if loss or unexpected else 0.15),
                drive_changes={
                    "connection": -0.08 if conflict or loss else (-0.04 if praise else 0.0),
                    "competence": 0.08 if conflict or self_fault else (-0.04 if praise else 0.0),
                    "safety": 0.06 if conflict else 0.0,
                    "curiosity": -0.05 if unexpected else 0.0,
                },
            ),
        )

    def appraise_outcome(
        self,
        session_id: str,
        event_id: str,
        outcome: OutcomeKind,
        *,
        importance: float,
        relationship_significance: float = 0.0,
        controllability: float = 0.5,
    ) -> AffectResult:
        """Appraise verified goal, action, and memory outcomes."""
        if not 0.0 <= importance <= 1.0:
            raise ValueError("outcome importance must be within [0, 1]")
        if not 0.0 <= relationship_significance <= 1.0:
            raise ValueError("relationship significance must be within [0, 1]")
        if not 0.0 <= controllability <= 1.0:
            raise ValueError("outcome controllability must be within [0, 1]")
        positive = outcome in {OutcomeKind.GOAL_COMPLETED, OutcomeKind.ACTION_CONFIRMED}
        self_caused = outcome in {
            OutcomeKind.GOAL_COMPLETED,
            OutcomeKind.GOAL_FAILED,
            OutcomeKind.ACTION_CONFIRMED,
            OutcomeKind.ACTION_MISMATCH,
            OutcomeKind.MEMORY_CORRECTED,
        }
        mismatch = outcome in {
            OutcomeKind.GOAL_FAILED,
            OutcomeKind.ACTION_MISMATCH,
            OutcomeKind.ACTION_DENIED,
            OutcomeKind.MEMORY_CORRECTED,
        }
        norm_violation = outcome in {
            OutcomeKind.ACTION_MISMATCH,
            OutcomeKind.MEMORY_CORRECTED,
        }
        return self.evaluate(
            session_id,
            Appraisal(
                event_id=event_id,
                novelty=0.2,
                pleasantness=0.8 if positive else -0.7,
                goal_relevance=importance,
                goal_conduciveness=1.0 if positive else -1.0,
                certainty=1.0,
                agency=Agency.SELF if self_caused else Agency.CIRCUMSTANCE,
                controllability=controllability,
                power=controllability,
                norm_compatibility=-0.9 if norm_violation else 0.5,
                relationship_significance=relationship_significance,
                urgency=0.75 if mismatch else 0.2,
                drive_changes={
                    "competence": -0.12 if positive else 0.16,
                    "safety": 0.08 if outcome is OutcomeKind.ACTION_MISMATCH else 0.0,
                    "connection": 0.08 if norm_violation else 0.0,
                },
            ),
        )

    def appraise_concern_outcome(
        self,
        session_id: str,
        event_id: str,
        concern: SelfConcern,
        *,
        outcome_value: float,
        certainty: float,
        agency: Agency = Agency.CIRCUMSTANCE,
        controllability: float = 0.5,
        relationship_significance: float = 0.0,
    ) -> AffectResult:
        """Appraise an event against SIRO's own sourced preference."""
        if not -1.0 <= outcome_value <= 1.0:
            raise ValueError("concern outcome value must be within [-1, 1]")
        if not 0.0 <= certainty <= 1.0:
            raise ValueError("concern certainty must be within [0, 1]")
        congruence = _signed(concern.polarity * outcome_value)
        relevance = _unit(concern.strength * concern.confidence)
        return self.evaluate(
            session_id,
            Appraisal(
                event_id=event_id,
                novelty=0.15,
                pleasantness=congruence,
                goal_relevance=relevance,
                goal_conduciveness=congruence,
                certainty=certainty,
                agency=agency,
                controllability=controllability,
                power=controllability,
                norm_compatibility=0.5,
                relationship_significance=relationship_significance,
                urgency=relevance * max(0.0, -congruence),
                drive_changes={
                    "curiosity": -0.08 * max(0.0, congruence),
                    "competence": 0.10 * max(0.0, -congruence),
                },
            ),
        )

    @staticmethod
    def _choose_coping(
        emotion: EmotionActivation, appraisal: Appraisal, threshold: float
    ) -> CopingDecision:
        urgency = _unit(max(appraisal.urgency, emotion.intensity))
        if emotion.intensity < threshold:
            return CopingDecision(
                CopingStrategy.NONE, urgency, "activation is below the coping threshold"
            )
        if emotion.emotion in {"joy", "pride", "gratitude"}:
            return CopingDecision(
                CopingStrategy.SAVOR, urgency, "preserve and acknowledge the beneficial outcome"
            )
        if emotion.emotion == "guilt":
            return CopingDecision(
                CopingStrategy.REPAIR, urgency, "take responsibility and repair the norm violation"
            )
        if emotion.emotion in {"fear", "surprise"} and appraisal.certainty < 0.55:
            return CopingDecision(
                CopingStrategy.SEEK_INFORMATION, urgency, "reduce uncertainty before acting"
            )
        if emotion.emotion in {"anger", "distress"} and appraisal.controllability >= 0.5:
            return CopingDecision(
                CopingStrategy.PROBLEM_SOLVE, urgency, "the obstruction appears controllable"
            )
        if emotion.emotion == "sadness" and appraisal.relationship_significance >= 0.5:
            return CopingDecision(
                CopingStrategy.SEEK_SUPPORT, urgency, "the meaningful loss benefits from connection"
            )
        return CopingDecision(
            CopingStrategy.ACCEPT, urgency, "adjust to an outcome that cannot currently be changed"
        )

    def appraise(self, session_id: str, text: str) -> AffectState:
        """Compatibility adapter until upstream emits semantic event appraisals."""
        normalized = text.casefold()
        positive = any(word in normalized for word in ("太棒", "謝謝", "喜歡你", "做得好", "成功"))
        negative = any(
            word in normalized
            for word in ("生氣", "討厭你", "騙人", "亂做", "失敗", "難過", "傷心", "失去", "不開心")
        )
        novelty = any(word in normalized for word in ("嚇到", "沒想到", "竟然", "驚訝"))
        if not (positive or negative or novelty):
            previous = self._states.get(session_id)
            if previous is None:
                return self.state(session_id)
            decayed = AffectState(
                "neutral" if previous.intensity * 0.55 < 0.18 else previous.emotion,
                previous.valence * 0.55,
                max(0.18, previous.arousal * 0.55),
                previous.intensity * 0.55,
                "decay from previous event",
            )
            self._states[session_id] = decayed
            return decayed
        result = self.appraise_user_event(session_id, "text-adapter", text)
        legacy_name = {
            "joy": "happy",
            "hope": "happy",
            "pride": "happy",
            "gratitude": "happy",
            "distress": "sad",
            "sadness": "sad",
            "fear": "surprised",
            "surprise": "surprised",
            "anger": "angry",
        }.get(result.state.emotion, result.state.emotion)
        state = AffectState(
            legacy_name,
            result.state.valence,
            result.state.arousal,
            result.state.intensity,
            result.state.reason,
        )
        self._states[session_id] = state
        return state

    def restore(
        self,
        session_id: str,
        state: AffectState,
        mood: MoodState | None = None,
        drives: DriveState | None = None,
    ) -> None:
        self._states[session_id] = state
        if mood is not None:
            self._moods[session_id] = mood
        if drives is not None:
            self._drives[session_id] = drives

    def state(self, session_id: str) -> AffectState:
        return self._states.get(
            session_id, AffectState("neutral", 0.0, 0.25, 0.20, "initial state")
        )

    def mood(self, session_id: str) -> MoodState:
        return self._moods.get(session_id, MoodState())

    def drives(self, session_id: str) -> DriveState:
        return self._drives.get(session_id, DriveState())
