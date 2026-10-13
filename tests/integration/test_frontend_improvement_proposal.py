from __future__ import annotations

from pathlib import Path

import pytest
from test_frontend_control import run_control

FIXTURE = r"""
const sourceRun = '00000000-0000-0000-0000-000000000001';
const otherRun = '00000000-0000-0000-0000-000000000002';
const proposalUrl = '/v1/conversations/browser/improvement-proposal';
const investigation = (changes = {}) => ({
  schema_version:1, source_task:'RI-006', proposal_id:`RI-006:${sourceRun}:http-status-v1`,
  classification:'DEFER', root_cause:'UNKNOWN — NEEDS INVESTIGATION',
  patch:null, approval_required:true, authorizes_execution:false,
  evidence:{source_run_id:sourceRun,state:'failed',error_class:'HTTPStatusError',
    tool_dispatch_recorded:false,root_cause:'UNKNOWN'},
  problem:'Synthetic service response failure needs investigation.',
  expected_behavior:'Investigate the recorded failure before proposing a repair.',
  actual_behavior:'Only the HTTPStatusError class is recorded.',
  scope:'Review this synthetic source without replaying an operation.',
  proposed_repair:'Find the smallest verified defect first.',
  files_expected_to_change:[], files_must_not_change:['src/siro/core/authorization.py'],
  compatibility_requirements:'Preserve recorded results and permissions.',
  tests_required:['Verify the actual recorded failure.'],
  regression_tests:['Preserve the original authorization checks.'],
  acceptance_criteria:['Root cause established with reproducible evidence.'],
  rollback_method:'Remove this read-only view; preserve recorded data.',
  risk:'Unknown until investigation.', ...changes
});
const proposalReply = (changes = {}) => ({
  status:'awaiting_investigation',proposal:investigation(changes)
});
const delayed = () => {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
};
const proposalButton = document.querySelector('#improvement-proposal-refresh');
const proposalStatus = document.querySelector('#improvement-proposal-status');
const proposalDetails = document.querySelector('#improvement-proposal-review');
const proposalCalls = () => targetCalls().filter(call => call.url === proposalUrl);
assert(proposalButton && proposalStatus && proposalDetails, 'Missing improvement proposal panel');
const displayedSource = () => proposalDetails.textContent.includes(sourceRun);
const quietFetch = (url, options) => {
  if (url === '/v1/runtime') return response(200,{tools:[],features:{},routes:{}});
  if (url === '/v1/memory-organization') return response(200,{state:'unavailable',groups:[]});
  if (url === '/v1/memories?limit=100') return response(200,{items:[]});
  return response(200,{turn_id:'synthetic-new-turn'});
};
"""


def proposal_control(checks: str) -> None:
    run_control(FIXTURE + checks)


def test_panel_has_one_manual_read_only_action_inside_computer_help() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    computer = html.split('id="computer-panel"', 1)[1].split('id="memories-panel"', 1)[0]
    panel = computer.split('id="improvement-proposal-panel"', 1)[1].split("</section>", 1)[0]
    assert "改善建議" in panel
    assert "查看這段對話的改善建議" in panel
    assert 'id="improvement-proposal-refresh"' in panel
    assert panel.count("<button") == 1
    assert 'type="button"' in panel
    assert 'id="improvement-proposal-review"' in panel


def test_connect_and_other_refreshes_never_automatically_query_proposal() -> None:
    proposal_control(
        """
fetchPlan = quietFetch;
await readyControl(); await refreshProduct(); await refreshCapabilities(); await flush();
assert.equal(proposalCalls().length,0);
assert.equal(proposalDetails.textContent,'');
assert.equal(proposalButton.disabled,false);
assert.equal(timers.size,0,'Read-only proposal must not add polling');
"""
    )


def test_programmatic_click_without_authenticated_control_cannot_fetch() -> None:
    proposal_control(
        """
await proposalButton.onclick(); await flush();
assert.equal(proposalCalls().length,0); assert.equal(calls.length,0);
assert.equal(proposalDetails.textContent,'');
"""
    )


def test_manual_click_gets_one_authenticated_snapshot_and_no_other_action() -> None:
    proposal_control(
        """
const owner = await readyControl();
fetchPlan = async () => response(200,proposalReply());
await proposalButton.onclick();
assert.equal(targetCalls().length,1); assert.equal(proposalCalls().length,1);
const sent = proposalCalls()[0];
assert.equal(sent.options.method,'GET'); assert.equal(sent.options.cache,'no-store');
assert.equal(sent.options.body,undefined);
assert(new Headers(sent.options.headers).get('Authorization').startsWith('Bearer '));
assert.equal(sent.options.signal.aborted,false);
assert.equal(owner.sent.length,1,'Viewing a proposal must not send control/model messages');
assert.equal(timers.size,0);
assert(displayedSource());
assert(proposalDetails.textContent.includes(investigation().problem));
assert(proposalDetails.textContent.includes(investigation().expected_behavior));
assert(proposalDetails.textContent.includes(investigation().files_must_not_change[0]));
assert(proposalStatus.textContent.includes('調查'));
assert(proposalStatus.textContent.includes('快照'));
assert(proposalStatus.textContent.includes('重新'));
"""
    )


