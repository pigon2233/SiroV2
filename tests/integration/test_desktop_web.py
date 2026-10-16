from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

STATIC = Path("src/siro/services/presentation/static")


def run_node(source: str) -> None:
    result = subprocess.run(["node", "-e", source], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def run_desktop(checks: str) -> None:
    setup = r"""
const assert = require('node:assert/strict');
const nativeMessages=[], opened=[], observers=[], listeners=new Map();
class Element {
  constructor(tag) {
    this.tagName=tag; this.children=[]; this.textContent=''; this.className='';
    this.attrs={}; this.events=new Map();
    this.classList={
      contains: name => this.className.split(/\s+/).includes(name),
      add: name => {if(!this.classList.contains(name)) this.className+=' '+name;},
      remove: name => {this.className=this.className.split(/\s+/).filter(x=>x!==name).join(' ');},
      toggle: (name,on) => {if(on) this.classList.add(name);else this.classList.remove(name);}
    };
  }
  setAttribute(key,value) {this.attrs[key]=value;}
  appendChild(node) {this.children.push(node);return node;}
  addEventListener(name,fn) {this.events.set(name,fn);}
  click() {this.events.get('click')?.({});this.onclick?.();}
  focus() {document.activeElement=this;}
}
const document={readyState:'complete',body:new Element('body'),documentElement:new Element('html'),
  createElement: tag=>new Element(tag)};
document.body.className='siro-desktop';
const existing=new Map();
for(const id of ['companion','messages','text','voice','cancel','connection',
                'voice-status','tts-status']) {
  const node=new Element('div');node.id=id;existing.set('#'+id,node);
}
const conversation=new Element('section');conversation.className='conversation';
existing.set('.conversation',conversation);
existing.get('#companion').contentWindow={renderer:true};
const find=(node,id)=>node.id===id?node:node.children.map(child=>find(child,id)).find(Boolean);
document.querySelector=selector=>existing.get(selector)||find(document.body,selector.slice(1))||null;
const window={
  webkit:{messageHandlers:{siroDesktop:{postMessage: text=>nativeMessages.push(JSON.parse(text))}}},
  addEventListener(name,fn) {
    if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(fn);
  },
  open(url,name) {opened.push({url,name});}
};
const location={origin:'http://localhost'};
class MutationObserver {
  constructor(fn) {this.fn=fn;this.owned=[];observers.push(this);}
  observe(node,options) {this.owned.push(node);}
  disconnect() {this.disconnected=true;}
}
const dispatch=(name,event)=>{for(const fn of listeners.get(name)||[])fn(event);};
let stopped=0,voiced=0;
existing.get('#cancel').onclick=()=>stopped++;
existing.get('#voice').onclick=()=>voiced++;
existing.get('#connection').textContent='已連線';
existing.get('#voice-status').textContent='麥克風待命';
existing.get('#tts-status').textContent='TTS 待命';
"""
    run_node(setup + STATIC.joinpath("desktop.js").read_text() + "\n" + checks)


def test_desktop_chat_uses_original_nodes_and_native_focus_notification() -> None:
    run_desktop(
        """
assert(window.siroDesktopView);
assert.equal(conversation.inert,true);
const input=existing.get('#text'),frame=existing.get('#companion');
assert.equal(window.siroDesktopView.openChat(),true);
assert.equal(document.activeElement,input);
assert.equal(conversation.inert,false);
assert.deepEqual(nativeMessages.at(-1),{type:'desktop.chat',open:true});
assert.equal(window.siroDesktopView.toggleChat(),false);
assert.equal(conversation.inert,true);
assert.equal(existing.get('#companion'),frame);
assert.equal(existing.get('#text'),input);
assert.equal(document.querySelector('#desktop-chat').attrs['aria-expanded'],'false');
"""
    )


def test_native_controls_and_escape_keep_real_stop_and_voice_paths_reachable() -> None:
    run_desktop(
        """
document.querySelector('#desktop-stop').click();
document.querySelector('#desktop-voice').click();
assert.equal(stopped,1);assert.equal(voiced,1);
assert.equal(conversation.inert,false);
let prevented=0;
document.querySelector('#desktop-move').events.get('pointerdown')({
  button:0,screenX:123,screenY:234,preventDefault(){prevented++;}
});
assert.equal(prevented,1);
assert.deepEqual(nativeMessages.at(-1),{type:'desktop.move',button:1,screenX:123,screenY:234});
for(const name of ['console','hide','quit']) document.querySelector('#desktop-'+name).click();
assert.deepEqual(nativeMessages.slice(-3),[
  {type:'desktop.console'},{type:'desktop.hide'},{type:'desktop.quit'}
]);
dispatch('keydown',{key:'Escape'});
assert.equal(stopped,2);assert.equal(conversation.inert,true);
assert.equal(opened.length,0);
"""
    )


def test_desktop_unread_status_and_renderer_events_are_origin_and_source_scoped() -> None:
    run_desktop(
        """
observers.find(item=>item.owned.includes(existing.get('#messages'))).fn();
assert(document.querySelector('#desktop-chat').classList.contains('desktop-unread'));
window.siroDesktopView.openChat();
assert(!document.querySelector('#desktop-chat').classList.contains('desktop-unread'));
const detached={type:'siro.renderer.detached'};
dispatch('message',{origin:'http://foreign',source:existing.get('#companion').contentWindow,data:detached});
dispatch('message',{origin:location.origin,source:{},data:detached});
assert(document.querySelector('#desktop-status').textContent.includes('已連線'));
dispatch('message',{origin:location.origin,source:existing.get('#companion').contentWindow,data:detached});
assert(document.querySelector('#desktop-status').textContent.includes('已交接'));
dispatch('pagehide',{});
assert(observers.every(item=>item.disconnected));
"""
    )


def test_browser_preview_does_not_gain_native_commands() -> None:
    run_desktop(
        """
delete window.webkit;
document.querySelector('#desktop-console').click();
document.querySelector('#desktop-quit').click();
assert.deepEqual(opened,[{url:'/?view=control#/chat',name:'siro-control'}]);
assert.equal(nativeMessages.length,0);
"""
    )


def load_repair() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "desktop_repair", "scripts/repair_companion_renderer.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_sdk(tmp_path: Path) -> Path:
    """Use the real preparation bridge, without licensed SDK assets or build tools."""
    tree = ast.parse(Path("scripts/prepare_live2d_renderer.py").read_text())
    bridge = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "bridge" for target in node.targets)
    )
    sources = {
        "main.ts": bridge + "\nwindow.onload = () => {};\n",
        "lappmodel.ts": "  public setExpression(expressionId: string): void {}\n"
        "this._wavFileHandler.start(path);",
        "lapplive2dmanager.ts": "  public setSiroExpression(expressionId: string): void {}\n"
        "model.setRandomExpression();",
        "lappdefine.ts": "export const ModelDir: string[] = ['Haru', 'Other'];",
        "lappview.ts": "this._gear.render(this._programId);\n"
        "this._back.render(this._programId);\nlapplive2dmanager.nextScene();",
        "lappsubdelegate.ts": "gl.clearColor(0.0, 0.0, 0.0, 1.0);",
    }
    tmp_path.joinpath("src").mkdir()
    for name, content in sources.items():
        tmp_path.joinpath("src", name).write_text(content)
    tmp_path.joinpath("index.html").write_text(
        "<html><head><style></style></head><body></body></html>"
    )
    return tmp_path


