from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import struct
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, Playwright, Route, WebSocketRoute, sync_playwright

from siro.adapters.body.assets import verified_vrm_model
from siro.services.presentation.gateway import create_app, vrm_renderer_from_env

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "renderers" / "vrm"
ORIGIN = "http://siro.test"


def _load_prepare_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "prepare_vrm_renderer", ROOT / "scripts" / "prepare_vrm_renderer.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


PREPARE = _load_prepare_script()

# Required VRM 1.0 humanoid bones: (name, parent, local translation).
BONES = [
    ("hips", None, (0, 0.9, 0)),
    ("spine", "hips", (0, 0.1, 0)),
    ("neck", "spine", (0, 0.35, 0)),
    ("head", "neck", (0, 0.1, 0)),
    ("leftUpperArm", "spine", (0.15, 0.3, 0)),
    ("leftLowerArm", "leftUpperArm", (0.25, 0, 0)),
    ("leftHand", "leftLowerArm", (0.22, 0, 0)),
    ("rightUpperArm", "spine", (-0.15, 0.3, 0)),
    ("rightLowerArm", "rightUpperArm", (-0.25, 0, 0)),
    ("rightHand", "rightLowerArm", (-0.22, 0, 0)),
    ("leftUpperLeg", "hips", (0.1, -0.05, 0)),
    ("leftLowerLeg", "leftUpperLeg", (0, -0.4, 0)),
    ("leftFoot", "leftLowerLeg", (0, -0.4, 0)),
    ("rightUpperLeg", "hips", (-0.1, -0.05, 0)),
    ("rightLowerLeg", "rightUpperLeg", (0, -0.4, 0)),
    ("rightFoot", "rightLowerLeg", (0, -0.4, 0)),
]


def synthetic_vrm() -> bytes:
    """A tiny, self-made VRM 1.0 GLB: one skinned quad with happy/blink/aa morph targets."""

    positions = [(-0.2, 0.6, 0.0), (0.2, 0.6, 0.0), (0.2, 1.5, 0.0), (-0.2, 1.5, 0.0)]
    happy = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.05, 0.0), (0.0, 0.05, 0.0)]
    blink = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, -0.05, 0.0), (0.0, -0.05, 0.0)]
    aa = [(0.0, -0.03, 0.0), (0.0, -0.03, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    chunks: list[bytes] = []
    views: list[dict[str, int]] = []
    accessors: list[dict[str, object]] = []

    def add(data: bytes, accessor: dict[str, object]) -> int:
        offset = sum(len(c) for c in chunks)
        chunks.append(data + b"\0" * (-len(data) % 4))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data)})
        accessors.append({"bufferView": len(views) - 1, **accessor})
        return len(accessors) - 1

    def vec3(values: list[tuple[float, float, float]]) -> int:
        data = b"".join(struct.pack("<3f", *v) for v in values)
        lows = [min(v[i] for v in values) for i in range(3)]
        highs = [max(v[i] for v in values) for i in range(3)]
        return add(
            data,
            {
                "componentType": 5126,
                "count": len(values),
                "type": "VEC3",
                "min": lows,
                "max": highs,
            },
        )

    position = vec3(positions)
    normal = add(
        b"".join(struct.pack("<3f", 0, 0, 1) for _ in positions),
        {"componentType": 5126, "count": 4, "type": "VEC3"},
    )
    joints = add(
        struct.pack("<16H", *([0] * 16)), {"componentType": 5123, "count": 4, "type": "VEC4"}
    )
    weights = add(
        b"".join(struct.pack("<4f", 1, 0, 0, 0) for _ in positions),
        {"componentType": 5126, "count": 4, "type": "VEC4"},
    )
    indices = add(
        struct.pack("<6H", 0, 1, 2, 0, 2, 3), {"componentType": 5123, "count": 6, "type": "SCALAR"}
    )
    happy_target, blink_target, aa_target = vec3(happy), vec3(blink), vec3(aa)
    inverse_bind = add(
        struct.pack("<16f", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -0.9, 0, 1),
        {"componentType": 5126, "count": 1, "type": "MAT4"},
    )
    names = [name for name, _, _ in BONES]
    nodes: list[dict[str, object]] = []
    for name, _parent, translation in BONES:
        children = [names.index(n) for n, p, _ in BONES if p == name]
        node: dict[str, object] = {"name": name, "translation": list(translation)}
        if children:
            node["children"] = children
        nodes.append(node)
    mesh_node = len(nodes)
    nodes.append({"name": "Body", "mesh": 0, "skin": 0})
    document = {
        "asset": {"version": "2.0", "generator": "SIRO synthetic VRM test fixture"},
        "extensionsUsed": ["VRMC_vrm"],
        "scene": 0,
        "scenes": [{"nodes": [0, mesh_node]}],
        "nodes": nodes,
        "skins": [{"joints": [0], "inverseBindMatrices": inverse_bind}],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": position,
                            "NORMAL": normal,
                            "JOINTS_0": joints,
                            "WEIGHTS_0": weights,
                        },
                        "indices": indices,
                        "targets": [
                            {"POSITION": happy_target},
                            {"POSITION": blink_target},
                            {"POSITION": aa_target},
                        ],
                    }
                ],
                "extras": {"targetNames": ["happy", "blink", "aa"]},
            }
        ],
        "buffers": [{"byteLength": sum(len(c) for c in chunks)}],
        "bufferViews": views,
        "accessors": accessors,
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {
                    "name": "Synthetic SIRO fixture",
                    "authors": ["SIRO tests"],
                    "licenseUrl": "https://vrm.dev/licenses/1.0/",
                },
                "humanoid": {"humanBones": {name: {"node": i} for i, name in enumerate(names)}},
                "expressions": {
                    "preset": {
                        "happy": {
                            "morphTargetBinds": [{"node": mesh_node, "index": 0, "weight": 1}]
                        },
                        "blink": {
                            "morphTargetBinds": [{"node": mesh_node, "index": 1, "weight": 1}]
                        },
                        "aa": {"morphTargetBinds": [{"node": mesh_node, "index": 2, "weight": 1}]},
                    }
                },
            }
        },
    }
    payload = json.dumps(document).encode()
    payload += b" " * (-len(payload) % 4)
    binary = b"".join(chunks)
    total = 12 + 8 + len(payload) + 8 + len(binary)
    return (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
        + struct.pack("<II", len(binary), 0x004E4942)
        + binary
    )


