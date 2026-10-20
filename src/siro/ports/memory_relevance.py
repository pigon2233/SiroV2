"""Relevance selection is a fallible read-only hint, never a grant or fact."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RelevanceCandidate:
    source_key: str
    text: str = field(repr=False)
    source_event_types: tuple[str, ...] = ()


class MemoryRelevanceFilter(Protocol):
    async def select(
        self,
        query: str,
        candidates: tuple[RelevanceCandidate, ...],
    ) -> tuple[int, ...]:
        """Return indices only; caller must revalidate sources after this await."""
        ...
