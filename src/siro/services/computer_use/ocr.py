"""Local Windows OCR on an already-sanitized frame; optional immutable SHA256 cache."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageOps

from siro.services.computer_use.decision import DecisionError
from siro.services.computer_use.perception import Observation

PIPELINE_VERSION = 3


@dataclass(frozen=True, slots=True)
class TextBlock:
    id: int
    text: str
    box: tuple[int, int, int, int]
    language: str = ""

    @property
    def center(self) -> tuple[int, int]:
        x0, y0, x1, y1 = self.box
        return (x0 + x1) // 2, (y0 + y1) // 2


@dataclass(frozen=True, slots=True)
class OcrFrame:
    sha256: str
    size: tuple[int, int]
    blocks: tuple[TextBlock, ...]
    cold_seconds: float
    cached: bool


def _overlap(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area
    return area / union if union else 0


def original_box(line: dict[str, Any]) -> list[float]:
    """WinRT BoundingRect is deskewed: rotate clockwise about band center first.

    Matches Microsoft's OCR sample overlay, then undo resize and add crop offset.
    """
    box = line["box"]
    if "region_size" not in line:
        return [float(value) for value in box]
    width, height = line["region_size"]
    scale = float(line["scale"])
    ox, oy = line["offset"]
    angle = math.radians(float(line.get("angle") or 0))
    if not math.isfinite(angle) or not math.isfinite(scale) or scale <= 0:
        raise DecisionError("ocr_bad_transform")
    cosine, sine = math.cos(angle), math.sin(angle)
    points = []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
        dx, dy = x - width / 2, y - height / 2
        points.append(
            (
                (width / 2 + dx * cosine - dy * sine) / scale + ox,
                (height / 2 + dx * sine + dy * cosine) / scale + oy,
            )
        )
    return [
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    ]


def normalize_lines(lines: list[dict[str, Any]], size: tuple[int, int]) -> tuple[TextBlock, ...]:
    """Prefer installed Chinese recognition for overlapping lines; then stable reading order."""
    candidates = []
    for line in lines:
        text = re.sub(r"\s+", " ", str(line.get("text", ""))).strip()[:300]
        text = re.sub(r"(?<=[\u3400-\u9fff]) +(?=[\u3400-\u9fff])", "", text)
        box = line.get("box")
        if not text or not isinstance(box, list) or len(box) != 4:
            continue
        if any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in box):
            continue
        box = original_box(line)
        rect = (
            max(0, math.floor(box[0])),
            max(0, math.floor(box[1])),
            min(size[0] - 1, math.ceil(box[2])),
            min(size[1] - 1, math.ceil(box[3])),
        )
        if rect[0] >= rect[2] or rect[1] >= rect[3]:
            continue
        candidates.append((str(line.get("language", "")), text, rect))
    kept: list[tuple[str, str, tuple[int, int, int, int]]] = []
    for language, text, rect in sorted(candidates, key=lambda c: (not c[0].startswith("zh"), c[2])):
        if not any(_overlap(rect, old[2]) > 0.55 for old in kept):
            kept.append((language, text, rect))
    kept.sort(key=lambda c: (c[2][1], c[2][0], c[1]))
    return tuple(TextBlock(i, text, rect, lang) for i, (lang, text, rect) in enumerate(kept, 1))


def recognition_input(image_b64: str) -> dict[str, Any]:
    """Generic overlapping horizontal bands + 2x grayscale contrast for small UI text.

    Geometry is carried back to frozen-frame pixels. No target labels/scene-specific crops.
    """
    with Image.open(io.BytesIO(base64.b64decode(image_b64))) as source:
        width, height = source.size
        if width * height > 16_000_000 or min(width, height) < 1:
            raise DecisionError("ocr_dimensions_too_large")
        gray = source.convert("L")
        scale = min(2.0, 2048 / width)
        regions = []
        for top in range(0, height, 160):
            bottom = min(height, top + 200)
            if bottom - top < 24:
                continue
            band = ImageOps.autocontrast(gray.crop((0, top, width, bottom)))
            band = band.resize(
                (round(width * scale), round((bottom - top) * scale)), Image.Resampling.LANCZOS
            )
            out = io.BytesIO()
            band.save(out, format="PNG")
            regions.append(
                {
                    "image": base64.b64encode(out.getvalue()).decode("ascii"),
                    "offset": [0, top],
                    "scale": scale,
                }
            )
    return {"image_size": [width, height], "regions": regions}


class WindowsTextReader:
    """No capture/input APIs. No persistence unless an explicit cache directory is supplied."""

    def __init__(
        self, cache_dir: Path | None = None, *, cache_only: bool = False, timeout: float = 30
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_only = cache_only
        self.timeout = timeout

    async def _recognize(self, image_b64: str) -> dict[str, Any]:
        helper = Path(__file__).resolve().parents[4] / "scripts/windows_ocr_blocks.ps1"
        if os.name == "nt":
            binary, script = "powershell.exe", str(helper)
        elif Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe").is_file():
            binary = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
            convert = await asyncio.create_subprocess_exec(
                "wslpath",
                "-w",
                str(helper),
                stdout=asyncio.subprocess.PIPE,
            )
            out, _ = await convert.communicate()
            if convert.returncode:
                raise DecisionError("ocr_path_conversion")
            script = out.decode().strip()
        else:
            raise DecisionError("windows_ocr_unavailable")
        proc = await asyncio.create_subprocess_exec(
            binary,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, _ = await asyncio.wait_for(
                proc.communicate(json.dumps(recognition_input(image_b64)).encode()),
                self.timeout,
            )
        except BaseException:
            if proc.returncode is None:
                proc.kill()
            await proc.communicate()
            raise
        if proc.returncode:
            raise DecisionError("windows_ocr_failed")
        body = json.loads(out.decode("utf-8-sig"))
        if not isinstance(body, dict):
            raise DecisionError("windows_ocr_bad_output")
        return body

    @staticmethod
    def _cached(body: dict[str, Any], digest: str, size: tuple[int, int]) -> OcrFrame:
        if (
            body.get("pipeline_version") != PIPELINE_VERSION
            or body.get("sha256") != digest
            or body.get("image_size") != list(size)
            or body.get("engine") != "Windows.Media.Ocr"
        ):
            raise DecisionError("ocr_cache_mismatch")
        blocks = []
        for i, raw in enumerate(body["blocks"], 1):
            box = raw["box"]
            if (
                raw["id"] != i
                or not isinstance(raw["text"], str)
                or not raw["text"].strip()
                or not isinstance(box, list)
                or len(box) != 4
                or any(type(v) is not int for v in box)
                or not (0 <= box[0] < box[2] < size[0] and 0 <= box[1] < box[3] < size[1])
            ):
                raise DecisionError("ocr_cache_invalid_block")
            blocks.append(
                TextBlock(i, raw["text"], (box[0], box[1], box[2], box[3]), raw.get("language", ""))
            )
        cold = float(body["cold_seconds"])
        if not math.isfinite(cold) or cold < 0:
            raise DecisionError("ocr_cache_invalid_time")
        return OcrFrame(digest, size, tuple(blocks), cold, True)

    async def read(self, observation: Observation) -> OcrFrame:
        if not observation.image_png_b64 or not observation.image_size:
            raise DecisionError("ocr_no_image")
        data = base64.b64decode(observation.image_png_b64, validate=True)
        if len(data) > 20_000_000:
            raise DecisionError("ocr_image_too_large")
        digest = hashlib.sha256(data).hexdigest()
        size = observation.image_size
        path = self.cache_dir / f"{digest}.json" if self.cache_dir else None
        if path is not None and path.is_file():
            try:
                return self._cached(json.loads(path.read_text(encoding="utf-8")), digest, size)
            except (KeyError, TypeError, ValueError, AttributeError) as error:
                if isinstance(error, DecisionError):
                    raise
                raise DecisionError("ocr_cache_invalid") from error
        if self.cache_only:
            raise DecisionError("ocr_cache_missing")
        started = time.perf_counter()
        body = await self._recognize(observation.image_png_b64)
        if body.get("image_size") != list(size):
            raise DecisionError("ocr_size_mismatch")
        blocks = normalize_lines(body.get("lines", []), size)
        cold = time.perf_counter() - started
        if path is not None:
            payload = {
                "pipeline_version": PIPELINE_VERSION,
                "engine": "Windows.Media.Ocr",
                "sha256": digest,
                "image_size": list(size),
                "cold_seconds": cold,
                "languages": body.get("languages", []),
                "windows_version": body.get("windows_version"),
                "ocr_seconds": body.get("ocr_seconds"),
                "blocks": [
                    {"id": b.id, "text": b.text, "box": list(b.box), "language": b.language}
                    for b in blocks
                ],
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(f".{uuid4().hex}.tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(path)
        return OcrFrame(digest, size, blocks, cold, False)