def write_model(directory: Path, *, tamper: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    model = directory / "model.vrm"
    model.write_bytes(synthetic_vrm())
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    if tamper:
        model.write_bytes(model.read_bytes() + b"\0")
    manifest = directory / "asset-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "asset_id": "vrm.synthetic-fixture",
                "source_url": "https://example.invalid/source",
                "license_name": "Synthetic test fixture",
                "license_url": "https://example.invalid/license",
                "accepted_by": "tests",
                "accepted_at": "2026-10-19T00:00:00+08:00",
                "files": [{"path": "model.vrm", "sha256": digest}],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def renderer_fixture(tmp_path: Path) -> Path:
    dist = tmp_path / "vrm-dist"
    (dist / "index.html").parent.mkdir(parents=True)
    (dist / "index.html").write_text("<title>vrm renderer fixture</title>", encoding="utf-8")
    return dist


def test_vrm_renderer_is_only_mounted_when_configured(tmp_path: Path) -> None:
    dist = renderer_fixture(tmp_path)
    model = verified_vrm_model(write_model(tmp_path / "assets"))
    configured = TestClient(create_app(vrm_dist=dist, vrm_model=model))
    assert configured.get("/vrm/").text == "<title>vrm renderer fixture</title>"
    served = configured.get("/vrm-model/model.vrm")
    assert served.status_code == 200
    assert served.content == model.read_bytes()
    assert served.headers["cache-control"] == "no-store"
    index = configured.get("/").text
    assert 'src="/vrm/"' in index
    assert "VRM 角色載入中" in index
    assert "角色目前顯示替身" not in index.split('<p id="runtime-notice"', 1)[1].split("</p>")[0]
    assert configured.get("/desktop").status_code == 200
    assert 'src="/vrm/?presentation=desktop"' in configured.get("/desktop").text

    unconfigured = TestClient(create_app())
    assert unconfigured.get("/vrm/").status_code == 404
    assert unconfigured.get("/vrm-model/model.vrm").status_code == 404
    assert unconfigured.get("/desktop").status_code == 503


def test_vrm_takes_precedence_and_live2d_stays_mounted(tmp_path: Path) -> None:
    dist = renderer_fixture(tmp_path)
    live2d = tmp_path / "live2d"
    live2d.mkdir()
    (live2d / "index.html").write_text("<title>licensed renderer</title>", encoding="utf-8")
    model = verified_vrm_model(write_model(tmp_path / "assets"))
    client = TestClient(create_app(vrm_dist=dist, vrm_model=model, live2d_dist=live2d))
    assert 'src="/vrm/"' in client.get("/").text
    assert client.get("/live2d/").text == "<title>licensed renderer</title>"


def test_vrm_configuration_must_be_complete_and_verified(tmp_path: Path) -> None:
    dist = renderer_fixture(tmp_path)
    manifest = write_model(tmp_path / "assets")
    with pytest.raises(ValueError, match="configured together"):
        create_app(vrm_dist=dist)
    assert vrm_renderer_from_env({}) == (None, None)
    with pytest.raises(ValueError, match="set together"):
        vrm_renderer_from_env({"SIRO_VRM_DIST": str(dist)})
    with pytest.raises(ValueError, match=r"index\.html"):
        vrm_renderer_from_env(
            {"SIRO_VRM_DIST": str(tmp_path), "SIRO_VRM_MODEL_MANIFEST": str(manifest)}
        )
    resolved = vrm_renderer_from_env(
        {"SIRO_VRM_DIST": str(dist), "SIRO_VRM_MODEL_MANIFEST": str(manifest)}
    )
    assert resolved == (dist.resolve(), (tmp_path / "assets" / "model.vrm").resolve())
    with pytest.raises(ValueError, match="checksum mismatch"):
        verified_vrm_model(write_model(tmp_path / "tampered", tamper=True))
    other = tmp_path / "no-vrm"
    other.mkdir()
    (other / "texture.png").write_bytes(b"synthetic")
    (other / "asset-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "asset_id": "vrm.no-model",
                "source_url": "https://example.invalid/source",
                "license_name": "Synthetic",
                "license_url": "https://example.invalid/license",
                "accepted_by": "tests",
                "accepted_at": "2026-10-19T00:00:00+08:00",
                "files": [
                    {"path": "texture.png", "sha256": hashlib.sha256(b"synthetic").hexdigest()}
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"exactly one \.vrm"):
        verified_vrm_model(other / "asset-manifest.json")


def test_prepare_script_checks_vrm_extension(tmp_path: Path) -> None:
    model = tmp_path / "model.vrm"
    model.write_bytes(synthetic_vrm())
    assert PREPARE.vrm_spec_version(model) == "1.0"
    (tmp_path / "plain.glb").write_bytes(b"not a glb")
    with pytest.raises(ValueError, match="binary glTF"):
        PREPARE.vrm_spec_version(tmp_path / "plain.glb")


# ---- Real browser checks of the renderer source against a mocked gateway ----

INIT = """
window.__posted = [];
window.addEventListener('message', event => window.__posted.push(event.data));
window.__speak = 0;
if ('speechSynthesis' in window) window.speechSynthesis.speak = () => { window.__speak += 1; };
"""


def built_renderer(tmp_path: Path) -> Path:
    modules = SOURCE / "node_modules"
    if not (modules / "three").is_dir() or not (modules / "@pixiv" / "three-vrm").is_dir():
        pytest.skip("renderer dependencies missing: run `npm ci` in renderers/vrm")
    dist = tmp_path / "dist"
    shutil.copytree(SOURCE / "src", dist / "src")
    shutil.copy2(SOURCE / "index.html", dist / "index.html")
    for target, source in PREPARE.VENDOR.items():
        (dist / "vendor" / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(modules / source, dist / "vendor" / target)
    PREPARE.copy_motions(dist / "motions")
    return dist


class MockGateway:
    def __init__(self, dist: Path, *, model: bytes | None) -> None:
        self.dist = dist
        self.model = model
        self.sessions = 0
        self.received: list[dict[str, object]] = []
        self.socket: WebSocketRoute | None = None
        self.missing: set[str] = set()  # renderer files answered 404, to test partial loads

    def http(self, route: Route) -> None:
        path = route.request.url.removeprefix(ORIGIN).split("?", 1)[0]
        if path == "/v1/session":
            self.sessions += 1
            route.fulfill(json={"token": "synthetic-token"})
        elif path == "/vrm-model/model.vrm":
            if self.model is None:
                route.fulfill(status=404, body="missing")
            else:
                route.fulfill(body=self.model, content_type="model/gltf-binary")
        elif path.startswith("/vrm/"):
            relative = path.removeprefix("/vrm/") or "index.html"
            if relative in self.missing:
                route.fulfill(status=404, body="missing")
                return
            file = (self.dist / relative).resolve()
            if not file.is_relative_to(self.dist.resolve()) or not file.is_file():
                route.fulfill(status=404, body="missing")
                return
            types = {".html": "text/html", ".js": "text/javascript", ".txt": "text/plain"}
            route.fulfill(body=file.read_bytes(), content_type=types.get(file.suffix, "text/plain"))
        else:
            route.fulfill(status=404, body="missing")

    def websocket(self, socket: WebSocketRoute) -> None:
        self.socket = socket
        socket.on_message(lambda message: self.received.append(json.loads(message)))

    def send(self, message: dict[str, object]) -> None:
        assert self.socket is not None
        self.socket.send(json.dumps(message))


def open_renderer(
    playwright: Playwright,
    gateway: MockGateway,
    query: str = "",
    viewport: tuple[int, int] = (360, 640),
) -> tuple[Browser, Page]:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    browser = playwright.chromium.launch(
        executable_path=executable,
        headless=True,
        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
    )
    page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
    page.add_init_script(INIT)
    page.route(f"{ORIGIN}/**", gateway.http)
    page.route_web_socket("ws://siro.test/ws/body", gateway.websocket)
    page.goto(f"{ORIGIN}/vrm/{query}")
    return browser, page


def test_renderer_follows_body_protocol_without_owning_speech(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway)
        try:
            page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=60000)
            page.wait_for_function("window.__siroVrm.frames() > 3")
            deadline = time.monotonic() + 10
            while not gateway.received and time.monotonic() < deadline:
                page.wait_for_timeout(50)
            assert gateway.received[0] == {"type": "authenticate", "token": "synthetic-token"}
            assert page.evaluate("document.documentElement.dataset.siroRenderer") == "vrm"
            page.wait_for_function("window.__siroVrm.activity() !== null", timeout=30000)

            gateway.send({"v": 1, "type": "body.emotion", "name": "happy", "intensity": 0.8})
            page.wait_for_function("window.__siroVrm.expression('happy') > 0.5")
            # A new emotion gets one body reaction, then its own idle loop while it holds.
            page.wait_for_function("window.__siroVrm.activity() === 'clap'")
            page.wait_for_function("window.__siroVrm.activity() === 'idle_happy'", timeout=10000)
            page.wait_for_function(
                "window.__posted.some(m => m.type === 'siro.renderer.ready'"
                " && m.emotion === 'happy')"
            )
            ready = page.evaluate(
                "window.__posted.find(m => m.type === 'siro.renderer.ready'"
                " && m.emotion === 'happy')"
            )
            assert ready["renderer"] == "VRM"
            assert ready["character"] == "Synthetic SIRO fixture"

            # A future protocol version is ignored rather than guessed.
            gateway.send({"v": 2, "type": "body.emotion", "name": "sad"})
            page.wait_for_timeout(300)
            assert page.evaluate("document.documentElement.dataset.siroEmotion") == "happy"

            # body.look holds the target 0.8 m to her right of the head (glances can't fake it:
            # they keep the far viewer distance, this one sits 1.2 m in front of her).
            gateway.send({"v": 1, "type": "body.look", "x": 1, "y": 0})
            page.wait_for_function(
                "(([x, , z]) => x > 0.6 && x < 1.0 && z < 1.5)(window.__siroVrm.lookTarget())"
            )

            # Back to neutral, the plain idle loop returns.
            gateway.send({"v": 1, "type": "body.emotion", "name": "neutral", "intensity": 1})
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=10000)

            # The authored idle loop drives the body; a gesture cross-fades in and hands back.
            gateway.send({"v": 1, "type": "body.gesture", "name": "nod"})
            page.wait_for_function("window.__siroVrm.activity() === 'nod'")
            page.wait_for_function("window.__siroVrm.neckPitch() > 0.05")
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=10000)

            # Speech cues pick one gesture per reply; the menu triggers any gesture by hand.
            gateway.send({"v": 1, "type": "body.speech", "text": "你好呀!", "generation_id": "g0"})
            page.wait_for_function("window.__siroVrm.activity() === 'wave'")
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=10000)
            gateway.send(
                {"v": 1, "type": "body.speech", "text": "嗨 再說一次", "generation_id": "g0"}
            )
            page.wait_for_timeout(300)
            assert page.evaluate("window.__siroVrm.activity()") == "idle"
            assert page.locator("#gesture-menu").is_hidden()
            page.mouse.click(180, 320, button="right")
            page.locator("#gesture-menu button", has_text="鞠躬").click()
            assert page.locator("#gesture-menu").is_hidden()
            page.wait_for_function("window.__siroVrm.activity() === 'bow'")
            assert not any(
                m.get("type") == "siro.renderer.interact" for m in page.evaluate("window.__posted")
            )
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=10000)
            page.mouse.click(180, 320, button="right")
            page.locator("#gesture-menu button", has_text="坐下").click()
            page.wait_for_function("window.__siroVrm.activity() === 'sit_loop'", timeout=5000)
            # A held pose keeps its arms: the mixer skips unchanged values, so the life layer
            # must not zero bones it then never gets back.
            page.wait_for_timeout(500)
            assert abs(page.evaluate("window.__siroVrm.bone('rightUpperArm')")[3]) < 0.95

            gateway.send({"v": 1, "type": "body.speech", "text": "合成測試", "generation_id": "g1"})
            gateway.send({"v": 1, "type": "body.cancel", "generation_id": "g1"})
            page.wait_for_timeout(300)
            assert page.evaluate("window.__speak") == 0
            assert page.evaluate("window.__siroVrm.expression('aa')") in (None, 0)

            # The mouth follows only the parent's playback-clock loudness, and closes when the
            # player stops sending.
            page.evaluate(
                "window.__talk = setInterval(() => window.postMessage("
                "{type: 'siro.speech.mouth', v: 1, level: 0.9, tone: 0.5}, location.origin), 30)"
            )
            page.wait_for_function("window.__siroVrm.expression('aa') > 0.5")
            page.evaluate("clearInterval(window.__talk)")
            page.wait_for_function("window.__siroVrm.expression('aa') < 0.05", timeout=3000)
            page.evaluate(
                "window.postMessage({type: 'siro.speech.mouth', v: 2, level: 1}, location.origin)"
            )
            page.wait_for_timeout(200)
            assert page.evaluate("window.__siroVrm.expression('aa')") < 0.05
        finally:
            browser.close()


