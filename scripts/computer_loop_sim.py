"""Opt-in, device-free full-loop contract simulation; NOT a game emulator or VLM benchmark.

Only an in-memory queue consumes the real ComputerBridge commands. No HTTP server,
input helper, desktop API or device adapter exists here. Oracle/JSON decisions are
scripted, not model inference. Original frames stay private; map/animation synthetic.
Next-turn reuses a stored frame, not a recorded transition.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
import statistics
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from PIL import Image, ImageDraw

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import parse_decision
from siro.services.computer_use.interface import Decision, StepRecord, VerifyResult
from siro.services.computer_use.loop import DecisionLoop
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import ControlGate, InputAction

SIM_FLAG = "SIRO_COMPUTER_SIM_ENABLED"
MODES = (
    "oracle",
    "scripted-json",
    "bad-once",
    "bad-soft-once",
    "click-noop",
    "persistent-animation",
    "delayed-unconfirmed",
    "bad-always",
    "bad-soft-always",
    "wrong",
    "animated-noop",
    "transient-animation",
    "delayed-transition",
    "liar-done",
    "verifier-timeout",
    "gate-off",
    "wrong-process",
    "no-whitelist",
    "secret",
    "emergency",
)
ENV = {
    "SIRO_COMPUTER_ALLOWED_PROCESSES": "slaythespire2.exe",
    "SIRO_COMPUTER_NORMALIZE_PROCESS_NAMES": "1",
    "SIRO_COMPUTER_STRICT_BACKEND": "1",
    "SIRO_COMPUTER_CLAUDE_VERIFY": "1",
    "SIRO_COMPUTER_SCREEN_GUARD": "1",
    "SIRO_COMPUTER_AUTONOMOUS": "0",
    "SIRO_COMPUTER_ENDLESS": "0",
    "SIRO_COMPUTER_MAX_STEPS": "10",
    "SIRO_COMPUTER_MAX_SECONDS": "120",
    "SIRO_COMPUTER_MAX_SEGMENTS": "1",
    "SIRO_COMPUTER_ACTION_BATCH": "0",
    "SIRO_COMPUTER_CONTROL_ENABLED": "0",
    "SIRO_COMPUTER_PLAYBOOK": "0",
    "SIRO_COMPUTER_OCR_NUMBERED": "0",
    "SIRO_COMPUTER_REGION_NUMBERED": "0",
    "SIRO_COMPUTER_DUMP_FRAMES": "",
    "SIRO_COMPUTER_TRACE_REPLIES": "0",
    "SIRO_COMPUTER_COORD_CALIB": "",
}


@dataclass(frozen=True)
class State:
    name: str
    scene: str
    image: bytes
    box: tuple[int, int, int, int] | None
    label_source: str

    @property
    def size(self) -> tuple[int, int]:
        with Image.open(io.BytesIO(self.image)) as image:
            return image.size


def synthetic(name: str, box: tuple[int, int, int, int] | None) -> bytes:
    image = Image.new("RGB", (1024, 576), (20, 30, 40))
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), "SYNTHETIC LOOP CONTRACT: " + name, fill="white")
    if box:
        draw.rectangle(box, outline="white", width=2)
        draw.text((box[0] + 5, box[1] + 5), "reachable node", fill="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def load_states(root: Path) -> list[State]:
    path = root / "docs/verification/COMPUTER-USE/stage2/cases.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    frame_root = (path.parent / manifest["image_root"]).resolve()
    cases = {case["id"]: case for case in manifest["cases"]}

    def saved(ident: str, name: str) -> State:
        case = cases[ident]
        data = (frame_root / case["image"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != case["sha256"] or case["uncertain"]:
            raise ValueError("untrusted/mismatched frame label: " + ident)
        # Top-left letterbox only; no coordinate shift/scaling of manual target labels.
        image = Image.open(io.BytesIO(data)).convert("RGB")
        if image.width > 1024 or image.height > 576:
            raise ValueError("fixture too large for common canvas")
        canvas = Image.new("RGB", (1024, 576))
        canvas.paste(image, (0, 0))
        output = io.BytesIO()
        canvas.save(output, format="PNG")
        return State(
            name,
            case["scenario"],
            output.getvalue(),
            tuple(case["expect"]["click_boxes"][0]),
            "existing manual_visual_review, top-left1024x576 letterbox: " + ident,
        )

    box = (400, 250, 450, 300)
    return [
        saved("menu-continue", "menu"),
        State("map", "map", synthetic("map", box), box, "synthetic fixture, not saved STS2"),
        saved("combat-right-defend", "combat"),
        saved("zero-energy-end-turn", "end-turn"),
        State(
            "next-turn",
            "combat",
            cases_image(cases, frame_root, "combat-end-turn"),
            None,
            "existing frame reused as scripted next-turn checkpoint; NOT real transition",
        ),
    ]


def cases_image(cases: dict[str, Any], root: Path, ident: str) -> bytes:
    case = cases[ident]
    data = (root / case["image"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != case["sha256"]:
        raise ValueError("frame hash mismatch")
    image = Image.open(io.BytesIO(data)).convert("RGB")
    canvas = Image.new("RGB", (1024, 576))
    canvas.paste(image, (0, 0))
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


class Desktop:
    """The ONLY executor, incapable of sending input outside an in-memory state machine."""

    def __init__(self, states: list[State], bridge: ComputerBridge, mode: str) -> None:
        self.states, self.bridge, self.mode = states, bridge, mode
        self.index = self.decisions = self.observes = 0
        self.events: list[dict[str, Any]] = []
        self.proofs: list[dict[str, Any]] = []
        self.pending = 0
        self.animate = False
        self.transient = 0
        self.last_progress_step = 0

    @property
    def current(self) -> State:
        return self.states[self.index]

    def pixels(self) -> bytes:
        data = self.current.image
        if self.animate or self.transient:
            image = Image.open(io.BytesIO(data)).convert("RGB")
            image.putpixel((0, 0), (255, 0, 255))
            output = io.BytesIO()
            image.save(output, format="PNG")
            data = output.getvalue()
        if self.transient:
            self.transient -= 1
        return data

    async def serve(self) -> None:
        while True:
            command = await self.bridge.next_command(wait=1)
            if command is None:
                continue
            op = command["op"]
            data = None
            if op == "observe":
                self.observes += 1
                if self.pending:
                    self.pending -= 1
                    if not self.pending:
                        self.index += 1
                        self.last_progress_step = self.decisions
                pixels = self.pixels()
                data = {
                    "title": "Slay the Spire 2",
                    "process": "slaythespire2.exe",
                    "screen": [1920, 1080],
                    "rect": [0, 0, 1920, 1040],
                    "image_rect": [0, 0, 1920, 1040],
                    "image_size": self.current.size,
                    "image_png_b64": base64.b64encode(pixels).decode(),
                    "fingerprint": hashlib.sha256(pixels).hexdigest(),
                    "window_id": "123",
                    "pid": 456,
                    "focus_is_secret": self.mode == "secret",
                }
                if self.mode == "wrong-process":
                    data["process"] = "other.exe"
            elif op == "input":
                if self.mode == "emergency":
                    self.bridge.stop()
                    continue  # pending command failed by stop(); nothing applied
                action = command["payload"]
                before = self.index
                w, h = self.current.size
                x, y = action.get("x", -1) * w / 1920, action.get("y", -1) * h / 1040
                box = self.current.box
                hit = bool(
                    action["kind"] == "click"
                    and box
                    and box[0] <= x <= box[2]
                    and box[1] <= y <= box[3]
                )
                if hit and self.mode != "click-noop":
                    if (
                        self.mode in {"delayed-transition", "delayed-unconfirmed"}
                        and self.index == 0
                    ):
                        self.pending = 2
                    else:
                        self.index += 1
                        self.last_progress_step = self.decisions
                if self.mode == "animated-noop":
                    self.animate = not self.animate
                self.events.append(
                    {
                        "before": before,
                        "after": self.index,
                        "hit": hit,
                        "x": action.get("x"),
                        "y": action.get("y"),
                    }
                )
            else:
                raise AssertionError("Unexpected executor op (real execution unavailable): " + op)
            self.bridge.submit_result(command["id"], True, data=data)


class ReplayDecider:
    def __init__(self, desktop: Desktop) -> None:
        self.desktop = desktop

    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        d = self.desktop
        d.decisions += 1
        if d.mode in {"bad-once", "bad-always"} and (d.decisions == 1 or d.mode == "bad-always"):
            return parse_decision("invalid model output")
        if d.mode == "bad-soft-always" or (d.mode == "bad-soft-once" and d.decisions == 1):
            return Decision(
                "wait",
                confidence=0.2,
                seen="model output invalid; re-observe",
                uncertainty="bad_model_output",
            )
        if d.mode == "liar-done" or d.index == len(d.states) - 1:
            return Decision(
                "done",
                confidence=0.99,
                evidence="state:0" if d.mode == "liar-done" else "state:4",
                seen="checkpoint",
            )
        if d.pending:
            return Decision("wait", confidence=0.9, expect="state:1", seen="transition pending")
        state = d.current
        assert state.box is not None
        x = (state.box[0] + state.box[2]) // 2
        y = (state.box[1] + state.box[3]) // 2
        if d.mode in {"wrong", "animated-noop"}:
            x, y = (40, 400, 850, 700)[(d.decisions - 1) % 4], 75
        if d.mode == "transient-animation" and d.decisions == 1:
            d.transient = 1
        if d.mode == "persistent-animation":
            d.animate = True
        choice = Decision(
            "act",
            InputAction("click", x=x, y=y),
            "state:" + str(d.index + 1),
            confidence=0.99,
            seen=state.name,
            scene=state.scene,
        )
        if d.mode == "scripted-json":
            return parse_decision(json.dumps(asdict(choice)))
        return choice

    async def verify(self, expect: str, before_seen: str, observation: Observation) -> VerifyResult:
        if self.desktop.mode == "verifier-timeout":
            await asyncio.sleep(10)  # caught by external bound on baseline; never an OS action
        truth = (
            self.desktop.index == 4
            if expect.startswith("Goal achieved:")
            else expect == "state:" + str(self.desktop.index)
        )
        self.desktop.proofs.append({"expect": expect, "index": self.desktop.index, "truth": truth})
        return VerifyResult(
            "unknown"
            if self.desktop.mode == "delayed-unconfirmed"
            else "confirmed"
            if truth
            else "denied",
            "simulated state proof",
            self.desktop.current.name,
            self.desktop.current.scene,
        )


async def simulate(
    root: Path, mode: str, *, fixed_flags: bool = True, fast: bool = False
) -> dict[str, Any]:
    if os.environ.get(SIM_FLAG) != "1":
        raise ValueError("simulation is default OFF; set " + SIM_FLAG + "=1")
    if mode not in MODES:
        raise ValueError("unknown simulation mode")
    values = dict(ENV)
    if fixed_flags:
        values.update(
            SIRO_COMPUTER_VERIFY_DONE="1",
            SIRO_COMPUTER_BOUNDED_VERIFY="1",
            SIRO_COMPUTER_VERIFY_DELAYED_PROGRESS="1",
        )
    else:
        values.update(
            SIRO_COMPUTER_VERIFY_DONE="0",
            SIRO_COMPUTER_BOUNDED_VERIFY="0",
            SIRO_COMPUTER_VERIFY_DELAYED_PROGRESS="0",
        )
    if mode == "no-whitelist":
        values["SIRO_COMPUTER_ALLOWED_PROCESSES"] = ""
    with patch.dict(os.environ, values):
        states = load_states(root)
        gate = ControlGate(enabled=mode != "gate-off")  # simulated owner enables fake tray
        bridge = ComputerBridge(gate)
        desktop = Desktop(states, bridge, mode)
        loop = DecisionLoop(
            bridge,
            ReplayDecider(desktop),
            focus=False,
            max_seconds=0.15 if mode in {"verifier-timeout", "persistent-animation"} else 120,
            settle=0 if fast or mode == "verifier-timeout" else 0.4,
            wait=0 if fast else 1,
        )
        worker = asyncio.create_task(desktop.serve())
        await asyncio.sleep(0)  # executor parks on real bridge queue
        start = time.perf_counter()
        try:
            async with asyncio.timeout(0.6 if mode == "verifier-timeout" else 45):
                report = await loop.run("Operate slaythespire2 until next-turn checkpoint state:4")
            state, reason, steps = report.state, report.reason, [asdict(s) for s in report.steps]
        except TimeoutError:
            state, reason, steps = "failed", "harness_timeout", [asdict(s) for s in loop.live]
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        elapsed = time.perf_counter() - start
        positive = mode in {
            "oracle",
            "scripted-json",
            "bad-once",
            "bad-soft-once",
            "transient-animation",
            "delayed-transition",
        }
        false_progress = int(state == "done" and desktop.index != len(states) - 1)
        false_effective = sum(
            s["outcome"] == "effective"
            and not any(p["expect"] == s["expect"] and p["truth"] for p in desktop.proofs)
            for s in steps
        )
        expected_stop = {
            "wrong": {"stuck_no_progress", "too_many_invalid_decisions"},
            "click-noop": {"stuck_no_progress", "too_many_invalid_decisions"},
            "persistent-animation": {"time_limit"},
            "delayed-unconfirmed": {"too_many_invalid_decisions"},
            "animated-noop": {"stuck_no_progress"},
            "bad-always": {"decider_error:not_json"},
            "bad-soft-always": {"stuck_waiting"},
            "gate-off": {"control_disabled"},
            "wrong-process": {"window_not_allowed"},
            "no-whitelist": {"no_allowed_processes"},
            "secret": {"secret_field_focused"},
            "emergency": {"emergency_stop", "denied:emergency_stop"},
            "liar-done": {"done_unconfirmed"},
            "verifier-timeout": {"time_limit"},
        }
        passed = (
            (state == "done" and desktop.index == 4) if positive else reason in expected_stop[mode]
        )
        passed = passed and not false_progress and not false_effective
        count = len(desktop.events)
        return {
            "mode": mode,
            "pass": passed,
            "state": state,
            "reason": reason,
            "advances": desktop.index,
            "decisions": desktop.decisions,
            "steps_to_full_progress": desktop.last_progress_step if desktop.index == 4 else None,
            "clicks": count,
            "hits": sum(e["hit"] for e in desktop.events),
            "hit_rate": sum(e["hit"] for e in desktop.events) / count if count else None,
            "seconds": elapsed,
            "seconds_per_decision": elapsed / desktop.decisions if desktop.decisions else None,
            "false_stuck": int(positive and state != "done"),
            "false_progress": false_progress,
            "false_effective": false_effective,
            "observations": desktop.observes,
            "events": desktop.events,
            "proofs": desktop.proofs,
            "steps": steps,
        }


def timing_mean(rows: list[dict[str, Any]], mode: str) -> float | None:
    measured = [
        r["seconds_per_decision"]
        for r in rows
        if r["mode"] == mode and r["seconds_per_decision"] is not None
    ]
    return statistics.mean(measured) if measured else None


async def evaluate(
    root: Path, repeats: int, modes: list[str], fixed_flags: bool, fast: bool = False
) -> dict[str, Any]:
    rows = []
    for mode in modes:
        for run in range(repeats):
            row = await simulate(root, mode, fixed_flags=fixed_flags, fast=fast)
            row["run"] = run + 1
            rows.append(row)
            print(mode, run + 1, row["pass"], row["reason"], flush=True)
    return {
        "kind": "simulated_contract_NOT_real_game_or_VLM",
        "fixed_flags": fixed_flags,
        "fast_test_timings": fast,
        "states": [
            {
                "name": s.name,
                "source": s.label_source,
                "sha256": hashlib.sha256(s.image).hexdigest(),
                "box": s.box,
            }
            for s in load_states(root)
        ],
        "rows": rows,
        "summary": {
            m: {
                "passes": sum(r["pass"] for r in rows if r["mode"] == m),
                "runs": repeats,
                "mean_seconds_per_decision": timing_mean(rows, m),
            }
            for m in modes
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--mode", choices=MODES, action="append")
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("repeats must be1..10")
    result = asyncio.run(
        evaluate(args.root, args.repeats, args.mode or list(MODES), not args.baseline)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    return 0 if all(r["pass"] for r in result["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
