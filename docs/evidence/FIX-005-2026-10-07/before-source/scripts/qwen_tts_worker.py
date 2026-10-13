#!/usr/bin/env python3
"""Persistent JSON-lines worker for Qwen3-TTS reference-voice synthesis."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: qwen_tts_worker.py MODEL REF_WAV REF_TEXT CACHE_DIR")
    model_path, reference_wav, reference_text, cache_text = sys.argv[1:]
    cache = Path(cache_text)
    cache.mkdir(parents=True, exist_ok=True)
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map=device,
        dtype=torch.bfloat16,
        attn_implementation="eager",
    )
    voice = model.create_voice_clone_prompt(
        ref_audio=reference_wav,
        ref_text=reference_text,
        x_vector_only_mode=False,
    )
    print(json.dumps({"ready": True, "device": device}), flush=True)
    for line in sys.stdin:
        identity = {}
        try:
            request = json.loads(line)
            identity = {key: request[key] for key in ("request_id", "epoch") if key in request}
            text = str(request["text"]).strip()
            if not text:
                raise ValueError("text is empty")
            digest = hashlib.sha256(text.encode()).hexdigest()
            cached = cache / f"{digest}.wav"
            if cached.is_file():
                audio = cached.read_bytes()
                hit = True
            else:
                wavs, sample_rate = model.generate_voice_clone(
                    text=text,
                    language="Chinese",
                    voice_clone_prompt=voice,
                    non_streaming_mode=True,
                    max_new_tokens=512,
                )
                output = io.BytesIO()
                sf.write(output, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
                audio = output.getvalue()
                cached.write_bytes(audio)
                hit = False
            print(
                json.dumps(
                    {**identity, "audio": base64.b64encode(audio).decode(), "cache_hit": hit}
                ),
                flush=True,
            )
        except Exception as error:
            print(json.dumps({**identity, "error": type(error).__name__}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