def test_framing_gaze_and_pointer_reactions(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway, "?presentation=desktop")
        try:
            page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=60000)
            page.wait_for_function("window.__siroVrm.activity() !== null", timeout=30000)
            # Every clip's reach fits in the frame, so a raised hand is never cut off.
            framing = page.evaluate("window.__siroVrm.framing()")
            assert framing["reachTop"] is not None
            assert framing["centerY"] + framing["height"] / 2 >= framing["reachTop"]

            # The page points her at the chat box while the user types; she looks over there
            # (far below her feet here, where no idle glance ever goes).
            page.evaluate(
                "window.postMessage({type: 'siro.view.focus', v: 1, x: 0.5, y: 1.5},"
                " location.origin)"
            )
            page.wait_for_function("window.__siroVrm.lookTarget()[1] < -1")

            # Stroking her head is a pat: a brief smile over Core's emotion, then back.
            head = page.evaluate("window.__siroVrm.head()")
            sweep = max(8, head["radius"] * 0.6)
            for i in range(10):
                page.mouse.move(head["x"] + (sweep if i % 2 else -sweep), head["y"], steps=3)
                page.wait_for_timeout(40)
            page.wait_for_function("window.__siroVrm.reaction() === 'happy'")
            page.wait_for_function("window.__siroVrm.reaction() === null", timeout=6000)

            # Poking her again and again makes her pout; each click still asks for the chat.
            for _ in range(4):
                page.mouse.click(head["x"], head["y"] + 3 * head["radius"])
                page.wait_for_timeout(100)
            assert page.evaluate("window.__siroVrm.reaction()") == "angry"
            assert any(
                m.get("type") == "siro.renderer.interact" for m in page.evaluate("window.__posted")
            )
            # Touches reach SIRO as body.touch: one pat for the patting, and the burst of four
            # clicks as one poke once the clicking stops. Nothing else leaves the renderer.
            deadline = time.monotonic() + 5
            while len(gateway.received) < 3 and time.monotonic() < deadline:
                page.wait_for_timeout(100)
            assert gateway.received[1:] == [
                {"v": 1, "type": "body.touch", "kind": "pat", "count": 1},
                {"v": 1, "type": "body.touch", "kind": "poke", "count": 4},
            ]
        finally:
            browser.close()


