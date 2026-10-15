from __future__ import annotations

from pathlib import Path

import pytest
from test_frontend_control import run_control

FIXTURE = r"""
const goalId = '00000000-0000-0000-0000-000000000057';
const taskUrl = '/v1/goal-tasks/browser';
const goalView = (changes = {}) => ({
  goal_id:goalId, state:'proposed', next_step:'notes.md', revision:1,
  steps_used:0, max_steps:8, deadline:'2026-10-15T00:00:00+00:00',
  task:{profile:'document-checklist-v1',paths:['notes.md'],approved_at:null,
    pause_reason:null,intent_path:null,observations:[]}, ...changes
});
const taskReply = (goals = [goalView()], active = null) => ({
  available:true, profile:'document-checklist-v1',max_tasks:20,
  active_goal_id:active,goals
});
const observed = (changes = {}) => ({path:'notes.md',status:'completed',
  sha256:'a'.repeat(64),read_at:'2026-10-14T10:00:00+00:00',
  matches:[{line:3,text:'- [ ] synthetic task'}],truncated:false,error:null,...changes});
const delayed = () => { let resolve,reject;
  const promise = new Promise((done,fail) => {resolve=done;reject=fail;});
  return {promise,resolve,reject};
};
const taskField = document.querySelector('#goal-task-paths');
const createTask = document.querySelector('#goal-task-create');
const refreshTasks = document.querySelector('#goal-task-refresh');
const taskStatus = document.querySelector('#goal-task-status');
const taskCards = document.querySelector('#goal-task-items');
const taskCalls = () => targetCalls().filter(call => call.url.startsWith(taskUrl));
const taskAction = action => document.querySelector(`#goal-${goalId}-${action}`);
assert(taskField && createTask && refreshTasks && taskStatus && taskCards,
  'Missing owner-approved durable task panel');
const showTasks = async (goals = [goalView()], active = null) => {
  fetchPlan = async () => response(200,taskReply(goals,active));
  await refreshTasks.onclick();
};
"""


def goal_control(checks: str) -> None:
    run_control(FIXTURE + checks)


def test_owner_task_panel_explains_scope_and_proposal_before_execution() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    computer = html.split('id="computer-panel"', 1)[1].split('id="memories-panel"', 1)[0]
    panel = computer.split('id="goal-task-panel"', 1)[1].split("</section>", 1)[0]
    assert "交給 SIRO 的任務" in panel
    assert "1\u20135" in panel
    assert "唯讀" in panel
    assert "每行" in panel
    assert "批准" in panel
    assert "待辦" in panel


def test_connection_never_proposes_or_approves_any_task() -> None:
    goal_control(
        """
await readyControl(); await flush();
assert.equal(taskCalls().length,0);
assert.equal(createTask.disabled,false); assert.equal(refreshTasks.disabled,false);
assert.equal(timers.size,0);
"""
    )


def test_unauthenticated_programmatic_actions_do_not_dispatch() -> None:
    goal_control(
        """
taskField.value='notes.md'; await createTask.onclick(); await refreshTasks.onclick();
assert.equal(calls.length,0); assert.equal(taskCards.textContent,'');
"""
    )


def test_propose_preserves_exact_paths_and_full_mode_requires_explicit_approval() -> None:
    goal_control(
        """
await readyControl(); authorizationMode='full';
taskField.value='notes.md\\nproject/tasks.txt';
const proposed=goalView({task:{...goalView().task,paths:['notes.md','project/tasks.txt']}});
fetchPlan=async () => response(200,{goal:proposed});
await createTask.onclick();
assert.equal(taskCalls().length,1);
assert.equal(taskCalls()[0].options.method,'POST');
assert.deepEqual(JSON.parse(taskCalls()[0].options.body),{paths:['notes.md','project/tasks.txt']});
assert(new Headers(taskCalls()[0].options.headers).get('Authorization').startsWith('Bearer '));
assert(taskCards.textContent.includes('待批准')); assert(taskCards.textContent.includes('唯讀'));
assert(taskCards.textContent.includes('project/tasks.txt'));
assert(taskCards.textContent.includes('版本 1'));
assert(taskAction('approve')); assert(!taskAction('resume'));
fetchPlan=async () => response(200,{goal:goalView({state:'running',revision:2,
  task:{...proposed.task,approved_at:'2026-10-14T10:00:00+00:00'}})});
await taskAction('approve').onclick();
assert.equal(taskCalls().length,2); assert.equal(taskCalls()[1].url,taskUrl+'/'+goalId+'/approve');
assert.deepEqual(JSON.parse(taskCalls()[1].options.body),{revision:1});
assert(!taskAction('approve')); assert(taskAction('pause')); assert(taskAction('cancel'));
assert([...timers.values()].some(timer => timer.delay===1000));
"""
    )


