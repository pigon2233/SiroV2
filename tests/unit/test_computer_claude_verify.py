"""Semantic verification never treats pixel movement alone as success; all provider calls fake."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import pytest

from siro.services.computer_use.decision import ClaudeVisionDecider, CloudScreenNotAllowed
from siro.services.computer_use.perception import Observation

OBS = Observation(
    1,
    0,
    "Game",
    "game.exe",
    (0, 0, 100, 100),
    (100, 100),
    "one",
    base64.b64encode(b"image").decode(),
    (100, 100),
    (0, 0, 100, 100),
)


def test_default_off_does_not_call_cli() -> None:
    async def never(*args: Any, **kw: Any) -> dict[str, Any]:
        raise AssertionError("provider called")

    brain = ClaudeVisionDecider(env={}, run=never)
    result = asyncio.run(brain.verify("menu closed", "menu", OBS))
    assert result.status == "unknown" and result.detail == "claude_verify_not_used"


def test_cloud_consent_still_required() -> None:
    brain = ClaudeVisionDecider(env={"SIRO_COMPUTER_CLAUDE_VERIFY": "1"})
    with pytest.raises(CloudScreenNotAllowed):
        asyncio.run(brain.verify("menu closed", "menu", OBS))


@pytest.mark.parametrize(
    "reply,status",
    [
        ('{"status":"confirmed","detail":"character select visible"}', "confirmed"),
        ('{"status":"denied","detail":"still menu"}', "denied"),
        ("invalid", "unknown"),
        ('{"status":"yes"}', "unknown"),
    ],
)
def test_bounded_read_only_cli_and_strict_proof(reply: str, status: str) -> None:
    calls = []

    async def fake(argv: tuple[str, ...], **kw: Any) -> dict[str, Any]:
        calls.append(argv)
        assert (Path(kw["cwd"]) / "screen.jpg").read_bytes() == b"image"
        assert "--allowedTools" in argv and argv[argv.index("--allowedTools") + 1] == "Read"
        assert "--no-session-persistence" in argv
        return {"returncode": 0, "stdout": json.dumps({"result": reply})}

    brain = ClaudeVisionDecider(
        env={"SIRO_COMPUTER_CLAUDE_VERIFY": "1", "SIRO_COMPUTER_CLOUD_SCREEN": "1"},
        run=fake,
        binary=Path("/unit/claude"),
    )
    assert asyncio.run(brain.verify("character select visible", "menu", OBS)).status == status
    assert len(calls) == 1