def test_drag_dangles_and_lands_and_the_notebook_is_a_held_state(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway, "?presentation=desktop")
        try:
            page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=60000)
            page.wait_for_function("window.__siroVrm.activity() !== null", timeout=30000)
            head = page.evaluate("window.__siroVrm.head()")
            x, y = head["x"], head["y"] + 3 * head["radius"]

            # Dragging the desktop window picks her up; letting go sets her down.
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 20, y + 10, steps=4)
            page.wait_for_function("window.__siroVrm.activity() === 'dangle'")
            page.wait_for_timeout(800)
            assert page.evaluate("window.__siroVrm.activity()") == "dangle"
            page.mouse.up()
            page.wait_for_function("window.__siroVrm.activity() === 'land'", timeout=5000)
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=10000)
            # Being carried reaches SIRO once, on landing.
            assert gateway.received[1:] == [
                {"v": 1, "type": "body.touch", "kind": "carry", "count": 1}
            ]

            # The notebook: out, read (a held loop with the prop in her hands), then away.
            page.mouse.click(x, y, button="right")
            page.locator("#gesture-menu button", has_text="看筆記").click()
            page.wait_for_function("window.__siroVrm.activity() === 'notebook_read'", timeout=10000)
            assert page.evaluate("window.__siroVrm.notebook()")
            # A gesture from Core waits while she reads.
            gateway.send({"v": 1, "type": "body.gesture", "name": "wave"})
            page.wait_for_timeout(300)
            assert page.evaluate("window.__siroVrm.activity()") == "notebook_read"
        finally:
            browser.close()


