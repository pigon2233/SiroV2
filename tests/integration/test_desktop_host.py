from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from siro.adapters.body.web import WebSocketBodyTransport
from siro.services.presentation.gateway import create_app

ORIGIN = "http://127.0.0.1:8000"


def test_native_mask_passes_clear_pixels_and_keeps_odd_edge() -> None:
    source = Path(__file__).parents[2] / "desktop/input-mask.mjs"
    script = f"""
import {{inputMask}} from {json.dumps(source.as_uri())};
const image=new Uint8Array(7*7*4);
if(inputMask(image,7,7,28,4).occupied!==0)throw Error('clear blocks');
image[(6*7+6)*4+3]=255;
if(inputMask(image,7,7,28,4).occupied!==1)throw Error('odd edge lost');
image.fill(255);
if(inputMask(image,7,7,28,4).occupied!==49)throw Error('opaque incomplete');
for(const args of [[image,0,7,28,4],[image,7,7,1,4],[[],7,7,28,4]]){{
 let rejected=false;try{{inputMask(...args)}}catch(e){{rejected=true}}
 if(!rejected)throw Error('invalid geometry accepted');
}}
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, timeout=10)


def test_desktop_requires_real_prepared_renderer() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/desktop").status_code == 503


def test_desktop_priority_then_explicit_web_handoff(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("synthetic renderer")
    body = WebSocketBodyTransport()
    emotion = {"v": 1, "type": "body.emotion", "name": "sad", "intensity": 0.4}
    body.remember_emotion(emotion)
    with TestClient(create_app(live2d_dist=tmp_path, body_transport=body)) as client:
        token = client.post("/v1/session", headers={"origin": ORIGIN}).json()["token"]
        headers = {"authorization": f"Bearer {token}"}
        desktop = client.get("/desktop")
        assert 'class="siro-desktop"' in desktop.text
        assert "/live2d/?presentation=desktop" in desktop.text
        assert client.get("/static/desktop.js").status_code == 200
        assert client.get("/static/desktop.css").headers["content-type"].startswith("text/css")
        with client.websocket_connect("/ws/body", headers={"origin": ORIGIN}) as pet:
            pet.send_json({"type": "authenticate", "token": token, "presentation": "desktop"})
            assert pet.receive_json() == emotion
            page = client.get("/").text
            assert 'src="about:blank"' in page
            assert 'class="siro-control"' in page
            assert (
                client.get("/v1/runtime", headers=headers).json()["presentation"]["owner"]
                == "desktop"
            )
            with client.websocket_connect("/ws/body", headers={"origin": ORIGIN}) as web:
                web.send_json({"type": "authenticate", "token": token})
                with pytest.raises(WebSocketDisconnect) as rejected:
                    web.receive_json()
                assert rejected.value.reason == "desktop owner active"
            assert body.connected
        # New explicit web attachment after native exit receives only latest emotion, no speech.
        with client.websocket_connect("/ws/body", headers={"origin": ORIGIN}) as web:
            web.send_json({"type": "authenticate", "token": token})
            assert web.receive_json() == emotion
        assert 'src="about:blank"' in client.get("/?view=control").text


def test_body_rejects_malformed_presentation_without_detaching_owner() -> None:
    with TestClient(create_app()) as client:
        token = client.post("/v1/session", headers={"origin": ORIGIN}).json()["token"]
        with client.websocket_connect("/ws/body", headers={"origin": ORIGIN}) as socket:
            socket.send_json({"type": "authenticate", "token": token, "presentation": {}})
            with pytest.raises(WebSocketDisconnect) as rejected:
                socket.receive_json()
            assert rejected.value.code == 1008
