"""Local embedding boundary; vectors carry no factual or authorization authority."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Protocol


class RetrievalUnavailable(RuntimeError):
    """Retrieval could not safely complete; callers must surface the failure."""


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    model: str
    digest: str
    dimensions: int = 1024
    format_version: str = "qwen3-retrieval-v1"

    def __post_init__(self) -> None:
        if (
            not self.model
            or len(self.digest) != 64
            or any(c not in "0123456789abcdef" for c in self.digest)
            or not 32 <= self.dimensions <= 1024
            or self.format_version != "qwen3-retrieval-v1"
        ):
            raise ValueError("invalid pinned embedding profile")

    @property
    def key(self) -> str:
        return hashlib.sha256(
            f"{self.model}|{self.digest}|{self.dimensions}|{self.format_version}".encode()
        ).hexdigest()


def normalized(values: list[float] | tuple[float, ...], dimensions: int) -> tuple[float, ...]:
    if len(values) != dimensions or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise RetrievalUnavailable("invalid embedding vector")
    norm = math.sqrt(sum(v * v for v in values))
    if not math.isfinite(norm) or norm <= 0:
        raise RetrievalUnavailable("invalid embedding norm")
    return tuple(v / norm for v in values)


class LocalEmbedder(Protocol):
    @property
    def profile(self) -> EmbeddingProfile: ...

    async def embed(self, texts: tuple[str, ...], *, query: bool) -> tuple[tuple[float, ...], ...]:
        """Bound local input, no truncation, cancellation propagates."""
        ...