def ready_renderer(page: Page, gateway: MockGateway) -> None:
    page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=60000)
    page.wait_for_function("window.__siroVrm.activity() !== null", timeout=30000)
    deadline = time.monotonic() + 10
    while not gateway.received and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert gateway.received, "the renderer never authenticated"


def menu(page: Page, label: str) -> None:
    page.mouse.click(180, 320, button="right")
    page.locator("#gesture-menu button", has_text=label).click()


def test_emotion_while_seated_keeps_the_hold_and_a_second_sit_works(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway)
        try:
            ready_renderer(page, gateway)
            menu(page, "坐下")
            page.wait_for_function("window.__siroVrm.activity() === 'sit_loop'", timeout=5000)
            # An emotion while seated changes her face, not her posture: no nod or clap out of the
            # sit, and the mood idle does not replace the seated loop.
            gateway.send({"v": 1, "type": "body.emotion", "name": "happy", "intensity": 0.8})
            page.wait_for_function("window.__siroVrm.expression('happy') > 0.5")
            page.wait_for_timeout(600)
            assert page.evaluate("window.__siroVrm.activity()") == "sit_loop"
            # The hold ends the one way it should: stand_up, then the (happy) idle.
            page.wait_for_function("window.__siroVrm.activity() === 'stand_up'", timeout=15000)
            page.wait_for_function("window.__siroVrm.activity() === 'idle_happy'", timeout=10000)
            gateway.send({"v": 1, "type": "body.emotion", "name": "neutral", "intensity": 1})
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=10000)
            menu(page, "坐下")
            page.wait_for_function("window.__siroVrm.activity() === 'sit_loop'", timeout=5000)
        finally:
            browser.close()


