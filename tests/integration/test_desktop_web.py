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
    const data={};
    this.classList={
      contains: name => this.className.split(/\s+/).includes(name),
      add: name => {if(!this.classList.contains(name)) this.className+=' '+name;},
      remove: name => {this.className=this.className.split(/\s+/).filter(x=>x!==name).join(' ');},
      toggle: (name,on) => {if(on) this.classList.add(name);else this.classList.remove(name);}
    };
    this.style={setProperty(){}};
    // HTMLElement.dataset is getter-only. Replacing it must throw, as it does in the browser.
    Object.defineProperty(this,'dataset',{get(){return data;},enumerable:true});
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
  createElement: tag=>new Element(tag),activeElement:null};
document.body.className='siro-desktop';
const existing=new Map();
const add=(id,tag,parent)=>{
  const node=new Element(tag);node.id=id;
  (parent||document.body).appendChild(node);
  existing.set('#'+id,node);return node;
};
const stage=add('pet-stage','main');
const petFrame=add('companion','iframe',stage);
petFrame.contentWindow={renderer:true};
add('pet-state-label','span',add('pet-state','p',stage));
const petBubble=add('desktop-bubble','div',stage);petBubble.hidden=true;
for(const [tag,cls] of [['span','desktop-bubble-icon'],['span','desktop-bubble-label']]){
  const node=new Element(tag);node.className=cls;petBubble.appendChild(node);
}
const bubbleAction=new Element('button');
bubbleAction.hidden=true;petBubble.appendChild(bubbleAction);
const controls=add('pet-controls','nav',stage);
add('desktop-voice','button',controls);
const stop=add('desktop-stop','button',controls);stop.hidden=true;
add('desktop-more','button',controls);
const more=add('pet-more','div',controls);more.hidden=true;
for(const id of ['desktop-chat','desktop-microphone','desktop-voice-auto','desktop-speech',
  'desktop-replay','desktop-smaller','desktop-scale','desktop-larger','desktop-move',
  'desktop-console','desktop-hide','desktop-quit']) add(id,'button',more);
const chat=add('pet-chat','section');chat.hidden=true;
add('messages','div',chat);
add('text','textarea',add('chat','form',chat));
const err=add('pet-error','p');err.hidden=true;
const find=(node,id)=>node.id===id?node:node.children.map(child=>find(child,id)).find(Boolean);
document.querySelector=selector=>existing.get(selector)||find(document.body,selector.slice(1))||null;
const window={
  webkit:{messageHandlers:{siroDesktop:{postMessage: text=>nativeMessages.push(JSON.parse(text))}}},
  addEventListener(name,fn) {
    if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(fn);
  },
  open(url,name) {opened.push({url,name});}
};
const location={origin:'http://localhost',protocol:'http:',host:'localhost'};
class MutationObserver {
  constructor(fn) {this.fn=fn;this.owned=[];observers.push(this);}
  observe(node,options) {this.owned.push(node);}
  disconnect() {this.disconnected=true;}
}
const dispatch=(name,event)=>{for(const fn of listeners.get(name)||[])fn(event);};
"""
    run_node(setup + before + STATIC.joinpath("pet.js").read_text() + "\n" + checks)


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
assert.equal(window.siroPet.stops,1);
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
assert.equal(document.querySelector('#pet-chat').hidden,true);
role.events.get('pointerdown')(event(120,115));
role.events.get('pointerup')(event(120,115));
dispatch('message',{origin:location.origin,source:existing.get('#companion').contentWindow,
 data:{type:'siro.renderer.interact'}});
assert.equal(document.querySelector('#pet-chat').hidden,true);
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


def test_desktop_speech_switch_toggles_without_scraping_the_console() -> None:
    run_desktop(
        """
