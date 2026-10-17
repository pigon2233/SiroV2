"""One offline utterance. Raw audio stays in stdin memory and is never saved."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path


def main() -> int:
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]

    from siro.services.audio.local_stt import LocalWhisper

    directory = Path(sys.argv[1]).resolve(strict=True)
    language = None if sys.argv[2] == "auto" else sys.argv[2]
    audio = sys.stdin.buffer.read(3 * 1024 * 1024 + 1)
    LocalWhisper._validate_audio(audio)
    model = WhisperModel(
        str(directory), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True
    )
    segments, info = model.transcribe(
        io.BytesIO(audio),
        language=language,
        beam_size=3,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    text = "".join(segment.text for segment in segments).strip()
    if len(text) > 20_000:
        raise ValueError("speech response limit exceeded")
    print(json.dumps({"text": text, "language": info.language}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Neither raw audio, decoded text nor SDK payloads belong in worker logs.
        raise SystemExit(1) from None
