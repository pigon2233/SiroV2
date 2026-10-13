from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from test_frontend_control import run_control
from test_isolated_patch_verification import real_profile

from siro.core.evolution import PatchProposal, VerificationReport
from siro.services.tools import skill_candidates
from siro.services.tools.orchestrator import ToolCatalog

REVIEW_FIXTURE = r"""
const deferredCandidate = () => {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
};
const candidateRuntime = (changes = {}) => ({
  runtime_profile:'candidate', kill_switches:{tools:true},
  skill_candidates:{available:true,busy:false,profile:'markdown-checklist-v1',
    authorizes_execution:false}, ...changes
});
const candidateReview = (changes = {}) => ({
  status:'awaiting_review', enabled:false, installed:false, authorizes_execution:false,
  approval_required:true, trust_level:'unreviewed',
  source:'siro_builtin_template:markdown-checklist-v1',
  package_hash:'siro-skill-package-v1:' + 'a'.repeat(64), tests_sha256:'b'.repeat(64),
  files:{'manifest.json':'{"network":"denied"}', 'input.json':'{"type":"object"}',
    'output.json':'{"type":"object"}', 'plugin.py':'# synthetic source'},
  verification:{status:'passed',workspace_removed:true,outputs:['Ran 12 tests; OK']},
  ...changes
});
const prepareButton = document.querySelector('#skill-candidate-prepare');
const cancelButton = document.querySelector('#skill-candidate-cancel');
const exportButton = document.querySelector('#skill-candidate-export');
const candidateStatus = document.querySelector('#skill-candidate-status');
const candidateDetails = document.querySelector('#skill-candidate-review');
const candidateFiles = document.querySelector('#skill-candidate-files');
const candidatePosts = () => targetCalls().filter(call => call.options?.method === 'POST');
"""


def candidate_control(checks: str) -> None:
    run_control(REVIEW_FIXTURE + checks)


def test_candidate_panel_is_inside_computer_help_without_activation_control() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    panel = html.split('id="computer-panel"', 1)[1].split('id="memories-panel"', 1)[0]
    assert "學習新能力" in panel
    assert "解析貼上的 Markdown 待辦清單" in panel
    assert 'id="skill-candidate-prepare"' in panel
    assert 'id="skill-candidate-cancel"' in panel
    assert 'id="skill-candidate-export"' in panel
    assert 'id="skill-candidate-approve"' not in html
    assert 'id="skill-candidate-enable"' not in html


@pytest.mark.parametrize(
    "runtime",
    [
        "{}",
        "candidateRuntime({runtime_profile:'legacy'})",
        "candidateRuntime({kill_switches:{tools:false}})",
        "candidateRuntime({skill_candidates:{available:false,busy:false,authorizes_execution:false}})",
        "candidateRuntime({skill_candidates:{available:true,busy:true,authorizes_execution:false}})",
        "candidateRuntime({skill_candidates:{available:true,busy:false,authorizes_execution:true}})",
    ],
)
def test_unavailable_candidates_cannot_post_even_with_programmatic_click(runtime: str) -> None:
    candidate_control(
        f"""
renderSkillCandidateAvailability({runtime});
assert.equal(prepareButton.disabled, true);
await prepareButton.onclick();
assert.equal(candidatePosts().length, 0);
assert.equal(exportButton.disabled, true);
"""
    )


def test_owner_click_posts_fixed_request_once_and_shows_uninstalled_review() -> None:
    candidate_control(
        """
renderSkillCandidateAvailability(candidateRuntime());
const pending = deferredCandidate();
fetchPlan = async (url, options) => pending.promise;
const first = prepareButton.onclick(), second = prepareButton.onclick();
await until(() => candidatePosts().length === 1);
assert.equal(prepareButton.disabled, true); assert.equal(cancelButton.disabled, false);
const sent = candidatePosts()[0];
assert.equal(sent.url, '/v1/skills/candidates');
assert.deepEqual(JSON.parse(sent.options.body), {capability:'text.checklist.parse'});
assert(new Headers(sent.options.headers).get('Authorization').startsWith('Bearer '));
pending.resolve(response(200, candidateReview())); await Promise.all([first,second]);
assert.equal(candidatePosts().length, 1);
assert(candidateStatus.textContent.includes('尚未安裝'));
assert(candidateStatus.textContent.includes('啟用'));
assert(candidateDetails.textContent.includes('不等於人工審查'));
assert(candidateDetails.textContent.includes('siro_builtin_template:markdown-checklist-v1'));
assert(candidateFiles.textContent.includes('# synthetic source'));
assert.equal(exportButton.disabled, false);
"""
    )


