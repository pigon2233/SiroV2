from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import TypedDict

import pytest
from test_frontend_control import run_control


class NodeSpec(TypedDict):
    tag: str
    attrs: dict[str, str]
    children: list[NodeSpec]


class PageStructure(HTMLParser):
    """Keep the real body hierarchy; scripts and private runtime data are unnecessary."""

    def __init__(self) -> None:
        super().__init__()
        self.root: NodeSpec = {"tag": "body", "attrs": {}, "children": []}
        self.stack = [self.root]
        self.in_body = False
        self.ignored = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "body":
            self.in_body = True
            self.root["attrs"] = {key: value or "" for key, value in attrs}
            return
        if not self.in_body:
            return
        if tag in {"script", "style"}:
            self.ignored = True
        if self.ignored:
            return
        node: NodeSpec = {
            "tag": tag,
            "attrs": {key: value or "" for key, value in attrs},
            "children": [],
        }
        self.stack[-1]["children"].append(node)
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag == "body":
            self.in_body = False
        if tag in {"script", "style"}:
            self.ignored = False
        if self.ignored:
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == tag:
                self.stack = self.stack[:index]
                break


PAGES = (
    "chat",
    "tasks",
    "memory",
    "capabilities",
    "computer",
    "skills",
    "settings",
    "permissions",
    "system",
)


def page_structure() -> NodeSpec:
    parser = PageStructure()
    parser.feed(Path("src/siro/services/presentation/static/index.html").read_text())
    return parser.root


def run_navigation(checks: str, initial_hash: str = "#/chat") -> None:
    """Extend the established control harness with the actual body and browser history."""
    setup = r"""
const oldNodes = new Map(roots.map(node => [node.id, node]));
const focusChanges = [], historyWrites = [];
const descendants = node => node.children.flatMap(child => [child, ...descendants(child)]);
const matches = (node, selector) => {
  if (selector.startsWith('#')) return node.id === selector.slice(1);
  if (selector.startsWith('.'))
    return (node.className || '').split(/\s+/).includes(selector.slice(1));
  const attribute = /^\[([^=\]]+)(?:=["']?([^"'\]]+)["']?)?\]$/.exec(selector);
  if (attribute) return node.hasAttribute(attribute[1]) &&
    (attribute[2] === undefined || node.getAttribute(attribute[1]) === attribute[2]);
  return node.tagName === selector;
};
const decorate = (node, attrs = {}) => {
  node.attributes = {...attrs}; node.dataset = {};
  node.className = attrs.class || ''; node.ownerDocument = document;
  node.hidden = Object.hasOwn(attrs, 'hidden'); node.inert = Object.hasOwn(attrs, 'inert');
  for (const [name,value] of Object.entries(attrs)) if (name.startsWith('data-'))
    node.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
  node.id = attrs.id || node.id;
  node.getAttribute = name => Object.hasOwn(node.attributes,name) ? node.attributes[name] : null;
  node.hasAttribute = name => Object.hasOwn(node.attributes,name);
  node.setAttribute = (name,value) => {node.attributes[name]=String(value);};
  node.removeAttribute = name => {delete node.attributes[name];};
  node.replaceChildren = (...children) => {node.textContent='';node.append(...children);};
  node.eventListeners = new Map();
  node.addEventListener = (name,callback) => {
    if (!node.eventListeners.has(name)) node.eventListeners.set(name,[]);
    node.eventListeners.get(name).push(callback);
  };
  node.querySelectorAll = selector => descendants(node)
    .filter(child => selector.split(',').some(part=>matches(child,part.trim())));
  node.querySelector = selector => node.querySelectorAll(selector)[0] || null;
  node.closest = selector => {
    for (let current=node;current;current=current.parent)
      if (matches(current,selector)) return current;
    return null;
  };
  node.focus = () => {document.activeElement=node;focusChanges.push(node.id || node.tagName);};
  node.remove = () => {
    if (node.parent) node.parent.children=node.parent.children.filter(child=>child!==node);
  };
  node.contentWindow ||= {syntheticRenderer:true};
  return node;
};
const build = spec => {
  const node=decorate(oldNodes.get(spec.attrs.id) || new Element(spec.tag),spec.attrs);
  node.tagName=spec.tag; node.children=[];
  for(const child of spec.children) node.appendChild(build(child));
  return node;
};
roots.splice(0,roots.length,build(PAGE_SPEC));
document.body=roots[0];document.title='SIRO';
document.querySelectorAll=selector=>[document.body,...descendants(document.body)]
  .filter(node=>selector.split(',').some(part=>matches(node,part.trim())));
document.querySelector=selector=>document.querySelectorAll(selector)[0] || null;
document.createElement=tag=>decorate(new Element(tag));
document.createTextNode=text=>{
  const node=document.createElement('#text');node.textContent=text;return node;
};
document.getElementById=id=>document.querySelector('#'+id);
location.hash=INITIAL_HASH;
const historyEntries=[INITIAL_HASH];let historyIndex=0;
const history={
  pushState(state,title,url) {
    historyEntries.splice(historyIndex+1);historyEntries.push(String(url));historyIndex++;
    location.hash=String(url);historyWrites.push({method:'push',url:String(url)});
  },
  replaceState(state,title,url) {
    historyEntries[historyIndex]=String(url);location.hash=String(url);
    historyWrites.push({method:'replace',url:String(url)});
  },
  back() {
    if(historyIndex){location.hash=historyEntries[--historyIndex];
      dispatchWindow('popstate');dispatchWindow('hashchange');}
  },
  forward() {
    if(historyIndex+1<historyEntries.length){location.hash=historyEntries[++historyIndex];
      dispatchWindow('popstate');dispatchWindow('hashchange');}
  }
};
window.location=location;window.history=history;globalThis.history=history;
const routeLink = page => document.querySelectorAll('[data-nav]')
  .find(link=>link.dataset.nav===page);
const clickLink = async link => {
  assert(link,'Missing route link');let prevented=false;
  const event={target:link,currentTarget:link,button:0,
    preventDefault(){prevented=true;}};
  await link.onclick?.(event);
  for(const callback of link.eventListeners.get('click') || []) await callback(event);
  if(!prevented && link.getAttribute('href')?.startsWith('#')) {
    history.pushState({},'',link.getAttribute('href'));dispatchWindow('hashchange');
  }
};
const visiblePages = () => document.querySelectorAll('[data-page]')
  .filter(node=>!node.hidden).map(node=>node.dataset.page);
const assertPage = page => {
  assert.equal(activePage,page);assert.deepEqual(visiblePages(),[page]);
  for(const pane of document.querySelectorAll('[data-page]')) {
    assert.equal(pane.inert,pane.dataset.page!==page,'Inactive work must not take keyboard focus');
  }
  for(const link of document.querySelectorAll('[data-nav]'))
    assert.equal(link.getAttribute('aria-current')==='page',link.dataset.nav===page);
};
"""
    run_control(
        "const PAGE_SPEC="
        + json.dumps(page_structure())
        + ";const INITIAL_HASH="
        + json.dumps(initial_hash)
        + ";\n"
        + setup
        + checks
    )


