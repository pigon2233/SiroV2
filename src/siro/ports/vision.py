"""Ports and evidence-bearing observations for on-demand screen analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class VisualObservation:
    description: str
    source: str
    confidence: float
    width: int
    height: int


class VisionModel(Protocol):
    async def analyze(self, image_png: bytes) -> VisualObservation: ...
