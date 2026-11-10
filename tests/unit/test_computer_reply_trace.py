"""Raw diagnostics require explicit consent, existing dump destination and game allowlist."""

from __future__ import annotations

import base64
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from siro.services.computer_use import reply_trace
from siro.services.computer_use.decision import DecisionError
from siro.services.computer_use.perception import Observation


@pytest.fixture
def obs() -> Observation:
    output = io.BytesIO()
    Image.new("RGB", (20, 20)).save(output, format="PNG")
    return Observation(
        4,
        1,
        "Game",
        "game.exe",
        (0, 0, 40, 40),
        (40, 40),
        "hash",
        base64.b64encode(output.getvalue()).decode(),
        (20, 20),
        (0, 0, 40, 40),
        window_id="5",
        pid=6,
    )


def env(tmp_path: Path) -> dict[str, str]:
    return {
        "SIRO_COMPUTER_TRACE_REPLIES": "1",
        "SIRO_COMPUTER_DUMP_FRAMES": str(tmp_path / "trace"),
        "SIRO_COMPUTER_ALLOWED_PROCESSES": "game.exe",
    }


@pytest.mark.parametrize(
    "missing",
    ["SIRO_COMPUTER_TRACE_REPLIES", "SIRO_COMPUTER_DUMP_FRAMES", "SIRO_COMPUTER_ALLOWED_PROCESSES"],
)
def test_each_permission_required(tmp_path: Path, obs: Observation, missing: str) -> None:
    values = env(tmp_path)
    values.pop(missing)
    with pytest.raises(DecisionError):
        reply_trace.parse_reply("broken", obs, values, goal="play", model="unit")
    assert not (tmp_path / "trace").exists()


@pytest.mark.parametrize("problem", ["blocked", "secret", "wrong_process"])
def test_privacy_and_whitelist_never_record(tmp_path: Path, obs: Observation, problem: str) -> None:
    current = (
        replace(obs, blocked_reason="blocked_title")
        if problem == "blocked"
        else replace(obs, focus_is_secret=True)
        if problem == "secret"
        else replace(obs, process="other.exe")
    )
    reply_trace.record_reply("broken", current, env(tmp_path), goal="play", model="unit")
    assert not (tmp_path / "trace").exists()


def test_exact_error_raw_frame_hash_mapping_and_redaction(tmp_path: Path, obs: Observation) -> None:
    raw = "not-json sk-" + "x" * 25
    with pytest.raises(DecisionError, match="not_json"):
        reply_trace.parse_reply(raw, obs, env(tmp_path), goal="play", model="unit")
    folder = tmp_path / "trace"
    rows = list(folder.glob("reply-*.json"))
    assert len(rows) == 1
    data = json.loads(rows[0].read_text())
    assert data["error"] == "not_json"
    assert data["raw"] == "not-json [redacted]"
    assert data["seq"] == 4 and data["image_rect"] == [0, 0, 40, 40]
    assert (folder / data["image"]).is_file()


def test_io_failure_never_changes_parse_result(tmp_path: Path, obs: Observation) -> None:
    target = tmp_path / "trace"
    target.write_text("file not dir")
    result = reply_trace.parse_reply(
        '{"kind":"wait"}', obs, env(tmp_path), goal="play", model="unit"
    )
    assert result.kind == "wait"


def test_bounded_records(tmp_path: Path, obs: Observation, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reply_trace, "_records", reply_trace.MAX_RECORDS)
    reply_trace.record_reply("broken", obs, env(tmp_path), goal="play", model="unit")
    assert not (tmp_path / "trace").exists()
