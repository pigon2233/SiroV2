from __future__ import annotations

from pathlib import Path

import pytest
from test_frontend_control import run_control
from test_frontend_skill_candidate import REVIEW_FIXTURE

FIXTURE = (
    REVIEW_FIXTURE
    + r"""
const hash = 'siro-skill-package-v1:' + 'a'.repeat(64);
const reviewId = '621f1ee2-8092-4ccb-8794-cf52683e1405';
const activation = (changes = {}) => ({available:true, installed:false, enabled:false,
  package_hash:null,profile:'markdown-checklist-v1',capability:'text.checklist.parse',
  authorizes_execution:false,busy:false,...changes});
const runtime = (changes = {}) => ({...candidateRuntime(),
  skill_activation:activation(),...changes});
const installButton = document.querySelector('#skill-activation-install');
const enableButton = document.querySelector('#skill-activation-enable');
const revokeButton = document.querySelector('#skill-activation-revoke');
const fillButton = document.querySelector('#skill-activation-fill');
const refreshButton = document.querySelector('#skill-activation-refresh');
const activationStatus = document.querySelector('#skill-activation-status');
const activationPosts = () => targetCalls().filter(call =>
  call.url.startsWith('/v1/skills/activation/') && call.options?.method === 'POST');
const offerReview = () => renderSkillCandidateResult(candidateReview({review_id:reviewId}));
"""
)


def control(checks: str) -> None:
    run_control(FIXTURE + checks)


def test_activation_panel_has_separate_explicit_controls_without_direct_executor() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    panel = html.split('id="computer-panel"', 1)[1].split('id="memories-panel"', 1)[0]
    for suffix in ("install", "enable", "revoke", "fill", "refresh", "status"):
        assert f'id="skill-activation-{suffix}"' in panel
    assert "安裝（保持停用）" in panel  # noqa: RUF001
    assert 'id="skill-candidate-approve"' not in html
    assert 'id="skill-candidate-enable"' not in html
    assert "/v1/skills/activation/execute" not in html


def test_review_install_enable_and_revoke_require_individual_human_clicks() -> None:
    control(
        """
renderSkillActivation(runtime()); offerReview();
assert.equal(activationPosts().length, 0);
assert.equal(installButton.disabled, false); assert.equal(enableButton.disabled, true);
assert.equal(fillButton.disabled, true);
fetchPlan = async (url, options) => {
  if (url.endsWith('/install'))
    return response(200, activation({installed:true,package_hash:hash}));
  if (url.endsWith('/enable'))
    return response(200, activation({installed:true,enabled:true,package_hash:hash}));
  if (url.endsWith('/revoke')) return response(200, activation({installed:true,package_hash:hash}));
  throw Error('unexpected auto-request');
};
await installButton.onclick();
assert.deepEqual(JSON.parse(activationPosts()[0].options.body),
  {review_id:reviewId,package_hash:hash});
assert(new Headers(activationPosts()[0].options.headers)
  .get('Authorization').startsWith('Bearer '));
assert.equal(activationPosts().length, 1); assert.equal(installButton.disabled, true);
assert.equal(enableButton.disabled, false); assert.equal(fillButton.disabled, true);
assert(activationStatus.textContent.includes('停用'));
await enableButton.onclick();
assert.deepEqual(JSON.parse(activationPosts()[1].options.body), {package_hash:hash});
assert.equal(fillButton.disabled, false);
await revokeButton.onclick();
assert.deepEqual(JSON.parse(activationPosts()[2].options.body), {package_hash:hash});
assert.equal(fillButton.disabled, true); assert.equal(enableButton.disabled, false);
assert.equal(activationPosts().length, 3);
"""
    )


@pytest.mark.parametrize(
    "view",
    [
        "{}",
        "runtime({runtime_profile:'legacy'})",
        "runtime({kill_switches:{tools:false}})",
        "runtime({skill_activation:activation({available:false})})",
        "runtime({skill_activation:activation({busy:true})})",
        "runtime({skill_activation:activation({authorizes_execution:true})})",
        "runtime({skill_activation:activation({profile:'host'})})",
        "runtime({skill_activation:activation({capability:'computer.execute'})})",
    ],
)
def test_unavailable_or_inconsistent_runtime_cannot_install_or_enable(view: str) -> None:
    control(
        f"""
renderSkillActivation({view}); offerReview();
assert.equal(installButton.disabled, true); assert.equal(enableButton.disabled, true);
await installButton.onclick(); await enableButton.onclick(); await fillButton.onclick();
assert.equal(activationPosts().length, 0);
"""
    )


@pytest.mark.parametrize(
    "change",
    [
        "{review_id:undefined}",
        "{review_id:'forged'}",
        "{review_id:1}",
        "{review_id:reviewId+'x'}",
        "{enabled:true}",
        "{installed:true}",
        "{source:'unknown'}",
        "{status:'verification_failed',verification:{status:'failed_checks',workspace_removed:true}}",
    ],
)
def test_only_passed_server_review_identity_offers_install(change: str) -> None:
    control(
        f"""
renderSkillActivation(runtime());
renderSkillCandidateResult(candidateReview({{review_id:reviewId,...{change}}}));
assert.equal(installButton.disabled, true);
await installButton.onclick(); assert.equal(activationPosts().length, 0);
"""
    )