def repaired_bridge(tmp_path: Path) -> str:
    demo = synthetic_sdk(tmp_path)
    assert load_repair().repair(demo)
    source = demo.joinpath("src/main.ts").read_text()
    bridge = source.split("// SIRO renderer ownership v3", 1)[1].split(
        "// End SIRO renderer ownership v3", 1
    )[0]
    bridge = re.sub(r": (?:number|WebSocket) \| undefined", "", bridge)
    return re.sub(r": (?:void|Promise<void>)", "", bridge)


def run_bridge(tmp_path: Path, checks: str, presentation: str = "desktop") -> None:
    bridge = repaired_bridge(tmp_path)
    setup = r"""
const assert=require('node:assert/strict');
const sockets=[],timers=new Map(),messages=[],listeners=new Map();
let sequence=0,stopCount=0,fetches=0,rendered=0;
const window={setTimeout(fn){const id=++sequence;timers.set(id,fn);return id;},
  clearTimeout(id){timers.delete(id);},parent:{postMessage(message,origin){messages.push({message,origin});}},
  addEventListener(name,fn){listeners.set(name,fn);}};
const location={origin:'http://localhost',host:'localhost',protocol:'http:',search:SEARCH};
const fetch=async(url,options)=>{assert.equal(url,'/v1/session');fetches++;return {
  ok:true,json:async()=>({token:'synthetic-'+fetches})};};
const stopSpeaking=()=>stopCount++;
const renderSiro=()=>rendered++;
class WebSocket {
  constructor(url){this.url=url;this.listeners=new Map();this.sent=[];sockets.push(this);}
  addEventListener(name,fn){this.listeners.set(name,fn);}
  send(message){this.sent.push(JSON.parse(message));}
  close(){this.closed=true;}
  emit(name,event={}){this.listeners.get(name)?.(event);}
}
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve();};
""".replace("SEARCH", json.dumps("?presentation=" + presentation))
    run_node(
        setup
        + bridge
        + "\n(async()=>{\n"
        + checks
        + "\n})().catch(error=>{console.error(error);process.exitCode=1;});"
    )