const speech=document.querySelector('#desktop-speech');
assert.equal(speech.attrs['aria-pressed'],'true');
assert(!speech.textContent.includes('\uff1a開'));
speech.click();
assert.equal(speech.attrs['aria-pressed'],'false');
assert(!speech.textContent.includes('\uff1a關'));
speech.click();
assert.equal(speech.attrs['aria-pressed'],'true');
assert.equal(document.querySelector('#connection'),null);
assert.equal(document.querySelector('#tts-status'),null);
"""
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
const walks=()=>toRole.filter(item=>item.message.type==='siro.desktop.walk.state');
assert.equal(walks().length,1);
assert.deepEqual(walks()[0].message,{id:'walk-1',state:'started',direction:-1,distance:400,
 ramp:1.4,cruise:0.2,delay:1.4,type:'siro.desktop.walk.state',v:1});
assert.equal(walks()[0].origin,location.origin);
// With the chat open she does not wander off from it.
existing.get('#text').focus=()=>{};
document.querySelector('#desktop-chat').click();
fromRole({type:'siro.desktop.walk',v:1,action:'start',id:'walk-3',direction:1,
 distance:400,speed:250,ramp:1.4,delay:1.4});
assert(!nativeMessages.some(item=>item.id==='walk-3'));
assert.deepEqual(walks().at(-1).message,{id:'walk-3',state:'refused',reason:'chat',
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
assert.equal(button.getAttribute('aria-pressed'),'false');
assert(!button.textContent.includes('\uff1a關'));
let calls=0;
globalThis.navigator={mediaDevices:{getUserMedia(){calls++;
  return Promise.resolve({getTracks(){return [];}});}}};
button.click();
assert.equal(calls,0);
assert.equal(button.attrs['aria-pressed'],'false');
"""
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
assert.equal(document.querySelector('#pet-chat').hidden,true);
const input=existing.get('#text'),frame=existing.get('#companion');
assert.equal(window.siroDesktopView.openChat(),true);
assert.equal(document.activeElement,input);
assert.equal(document.querySelector('#pet-chat').hidden,false);
assert.deepEqual(nativeMessages.at(-1),{type:'desktop.chat',open:true});
assert.equal(window.siroDesktopView.toggleChat(),false);
assert.equal(document.querySelector('#pet-chat').hidden,true);
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
assert.equal(window.siroPet.stops,1);
assert.match(document.querySelector('#pet-error').textContent,/麥克風/);
assert.equal(document.querySelector('#pet-chat').hidden,true);
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
assert.equal(window.siroPet.stops,2);assert.equal(document.querySelector('#pet-chat').hidden,true);
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
window.siroPet.applyControl({type:'snapshot',authorization_mode:'full',kill_switches:{microphone:false},active_turns:{},routes:{},health:{},identity:{}});
assert.equal(document.querySelector('#pet-state').getAttribute('data-state'),'ready');
dispatch('message',{origin:location.origin,source:existing.get('#companion').contentWindow,data:detached});
assert(document.querySelector('#pet-state-label').textContent.includes('交接'));
dispatch('pagehide',{});
assert(observers.every(item=>item.disconnected));
"""
    )


def test_desktop_startup_does_not_open_a_browser_tab() -> None:
    run_desktop(
        """
assert.equal(opened.length,0);
assert.equal(nativeMessages.length,0);
assert.equal(document.querySelector('#desktop-hide').title,'最小化；可從工作列恢復');
"""  # noqa: RUF001
    )


def test_electron_hide_hint_points_at_the_tray() -> None:
    run_desktop(
        """
assert.equal(document.querySelector('#desktop-hide').title,'先藏起來；可從系統匣恢復');
assert.equal(opened.length,0);
""",  # noqa: RUF001
        before="window.siroDesktopHost='electron';\n",
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
"""  # noqa: E501


def test_activity_bubble_without_native_bridge_opens_one_control_tab_on_click() -> None:
    run_desktop(
        """
feed(view([act('a','running',[tool('browser.navigate+read','running')])]));
feed(view([act('a','completed',[tool('browser.navigate+read','completed')])]));
assert.equal(opened.length,0);
delete window.webkit;
document.querySelector('#desktop-bubble').children[2].click();
assert.deepEqual(opened,[{url:'/?view=control#/activity',name:'siro-control'}]);
assert.equal(nativeMessages.length,0);
""",
        before=BUBBLE_FEED,
    )


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
""",  # noqa: E501, RUF001
        before=BUBBLE_FEED,
    )


def test_bubble_proposal_opens_chat_and_escape_only_folds_the_bubble() -> None:
    run_desktop(
        """