def test_cancel_stops_the_gesture_its_reply_started(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway)
        try:
            ready_renderer(page, gateway)
            gateway.send({"v": 1, "type": "body.speech", "text": "你好", "generation_id": "r-g1"})
            page.wait_for_function("window.__siroVrm.activity() === 'wave'")
            # Another reply's cancel leaves it alone; its own cancel ends it.
            gateway.send({"v": 1, "type": "body.cancel", "generation_id": "other"})
            page.wait_for_timeout(300)
            assert page.evaluate("window.__siroVrm.activity()") == "wave"
            gateway.send({"v": 1, "type": "body.cancel", "generation_id": "r-g1"})
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=1000)
        finally:
            browser.close()


READY = "window.__posted.find(m => m && m.type === 'siro.renderer.ready')"


def test_one_missing_clip_only_disables_what_needs_it(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    gateway.missing = {"motions/wave.vrma"}
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway)
        try:
            ready_renderer(page, gateway)
            assert page.evaluate("window.__siroVrm.motions()") == {
                "state": "partial",
                "missing": ["wave"],
            }
            page.wait_for_function(READY)
            assert page.evaluate(READY)["motions"] == {"state": "partial", "missing": ["wave"]}
            assert page.evaluate("window.__siroVrm.activity()") == "idle"
            # Other gestures still play; the missing one's menu item is off and a cue just falls
            # back to the idle.
            gateway.send({"v": 1, "type": "body.gesture", "name": "nod"})
            page.wait_for_function("window.__siroVrm.activity() === 'nod'")
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=10000)
            page.mouse.click(180, 320, button="right")
            assert page.locator("#gesture-menu button", has_text="揮手").is_disabled()
            assert page.locator("#gesture-menu button", has_text="鞠躬").is_enabled()
            assert page.inner_text("#status") == ""
        finally:
            browser.close()


def test_missing_idle_falls_back_to_the_still_pose_and_says_so(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    gateway.missing = {"motions/idle.vrma"}
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway)
        try:
            page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=60000)
            page.wait_for_function("window.__siroVrm.motions().state === 'none'", timeout=30000)
            assert page.evaluate("window.__siroVrm.activity()") is None
            assert "靜態姿勢" in page.inner_text("#status")
            page.wait_for_function(READY)
            assert page.evaluate(READY)["motions"]["state"] == "none"
            assert page.evaluate("document.documentElement.dataset.siroRenderer") == "vrm"
        finally:
            browser.close()


