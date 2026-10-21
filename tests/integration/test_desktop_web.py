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


def run_desktop(checks: str, before: str = "") -> None:
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
  getAttribute(key) {return this.attrs[key]??null;}
  appendChild(node) {this.children.push(node);return node;}
  addEventListener(name,fn) {this.events.set(name,fn);}
  removeEventListener(name,fn) {if(this.events.get(name)===fn)this.events.delete(name);}
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
    run_node(setup + before + STATIC.joinpath("desktop.js").read_text() + "\n" + checks)


def test_desktop_scale_controls_request_only_fixed_native_steps() -> None:
    run_desktop(
        """
document.querySelector('#desktop-smaller').click();
document.querySelector('#desktop-scale').click();
document.querySelector('#desktop-larger').click();
assert.deepEqual(nativeMessages.slice(-3),[
 {type:'desktop.scale',step:-1},{type:'desktop.scale',step:0},{type:'desktop.scale',step:1}
]);
assert.equal(existing.get('#companion'),originalFrame);
document.querySelector('#desktop-stop').click();
assert.equal(stopped,1);
""",
        "const originalFrame=existing.get('#companion');\n",
    )


def test_desktop_role_pointer_drag_uses_threshold_and_suppresses_chat_after_drag() -> None:
    run_desktop(
        """
const event=(x,y,button=0)=>({button,screenX:x,screenY:y,pointerId:3,
 preventDefault(){},stopImmediatePropagation(){}});
role.events.get('pointerdown')(event(100,100));
role.events.get('pointermove')(event(103,103));
assert(!nativeMessages.some(item=>item.type==='desktop.move'));
role.events.get('pointermove')(event(117,111));
role.events.get('pointermove')(event(120,115));
assert.deepEqual(nativeMessages.filter(item=>item.type==='desktop.move'),[
 {type:'desktop.move',button:1,screenX:117,screenY:111}
]);
role.events.get('pointerup')(event(120,115));
dispatch('message',{origin:location.origin,source:existing.get('#companion').contentWindow,
 data:{type:'siro.renderer.interact'}});
assert.equal(conversation.inert,true);
role.events.get('pointerdown')(event(120,115));
role.events.get('pointerup')(event(120,115));
dispatch('message',{origin:location.origin,source:existing.get('#companion').contentWindow,
 data:{type:'siro.renderer.interact'}});
assert.equal(conversation.inert,false);
""",
        """
const role=new Element('document');
existing.get('#companion').contentDocument=role;
""",
    )


def test_desktop_role_pointer_right_button_does_not_move_or_suppress_click() -> None:
    run_desktop(
        """
const event={button:2,screenX:100,screenY:100,pointerId:3,preventDefault(){}};
role.events.get('pointerdown')(event);
role.events.get('pointermove')({...event,screenX:200});
assert(!nativeMessages.some(item=>item.type==='desktop.move'));
""",
        "const role=new Element('document');existing.get('#companion').contentDocument=role;\n",
    )


def test_desktop_visible_speech_switch_uses_original_checkbox_and_change() -> None:
    run_desktop(
        """
const speech=document.querySelector('#desktop-speech');
assert.equal(output.checked,false);
assert.equal(speech.attrs['aria-pressed'],'false');
speech.click();
assert.equal(output.checked,true);
assert.equal(changes,1);
assert.equal(speech.attrs['aria-pressed'],'true');
assert(speech.textContent.includes('開'));
speech.click();
assert.equal(output.checked,false);
assert.equal(changes,2);
assert.equal(existing.get('#voice-output'),output);
""",
        """
let changes=0;
const output=new Element('input');output.checked=false;
output.dispatchEvent=event=>{assert.equal(event.type,'change');changes++;};
existing.set('#voice-output',output);
""",
    )


def test_desktop_native_layout_api_updates_geometry_without_replacing_nodes() -> None:
    run_desktop(
        """
const frame=existing.get('#companion'),input=existing.get('#text');
window.siroDesktopView.setLayout({petWidth:360,petHeight:570,petX:0,
 chatX:372,chatY:8,chatWidth:380,chatHeight:554,scale:1});
assert.equal(properties.get('--desktop-pet-width'),'360px');
assert.equal(properties.get('--desktop-chat-x'),'372px');
assert.equal(document.querySelector('#desktop-scale').textContent,'100%');
window.siroDesktopView.openChat();
window.siroDesktopView.closeChat();
assert.equal(existing.get('#companion'),frame);assert.equal(existing.get('#text'),input);
const previous=new Map(properties);
window.siroDesktopView.setLayout({petWidth:NaN});
assert.deepEqual(properties,previous);
""",
        """
const properties=new Map();
document.documentElement.style={setProperty:(key,value)=>properties.set(key,value)};
""",
    )


