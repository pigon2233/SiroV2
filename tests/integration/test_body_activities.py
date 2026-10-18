"""CP-P01: activity cues from real turn events, reconnect projection and the kill switch."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from siro.adapters.body.visual_pack import VisualPack, load_visual_pack
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.mock import MockModel
from siro.ports.body import SpeechIntent
from siro.ports.models import Privacy
from siro.services.presentation.gateway import GatewayHub, create_app, load_body_pack
from siro.services.presentation.integrated import IntegratedCompanion

PACK = Path("assets/companion/haru-upperbody/0.1.0")


def make_pack(tmp_path: Path) -> tuple[Path, Path]:
    """Copy the committed pack and bind it to synthetic model files (no licensed assets)."""
    pack_dir = tmp_path / "pack"
    shutil.copytree(PACK, pack_dir)
    model_root = tmp_path / "dist"
    pack = json.loads((pack_dir / "pack.json").read_text())
    compatibility = {}
    for relative in pack["compatibility"]:
        data = f"synthetic {relative}".encode()
        target = model_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        compatibility[relative] = hashlib.sha256(data).hexdigest()
    pack["compatibility"] = compatibility
    (pack_dir / "pack.json").write_text(json.dumps(pack))
    return pack_dir, model_root


@pytest.fixture
def pack(tmp_path: Path) -> VisualPack:
    return load_visual_pack(*make_pack(tmp_path))


class RecordingTransport:
    def __init__(self) -> None:
        self.connected = True
        self.messages: list[dict[str, object]] = []

    async def send(self, message: dict[str, object]) -> None:
        self.messages.append(message)


class RecordingSocket:
    def __init__(self) -> None:
        self.messages: list[object] = []

    async def send_json(self, data: object) -> None:
        self.messages.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason


def activities(messages: list[dict[str, object]]) -> list[str]:
    return [str(m["activity"]) for m in messages if m["type"] == "body.activity"]


@pytest.mark.asyncio
async def test_adapter_without_pack_sends_nothing_new() -> None:
    transport = RecordingTransport()
    body = MinimalWebBodyAdapter(transport)
    assert not await body.set_activity("thinking", generation_id="g1")
    assert await body.speak(SpeechIntent("s1", "你好", "g1"))
    assert not await body.stop_activity()
    assert [m["type"] for m in transport.messages] == ["body.speech"]


@pytest.mark.asyncio
async def test_adapter_activity_messages_and_speaking_lifetime(pack: VisualPack) -> None:
    transport = RecordingTransport()
    body = MinimalWebBodyAdapter(transport, activity_pack=pack)
    assert not await body.set_activity("walk", generation_id="g1")
    assert await body.set_activity("thinking", generation_id="g1")
    start = transport.messages[-1]
    assert start == {
        "v": 1,
        "type": "body.activity",
        "op": "start",
        "instance_id": start["instance_id"],
        "generation_id": "g1",
        "activity": "thinking",
        "pack_version": "0.1.0",
    }
    assert await body.speak(SpeechIntent("s1", "嗨", "g2"))
    assert await body.speak(SpeechIntent("s2", "長" * 500, "g3"))
    poses = [m for m in transport.messages if m.get("activity") == "speaking_pose"]
    assert [(m["generation_id"], m["ttl_s"]) for m in poses] == [("g2", 2.0), ("g3", 30.0)]
    assert await body.stop_activity()
    stop = transport.messages[-1]
    assert (stop["op"], stop["instance_id"], stop["generation_id"]) == (
        "stop",
        poses[-1]["instance_id"],
        "g3",
    )
    assert not await body.stop_activity()
    with pytest.raises(ValueError, match="ttl"):
        await body.set_activity("idle", generation_id="g4", ttl_seconds=0)


@pytest.mark.asyncio
async def test_reconnect_projects_only_the_latest_durable_activity(pack: VisualPack) -> None:
    transport = WebSocketBodyTransport()
    body = MinimalWebBodyAdapter(transport, activity_pack=pack)
    first = RecordingSocket()
    await transport.attach(first)
    assert await body.set_activity("reading_pose", generation_id="g1")
    await asyncio.sleep(0)
    sent = first.messages[-1]

    second = RecordingSocket()
    await transport.attach(second)
    await asyncio.sleep(0)
    # Identical ids: a renderer that kept running treats it as a duplicate and keeps its phase.
    assert second.messages == [sent]

    assert await body.speak(SpeechIntent("s1", "好", "g2"))
    third = RecordingSocket()
    await transport.attach(third)
    await asyncio.sleep(0)
    assert third.messages == []  # Timed speaking poses and speech are never replayed.

    assert await body.set_activity("nod", generation_id="g3")
    fourth = RecordingSocket()
    await transport.attach(fourth)
    await asyncio.sleep(0)
    assert fourth.messages == []  # One-shot gestures do not restart after reconnect.
    await transport.detach()


def test_pack_route_serves_validated_data_or_reports_unavailable(pack: VisualPack) -> None:
    with TestClient(create_app(body_pack=pack)) as client:
        response = client.get("/v1/body/pack")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["schema"] == "siro.visual.pack.runtime.v0"
        assert payload["version"] == "0.1.0" and payload["gaze"] == "unsupported"
    with TestClient(create_app()) as client:
        response = client.get("/v1/body/pack")
        assert (response.status_code, response.json()) == (404, {"state": "unavailable"})


def test_kill_switch_and_bad_packs_keep_the_existing_character(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_dir, model_root = make_pack(tmp_path)
    monkeypatch.setenv("SIRO_BODY_PACK", str(pack_dir))
    loaded, state = load_body_pack(model_root)
    assert loaded is not None and state == "ready"
    assert load_body_pack(None) == (None, "no_renderer")
    monkeypatch.setenv("SIRO_BODY_ACTIVITIES", "0")
    assert load_body_pack(model_root) == (None, "disabled")
    monkeypatch.setenv("SIRO_BODY_ACTIVITIES", "yes")
    with pytest.raises(ValueError, match="SIRO_BODY_ACTIVITIES"):
        load_body_pack(model_root)
    monkeypatch.setenv("SIRO_BODY_ACTIVITIES", "1")
    next(model_root.rglob("*.moc3")).write_bytes(b"another model")
    loaded, state = load_body_pack(model_root)
    assert loaded is None and state.startswith("unsupported: model file")
    monkeypatch.setenv("SIRO_BODY_PACK", str(tmp_path / "missing"))
    assert load_body_pack(model_root) == (None, "unsupported: pack.json is missing")


def test_turn_events_drive_low_frequency_activity_cues(tmp_path: Path, pack: VisualPack) -> None:
    origin = "http://testserver"
    hub = GatewayHub()
    recording = RecordingTransport()
    controller = IntegratedCompanion(
        tmp_path / "data",
        MockModel(("你好", "、我是 SIRO。")),
        hub,
        MinimalWebBodyAdapter(recording, activity_pack=pack),
        privacy=Privacy.LOCAL_ONLY,
    )
    app = create_app(
        allowed_origins={origin},
        hub=hub,
        body_transport=WebSocketBodyTransport(),
        on_turn=controller.respond,
        on_cancel=controller.cancel,
    )
    with TestClient(app) as client:
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        with client.websocket_connect("/ws/control", headers={"origin": origin}) as socket:
            socket.send_json({"type": "authenticate", "token": token})
            assert socket.receive_json()["type"] == "snapshot"
            response = client.post(
                "/v1/conversations/browser/turns",
                headers={"authorization": f"Bearer {token}"},
                json={"text": "介紹你自己"},
            )
            assert response.status_code == 200
            messages = [socket.receive_json() for _ in range(6)]
            assert messages[-1]["type"] == "assistant_terminal"
            deadline = time.monotonic() + 5
            while "speaking_pose" not in activities(recording.messages):
                assert time.monotonic() < deadline, recording.messages
                time.sleep(0.01)
    assert activities(recording.messages) == ["thinking", "idle", "speaking_pose"]
    cues = [m for m in recording.messages if m["type"] == "body.activity"]
    assert cues[0]["generation_id"] == cues[1]["generation_id"]
    speech = next(m for m in recording.messages if m["type"] == "body.speech")
    assert cues[2]["generation_id"] == speech["generation_id"]
    # The cue follows the speech intent; it never replaces the speech owner or the emotion.
    types = [m["type"] for m in recording.messages]
    assert types.index("body.speech") < len(types) - 1 - types[::-1].index("body.activity")
    assert "body.emotion" in types