def test_desktop_framing_keeps_every_clips_soles_and_hands_on_screen(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(
            playwright, gateway, "?presentation=desktop", viewport=(540, 960)
        )
        try:
            ready_renderer(page, gateway)
            # Boot soles (the shoe's measured sole below the foot joints) and hand tips of every
            # clip, projected with perspective, stay inside the frame: seated feet forward, raised
            # hands.
            reach = page.evaluate("window.__siroVrm.reachOnScreen()")
            assert reach["points"] > 0
            assert -1 < reach["lowest"] < -0.8, reach
            assert reach["highest"] < 1, reach
        finally:
            browser.close()


WALK_REQUESTS = "window.__posted.filter(m => m && m.type === 'siro.desktop.walk' && m.v === 1)"


def test_desktop_stroll_turns_walks_with_the_window_and_stops_when_called(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway, "?presentation=desktop")
        try:
            page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=60000)
            page.wait_for_function("window.__siroVrm.activity() !== null", timeout=30000)
            head = page.evaluate("window.__siroVrm.head()")
            x, y = head["x"], head["y"] + 3 * head["radius"]

            def menu_stroll() -> dict[str, object]:
                count = page.evaluate(f"{WALK_REQUESTS}.length")
                page.mouse.click(x, y, button="right")
                page.locator("#gesture-menu button", has_text="散步").click()
                page.wait_for_function(f"{WALK_REQUESTS}.length > {count}")
                return page.evaluate(f"{WALK_REQUESTS}.at(-1)")

            def host(update: dict[str, object]) -> None:
                message = {"type": "siro.desktop.walk.state", "v": 1, **update}
                page.evaluate("m => window.postMessage(m, location.origin)", message)

            # She asks the host for room at her stride speed; the host lets her walk right.
            request = menu_stroll()
            assert request["action"] == "start" and request["direction"] == 0
            assert request["speed"] > 0 and request["distance"] > 0
            # Room for both ramps and at least one whole stride cycle, which the host can grant.
            assert abs(request["cycle"] - 1 / 0.7) < 0.05
            minimum = request["speed"] * (request["ramp"] + request["cycle"])
            assert request["distance"] >= minimum
            # The window travels at the stride speed the pack records for the walk.
            pack = json.loads((PREPARE.MOTIONS / "pack.json").read_text(encoding="utf-8"))
            walk = next(a for a in pack["activities"] if a["activity"] == "walk")
            assert page.evaluate("window.__siroVrm.walkSpeed()") == walk["root_speed_mps"]
            assert abs(request["ramp"] - 1 / 0.7) < 0.05 and abs(request["delay"] - 1 / 0.7) < 0.05
            host(
                {
                    "id": request["id"],
                    "state": "started",
                    "direction": 1,
                    "distance": 500,
                    "ramp": request["ramp"],
                    "cruise": 0.6,
                    "delay": request["delay"],
                }
            )
            page.wait_for_function("window.__siroVrm.activity() === 'turn_step'")
            page.wait_for_function("window.__siroVrm.activity() === 'walk_start'", timeout=5000)
            assert page.evaluate("window.__siroVrm.facing()") > 1.5  # turned to screen right
            page.wait_for_function("window.__siroVrm.activity() === 'walk'", timeout=5000)
            page.wait_for_function("window.__siroVrm.activity() === 'walk_stop'", timeout=5000)
            page.wait_for_function("window.__siroVrm.stroll() === 'back'", timeout=5000)
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=5000)
            assert page.evaluate("window.__siroVrm.stroll()") is None
            assert abs(page.evaluate("window.__siroVrm.facing()")) < 1e-3

            # Called back mid-walk (a click): she asks the host to stop, settles and turns back.
            request = menu_stroll()
            host(
                {
                    "id": request["id"],
                    "state": "started",
                    "direction": -1,
                    "distance": 900,
                    "ramp": request["ramp"],
                    "cruise": 5,
                    "delay": request["delay"],
                }
            )
            page.wait_for_function("window.__siroVrm.activity() === 'walk'", timeout=8000)
            page.mouse.click(x, y)
            # postMessage delivers on a later task: wait for the request to arrive.
            page.wait_for_function(f"{WALK_REQUESTS}.at(-1).action === 'stop'")
            stop = page.evaluate(f"{WALK_REQUESTS}.at(-1)")
            assert stop == {
                "type": "siro.desktop.walk",
                "v": 1,
                "action": "stop",
                "id": request["id"],
            }
            assert page.evaluate("window.__siroVrm.activity()") == "walk_stop"
            page.wait_for_function("window.__siroVrm.activity() === 'idle'", timeout=8000)

            # No room (or the chat is open): the host refuses and she stays where she is.
            request = menu_stroll()
            host({"id": request["id"], "state": "refused", "reason": "room"})
            page.wait_for_function("window.__siroVrm.stroll() === null")
            assert page.evaluate("window.__siroVrm.activity()") == "idle"

            # No host at all: after a second she gives up, and calls off any late start.
            request = menu_stroll()
            page.wait_for_function("window.__siroVrm.stroll() === null", timeout=3000)
            page.wait_for_function(f"{WALK_REQUESTS}.at(-1).action === 'stop'")
            assert page.evaluate("window.__siroVrm.activity()") == "idle"
            assert not gateway.received[1:], "strolling stays between the renderer and the host"
        finally:
            browser.close()


