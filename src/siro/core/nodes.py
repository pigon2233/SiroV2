"""Pre-paired compute node trust registry with expiry and revocation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from siro.contracts.events import Privacy


class NodeStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    REVOKED = "revoked"


class NodeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    paired_key_id: str = Field(min_length=8)
    privacy_ceiling: Privacy
    models: tuple[str, ...]
    location: Literal["local", "lan", "cloud"] = "local"
    protocol_version: int = Field(default=1, ge=1)
    capabilities: tuple[str, ...] = ("inference",)
    hardware: str = "unknown"
    heartbeat_ttl_seconds: int = Field(default=30, ge=1, le=3600)


class NodeHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1, max_length=64)
    available_memory_bytes: int = Field(ge=0)
    queue_depth: int = Field(ge=0, le=100_000)


class NodeRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, NodeProfile] = {}
        self._heartbeats: dict[str, tuple[datetime, NodeHeartbeat]] = {}
        self._revoked: set[str] = set()

    def pair(self, profile: NodeProfile) -> None:
        if profile.node_id in self._profiles:
            raise ValueError("node is already paired")
        self._profiles[profile.node_id] = profile

    def heartbeat(
        self,
        node_id: str,
        key_id: str,
        *,
        now: datetime,
        advertisement: NodeHeartbeat | None = None,
    ) -> None:
        profile = self._profiles.get(node_id)
        if profile is None or profile.paired_key_id != key_id or node_id in self._revoked:
            raise PermissionError("unknown or revoked node")
        self._heartbeats[node_id] = (
            now,
            advertisement
            or NodeHeartbeat(version="unknown", available_memory_bytes=0, queue_depth=0),
        )

    def revoke(self, node_id: str) -> None:
        if node_id not in self._profiles:
            raise KeyError(node_id)
        self._revoked.add(node_id)

    def status(self, node_id: str, *, now: datetime) -> NodeStatus:
        if node_id in self._revoked:
            return NodeStatus.REVOKED
        profile = self._profiles.get(node_id)
        heartbeat = self._heartbeats.get(node_id)
        seen = heartbeat[0] if heartbeat else None
        if (
            profile is None
            or seen is None
            or now >= seen + timedelta(seconds=profile.heartbeat_ttl_seconds)
        ):
            return NodeStatus.OFFLINE
        return NodeStatus.ONLINE

    def heartbeat_details(self, node_id: str) -> NodeHeartbeat | None:
        heartbeat = self._heartbeats.get(node_id)
        return heartbeat[1] if heartbeat else None

    def save(self, path: Path) -> None:
        payload = {
            "profiles": [profile.model_dump(mode="json") for profile in self._profiles.values()],
            "revoked": sorted(self._revoked),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> NodeRegistry:
        registry = cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        for raw in payload["profiles"]:
            registry.pair(NodeProfile.model_validate(raw))
        registry._revoked = set(payload["revoked"])
        return registry

    def routeable(self, *, privacy: Privacy, now: datetime) -> tuple[NodeProfile, ...]:
        return tuple(
            profile
            for profile in self._profiles.values()
            if self.status(profile.node_id, now=now) is NodeStatus.ONLINE
            and privacy_rank(privacy) <= privacy_rank(profile.privacy_ceiling)
        )


def privacy_rank(value: Privacy) -> int:
    return {Privacy.LOCAL_ONLY: 0, Privacy.TRUSTED_LAN: 1, Privacy.CLOUD_ALLOWED: 2}[value]
