from __future__ import annotations

import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

WORKER = Path(__file__).parents[1] / "scripts/qwen_tts_worker.py"
FAKE_QWEN = """
from pathlib import Path
from types import SimpleNamespace

class Sequence:
    def __init__(self, rows): self.rows = rows; self.shape = (len(rows), len(rows[0]))
    def tolist(self): return self.rows

class Talker:
    def generate(self, **kwargs):
        text = self.text
        if text == 'original-error': raise LookupError('synthetic SDK failure')
        if text == 'limit': rows = [[7] * 512]
        elif text == 'boundary': rows = [[7] * 511 + [42]]
        elif text == 'no-eos': rows = [[7, 8]]
        elif text == 'empty': rows = [[]]
        elif text == 'batch': rows = [[7, 42], [8, 42]]
        elif text == 'early-eos': rows = [[42, 7, 42]]
        elif text == 'bool-token': rows = [[True, 42]]
        else: rows = [[7, 8, 42]]
        if text == 'no-sequences': result = SimpleNamespace()
        else: result = SimpleNamespace(sequences=Sequence(rows))
        if text == 'bool-shape': result.sequences.shape = (True, len(rows[0]))
        if text == 'observer-error':
            def unreadable(): raise RuntimeError('synthetic observation failure')
            result.sequences.tolist = unreadable
        self.last_result = result
        return result

class Qwen3TTSModel:
    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        import json
        Path(__file__).with_suffix('.profile').write_text(json.dumps(kwargs))
        return cls()
    def __init__(self): self.model = SimpleNamespace(talker=Talker())
    def create_voice_clone_prompt(self, **kwargs): return {'synthetic_voice': True}
    def _merge_generate_kwargs(self, **kwargs):
        return dict(do_sample=True, top_k=50, top_p=1.0, temperature=0.9,
                    repetition_penalty=1.05, subtalker_dosample=True,
                    subtalker_top_k=50, subtalker_top_p=1.0,
                    subtalker_temperature=0.9, **kwargs)
    def generate_voice_clone(self, **kwargs):
        assert kwargs['language'] == 'Chinese'
        assert kwargs['non_streaming_mode'] is True and kwargs['max_new_tokens'] == 512
        assert kwargs['voice_clone_prompt'] == {'synthetic_voice': True}
        with Path(__file__).with_suffix('.calls').open('a') as log: log.write('generate\\n')
        talker = self.model.talker; talker.text = kwargs['text']
        if talker.text != 'missing':
            result = talker.generate(inputs_embeds=object(), eos_token_id=42,
                                     **self._merge_generate_kwargs(max_new_tokens=512))
            assert result is talker.last_result, 'observer changed the SDK result'
            if talker.text == 'duplicate': talker.generate(
                inputs_embeds=object(), eos_token_id=42, max_new_tokens=512)
        return [kwargs['text'].encode()], 24000
"""
FAKE_SOUNDFILE = """
import wave
def write(output, samples, sample_rate, **kwargs):
    assert kwargs == {'format':'WAV', 'subtype':'PCM_16'}
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
        wav.writeframes((samples + b'0') * 2)
"""


@pytest.fixture
def worker_fixture(tmp_path: Path) -> dict[str, Path]:
    packages = tmp_path / "synthetic-packages"
    packages.mkdir()
    (packages / "qwen_tts.py").write_text(FAKE_QWEN)
    (packages / "soundfile.py").write_text(FAKE_SOUNDFILE)
    (packages / "torch.py").write_text(
        "from types import SimpleNamespace\ncuda=SimpleNamespace(is_available=lambda:False)\n"
        "bfloat16='synthetic-dtype'\n"
    )
    for name, version in (
        ("qwen_tts", "0.1.1"),
        ("transformers", "4.57.3"),
        ("torch", "2.12.0"),
        ("soundfile", "0.13.1"),
    ):
        info = packages / f"{name}-{version}.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(f"Name: {name.replace('_', '-')}\nVersion: {version}\n")
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text('{"synthetic":true}')
    (model / "model.safetensors").write_bytes(b"synthetic weights")
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"synthetic reference fixture, not private audio")
    return {
        "packages": packages,
        "model": model,
        "reference": reference,
        "cache": tmp_path / "cache",
    }


def run_worker(
    fixture: dict[str, Path], texts: list[str], *, reference_text: str = "synthetic reference"
) -> list[dict[str, Any]]:
    requests = [
        {"text": text, "request_id": f"synthetic-{index}", "epoch": 7}
        for index, text in enumerate(texts)
    ]
    result = subprocess.run(
        [
            sys.executable,
            str(WORKER),
            str(fixture["model"]),
            str(fixture["reference"]),
            reference_text,
            str(fixture["cache"]),
        ],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(fixture["packages"])},
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


