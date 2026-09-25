from pathlib import Path

import pytest
from pydantic import ValidationError

from siro.config import DeploymentProfile, PrivacyClass, SiroSettings, load_settings


def test_defaults_are_offline_and_minimal() -> None:
    settings = SiroSettings()

    assert settings.schema_version == 1
    assert settings.profile is DeploymentProfile.MINIMAL
    assert settings.privacy is PrivacyClass.LOCAL_ONLY
    assert settings.network.bind_host == "127.0.0.1"
    assert settings.network.cloud_routes_enabled is False
    assert settings.proactivity.enabled is False


def test_unknown_settings_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"schema_version": 1, "unknown": true}', encoding="utf-8")

    with pytest.raises(ValidationError):
        load_settings(path)


def test_future_schema_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"schema_version": 2}', encoding="utf-8")

    with pytest.raises(ValidationError):
        load_settings(path)