def test_review_html_is_plain_text_and_export_requires_owner_click() -> None:
    candidate_control(
        """
Element.prototype.__defineSetter__('innerHTML', () => { throw Error('candidate entered HTML'); });
const links = [], blobs = []; let downloaded;
const create = document.createElement;
document.createElement = tag => {
  const node = create(tag);
  if (tag === 'a') { node.click = () => { downloaded = node.download; }; links.push(node); }
  return node;
};
URL.createObjectURL = blob => { blobs.push(blob); return 'blob:synthetic-review'; };
URL.revokeObjectURL = url => { assert.equal(url, 'blob:synthetic-review'); };
const malicious = '<img src=x onerror=evil()>';
fetchPlan = async () => response(200, candidateReview({
  files:{...candidateReview().files,'plugin.py':malicious},
  verification:{status:'passed',workspace_removed:true,outputs:[malicious]}
}));
renderSkillCandidateAvailability(candidateRuntime()); await prepareButton.onclick();
assert(candidateFiles.textContent.includes(malicious));
assert(candidateDetails.textContent.includes(malicious));
assert.equal(blobs.length, 0); assert.equal(downloaded, undefined);
await exportButton.onclick();
assert.equal(blobs.length, 1); assert(downloaded.endsWith('.json'));
const payload = JSON.parse(await blobs[0].text());
assert.equal(payload.status, 'awaiting_review');
assert.equal(payload.verification.status, 'passed');
assert.equal(payload.enabled, false); assert.equal(payload.installed, false);
assert.equal(payload.authorizes_execution, false); assert.equal(payload.approval_required, true);
assert.equal(payload.files['plugin.py'], malicious);
"""
    )


@pytest.mark.parametrize(
    "change",
    [
        "{enabled:true}",
        "{installed:true}",
        "{authorizes_execution:true}",
        "{approval_required:false}",
        "{trust_level:'approved'}",
        "{source:'unknown'}",
        "{package_hash:'forged'}",
        "{tests_sha256:'forged'}",
        "{verification:{status:'failed_checks',workspace_removed:true}}",
        "{verification:{status:'passed',workspace_removed:false}}",
        "{files:{...candidateReview().files,'extra.py':'unexpected'}}",
    ],
)
def test_inconsistent_or_untrusted_review_cannot_be_exported(change: str) -> None:
    candidate_control(
        f"""
renderSkillCandidateAvailability(candidateRuntime());
fetchPlan = async () => response(200, candidateReview({change}));
await prepareButton.onclick();
assert.equal(exportButton.disabled, true);
assert(candidateStatus.textContent.includes('無法確認'));
let exports = 0; URL.createObjectURL = () => {{ exports++; return 'blob:forbidden'; }};
await exportButton.onclick(); assert.equal(exports, 0);
assert(!candidateStatus.textContent.includes('可啟用'));
"""
    )


@pytest.mark.parametrize(
    "status",
    ["existing_available", "existing_unavailable", "existing_unknown", "unsupported_capability"],
)
def test_existing_or_unsupported_result_does_not_offer_export(status: str) -> None:
    candidate_control(
        f"""
renderSkillCandidateAvailability(candidateRuntime());
fetchPlan = async () => response(200, {{status:'{status}', enabled:false,
  installed:false,authorizes_execution:false,approval_required:true}});
await prepareButton.onclick();
assert.equal(exportButton.disabled, true); assert.equal(candidateFiles.textContent, '');
assert.equal(candidatePosts().length, 1); assert.equal(prepareButton.disabled, false);
assert(!candidateStatus.textContent.includes('可啟用'));
"""
    )


