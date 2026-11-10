"""Offline evaluator contracts; all model requests in this file are in-memory fakes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import Decision
from siro.services.computer_use.safety import InputAction

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import computer_click_eval as bench


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    image = tmp_path / "frame.png"
    Image.new("RGB", (40, 30)).save(image)
    spec = {
        "version": 1,
        "dataset_id": "synthetic-unit-only",
        "image_root": ".",
        "cases": [
            {
                "id": "one",
                "image": image.name,
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "image_size": [40, 30],
                "process": "game.exe",
                "scenario": "menu",
                "goal": "Click Continue",
                "expect": {"click_boxes": [[10, 10, 20, 20]]},
                "label_source": {"method": "synthetic_unit_test"},
                "uncertain": False,
            }
        ],
    }
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def update_case(path: Path, **fields: object) -> None:
    spec = json.loads(path.read_text())
    spec["cases"][0].update(fields)
    path.write_text(json.dumps(spec))


def click(
    x: int | None = 15, y: int | None = 15, *, kind: str = "click", button: str = "left"
) -> Decision:
    return Decision("act", InputAction(kind, x=x, y=y, button=button), expect="menu closes")


@pytest.mark.parametrize(
    "x,y,hit", [(10, 10, True), (20, 20, True), (9, 15, False), (21, 15, False), (-1, 15, False)]
)
def test_exact_screenshot_pixel_boundaries(x: int, y: int, hit: bool) -> None:
    assert bench.score_click(click(x, y), [[10, 10, 20, 20]])[0] is hit


@pytest.mark.parametrize(
    "decision",
    [
        click(kind="move"),
        click(button="right"),
        click(x=None),
        click(kind="type"),
        Decision("wait"),
        Decision("act"),
    ],
)
def test_only_actual_left_click_can_hit(decision: Decision) -> None:
    assert not bench.score_click(decision, [[10, 10, 20, 20]])[0]


def test_frozen_case_load(dataset: Path) -> None:
    spec, cases = bench.load_cases(dataset)
    assert spec["dataset_id"] == "synthetic-unit-only"
    case, obs = cases[0]
    assert obs.image_size == (40, 30)
    assert obs.image_rect == (0, 0, 40, 30)
    assert obs.process == "game.exe"
    assert case["label_source"]


@pytest.mark.parametrize(
    "fields,error",
    [
        ({"sha256": "wrong"}, "sha256 mismatch"),
        ({"image_size": [1, 1]}, "image_size mismatch"),
        ({"expect": {"click_boxes": [[0, 0, 40, 30]]}}, "out-of-bounds"),
        ({"expect": {"click_boxes": [[False, 0, 3, 3]]}}, "out-of-bounds"),
        ({"expect": {}}, "click_boxes"),
        ({"label_source": {}}, "label_source"),
        ({"uncertain": "no"}, "boolean"),
        ({"image": "../outside.png"}, "escapes"),
    ],
)
def test_bad_manifest_rejected_before_models(
    dataset: Path, fields: dict[str, object], error: str
) -> None:
    update_case(dataset, **fields)
    with pytest.raises(ValueError, match=error):
        bench.load_cases(dataset)


def test_duplicate_ids_rejected(dataset: Path) -> None:
    spec = json.loads(dataset.read_text())
    spec["cases"].append(spec["cases"][0])
    dataset.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="duplicate"):
        bench.load_cases(dataset)


def test_default_off(dataset: Path) -> None:
    with pytest.raises(ValueError, match="BENCH_ENABLED"):
        asyncio.run(bench.evaluate(dataset, ["ollama"], {}))


def test_cloud_opt_in_and_missing_key_are_not_zero_accuracy(dataset: Path) -> None:
    _, cases = bench.load_cases(dataset)
    for backend in ("claude", "groq"):
        result = asyncio.run(bench.measure(backend, cases, {}, 1))
        assert result["reason"] == "cloud_screen_not_allowed"
        assert result["hit_rate"] is None and result["mean_seconds"] is None
    result = asyncio.run(bench.measure("groq", cases, {"SIRO_COMPUTER_CLOUD_SCREEN": "1"}, 1))
    assert result["reason"] == "groq_no_key"
    assert not result["rows"]


def test_uncertain_labels_never_enter_metrics(dataset: Path) -> None:
    update_case(dataset, uncertain=True)
    result = asyncio.run(bench.evaluate(dataset, ["ollama"], {bench.ENABLED: "1"}))
    assert result["excluded_uncertain"] == ["one"]
    assert result["results"][0]["reason"] == "no_certain_labels"
    assert result["results"][0]["eligible_cases"] == 0


def test_transport_changes_only_ollama_context() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={})

    async def send() -> None:
        transport = bench.Context8192Transport(httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=transport) as client:
            body = {"options": {"num_ctx": 2048, "num_predict": 150}, "model": "gemma"}
            await client.post("http://local/api/chat", json=body)
            await client.post("http://local/other", json=body)

    asyncio.run(send())
    assert bodies[0]["options"] == {"num_ctx": 8192, "num_predict": 150}
    assert bodies[1]["options"]["num_ctx"] == 2048


def test_real_decider_parser_with_fake_network_never_sends_input(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    async def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline evaluation attempted desktop input/capture")

    monkeypatch.setattr(ComputerBridge, "act", forbidden)
    monkeypatch.setattr(ComputerBridge, "observe", forbidden)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gemma4:e4b"}]})
        body = json.loads(request.content)
        assert body["options"]["num_ctx"] == 8192
        prompt = body["messages"][0]["content"]
        assert "click_boxes" not in prompt and "manual_visual_review" not in prompt
        reply = {
            "kind": "act",
            "action": {"kind": "click", "x": 15, "y": 15},
            "expect": "menu closes",
            "seen": "a menu",
            "confidence": 0.9,
        }
        return httpx.Response(200, json={"message": {"content": json.dumps(reply)}})

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda: httpx.MockTransport(handler))
    env = {bench.ENABLED: "1", "SIRO_COMPUTER_OLLAMA_MODEL": "gemma4:e4b"}
    result = asyncio.run(bench.evaluate(dataset, ["ollama"], env))["results"][0]
    assert result["status"] == "measured" and result["hits"] == 1
    assert result["hit_rate"] == 1.0 and result["errors"] == 0
    assert result["mean_seconds"] > 0
    assert result["mean_seconds"] == result["median_seconds"]
    assert calls == ["/api/tags", "/api/chat"]  # exactly one inference, no retry or execution


def test_ollama_unavailable_does_not_make_up_accuracy(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no service", request=request)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda: httpx.MockTransport(unavailable))
    _, cases = bench.load_cases(dataset)
    result = asyncio.run(bench.measure("ollama", cases, {}, 1))
    assert result["reason"] == "ollama_preflight:ConnectError"
    assert result["status"] == "not_measured" and result["hits"] is None


def test_mean_and_median_and_error_attempt_accounting() -> None:
    rows: list[dict[str, Any]] = [
        {"hit": True, "decision": "act", "seconds": 1.0},
        {"hit": False, "decision": "wait", "seconds": 2.0},
        {"hit": False, "why": "error", "seconds": 9.0},
    ]
    result = bench.summarize("ollama", "m", rows, 3)
    assert result["hit_rate"] == 1 / 3
    assert result["mean_seconds"] == 4.0 and result["median_seconds"] == 2.0
    assert result["errors"] == 1
    result = bench.summarize("claude", "m", [{"hit": False, "seconds": 1}], 3)
    assert result["status"] == "not_measured" and result["hit_rate"] is None


def test_cli_creates_report_parent_without_any_live_input(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_evaluate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"results": [{"status": "measured"}]}

    output = tmp_path / "new" / "nested" / "report.json"
    monkeypatch.setattr(bench, "evaluate", fake_evaluate)
    monkeypatch.setattr(sys, "argv", ["computer_click_eval", str(dataset), "--out", str(output)])
    assert bench.main() == 0
    assert json.loads(output.read_text()) == {"results": [{"status": "measured"}]}
