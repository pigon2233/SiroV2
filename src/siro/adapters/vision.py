"""Conservative local screen analysis that makes no semantic UI claims."""

from __future__ import annotations

import io
from collections import Counter
from collections.abc import Iterable
from typing import cast

from PIL import Image

from siro.ports.vision import VisualObservation


class PixelScreenAnalyzer:
    """Reports only directly measured size, brightness and coarse dominant colour."""

    async def analyze(self, image_png: bytes) -> VisualObservation:
        with Image.open(io.BytesIO(image_png)) as source:
            image = source.convert("RGB")
            image.thumbnail((256, 256))
            pixels = list(cast(Iterable[tuple[int, int, int]], image.get_flattened_data()))
            width, height = source.size
        if not pixels:
            raise ValueError("screen image contains no pixels")
        brightness = sum(sum(pixel) / 3 for pixel in pixels) / len(pixels)
        buckets: Counter[str] = Counter()
        for red, green, blue in pixels:
            spread = max(red, green, blue) - min(red, green, blue)
            if spread < 24:
                buckets["neutral"] += 1
            elif red == max(red, green, blue):
                buckets["red"] += 1
            elif green == max(red, green, blue):
                buckets["green"] += 1
            else:
                buckets["blue"] += 1
        colour, count = buckets.most_common(1)[0]
        tone = "light" if brightness >= 128 else "dark"
        confidence = round(count / len(pixels), 4)
        return VisualObservation(
            description=f"{tone} screen; {colour} is the largest coarse colour bucket",
            source="pixel-screen-analyzer:v1",
            confidence=confidence,
            width=width,
            height=height,
        )
