from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("chat_open", [False, True])
@pytest.mark.parametrize("report_enabled", [False, True])
def test_native_shape_sampling_never_writes_images(chat_open: bool, report_enabled: bool) -> None:
    run_shape(
        f"lastChat = {str(chat_open).lower()}; "
        f"reportDirectory = {repr('/synthetic/report') if report_enabled else 'null'};\n"
        "for (let i=0;i<120;i++) { updateShape(); callbacks.shift()(); }\n"
        "assert.equal(samples,120); assert.equal(masks.length,120);\n"
        "assert.equal(state.chat_open,lastChat); assert.equal(state.alpha,true);\n"
        "assert.deepEqual(imageWrites,[], 'sampling must not persist any WebView pixels');\n"
        "assert.equal(stateWrites,120); assert.equal(pendingSnapshot,false);\n"
    )


@pytest.mark.parametrize("initial_open", [False, True])
def test_chat_changes_during_snapshot_do_not_persist_private_pixels(initial_open: bool) -> None:
    run_shape(
        f"lastChat = {str(initial_open).lower()};\n"
        "updateShape(); lastChat=!lastChat; callbacks.shift()();\n"
        "assert.deepEqual(imageWrites,[]); assert.equal(masks.length,1);\n"
        "assert.equal(state.chat_open,lastChat);\n"
    )


def test_snapshot_failure_can_recover_without_a_temporary_image() -> None:
    run_shape(
        "broken=true; updateShape(); callbacks.shift()();\n"
        "assert.match(state.snapshot_error,/synthetic snapshot failure/);\n"
        "assert.equal(pendingSnapshot,false); assert.deepEqual(imageWrites,[]);\n"
        "broken=false; nullPixels=true; updateShape(); callbacks.shift()();\n"
        "assert.match(state.snapshot_error,/snapshot pixels are unavailable/);\n"
        "assert.equal(pendingSnapshot,false); assert.deepEqual(imageWrites,[]);\n"
        "nullPixels=false;\n"
        "broken=false; updateShape(); callbacks.shift()();\n"
        "assert.equal(masks.length,1); assert.deepEqual(imageWrites,[]);\n"
    )


def test_shape_guards_pending_loading_hidden_and_closed_views() -> None:
    run_shape(
        "hidden=true; updateShape(); assert.equal(callbacks.length,0); hidden=false;\n"
        "web.is_loading=true; updateShape(); assert.equal(callbacks.length,0);\n"
        "web.is_loading=false; updateShape(); updateShape();\n"
        "assert.equal(callbacks.length,1); window=null; callbacks.shift()();\n"
        "assert.equal(pendingSnapshot,false); assert.equal(masks.length,0);\n"
        "assert.deepEqual(imageWrites,[]);\n"
    )


def run_shape(checks: str) -> None:
    source = Path("desktop/host.js").read_text()
    start = source.index("function updateShape()")
    end = source.index("\nfunction activate()", start)
    harness = r"""
const assert=require('node:assert/strict');
let reportDirectory='/synthetic/report',lastChat=false,pendingSnapshot=false,ready=true;
let samples=0,lastRegion=0,stateWrites=0,broken=false,hidden=false,nullPixels=false;
const imageWrites=[],masks=[],callbacks=[],state={},scratch='/synthetic/temporary.png';
const surface={getWidth:()=>7,getHeight:()=>9,writeToPNG:path=>imageWrites.push(path)};
const image={get_pixels:()=>new Uint8Array(7*9*4),get_n_channels:()=>4,
 get_rowstride:()=>28,get_width:()=>7,get_height:()=>9,get_has_alpha:()=>true};
const Gdk={pixbuf_get_from_surface:(value,x,y,width,height)=>{
 assert.equal(value,surface);assert.deepEqual([x,y,width,height],[0,0,7,9]);
 return nullPixels?null:image;
}};
// The former file decoder remains available so the old implementation reaches
// the zero-write assertion rather than failing on a missing test double.
const GdkPixbuf={Pixbuf:{new_from_file:()=>image}};
const GLib={SOURCE_CONTINUE:1,build_filenamev:parts=>parts.join('/')};
const Cairo={Region:class {
 constructor(){this.rectangles=[];} unionRectangle(value){this.rectangles.push(value);}
 numRectangles(){return this.rectangles.length;}
}};
const inputMask=()=>({rectangles:[{x:0,y:0,width:2,height:2}],occupied:4});
const saveState=()=>stateWrites++;
let window={get_visible:()=>!hidden,get_window:()=>({
 input_shape_combine_region:region=>masks.push(region.rectangles)
}),get_position:()=>[10,20]};
const web={is_loading:false,get_mapped:()=>true,get_allocated_width:()=>7,get_allocated_height:()=>9,get_snapshot:(_r,_o,_c,callback)=>callbacks.push(()=>callback(web,{})),
 get_snapshot_finish:()=>{if(broken)throw new Error('synthetic snapshot failure');return surface;}};
const WebKit={SnapshotRegion:{VISIBLE:1},SnapshotOptions:{TRANSPARENT_BACKGROUND:1}};
"""
    result = subprocess.run(
        ["node"],
        input=harness + source[start:end] + "\n" + checks,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