@pytest.mark.parametrize("reason", ["renderer replaced", "desktop owner active"])
def test_renderer_handoff_notifies_parent_and_never_reclaims_owner(
    tmp_path: Path, reason: str
) -> None:
    run_bridge(
        tmp_path,
        """
await connectSiro();const socket=sockets[0];socket.emit('open');
assert.deepEqual(socket.sent,[{type:'authenticate',token:'synthetic-1',presentation:'desktop'}]);
socket.emit('close',{reason:REASON});
assert.equal(stopCount,1);assert.equal(timers.size,0);
assert.deepEqual(messages,[{message:{type:'siro.renderer.detached'},origin:location.origin}]);
await connectSiro();assert.equal(sockets.length,1);assert.equal(fetches,1);
socket.emit('message',{data:'{}'});assert.equal(rendered,0);
""".replace("REASON", json.dumps(reason)),
    )


def test_renderer_network_close_reauthenticates_and_pagehide_cancels_retry(tmp_path: Path) -> None:
    run_bridge(
        tmp_path,
        """
await connectSiro();sockets[0].emit('open');
assert.deepEqual(sockets[0].sent,[{type:'authenticate',token:'synthetic-1'}]);
sockets[0].emit('close',{reason:''});assert.equal(timers.size,1);
const retry=[...timers.values()][0];timers.clear();retry();await flush();
assert.equal(sockets.length,2);sockets[1].emit('open');
assert.equal(sockets[1].sent[0].token,'synthetic-2');
sockets[1].emit('close',{reason:''});assert.equal(timers.size,1);
listeners.get('pagehide')();assert.equal(timers.size,0);
await connectSiro();assert.equal(sockets.length,2);
""",
        presentation="web",
    )


def test_renderer_repair_is_idempotent_and_desktop_transparency_is_opt_in(tmp_path: Path) -> None:
    demo = synthetic_sdk(tmp_path)
    module = load_repair()
    assert module.repair(demo)
    snapshot = {path: path.read_bytes() for path in demo.rglob("*") if path.is_file()}
    assert not module.repair(demo)
    assert all(path.read_bytes() == content for path, content in snapshot.items())
    markup = demo.joinpath("index.html").read_text()
    assert 'html[data-siro-presentation="desktop"]' in markup
    assert "radial-gradient" in markup  # The ordinary web renderer retains its scene.
    main = demo.joinpath("src/main.ts").read_text()
    assert "// SIRO persistent presentation v2" in main
    assert "Audible speech has one owner in the parent page" in main
    assert main.count("async function connectSiro()") == 1