def test_failed_verification_export_preserves_failure_and_has_no_approval_claim() -> None:
    candidate_control(
        """
renderSkillCandidateAvailability(candidateRuntime());
fetchPlan = async () => response(200, candidateReview({status:'verification_failed',
  verification:{status:'failed_checks',workspace_removed:true,outputs:['synthetic failed test']}}));
await prepareButton.onclick();
assert(candidateStatus.textContent.includes('驗證未通過'));
assert(!candidateStatus.textContent.includes('可啟用'));
assert.equal(exportButton.disabled, false);
"""
    )


def test_cancel_fences_late_review_and_repeated_click_without_queue_or_replay() -> None:
    candidate_control(
        """
renderSkillCandidateAvailability(candidateRuntime());
const pending = deferredCandidate(), stopped = deferredCandidate();
fetchPlan = async url => url.endsWith('/cancel') ? stopped.promise : pending.promise;
const first = prepareButton.onclick(); await until(() => candidatePosts().length === 1);
const cancelling = cancelButton.onclick(), duplicate = cancelButton.onclick();
await until(() => candidatePosts().length === 2);
renderSkillCandidateAvailability(candidateRuntime());
await prepareButton.onclick(); assert.equal(candidatePosts().length, 2);
stopped.resolve(response(200, {cancelled:true})); await Promise.all([cancelling,duplicate]);
pending.resolve(response(200, candidateReview())); await first;
assert(candidateStatus.textContent.includes('已取消'));
assert.equal(candidateFiles.textContent, ''); assert.equal(exportButton.disabled, true);
assert.equal(candidatePosts().length, 2);
"""
    )


def test_network_unknown_and_failed_cancel_keep_busy_until_manual_acknowledgement() -> None:
    candidate_control(
        """
renderSkillCandidateAvailability(candidateRuntime());
fetchPlan = async () => { throw Error('synthetic-private-error'); };
await prepareButton.onclick();
assert(candidateStatus.textContent.includes('結果未知'));
assert(!candidateStatus.textContent.includes('synthetic-private-error'));
assert.equal(prepareButton.disabled, true); assert.equal(cancelButton.disabled, false);
renderSkillCandidateAvailability(candidateRuntime()); await prepareButton.onclick();
assert.equal(candidatePosts().length, 1);
await cancelButton.onclick();
assert.equal(prepareButton.disabled, true); assert.equal(cancelButton.disabled, false);
assert(candidateStatus.textContent.includes('無法確認取消'));
renderSkillCandidateAvailability(candidateRuntime()); await prepareButton.onclick();
assert.equal(candidatePosts().length, 2);
fetchPlan = async () => response(200, {cancelled:false});
await cancelButton.onclick(); assert.equal(prepareButton.disabled, false);
assert.equal(candidatePosts().length, 3);
"""
    )


def test_control_snapshots_and_reconnect_do_not_prepare_a_candidate() -> None:
    candidate_control(
        """
const first = await readyControl();
first.message({...snapshot(), ...candidateRuntime()}); await flush();
assert.equal(prepareButton.disabled, false);
first.disconnect(); await flush();
const second = await readyControl();
second.message({...snapshot(), ...candidateRuntime()}); await flush();
assert.equal(candidatePosts().length, 0);
"""
    )


def test_verified_expired_token_retries_only_pre_accept_rejection_with_same_body() -> None:
    candidate_control(
        """
renderSkillCandidateAvailability(candidateRuntime());
let requests = 0;
fetchPlan = async () => ++requests === 1
  ? response(401, {detail:'session token is invalid or expired'})
  : response(200, candidateReview());
await prepareButton.onclick();
assert.equal(candidatePosts().length, 2); assert.equal(nextToken, 2);
assert.equal(candidatePosts()[0].options.body, candidatePosts()[1].options.body);
assert.equal(exportButton.disabled, false);
"""
    )


