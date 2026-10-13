"""Resource admission and hysteresis for models and background work."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    memory_total_bytes: int
    memory_available_bytes: int
    active_model_slots: int

    @property
    def available_ratio(self) -> float:
        return self.memory_available_bytes / self.memory_total_bytes


class Admission(StrEnum):
    ALLOW = "allow"
    DENY_MEMORY = "deny_memory"
    DENY_SLOTS = "deny_slots"
    DENY_CLOUD_BUDGET = "deny_cloud_budget"


class ProcMemoryTelemetry:
    def snapshot(self, *, active_model_slots: int) -> ResourceSnapshot:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, value, *_ = line.replace(":", "").split()
            values[key] = int(value) * 1024
        return ResourceSnapshot(values["MemTotal"], values["MemAvailable"], active_model_slots)


class ComputeGovernor:
    def __init__(
        self, *, high_water: float = 0.15, low_water: float = 0.25, max_slots: int = 1
    ) -> None:
        if not 0 < high_water < low_water < 1:
            raise ValueError("water marks must satisfy 0 < high < low < 1")
        self._high = high_water
        self._low = low_water
        self._max_slots = max_slots
        self._background_paused = False

    @property
    def background_paused(self) -> bool:
        return self._background_paused

    def observe(self, snapshot: ResourceSnapshot) -> bool:
        if snapshot.available_ratio <= self._high:
            self._background_paused = True
        elif snapshot.available_ratio >= self._low:
            self._background_paused = False
        return self._background_paused

    def admit(self, snapshot: ResourceSnapshot, *, cloud: bool, cloud_budget: float) -> Admission:
        self.observe(snapshot)
        if cloud and cloud_budget <= 0:
            return Admission.DENY_CLOUD_BUDGET
        if snapshot.available_ratio <= self._high:
            return Admission.DENY_MEMORY
        if snapshot.active_model_slots >= self._max_slots:
            return Admission.DENY_SLOTS
        return Admission.ALLOW
