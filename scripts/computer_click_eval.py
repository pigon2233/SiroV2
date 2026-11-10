"""Fixed screenshot click evaluation. No capture, bridge, loop, verification or input execution.

Opt in with SIRO_COMPUTER_BENCH_ENABLED=1. Cloud backends also require the existing
SIRO_COMPUTER_CLOUD_SCREEN=1; this script never enables it. --validate-only is local-only.
Measures one production _decide_once call (no automatic retries), including prompt/grid,
provider request and parsing. Ollama context is explicitly 8192 for this offline benchmark.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from PIL import Image

from siro.services.computer_use.decision import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_OLLAMA_MODEL,
    ClaudeVisionDecider,
    Decision,
    GroqVisionDecider,
    OllamaVisionDecider,
    cloud_screen_allowed,
)
from siro.services.computer_use.numbered import NUMBERED_ENV, NumberedTextDecider, NumberSelector
from siro.services.computer_use.ocr import WindowsTextReader
from siro.services.computer_use.perception import Observation
from siro.services.tools.claude import claude_binary, claude_model

ENABLED = "SIRO_COMPUTER_BENCH_ENABLED"
BACKENDS = ("claude", "ollama", "groq")
Case = dict[str, Any]
Cases = list[tuple[Case, Observation]]
Result = dict[str, Any]


def load_cases(path: Path, image_root: Path | None = None) -> tuple[dict[str, Any], Cases]:
    """Validate all labels and frozen image bytes before any model/network request."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("version") != 1 or not spec.get("cases"):
        raise ValueError("expected nonempty version=1 dataset")
    root = image_root or path.parent / spec.get("image_root", ".")
    root = root.resolve()
    cases: Cases = []
    ids: set[str] = set()
    for case in spec["cases"]:
        ident = case["id"]
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("empty/duplicate case id")
        ids.add(ident)
        if not case.get("goal") or not case.get("scenario") or not case.get("label_source"):
            raise ValueError(f"{ident}: goal/scenario/label_source required")
        if type(case.get("uncertain")) is not bool:
            raise ValueError(f"{ident}: explicit uncertain boolean required")
        image_path = (root / case["image"]).resolve()
        if not image_path.is_relative_to(root):
            raise ValueError(f"{ident}: image escapes image root")
        data = image_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != case.get("sha256"):
            raise ValueError(f"{ident}: image sha256 mismatch")
        with Image.open(image_path) as image:
            image.load()
            size = image.size
        if list(size) != case.get("image_size"):
            raise ValueError(f"{ident}: image_size mismatch")
        boxes = case.get("expect", {}).get("click_boxes")
        if not isinstance(boxes, list) or not boxes:
            raise ValueError(f"{ident}: nonempty click_boxes required")
        for box in boxes:
            if (
                not isinstance(box, list)
                or len(box) != 4
                or any(type(v) is not int for v in box)
                or not (0 <= box[0] <= box[2] < size[0])
                or not (0 <= box[1] <= box[3] < size[1])
            ):
                raise ValueError(f"{ident}: invalid/out-of-bounds click box")
        obs = Observation(
            seq=1,
            taken_at=0.0,
            window_title="",
            process=case.get("process", "game.exe"),
            window_rect=(0, 0, *size),
            screen=size,
            fingerprint=case["sha256"],
            image_png_b64=base64.b64encode(data).decode("ascii"),
            image_size=size,
            image_rect=(0, 0, *size),
        )
        cases.append((case, obs))
    return spec, cases


def score_click(decision: Decision, boxes: list[list[int]]) -> tuple[bool, str]:
    action = decision.action
    if decision.kind != "act" or action is None:
        return False, f"decision:{decision.kind}"
    if action.kind != "click" or action.button != "left":
        return False, f"action:{action.kind}/{action.button}"
    if type(action.x) is not int or type(action.y) is not int:
        return False, "missing_coordinates"
    hit = any(x0 <= action.x <= x1 and y0 <= action.y <= y1 for x0, y0, x1, y1 in boxes)
    return hit, "hit" if hit else "miss"


class Context8192Transport(httpx.AsyncBaseTransport):
    """Benchmark-only override; leave the production decider and its prompts untouched."""

    def __init__(
        self, inner: httpx.AsyncBaseTransport | None = None, *, env: dict[str, str] | None = None
    ) -> None:
        self.disable_draft = (env or {}).get("SIRO_COMPUTER_BENCH_NO_DRAFT", "0") == "1"
        value = (env or {}).get("SIRO_COMPUTER_BENCH_GPU_LAYERS")
        self.gpu_layers = None if value is None else int(value)
        if self.gpu_layers is not None and not 0 <= self.gpu_layers <= 256:
            raise ValueError("benchmark GPU layers must be between 0 and 256")
        self.inner = inner if inner is not None else httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/chat":
            body = json.loads(request.content)
            body.setdefault("options", {})["num_ctx"] = 8192
            if self.disable_draft:
                body["options"]["draft_num_predict"] = 0
            if self.gpu_layers is not None:
                body["options"]["num_gpu"] = self.gpu_layers
            request = httpx.Request(
                request.method,
                request.url,
                headers={k: v for k, v in request.headers.items() if k != "content-length"},
                content=json.dumps(body).encode(),
                extensions=request.extensions,
            )
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self.inner.aclose()