def test_desktop_walk_bridge_forwards_valid_requests_and_host_updates_only() -> None:
    run_desktop(
        """
const role=existing.get('#companion').contentWindow;
const fromRole=data=>dispatch('message',{origin:location.origin,source:role,data});
fromRole({type:'siro.desktop.walk',v:1,action:'start',id:'walk-1',direction:0,
 distance:400,speed:250,ramp:1.4,delay:1.4,cycle:1.43});
assert.deepEqual(nativeMessages.at(-1),{type:'desktop.walk',id:'walk-1',direction:0,
 distance:400,speed:250,ramp:1.4,delay:1.4,cycle:1.43});
fromRole({type:'siro.desktop.walk',v:1,action:'stop',id:'walk-1'});
assert.deepEqual(nativeMessages.at(-1),{type:'desktop.walk.stop',id:'walk-1'});
const count=nativeMessages.length;
for(const bad of [{v:2,action:'start'},{v:1,action:'start',direction:2},
 {v:1,action:'start',direction:0,distance:'far'},{v:1,action:'fly'}])
 fromRole({type:'siro.desktop.walk',id:'walk-2',direction:0,distance:1,speed:1,ramp:1,delay:0,...bad});
dispatch('message',{origin:'http://evil',source:role,data:{type:'siro.desktop.walk',v:1,
 action:'start',id:'x',direction:0,distance:1,speed:1,ramp:1,delay:0}});
assert.equal(nativeMessages.length,count);
// Host updates reach the role with the protocol stamp; malformed ones are dropped.
window.siroDesktopView.walkUpdate({id:'walk-1',state:'started',direction:-1,distance:400,
 ramp:1.4,cruise:0.2,delay:1.4});
window.siroDesktopView.walkUpdate({id:'walk-1',state:'teleported'});
window.siroDesktopView.walkUpdate({id:'walk-1',state:'started',distance:'far'});
assert.equal(toRole.length,1);
assert.deepEqual(toRole[0].message,{id:'walk-1',state:'started',direction:-1,distance:400,
 ramp:1.4,cruise:0.2,delay:1.4,type:'siro.desktop.walk.state',v:1});
assert.equal(toRole[0].origin,location.origin);
// With the chat open she does not wander off from it.
existing.get('#text').focus=()=>{};
document.querySelector('#desktop-chat').click();
fromRole({type:'siro.desktop.walk',v:1,action:'start',id:'walk-3',direction:1,
 distance:400,speed:250,ramp:1.4,delay:1.4});
assert(!nativeMessages.some(item=>item.id==='walk-3'));
assert.deepEqual(toRole.at(-1).message,{id:'walk-3',state:'refused',reason:'chat',
 type:'siro.desktop.walk.state',v:1});
""",
        "const toRole=[];\n"
        "existing.get('#companion').contentWindow={renderer:true,"
        "postMessage:(message,origin)=>toRole.push({message,origin})};\n",
    )


def test_desktop_microphone_switch_forwards_without_starting_recording() -> None:
    run_desktop(
        """
const button=document.querySelector('#desktop-microphone');
assert.equal(button.textContent,'麥克風\uff1a關');
button.click();
assert.equal(toggled,1);assert.equal(voiced,0);
observers.find(item=>item.owned.includes(microphone)).fn();
assert.equal(button.textContent,'麥克風\uff1a開');
assert.equal(button.attrs['aria-pressed'],'true');
microphone.disabled=true;
observers.find(item=>item.owned.includes(microphone)).fn();
assert.equal(button.disabled,true);
""",
        """
let toggled=0;
const microphone=new Element('button');
microphone.textContent='麥克風\uff1a關';microphone.setAttribute('aria-pressed','false');
microphone.onclick=()=>{toggled++;microphone.textContent='麥克風\uff1a開';microphone.setAttribute('aria-pressed','true');};
existing.set('#microphone-toggle',microphone);
""",
    )


def test_desktop_geometry_keeps_chat_and_role_separate_and_inside_workarea() -> None:
    source = Path("desktop/layout.mjs").resolve().as_uri()
    run_node(
        f"""
(async()=>{{
 const assert=require('node:assert/strict');
 const {{desktopLayout}}=await import({json.dumps(source)});
 for(const [width,height] of [[1920,1080],[1280,720],[640,480],[360,640],[64,64]])
  for(const scale of [.6,1,1.5]) for(const chat of [false,true]){{
   const r=desktopLayout(scale,chat,width,height);
   for(const key of ['width','height','petWidth','petHeight','chatWidth','chatHeight'])
    assert(Number.isSafeInteger(r[key]) && r[key]>0,key);
   assert(r.width<=width && r.height<=height,JSON.stringify(r));
   assert(r.petX>=0 && r.petX+r.petWidth<=r.width);
   assert(r.petHeight<=r.height);
   assert(r.controlsY>=r.petHeight && r.paneX>=0 && r.paneX+r.paneWidth<=r.width);
   if(chat){{
    assert(r.chatX>=0 && r.chatY>=0);
    assert(r.chatX+r.chatWidth<=r.width);
    assert(r.chatY+r.chatHeight<=r.height);
    assert(r.chatX>=r.petX+r.petWidth || r.chatY>=r.petHeight,JSON.stringify(r));
   }}
  }}
 for(const invalid of [NaN,Infinity,-1,0,2])
  assert.throws(()=>desktopLayout(invalid,true,1280,720));
}})().catch(error=>{{console.error(error);process.exit(1);}});
"""
    )


