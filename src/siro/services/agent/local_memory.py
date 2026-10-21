"""Explicit local retrieval composition; no automatic writes or model installation."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from siro.adapters.models.ollama_embeddings import OllamaEmbedder
from siro.adapters.models.ollama_memory_relevance import OllamaMemoryRelevance
from siro.core.memory import MemoryService
from siro.core.memory_retrieval import HybridMemoryRetriever
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_vectors import SQLiteMemoryVectors
from siro.persistence.sqlite import SQLiteStore
from siro.ports.embeddings import EmbeddingProfile


class LocalMemoryProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    mode: Literal["hybrid", "relevance"] = "hybrid"
    base_url: str = "http://127.0.0.1:11434"
    embedding_model: str = Field(min_length=1, max_length=128)
    embedding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    dimensions: int = Field(default=1024, ge=32, le=4096)
    relevance_model: str | None = Field(default=None, min_length=1, max_length=128)
    relevance_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    context_bytes: int = Field(default=8192, ge=0, le=65536)

    @model_validator(mode="after")
    def local_and_complete(self) -> LocalMemoryProfile:
        parts = urlsplit(self.base_url)
        if (
            parts.scheme != "http"
            or parts.hostname not in ("127.0.0.1", "::1")
            or parts.username
            or parts.password
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
            or (parts.port is not None and not 1 <= parts.port <= 65535)
        ):
            raise ValueError("literal loopback HTTP required")
        for model in (self.embedding_model, self.relevance_model):
            if model is not None and (
                any(c.isspace() for c in model)
                or ":cloud" in model.lower()
                or model.lower().endswith("-cloud")
            ):
                raise ValueError("local model required")
        if self.mode == "relevance":
            if self.relevance_model is None or self.relevance_digest is None:
                raise ValueError("relevance mode requires a pinned classifier")
        elif self.relevance_model is not None or self.relevance_digest is not None:
            raise ValueError("classifier fields require relevance mode")
        return self


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate profile field")
        result[key] = value
    return result


def load_local_memory_profile(path: Path) -> LocalMemoryProfile:
    """Bounded regular JSON file; sanitize validation errors containing input values."""
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 8192:
                raise ValueError("invalid profile file")
            data = stream.read(8193)
        if len(data) > 8192:
            raise ValueError("profile too large")
        return LocalMemoryProfile.model_validate(json.loads(data, object_pairs_hook=_unique_object))
    except (OSError, ValueError, TypeError, RecursionError):
        raise ValueError("local memory profile unavailable or invalid") from None


def build_local_memory(
    store: SQLiteStore,
    profile: LocalMemoryProfile | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> MemoryService:
    """No profile preserves lexical-only operation and performs no model HTTP."""
    repository = SQLiteMemoryRepository(store)
    if profile is None:
        return MemoryService(repository)
    classifier = (
        OllamaMemoryRelevance(
            profile.relevance_model,
            profile.relevance_digest,
            base_url=profile.base_url,
            transport=transport,
        )
        if profile.relevance_model is not None and profile.relevance_digest is not None
        else None
    )
    embedder = OllamaEmbedder(
        EmbeddingProfile(profile.embedding_model, profile.embedding_digest, profile.dimensions),
        base_url=profile.base_url,
        transport=transport,
    )
    return MemoryService(
        repository,
        retriever=HybridMemoryRetriever(SQLiteMemoryVectors(store), embedder, relevance=classifier),
    )
