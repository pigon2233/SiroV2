#!/usr/bin/env python3
"""Opt-in, single-model Qwen thread comparison; never reads/writes speech caches.

Run only after the product worker and other probes release the GPU:
  .siro-data/qwen-tts-venv/bin/python \\
    docs/evidence/FIX-005-2026-10-07/benchmark_inference.py --run-real

This changes torch intra-op threads between inference groups and optionally the
requested attention implementation. It retains the installed worker's bfloat16
model, reference voice, generation settings and completion observer. Fixed seeds
improve comparability, but do not guarantee
identical CUDA results. One uncounted warmup per group precedes two measured
uncached samples. This is a diagnostic, not a p95 or listening acceptance test.

Primary API evidence (also checked in the installed source):
https://docs.pytorch.org/docs/stable/generated/torch.set_num_threads.html
https://github.com/QwenLM/Qwen3-TTS
https://huggingface.co/docs/transformers/v4.57.3/en/attention_interface
"""

# ruff: noqa: RUF001  # Mandarin punctuation is intentional synthetic input.

from __future__ import annotations

import argparse
import ast
import gc
import hashlib
import importlib.util
import io
import json
import os
import random
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).with_name("benchmark-inference-results.json")
TEXT = "今天的天空很晴朗，我們一起把小故事慢慢說完。"
SEED = 20261008


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_report(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_suffix(".pending.json")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def reference_text() -> str:
    """Read the existing public launcher constant without loading the Gateway."""
    source = (ROOT / "src/siro/services/presentation/gateway.py").read_text()
    tree = ast.parse(source)
    values = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "QwenReferenceTTS"
            and len(node.args) >= 5
            and isinstance(node.args[4], ast.Constant)
            and isinstance(node.args[4].value, str)
        ):
            values.append(node.args[4].value)
    if len(values) != 1:
        raise ValueError("expected exactly one existing reference-text constant")
    return values[0]


