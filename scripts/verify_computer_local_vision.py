"""Evaluate local vision on synthetic screens, without desktop control or user data."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
from verify_computer_vision import CASES, SIZE, _observation, _png

from siro.services.computer_use.decision import DECISION_PROMPT, _history_text, parse_decision

MODEL = "gemma4:e4b"
OUT = Path("docs/verification/COMPUTER-USE/local-vision-schema-20261030.json")
SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["act", "done", "stuck", "ask", "wait"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "seen": {"type": "string"},
        "reason": {"type": "string"},
        "expect": {"type": "string"},
        "evidence": {"type": "string"},
        "action": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["click", "move", "key", "scroll", "type"]},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {"type": "string"},
                "key": {"type": "string"},
                "text": {"type": "string"},
                "amount": {"type": "integer"},
                "hold_ms": {"type": "integer"},
            },
            "required": ["kind"],
        },
    },
    "required": ["kind", "confidence"],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-mode", action="store_true", help="Use unconstrained JSON mode")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    rows: list[dict[str, object]] = []
    with httpx.Client(timeout=120) as client:
        for name, goal, scene, history, check in CASES:
            image = _png(scene)
            observation = _observation(image)
            prompt = DECISION_PROMPT.format(
                image="attached image",
                goal=goal,
                title=observation.window_title,
                process=observation.process,
                rect=(0, 0, *SIZE),
                size=SIZE,
                history=_history_text(history),
            ).replace(
                "Read the screenshot file attached image (your only tool is Read)",
                "Examine the attached image",
            )
            start = time.monotonic()
            row: dict[str, object] = {"case": name}
            try:
                response = client.post(
                    "http://127.0.0.1:11434/api/chat",
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt, "images": [image]}],
                        "stream": False,
                        "think": False,
                        "format": "json" if args.json_mode else SCHEMA,
                        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 512},
                    },
                )
                response.raise_for_status()
                body = response.json()
                answer = body["message"]["content"]
                row["answer"] = answer
                result = parse_decision(answer)
                original_pass = bool(check(result))
                # The same START button has already failed twice. A new coordinate is not
                # proof of a different action, and the image contains no alternative control.
                semantic_pass = original_pass
                if name == "no_blind_repeat":
                    semantic_pass = result.kind in {"ask", "stuck"} or (
                        result.kind == "act" and result.confidence < 0.6
                    )
                row.update(
                    kind=result.kind,
                    action=None
                    if result.action is None
                    else {
                        "kind": result.action.kind,
                        "x": result.action.x,
                        "y": result.action.y,
                        "key": result.action.key,
                    },
                    confidence=result.confidence,
                    reason=result.reason,
                    evidence=result.evidence,
                    passed=original_pass,
                    semantic_passed=semantic_pass,
                    prompt_tokens=body.get("prompt_eval_count"),
                    output_tokens=body.get("eval_count"),
                    done_reason=body.get("done_reason"),
                )
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                row.update(error=f"{type(error).__name__}: {error}", passed=False)
            row["seconds"] = round(time.monotonic() - start, 3)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {"model": MODEL, "format": "json" if args.json_mode else "schema", "cases": rows},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