def test_work_pages_have_separate_dom_and_global_stop_is_outside_them() -> None:
    root = page_structure()
    ids: list[str] = []
    panes: dict[str, NodeSpec] = {}
    owners: dict[str, str | None] = {}

    def visit(node: NodeSpec, page: str | None = None) -> None:
        attrs = node["attrs"]
        if "data-page" in attrs:
            assert page is None, "Work pages must not nest inside another work page"
            page = attrs["data-page"]
            assert page not in panes
            panes[page] = node
        if "id" in attrs:
            ids.append(attrs["id"])
            owners[attrs["id"]] = page
        for child in node["children"]:
            visit(child, page)

    visit(root)
    assert len(ids) == len(set(ids)), (
        "A second renderer or duplicate controls create parallel owners"
    )
    assert set(panes) == set(PAGES)
    assert owners["messages"] == owners["chat"] == owners["companion"] == "chat"
    assert owners["goal-task-panel"] == "tasks"
    assert owners["memory-items"] == "memory"
    assert owners["tool-proposals"] == owners["workspace-file"] == "computer"
    assert owners["capability-items"] == "capabilities"
    assert owners["skill-candidate-panel"] == owners["improvement-proposal-panel"] == "skills"
    assert owners["cancel"] is None
    assert owners["activity-notice"] is None


@pytest.mark.parametrize("page", PAGES)
def test_direct_route_initialization_shows_only_the_requested_work(page: str) -> None:
    run_navigation(
        f"""
initializePageNavigation();assertPage({json.dumps(page)});
assert.equal(calls.length,0,'Opening a work page must not execute or bootstrap anything');
assert.equal(sockets.length,0);assert.equal(timers.size,0);
""",
        initial_hash=f"#/{page}",
    )


@pytest.mark.parametrize(
    "hash_value", ["", "#/unknown", "#/tasks/private-canary", "#/%ZZ", "#/<img src=x>"]
)
def test_unknown_or_malformed_hash_falls_back_without_interpreting_or_echoing_it(
    hash_value: str,
) -> None:
    run_navigation(
        """
initializePageNavigation();assertPage('chat');
assert(!document.title.includes('private-canary'));
assert(!document.body.textContent.includes('<img src=x>'));
assert.equal(calls.length,0);assert.equal(sockets.length,0);
""",
        initial_hash=hash_value,
    )


