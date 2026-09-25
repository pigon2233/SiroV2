from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from siro.services.audio.protocol import (
    AudioFrame,
    AudioMetadata,
    AudioRingBuffer,
    BufferResult,
    PlaybackOwnership,
)


def test_python_and_node_share_binary_audio_golden_fixture() -> None:
    root = Path(__file__).parents[2]
    fixture_path = root / "tests" / "fixtures" / "audio" / "frame.v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    frame = AudioFrame(
        int(fixture["stream_token"], 16),
        fixture["sequence"],
        int(fixture["sample_offset"], 16),
        bytes.fromhex(fixture["payload_hex"]),
    )
    assert frame.encode().hex() == fixture["encoded_hex"]
    assert AudioFrame.decode(bytes.fromhex(fixture["encoded_hex"])) == frame
    result = subprocess.run(
        ["node", root / "tests" / "contract" / "audio_golden.mjs", fixture_path],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == "ok\n"


def test_sample_rate_ring_buffer_failures_and_single_owner_are_explicit() -> None:
    with pytest.raises(ValueError, match="sample rate"):
        AudioMetadata("s", "session", "turn", "generation", "speech", 44_100)
    metadata = AudioMetadata("s", "session", "turn", "generation", "speech", 16_000)
    payload = bytes(metadata.frame_samples * 2)
    buffer = AudioRingBuffer(metadata, capacity_seconds=0.04)
    assert buffer.push(AudioFrame(1, 0, 0, payload)) is BufferResult.ACCEPTED
    assert buffer.push(AudioFrame(1, 2, 640, payload)) is BufferResult.MISSING
    assert buffer.push(AudioFrame(1, 1, 320, payload)) is BufferResult.OUT_OF_ORDER
    assert buffer.push(AudioFrame(1, 3, 960, payload)) is BufferResult.OVERFLOW
    assert buffer.pending == 2

    owners = PlaybackOwnership()
    assert owners.acquire("session", "audio-service")
    assert not owners.acquire("session", "renderer")
    assert not owners.release("session", "renderer")
    assert owners.release("session", "audio-service")
    assert owners.acquire("session", "renderer")