const bubble=document.querySelector('#desktop-bubble');
feed(view([act('c','proposed',[tool('computer.execute','proposed',{program:'git'})],null)]));
assert.equal(bubble.children[1].textContent,'等你允許：執行 git');
bubble.events.get('keydown')({key:'Escape',stopPropagation(){}});
assert.equal(bubble.hidden,true); assert.equal(window.siroPet.stops,0);
feed(view([act('c','proposed',[tool('computer.execute','proposed',{program:'git'})],null)]));
assert.equal(bubble.hidden,true);
feed(view([])); feed(view([act('c','proposed',[tool('computer.execute','proposed',{program:'git'})],null)]));
assert.equal(bubble.hidden,false);
bubble.children[2].click();
assert.equal(document.querySelector('#pet-chat').hidden,false);
dispatch('pagehide',{}); assert.equal(feed,null);
""",  # noqa: E501, RUF001
        before=BUBBLE_FEED,
    )


def test_bubble_for_her_own_reading_offers_a_stop_for_that_activity() -> None:
    run_desktop(
        """
const stops=[]; window.siroStopActivity=id=>stops.push(id);
const bubble=document.querySelector('#desktop-bubble');
const own=act('s1','running',[tool('browser.navigate+read','running')],'獵戶座星雲'); own.origin='self_interest';
feed(view([own]));
assert.equal(bubble.children[1].textContent,'自己在讀：獵戶座星雲');
assert.equal(bubble.children[2].textContent,'停');
bubble.children[2].click();
assert.deepEqual(stops,['s1']);
""",  # noqa: E501, RUF001
        before=BUBBLE_FEED,
    )


def test_bubble_offers_her_unshared_note_and_escape_marks_it_seen() -> None:
    run_desktop(
        """
const shared=[], seen=[];
window.siroShareNote=id=>shared.push(id); window.siroDismissNote=id=>seen.push(id);
const bubble=document.querySelector('#desktop-bubble');
const withNote=view([]); withNote.selfActivity={paused:false,unshared:['n1']};
feed(withNote);
assert.equal(bubble.children[1].textContent,'查好了，要聽嗎？');
bubble.children[2].click();
assert.deepEqual(shared,['n1']);
bubble.events.get('keydown')({key:'Escape',stopPropagation(){}});
assert.deepEqual(seen,['n1']);
assert.equal(bubble.hidden,true);
assert.equal(window.siroPet.stops,0);
""",  # noqa: RUF001
        before=BUBBLE_FEED,
    )


def test_pet_state_comes_from_control_events_not_hidden_console_nodes() -> None:
    run_desktop(
        """
assert.equal(document.querySelector('#connection'),null);
assert.equal(document.querySelector('#tts-status'),null);
assert.equal(document.querySelector('#voice-status'),null);
document.querySelector('#desktop-speech').click();
const snap={type:'snapshot',authorization_mode:'full',kill_switches:{microphone:false},
  active_turns:{},routes:{},health:{},identity:{}};
window.siroPet.applyControl(snap);
assert.equal(window.siroPet.state,'ready');
window.siroPet.applyControl({type:'turn_started',turn_id:'t1',session_id:'browser'});
assert.equal(window.siroPet.state,'thinking');
assert.equal(document.querySelector('#desktop-stop').hidden,false);
assert.equal(document.body.classList.contains('pet-busy'),true);
window.siroPet.applyControl({type:'turn_cancelled',turn_id:'t1'});
assert.equal(window.siroPet.state,'ready');
assert.equal(document.body.classList.contains('pet-busy'),false);
window.siroPet.applyControl({type:'assistant_started',stream_id:'s1'});
window.siroPet.applyControl({type:'assistant_delta',stream_id:'s1',text:'你好'});
assert.equal(document.querySelector('#messages').children.at(-1).textContent,'你好');
assert.equal(window.siroPet.speakablePrefix('你好。下一句'),'你好。');
assert.equal(window.siroPet.speakablePrefix('還沒說完'),'');
window.siroPet.applyControl({type:'assistant_started',stream_id:'touch'});
window.siroPet.applyControl({type:'assistant_delta',stream_id:'touch',text:'嘿嘿好舒服'});
window.siroPet.applyControl({type:'assistant_terminal',stream_id:'touch',state:'completed'});
window.siroPet.applyControl({type:'assistant_delta',stream_id:'s1',text:'今天也好'});
assert.equal(document.querySelector('#messages').children.length,1);
assert.equal(document.querySelector('#messages').children[0].textContent,'你好今天也好');
window.siroPet.applyControl({type:'assistant_terminal',stream_id:'s1',state:'completed'});
assert.equal(document.querySelector('#messages').children.length,2);
assert.equal(document.querySelector('#messages').children[1].textContent,'嘿嘿好舒服');
"""
    )


def test_pet_menu_owns_gestures_and_iframe_keys_still_open_chat() -> None:
    run_desktop(
        """
