"""Versioned PCM frame header, bounded ring buffer, and playback ownership."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import StrEnum

MAGIC = b"SRA1"
HEADER = struct.Struct(">4sBBHQIQI")
HEADER_BYTES = HEADER.size
SUPPORTED_SAMPLE_RATES = (16_000, 24_000, 48_000)


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    stream_id: str
    session_id: str
    turn_id: str
    generation_id: str
    speech_id: str
    sample_rate: int
    channels: int = 1
    codec: str = "pcm_s16le"

    def __post_init__(self) -> None:
        identifiers = (
            self.stream_id,
            self.session_id,
            self.turn_id,
            self.generation_id,
            self.speech_id,
        )
        if any(not value for value in identifiers):
            raise ValueError("audio metadata identifiers cannot be empty")
        if self.sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise ValueError("unsupported audio sample rate")
        if self.channels != 1 or self.codec != "pcm_s16le":
            raise ValueError("protocol v1 requires PCM s16le mono")

    @property
    def frame_samples(self) -> int:
        return self.sample_rate // 50


@dataclass(frozen=True, slots=True)
class AudioFrame:
    stream_token: int
    sequence: int
    sample_offset: int
    payload: bytes
    end_of_stream: bool = False

    def encode(self) -> bytes:
        if not 0 <= self.stream_token < 2**64:
            raise ValueError("stream token is out of range")
        if not 0 <= self.sequence < 2**32 or not 0 <= self.sample_offset < 2**64:
            raise ValueError("audio sequence or offset is out of range")
        if len(self.payload) > 2**32 - 1:
            raise ValueError("audio payload is too large")
        flags = 1 if self.end_of_stream else 0
        return (
            HEADER.pack(
                MAGIC,
                1,
                flags,
                HEADER_BYTES,
                self.stream_token,
                self.sequence,
                self.sample_offset,
                len(self.payload),
            )
            + self.payload
        )

    @classmethod
    def decode(cls, encoded: bytes) -> AudioFrame:
        if len(encoded) < HEADER_BYTES:
            raise ValueError("audio frame is shorter than its header")
        magic, version, flags, header_bytes, token, sequence, offset, payload_bytes = HEADER.unpack(
            encoded[:HEADER_BYTES]
        )
        if magic != MAGIC or version != 1 or header_bytes != HEADER_BYTES or flags & ~1:
            raise ValueError("unsupported or malformed audio frame header")
        payload = encoded[HEADER_BYTES:]
        if len(payload) != payload_bytes:
            raise ValueError("audio payload length mismatch")
        return cls(token, sequence, offset, payload, bool(flags & 1))


class BufferResult(StrEnum):
    ACCEPTED = "accepted"
    MISSING = "missing"
    OUT_OF_ORDER = "out_of_order"
    OVERFLOW = "overflow"


class AudioRingBuffer:
    def __init__(self, metadata: AudioMetadata, *, capacity_seconds: float = 2.0) -> None:
        self._metadata = metadata
        self._capacity = max(1, int(capacity_seconds * 50))
        self._frames: list[AudioFrame] = []
        self._next_sequence = 0

    def push(self, frame: AudioFrame) -> BufferResult:
        if len(frame.payload) != self._metadata.frame_samples * 2:
            raise ValueError("PCM frame is not exactly 20 ms")
        if frame.sequence < self._next_sequence:
            return BufferResult.OUT_OF_ORDER
        if len(self._frames) >= self._capacity:
            return BufferResult.OVERFLOW
        result = (
            BufferResult.MISSING if frame.sequence > self._next_sequence else BufferResult.ACCEPTED
        )
        self._frames.append(frame)
        self._next_sequence = frame.sequence + 1
        return result

    def pop(self) -> AudioFrame | None:
        return self._frames.pop(0) if self._frames else None

    @property
    def pending(self) -> int:
        return len(self._frames)


class PlaybackOwnership:
    def __init__(self) -> None:
        self._owners: dict[str, str] = {}

    def acquire(self, session_id: str, owner_id: str) -> bool:
        owner = self._owners.get(session_id)
        if owner is not None and owner != owner_id:
            return False
        self._owners[session_id] = owner_id
        return True

    def release(self, session_id: str, owner_id: str) -> bool:
        if self._owners.get(session_id) != owner_id:
            return False
        self._owners.pop(session_id)
        return True
