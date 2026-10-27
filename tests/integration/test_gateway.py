from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from siro.persistence.sqlite import SQLiteStore
from siro.services.audio.protocol import AudioFrame
from siro.services.audio.stt import MockSpeechToText
from siro.services.presentation.gateway import (
    GatewayHub,
    GatewayState,
    _application_request,
    create_app,
)
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

ORIGIN = "http://testserver"


def issue_token(client: TestClient) -> str:
    response = client.post("/v1/session", headers={"origin": ORIGIN})
    assert response.status_code == 200
    return str(response.json()["token"])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("幫我打開 Firefox", "firefox"),
        ("請開啟檔案", "files"),
        ("啟動終端機", "terminal"),
        ("打開計算機", "calculator"),
        ("open visual studio code", "vscode"),
        ("我喜歡 Firefox", None),
    ],
)
def test_allowlisted_application_intent(text: str, expected: str | None) -> None:
    assert _application_request(text) == expected


def test_http_auth_snapshot_and_control_websocket() -> None:
    app = create_app(allowed_origins={ORIGIN})
    client = TestClient(app)
    assert client.get("/health/live").json() == {"state": "alive"}
    body_page = client.get("/body")
    assert body_page.status_code == 200
    assert "placeholder, not Live2D" in body_page.text
    audio_test = client.get("/audio-field-test")
    assert audio_test.status_code == 200
    assert "不傳送或保存錄音" in audio_test.text
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


def test_gateway_shutdown_marks_inflight_and_calls_cancel() -> None:
    state = GatewayState()
    state.active_turns["session"] = {"turn_id": "turn-1", "state": "responding"}
    cancelled: list[tuple[str, str]] = []

    async def cancel(turn_id: str, reason: str) -> None:
        cancelled.append((turn_id, reason))

    with TestClient(create_app(state=state, on_cancel=cancel)):
        assert state.health["core"] == "healthy"
    assert state.health["core"] == "draining"
    assert state.active_turns["session"]["state"] == "interrupted_shutdown"
    assert cancelled == [("turn-1", "service shutdown")]


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


def test_authenticated_microphone_transcription_obeys_kill_switch() -> None:
    state = GatewayState()
    state.kill_switches["microphone"] = False
    stt = MockSpeechToText("你好 SIRO", "zh")
    client = TestClient(create_app(allowed_origins={ORIGIN}, state=state, speech_to_text=stt))
    token = issue_token(client)
    headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}

    denied = client.post("/v1/audio/transcriptions", headers=headers, content=b"wav")
    assert denied.status_code == 403
    state.kill_switches["microphone"] = True
    accepted = client.post("/v1/audio/transcriptions?language=zh", headers=headers, content=b"wav")
    assert accepted.status_code == 200
    assert accepted.json() == {"text": "你好 SIRO", "language": "zh", "final": True}
    assert stt.calls == 1


def test_cloud_speech_recognition_obeys_cloud_switch_and_local_stays_available() -> None:
    class CloudSpeechToText(MockSpeechToText):
        is_cloud = True

    state = GatewayState()
    state.kill_switches["cloud"] = False
    cloud = CloudSpeechToText("雲端", "zh")
    client = TestClient(create_app(allowed_origins={ORIGIN}, state=state, speech_to_text=cloud))
    token = issue_token(client)
    headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
    denied = client.post("/v1/audio/transcriptions", headers=headers, content=b"wav")
    assert denied.status_code == 403
    assert cloud.calls == 0
    state.kill_switches["cloud"] = True
    assert (
        client.post("/v1/audio/transcriptions", headers=headers, content=b"wav").status_code == 200
    )

    local_state = GatewayState()
    local_state.kill_switches["cloud"] = False
    local = MockSpeechToText("本機", "zh")
    local_client = TestClient(
        create_app(allowed_origins={ORIGIN}, state=local_state, speech_to_text=local)
    )
    local_token = issue_token(local_client)
    local_headers = {"origin": ORIGIN, "authorization": f"Bearer {local_token}"}
    ok = local_client.post("/v1/audio/transcriptions", headers=local_headers, content=b"wav")
    assert ok.status_code == 200
    assert local.calls == 1


def test_authenticated_neural_speech_obeys_cloud_switch() -> None:
    class FakeSpeech:
        async def render(self, text: str, *, rate: float, pitch: float, energy: float) -> bytes:
            assert (text, rate, pitch, energy) == ("你好", 1.1, 0.2, 0.7)
            return b"mp3-audio"

    state = GatewayState()
    state.kill_switches["cloud"] = False
    state.routes["tts"] = "edge:test"
    client = TestClient(
        create_app(allowed_origins={ORIGIN}, state=state, text_to_speech=FakeSpeech())
    )
    token = issue_token(client)
    headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
    body = {"text": "你好", "rate": 1.1, "pitch": 0.2, "energy": 0.7}
    assert client.post("/v1/audio/speech", headers=headers, json=body).status_code == 403
    state.kill_switches["cloud"] = True
    response = client.post("/v1/audio/speech", headers=headers, json=body)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"mp3-audio"