const probe=document.createElement('button');
assert.throws(()=>{ "use strict"; probe.dataset={gesture:'no'}; }, TypeError);
probe.dataset.gesture='wave';
assert.equal(probe.dataset.gesture,'wave');
const frame=existing.get('#companion');
const sent=[];
frame.contentWindow.postMessage=(message)=>sent.push(message);
dispatch('message',{origin:location.origin,source:frame.contentWindow,
  data:{type:'siro.contextmenu',v:1,x:10,y:20}});
assert.equal(document.body.classList.contains('pet-menu'),true);
const wave=[...document.querySelector('#pet-gestures').children]
  .find(node=>node.dataset?.gesture==='wave');
assert.equal(wave.textContent,'揮手');
wave.click();
assert.deepEqual(sent.at(-1),{type:'siro.gesture',v:1,name:'wave'});
assert.equal(document.body.classList.contains('pet-menu'),false);
const input=document.querySelector('#text');
input.focus();
assert.equal(document.activeElement,input);
input.events.get('keydown')({key:'a',preventDefault(){},isComposing:false,keyCode:65,which:65});
assert.equal(document.querySelector('#pet-chat').hidden,true);
dispatch('message',{origin:location.origin,source:frame.contentWindow,
  data:{type:'siro.key',v:1,key:'F2'}});
assert.equal(document.querySelector('#pet-chat').hidden,false);
input.focus();
assert.equal(document.activeElement,input);
dispatch('message',{origin:location.origin,source:frame.contentWindow,
  data:{type:'siro.key',v:1,key:'Enter'}});
assert.equal(document.querySelector('#pet-chat').hidden,false);
dispatch('message',{origin:location.origin,source:frame.contentWindow,
  data:{type:'siro.key',v:1,key:'Escape'}});
assert.equal(document.querySelector('#pet-chat').hidden,true);
""",
    )


def test_left_click_on_the_character_closes_the_one_menu() -> None:
    run_desktop(
        """
const frame=existing.get('#companion');
dispatch('message',{origin:location.origin,source:frame.contentWindow,
  data:{type:'siro.contextmenu',v:1,x:4,y:8}});
assert.equal(document.body.classList.contains('pet-menu'),true);
assert.equal(document.querySelector('#pet-more').hidden,false);
assert.equal(document.querySelector('#desktop-more').attrs['aria-expanded'],'true');
frame.contentDocument.events.get('pointerdown')({button:2,screenX:1,screenY:1,pointerId:1,preventDefault(){}});
assert.equal(document.body.classList.contains('pet-menu'),true);
frame.contentDocument.events.get('pointerdown')({button:0,screenX:2,screenY:2,pointerId:1,preventDefault(){}});
assert.equal(document.body.classList.contains('pet-menu'),false);
assert.equal(document.querySelector('#pet-more').hidden,true);
assert.equal(document.querySelector('#pet-stage').getAttribute('data-dock'),'right');
dispatch('message',{origin:location.origin,source:frame.contentWindow,
  data:{type:'siro.contextmenu',v:1}});
