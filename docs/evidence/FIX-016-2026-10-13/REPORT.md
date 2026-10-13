# FIX-016 — clean CI bootstrap / exact public-pin review

Status: IN_PROGRESS until full local check and exact-head GitHub Actions are complete. Scope is build tooling only; production source and existing tests are byte-identical.

## Problem and confirmed root cause

[Before Actions](https://github.com/pigon2233/SiroV2/actions/runs/38356354040) is a push run at d1f5d07; repository has no pull requests (pull-request-state.json). The minimal Rust1.97.1 manifest did not declare cargo-fmt/clippy despite scripts/check requiring them. Cold isolated official installation independently reproduced both missing components, then manifest-only addition automatically installed both. toolchain-probe.json records success and temporary-root cleanup.

The unchanged secret scan returned six Hex High Entropy String findings in the public GPT-OSS profile; the old all-findings failure gate rejected them. Official pinned revision downloads matched all five file hashes; scan-public-primary-pins.json and scan-public-fingerprint-binding.json bind every finding. This is a broken integration gate (REQUIRED_FIX/MEDIUM / MISSING_INTEGRATION, INCOMPLETE_TASK, TEST_GAP) with six verified FALSE_POSITIVE values, not a newly proven runtime architecture defect.

## Minimal correction / compatibility

rust-toolchain.toml declares rustfmt/clippy, and scripts/check replaces its report-evaluation block with scripts/check_secrets.py. The next actual remote run38388506116 at f253dec passed fmt/build but exposed three cfg(test) fixture literals requiring nonexistent /usr/bin/python3.14. Only those three literals now use portable /usr/bin/python3; all process/shell/timeout/ownership assertions and bytes before cfg(test) remain exact. Original fmt/build/test/clippy/Ruff/mypy/pytest/schema/detect-secrets commands, scanner exclusions and order remain. No production code, prior assertions, workflow, Python/Rust version or lockfile changes; the only prior-test change is the confirmed three executable literals. Helper acknowledges only exact audited profile blob/path/type/line/fingerprint and is_verified=False; changed bytes, new/other findings, malformed/bad binding or duplicate JSON fails. Explicit per-line annotation covers only public hash constants in helper; no whole-file/plugin exemption.

New tests use actual detect-secrets reports plus deterministic never-valid synthetic credentials. Before helper implementation24FAIL (missing new helper); old gate independently exit1 on the actual six findings. Final focused24PASS/1.48s on CPython3.14.4. Before-case failure is not evidence of24 historical runtime bugs. Focused Ruff format/lint/type plus scoped source/docs whitespace PASS; repair-source-secrets.json has zero findings. Independent final read-only four-file review plus independent cfg(test) refinement review found no actionable issue; cold probe and final source binding recorded separately.

## Complete verification

Pending final local scripts/check outcome. Pending exact-head remote Actions outcome. Five real_provider tests are opt-in and cannot be counted as passed. No real model/voice/user UI/hardware/deployment acceptance is claimed by this card.

Initial full pipeline was interrupted by the reviewer execution limit; owned children were subsequently stopped/joined. A second run exposed a harness defect: UV_NO_CONFIG caused temp .venv to select CPython3.12.14 while repository .python-version requests3.14. Standalone broker test in that wrong-version environment timed out; root cause UNKNOWN — NEEDS INVESTIGATION. That run was stopped/joined, retained as INVALID_HARNESS, not claimed as CI/runtime verification. Root removed only owned temp .venv and used empty owned XDG_CONFIG_HOME while respecting the existing project version request; corrected run selects actual local3.14.4. Remote runner's real version is verified independently. No product or test timeout threshold was changed to hide the failure.

The first corrected-version full suite reported1697PASS/5opt-inSKIP/3warnings but an overly long harness TMPDIR caused three earlier socket failures; short owned scratch proved those3PASS/0.09s. This was another harness defect, not a production patch. A mistakenly overlapping rerun was stopped/joined; its shared log overwrite is recorded and cannot certify final source. Only the current sequential five-file full pass is authoritative. All Rust fmt/build/6tests/clippy pass after the cfg(test) refinement.

## Supported CI / independent owner-import follow-up

Actual2324b35 cloud run38389536976 progressed through all Rust/static checks, then54FAIL/1541PASS/107SKIP/7warnings:52 unsupported native-sandbox failures, one eager ONNXimport owner violation and one old-SQLite fixture assumption. Do not certify this as success. OfficialUbuntu26.04 x64/native3.14 plus signed-apt bwrap/seccomp/AppArmor and realnamespace preflight now supply the unchanged supported profile; no global-defense disable/root tests/skip/fallback. Existing workflow3.12 extra-install is left as documented debt.

Quoted numeric-key fixture has been made portable without SQL changes: real old3.46.1 vs official-source-verified3.50.4 extraction isNULL vs exact numericstring, and original policyguard holds in both. Only rename/intermediate assertion changes; wrongbindingPENDING/effects0/fullDBdumpunchanged remain. Full44cases PASS in each version, Ruff/type PASS. New official source proof/cleanup recorded in scan-sqlite-* evidence.

Separate FIX-017/D54 owns one confirmed production leaf correction: eager optional Kokoro SDK import delayed to existing owned offloop render. Its5RED→5PASS,34focusedPASS/exact2rollback are in ../FIX-017-2026-10-13/REPORT.md. FIX-016 remains build/test only; combined nine-file final full local and supported exact-head remote are PENDING. Oldsource-only five-file proof is historical and cannot certify the latest combined runtime scope.

## Preservation / rollback / cleanup

303 existing source/test/build/pin/lock/Rust files captured before changes;300 unchanged, two existing build files plus only the three Rust unit-fixture literals changed, two new helper/test files. All production and old test assertions retained. preservation-and-rollback.json verifies exact five-file source-only reverse/reapply in disposable directory, including executable check mode; data/Git history untouched. A rollback would reopen CI FAILED_VERIFICATION, not restore passing status. Temporary archive contains only public git source and generated public tokenizer/runtime binaries; no private main workspace scan.

## Architecture / roadmap / remaining risks

Overall architecture YELLOW unchanged. No new runtime responsibility/dependency/global-state/interface leakage; build-only local repair. Fresh-bootstrap regression blind spot now covered by true isolated tooling and complete CI. CI build zone stays YELLOW until local+remote final acceptance; test/evidence GREEN, liveDB/migration/permission/release RED. RI-005/RI-006 subsequent implementation BLOCKED_BY_FIX: FIX-016 until exact-head green. Original numbered RT DONE history, RI-005 PARTIAL adoption/handoff and FIX-002/005/006 product limitations remain.

Python3.12 pre-install versus actual pin is TECH_DEBT, not this remote failure's cause; keep existing pin/workflow. Unverified general3.12 broker support is TEST_GAP / DEFER (observed only wrong-version harness; root cause unknown); do not infer a runtime root cause or change declared support opportunistically. Public profile edits require another explicit audit; no automatic exception expansion. No new architecture correction is warranted. KEEP/SPLIT remaining RI-005 adoption and approved exact-package handoff; KEEP RI-006 read-only proposal. REJECT duplicate updater/owner/intelligence abstractions. Next three existing scopes, without ranking: RI-005 old/unmanaged-writer absence; RI-005 immutable approved handoff; RI-006 source-bound read-only proposal.

No live8026 restart, private DB/chat/WAV/key/config/model/GPU access or formal deployment. Codebase Memory callable tools unavailable; graph/reindex NOT_RUN. Source evidence and actual checks are authoritative.
