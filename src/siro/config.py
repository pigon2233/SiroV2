"""Versioned settings for the minimal SIRO profile."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeploymentProfile(StrEnum):
    """Profiles that have explicit gates in the development plan."""

    MINIMAL = "minimal"
    COMPANION = "companion"
    LOCAL_AI = "local-ai"
    DISTRIBUTED = "distributed"


class PrivacyClass(StrEnum):
    """Maximum data disclosure allowed by a setting or event."""

    LOCAL_ONLY = "local_only"
    TRUSTED_LAN = "trusted_lan"
    CLOUD_ALLOWED = "cloud_allowed"


class ProactivitySettings(BaseModel):
    """User-controlled proactive behaviour defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    timezone: str = "Asia/Taipei"
    quiet_start: str = Field(default="23:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    quiet_end: str = Field(default="08:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    daily_social_limit: int = Field(default=6, ge=0, le=100)


class NetworkSettings(BaseModel):
    """Network defaults remain loopback and offline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bind_host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    cloud_routes_enabled: bool = False
    telemetry_enabled: bool = False


class SiroSettings(BaseModel):
    """Top-level settings schema version 1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile: DeploymentProfile = DeploymentProfile.MINIMAL
    privacy: PrivacyClass = PrivacyClass.LOCAL_ONLY
    network: NetworkSettings = NetworkSettings()
    proactivity: ProactivitySettings = ProactivitySettings()


def load_settings(path: Path | None = None) -> SiroSettings:
    """Load a JSON settings file, or return conservative defaults."""

    if path is None:
        return SiroSettings()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("settings root must be a JSON object")
    return SiroSettings.model_validate(raw)