def test_exact_empty_reply_removes_prior_proposal_without_inventing_repair() -> None:
    proposal_control(
        """
await readyControl(); fetchPlan = async () => response(200,proposalReply());
await proposalButton.onclick(); assert(displayedSource());
fetchPlan = async () => response(200,{status:'no_supported_evidence',proposal:null});
await proposalButton.onclick();
assert.equal(proposalDetails.textContent,'');
assert(proposalStatus.textContent.includes('沒有'));
assert(proposalStatus.textContent.includes('快照'));
assert.equal(proposalCalls().length,2);
"""
    )


@pytest.mark.parametrize(
    "body",
    [
        "null",
        "[]",
        "{}",
        "{status:'awaiting_investigation',proposal:null}",
        "{status:'no_supported_evidence',proposal:investigation()}",
        "{status:'no_supported_evidence',proposal:null,raw_error:'private-canary'}",
        "{...proposalReply(),status:'approved'}",
        "{...proposalReply(),raw_error:'private-canary'}",
        "proposalReply({source_task:'RT-015'})",
        "proposalReply({classification:'REQUIRED_FIX'})",
        "proposalReply({approval_required:false})",
        "proposalReply({approval_required:1})",
        "proposalReply({authorizes_execution:true})",
        "proposalReply({authorizes_execution:0})",
        "proposalReply({patch:{diff:'private-canary'}})",
        "proposalReply({root_cause:'verified: private-canary'})",
        "proposalReply({proposal_id:`RI-006:${otherRun}:http-status-v1`})",
        "proposalReply({proposal_id:`RI-006:${sourceRun}:arbitrary-patch`})",
        "proposalReply({evidence:{...investigation().evidence,source_run_id:sourceRun.toUpperCase()+'X'}})",
        "proposalReply({evidence:{...investigation().evidence,state:'completed'}})",
        "proposalReply({evidence:{...investigation().evidence,error_class:'HTTPStatusError:private-canary'}})",
        "proposalReply({evidence:{...investigation().evidence,tool_dispatch_recorded:1}})",
        "proposalReply({evidence:{...investigation().evidence,root_cause:'known'}})",
        "proposalReply({evidence:{...investigation().evidence,goal:'private-canary'}})",
        "proposalReply({problem:null})",
        "proposalReply({actual_behavior:' '})",
        "proposalReply({scope:'x'.repeat(4097)})",
        "proposalReply({files_expected_to_change:['src/siro/core/authorization.py']})",
        "proposalReply({files_must_not_change:'private-canary'})",
        "proposalReply({tests_required:[null]})",
        "proposalReply({regression_tests:['']})",
        "proposalReply({acceptance_criteria:'private-canary'})",
        "proposalReply({raw_error:'private-canary'})",
    ],
)
def test_malformed_or_authorizing_reply_is_rejected_without_raw_echo(body: str) -> None:
    proposal_control(
        f"""
await readyControl(); fetchPlan = async () => response(200,{body});
await proposalButton.onclick();
assert.equal(proposalDetails.textContent,'');
assert(!proposalStatus.textContent.includes('private-canary'));
assert(!proposalDetails.textContent.includes('private-canary'));
assert.equal(proposalCalls().length,1);
assert.equal(targetCalls().length,1);
"""
    )


def test_valid_fixed_fields_are_plain_text_without_html_export_or_approval() -> None:
    proposal_control(
        """
Element.prototype.__defineSetter__('innerHTML', () => { throw Error('proposal entered HTML'); });
URL.createObjectURL = () => { throw Error('proposal must not export'); };
const malicious = '<img src=x onerror=syntheticEvil()>';
await readyControl();
fetchPlan = async () => response(200,proposalReply({problem:malicious,
  evidence:{...investigation().evidence,tool_dispatch_recorded:true}}));
await proposalButton.onclick();
assert(proposalDetails.textContent.includes(malicious));
assert.equal(proposalDetails.children.length,0);
assert.equal(targetCalls().length,1);
"""
    )


@pytest.mark.parametrize("status", [400, 401, 403, 503, 500])
def test_error_status_does_not_echo_error_detail_or_replay(status: int) -> None:
    proposal_control(
        f"""
await readyControl();
fetchPlan = async () => response({status},{{detail:'private-canary <img src=x>'}});
await proposalButton.onclick();
assert.equal(proposalDetails.textContent,'');
assert(!proposalStatus.textContent.includes('private-canary'));
assert(!proposalStatus.textContent.includes('<img'));
assert.equal(targetCalls().length,1);
"""
    )


def test_network_failure_has_fixed_status_without_private_error_or_retry() -> None:
    proposal_control(
        """
await readyControl(); fetchPlan = async () => { throw Error('private-canary'); };
await proposalButton.onclick();
assert.equal(proposalDetails.textContent,'');
assert(!proposalStatus.textContent.includes('private-canary'));
assert.equal(proposalCalls().length,1);
"""
    )