@pytest.mark.parametrize(
    "paths",
    [
        "",
        "a\nb\nc\nd\ne\nf",
        "/tmp/a",
        "../a",
        "a/../b",
        "a\\b",
        "a\na",
        " a",
        "a ",
        "a//b",
        "./a",
        "a\u0000b",
        "notes\u0085.md",
    ],
)
def test_invalid_selected_paths_are_rejected_before_any_request(paths: str) -> None:
    import json

    goal_control(
        f"""
await readyControl(); taskField.value={json.dumps(paths)}; await createTask.onclick();
assert.equal(taskCalls().length,0); assert.equal(taskCards.textContent,'');
"""
    )


def test_completed_observations_show_provenance_and_never_claim_todos_performed() -> None:
    goal_control(
        """
await readyControl(); await showTasks([goalView({state:'completed',revision:4,steps_used:1,
  task:{...goalView().task,approved_at:'2026-10-14T09:00:00+00:00',observations:[observed()]}})]);
assert(taskCards.textContent.includes('已讀取'));
assert(taskCards.textContent.includes('待辦尚未執行'));
assert(taskCards.textContent.includes('a'.repeat(64)));
assert(taskCards.textContent.includes('第 3 行')); assert(taskCards.textContent.includes('2026'));
assert(!taskAction('approve')); assert(!taskAction('resume')); assert(!taskAction('cancel'));
assert(taskAction('remove')); assert.equal(timers.size,0);
"""
    )


def test_restart_unknown_intent_known_and_unread_parts_remain_distinct() -> None:
    goal_control(
        """
await readyControl(); await showTasks([goalView({state:'waiting_external',revision:6,steps_used:2,
 task:{...goalView().task,paths:['notes.md','unknown.txt','unread.md'],
 approved_at:'2026-10-14T09:00:00+00:00',pause_reason:'interrupted_restart',
 intent_path:'unknown.txt',observations:[observed()]}})]);
assert(taskCards.textContent.includes('notes.md\uff1a已讀取'));
assert(taskCards.textContent.includes('unknown.txt\uff1a讀取結果未知'));
assert(taskCards.textContent.includes('unread.md\uff1a尚未讀取'));
assert(taskAction('resume')); assert(taskAction('cancel')); assert(!taskAction('approve'));
fetchPlan=async () => response(200,{goal:goalView({state:'running',revision:7,
 task:{...goalView().task,paths:['notes.md','unknown.txt','unread.md'],
 approved_at:'2026-10-14T09:00:00+00:00',observations:[observed()]}})});
await taskAction('resume').onclick();
assert.equal(taskCalls()[1].url,taskUrl+'/'+goalId+'/resume');
assert.deepEqual(JSON.parse(taskCalls()[1].options.body),{revision:6});
assert(taskAction('pause')); assert(taskCards.textContent.includes('notes.md\uff1a已讀取'));
"""
    )