dispatch('keydown',{key:'Escape'});
assert.equal(document.querySelector('#pet-more').hidden,true);
""",
        "existing.get('#companion').contentDocument=new Element('document');\n",
    )


def test_pet_page_keeps_the_audio_and_renderer_contract() -> None:
    source = (STATIC / "pet.js").read_text(encoding="utf-8")
    page = (STATIC / "pet.html").read_text(encoding="utf-8")
    for needle in (
        "/v1/session",
        "/v1/conversations/browser/turns",
        "/v1/turns/",
        "/v1/audio/speech",
        "/v1/audio/speech/stream",
        "/v1/audio/speech/plan",
        "/v1/audio/transcriptions",
        "/ws/control",
        "siro.speech.mouth",
        "siro.desktop.walk",
        "siro.view.focus",
        "siro.audio.busy",
        "siro.renderer.ready",
        "siro.contextmenu",
        "siro.key",
        "siro.gesture",
        "siro.sfx",
        "desktop.scale",
    ):
        assert needle in source
    assert "#connection" not in source
    assert "#tts-status" not in source
    assert "app-shell" not in page
    assert 'id="companion"' in page
    assert 'id="pet-state"' in page
    for needle in (
        'aria-label="說話"',
        'aria-label="聊聊"',
        'aria-label="停止"',
        'aria-label="更多"',
        'id="pet-actions"',
        'id="desktop-quit"',
    ):
        assert needle in page
    assert "麥克風：關" not in page  # noqa: RUF001
    assert "朗讀：開" not in page  # noqa: RUF001
    assert "免手動：關" not in page  # noqa: RUF001
    css = (STATIC / "pet.css").read_text(encoding="utf-8")
    assert "background: transparent" in css
    assert "pet-hot" in css
    assert "pet-busy" in css
    assert "data-dock" in css
    assert "backdrop-filter" not in css
    assert "rgba(16, 14, 24, 0.88)" in css
    assert "rgba(16, 14, 24, 0.94)" in css
    assert "prefers-reduced-motion" in css
    assert "#pet-controls" in css
    assert "pointer-events: none" in css


def test_pet_hit_mask_and_mouth_sync_skip_the_extra_loops() -> None:
    pet = (STATIC / "pet.js").read_text(encoding="utf-8")
    mouth = pet[pet.index("function syncMouth") : pet.index("const validSpeechPlan")]
    assert "requestAnimationFrame" not in mouth
    assert "siro.renderer.frame" in mouth
    assert "siro.mouth.watch" in mouth
    assert "1000 / 30" in mouth
    host = Path("desktop-win/main.js").read_text(encoding="utf-8")
    assert "setInterval(refreshMask, 700)" not in host
    assert "CAPTURE_FALLBACK_MS" in host
    assert "}, 8);" not in host
    assert "pointerShouldNotify" in host
    renderer = Path("renderers/vrm/src/main.js").read_text(encoding="utf-8")
    assert "siro.alpha.mask" in renderer
    assert "siro.mouth.watch" in renderer
    assert "Math.max(window.devicePixelRatio || 1, 1.25)" in renderer
    assert "1000 / (resting() ? 20 : 30)" in renderer
    run_desktop(
        """
window.innerWidth=80; window.innerHeight=64;
Element.prototype.getBoundingClientRect=()=>({left:4,top:8,width:72,height:48});
document.querySelectorAll=sel=>sel==='.pet-dock button'
  ? [existing.get('#desktop-voice')].filter(Boolean) : [];
document.body.classList.add('pet-hot');
dispatch('message',{origin:location.origin,source:existing.get('#companion').contentWindow,
  data:{type:'siro.alpha.mask',v:1,columns:2,rows:2,width:72,height:48,bits:'AQ=='}});
const posted=nativeMessages.filter(item=>item.type==='desktop.mask');
assert.equal(posted.length,1);
assert.equal(posted[0].width,80);
assert.equal(posted[0].character.bits,'AQ==');
assert.equal(posted[0].character.columns,2);
assert.ok(posted[0].rects.length>=1);
""",
    )


def test_bubble_in_focus_mode_hides_what_she_is_doing_but_keeps_what_needs_the_owner() -> None:
    run_desktop(
        """
const bubble=document.querySelector('#desktop-bubble');
const running=view([act('a','running',[tool('browser.navigate+read','running')])]);
running.selfActivity={paused:false,quiet:true,unshared:['n1']};
feed(running);
assert.equal(bubble.hidden,true);
const proposed=view([act('b','proposed',[tool('computer.execute','proposed',{program:'git'})])]);
proposed.selfActivity={paused:false,quiet:true};
feed(proposed);
assert.equal(bubble.hidden,false); assert.equal(bubble.children[1].textContent,'等你允許：執行 git');
running.selfActivity={paused:false};
feed(running);
assert.equal(bubble.children[1].textContent,'正在查：查今晚的星雲');
""",  # noqa: E501, RUF001
        before=BUBBLE_FEED,
    )
