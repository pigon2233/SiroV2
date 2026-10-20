#!/usr/bin/env python3
"""Persistent JSON-lines worker for Qwen3-TTS reference-voice synthesis."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

COMPLETION_PROTOCOL = 2
MAX_NEW_TOKENS = 512
SEGMENT_VERSION = "sentence-v2-first24-rest80"
CACHE_VERSION = "completion-v2"
MAX_CACHE_BYTES = 16 * 1024 * 1024


class QwenOutputIncomplete(ValueError):
    """The owned talker call did not prove complete, uncapped generation."""


def verified_completion(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or set(value) != {
        "status",
        "eos_observed",
        "cap_reached",
        "generated_tokens",
        "max_new_tokens",
        "observer_calls",
    }:
        return None
    count = value.get("generated_tokens")
    if (
        value.get("status") != "complete"
        or value.get("eos_observed") is not True
        or value.get("cap_reached") is not False
        or type(count) is not int
        or not 0 < count < MAX_NEW_TOKENS
        or type(value.get("max_new_tokens")) is not int
        or value.get("max_new_tokens") != MAX_NEW_TOKENS
        or type(value.get("observer_calls")) is not int
        or value.get("observer_calls") != 1
    ):
        return None
    return dict(value)


def observe_voice_clone(model: Any, text: str, voice: Any) -> tuple[Any, int, dict[str, object]]:
    """Observe only this instance's top-level talker, keeping its result untouched."""
    talker = model.model.talker
    original = talker.generate
    had_override = "generate" in vars(talker)
    prior_override = vars(talker).get("generate")
    calls = 0
    completion: dict[str, object] | None = None

    def observed(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls, completion
        calls += 1
        # This installed SDK uses inputs_embeds with an initially empty input_ids.
        # Other call shapes cannot establish how many returned tokens are new.
        eos = kwargs.get("eos_token_id")
        if (
            calls != 1
            or args
            or kwargs.get("inputs_embeds") is None
            or kwargs.get("input_ids") is not None
            or type(eos) is not int
            or eos < 0
            or type(kwargs.get("max_new_tokens")) is not int
            or kwargs.get("max_new_tokens") != MAX_NEW_TOKENS
        ):
            raise QwenOutputIncomplete("unsupported talker generation call")
        result = original(*args, **kwargs)
        sequences = getattr(result, "sequences", None)
        if sequences is None:
            raise QwenOutputIncomplete("unobservable talker output")
        try:
            shape = tuple(sequences.shape)
            rows = sequences.tolist()
        except Exception as error:
            raise QwenOutputIncomplete("unobservable talker output") from error
        if (
            len(shape) != 2
            or any(type(dimension) is not int for dimension in shape)
            or shape[0] != 1
            or not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], list)
            or not rows[0]
            or shape[1] != len(rows[0])
            or any(type(token) is not int or token < 0 for token in rows[0])
        ):
            raise QwenOutputIncomplete("unsupported talker output shape")
        tokens = rows[0]
        candidate: dict[str, object] = {
            "status": "complete",
            "eos_observed": tokens[-1] == eos,
            "cap_reached": len(tokens) >= MAX_NEW_TOKENS,
            "generated_tokens": len(tokens),
            "max_new_tokens": MAX_NEW_TOKENS,
            "observer_calls": calls,
        }
        completion = verified_completion(candidate)
        if completion is None or eos in tokens[:-1]:
            raise QwenOutputIncomplete("talker did not finish before the generation cap")
        return result

    talker.generate = observed
    primary_error: BaseException | None = None
    try:
        wavs, sample_rate = model.generate_voice_clone(
            text=text,
            language="Chinese",
            voice_clone_prompt=voice,
            non_streaming_mode=True,
            max_new_tokens=MAX_NEW_TOKENS,
        )
        if calls != 1 or completion is None:
            raise QwenOutputIncomplete("missing talker completion observation")
        return wavs, sample_rate, completion
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            if had_override:
                talker.generate = prior_override
            else:
                del talker.generate
        except Exception as error:
            if primary_error is None:
                raise QwenOutputIncomplete("cannot restore talker observer") from error
            primary_error.add_note("talker observer restoration failed")


# The CUDA-graph backend replays the same Qwen3 talker/code predictor with the same
# sampling settings; its static cache only has to hold prompt plus MAX_NEW_TOKENS.
FAST_MAX_SEQ_LEN = 2048