def generation_count(fixture: dict[str, Path]) -> int:
    calls = fixture["packages"] / "qwen_tts.calls"
    return len(calls.read_text().splitlines()) if calls.exists() else 0


def test_worker_requires_real_eos_and_preserves_identity(worker_fixture: dict[str, Path]) -> None:
    ready, result = run_worker(worker_fixture, ["complete"])
    assert ready["completion_protocol"] == 2
    assert result["request_id"] == "synthetic-0" and result["epoch"] == 7
    assert result["completion"] == {
        "status": "complete",
        "eos_observed": True,
        "cap_reached": False,
        "generated_tokens": 3,
        "max_new_tokens": 512,
        "observer_calls": 1,
    }
    assert result["audio"] and result["cache_hit"] is False


@pytest.mark.parametrize(
    "text",
    [
        "limit",
        "boundary",
        "no-eos",
        "empty",
        "batch",
        "no-sequences",
        "missing",
        "duplicate",
        "early-eos",
        "bool-token",
        "bool-shape",
        "observer-error",
    ],
)
def test_incomplete_or_unknown_output_never_returns_audio_or_success_cache(
    worker_fixture: dict[str, Path], text: str
) -> None:
    _, result = run_worker(worker_fixture, [text])
    assert result["error"] == "QwenOutputIncomplete"
    assert "audio" not in result
    assert not list(worker_fixture["cache"].rglob("*.json"))


def test_original_sdk_error_remains_original(worker_fixture: dict[str, Path]) -> None:
    _, result = run_worker(worker_fixture, ["original-error"])
    assert result["error"] == "LookupError"
    assert "audio" not in result
    assert not list(worker_fixture["cache"].rglob("*.json"))


def test_observer_state_does_not_survive_failed_request(worker_fixture: dict[str, Path]) -> None:
    _, first, failed, last = run_worker(worker_fixture, ["complete", "missing", "complete again"])
    assert first["completion"]["observer_calls"] == 1
    assert failed["error"] == "QwenOutputIncomplete" and "audio" not in failed
    assert last["completion"]["observer_calls"] == 1
    assert last["request_id"] == "synthetic-2"


def test_cache_hits_have_verified_metadata_and_fresh_request_identity(
    worker_fixture: dict[str, Path],
) -> None:
    _, first, second = run_worker(worker_fixture, ["same text", "same text"])
    assert first["cache_hit"] is False and second["cache_hit"] is True
    assert first["audio"] == second["audio"] and first["completion"] == second["completion"]
    assert second["request_id"] == "synthetic-1"
    assert generation_count(worker_fixture) == 1
    _, after_restart = run_worker(worker_fixture, ["same text"])
    assert after_restart["cache_hit"] is True
    assert generation_count(worker_fixture) == 1


def test_legacy_cache_is_preserved_but_never_trusted(worker_fixture: dict[str, Path]) -> None:
    cache = worker_fixture["cache"]
    cache.mkdir()
    legacy = cache / (hashlib.sha256(b"same text").hexdigest() + ".wav")
    legacy.write_bytes(b"RIFFsynthetic unverified legacy cache")
    _, result = run_worker(worker_fixture, ["same text"])
    assert result["cache_hit"] is False
    assert legacy.read_bytes() == b"RIFFsynthetic unverified legacy cache"
    assert generation_count(worker_fixture) == 1


@pytest.mark.parametrize("changed", ["weights", "config", "reference", "reference-text", "library"])
def test_cache_isolates_model_voice_library_and_reference_changes(
    worker_fixture: dict[str, Path], changed: str
) -> None:
    run_worker(worker_fixture, ["same text"])
    reference_text = "synthetic reference"
    if changed == "weights":
        (worker_fixture["model"] / "model.safetensors").write_bytes(b"different weights")
    elif changed == "config":
        (worker_fixture["model"] / "config.json").write_text('{"synthetic":"different"}')
    elif changed == "reference":
        worker_fixture["reference"].write_bytes(b"different synthetic reference")
    elif changed == "reference-text":
        reference_text = "different synthetic reference text"
    else:
        metadata = worker_fixture["packages"] / "transformers-4.57.3.dist-info/METADATA"
        metadata.write_text("Name: transformers\nVersion: synthetic-upgrade\n")
    _, result = run_worker(worker_fixture, ["same text"], reference_text=reference_text)
    assert result["cache_hit"] is False
    assert generation_count(worker_fixture) == 2


