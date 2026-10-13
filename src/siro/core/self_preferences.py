"""Evidence-gated development of SIRO's own preferences."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelfPreferenceUpdate:
    subject: str
    polarity: float
    strength: float
    confidence: float
    status: str
    source_ids: tuple[str, ...]


def develop_self_preference(
    subject: str,
    valence: float,
    source_ids: tuple[str, ...],
    *,
    previous_strength: float = 0.5,
) -> SelfPreferenceUpdate:
    """Require repeated independent experiences and clamp each change."""
    sources = tuple(dict.fromkeys(source_ids))
    if not subject.strip() or not sources or not -1 <= valence <= 1:
        raise ValueError("self preference evidence is invalid")
    delta = max(-0.1, min(0.1, valence * 0.1))
    strength = max(0.0, min(1.0, previous_strength + delta))
    status = "committed" if len(sources) >= 3 else "candidate"
    confidence = min(1.0, len(sources) / 3)
    return SelfPreferenceUpdate(
        subject.strip(),
        1.0 if valence > 0 else -1.0 if valence < 0 else 0.0,
        strength,
        confidence,
        status,
        sources,
    )
