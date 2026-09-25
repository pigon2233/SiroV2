from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from siro.services.audio.protocol import AudioFrame
from siro.services.presentation.gateway import GatewayHub, create_app

ORIGIN = "http://testserver"


def issue_token(client: TestClient) -> str:
    response = client.post("/v1/session", headers={"origin": ORIGIN})
    assert response.status_code == 200
    return str(response.json()["token"])


def test_http_auth_snapshot_and_control_websocket() -> None:
    app = create_app(allowed_origins={ORIGIN})
    client = TestClient(app)
    assert client.get("/health/live").json() == {"state": "alive"}
    body_page = client.get("/body")
    assert body_page.status_code == 200
    assert "placeholder, not Live2D" in body_page.text
    assert client.get("/v1/snapshot").status_code == 401
    assert client.post("/v1/session", headers={"origin": "https://evil.invalid"}).status_code == 403
    token = issue_token(client)
    authorization = {"authorization": f"Bearer {token}"}
    snapshot = client.get("/v1/snapshot", headers=authorization).json()
    assert snapshot["identity"]["identity_id"] == "siro"
    assert "memories" not in snapshot

    with client.websocket_connect("/ws/control", headers={"origin": ORIGIN}) as socket:
        socket.send_json({"type": "authenticate", "token": token})
        assert socket.receive_json()["type"] == "snapshot"
        response = client.post(
            "/v1/conversations/browser/turns",
            headers=authorization,
            json={"text": "hello"},
        )
        turn_id = response.json()["turn_id"]
        started = socket.receive_json()
        assert started == {
            "type": "turn_started",
            "session_id": "browser",
            "turn_id": turn_id,
        }
        assert (
            client.post(
                f"/v1/turns/{turn_id}/cancel",
                headers=authorization,
                json={"reason": "user"},
            ).status_code
            == 200
        )
        assert socket.receive_json()["type"] == "turn_cancelled"


def test_websocket_rejects_bad_origin_and_reconnects_100_times() -> None:
    app = create_app(allowed_origins={ORIGIN})
    client = TestClient(app)
    token = issue_token(client)
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/control", headers={"origin": "https://evil.invalid"}),
    ):
        pass

    for _ in range(100):
        with client.websocket_connect("/ws/control", headers={"origin": ORIGIN}) as socket:
            socket.send_json({"type": "authenticate", "token": token})
            assert socket.receive_json()["type"] == "snapshot"
    assert app.state.gateway_hub.client_count == 0


def test_audio_channels_negotiate_frames_and_enforce_single_playback_owner() -> None:
    app = create_app(allowed_origins={ORIGIN})
    client = TestClient(app)
    token = issue_token(client)
    metadata = {
        "stream_id": "stream",
        "session_id": "session",
        "turn_id": "turn",
        "generation_id": "generation",
        "speech_id": "speech",
        "sample_rate": 16000,
    }
    with client.websocket_connect("/ws/audio/input", headers={"origin": ORIGIN}) as socket:
        socket.send_json({"token": token, "owner_id": "microphone", "metadata": metadata})
        assert socket.receive_json() == {"type": "audio_ready", "sample_rate": 16000}
        socket.send_bytes(AudioFrame(1, 0, 0, bytes(640)).encode())
        assert socket.receive_json()["result"] == "accepted"

    with client.websocket_connect("/ws/audio/output", headers={"origin": ORIGIN}) as first:
        first.send_json({"token": token, "owner_id": "audio-service", "metadata": metadata})
        assert first.receive_json()["owner_id"] == "audio-service"
        with client.websocket_connect("/ws/audio/output", headers={"origin": ORIGIN}) as second:
            second.send_json({"token": token, "owner_id": "renderer", "metadata": metadata})
            with pytest.raises(WebSocketDisconnect) as error:
                second.receive_json()
            assert error.value.code == 1008


def test_live2d_distribution_is_only_mounted_when_configured(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>licensed renderer</title>", encoding="utf-8")
    configured = TestClient(create_app(live2d_dist=tmp_path))
    assert configured.get("/live2d/").text == "<title>licensed renderer</title>"

    unconfigured = TestClient(create_app())
    assert unconfigured.get("/live2d/").status_code == 404


class FakeSocket:
    def __init__(self, *, blocked: bool = False, delay: float = 0) -> None:
        self.sent: list[object] = []
        self.closed = False
        self.delay = delay
        self.blocker = asyncio.Event()
        if not blocked:
            self.blocker.set()
        self.active_sends = 0
        self.max_active_sends = 0

    async def send_json(self, data: object) -> None:
        self.active_sends += 1
        self.max_active_sends = max(self.max_active_sends, self.active_sends)
        try:
            await self.blocker.wait()
            if self.delay:
                await asyncio.sleep(self.delay)
            self.sent.append(data)
        finally:
            self.active_sends -= 1

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason
        self.closed = True
        self.blocker.set()


class AlreadyDisconnectedSocket(FakeSocket):
    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason
        raise WebSocketDisconnect(code=1006)


@pytest.mark.asyncio
async def test_slow_client_isolated_and_each_client_has_one_writer() -> None:
    hub = GatewayHub(urgent_capacity=2, normal_capacity=4)
    slow, fast = FakeSocket(blocked=True), FakeSocket(delay=0.001)
    await hub.connect(slow, {"type": "snapshot"})
    fast_channel = await hub.connect(fast, {"type": "snapshot"})
    await asyncio.sleep(0)

    for index in range(12):
        await hub.broadcast({"type": "delta", "index": index})
        await asyncio.sleep(0.002)
    await asyncio.sleep(0.03)

    assert slow.closed
    assert hub.client_count == 1
    assert any(isinstance(item, dict) and item.get("index") == 11 for item in fast.sent)
    assert fast.max_active_sends == 1
    await hub.disconnect(fast_channel)


@pytest.mark.asyncio
async def test_many_producers_still_use_single_socket_writer() -> None:
    hub = GatewayHub(normal_capacity=64)
    socket = FakeSocket(delay=0.001)
    channel = await hub.connect(socket, {"type": "snapshot"})

    async def producer(index: int) -> None:
        await hub.broadcast({"type": "event", "index": index})

    await asyncio.gather(*(producer(index) for index in range(50)))
    await asyncio.sleep(0.1)
    assert socket.max_active_sends == 1
    assert len(socket.sent) == 51
    await hub.disconnect(channel)
    assert not [
        task for task in asyncio.all_tasks() if task.get_name().startswith("gateway-writer-")
    ]


@pytest.mark.asyncio
async def test_disconnect_cleanup_is_idempotent_when_peer_is_already_gone() -> None:
    hub = GatewayHub()
    channel = await hub.connect(AlreadyDisconnectedSocket(), {"type": "snapshot"})
    await hub.disconnect(channel)
    await hub.disconnect(channel)
    assert hub.client_count == 0