def test_desktop_draws_lightly_when_resting_and_not_at_all_when_hidden(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway, "?presentation=desktop")
        try:
            ready_renderer(page, gateway)
            # Drawn at twice the screen's pixels, the downscale smooths her edges: no multisampling.
            graphics = page.evaluate("window.__siroVrm.graphics()")
            assert graphics["pixelRatio"] >= 2 and graphics["antialias"] is False
            assert graphics["renderer"]
            page.wait_for_function("window.__siroVrm.resting()", timeout=15000)
            start = page.evaluate("window.__siroVrm.frames()")
            page.wait_for_timeout(2000)
            drawn = page.evaluate("window.__siroVrm.frames()") - start
            assert 0 < drawn <= 2 * 20 + 2, drawn
            page.evaluate("Object.defineProperty(document, 'hidden', { get: () => true })")
            page.wait_for_timeout(200)
            start = page.evaluate("window.__siroVrm.frames()")
            page.wait_for_timeout(1000)
            assert page.evaluate("window.__siroVrm.frames()") == start
        finally:
            browser.close()


def test_chat_input_shares_its_position_with_the_character() -> None:
    html = (ROOT / "src/siro/services/presentation/static/index.html").read_text(encoding="utf-8")
    hook = html[html.index("const shareFocus") : html.index('chatInput.addEventListener("focus"')]
    assert '"siro.view.focus", v: 1' in hook and "location.origin" in hook
    assert 'chatInput.addEventListener("input", shareFocus)' in html


def test_desktop_owner_replacement_detaches_without_reconnect(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=synthetic_vrm())
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway, "?presentation=desktop")
        try:
            page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=60000)
            deadline = time.monotonic() + 10
            while not gateway.received and time.monotonic() < deadline:
                page.wait_for_timeout(50)
            assert gateway.received[0] == {
                "type": "authenticate",
                "token": "synthetic-token",
                "presentation": "desktop",
            }
            assert page.evaluate("document.documentElement.dataset.siroPresentation") == "desktop"
            assert gateway.socket is not None
            gateway.socket.close(code=1000, reason="renderer replaced")
            page.wait_for_function("window.__posted.some(m => m.type === 'siro.renderer.detached')")
            page.wait_for_timeout(1500)
            assert gateway.sessions == 1
        finally:
            browser.close()


def test_missing_model_is_reported_and_never_connects(tmp_path: Path) -> None:
    gateway = MockGateway(built_renderer(tmp_path), model=None)
    with sync_playwright() as playwright:
        browser, page = open_renderer(playwright, gateway)
        try:
            page.wait_for_function(
                "document.documentElement.dataset.siroRendererError === 'model'", timeout=60000
            )
            assert "載入失敗" in page.inner_text("#status")
            page.wait_for_timeout(500)
            assert gateway.sessions == 0
            assert gateway.socket is None
        finally:
            browser.close()


def test_launcher_prefers_prepared_vrm_over_live2d_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location(
        "companion_launcher_tests", Path(__file__).with_name("test_companion_launcher.py")
    )
    assert spec is not None and spec.loader is not None
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    module = helpers.launcher(tmp_path, monkeypatch)
    monkeypatch.setenv("SIRO_OPENAI_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv(
        "SIRO_OPENAI_API_KEY", "synthetic-not-a-real-key"
    )  # pragma: allowlist secret
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    binary = tmp_path / "target/debug/siro-runtime"
    binary.parent.mkdir(parents=True)
    binary.touch()
    demo = tmp_path / "models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo"
    (demo / "src").mkdir(parents=True)
    (demo / "src/main.ts").write_text("// synthetic live2d sample")
    renderer_fixture_dir = tmp_path / "models/vrm-renderer"
    renderer_fixture_dir.mkdir(parents=True)
    (renderer_fixture_dir / "index.html").write_text("synthetic vrm renderer")
    write_model(tmp_path / "config/body-assets/siro-vrm")
    calls: list[object] = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(module.os, "execv", lambda *a: calls.append(a))
    module.main()
    assert os.environ["SIRO_VRM_DIST"] == str(renderer_fixture_dir)
    assert os.environ["SIRO_VRM_MODEL_MANIFEST"].endswith(
        "config/body-assets/siro-vrm/asset-manifest.json"
    )
    assert "SIRO_LIVE2D_DIST" not in os.environ
    assert not any("repair_companion_renderer.py" in str(call) for call in calls)
    assert len(calls) == 1  # only the gateway process; no Live2D rebuild