@pytest.mark.parametrize("corruption", ["audio_sha", "completion", "truncated", "text_sha"])
def test_corrupt_or_uncommitted_cache_cannot_be_success_hit(
    worker_fixture: dict[str, Path], corruption: str
) -> None:
    run_worker(worker_fixture, ["same text"])
    entry = next(worker_fixture["cache"].rglob("*.json"))
    data = json.loads(entry.read_text())
    if corruption == "audio_sha":
        data["audio_sha256"] = "0" * 64
    elif corruption == "completion":
        data["completion"]["eos_observed"] = False
    elif corruption == "text_sha":
        data["text_sha256"] = "0" * 64
    else:
        entry.write_text('{"audio":')
    if corruption != "truncated":
        entry.write_text(json.dumps(data))
    _, result = run_worker(worker_fixture, ["same text"])
    assert result["cache_hit"] is False
    assert generation_count(worker_fixture) == 2


def test_fingerprint_binds_effective_generation_and_segment_versions(tmp_path: Path) -> None:
    worker = runpy.run_path(str(WORKER))
    model = tmp_path / "model"
    model.mkdir()
    (model / "weights.bin").write_bytes(b"synthetic")
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"synthetic")
    fingerprint = worker["cache_fingerprint"]
    settings: dict[str, object] = {"max_new_tokens": 512, "temperature": 0.9}
    first = fingerprint(model, reference, "synthetic", {"qwen-tts": "0.1.1"}, settings)
    changed = fingerprint(
        model, reference, "synthetic", {"qwen-tts": "0.1.1"}, {**settings, "temperature": 0.8}
    )
    assert first != changed
    fingerprint.__globals__["SEGMENT_VERSION"] = "sentence-v2-synthetic"
    assert first != fingerprint(model, reference, "synthetic", {"qwen-tts": "0.1.1"}, settings)


def test_observer_restores_instance_method_and_preserves_result_and_exception() -> None:
    worker = runpy.run_path(str(WORKER))
    fake: dict[str, Any] = {}
    exec(FAKE_QWEN, fake)
    model = fake["Qwen3TTSModel"]()
    # This unit case avoids the fake SDK's subprocess-only invocation log.
    talker = model.model.talker
    original = talker.generate

    def generate_voice_clone(**kwargs: Any) -> tuple[list[bytes], int]:
        talker.text = kwargs["text"]
        result = talker.generate(inputs_embeds=object(), eos_token_id=42, max_new_tokens=512)
        assert result is talker.last_result
        return [b"synthetic"], 24000

    model.generate_voice_clone = generate_voice_clone
    worker["observe_voice_clone"](model, "complete", {"synthetic_voice": True})
    assert "generate" not in vars(talker)
    assert talker.generate.__func__ is original.__func__
    with pytest.raises(LookupError, match="synthetic SDK failure"):
        worker["observe_voice_clone"](model, "original-error", {"synthetic_voice": True})
    assert "generate" not in vars(talker)
    assert talker.generate.__func__ is original.__func__


@pytest.mark.parametrize(
    "changed",
    ["input_ids", "missing_embeds", "eos_list", "bool_eos", "wrong_cap", "bool_cap"],
)
def test_unknown_talker_call_shape_is_fail_closed(changed: str) -> None:
    worker = runpy.run_path(str(WORKER))
    original_calls = 0

    def original(**kwargs: Any) -> object:
        nonlocal original_calls
        original_calls += 1
        raise AssertionError("unsupported calls must not reach generation")

    talker = SimpleNamespace(generate=original)

    def generate_voice_clone(**kwargs: Any) -> object:
        call: dict[str, object] = {
            "inputs_embeds": object(),
            "eos_token_id": 42,
            "max_new_tokens": 512,
        }
        if changed == "input_ids":
            call["input_ids"] = [7]
        elif changed == "missing_embeds":
            del call["inputs_embeds"]
        elif changed == "eos_list":
            call["eos_token_id"] = [42]
        elif changed == "bool_eos":
            call["eos_token_id"] = True
        elif changed == "wrong_cap":
            call["max_new_tokens"] = 1024
        else:
            call["max_new_tokens"] = True
        return talker.generate(**call)

    model = SimpleNamespace(
        model=SimpleNamespace(talker=talker), generate_voice_clone=generate_voice_clone
    )
    with pytest.raises(worker["QwenOutputIncomplete"]):
        worker["observe_voice_clone"](model, "synthetic", {})
    assert original_calls == 0
    assert talker.generate is original