def test_unverified_auth_error_has_no_automatic_retry() -> None:
    candidate_control(
        """
renderSkillCandidateAvailability(candidateRuntime());
fetchPlan = async () => response(401, {detail:'unknown rejection'});
await prepareButton.onclick();
assert.equal(candidatePosts().length, 1); assert.equal(nextToken, 1);
assert.equal(prepareButton.disabled, true);
assert(candidateStatus.textContent.includes('結果未知'));
"""
    )


def test_malformed_successful_cancel_cannot_clear_unknown_owner_state() -> None:
    candidate_control(
        """
renderSkillCandidateAvailability(candidateRuntime());
fetchPlan = async () => { throw Error('unknown outcome'); };
await prepareButton.onclick();
fetchPlan = async () => response(200, {cancelled:'yes'});
await cancelButton.onclick();
assert.equal(prepareButton.disabled, true); assert.equal(cancelButton.disabled, false);
assert(candidateStatus.textContent.includes('無法確認取消'));
renderSkillCandidateAvailability(candidateRuntime()); await prepareButton.onclick();
assert.equal(candidatePosts().length, 2);
"""
    )


def assert_service_payload_review(
    payload: dict[str, object], *, status: str, verification: str, visible: str
) -> None:
    candidate_control(
        "const actualPayload = "
        + json.dumps(payload, ensure_ascii=False)
        + f""";
renderSkillCandidateAvailability(candidateRuntime());
fetchPlan = async () => response(200, actualPayload);
const blobs = []; let downloads = 0;
const create = document.createElement;
document.createElement = tag => {{
  const node = create(tag); if (tag === 'a') node.click = () => downloads++; return node;
}};
URL.createObjectURL = blob => {{ blobs.push(blob); return 'blob:actual-service-review'; }};
URL.revokeObjectURL = url => assert.equal(url, 'blob:actual-service-review');
await prepareButton.onclick();
assert(candidateStatus.textContent.includes({json.dumps(visible)}));
assert(candidateStatus.textContent.includes('尚未安裝或啟用'));
assert(!candidateStatus.textContent.includes('可啟用'));
assert(candidateDetails.textContent.includes('不等於人工審查'));
assert(candidateDetails.textContent.includes({json.dumps(verification)}));
assert(candidateFiles.textContent.includes(actualPayload.files['plugin.py']));
assert.equal(exportButton.disabled, false); assert.equal(downloads, 0);
await exportButton.onclick();
assert.equal(downloads, 1); assert.equal(blobs.length, 1);
const exported = JSON.parse(await blobs[0].text());
assert.deepEqual(exported, actualPayload);
assert.equal(exported.status, {json.dumps(status)});
assert.equal(exported.verification.status, {json.dumps(verification)});
assert.equal(exported.enabled, false); assert.equal(exported.installed, false);
assert.equal(exported.authorizes_execution, false); assert.equal(exported.approval_required, true);
assert.equal(exported.trust_level, 'unreviewed');
assert.equal(candidatePosts().length, 1);
"""
    )


@pytest.mark.asyncio
@real_profile
async def test_actual_service_pass_payload_renders_and_exports_unreviewed_evidence() -> None:
    service = skill_candidates.SkillCandidatePreparer(ToolCatalog(()))
    try:
        payload = await service.prepare("text.checklist.parse")
        assert payload["status"] == "awaiting_review", payload
        assert_service_payload_review(
            payload,
            status="awaiting_review",
            verification="passed",
            visible="待你審查",
        )
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_actual_service_binding_mismatch_payload_renders_failed_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def wrong_id(root: Path, proposal: PatchProposal) -> VerificationReport:
        return VerificationReport(uuid4(), "passed", ("src/plugin.py",), (), True)

    monkeypatch.setattr(skill_candidates, "verify_isolated_patch", wrong_id)
    service = skill_candidates.SkillCandidatePreparer(ToolCatalog(()))
    try:
        payload = await service.prepare("text.checklist.parse")
        assert payload["status"] == "verification_failed", payload
        assert_service_payload_review(
            payload,
            status="verification_failed",
            verification="binding_mismatch",
            visible="驗證未通過",
        )
    finally:
        await service.close()