@pytest.mark.parametrize(
    "action,state", [("pause", "running"), ("cancel", "proposed"), ("remove", "failed")]
)
def test_controls_bind_displayed_revision_and_terminal_delete(action: str, state: str) -> None:
    reply = (
        "{removed:true}"
        if action == "remove"
        else "{goal:goalView({state:'cancelled',revision:12})}"
    )
    outcome = (
        "assert.equal(taskCards.textContent,'');"
        if action == "remove"
        else "assert(taskAction('remove')); assert(!taskAction('cancel'));"
    )
    goal_control(
        f"""
await readyControl(); await showTasks([goalView({{state:'{state}',revision:11}})]);
const button=taskAction('{action}'); assert(button);
fetchPlan=async () => response(200,{reply});
await button.onclick(); assert.equal(taskCalls().length,2);
const sent=taskCalls()[1]; assert.deepEqual(JSON.parse(sent.options.body),{{revision:11}});
assert.equal(sent.options.method,'{("DELETE" if action == "remove" else "POST")}');
assert.equal(sent.url,taskUrl+'/'+goalId{("" if action == "remove" else "+'/'+'" + action + "'")});
{outcome}
"""
    )


@pytest.mark.parametrize(
    "body",
    [
        "null",
        "[]",
        "{...taskReply(),owner_session_id:'private-canary'}",
        "{...taskReply(),max_tasks:21}",
        "{...taskReply(),profile:'computer.execute'}",
        "taskReply([goalView({revision:-1})])",
        "taskReply([goalView({revision:0})])",
        "taskReply([goalView({state:'approved'})])",
        "taskReply([goalView({max_steps:99})])",
        "taskReply([goalView({goal_id:'../private-canary'})])",
        "taskReply([goalView({goal_id:[goalId]})])",
        "taskReply([goalView({next_step:'computer.execute'})])",
        "taskReply([goalView({deadline:'2026-10-15T00:00:00'})])",
        "taskReply([goalView({task:{...goalView().task,workspace:'private-canary'}})])",
        "taskReply([goalView({task:{...goalView().task,paths:['../private-canary']}})])",
        "taskReply([goalView({task:{...goalView().task,intent_path:'private-canary'}})])",
        "taskReply([goalView({task:{...goalView().task,observations:[observed({path:'private-canary'})]}})])",
        "taskReply([goalView({task:{...goalView().task,observations:[observed({sha256:null})]}})])",
        "taskReply([goalView({task:{...goalView().task,observations:[observed({matches:[{line:0,text:'private-canary'}]})]}})])",
        "taskReply([goalView({task:{...goalView().task,observations:[observed({matches:[{line:1,text:'x'.repeat(257)}]})]}})])",
        "taskReply([goalView(),goalView()])",
        "taskReply([goalView()], '00000000-0000-0000-0000-000000000058')",
    ],
)
def test_closed_response_shape_rejects_invalid_private_or_authorizing_fields(body: str) -> None:
    goal_control(
        f"""
await readyControl(); fetchPlan=async () => response(200,{body}); await refreshTasks.onclick();
assert.equal(taskCards.textContent,''); assert(!taskStatus.textContent.includes('private-canary'));
assert.equal(taskCalls().length,1); assert.equal(timers.size,0);
"""
    )


def test_file_matches_are_plain_text_without_html_execution() -> None:
    goal_control(
        """
Element.prototype.__defineSetter__('innerHTML',() => {throw Error('unsafe HTML');});
await readyControl(); const payload='<img src=x onerror=syntheticEvil()>';
await showTasks([goalView({state:'completed',task:{...goalView().task,
 observations:[observed({matches:[{line:7,text:payload}]})]}})]);
assert(taskCards.textContent.includes(payload));
assert.equal(taskCalls().length,1);
"""
    )


@pytest.mark.parametrize("status", [401, 409, 503, 500])
def test_failed_mutation_is_never_automatically_retried_even_on_auth_error(status: int) -> None:
    goal_control(
        f"""
await readyControl(); await showTasks();
fetchPlan=async () => response({status},{{detail:'session token is invalid or expired'}});
await taskAction('approve').onclick();
assert.equal(taskCalls().length,2);
assert.equal(calls.filter(call=>call.url==='/v1/session').length,1);
assert.equal(taskCards.textContent,''); assert(taskStatus.textContent.includes('未確認'));
assert(taskStatus.textContent.includes('重新查詢')); assert.equal(timers.size,0);
"""
    )


