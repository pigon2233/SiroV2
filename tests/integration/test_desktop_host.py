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


def test_native_microphone_gi_properties_keep_dialog_and_reject_other_devices() -> None:
    source = Path("desktop/host.js").read_text()
    start = source.index("function restrict(view)")
    end = source.index("\nfunction evaluate(", start)
    script = (
        r"""
const assert=require('node:assert/strict'), dialogs=[], handlers=new Map(), window={};
let allowedOrigin=true;
const permitted=()=>allowedOrigin;
class Request {
 constructor(audio,video){this.is_for_audio_device=audio;this.is_for_video_device=video;this.allowed=0;this.denied=0;}
 allow(){this.allowed++;} deny(){this.denied++;}
}
const WebKit={UserMediaPermissionRequest:Request};
const Gtk={MessageType:{QUESTION:1},ButtonsType:{NONE:0},ResponseType:{CANCEL:0,ACCEPT:1},
 MessageDialog:class {
  constructor(options){this.options=options;dialogs.push(this);}
  add_button(){} connect(_name,callback){this.response=callback;}
  show_all(){} destroy(){this.closed=true;}
 }};
const view={connect:(name,fn)=>handlers.set(name,fn),get_uri:()=> 'http://127.0.0.1/desktop'};
"""
        + source[start:end]
        + r"""
restrict(view);
const permission=handlers.get('permission-request');
const audio=new Request(true,false);
assert.equal(permission(view,audio),true);
assert.equal(dialogs.length,1);assert.equal(audio.allowed,0);assert.equal(audio.denied,0);
dialogs[0].response(dialogs[0],Gtk.ResponseType.ACCEPT);
assert.equal(audio.allowed,1);assert.equal(dialogs[0].closed,true);
for(const [a,v] of [[true,true],[false,true],[false,false],[undefined,undefined]]){
 const request=new Request(a,v);permission(view,request);
 assert.equal(request.denied,1);assert.equal(request.allowed,0);
}
const unknown={denied:0,deny(){this.denied++;}};
permission(view,unknown);assert.equal(unknown.denied,1);
allowedOrigin=false;
const foreign=new Request(true,false);permission(view,foreign);assert.equal(foreign.denied,1);
allowedOrigin=true;
const moved=new Request(true,false);permission(view,moved);allowedOrigin=false;
dialogs.at(-1).response(dialogs.at(-1),Gtk.ResponseType.ACCEPT);
assert.equal(moved.denied,1);assert.equal(moved.allowed,0);
"""
    )
    subprocess.run(["node", "-e", script], check=True, timeout=10)


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


def test_walk_travel_follows_the_stride_curve_and_stays_in_the_work_area() -> None:
    source = Path(__file__).parents[2] / "desktop/wander.mjs"
    script = f"""
import assert from 'node:assert/strict';
import {{ease, rampDistance, stopPlan, walkPlan, walkRoom}} from {json.dumps(source.as_uri())};
const close=(a,b,eps=1e-6)=>assert(Math.abs(a-b)<eps,`${{a}} != ${{b}}`);
// The ramp curve is the one walk_start/walk_stop blend the stride with; its area is one half.
close(ease(0),0);close(ease(.5),.5);close(ease(1),1);close(rampDistance(1),.5);
let sum=0;for(let i=0;i<10000;i++)sum+=ease((i+.5)/10000)/10000;close(sum,.5,1e-6);
// A walk: half a ramp of distance in each ramp, full speed in between, exact at the end.
const plan=walkPlan(500,200,1.4);
close(plan.cruise,1.1);close(plan.duration,3.9);close(plan.at(1.4),140);close(plan.at(2.5),360);
close(plan.at(plan.duration),500);assert.equal(plan.at(-1),0);assert.equal(plan.at(99),500);
// Position never jumps or runs backwards, and the speed never exceeds the stride's.
let last=0;for(let t=0;t<=plan.duration;t+=1/240){{const x=plan.at(t);
 assert(x>=last-1e-9);assert(x-last<=200/240+1e-6);last=x;}}
// Too little room for the two ramps: no walk rather than a skating one.
assert.equal(walkPlan(200,200,1.4),null);assert.equal(walkPlan(0,200,1),null);
assert.equal(walkPlan(NaN,200,1),null);
// Stopping early settles over one ramp from the speed she has, never past the room left.
const cut=stopPlan(plan,2);close(cut.remaining,140);close(cut.at(1.4),140);close(cut.at(0),0);
const early=stopPlan(plan,.7);close(early.remaining,70);  // half speed mid-ramp
const late=stopPlan(plan,3.8);assert(late.remaining<=500-plan.at(3.8)+1e-9);
// Room: the pet pane stays 8 px inside the work area; 0 picks the roomier side.
const area={{x:0,width:1920}};
assert.deepEqual(walkRoom(1000,0,360,area,0,800),{{direction:-1,distance:800}});
assert.deepEqual(walkRoom(1000,0,360,area,1,800),{{direction:1,distance:552}});
assert.deepEqual(walkRoom(5,0,360,area,-1,800),{{direction:-1,distance:0}});
assert.deepEqual(walkRoom(1552,0,360,{{x:0,width:1920}},1,50),{{direction:1,distance:0}});
assert.deepEqual(walkRoom(1100,20,320,{{x:1920,width:1280}},0,100),{{direction:1,distance:100}});
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, timeout=10)


def test_host_walk_messages_are_validated_and_taken_over_by_drag_chat_and_layout() -> None:
    source = Path("desktop/host.js").read_text()
    # The native side only walks on a fully validated request, and anything that takes the
    # window over halts it first.
    handler = source[source.index("message.type === 'desktop.walk' &&") :]
    handler = handler[: handler.index("startWalk(message);")]
    for check in (
        "message.id.length <= 40",
        "[-1, 0, 1].includes(message.direction)",
        "message.distance <= 4096",
        "message.speed <= 2000",
        "message.ramp <= 5",
        "message.delay <= 5",
    ):
        assert check in handler
    assert "haltWalk('dragged');" in source[source.index("message.type === 'desktop.move'") :]
    layout = source[source.index("function applyLayout()") :]
    assert layout.index("haltWalk('layout');") < layout.index("window.move(")
    assert "haltWalk('hidden'); window.iconify();" in source
    assert "window.connect('unmap', () => haltWalk('hidden'));" in source
    assert "if (lastChat || !area || !layout) return walkReport(" in source


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
