from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_memory_ingress import auth, boot

from siro.core.profile import ProfileService
from siro.persistence.profile import SQLiteProfileSource
from siro.services.presentation import gateway


@dataclass
class Reply:
    text: str


class Completer:
    async def complete(self, role: str, prompt: str) -> Reply:
        return Reply(
            '{"entries":[{"index":0,"category":"preference",'
            '"text":"喜歡無糖綠茶","quote":"喜歡喝無糖綠茶"}]}'
        )


def test_profile_routes_list_rebuild_and_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, captured = boot(tmp_path, monkeypatch)
    memory = captured["memory_service"]
    source = SQLiteProfileSource(memory._repository._store)
    captured["profile_service"] = ProfileService(memory, Completer(), cloud=False)
    captured["profile_source"] = source
    client = TestClient(gateway.create_app(**captured))
    with client:
        headers = auth(client)
        assert client.get("/v1/profile").status_code == 401
        assert client.post("/v1/profile/rebuild").status_code == 401
        assert client.get("/v1/profile", headers=headers).json() == {"items": []}
        assert client.post(
            "/v1/conversations/search/turns", headers=headers, json={"text": "我平常喜歡喝無糖綠茶"}
        ).is_success
        assert client.post("/v1/profile/rebuild", headers=headers).json() == {"created": 1}
        assert client.post("/v1/profile/rebuild", headers=headers).json() == {"created": 0}
        (item,) = client.get("/v1/profile", headers=headers).json()["items"]
        assert item["category"] == "preference" and item["text"] == "喜歡無糖綠茶"
        assert item["quote"] == "喜歡喝無糖綠茶"
        assert item["message_text"] == "我平常喜歡喝無糖綠茶" and item["message_at"]
        assert client.delete(f"/v1/memories/{item['memory_id']}", headers=headers).is_success
        assert client.get("/v1/profile", headers=headers).json() == {"items": []}


def test_profile_routes_unavailable_without_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway, "codex_ready", lambda binary: False)
    client, _, _ = boot(tmp_path, monkeypatch)
    with client:
        headers = auth(client)
        assert client.get("/v1/profile", headers=headers).status_code == 503
        assert client.post("/v1/profile/rebuild", headers=headers).status_code == 503