def test_network_unknown_submission_requires_readback_and_never_replays_mutation() -> None:
    goal_control(
        """
await readyControl(); await showTasks(); fetchPlan=async () => {throw Error('private-canary');};
await taskAction('approve').onclick(); assert.equal(taskCalls().length,2);
assert(taskStatus.textContent.includes('未確認'));
assert(!taskStatus.textContent.includes('private-canary'));
assert.equal(taskCards.textContent,''); assert.equal(timers.size,0);
fetchPlan=async () => response(200,taskReply([goalView({state:'completed'})]));
await refreshTasks.onclick(); assert.equal(taskCalls().length,3);
assert.equal(taskCalls()[2].options.method,'GET'); assert(taskAction('remove'));
"""
    )


@pytest.mark.parametrize("boundary", ["new_turn", "disconnect", "reconnect", "unload"])
def test_late_snapshot_and_mutation_cannot_revive_retired_page_state(boundary: str) -> None:
    trigger = {
        "new_turn": "owner.message({type:'turn_started',turn_id:'foreground-turn'});",
        "disconnect": "owner.disconnect();",
        "reconnect": "connectControl();",
        "unload": "dispatchWindow('beforeunload');",
    }[boundary]
    goal_control(
        f"""
const owner=await readyControl(); await showTasks();
const pending=delayed(); fetchPlan=async () => pending.promise;
const clicked=taskAction('approve').onclick(); await until(()=>taskCalls().length===2);
const signal=taskCalls()[1].options.signal;
{trigger} await flush(); assert.equal(signal.aborted,true); assert.equal(taskCards.textContent,'');
pending.resolve(response(200,{{goal:goalView({{state:'running'}})}})); await clicked;
assert.equal(taskCards.textContent,''); assert.equal(taskCalls().length,2);
assert(![...timers.values()].some(timer=>timer.delay===1000));
"""
    )


def test_request_timeout_aborts_and_unknown_mutation_does_not_recur() -> None:
    goal_control(
        """
await readyControl(); await showTasks(); const pending=delayed();
fetchPlan=async () => pending.promise;
const clicked=taskAction('approve').onclick(); await until(()=>taskCalls().length===2);
fireTimer(timer=>timer.delay===5000);
assert.equal(taskCalls()[1].options.signal.aborted,true);
assert.equal(taskCards.textContent,''); assert(taskStatus.textContent.includes('未確認'));
pending.resolve(response(200,{goal:goalView({state:'completed'})})); await clicked;
assert.equal(taskCards.textContent,''); assert.equal(taskCalls().length,2);
assert.equal(timers.size,0);
"""
    )


def test_manual_refresh_retires_prior_snapshot_without_old_result_reappearing() -> None:
    goal_control(
        """
await readyControl(); const old=delayed(),current=delayed();
fetchPlan=async () => taskCalls().length===1 ? old.promise : current.promise;
const first=refreshTasks.onclick(); await until(()=>taskCalls().length===1);
const second=refreshTasks.onclick(); await until(()=>taskCalls().length===2);
assert.equal(taskCalls()[0].options.signal.aborted,true);
current.resolve(response(200,taskReply([]))); await second;
old.resolve(response(200,taskReply())); await first;
assert.equal(taskCards.textContent,''); assert.equal(timers.size,0);
"""
    )


def test_polling_is_get_only_bounded_and_terminal_stops_it() -> None:
    goal_control(
        """
await readyControl(); await showTasks([goalView({state:'running'})],goalId);
for(let index=0;index<30;index++) {
 fireTimer(timer=>timer.delay===1000); await flush();
}
assert.equal(taskCalls().length,31);
assert(taskCalls().every(call=>call.options.method==='GET'));
assert.equal(timers.size,0); assert(taskStatus.textContent.includes('手動'));
await showTasks([goalView({state:'completed'})]); assert.equal(timers.size,0);
"""
    )


def test_unicode_and_internal_spaces_in_selected_file_names_are_preserved() -> None:
    goal_control(
        r"""
await readyControl(); taskField.value='會議/今日 筆記.md';
fetchPlan=async () => response(200,{goal:goalView({next_step:'會議/今日 筆記.md',
  task:{...goalView().task,paths:['會議/今日 筆記.md']}})});
await createTask.onclick();
assert.deepEqual(JSON.parse(taskCalls()[0].options.body),{paths:['會議/今日 筆記.md']});
assert(taskCards.textContent.includes('會議/今日 筆記.md')); assert(taskAction('approve'));
"""
    )


