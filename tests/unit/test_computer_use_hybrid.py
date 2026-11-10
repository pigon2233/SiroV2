"""Label-free regions and hybrid contracts; no live provider or desktop input."""

from __future__ import annotations

import asyncio
import base64
import io
import json
from typing import Any

import httpx
import pytest
from PIL import Image, ImageDraw

from siro.services.computer_use import regions
from siro.services.computer_use.decision import CloudScreenNotAllowed, Decision, make_decider
from siro.services.computer_use.hybrid import HybridNumberedDecider, VisualSelector
from siro.services.computer_use.ocr import OcrFrame, TextBlock
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import InputAction


@pytest.fixture
def obs() -> Observation:
    image = Image.new("RGB", (120, 100), "black")
    ImageDraw.Draw(image).rectangle((60, 40, 90, 70), fill="yellow")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return Observation(
        1,
        0,
        "",
        "game.exe",
        (0, 0, 120, 100),
        (120, 100),
        "unit",
        base64.b64encode(output.getvalue()).decode(),
        (120, 100),
        (0, 0, 120, 100),
    )


class Inner:
    calls = 0

    async def decide(self, *args: Any, **kwargs: Any) -> Decision:
        self.calls += 1
        return Decision("act", InputAction("click", x=75, y=55), expect="changed")

    async def verify(self, *args: Any) -> Any:
        raise AssertionError("offline must never verify")


class Reader:
    async def read(self, obs: Observation) -> OcrFrame:
        return OcrFrame("unit", (120, 100), (TextBlock(1, "Continue", (5, 5, 25, 25)),), 0.1, True)


class Selector:
    def __init__(self, text: str = "0", visual: str = "0") -> None:
        self.text = text
        self.visual = visual
        self.visual_calls = 0

    async def select(self, prompt: str) -> str:
        return self.text

    async def choose(self, goal: str, encoded: str, frame: OcrFrame) -> str:
        self.visual_calls += 1
        if self.visual == "region":
            return str(next(b.id for b in frame.blocks if b.language == "contour/color"))
        return self.visual


def test_region_proposals_cover_synthetic_icon(obs: Observation) -> None:
    assert obs.image_png_b64 is not None
    image = Image.open(io.BytesIO(base64.b64decode(obs.image_png_b64)))
    boxes = regions.proposals(image)
    assert any(60 <= (b[0] + b[2]) // 2 <= 90 and 40 <= (b[1] + b[3]) // 2 <= 70 for b in boxes)
    assert len(boxes) <= 120


def test_default_flag_and_existing_api() -> None:
    assert not isinstance(make_decider({}), HybridNumberedDecider)
    assert isinstance(make_decider({"SIRO_COMPUTER_REGION_NUMBERED": "1"}), HybridNumberedDecider)


def test_text_route_never_calls_vision(obs: Observation) -> None:
    selector = Selector("1")
    decider = HybridNumberedDecider(Inner(), Reader(), selector)  # type: ignore[arg-type]
    decision = asyncio.run(decider.decide("Continue", [], obs))
    assert decision.action is not None and decision.action.x == 15
    assert selector.visual_calls == 0 and decider.last_route == "ocr"
    assert decision.confidence == 0


@pytest.mark.parametrize("enabled", [False, True])
def test_pixel_fallback_requires_separate_flag_and_explicit_zero(
    obs: Observation, enabled: bool
) -> None:
    inner = Inner()
    decider = HybridNumberedDecider(inner, Reader(), Selector(), pixel_fallback=enabled)  # type: ignore[arg-type]
    decision = asyncio.run(decider.decide("icon", [], obs))
    assert inner.calls == int(enabled)
    assert decision.kind == ("act" if enabled else "wait")


@pytest.mark.parametrize("reply", ["bad", "99999", "1;delete"])
def test_malformed_visual_never_triggers_pixel_fallback(obs: Observation, reply: str) -> None:
    inner = Inner()
    decider = HybridNumberedDecider(inner, Reader(), Selector(visual=reply), pixel_fallback=True)  # type: ignore[arg-type]
    assert asyncio.run(decider.decide("icon", [], obs)).kind == "wait"
    assert inner.calls == 0


def test_real_center_mapping_for_contour(obs: Observation) -> None:
    decider = HybridNumberedDecider(Inner(), Reader(), Selector(visual="region"))  # type: ignore[arg-type]
    result = asyncio.run(decider.decide("icon", [], obs))
    assert result.action is not None
    assert decider.last_frame is not None
    assert any((result.action.x, result.action.y) == b.center for b in decider.last_frame.blocks)


def test_visual_request_context_and_resource_options(obs: Observation) -> None:
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "1"}})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            selector = VisualSelector(
                "ollama",
                {"SIRO_COMPUTER_OLLAMA_NO_DRAFT": "1", "SIRO_COMPUTER_OLLAMA_GPU_LAYERS": "24"},
                client=client,
            )
            assert obs.image_png_b64 is not None
            await selector.choose("icon", obs.image_png_b64, await Reader().read(obs))

    asyncio.run(run())
    assert bodies[0]["options"] == {
        "num_ctx": 8192,
        "num_predict": 8,
        "temperature": 0,
        "draft_num_predict": 0,
        "num_gpu": 24,
    }
    assert bodies[0]["messages"][0]["images"]


def test_cloud_gate_before_image_processing(obs: Observation) -> None:
    selector = VisualSelector("claude", {})
    assert obs.image_png_b64 is not None
    with pytest.raises(CloudScreenNotAllowed):
        asyncio.run(selector.choose("icon", obs.image_png_b64, asyncio.run(Reader().read(obs))))