def load_observer() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fix005_benchmark_worker", ROOT / "scripts/qwen_tts_worker.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("worker observer is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true", help="Explicitly enable GPU inference")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--attention", choices=("eager", "sdpa"), default="eager")
    parser.add_argument(
        "--threads", choices=("default", "1", "4"), nargs="+", default=["default", "1", "4"]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.run_real:
        print("NOT_RUN: pass --run-real only when this probe owns the GPU exclusively.")
        return 0
    if not 2 <= args.repeats <= 5 or not 1 <= args.warmups <= 2:
        parser.error("repeats must be 2..5 and warmups must be 1..2")
    if len(set(args.threads)) != len(args.threads):
        parser.error("thread profiles must not repeat")
    if args.output is None:
        args.output = (
            OUTPUT if args.attention == "eager" else OUTPUT.with_name("benchmark-sdpa-results.json")
        )

    # All models and the reference stay local. No original cache or private DB use.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    began = time.monotonic()
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    observer = load_observer()
    report: dict[str, Any] = {
        "result": "RUNNING",
        "synthetic_text": TEXT,
        "text_sha256": sha(TEXT.encode()),
        "seed": SEED,
        "cache": "NOT_USED; no cache API is called",
        "model_loads": 0,
        "attention": args.attention,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "selected_profiles": [
            {"attention": args.attention, "threads": label} for label in args.threads
        ],
        "dtype": "bfloat16",
        "non_streaming_mode": True,
        "max_new_tokens": observer.MAX_NEW_TOKENS,
        "versions": {
            key: version(key) for key in ("qwen-tts", "torch", "transformers", "soundfile")
        },
        "default_num_threads": torch.get_num_threads(),
        "num_interop_threads": torch.get_num_interop_threads(),
        "cpu_count": os.cpu_count(),
        "import_seconds": round(time.monotonic() - began, 6),
        "samples": [],
        "limitations": [
            "One model stays loaded; only warmed generation is compared.",
            "Thread setter is called before each group, after model initialization.",
            "Fixed seed does not guarantee CUDA/audio identity across settings.",
            "No human listening, desktop playback or p95 latency validation.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_report(args.output, report)
    model = voice = None
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA required for the target-hardware comparison")
        default_threads = report["default_num_threads"]
        report["device"] = torch.cuda.get_device_name(0)
        torch.manual_seed(SEED)
        random.seed(SEED)
        np.random.seed(SEED)
        torch.cuda.synchronize()
        started = time.monotonic()
        model = Qwen3TTSModel.from_pretrained(
            str(ROOT / ".siro-data/models/qwen3-tts-0.6b-base"),
            device_map="cuda:0",
            dtype=torch.bfloat16,
            attn_implementation=args.attention,
            local_files_only=True,
        )
        torch.cuda.synchronize()
        report["model_loads"] = 1
        report["model_load_seconds"] = round(time.monotonic() - started, 6)
        report["actual_attention"] = {
            "model": model.model.config._attn_implementation,
            "talker": model.model.talker.config._attn_implementation,
            "code_predictor": model.model.talker.code_predictor.config._attn_implementation,
            "speech_tokenizer": model.model.speech_tokenizer.model.config._attn_implementation,
        }
        if report["actual_attention"]["talker"] != args.attention:
            raise RuntimeError("requested talker attention implementation was not selected")
        started = time.monotonic()
        voice = model.create_voice_clone_prompt(
            ref_audio=str(ROOT / ".siro-data/qwen3-siro-anime-daughter-v1.wav"),
            ref_text=reference_text(),
            x_vector_only_mode=False,
        )
        torch.cuda.synchronize()
        report["reference_prompt_seconds"] = round(time.monotonic() - started, 6)
        report["generation_settings_sha256"] = sha(
            json.dumps(
                model._merge_generate_kwargs(max_new_tokens=observer.MAX_NEW_TOKENS),
                sort_keys=True,
                default=str,
            ).encode()
        )
        report["worker_sha256"] = sha((ROOT / "scripts/qwen_tts_worker.py").read_bytes())
        write_report(args.output, report)
        profile_threads = {"default": default_threads, "1": 1, "4": 4}
        for label in args.threads:
            threads = profile_threads[label]
            torch.set_num_threads(threads)
            if torch.get_num_threads() != threads:
                raise RuntimeError("thread-setting verification failed")
            for index in range(args.warmups + args.repeats):
                random.seed(SEED)
                np.random.seed(SEED)
                torch.manual_seed(SEED)
                torch.cuda.manual_seed_all(SEED)
                torch.cuda.synchronize()
                talker = model.model.talker
                previous = talker.generate
                had_override = "generate" in vars(talker)
                prior_override = vars(talker).get("generate")
                talker_seconds: list[float] = []

                def timed_generate(
                    *call_args: Any,
                    _generate: Any = previous,
                    _timings: list[float] = talker_seconds,
                    **kwargs: Any,
                ) -> Any:
                    torch.cuda.synchronize()
                    clock_started = time.monotonic()
                    try:
                        return _generate(*call_args, **kwargs)
                    finally:
                        torch.cuda.synchronize()
                        _timings.append(time.monotonic() - clock_started)

                talker.generate = timed_generate
                sample: dict[str, Any] = {
                    "group": label,
                    "attention": args.attention,
                    "num_threads": torch.get_num_threads(),
                    "num_interop_threads": torch.get_num_interop_threads(),
                    "kind": "warmup" if index < args.warmups else "measured",
                    "index": index,
                    "result": "RUNNING",
                }
                report["samples"].append(sample)
                write_report(args.output, report)
                started = time.monotonic()
                try:
                    wavs, rate, completion = observer.observe_voice_clone(model, TEXT, voice)
                    torch.cuda.synchronize()
                    elapsed = time.monotonic() - started
                    if len(wavs) != 1 or len(wavs[0]) == 0 or rate <= 0:
                        raise ValueError("empty or unexpected audio output")
                    if len(talker_seconds) != 1:
                        raise ValueError("expected one top-level talker timing")
                    duration = len(wavs[0]) / rate
                    output = io.BytesIO()
                    sf.write(output, wavs[0], rate, format="WAV", subtype="PCM_16")
                    sample.update(
                        result="PASS",
                        completion=completion,
                        generation_seconds=round(elapsed, 6),
                        talker_seconds=round(talker_seconds[0], 6),
                        outside_talker_seconds=round(elapsed - talker_seconds[0], 6),
                        duration_seconds=round(duration, 6),
                        real_time_factor=round(elapsed / duration, 6),
                        sample_rate=rate,
                        audio_sha256=sha(output.getvalue()),
                    )
                    print(json.dumps(sample, ensure_ascii=False), flush=True)
                except BaseException as error:
                    sample.update(result="FAIL", error_type=type(error).__name__)
                    raise
                finally:
                    if had_override:
                        talker.generate = prior_override
                    else:
                        del talker.generate
                    write_report(args.output, report)
        report["result"] = "PASS"
    except BaseException as error:
        report.update(result="FAIL", error_type=type(error).__name__)
        print(json.dumps({"result": "FAIL", "error_type": type(error).__name__}), flush=True)
    finally:
        voice = model = talker = previous = prior_override = timed_generate = None
        gc.collect()
        if torch.cuda.is_initialized():
            torch.cuda.empty_cache()
        report["total_seconds"] = round(time.monotonic() - began, 6)
        report["cleanup"] = "model/voice references released; process exit releases CUDA context"
        write_report(args.output, report)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