def test_saved_owner_scope_with_spaces_and_dot_git_component_is_shown_exactly() -> None:
    goal_control(
        """
await readyControl(); await showTasks([goalView({next_step:' leading.md ',
 task:{...goalView().task,paths:[' leading.md ','.git/note.md']}})]);
assert(taskCards.textContent.includes(' leading.md '));
assert(taskCards.textContent.includes('.git/note.md')); assert(taskAction('approve'));
fetchPlan=async () => response(200,{goal:goalView({state:'cancelled',revision:2,
 next_step:null,task:{...goalView().task,paths:[' leading.md ','.git/note.md']}})});
await taskAction('cancel').onclick(); assert.equal(taskCalls().length,2);
assert(taskAction('remove'));
"""
    )


def test_rapid_duplicate_approval_and_retired_button_cannot_dispatch_again() -> None:
    goal_control(
        """
await readyControl(); await showTasks(); const button=taskAction('approve'), pending=delayed();
fetchPlan=async () => pending.promise;
const first=button.onclick(); const second=button.onclick();
await until(()=>taskCalls().length===2); await second;
pending.resolve(response(200,{goal:goalView({state:'waiting_external',revision:2,
 task:{...goalView().task,approved_at:'2026-10-14T10:00:00+00:00'}})}));
await first; await button.onclick(); assert.equal(taskCalls().length,2);
assert(taskAction('resume'));
"""
    )


def test_unknown_mutation_blocks_further_mutations_until_successful_manual_readback() -> None:
    goal_control(
        """
await readyControl(); await showTasks(); const approve=taskAction('approve');
fetchPlan=async () => {throw Error('lost response');}; await approve.onclick();
taskField.value='notes.md'; await createTask.onclick(); await approve.onclick();
assert.equal(taskCalls().length,2); assert.equal(createTask.disabled,true);
await showTasks(); assert.equal(createTask.disabled,false);
fetchPlan=async () => response(200,{goal:goalView({state:'cancelled',revision:2})});
await taskAction('cancel').onclick(); assert.equal(taskCalls().length,4);
"""
    )


@pytest.mark.parametrize(
    "body",
    [
        "{goal:goalView({state:'running',revision:2}),raw_error:'private-canary'}",
        "{goal:goalView({state:'running',revision:1})}",
        "{goal:goalView({state:'running',revision:2,goal_id:'00000000-0000-0000-0000-000000000058'})}",
        "{goal:goalView({state:'running',revision:2,next_step:'other.md',task:{...goalView().task,paths:['other.md']}})}",
    ],
)
def test_mutation_response_must_bind_exact_displayed_identity_revision_and_scope(body: str) -> None:
    goal_control(
        f"""
await readyControl(); await showTasks(); fetchPlan=async () => response(200,{body});
await taskAction('approve').onclick(); assert.equal(taskCards.textContent,'');
assert(taskStatus.textContent.includes('未確認'));
assert(!taskStatus.textContent.includes('private-canary')); assert.equal(taskCalls().length,2);
"""
    )


def test_tools_disabled_history_remains_readable_and_only_safe_controls_work() -> None:
    goal_control(
        """
await readyControl(); fetchPlan=async () => response(200,{...taskReply(),available:false});
await refreshTasks.onclick(); assert(taskCards.textContent.includes('待批准'));
assert.equal(taskAction('approve').disabled,true);
assert.equal(taskAction('cancel').disabled,false);
assert.equal(createTask.disabled,true); await taskAction('approve').onclick();
assert.equal(taskCalls().length,1);
fetchPlan=async () => response(200,{goal:goalView({state:'cancelled',revision:2})});
await taskAction('cancel').onclick(); assert.equal(taskCalls().length,2);
"""
    )


