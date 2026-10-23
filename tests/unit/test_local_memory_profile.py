from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from siro.services.agent.local_memory import LocalMemoryProfile, load_local_memory_profile


def fields() -> dict[str, Any]:
    return {"embedding_model": "synthetic", "embedding_digest": "a" * 64, "dimensions": 32}


@pytest.mark.parametrize(
    "changes",
    [
        {"base_url": "https://127.0.0.1:11434"},
        {"base_url": "http://localhost:11434"},
        {"base_url": "http://127.0.0.1:0"},
        {"base_url": "http://127.0.0.1:65536"},
        {"base_url": "http://127.0.0.1:11434/other"},
        {"base_url": "http://private@127.0.0.1:11434"},
        {"base_url": "http://127.0.0.1:11434?private=value"},
        {"base_url": "http://127.0.0.1:11434#private"},
        {"embedding_model": "synthetic:cloud"},
        {"embedding_model": "synthetic:large-cloud"},
        {"embedding_model": "synthetic bad"},
        {"embedding_digest": "a" * 63},
        {"dimensions": True},
        {"dimensions": "32"},
        {"dimensions": 4097},
        {"context_bytes": -1},
        {"context_bytes": 65537},
        {"mode": "relevance"},
        {"relevance_model": "judge", "relevance_digest": "b" * 64},
        {"permission": "save automatically"},
    ],
)
def test_invalid_or_ignored_configuration_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        LocalMemoryProfile.model_validate(fields() | changes)


def test_profile_load_is_strict_and_errors_do_not_echo_input(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(fields()), encoding="utf-8")
    assert load_local_memory_profile(path).dimensions == 32
    for data in (
        '{"embedding_model":"PRIVATE","embedding_model":"other"}',
        json.dumps(fields() | {"PRIVATE": "PRIVATE"}),
        "[1]",
        "{" * 8192,
        " " * 8193,
    ):
        path.write_text(data, encoding="utf-8")
        with pytest.raises(ValueError) as error:
            load_local_memory_profile(path)
        assert "PRIVATE" not in str(error.value)
    with pytest.raises(ValueError):
        load_local_memory_profile(tmp_path)


def test_relevance_requires_both_pins_and_accepts_ipv6() -> None:
    values = fields() | {
        "mode": "relevance",
        "base_url": "http://[::1]:11434",
        "relevance_model": "judge",
        "relevance_digest": "b" * 64,
    }
    assert LocalMemoryProfile.model_validate(values).mode == "relevance"
    for key in ("relevance_model", "relevance_digest"):
        with pytest.raises(ValidationError):
            LocalMemoryProfile.model_validate(values | {key: None})