def test_browser_proposal_requires_owner_approval_and_tools_switch(tmp_path: Path) -> None:
    calls: list[str] = []

    async def browser_tool(url: str) -> dict[str, str]:
        calls.append(url)
        return {
            "url": url,
            "title": "Example",
            "text": "readback",
            "screen_version": "v1",
        }

    store = SQLiteStore(tmp_path / "tools.db")
    asyncio.run(store.initialize())

    async def execute(arguments: dict[str, object]) -> object:
        return await browser_tool(str(arguments["url"]))

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"browser.navigate+read": execute}
    )
    state = GatewayState()
    state.kill_switches["tools"] = False

    client = TestClient(
        create_app(
            allowed_origins={ORIGIN},
            state=state,
            on_browser_tool=browser_tool,
            tool_orchestrator=orchestrator,
            legacy_shortcuts=True,
        )
    )
    token = issue_token(client)
    headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
    with client.websocket_connect("/ws/control", headers={"origin": ORIGIN}) as socket:
        socket.send_json({"type": "authenticate", "token": token})
        assert socket.receive_json()["type"] == "snapshot"
        response = client.post(
            "/v1/conversations/browser/turns",
            headers=headers,
            json={"text": "請開啟 https://example.test/page 並讀取"},
        )
        assert response.status_code == 200
        first_two = [socket.receive_json(), socket.receive_json()]
        assert {message["type"] for message in first_two} == {"turn_started", "tool_proposal"}
        proposal = next(message for message in first_two if message["type"] == "tool_proposal")
        assert proposal["type"] == "tool_proposal"
        assert proposal["scope"] == "https://example.test"
        endpoint = f"/v1/tool-proposals/{proposal['proposal_id']}/approve"
        assert client.post(endpoint, headers=headers, json={"approved": True}).status_code == 403
        assert calls == []
        client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": True})
        assert socket.receive_json()["type"] == "kill_switch"
        assert client.post(endpoint, headers=headers, json={"approved": True}).status_code == 200
        assert socket.receive_json()["type"] == "tool_started"
        result = socket.receive_json()
        assert result["type"] == "tool_result"
        assert result["result"]["text"] == "readback"
    assert calls == ["https://example.test/page"]


def test_firefox_request_becomes_allowlisted_process_proposal(tmp_path: Path) -> None:
    calls: list[str] = []

    async def application_tool(application: str) -> dict[str, str]:
        calls.append(application)
        return {"application": "Firefox", "state": "running", "pid": "123"}

    store = SQLiteStore(tmp_path / "tools.db")
    asyncio.run(store.initialize())

    async def execute(arguments: dict[str, object]) -> object:
        return await application_tool(str(arguments["application"]))

    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {"process.start": execute})

    state = GatewayState()
    state.kill_switches["tools"] = True
    client = TestClient(
        create_app(
            allowed_origins={ORIGIN},
            state=state,
            on_application_tool=application_tool,
            tool_orchestrator=orchestrator,
            legacy_shortcuts=True,
        )
    )
    token = issue_token(client)
    headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
    with client.websocket_connect("/ws/control", headers={"origin": ORIGIN}) as socket:
        socket.send_json({"type": "authenticate", "token": token})
        socket.receive_json()
        response = client.post(
            "/v1/conversations/browser/turns",
            headers=headers,
            json={"text": "幫我打開firefox"},
        )
        assert response.status_code == 200
        first_two = [socket.receive_json(), socket.receive_json()]
        proposal = next(message for message in first_two if message["type"] == "tool_proposal")
        assert proposal["capability"] == "process.start"
        assert proposal["target"] == "firefox"
        assert proposal["scope"] == "allowlisted application: firefox"
        endpoint = f"/v1/tool-proposals/{proposal['proposal_id']}/approve"
        assert client.post(endpoint, headers=headers, json={"approved": True}).status_code == 200
        assert socket.receive_json()["type"] == "tool_started"
        result = socket.receive_json()
        assert result["result"] == {
            "application": "Firefox",
            "state": "running",
            "pid": "123",
        }
    assert calls == ["firefox"]


def test_live2d_distribution_is_only_mounted_when_configured(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>licensed renderer</title>", encoding="utf-8")
    configured = TestClient(create_app(live2d_dist=tmp_path))
    assert configured.get("/live2d/").text == "<title>licensed renderer</title>"
    configured_index = configured.get("/").text
    assert 'src="/live2d/"' in configured_index
    assert "Live2D 載入中" in configured_index

    unconfigured = TestClient(create_app())
    assert unconfigured.get("/live2d/").status_code == 404
    assert 'src="/body"' in unconfigured.get("/").text


@pytest.mark.parametrize("offline", [False, True])
@pytest.mark.parametrize("renderer", [False, True])
def test_homepage_persistently_identifies_demo_and_placeholder(
    tmp_path: Path, offline: bool, renderer: bool
) -> None:
    (tmp_path / "index.html").write_text("<title>renderer fixture</title>", encoding="utf-8")
    state = GatewayState(routes={"model": "offline" if offline else "cloud:synthetic"})
    client = TestClient(create_app(state=state, live2d_dist=tmp_path if renderer else None))
    html = client.get("/").text
    notice = html.split('<p id="runtime-notice"', 1)[1].split("</p>", 1)[0]
    assert ("hidden" not in notice.split(">", 1)[0]) == (offline or not renderer)
    assert ("離線示範。未連接正式對話模型" in notice) == offline
    assert ("回覆來自固定示範規則" in notice) == offline
    assert ("角色目前顯示替身" in notice) == (not renderer)
    assert ("scripts/start-runtime-product" in notice) == (offline or not renderer)
    # A successful socket handshake only clears transient connection errors.
    assert 'querySelector("#runtime-notice").hidden' not in html


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