def test_tools_switch_fences_pending_response_and_does_not_resume_it() -> None:
    goal_control(
        """
const owner=await readyControl(); await showTasks(); const pending=delayed();
fetchPlan=async () => pending.promise;
const clicked=taskAction('approve').onclick(); await until(()=>taskCalls().length===2);
owner.message({type:'kill_switch',name:'tools',enabled:false});
assert.equal(taskCalls()[1].options.signal.aborted,true); assert.equal(taskCards.textContent,'');
pending.resolve(response(200,{goal:goalView({state:'running',revision:2})})); await clicked;
owner.message({type:'kill_switch',name:'tools',enabled:true}); await flush();
assert.equal(taskCalls().length,2); assert.equal(taskCards.textContent,'');
assert.equal(createTask.disabled,true); assert.equal(timers.size,0);
"""
    )


def test_task_history_limit_keeps_all_twenty_records_and_refuses_new_proposal() -> None:
    goal_control(
        """
await readyControl(); const history=Array.from({length:20},(_,index)=>goalView({
  goal_id:'00000000-0000-0000-0000-'+String(index+1).padStart(12,'0'),state:'cancelled'}));
await showTasks(history); assert.equal(taskCards.children.length,20);
assert.equal(createTask.disabled,true); taskField.value='notes.md'; await createTask.onclick();
assert.equal(taskCalls().length,1); assert.equal(timers.size,0);
"""
    )


def test_failed_read_uses_fixed_error_and_empty_success_does_not_invent_todos() -> None:
    goal_control(
        """
await readyControl(); await showTasks([goalView({state:'failed',task:{...goalView().task,
 observations:[observed({status:'failed',sha256:null,matches:[],error:'timeout'})]}})]);
assert(taskCards.textContent.includes('讀取逾時'));
assert(!taskCards.textContent.includes('已讀取'));
await showTasks([goalView({state:'completed',task:{...goalView().task,
 observations:[observed({matches:[],truncated:true})]}})]);
assert(taskCards.textContent.includes('未找到')); assert(taskCards.textContent.includes('截短'));
assert(taskCards.textContent.includes('待辦尚未執行'));
"""
    )


def test_poll_terminal_observation_stops_timer_without_any_mutation() -> None:
    goal_control(
        """
await readyControl(); await showTasks([goalView({state:'running'})],goalId);
fetchPlan=async () => response(200,taskReply([goalView({state:'completed',next_step:null,
 task:{...goalView().task,observations:[observed()]}})]));
fireTimer(timer=>timer.delay===1000); await flush();
assert.equal(taskCalls().length,2); assert(taskCalls().every(call=>call.options.method==='GET'));
assert.equal(timers.size,0); assert(taskCards.textContent.includes('已讀取'));
"""
    )


def test_token_bootstrap_boundary_cannot_send_retired_mutation() -> None:
    goal_control(
        """
const owner=await readyControl(); await showTasks(); clock=285000;
const pending=delayed(); bootstrapPlan=async () => pending.promise;
const clicked=taskAction('approve').onclick(); await until(()=>calls.length===3);
owner.message({type:'turn_started',turn_id:'foreground-turn'});
pending.resolve(response(200,{token:'synthetic-new',expires_in_seconds:300})); await clicked;
assert.equal(taskCalls().length,1); assert.equal(taskCards.textContent,'');
assert.equal(timers.size,0);
"""
    )


def test_cancel_completed_during_control_race_shows_actual_terminal_readback() -> None:
    goal_control(
        """
await readyControl(); await showTasks([goalView({state:'running',revision:4,
 task:{...goalView().task,approved_at:'2026-10-14T10:00:00+00:00'}})],goalId);
fetchPlan=async () => response(200,{goal:goalView({state:'completed',revision:4,
 task:{...goalView().task,approved_at:'2026-10-14T10:00:00+00:00',observations:[observed()]}})});
await taskAction('cancel').onclick(); assert.equal(taskCalls().length,2);
assert(taskCards.textContent.includes('閱讀完成')); assert(taskAction('remove'));
assert(!taskStatus.textContent.includes('未確認')); assert.equal(timers.size,0);
"""
    )