def test_manual_refresh_aborts_previous_request_and_rejects_late_success() -> None:
    proposal_control(
        """
await readyControl();
const old = delayed(), current = delayed();
fetchPlan = async () => proposalCalls().length === 1 ? old.promise : current.promise;
const first = proposalButton.onclick(); await until(() => proposalCalls().length === 1);
const firstSignal = proposalCalls()[0].options.signal;
const second = proposalButton.onclick(); await until(() => proposalCalls().length === 2);
assert.equal(firstSignal.aborted,true);
current.resolve(response(200,proposalReply({proposal_id:`RI-006:${otherRun}:http-status-v1`,
  evidence:{...investigation().evidence,source_run_id:otherRun}}))); await second;
assert(proposalDetails.textContent.includes(otherRun));
old.resolve(response(200,proposalReply())); await first;
assert(!displayedSource()); assert(proposalDetails.textContent.includes(otherRun));
assert.equal(proposalCalls()[1].options.signal.aborted,false);
"""
    )


def test_refresh_fences_late_json_body_as_well_as_late_http_response() -> None:
    proposal_control(
        """
await readyControl();
const body = delayed(); let reading = false;
fetchPlan = async () => ({status:200,ok:true,json:() => { reading=true; return body.promise; }});
const first = proposalButton.onclick(); await until(() => reading);
const signal = proposalCalls()[0].options.signal;
fetchPlan = async () => response(200,{status:'no_supported_evidence',proposal:null});
await proposalButton.onclick(); assert.equal(signal.aborted,true);
const status = proposalStatus.textContent;
body.resolve(proposalReply()); await first;
assert.equal(proposalDetails.textContent,''); assert.equal(proposalStatus.textContent,status);
"""
    )


@pytest.mark.parametrize(
    "activity",
    [
        "owner.message({type:'turn_started',turn_id:'synthetic-new-turn'});",
        "owner.message({type:'assistant_started',session_id:'browser'});",
        "await submitText('synthetic new conversation input');",
        "await refreshProduct();",
        "await refreshCapabilities();",
        "document.querySelector('#connection').onclick(); await flush();",
        "owner.disconnect(); await flush();",
        "dispatchWindow('beforeunload'); await flush();",
    ],
)
@pytest.mark.parametrize("reject", [False, True])
def test_activity_aborts_request_and_late_result_cannot_revive_card(
    activity: str, reject: bool
) -> None:
    completion = (
        "pending.reject(Error('private-canary'));"
        if reject
        else "pending.resolve(response(200,proposalReply()));"
    )
    proposal_control(
        f"""
const owner = await readyControl(), pending = delayed();
fetchPlan = async (url,options) => url === proposalUrl ? pending.promise : quietFetch(url,options);
const viewing = proposalButton.onclick(); await until(() => proposalCalls().length === 1);
const signal = proposalCalls()[0].options.signal;
{activity}
assert.equal(signal.aborted,true);
const status = proposalStatus.textContent;
{completion} await viewing;
assert.equal(proposalDetails.textContent,''); assert.equal(proposalStatus.textContent,status);
assert(!proposalStatus.textContent.includes('private-canary'));
assert.equal(proposalCalls().length,1);
"""
    )


@pytest.mark.parametrize(
    "activity",
    [
        "owner.message({type:'turn_started',turn_id:'synthetic-new-turn'});",
        "owner.message({type:'assistant_started',session_id:'browser'});",
        "await submitText('synthetic new input');",
        "await refreshProduct();",
        "owner.disconnect(); await flush();",
        "dispatchWindow('beforeunload'); await flush();",
    ],
)
def test_activity_clears_already_rendered_snapshot(activity: str) -> None:
    proposal_control(
        f"""
const owner = await readyControl();
fetchPlan = async (url,options) => url === proposalUrl
  ? response(200,proposalReply()) : quietFetch(url,options);
await proposalButton.onclick(); assert(displayedSource());
{activity}
assert.equal(proposalDetails.textContent,''); assert.equal(proposalCalls().length,1);
"""
    )


def test_stale_old_socket_cannot_clear_new_owner_snapshot_or_replay_query() -> None:
    proposal_control(
        """
const first = await readyControl(), stale = first.onmessage;
fetchPlan = async () => response(200,proposalReply()); await proposalButton.onclick();
first.disconnect(); await readyControl();
fetchPlan = async () => response(200,proposalReply({proposal_id:`RI-006:${otherRun}:http-status-v1`,
  evidence:{...investigation().evidence,source_run_id:otherRun}}));
await proposalButton.onclick();
stale({data:JSON.stringify({type:'turn_started',turn_id:'stale-turn'})});
assert(proposalDetails.textContent.includes(otherRun)); assert.equal(proposalCalls().length,2);
"""
    )


def test_unloaded_page_cannot_query_again_even_with_programmatic_click() -> None:
    proposal_control(
        """
await readyControl(); dispatchWindow('beforeunload');
await proposalButton.onclick(); await flush();
assert.equal(proposalCalls().length,0); assert.equal(proposalDetails.textContent,'');
assert.equal(proposalButton.disabled,true);
"""
    )