def test_navigation_click_back_forward_and_reinitialization_keep_draft_and_dom_owners() -> None:
    run_navigation(
        """
initializePageNavigation();
const textarea=document.querySelector('#text'),renderer=document.querySelector('#companion');
textarea.value='尚未送出的繁體中文草稿';
const listenerCounts=[(listeners.get('hashchange') || []).length,
 (listeners.get('popstate') || []).length];
initializePageNavigation();
assert.deepEqual([(listeners.get('hashchange') || []).length,
 (listeners.get('popstate') || []).length],listenerCounts);
await clickLink(routeLink('tasks'));assertPage('tasks');
assert(document.activeElement?.hasAttribute('data-page-heading'),
 'A deliberate navigation must move keyboard focus to the work heading');
assert.equal(document.activeElement.closest('[data-page]').dataset.page,'tasks');
await clickLink(routeLink('memory'));assertPage('memory');
history.back();assertPage('tasks');history.back();assertPage('chat');
history.forward();assertPage('tasks');
assert.equal(textarea.value,'尚未送出的繁體中文草稿');
assert.strictEqual(document.querySelector('#text'),textarea);
assert.strictEqual(document.querySelector('#companion'),renderer);
assert.equal(historyWrites.filter(write=>write.method==='push').length,2);
assert.equal(calls.length,0);assert.equal(sockets.length,0);
"""
    )


@pytest.mark.parametrize("event_name", ["hashchange", "popstate"])
def test_browser_navigation_events_reconcile_without_writing_another_history_entry(
    event_name: str,
) -> None:
    run_navigation(
        f"""
initializePageNavigation();const before=historyWrites.length;
location.hash='#/skills';dispatchWindow({json.dumps(event_name)});assertPage('skills');
assert.equal(historyWrites.length,before,'Reading browser history must not push another entry');
location.hash='#/unknown';dispatchWindow({json.dumps(event_name)});assertPage('chat');
assert.equal(historyWrites.filter(write=>write.method==='push').length,0);
assert.equal(calls.length,0);assert.equal(sockets.length,0);
"""
    )


def test_repeated_same_page_and_invalid_programmatic_navigation_do_not_create_actions() -> None:
    run_navigation(
        """
initializePageNavigation();
const writes=historyWrites.length;
navigateToPage('chat');navigateToPage('chat');
assert.equal(historyWrites.length,writes);
navigateToPage('untrusted-private-canary');assertPage('chat');
assert(!String(location.hash).includes('private-canary'));
assert.equal(calls.length,0);assert.equal(sockets.length,0);assert.equal(timers.size,0);
"""
    )


def test_pending_turn_survives_navigation_without_resubmission_or_new_connection() -> None:
    run_navigation(
        """
initializePageNavigation();const owner=await readyControl();
let resolveTurn;
fetchPlan=()=>new Promise(resolve=>{resolveTurn=resolve;});
const submission=submitText('synthetic navigation submission');
await until(()=>targetCalls().length===1);
const request=targetCalls()[0],pending=pendingSubmission,generation=submissionGeneration;
const renderer=document.querySelector('#companion'),sessionOwner=sessionAccess;
owner.message({type:'turn_started',turn_id:'synthetic-preserved-turn'});
for(const page of ['tasks','memory','computer','system','chat']) navigateToPage(page);
history.back();history.forward();
assert.equal(targetCalls().length,1);assert.equal(request.url,'/v1/conversations/browser/turns');
assert.strictEqual(pendingSubmission,pending);assert(!pending.signal.aborted);
assert.equal(submissionGeneration,generation);assert.strictEqual(socket,owner);
assert.strictEqual(sessionAccess,sessionOwner);assert.equal(sockets.length,1);
assert.strictEqual(document.querySelector('#companion'),renderer);
resolveTurn(response(200,{turn_id:'ignored-http-response-turn'}));await submission;
assert.equal(currentTurn,'synthetic-preserved-turn');assert.equal(targetCalls().length,1);
"""
    )


def test_file_preview_explains_missing_service_and_never_bootstraps_actions() -> None:
    run_navigation(
        """
location.protocol='file:';await boot();assertPage('permissions');
assert.equal(calls.length,0);assert.equal(sockets.length,0);assert.equal(timers.size,0);
assert.equal(document.querySelector('#connection').textContent,'介面預覽');
assert.equal(document.querySelector('#service-notice').hidden,false);
assert(document.querySelector('#service-notice').textContent.includes('尚未連接 SIRO'));
assert(document.querySelectorAll('button, input, textarea').every(control=>control.disabled));
navigateToPage('tasks');assertPage('tasks');
assert.equal(calls.length,0);assert.equal(sockets.length,0);
""",
        initial_hash="#/permissions",
    )


