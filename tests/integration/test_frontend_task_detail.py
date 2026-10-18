from __future__ import annotations

import pytest
from test_frontend_goal_tasks import FIXTURE
from test_frontend_navigation import run_navigation

GOAL_ID = "00000000-0000-0000-0000-000000000057"


def detail_scenario(checks: str, route: str = "#/tasks") -> None:
    run_navigation(
        FIXTURE
        + r"""
// The shared synthetic DOM does not reflect anchor.href into its attribute.
// Match the real browser's property reflection for this new anchor element.
const createElement = document.createElement;
document.createElement = tag => {
  const node = createElement(tag);
  if (tag === 'a') Object.defineProperty(node, 'href', {
    get() {return node.getAttribute('href');},
    set(value) {node.setAttribute('href', String(value));}
  });
  return node;
};
initializePageNavigation();
const detailStatus = document.querySelector('#goal-task-detail-status');
const compose = document.querySelector('#goal-task-compose');
const back = document.querySelector('#goal-task-back');
const secondId = '00000000-0000-0000-0000-000000000058';
const detailHash = '#/tasks/' + goalId;
"""
        + checks,
        initial_hash=route,
    )


def test_list_link_opens_one_task_and_history_never_dispatches() -> None:
    detail_scenario(
        r"""
await readyControl(); await showTasks([goalView(), goalView({goal_id:secondId})]);
const before = calls.length;
const link = taskCards.querySelector('a');
assert.equal(link.getAttribute('href'), detailHash);
await clickLink(link); assertPage('tasks');
assert.equal(location.hash, detailHash); assert(compose.hidden && compose.inert);
assert.equal(taskCards.children.length, 1); assert(taskAction('approve'));
assert.equal(document.querySelector('#goal-'+secondId+'-approve'), null);
assert(document.title.includes('任務詳情')); assert.equal(back.hidden, false);
history.back(); assertPage('tasks'); assert.equal(location.hash, '#/tasks');
assert.equal(taskCards.children.length, 2); assert(!compose.hidden && !compose.inert);
history.forward(); assert.equal(taskCards.children.length, 1);
await back.onclick(); assert.equal(location.hash, '#/tasks');
assert.equal(taskCards.children.length, 2); assert.equal(calls.length, before);
assert.equal(sockets.length, 1); assert.equal(timers.size, 0);
"""
    )


def test_direct_detail_requires_explicit_readback_and_keeps_source_and_actions() -> None:
    detail_scenario(
        r"""
assertPage('tasks'); assert(compose.hidden); assert.equal(taskCards.textContent, '');
assert(detailStatus.textContent.includes('查詢')); assert.equal(calls.length, 0);
await readyControl(); assert.equal(taskCalls().length, 0);
await showTasks([goalView({state:'completed',next_step:null,task:{...goalView().task,
 approved_at:'2026-10-14T09:00:00+00:00',observations:[observed()]}})]);
assert.equal(taskCards.children.length, 1);
for(const text of ['第 3 行','synthetic task','SHA256','批准時間','1','待辦尚未執行'])
 assert(taskCards.textContent.includes(text));
assert(taskAction('remove')); assert(taskCalls().every(call=>call.options.method==='GET'));
assert.equal(timers.size, 0);
""",
        route=f"#/tasks/{GOAL_ID}",
    )


def test_missing_from_bounded_snapshot_is_not_claimed_deleted() -> None:
    detail_scenario(
        r"""
await readyControl(); await showTasks([goalView({goal_id:secondId})]);
assert.equal(taskCards.children.length, 0);
assert(detailStatus.textContent.includes('目前保存快照'));
assert(detailStatus.textContent.includes('無法據此判斷是否已刪除')); assert(!taskAction('approve'));
assert.equal(taskCalls().length, 1); await back.onclick();
assert.equal(taskCards.children.length, 1);
""",
        route=f"#/tasks/{GOAL_ID}",
    )


@pytest.mark.parametrize("boundary", ["disconnect", "unknown", "foreground"])
def test_detail_invalidates_old_controls_and_preserves_readback_gate(boundary: str) -> None:
    action = {
        "disconnect": "owner.disconnect();",
        "unknown": (
            "fetchPlan=async()=>{throw Error('private-error');}; "
            "await taskAction('approve').onclick();"
        ),
        "foreground": "owner.message({type:'turn_started',turn_id:'new-turn'});",
    }[boundary]
    detail_scenario(
        r"""
const owner=await readyControl(); await showTasks(); const old=taskAction('approve');
"""
        + action
        + r"""
assert.equal(taskCards.textContent,''); assert(detailStatus.textContent.includes('查詢'));
const before=taskCalls().length; await old.onclick(); assert.equal(taskCalls().length,before);
assert(!taskStatus.textContent.includes('private-error'));
""",
        route=f"#/tasks/{GOAL_ID}",
    )


def test_detail_uses_existing_revision_bound_mutation_and_cancel_readback() -> None:
    detail_scenario(
        r"""
await readyControl(); await showTasks();
fetchPlan=async()=>response(200,{goal:goalView({state:'waiting_external',revision:2,
 task:{...goalView().task,approved_at:'2026-10-14T10:00:00+00:00',pause_reason:'paused'}})});
await taskAction('approve').onclick();
assert.equal(taskCalls().length,2);
assert.equal(taskCalls()[1].url,taskUrl+'/'+goalId+'/approve');
assert.deepEqual(JSON.parse(taskCalls()[1].options.body),{revision:1});
assert(taskAction('resume')); assert(taskCards.textContent.includes('你已暫停'));
fetchPlan=async()=>response(200,{goal:goalView({state:'cancelled',revision:3,task:{...goalView().task,
 approved_at:'2026-10-14T10:00:00+00:00'}})});
await taskAction('cancel').onclick(); assert(taskAction('remove'));
assert.equal(taskCards.children.length,1); assert.equal(location.hash,detailHash);
""",
        route=f"#/tasks/{GOAL_ID}",
    )


@pytest.mark.parametrize(
    "route", ["#/tasks/private-path", "#/tasks/../memory", "#/tasks/" + GOAL_ID + "/approve"]
)
def test_invalid_detail_route_never_becomes_an_action_or_private_label(route: str) -> None:
    detail_scenario(
        "assertPage('chat'); assert.equal(calls.length,0); "
        "assert(!document.title.includes('private'));",
        route=route,
    )


def test_detail_switch_while_get_pending_keeps_latest_selection_without_extra_request() -> None:
    detail_scenario(
        r"""
await readyControl(); const pending=delayed(); fetchPlan=async()=>pending.promise;
const reading=refreshTasks.onclick(); await until(()=>taskCalls().length===1);
history.pushState(null,'','#/tasks/'+secondId); dispatchWindow('hashchange');
pending.resolve(response(200,taskReply([goalView(),goalView({goal_id:secondId})]))); await reading;
assert.equal(taskCards.children.length,1); assert(!taskAction('approve'));
assert(document.querySelector('#goal-'+secondId+'-approve'));
assert.equal(taskCalls().length,1);
""",
        route=f"#/tasks/{GOAL_ID}",
    )
