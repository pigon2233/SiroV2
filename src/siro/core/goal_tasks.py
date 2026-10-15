"""Closed data and source evaluation for the first approved document-reading goal."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def relative_document(path: str) -> str:
    parsed = PurePosixPath(path)
    if (
        not path
        or len(path.encode("utf-8")) > 512
        or parsed.is_absolute()
        or ".." in parsed.parts
        or not parsed.parts
        or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in path)
        or "\\" in path
    ):
        raise ValueError("select a relative document inside the workspace")
    return parsed.as_posix()


class SourceLine(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    line: int = Field(ge=1, strict=True)
    text: str = Field(max_length=256, strict=True)


class DocumentObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    status: Literal["completed", "failed"]
    sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    read_at: datetime
    matches: tuple[SourceLine, ...] = Field(default=(), max_length=20)
    truncated: bool = False
    error: Literal["read_failed", "path_denied", "invalid_result", "timeout"] | None = None

    @model_validator(mode="after")
    def verified_shape(self) -> DocumentObservation:
        if relative_document(self.path) != self.path or self.read_at.tzinfo is None:
            raise ValueError("observation requires exact path and aware time")
        if self.status == "completed":
            if self.sha256 is None or self.error is not None:
                raise ValueError("completed observation requires source identity")
        elif self.error is None or self.sha256 is not None or self.matches or self.truncated:
            raise ValueError("failed observation cannot claim source results")
        return self


class GoalTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profile: Literal["document-checklist-v1"] = "document-checklist-v1"
    owner_session_id: str = Field(min_length=1, max_length=128, strict=True)
    workspace: str = Field(min_length=1, max_length=4096, strict=True)
    paths: tuple[str, ...] = Field(min_length=1, max_length=5)
    approved_at: datetime | None = None
    intent_path: str | None = None
    pause_reason: (
        Literal["foreground", "tools_disabled", "shutdown", "interrupted_restart", "paused"] | None
    ) = None
    observations: tuple[DocumentObservation, ...] = Field(default=(), max_length=5)

    @field_validator("owner_session_id")
    @classmethod
    def printable_owner(cls, value: str) -> str:
        if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
            raise ValueError("invalid task owner")
        return value

    @field_validator("paths")
    @classmethod
    def exact_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(relative_document(path) for path in values)
        if len(set(normalized)) != len(normalized):
            raise ValueError("select each document once")
        return normalized

    @model_validator(mode="after")
    def source_binding(self) -> GoalTask:
        observed = tuple(item.path for item in self.observations)
        if (
            len(set(observed)) != len(observed)
            or any(path not in self.paths for path in observed)
            or (self.intent_path is not None and self.intent_path not in self.paths)
        ):
            raise ValueError("task evidence must belong to approved paths")
        if self.approved_at is not None and self.approved_at.tzinfo is None:
            raise ValueError("approval requires an aware time")
        if self.approved_at is None and (self.intent_path is not None or self.observations):
            raise ValueError("unapproved task cannot carry execution evidence")
        return self


def observe_document(path: str, text: str, now: datetime) -> DocumentObservation:
    encoded = text.encode("utf-8")
    if len(encoded) > 8192:
        raise ValueError("document exceeds the approved text limit")
    found = [
        (index, line.strip())
        for index, line in enumerate(text.splitlines(), 1)
        if re.match(r"^\s*[-*+]\s+\[ \]\s+", line) or re.search(r"\b(?:TODO|FIXME)\b", line)
    ]
    return DocumentObservation(
        path=path,
        status="completed",
        sha256=hashlib.sha256(encoded).hexdigest(),
        read_at=now,
        matches=tuple(SourceLine(line=index, text=text[:256]) for index, text in found[:20]),
        truncated=len(found) > 20 or any(len(text) > 256 for _, text in found),
    )
