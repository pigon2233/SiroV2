"""Persistent offline recognizer. Raw audio stays in stdin memory and is never saved.

Protocol: one ``{"ready": true}`` line once the model is loaded, then per request a
JSON header line ``{"bytes": N, "language": "zh"}`` followed by exactly N WAV bytes,
answered by one JSON line. The model loads once, so each utterance only pays for
recognition instead of process start, imports and model load.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

# Whisper otherwise drifts between scripts; the owner writes Traditional Chinese.
_LANGUAGE_PROMPTS = {"zh": "以下是繁體中文的句子。"}
_MAX_AUDIO = 3 * 1024 * 1024


def main() -> int:
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]

    from siro.services.audio.local_stt import LocalWhisper

    directory = Path(sys.argv[1]).resolve(strict=True)
    model = WhisperModel(
        str(directory), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True
    )
    stdin, stdout = sys.stdin.buffer, sys.stdout
    stdout.write(json.dumps({"ready": True}) + "\n")
    stdout.flush()
    while header := stdin.readline(4096):
        request = json.loads(header)
        size, language = request["bytes"], request.get("language")
        if type(size) is not int or not 0 < size <= _MAX_AUDIO:
            return 1  # framing is lost; the owner respawns
        audio = stdin.read(size)
        try:
            LocalWhisper._validate_audio(audio)
            if language is not None and not isinstance(language, str):
                raise ValueError("invalid speech language")
            segments, info = model.transcribe(
                io.BytesIO(audio),
                language=language,
                beam_size=3,
                vad_filter=True,
                condition_on_previous_text=False,
                initial_prompt=_LANGUAGE_PROMPTS.get(language or ""),
            )
            text = "".join(segment.text for segment in segments).strip()
            if len(text) > 20_000:
                raise ValueError("speech response limit exceeded")
            stdout.write(json.dumps({"text": text, "language": info.language}, ensure_ascii=False))
        except Exception:
            # Neither raw audio, decoded text nor SDK payloads belong in worker output.
            stdout.write(json.dumps({"error": "recognition failed"}))
        stdout.write("\n")
        stdout.flush()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(1) from None