def test_pending_install_double_click_is_one_request_and_does_not_auto_enable() -> None:
    control(
        """
renderSkillActivation(runtime()); offerReview();
const pending = deferredCandidate(); fetchPlan = async () => pending.promise;
const first = installButton.onclick(), second = installButton.onclick();
await until(() => activationPosts().length === 1);
assert.equal(installButton.disabled, true); assert.equal(enableButton.disabled, true);
pending.resolve(response(200, activation({installed:true,package_hash:hash})));
await Promise.all([first,second]); assert.equal(activationPosts().length, 1);
"""
    )


def test_network_unknown_has_no_retry_and_manual_read_confirms_actual_state() -> None:
    control(
        """
renderSkillActivation(runtime()); offerReview();
fetchPlan = async () => { throw Error('private-network-canary'); };
await installButton.onclick();
assert(activationStatus.textContent.includes('未知'));
assert(!activationStatus.textContent.includes('private'));
await installButton.onclick(); await enableButton.onclick();
assert.equal(activationPosts().length, 1);
fetchPlan = async url => {
  assert.equal(url, '/v1/runtime');
  return response(200,runtime({skill_activation:activation({installed:true,package_hash:hash})}));
};
await refreshButton.onclick();
assert.equal(activationPosts().length, 1);
assert.equal(installButton.disabled, true); assert.equal(enableButton.disabled, false);
"""
    )


def test_tools_off_fences_late_enable_and_still_offers_explicit_revoke() -> None:
    control(
        """
renderSkillActivation(runtime({skill_activation:activation({installed:true,package_hash:hash})}));
const pending = deferredCandidate(); fetchPlan = async () => pending.promise;
const enabling = enableButton.onclick(); await until(() => activationPosts().length === 1);
renderSkillActivation(runtime({kill_switches:{tools:false},skill_activation:activation({installed:true,package_hash:hash})}));
pending.resolve(response(200,activation({installed:true,enabled:true,package_hash:hash})));
await enabling;
assert.equal(fillButton.disabled, true); assert.equal(enableButton.disabled, true);
assert.equal(revokeButton.disabled, false);
fetchPlan = async () => response(200,activation({installed:true,package_hash:hash}));
await revokeButton.onclick(); assert.equal(activationPosts().length, 2);
assert.equal(activationPosts()[1].url, '/v1/skills/activation/revoke');
"""
    )


def test_reconnect_and_metadata_refresh_never_replay_activation_or_execute_chat() -> None:
    control(
        """
const view = runtime({skill_activation:
  activation({installed:true,enabled:true,package_hash:hash})});
renderSnapshot({...snapshot(),...view}); renderSnapshot({...snapshot(),...view});
assert.equal(activationPosts().length, 0);
await fillButton.onclick();
assert(document.querySelector('#text').value.includes('- [ ]'));
assert(document.querySelector('#text').value.includes('待辦'));
assert.equal(targetCalls().length, 0);
"""
    )


def test_unsafe_response_is_plain_fixed_text_and_never_becomes_enabled() -> None:
    control(
        """
Element.prototype.__defineSetter__('innerHTML', () => { throw Error('activation entered HTML'); });
renderSkillActivation(runtime()); offerReview();
fetchPlan = async () => response(200,{
  ...activation({installed:true,enabled:true,package_hash:hash}),
  capability:'<img src=x onerror=evil()>',detail:'private-path-canary'});
await installButton.onclick();
assert.equal(fillButton.disabled, true); assert.equal(enableButton.disabled, true);
assert(activationStatus.textContent.includes('未知'));
assert(!activationStatus.textContent.includes('<img'));
assert(!activationStatus.textContent.includes('private'));
"""
    )


def test_new_preparation_invalidates_prior_install_review_without_replaying_actions() -> None:
    control(
        """
renderSkillCandidateAvailability(candidateRuntime());
renderSkillActivation(runtime()); offerReview();
assert.equal(installButton.disabled,false);
const pending = deferredCandidate(); fetchPlan = async () => pending.promise;
const preparation = prepareButton.onclick();
await until(() => candidatePosts().length === 1);
assert.equal(installButton.disabled,true); await installButton.onclick();
assert.equal(activationPosts().length,0);
pending.resolve(response(200,candidateReview())); await preparation;
assert.equal(installButton.disabled,true);
"""
    )


def test_live_tools_off_event_disables_skill_and_tools_on_requires_explicit_enable() -> None:
    control(
        """
const connecting = connectControl(); await until(() => sockets.length === 1);
const owner = sockets[0]; owner.open();
owner.message({...snapshot(),...runtime({skill_activation:
  activation({installed:true,enabled:true,package_hash:hash})})});
await connecting; assert.equal(fillButton.disabled,false);
owner.message({type:'kill_switch',name:'tools',enabled:false});
assert.equal(fillButton.disabled,true); assert.equal(enableButton.disabled,true);
assert.equal(revokeButton.disabled,false);
owner.message({type:'kill_switch',name:'tools',enabled:true});
assert.equal(fillButton.disabled,true); assert.equal(enableButton.disabled,false);
assert.equal(activationPosts().length,0);
"""
    )