def fast_completion(steps: object) -> dict[str, object]:
    """Completion record for one CUDA-graph generation.

    The graph loop stops at EOS or at MAX_NEW_TOKENS; FAST_MAX_SEQ_LEN leaves room for
    every prompt plus the cap, so fewer steps than the cap can only mean EOS. EOS is
    counted as a generated token, as in the observed official talker output.
    """
    if type(steps) is not int or not 0 < steps < MAX_NEW_TOKENS - 1:
        raise QwenOutputIncomplete("talker did not finish before the generation cap")
    completion = verified_completion(
        {
            "status": "complete",
            "eos_observed": True,
            "cap_reached": False,
            "generated_tokens": steps + 1,
            "max_new_tokens": MAX_NEW_TOKENS,
            "observer_calls": 1,
        }
    )
    assert completion is not None
    return completion


class FastVoiceClone:
    """faster-qwen3-tts (CUDA graphs) behind the worker's synthesis contract."""

    def __init__(self, fast: Any) -> None:
        self.fast = fast
        self.model = fast.model if hasattr(fast, "model") else fast.base_model

    def synthesize(self, text: str, voice: Any) -> tuple[Any, int, dict[str, object]]:
        import faster_qwen3_tts.generate as fast_generate_module  # type: ignore[import-not-found]

        original = fast_generate_module.fast_generate
        steps: list[object] = []

        def observed(*args: Any, **kwargs: Any) -> Any:
            if kwargs.get("max_new_tokens") != MAX_NEW_TOKENS or steps:
                raise QwenOutputIncomplete("unsupported fast generation call")
            codes, timing = original(*args, **kwargs)
            steps.append(timing.get("steps") if codes is not None else 0)
            return codes, timing

        fast_generate_module.fast_generate = observed
        try:
            wavs, sample_rate = self.fast.generate_voice_clone(
                text=text,
                language="Chinese",
                voice_clone_prompt=voice,
                non_streaming_mode=True,
                max_new_tokens=MAX_NEW_TOKENS,
            )
        finally:
            fast_generate_module.fast_generate = original
        if len(steps) != 1:
            raise QwenOutputIncomplete("missing fast completion observation")
        return wavs, sample_rate, fast_completion(steps[0])


def load_fast_backend(model_path: str) -> FastVoiceClone | None:
    """Prefer the CUDA-graph backend when it and CUDA are present; else the official SDK."""
    if os.environ.get("SIRO_QWEN_FAST", "1") == "0":
        return None
    try:
        import torch  # type: ignore[import-not-found]
        from faster_qwen3_tts import FasterQwen3TTS  # type: ignore[import-not-found]
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None
    fast = FasterQwen3TTS.from_pretrained(
        model_path,
        device="cuda",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        max_seq_len=FAST_MAX_SEQ_LEN,
        local_files_only=True,
    )
    fast.warmup(prefill_len=100)
    return FastVoiceClone(fast)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_fingerprint(
    model_path: Path,
    reference_path: Path,
    reference_text: str,
    versions: dict[str, str],
    generation_settings: dict[str, object],
    *,
    attention: str = "eager",
) -> str:
    files = sorted(path for path in model_path.rglob("*") if path.is_file())
    if not files:
        raise ValueError("model directory has no files")
    manifest = {
        "cache_version": CACHE_VERSION,
        "completion_protocol": COMPLETION_PROTOCOL,
        "segment_version": SEGMENT_VERSION,
        "model": [(str(path.relative_to(model_path)), file_sha256(path)) for path in files],
        "reference_sha256": file_sha256(reference_path),
        "reference_text_sha256": hashlib.sha256(reference_text.encode()).hexdigest(),
        "versions": versions,
        "generation_settings": generation_settings,
        "language": "Chinese",
        "non_streaming_mode": True,
        "x_vector_only_mode": False,
        "dtype": "bfloat16",
        "attn_implementation": attention,
        "audio_format": "WAV/PCM_16",
    }
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def read_cache(
    path: Path, text_digest: str, fingerprint: str
) -> tuple[bytes, dict[str, object]] | None:
    try:
        if path.stat().st_size > MAX_CACHE_BYTES:
            return None
        entry = json.loads(path.read_bytes())
        if (
            not isinstance(entry, dict)
            or entry.get("cache_version") != CACHE_VERSION
            or entry.get("fingerprint") != fingerprint
            or entry.get("text_sha256") != text_digest
        ):
            return None
        completion = verified_completion(entry.get("completion"))
        if completion is None or not isinstance(entry.get("audio"), str):
            return None
        audio = base64.b64decode(entry["audio"], validate=True)
        if (
            len(audio) <= 44
            or audio[:4] != b"RIFF"
            or audio[8:12] != b"WAVE"
            or hashlib.sha256(audio).hexdigest() != entry.get("audio_sha256")
        ):
            return None
        return audio, completion
    except (OSError, ValueError, TypeError):
        return None