def test_instance_override_and_decode_exception_are_preserved() -> None:
    worker = runpy.run_path(str(WORKER))
    fake: dict[str, Any] = {}
    exec(FAKE_QWEN, fake)
    sequence = fake["Sequence"]([[7, 42]])

    def original(**kwargs: Any) -> object:
        return SimpleNamespace(sequences=sequence)

    talker = SimpleNamespace(generate=original)

    def generate_voice_clone(**kwargs: Any) -> object:
        talker.generate(inputs_embeds=object(), eos_token_id=42, max_new_tokens=512)
        raise ArithmeticError("synthetic decoder failed after EOS")

    model = SimpleNamespace(
        model=SimpleNamespace(talker=talker), generate_voice_clone=generate_voice_clone
    )
    with pytest.raises(ArithmeticError, match="synthetic decoder failed after EOS"):
        worker["observe_voice_clone"](model, "synthetic", {})
    assert talker.generate is original


def test_interrupted_atomic_commit_leaves_no_success_or_owned_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = runpy.run_path(str(WORKER))
    complete = {
        "status": "complete",
        "eos_observed": True,
        "cap_reached": False,
        "generated_tokens": 3,
        "max_new_tokens": 512,
        "observer_calls": 1,
    }

    def interrupted(*args: object) -> None:
        raise OSError("synthetic interrupted atomic commit")

    monkeypatch.setattr(worker["os"], "replace", interrupted)
    cached = tmp_path / "entry.json"
    with pytest.raises(OSError, match="synthetic interrupted atomic commit"):
        worker["write_cache"](
            cached, "synthetic-text-hash", "synthetic-fingerprint", b"audio", complete
        )
    assert not cached.exists()
    assert list(tmp_path.iterdir()) == []


def test_only_committed_cache_entry_can_be_hit(worker_fixture: dict[str, Path]) -> None:
    run_worker(worker_fixture, ["same text"])
    committed = next(worker_fixture["cache"].rglob("*.json"))
    committed.rename(committed.with_name(".pending-synthetic"))
    _, result = run_worker(worker_fixture, ["same text"])
    assert result["cache_hit"] is False
    assert generation_count(worker_fixture) == 2


def test_cuda_attention_profile_isolates_cpu_cache(worker_fixture: dict[str, Path]) -> None:
    _, cpu = run_worker(worker_fixture, ["same text"])
    profile = worker_fixture["packages"] / "qwen_tts.profile"
    assert json.loads(profile.read_text())["attn_implementation"] == "eager"
    torch = worker_fixture["packages"] / "torch.py"
    torch.write_text(torch.read_text().replace("lambda:False", "lambda:True"))
    _, cuda = run_worker(worker_fixture, ["same text"])
    selected = json.loads(profile.read_text())
    assert selected["device_map"] == "cuda:0"
    assert selected["attn_implementation"] == "sdpa"
    assert cpu["cache_hit"] is False and cuda["cache_hit"] is False
    assert generation_count(worker_fixture) == 2
    _, repeat = run_worker(worker_fixture, ["same text"])
    assert repeat["cache_hit"] is True
    assert generation_count(worker_fixture) == 2


def test_fingerprint_binds_effective_attention(tmp_path: Path) -> None:
    worker = runpy.run_path(str(WORKER))
    model = tmp_path / "model"
    model.mkdir()
    (model / "weights.bin").write_bytes(b"synthetic")
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"synthetic")
    fingerprint = worker["cache_fingerprint"]
    args = (model, reference, "synthetic", {"qwen-tts": "0.1.1"}, {"max_new_tokens": 512})
    assert fingerprint(*args, attention="eager") != fingerprint(*args, attention="sdpa")


@pytest.mark.parametrize("steps", [1, 57, 510])
def test_fast_backend_completion_counts_eos_like_the_observed_talker(steps: int) -> None:
    worker = runpy.run_path(str(WORKER))
    completion = worker["fast_completion"](steps)
    assert completion["generated_tokens"] == steps + 1
    assert worker["verified_completion"](completion) == completion


@pytest.mark.parametrize("steps", [0, 511, 512, None, 3.0])
def test_fast_backend_without_proven_eos_is_incomplete(steps: object) -> None:
    worker = runpy.run_path(str(WORKER))
    with pytest.raises(worker["QwenOutputIncomplete"]):
        worker["fast_completion"](steps)