def summarize(backend: str, model: str, rows: list[Result], total: int, reason: str = "") -> Result:
    returned = sum("decision" in row for row in rows)
    times = [row["seconds"] for row in rows]
    hits = sum(row["hit"] for row in rows)
    measured = bool(returned) and len(rows) == total
    return {
        "backend": backend,
        "model": model,
        "status": "measured" if measured else "not_measured",
        "reason": reason or ("no_valid_decision" if rows and not returned else ""),
        "eligible_cases": total,
        "attempted": len(rows),
        "returned": returned,
        "errors": len(rows) - returned,
        "hits": hits if measured else None,
        "hit_rate": hits / total if measured else None,
        "mean_seconds": statistics.mean(times) if measured else None,
        "median_seconds": statistics.median(times) if measured else None,
        "rows": rows,
    }


async def measure(
    backend: str,
    cases: Cases,
    env: dict[str, str],
    timeout: float,
    *,
    mode: str = "pixel",
    ocr_cache: Path | None = None,
) -> Result:
    model = {
        "claude": env.get("SIRO_CLAUDE_MODEL") or claude_model(),
        "ollama": env.get("SIRO_COMPUTER_OLLAMA_MODEL")
        or env.get("SIRO_OLLAMA_MODEL")
        or DEFAULT_OLLAMA_MODEL,
        "groq": env.get("SIRO_COMPUTER_GROQ_MODEL") or DEFAULT_GROQ_MODEL,
    }[backend]
    eligible = [(case, obs) for case, obs in cases if not case["uncertain"]]
    total = len(eligible)

    def unavailable(reason: str) -> Result:
        return summarize(backend, model, [], total, reason)

    if not total:
        return unavailable("no_certain_labels")
    if backend != "ollama" and not cloud_screen_allowed(env):
        return unavailable("cloud_screen_not_allowed")
    if backend == "groq" and not env.get("SIRO_OPENAI_API_KEY"):
        return unavailable("groq_no_key")
    if backend == "claude" and claude_binary() is None:
        return unavailable("claude_cli_missing")
    async with httpx.AsyncClient(
        transport=Context8192Transport(env=env), timeout=timeout
    ) as client:
        decider: OllamaVisionDecider | ClaudeVisionDecider | NumberedTextDecider
        if backend == "ollama":
            host = (env.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
            if "://" not in host:
                host = "http://" + host
            try:
                response = await client.get(host + "/api/tags", timeout=min(timeout, 15))
                response.raise_for_status()
                models = {m["name"] for m in response.json()["models"]}
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                return unavailable(f"ollama_preflight:{type(error).__name__}")
            if model not in models and model + ":latest" not in models:
                return unavailable("ollama_model_not_installed")
            decider = OllamaVisionDecider(model=model, env=env, timeout=timeout, client=client)
        elif backend == "groq":
            decider = GroqVisionDecider(model=model, env=env, timeout=timeout, client=client)
        else:
            decider = ClaudeVisionDecider(model=model, env=env, timeout=int(timeout))
        if mode == "numbered":
            decider = NumberedTextDecider(
                decider,
                WindowsTextReader(ocr_cache, cache_only=True),
                NumberSelector(backend, env, timeout=timeout, client=client),
            )
        rows: list[Result] = []
        for case, obs in eligible:
            started = time.perf_counter()
            row: dict[str, Any] = {
                "id": case["id"],
                "hit": False,
                "no_text_target": case.get("no_text_target", False),
            }
            try:
                # One shared production request/parser, not decide()'s hidden retries/fallback.
                async with asyncio.timeout(timeout):
                    decision = await decider._decide_once(case["goal"], [], obs)
                row["hit"], row["why"] = score_click(decision, case["expect"]["click_boxes"])
                action = decision.action
                row["decision"] = decision.kind
                row["action"] = (
                    None
                    if action is None
                    else {
                        "kind": action.kind,
                        "button": action.button,
                        "x": action.x,
                        "y": action.y,
                    }
                )
            except Exception as error:  # preserve per-case failure, never retry
                # Provider exceptions are codes; do not serialize arbitrary response bodies/secrets.
                row["why"] = type(error).__name__
                if type(error).__name__ in {"DecisionError", "CloudScreenNotAllowed"}:
                    row["why"] += ":" + str(error)[:100]
            row["seconds"] = time.perf_counter() - started
            if isinstance(decider, NumberedTextDecider) and decider.last_frame is not None:
                frame = decider.last_frame
                row["ocr"] = {
                    "sha256": frame.sha256,
                    "blocks": len(frame.blocks),
                    "cached": frame.cached,
                    "cold_seconds": frame.cold_seconds,
                    "target_available": any(
                        x0 <= block.center[0] <= x1 and y0 <= block.center[1] <= y1
                        for block in frame.blocks
                        for x0, y0, x1, y1 in case["expect"]["click_boxes"]
                    ),
                }
            rows.append(row)
            print(f"{backend} {case['id']}: {row['why']} {row['seconds']:.3f}s", flush=True)
            if env.get("SIRO_COMPUTER_BENCH_FAIL_FAST", "0") == "1" and (
                any(code in row["why"].lower() for code in ("timeout", "connect", "http_5"))
            ):
                break  # explicit diagnostic option; never issue more requests to unhealthy service
            if row["why"] in {"DecisionError:claude_auth", "DecisionError:groq_auth"}:
                break  # missing authorization is final, never retry through another route
        result = summarize(backend, model, rows, total)
        result["strata"] = {}
        for name, no_text in (("text_target", False), ("no_text_target", True)):
            subset = [row for row in rows if row["no_text_target"] == no_text]
            count = sum(case.get("no_text_target", False) == no_text for case, _ in eligible)
            stratum = summarize(backend, model, subset, count)
            result["strata"][name] = {
                key: stratum[key]
                for key in (
                    "eligible_cases",
                    "attempted",
                    "hits",
                    "hit_rate",
                    "mean_seconds",
                    "median_seconds",
                )
            }
        if mode == "numbered":
            result["ocr_covered_cases"] = sum(
                row.get("ocr", {}).get("target_available", False) for row in rows
            )
        return result


async def evaluate(
    path: Path,
    backends: list[str],
    env: dict[str, str],
    *,
    timeout: float = 90,
    image_root: Path | None = None,
    mode: str = "pixel",
    ocr_cache: Path | None = None,
) -> Result:
    if env.get(ENABLED, "0") != "1":
        raise ValueError(f"offline model evaluation is off; set {ENABLED}=1")
    if mode not in {"pixel", "numbered"}:
        raise ValueError("unknown evaluation mode")
    if mode == "numbered" and (env.get(NUMBERED_ENV, "0") != "1" or ocr_cache is None):
        raise ValueError(f"numbered mode requires {NUMBERED_ENV}=1 and --ocr-cache")
    spec, cases = load_cases(path, image_root)
    results = [
        await measure(name, cases, env, timeout, mode=mode, ocr_cache=ocr_cache)
        for name in backends
    ]
    return {
        "dataset_id": spec["dataset_id"],
        "mode": mode,
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "recorded_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "timing": (
            "single request including prompt/request/parsing; numbered mode uses frozen OCR cache; "
            "cold OCR seconds recorded separately, NOT included in cached latency; "
            "no retry, capture, verify, settle or input; error attempts included when measured"
        ),
        "ollama_num_ctx": 8192,
        "ollama_no_draft": env.get("SIRO_COMPUTER_BENCH_NO_DRAFT", "0") == "1",
        "ollama_gpu_layers": env.get("SIRO_COMPUTER_BENCH_GPU_LAYERS"),
        "coord_grid": env.get("SIRO_COMPUTER_COORD_GRID", "1"),
        "total_cases": len(cases),
        "unique_frames": len({case["sha256"] for case, _ in cases}),
        "no_text_targets": sum(case.get("no_text_target", False) for case, _ in cases),
        "excluded_uncertain": [case["id"] for case, _ in cases if case["uncertain"]],
        "results": results,
    }


