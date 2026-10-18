from __future__ import annotations

from pathlib import Path

import pytest
from test_memory_ingress import auth, boot


def test_actual_main_search_tracks_correction_deletion_and_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _ = boot(tmp_path, monkeypatch)
    with client:
        headers = auth(client)
        for text in ("remember: synthetic orchid tea", "remember: synthetic guitar"):
            assert client.post(
                "/v1/conversations/search/turns", headers=headers, json={"text": text}
            ).is_success
        endpoint = "/v1/memories?limit=100&query=orchid"
        assert client.get(endpoint).status_code == 401
        items = client.get(endpoint, headers=headers).json()["items"]
        assert len(items) == 1
        original = items[0]
        assert original["text"] == "synthetic orchid tea"
        assert original["revision"] == 1 and original["source_event_ids"]
        assert client.get(endpoint + "&person_id=guest", headers=headers).json()["items"] == []
        assert client.post(
            f"/v1/memories/{original['memory_id']}/correct",
            headers=headers,
            json={"text": "synthetic jasmine tea"},
        ).is_success
        assert client.get(endpoint, headers=headers).json()["items"] == []
        corrected = client.get("/v1/memories?limit=100&query=jasmine", headers=headers).json()[
            "items"
        ]
        assert corrected[0]["memory_id"] == original["memory_id"]
        assert corrected[0]["revision"] == 2
        assert client.delete(f"/v1/memories/{original['memory_id']}", headers=headers).is_success
        assert (
            client.get("/v1/memories?limit=100&query=jasmine", headers=headers).json()["items"]
            == []
        )
        remaining = client.get("/v1/memories?limit=100", headers=headers).json()["items"]
        assert len(remaining) == 1 and remaining[0]["text"] == "synthetic guitar"