def test_incoming_proposals_and_pending_approval_keep_route_and_never_repeat_approval() -> None:
    run_navigation(
        """
initializePageNavigation();await readyControl();authorizationMode='safe';
navigateToPage('memory');
renderToolProposal({proposal_id:'synthetic-proposal',capability:'computer.execute',
 scope:'synthetic read',target:'synthetic target',risk:'read-only'});
assertPage('memory');assert.equal(targetCalls().length,0);
const card=document.querySelector('#tool-synthetic-proposal');
const approve=card.children.find(child=>child.tagName==='button');assert(approve);
let resolveApproval;fetchPlan=()=>new Promise(resolve=>{resolveApproval=resolve;});
const approval=approve.onclick();await until(()=>targetCalls().length===1);
for(const page of ['computer','tasks','settings','chat','computer']) navigateToPage(page);
history.back();history.forward();assert(approve.disabled);
assert.equal(targetCalls().length,1);
assert.equal(targetCalls()[0].url,'/v1/tool-proposals/synthetic-proposal/approve');
assert.deepEqual(JSON.parse(targetCalls()[0].options.body),{approved:true});
resolveApproval(response(200,{}));await approval;
assert.equal(targetCalls().length,1);assert.equal(sockets.length,1);
"""
    )


def test_streaming_answer_updates_existing_chat_while_another_work_page_is_open() -> None:
    run_navigation(
        """
initializePageNavigation();const owner=await readyControl();navigateToPage('tasks');
const messages=document.querySelector('#messages');
owner.message({type:'turn_started',turn_id:'synthetic-stream-turn'});
owner.message({type:'assistant_started',stream_id:'synthetic-stream'});
owner.message({type:'assistant_delta',stream_id:'synthetic-stream',text:'合成來源仍然連續'});
assertPage('tasks');assert.equal(currentTurn,'synthetic-stream-turn');
assert(messages.textContent.includes('合成來源仍然連續'));
owner.message({type:'assistant_terminal',stream_id:'synthetic-stream',state:'completed'});
await flush();assertPage('tasks');assert.equal(currentTurn,undefined);
navigateToPage('chat');assert.strictEqual(document.querySelector('#messages'),messages);
assert(messages.textContent.includes('合成來源仍然連續'));
assert.equal(targetCalls().length,0,'Returning must not resubmit the turn or replay speech');
assert.equal(sockets.length,1);
"""
    )


def test_active_speech_is_not_replayed_on_navigation_and_global_cancel_still_stops_it() -> None:
    run_navigation(
        """
initializePageNavigation();await readyControl();
const audios=[],revoked=[];
globalThis.Audio=class {
 constructor(src){this.src=src;this.played=0;this.pauses=0;audios.push(this);}
 play(){this.played++;this.onplay?.();return Promise.resolve();}
 pause(){this.pauses++;}removeAttribute(){}load(){}
};
URL.createObjectURL=()=> 'blob:synthetic-navigation';
URL.revokeObjectURL=url=>revoked.push(url);
document.querySelector('#voice-output').checked=true;
fetchPlan=async url=>url==='/v1/audio/speech/plan' ? response(200,{
 segments:['合成的完整語音。'],spoken_text:'合成的完整語音。',version:'synthetic-v1',
 max_chars:80,max_segments:128,max_total_chars:8000,deadline_seconds:1200
}) : url==='/v1/audio/speech' ? new Response(new Uint8Array([1,2,3])) : response(200,{});
const narration=playTts('合成的完整語音。',{});
await until(()=>audios.length===1);
const audioOwner=ttsAudio,generation=ttsGeneration,controller=ttsController;
const before=targetCalls().length;currentTurn='synthetic-speaking-turn';
for(const page of ['tasks','memory','computer','skills','permissions','system'])
 navigateToPage(page);
assert.strictEqual(ttsAudio,audioOwner);assert.strictEqual(ttsController,controller);
assert.equal(ttsGeneration,generation);assert.equal(audios.length,1);
assert.equal(audios[0].played,1);assert.equal(audios[0].pauses,0);
assert.equal(targetCalls().length,before);assert.equal(sockets.length,1);
const cancel=document.querySelector('#cancel');assert.equal(cancel.closest('[data-page]'),null);
await cancel.onclick();await narration;
assert(audios[0].pauses>=1);assert.equal(ttsAudio,undefined);assert.equal(revoked.length,1);
assert.equal(targetCalls().filter(call=>call.url==='/v1/turns/synthetic-speaking-turn/cancel').length,1);
assert.equal(targetCalls().filter(call=>call.url==='/v1/audio/speech').length,1);
"""
    )
