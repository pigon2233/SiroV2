"""Desktop pet settings: owner-edited file read by scripts/start-desktop at the next launch."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from siro.services.presentation.desktop_settings import load_desktop_settings
from siro.services.presentation.gateway import create_app


def test_settings_round_trip_with_defaults_and_validation(tmp_path: Path) -> None:
    origin = "http://127.0.0.1:8000"
    path = tmp_path / "desktop-settings.json"
    app = create_app(allowed_origins={origin}, desktop_settings_path=path)
    with TestClient(app) as client:
        assert client.get("/v1/desktop/settings").status_code == 401
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        auth = {"authorization": f"Bearer {token}"}
        assert client.get("/v1/desktop/settings", headers=auth).json() == {
            "gpu": True,
            "position": None,
        }
        saved = {"gpu": False, "position": {"x": -300, "y": 40}}
        assert client.put("/v1/desktop/settings", json=saved, headers=auth).json() == saved
        assert client.get("/v1/desktop/settings", headers=auth).json() == saved
        bad = {"gpu": True, "position": {"x": 10**9, "y": 0}}
        assert client.put("/v1/desktop/settings", json=bad, headers=auth).status_code == 422
        extra = {"gpu": True, "position": None, "shell": "rm"}
        assert client.put("/v1/desktop/settings", json=extra, headers=auth).status_code == 422
    assert load_desktop_settings(path) == saved


def test_damaged_settings_file_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "desktop-settings.json"
    path.write_text('{"gpu": "yes", "position": {"x": true, "y": 1}}', encoding="utf-8")
    assert load_desktop_settings(path) == {"gpu": True, "position": None}
    path.write_text("not json", encoding="utf-8")
    assert load_desktop_settings(path) == {"gpu": True, "position": None}
