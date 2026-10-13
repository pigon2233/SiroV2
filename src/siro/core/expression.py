"""Context-sensitive presentation policy for internal affect."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from siro.core.affect import AffectResult


@dataclass(frozen=True, slots=True)
class ExpressionContext:
    owner_distress: bool = False
    task_critical: bool = False
    public_setting: bool = False


@dataclass(frozen=True, slots=True)
class ExpressionDecision:
    expression: str
    intensity: float
    inhibited: bool
    reason: str
    speech_rate: float = 1.0
    pitch: float = 0.0
    energy: float = 0.5


class ExpressionPolicy:
    _mapping: ClassVar[dict[str, str]] = {
        "joy": "happy",
        "hope": "happy",
        "pride": "happy",
        "gratitude": "happy",
        "interest": "surprised",
        "surprise": "surprised",
        "fear": "surprised",
        "sadness": "sad",
        "distress": "sad",
        "guilt": "sad",
        "anger": "angry",
        "neutral": "neutral",
    }

    def decide(self, result: AffectResult, context: ExpressionContext) -> ExpressionDecision:
        expression = self._mapping.get(result.state.emotion, "neutral")
        intensity = result.state.intensity
        reasons: list[str] = []
        if intensity < 0.18:
            return ExpressionDecision(
                "neutral", 0.2, True, "below expression threshold", 1.0, 0.0, 0.35
            )
        if context.owner_distress and expression == "angry":
            expression = "sad"
            intensity = min(intensity, 0.38)
            reasons.append("owner distress uses empathic concern")
        if context.owner_distress:
            intensity = min(intensity, 0.55)
            reasons.append("reduced intensity around owner distress")
        if context.task_critical:
            intensity = min(intensity, 0.35)
            reasons.append("task-critical context limits distraction")
        if context.public_setting:
            intensity = min(intensity, 0.45)
            reasons.append("public setting limits expression")
        speech_rate = max(0.78, min(1.18, 0.9 + 0.28 * result.state.arousal))
        pitch = max(-0.35, min(0.35, 0.28 * result.state.valence))
        energy = max(0.25, min(0.9, 0.3 + 0.6 * result.state.arousal))
        if context.owner_distress or context.task_critical:
            speech_rate = min(speech_rate, 0.98)
            energy = min(energy, 0.55)
        return ExpressionDecision(
            expression,
            max(0.0, min(1.0, intensity)),
            bool(reasons),
            "; ".join(reasons) if reasons else "direct bounded affect mapping",
            speech_rate,
            pitch,
            energy,
        )


def expression_context_from_text(text: str) -> ExpressionContext:
    normalized = text.casefold()
    owner_distress = any(
        phrase in normalized
        for phrase in ("我很生氣", "我生氣", "我很難過", "我難過", "我害怕", "我不舒服")
    )
    task_critical = any(word in normalized for word in ("緊急", "危險", "急救", "火災", "警報"))
    public_setting = any(word in normalized for word in ("公開場合", "會議中", "大家面前"))
    return ExpressionContext(owner_distress, task_critical, public_setting)