def test_desktop_pet_size_follows_the_screen_within_bounds() -> None:
    source = Path("desktop/layout.mjs").resolve().as_uri()
    run_node(
        f"""
(async()=>{{
 const assert=require('node:assert/strict');
 const {{desktopLayout}}=await import({json.dumps(source)});
 // 1920x1080 landscape (work area 1040 tall) keeps the original 360x640 pet at 100%.
 let r=desktopLayout(1,false,1920,1040);
 assert.equal(r.petHeight,640); assert.equal(r.scale,1);
 // Portrait 1080x1920 (work area 1872): 45% of the height, 842 px tall, shown as 100%.
 r=desktopLayout(1,false,1080,1872);
 assert(r.petHeight>=838 && r.petHeight<=842,JSON.stringify(r)); assert.equal(r.scale,1);
 // With the chat open on that portrait screen she keeps her size beside the chat window.
 const chat=desktopLayout(1,true,1080,1872);
 assert.equal(chat.petHeight,r.petHeight); assert(chat.chatX>=chat.petX+chat.petWidth);
 assert(chat.width<=1080 && chat.chatHeight>=520,JSON.stringify(chat));
 // A narrow portrait screen stacks the chat below and shrinks her to fit.
 const narrow=desktopLayout(1,true,540,960);
 assert(narrow.chatY>=narrow.petHeight && narrow.height<=960,JSON.stringify(narrow));
 // Upper bound: a 4K portrait monitor stops at 1040 px tall at 100%.
 assert(desktopLayout(1,false,2160,3800).petHeight<=1040);
 // The +/- buttons still scale the base, and the shown percentage is relative to it.
 const big=desktopLayout(1.5,false,1080,1872), small=desktopLayout(.6,false,1080,1872);
 assert(big.petHeight>r.petHeight && small.petHeight<r.petHeight);
 assert.equal(small.scale,.6);
 // Never taller than the screen leaves room for, even at 150%.
 assert(big.height<=1872);
}})().catch(error=>{{console.error(error);process.exit(1);}});
"""
    )


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


BUBBLE_FEED = r"""
let feed, speechBusy=false;
window.siroWatchActivity=listener=>{feed=listener;return ()=>{feed=null;};};
window.siroSpeechBusy=()=>speechBusy;
const tool=(capability,state,target={})=>({capability,state,target});
const act=(id,state,tools,reason='查今晚的星雲')=>({activity_id:id,state,reason,tools,
  updated_at:'2026-10-21T00:00:0'+id.length+'Z'});
const view=(items,status='ok')=>({status,items:new Map(items.map(item=>[item.activity_id,item])),stopping:new Set()});
"""


def test_bubble_only_says_working_when_the_journal_has_a_running_tool() -> None:
    run_desktop(
        """
const bubble=document.querySelector('#desktop-bubble');
const label=()=>bubble.children[1].textContent, action=bubble.children[2];
feed(view([act('a','running',[])]));
assert.equal(bubble.hidden,true);
feed(view([act('a','running',[tool('browser.navigate+read','running')])]));
assert.equal(bubble.hidden,false); assert.equal(label(),'正在查：查今晚的星雲'); assert.equal(action.hidden,true);
feed(view([act('a','completed',[tool('browser.navigate+read','completed')])]));
assert.equal(label(),'做好了：查今晚的星雲'); assert.equal(action.textContent,'看看');
action.click();
assert.deepEqual(nativeMessages.at(-1),{type:'desktop.console',page:'activity'});
window.siroDesktopView.openChat();
assert.equal(bubble.hidden,true);
window.siroDesktopView.closeChat(); document.activeElement=null;
speechBusy=true; feed(view([act('b','running',[tool('computer.execute','running',{program:'find'})])]));
assert.equal(bubble.hidden,true);
speechBusy=false; feed(view([act('b','running',[tool('computer.execute','running',{program:'find'})])]));
assert.equal(label(),'正在執行：查今晚的星雲');
feed(view([],'offline'));
assert.equal(label(),'斷線了，狀態可能過時');
""",
        before=BUBBLE_FEED,
    )


def test_bubble_proposal_opens_chat_and_escape_only_folds_the_bubble() -> None:
    run_desktop(
        """
const bubble=document.querySelector('#desktop-bubble');
feed(view([act('c','proposed',[tool('computer.execute','proposed',{program:'git'})],null)]));
assert.equal(bubble.children[1].textContent,'等你允許：執行 git');
bubble.events.get('keydown')({key:'Escape',stopPropagation(){}});
assert.equal(bubble.hidden,true); assert.equal(stopped,0);
feed(view([act('c','proposed',[tool('computer.execute','proposed',{program:'git'})],null)]));
assert.equal(bubble.hidden,true);
feed(view([])); feed(view([act('c','proposed',[tool('computer.execute','proposed',{program:'git'})],null)]));
assert.equal(bubble.hidden,false);
bubble.children[2].click();
assert.equal(conversation.inert,false);
dispatch('pagehide',{}); assert.equal(feed,null);
""",
        before=BUBBLE_FEED,
    )