async def prepare_ocr(path: Path, cache: Path, image_root: Path | None = None) -> Result:
    """Only Windows OCR on already-saved bytes; no model, capture or input."""
    _, cases = load_cases(path, image_root)
    reader = WindowsTextReader(cache)
    frames: dict[str, Any] = {}
    for case, obs in cases:
        if case["sha256"] not in frames:
            frame = await reader.read(obs)
            frames[frame.sha256] = {
                "blocks": len(frame.blocks),
                "cold_seconds": frame.cold_seconds,
                "cached": frame.cached,
            }
    return {"unique_frames": len(frames), "frames": frames}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--backend", choices=[*BACKENDS, "all"], default="ollama")
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--mode", choices=["pixel", "numbered"], default="pixel")
    parser.add_argument("--ocr-cache", type=Path)
    parser.add_argument(
        "--prepare-ocr", action="store_true", help="only freeze Windows OCR per SHA256"
    )
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be between 1 and 300 seconds")
    if args.validate_only:
        spec, cases = load_cases(args.cases, args.image_root)
        print(f"{spec['dataset_id']}: {len(cases)} frozen screenshots validated; no model called")
        return 0
    if args.prepare_ocr:
        if args.ocr_cache is None:
            parser.error("--prepare-ocr requires --ocr-cache")
        prepared = asyncio.run(prepare_ocr(args.cases, args.ocr_cache, args.image_root))
        text = json.dumps(prepared, indent=2) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        print(text)
        return 0
    backends = list(BACKENDS) if args.backend == "all" else [args.backend]
    result = asyncio.run(
        evaluate(
            args.cases,
            backends,
            dict(os.environ),
            timeout=args.timeout,
            image_root=args.image_root,
            mode=args.mode,
            ocr_cache=args.ocr_cache,
        )
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if all(r["status"] == "measured" for r in result["results"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
