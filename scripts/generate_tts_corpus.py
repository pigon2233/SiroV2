"""Render a text list with SIRO's current Qwen voice into a single-speaker training corpus.

The corpus is for training a small fixed-voice TTS that can run on the CPU. Each line of the
text file becomes ``wavs/<index>.wav`` plus one ``metadata.csv`` row (``<index>|<text>``, the
LJSpeech layout). The existing worker does the synthesis, so the voice, sampling settings and
the completion check are exactly the ones the product uses. Lines the worker rejects (too long
for its token cap, incomplete output) are skipped and listed in ``skipped.txt``.

Reruns continue where the last run stopped. Nothing is sent anywhere; write the corpus outside
the repository, it is generated audio of the owner's chosen voice.

    python scripts/generate_tts_corpus.py \\
        --python ~/.local/share/siro/data/qwen-tts-venv/bin/python \\
        --model ~/.local/share/siro/data/models/qwen3-tts-0.6b-base \\
        --voice-profile ~/.local/share/siro/data/voices/siro-sweet-b-v1.json \\
        --texts sentences.txt --out ~/.local/share/siro/tts-corpus/siro-sweet-b-v1
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

WORKER = Path(__file__).with_name("qwen_tts_worker.py")


def read_texts(path: Path, limit: int | None) -> list[str]:
    seen: set[str] = set()
    texts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = " ".join(line.split())
        if text and text not in seen:
            seen.add(text)
            texts.append(text)
    return texts if limit is None else texts[:limit]


def wav_seconds(audio: bytes) -> float:
    with wave.open(io.BytesIO(audio)) as source:
        return source.getnframes() / source.getframerate()


def read_reply(process: subprocess.Popen[str]) -> dict[str, object]:
    assert process.stdout is not None
    while True:
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("worker exited")
        if line.startswith("{"):  # the backend prints progress text on the same stream
            reply = json.loads(line)
            if isinstance(reply, dict):
                return reply


def generate(
    command: list[str], texts: list[str], out: Path, *, log: object = sys.stderr
) -> tuple[int, int, float]:
    """Returns (written, skipped, seconds of audio written in this run)."""
    wavs = out / "wavs"
    wavs.mkdir(parents=True, exist_ok=True)
    metadata = out / "metadata.csv"
    done = set()
    if metadata.is_file():
        done = {
            row.split("|", 1)[1] for row in metadata.read_text("utf-8").splitlines() if "|" in row
        }
    skipped_file = out / "skipped.txt"
    if skipped_file.is_file():
        done |= set(skipped_file.read_text("utf-8").splitlines())
    index = len(list(wavs.glob("*.wav")))
    pending = [text for text in texts if text not in done]
    if not pending:
        return 0, 0, 0.0
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8"
    )
    written = skipped = 0
    seconds = 0.0
    try:
        if read_reply(process).get("ready") is not True:
            raise RuntimeError("worker did not become ready")
        assert process.stdin is not None
        started = time.monotonic()
        for text in pending:
            process.stdin.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
            process.stdin.flush()
            reply = read_reply(process)
            audio = reply.get("audio")
            if not isinstance(audio, str):
                skipped += 1
                with skipped_file.open("a", encoding="utf-8") as target:
                    target.write(text + "\n")
                continue
            data = base64.b64decode(audio)
            index += 1
            name = f"{index:06d}"
            (wavs / f"{name}.wav").write_bytes(data)
            with metadata.open("a", encoding="utf-8") as target:
                target.write(f"{name}|{text}\n")
            written += 1
            seconds += wav_seconds(data)
            if written % 20 == 0:
                print(
                    f"{written}/{len(pending)} written, {seconds / 60:.1f} min of audio, "
                    f"{time.monotonic() - started:.0f}s elapsed",
                    file=log,  # type: ignore[arg-type]
                    flush=True,
                )
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
    return written, skipped, seconds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--python", required=True, type=Path, help="interpreter of the Qwen venv")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--voice-profile", required=True, type=Path)
    parser.add_argument("--texts", required=True, type=Path, help="UTF-8, one sentence per line")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=None, help="only the first N sentences")
    arguments = parser.parse_args()
    profile = json.loads(arguments.voice_profile.expanduser().read_text("utf-8"))
    out = arguments.out.expanduser()
    command = [
        str(arguments.python.expanduser()),
        str(WORKER),
        str(arguments.model.expanduser()),
        str(profile["reference_wav"]),
        str(profile["reference_text"]),
        str(out / "worker-cache"),  # separate from the product cache
    ]
    texts = read_texts(arguments.texts.expanduser(), arguments.limit)
    written, skipped, seconds = generate(command, texts, out)
    print(f"written={written} skipped={skipped} audio_minutes={seconds / 60:.1f} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
