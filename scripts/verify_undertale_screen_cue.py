"""Synthetic-only evaluation of a fast, local title-prompt detector.

This script does not capture a desktop, observe a real game or produce input events.
The cases are synthetic text layouts, not screenshots or assets from Undertale.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import random
import re
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

MODEL = "gemma4:e4b"
OUTPUT = Path("docs/verification/COMPUTER-USE/undertale-fast-cue-20261030.json")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
PROMPT = (
    "Look only at the image. Does it show a title screen for UNDERTALE with an instruction "
    "to PRESS Z OR ENTER to begin? Answer yes only for that title prompt. A loading screen, "
    "game dialogue, a save menu, a reset choice, or an instruction for different keys is no. "
    'Do not guess if the text is unclear. Respond with JSON: {"answer": "yes" or "no"}.'
)
SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}},
    "required": ["answer"],
}
TRANSCRIPT_PROMPT = (
    "Read the text visible near the top and near the bottom of this image. "
    "Transcribe each exactly, without adding words or guessing; use empty strings when blank. "
    'Return JSON with fields "heading" and "instruction".'
)
TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {"heading": {"type": "string"}, "instruction": {"type": "string"}},
    "required": ["heading", "instruction"],
}
MIDDLE_PROMPT = (
    "Read all text visible near the top, middle, and bottom of this image. "
    "Transcribe each exactly, without adding words or guessing; use empty strings when blank. "
    'Return JSON with fields "heading", "middle", and "instruction".'
)
MIDDLE_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string"} for key in ("heading", "middle", "instruction")},
    "required": ["heading", "middle", "instruction"],
}


def is_title_prompt(heading: str, instruction: str, middle: str = "") -> bool:
    def normal(text: str) -> str:
        return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()

    return (
        normal(heading) == "UNDERTALE"
        and normal(instruction) == "PRESS Z OR ENTER"
        and not middle.strip()
    )


# Manually fixed ground truth. These are deliberately simple, not evidence about the real game.
CASES = [
    ("title_large", "UNDERTALE", "[PRESS Z OR ENTER]", 38, 22, True),
    ("title_small", "UNDERTALE", "PRESS Z OR ENTER", 27, 16, True),
    ("title_mixed_case", "Undertale", "Press Z or Enter", 33, 20, True),
    ("different_keys", "UNDERTALE", "PRESS X OR ESC", 38, 22, False),
    ("reset", "UNDERTALE", "PRESS Z TO RESET", 38, 22, False),
    ("continue_menu", "UNDERTALE", "CONTINUE        RESET", 38, 22, False),
    ("loading", "UNDERTALE", "LOADING...", 38, 22, False),
    ("dialogue", "TORIEL", "PRESS Z OR ENTER TO CONTINUE", 33, 18, False),
    ("empty", "", "", 38, 22, False),
    ("save", "SAVE POINT", "SAVE                 RETURN", 33, 20, False),
]

HOLDOUT = [
    ("small_bracketed", "UNDERTALE", "[PRESS Z OR ENTER]", 24, 14, True),
    ("large_unbracketed", "UNDERTALE", "PRESS Z OR ENTER", 42, 26, True),
    ("lower_case", "undertale", "press z or enter", 30, 18, True),
    ("reset_instructions", "UNDERTALE", "PRESS Z OR ENTER TO RESET", 35, 18, False),
    ("dialogue_repeats_prompt", "TORIEL", "PRESS Z OR ENTER", 33, 18, False),
    ("misleading_heading", "SAVE UNDERTALE", "PRESS Z OR ENTER", 30, 18, False),
    ("wrong_order", "UNDERTALE", "PRESS ENTER OR Z", 33, 20, False),
    ("no_instruction", "UNDERTALE", "", 35, 18, False),
    ("title_typo", "UNDER TALE", "PRESS Z OR ENTER", 35, 18, False),
    ("press_to_continue", "UNDERTALE", "PRESS Z TO CONTINUE", 35, 18, False),
]

STRESS = [
    ("stress_noise", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, True),
    ("stress_blur", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, True),
    ("stress_dim", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, True),
    ("stress_offset", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, True),
    ("stress_tiny", "UNDERTALE", "PRESS Z OR ENTER", 18, 11, True),
    ("stress_noise_dialogue", "TORIEL", "PRESS Z OR ENTER", 35, 20, False),
    ("stress_blur_reset", "UNDERTALE", "PRESS Z OR ENTER TO RESET", 35, 18, False),
    ("stress_dim_save", "SAVE POINT", "PRESS Z OR ENTER", 35, 20, False),
    ("stress_offset_reset", "UNDERTALE", "PRESS Z TO RESET", 35, 20, False),
    ("stress_tiny_menu", "UNDERTALE", "CONTINUE    RESET", 18, 11, False),
]

OVERLAY = [
    ("plain_title", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, True),
    ("overlay_RESET", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
    ("overlay_SAVE", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
    ("overlay_DIALOGUE", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
    ("overlay_CONFIRM", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
]

OCR_HARD = [
    ("overlay_RESET_tiny", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
    ("overlay_RESET_dim", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
    ("overlay_ICON", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
    ("overlay_RESET_blur", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
    ("overlay_RESET_small", "UNDERTALE", "PRESS Z OR ENTER", 35, 20, False),
]


def render(title: str, text: str, title_size: int, text_size: int, variant: str = "") -> str:
    image = Image.new("RGB", (640, 360), "black")
    draw = ImageDraw.Draw(image)
    if "noise" in variant:
        rng = random.Random(54321)
        for _ in range(800):
            x, y = rng.randrange(640), rng.randrange(360)
            draw.point((x, y), fill=(80, 80, 80))
    title_font = ImageFont.truetype(FONT, title_size)
    text_font = ImageFont.truetype(FONT, text_size)
    color = (100, 100, 100) if "dim" in variant else "white"
    x = 400 if "offset" in variant else 320
    draw.text((x, 110), title, font=title_font, fill=color, anchor="mm")
    draw.text((x, 225), text, font=text_font, fill=color, anchor="mm")
    if variant.startswith("overlay_"):
        draw.rectangle((220, 145, 420, 195), fill=(120, 20, 20), outline="white", width=2)
        overlay_text = variant.removeprefix("overlay_").split("_")[0]
        overlay_size = (
            7 if variant.endswith("tiny") else 12 if variant.endswith("small") else text_size
        )
        overlay_font = ImageFont.truetype(FONT, overlay_size)
        overlay_color = (145, 22, 22) if variant.endswith("dim") else "white"
        draw.text(
            (320, 170),
            "" if overlay_text == "ICON" else overlay_text,
            font=overlay_font,
            fill=overlay_color,
            anchor="mm",
        )
        if overlay_text == "ICON":
            draw.ellipse((305, 155, 335, 185), fill="white")
    if "blur" in variant:
        image = image.filter(ImageFilter.GaussianBlur(1.2))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", action="store_true")
    parser.add_argument("--middle", action="store_true")
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--overlay", action="store_true")
    parser.add_argument("--ocr-hard", action="store_true")
    parser.add_argument("--fixtures", action="store_true", help="Emit synthetic PNGs as JSON")
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.middle and not args.transcript:
        parser.error("--middle requires --transcript")
    if args.fixtures:
        fixtures = []
        for name, title, text, title_size, text_size, expected in (
            HOLDOUT + STRESS + OVERLAY + OCR_HARD
        ):
            variant = name if name.startswith(("stress_", "overlay_")) else ""
            fixtures.append(
                {
                    "case": name,
                    "expected": expected,
                    "image": render(title, text, title_size, text_size, variant),
                }
            )
        print(json.dumps(fixtures))
        return
    rows: list[dict[str, object]] = []
    with httpx.Client(timeout=120) as client:
        cases = (
            OCR_HARD
            if args.ocr_hard
            else OVERLAY
            if args.overlay
            else STRESS
            if args.stress
            else HOLDOUT
            if args.holdout
            else CASES
        )
        for name, title, text, title_size, text_size, expected in cases:
            image = render(
                title,
                text,
                title_size,
                text_size,
                name if args.stress or args.overlay or args.ocr_hard else "",
            )
            row: dict[str, object] = {"case": name, "expected": "yes" if expected else "no"}
            start = time.monotonic()
            try:
                response = client.post(
                    "http://127.0.0.1:11434/api/chat",
                    json={
                        "model": MODEL,
                        "messages": [
                            {
                                "role": "user",
                                "content": MIDDLE_PROMPT
                                if args.middle
                                else TRANSCRIPT_PROMPT
                                if args.transcript
                                else PROMPT,
                                "images": [image],
                            }
                        ],
                        "stream": False,
                        "think": False,
                        "format": MIDDLE_SCHEMA
                        if args.middle
                        else TRANSCRIPT_SCHEMA
                        if args.transcript
                        else SCHEMA,
                        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 128},
                    },
                )
                response.raise_for_status()
                body = response.json()
                answer = body["message"]["content"]
                row["raw"] = answer
                parsed = json.loads(answer)
                if args.transcript:
                    heading, instruction = parsed.get("heading"), parsed.get("instruction")
                    if not isinstance(heading, str) or not isinstance(instruction, str):
                        raise ValueError("invalid transcription")
                    row.update(heading=heading, instruction=instruction)
                    middle = parsed.get("middle", "") if args.middle else ""
                    if not isinstance(middle, str):
                        raise ValueError("invalid middle transcription")
                    if args.middle:
                        row["middle"] = middle
                    actual = "yes" if is_title_prompt(heading, instruction, middle) else "no"
                else:
                    actual = parsed.get("answer")
                if actual not in {"yes", "no"} or body.get("done_reason") != "stop":
                    raise ValueError("invalid or incomplete answer")
                row.update(actual=actual, passed=(actual == row["expected"]))
                row["done_reason"] = body.get("done_reason")
                row["prompt_tokens"] = body.get("prompt_eval_count")
                row["output_tokens"] = body.get("eval_count")
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                row.update(error=f"{type(error).__name__}: {error}", passed=False)
            row["seconds"] = round(time.monotonic() - start, 3)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "model": MODEL,
                "method": "middle" if args.middle else "transcript" if args.transcript else "cue",
                "dataset": "ocr-hard"
                if args.ocr_hard
                else "overlay"
                if args.overlay
                else "stress"
                if args.stress
                else "holdout"
                if args.holdout
                else "development",
                "cases": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
