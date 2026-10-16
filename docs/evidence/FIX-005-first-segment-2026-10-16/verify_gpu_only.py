"""Opt-in, single owned Qwen worker measurement; no browser or product service."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import runpy
import subprocess
import time
from pathlib import Path
from typing import Any

from siro.services.audio.tts import plan_speech, prepare_spoken_text

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def qwen_pids() -> list[int]:
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(arg.endswith(b"/qwen_tts_worker.py") for arg in args):
            found.append(int(entry.name))
    return sorted(found)


def hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("scripts/qwen_tts_worker.py", "src/siro/services/audio/tts.py")
    }


async def verify(output: Path) -> None:
    if qwen_pids():
        raise RuntimeError("existing Qwen worker; single owner gate is not satisfied")
    query = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=True,
    )
    if query.stdout.strip():
        raise RuntimeError("existing GPU compute owner; refusing another model")
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "result.json"
    if report_path.exists():
        raise FileExistsError("use a new synthetic output directory")
    fixture = runpy.run_path(str(ROOT / "docs/evidence/FIX-005-2026-10-07/verify_real_voice.py"))
    previous = runpy.run_path(str(HERE / "before/tts.py"))["plan_speech"]
    report: dict[str, Any] = {
        "status": "RUNNING",
        "scope": "single current worker; old/new planner workload comparison; no browser",
        "human_listening": "NOT_RUN",
        "source_hashes_start": hashes(),
        "jobs": [],
        "measurements": [],
        "limits": [
            "No speed SLO, statistical significance or naturalness acceptance claim",
            "Cold includes worker load; cache hit is separate from warm uncached generation",
            "Both workloads use the same current voice/model/SDPA/generation settings",
            "Synthetic texts differ between groups; random sampling is unchanged",
        ],
    }

    def save() -> None:
        pending = report_path.with_suffix(".pending.json")
        pending.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        pending.replace(report_path)

    import tempfile

    with tempfile.TemporaryDirectory(prefix="siro-first24-gpu-cache-") as temporary:
        report["cache_directory"] = temporary

        class CUDAOnlyQwen(fixture["ObservedQwen"]):
            def _accept_ready(self, response: dict[str, object]) -> None:
                super()._accept_ready(response)
                if response.get("device") != "cuda:0":
                    raise RuntimeError("expected CUDA; refusing CPU inference")

        speech = CUDAOnlyQwen(Path(temporary), output)
        speech.save_callback = save
        report["jobs"] = speech.jobs
        save()
        try:
            samples = [
                ("cold-short", fixture["SHORT"], False),
                ("cache-hit", fixture["SHORT"], True),
            ]
            stories = [
                fixture["STORY"],
                fixture["STORY"]
                .replace("小雨", "小晴")
                .replace("爺爺", "奶奶")
                .replace("花園", "公園"),
            ]
            for index, story in enumerate(stories):
                old, current = previous(story), plan_speech(story)
                assert old["spoken_text"] == current["spoken_text"]
                pair = [
                    (f"warm-baseline-{index + 1}", old["segments"][0], False),
                    (f"warm-first24-{index + 1}", current["segments"][0], False),
                ]
                samples.extend(pair if index == 0 else reversed(pair))
            for name, text, expected_hit in samples:
                speech.case = name
                began = time.monotonic()
                await speech.render(text)
                job = speech.jobs[-1]
                metadata = fixture["response_metadata"](job)
                assert metadata["cache_hit"] is expected_hit
                completion = metadata["completion"]
                assert completion["eos_observed"] and not completion["cap_reached"]
                assert len(speech.processes) == 1
                process = speech.processes[0]
                assert process.returncode is None and qwen_pids() == [process.pid]
                measurement = {
                    "case": name,
                    "plan_characters": len(text),
                    "rendered_characters": len(prepare_spoken_text(text)),
                    "elapsed_seconds": round(time.monotonic() - began, 6),
                    "audio_duration_seconds": job["audio_duration_seconds"],
                    "real_time_factor": job["real_time_factor"],
                    "cache_hit": metadata["cache_hit"],
                    "completion": completion,
                    "owned_pid": process.pid,
                }
                report["measurements"].append(measurement)
                save()
                print(json.dumps(measurement), flush=True)
            report["checks_completed"] = True
        except BaseException as error:
            report["status"] = "FAILED_VERIFICATION"
            report["error_type"] = type(error).__name__
            raise
        finally:
            await speech.close()
            report["worker_pids"] = [process.pid for process in speech.processes]
            report["worker_returncodes"] = [process.returncode for process in speech.processes]
            report["owned_worker_reaped"] = all(
                process.returncode is not None for process in speech.processes
            )
            report["remaining_qwen_pids"] = qwen_pids()
            report["source_hashes_end"] = hashes()
            save()
    report["temporary_cache_removed"] = not Path(report["cache_directory"]).exists()
    report["source_unchanged"] = report["source_hashes_start"] == report["source_hashes_end"]
    report["status"] = (
        "FUNCTIONAL_MEASUREMENT_PASS"
        if report.get("checks_completed")
        and report["owned_worker_reaped"]
        and not report["remaining_qwen_pids"]
        and report["temporary_cache_removed"]
        and report["source_unchanged"]
        else "FAILED_VERIFICATION"
    )
    save()
    assert report["status"] == "FUNCTIONAL_MEASUREMENT_PASS"
    print(json.dumps({"status": report["status"], "output": str(output)}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.run_real:
        print("NOT_RUN: explicit --run-real and exclusive GPU ownership are required")
        return
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    asyncio.run(verify(args.output.resolve()))


if __name__ == "__main__":
    main()