def write_cache(
    path: Path, text_digest: str, fingerprint: str, audio: bytes, completion: dict[str, object]
) -> None:
    if verified_completion(completion) is None:
        raise QwenOutputIncomplete("cannot cache unverified completion")
    entry = {
        "cache_version": CACHE_VERSION,
        "fingerprint": fingerprint,
        "text_sha256": text_digest,
        "audio_sha256": hashlib.sha256(audio).hexdigest(),
        "audio": base64.b64encode(audio).decode(),
        "completion": completion,
    }
    encoded = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_CACHE_BYTES:
        raise ValueError("audio cache entry exceeds limit")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".pending-", delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: qwen_tts_worker.py MODEL REF_WAV REF_TEXT CACHE_DIR")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import soundfile as sf  # type: ignore[import-untyped]
    import torch  # type: ignore[import-not-found]
    from qwen_tts import Qwen3TTSModel  # type: ignore[import-not-found]

    model_path, reference_wav, reference_text, cache_text = sys.argv[1:]
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    attention = "sdpa" if device == "cuda:0" else "eager"
    backend = load_fast_backend(model_path)
    if backend is not None:
        model = backend.model
    else:
        model = Qwen3TTSModel.from_pretrained(
            model_path,
            device_map=device,
            dtype=torch.bfloat16,
            attn_implementation=attention,
            local_files_only=True,
        )
    versions = {name: version(name) for name in ("qwen-tts", "transformers", "torch", "soundfile")}
    if backend is not None:
        versions["faster-qwen3-tts"] = version("faster-qwen3-tts")
    voice = model.create_voice_clone_prompt(
        ref_audio=reference_wav,
        ref_text=reference_text,
        x_vector_only_mode=False,
    )
    fingerprint = cache_fingerprint(
        Path(model_path),
        Path(reference_wav),
        reference_text,
        versions,
        model._merge_generate_kwargs(max_new_tokens=MAX_NEW_TOKENS),
        attention=attention,
    )
    cache = Path(cache_text) / CACHE_VERSION / fingerprint
    cache.mkdir(parents=True, exist_ok=True)
    print(
        json.dumps(
            {
                "ready": True,
                "device": device,
                "backend": "cuda-graph" if backend is not None else "qwen-tts",
                "completion_protocol": COMPLETION_PROTOCOL,
            }
        ),
        flush=True,
    )
    for line in sys.stdin:
        identity = {}
        try:
            request = json.loads(line)
            identity = {key: request[key] for key in ("request_id", "epoch") if key in request}
            text = str(request["text"]).strip()
            if not text:
                raise ValueError("text is empty")
            digest = hashlib.sha256(text.encode()).hexdigest()
            cached = cache / f"{digest}.json"
            cached_result = read_cache(cached, digest, fingerprint)
            if cached_result is not None:
                audio, completion = cached_result
                hit = True
            else:
                wavs, sample_rate, completion = (
                    backend.synthesize(text, voice)
                    if backend is not None
                    else observe_voice_clone(model, text, voice)
                )
                if not wavs or len(wavs[0]) == 0:
                    raise QwenOutputIncomplete("voice decoder returned no samples")
                output = io.BytesIO()
                sf.write(output, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
                audio = output.getvalue()
                write_cache(cached, digest, fingerprint, audio, completion)
                hit = False
            print(
                json.dumps(
                    {
                        **identity,
                        "audio": base64.b64encode(audio).decode(),
                        "cache_hit": hit,
                        "completion": completion,
                    }
                ),
                flush=True,
            )
        except Exception as error:
            print(json.dumps({**identity, "error": type(error).__name__}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
