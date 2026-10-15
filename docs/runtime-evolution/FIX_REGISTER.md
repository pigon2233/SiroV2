# Runtime Evolution Fix Register

## RT-005-FIX-02 — reserve terminal bookkeeping inside cancellation deadline

- Classification: REQUIRED_FIX.
- Source types: ORIGINAL_DESIGN_ERROR / BAD_INTERFACE / TEST_GAP.
- Source Task: D22 / RT-005-FIX-01; D57 complete verification.
- Severity: MEDIUM.
- Problem: All-arguments cleanup consumes4.75s of a5s end-to-end cancel allowance before terminal IO/body work.
- Evidence: full1997-case suite4FAIL; original lifecycle cancel5.090748s at line799. Controlled300ms terminal transaction delay fails on baseline13 and candidate14; no-delaydirectcasespass. Exact fullrun excess IO/timer source remains unlocalized.
- Expected Behavior: Original<5s cancellation gate, truthful unknown/FAILED and retained late ownership; contextual4.5s cleanup stays allowed.
- Actual Behavior: Original caller can exceed5s even when individual cleanup wait obeys4.75s.
- Root Cause: CONFIRMED inadequate original end-to-end budget allocation; do not attribute unlocalized walltime to new goal/schema logic.
- Scope: One local timeout selection in existing ToolOrchestrator.cancel_run; controlled regression tests.
- Files expected to change: services/tools/orchestrator.py; new test_cancel_budget_reserve.py; contracts/correction/evidence.
- Files that MUST NOT change: Integrated, process execution/backend/PGID, original lifecycle tests/assertion5s, SQLite/oldSQL, policy/providers/voice/UI, dependencies/checks/CI.
- Compatibility requirements: Same callbacks/states/errors; cancellation once, no newdispatch/lateUI/replay; retainactive handles to actualdone. Contextual/mixed4.75s and native4.5s remain.
- Proposed repair: Allactive arguments-only use4.0s existingwait, leaving1s for terminalwork; other modes unchanged.
- Tests required: Controlled0.5s journal-delay originalSLO RED→GREEN; contextual4.2s cleanup succeedsCANCELLED/ownedzero; originalunknown/late/crosssession/detach/cancel race25cases.
- Regression tests: Fulloriginal gate with schema-awareD57journalfixture, actualnewheadcloud; no added skips or changed thresholds.
- Acceptance criteria: TrueRED, local/focused/allchecksPASS with original<5sassert; exact leaf source-onlyreverse/reapply; lateownership/unknown unaffected.
- Rollback method: Disable affectedentrypoints/drain, revertonlytimeoutchoice/newtest; preservealllatestjournal/DB. Reversalreopensdeadlinegate, notsafe-deployapproval.
- Risk: LOWlocalbudget; arbitraryblockedOS/storageIO andmixedloadend-to-endbeyondscopedvalidationremainunproven.
- Status: DONE / LOCAL_VERIFIED: new2/original25/exactleafreverseRED→reapplyGREEN, finalfullscripts/check EXIT0/578.090s (1994PASS/5oldoptinSKIP/7warnings). Removes only this local deadline blocker; exactheadcloud/publicscope separately checked, release/wider-autonomy gates remain.

## FIX-021 — T19/T20 owner-approved product goal loop

- Classification: REQUIRED_FIX.
- Source types: MISSING_INTEGRATION / INCOMPLETE_TASK / TEST_GAP.
- Source Task: T19/T20; owner-supplied 2026-10-14 architect audit F1 (no main-product GoalService/Planner caller).
- Severity: HIGH.
- Problem: Persisted goals/planning exist as components; the product cannot create, approve, execute and inspect a durable goal.
- Evidence: `core/cognition.py` and `persistence/goals.py` existed at 5c67c6f; main composition had no goal caller. New true HTTP counterexamples caught a filename `none` colliding with the do-nothing candidate and a foreground DB-await approval window; raw RED is in `T19-goal-loop-2026-10-14/api/`.
- Expected Behavior: One bounded approved task reaches actual results, retains source and pending intent across restart, gives foreground/cancel priority, and never resumes itself.
- Actual Behavior: Original product has no goal entrypoint; candidate integration requires the local validation gates below. This is not a claim of general autonomous intelligence.
- Root Cause: CONFIRMED missing composition/caller; component tests did not cover the product loop. The design already specifies goals/planning; no architecture correction is required.
- Scope: One fixed `document-checklist-v1` caller reads 1–5 exact selected UTF-8 workspace files and inventories sourced TODOs; reuse existing GoalService/Planner/repositories and runtime boundary.
- Files expected to change: `core/cognition.py`; new `core/goal_tasks.py`, `services/agent/goal_tasks.py`, migration014; `persistence/goals.py`; main/Gateway transport; existing page; three new integration tests; contracts/decision/evidence.
- Files that MUST NOT change: Integrated/LLM/TTS/browser/skills/owner/release source, existing SQL migrations and Python tests except the exact latest-schema fixture identity correction in test_run_journal, dependencies/pins/CI/check gates, private data/config/keys/models/live8026. Separate RT-005-FIX-02 is the only additional production leaf.
- Compatibility requirements: Old Goal constructor/rows/transitions remain valid with task=None; exact approval/session/workspace binding; tools-off stops new work; nullable schema14 is additive. A schema13-only approved release must reject schema14 without rewriting approval or data. No auto model authorization, intent replay or mutation retry.
- Proposed repair: Typed closed nullable task metadata; explicit revision approve/resume; one cancel/join owner; persisted intent/result and read budget; no generic scheduler, second planner or store. Fix confirmed local caller bugs before completion.
- Tests required: Actual main/HTTP/Rust/SQLite, auth/origin/no-store, malformed/cross-session/revision/scope negatives, 20-row retention/delete, foreground/kill-switch/pause/cancel/shutdown/timeout, SQLite join, three restarts, sources/SHA/time, UI approval and stale-state controls.
- Regression tests: Original goal/planner/Gateway/UI/skill/release/owner/storage suites; full clean public Git checkout scripts/check; exact new-head cloud CI. Original tests remain unchanged except the approved schema-aware journal identity fixture; all other original assertions remain.
- Acceptance criteria: Scoped negative/positive gates and original checks pass; actual visible product loop and normal owned-child shutdown proven; explicit source preservation and rollback. Completion means inventory read complete, not TODO execution or learned strategy.
- Rollback method: Set `SIRO_GOAL_TASKS_ENABLED=0`, drain/join, roll back only source/UI integration. Retain schema14 column and all task/history/latest data; never drop/reverse SQL or silently authorize an old max_schema13 release. Approved compatible source rollback is a separate release gate.
- Risk: MEDIUM integration/CAS/cancellation; no guarantee of autonomous goal creation, arbitrary computer sandbox, real provider quality, 24h operation or formal release.
- Status: DONE / LOCAL_VERIFIED: final15-pathscripts/check EXIT0/578.090s, actualthreeprocess/IAB/readbackcycles, scopedsource-onlydata-retainingrollback and local fixes PASS. Removes only this local integration blocker; exactheadcloud/publicscope separately checked. T19/T20 broader autonomy remains PARTIAL, numbered history preserved.

### D57 review dispositions without extra immediate tasks

- The confirmed candidate ID/foreground window/callback/shortcut/startup-isolation defects are REQUIRED_FIX or MINOR_FIX implementation/integration gaps handled locally in FIX-021; raw RED, exact root causes and tests are linked in its report. They do not justify another planner/store or reopening unrelated RT history.
- The initial interrupted original lifecycle F was DEFER/UNKNOWN; complete verification later proves a5.090748s deadline violation and controlled baseline/candidate budget sensitivity. Reclassified REQUIRED_FIX / ORIGINAL_DESIGN_ERROR as RT-005-FIX-02; actual fullrun extra duration remains unlocalized, not labeled false-positive or new goal logic regression.
- Existing append-only planning/journal retention is **TECH_DEBT**;20 limit is only goal rows. Terminal goal cleanup removes this profile's trace. No automatic broader retention/scheduler is introduced.
- Original T19/T20 component labels versus broader product completion are **DOCUMENTATION_ONLY / DOCUMENTATION_DRIFT**; clarified scope in STATUS/roadmap, no fake whole-product DONE.

## RT-013-FIX-01 — bound the existing Rust filesystem.read leaf

- Classification: REQUIRED_FIX.
- Source types: IMPLEMENTATION_BUG / TEST_GAP.
- Source Task: RT-013 read adapter; discovered while verifying FIX-021 background reads.
- Severity: MEDIUM.
- Problem: Read size limit was checked after full allocation; opening a FIFO could block a runtime worker.
- Evidence: Existing `linux.rs` filesystem.read used fs::read then checked limit. Real pre-fix 4GiB sparse-file child under 128MiB limit failed; FIFO with no writer blocked until the owned 3s harness stopped/joined it. [Rust evidence](../evidence/T19-goal-loop-2026-10-14/rust-read/REPORT.md).
- Expected Behavior: Ordinary scoped UTF-8 reads keep the original result; nonregular or oversized sources fail without whole-file allocation or FIFO blocking.
- Actual Behavior: Original leaf allocated unbounded input or blocked before the output limit.
- Root Cause: CONFIRMED eager fs::read/open before resource/type checks.
- Scope: Existing filesystem.read branch and meaningful Rust negative fixtures only; no list/recursive scanner/process/runtime framework redesign.
- Files expected to change: `runtime/siro-runtime/src/linux.rs` only (production leaf plus cfg(test)).
- Files that MUST NOT change: list/other drivers/protocol/policy/roots/versions/locks; Python workspace adapter and original checks.
- Compatibility requirements: Original root checks, UTF-8 error and {text} output, bounded result and zero write behavior. No claim that O_NOFOLLOW repairs all parent alias/TOCTOU races.
- Proposed repair: O_NONBLOCK/O_NOFOLLOW open, opened-FD regular/type/size checks and take(limit+1) before accepted UTF-8 projection.
- Tests required: Sparse-file allocation counterexample, FIFO no-writer bounded refusal, directory, normal UTF-8, oversize/scope errors; all owned children/timeouts cleaned.
- Regression tests: All original six Rust tests; build/fmt/clippy and full scripts/check.
- Acceptance criteria: Original negative cases turn GREEN; seven new cases and original six pass; production-only reverse/reapply and exact source preservation; full caller verification.
- Rollback method: Disable the new read task caller first, reverse only this leaf; preserve runtime ledger/data and other source. Rollback reopens the unbounded-read gate, so it is not deployment approval.
- Risk: LOW local leaf behavior; general host execution and directory enumeration remain separate gates.
- Status: DONE / LOCAL_VERIFIED (13 Rust cases/build/fmt/clippy and finalwholecheck EXIT0/578.090s PASS); FIX-021 localgate met. exactheadcloud/publicscope separately checked.

## FIX-020 — unambiguous signed release source tree

- Classification: REQUIRED_FIX.
- Source types: ORIGINAL_DESIGN_ERROR / BAD_INTERFACE / TEST_GAP.
- Source Task: original T32, D39/D52 verification during RI005 immutable-source research.
- Severity: HIGH.
- Problem: Different file contents can share the unframed source digest and therefore the same complete signed manifest.
- Evidence: `src/siro/core/releases.py` `_digest`→`_verified`→stage/rollback/launch；true two-tree [probe](../evidence/FIX-020-2026-10-14/collision-proof.json)，15 RED→PASS、216 focused、full1813 PASS、actual five child/source/data acceptance。[Report](../evidence/FIX-020-2026-10-14/REPORT.md)。
- Expected Behavior: A release approval binds exact source file count, paths and contents.
- Actual Behavior: Legacy filename/content concatenation lacks boundaries, so equality does not establish per-file equality.
- Root Cause: Confirmed ambiguous original serialization; not a SHA256 collision attack.
- Scope: One local release identity algorithm/tag and existing execution authorization boundary.
- Files expected to change: releases.py; seven existing release/owner positive fixture files (preparation only); one new identity test; relevant contracts/correction/evidence.
- Files that MUST NOT change: Gateway/launcher, SQLite/migrations/owner/operations, policy/config, providers/TTS/UI/skills, dependency pins, original assertions or test gates.
- Compatibility requirements: Historical v1 bytes remain inspectable; explicit v2 reapproval, no silent reinterpretation or auto-resigning; old safe rejection/result shapes and data retention.
- Proposed repair: Domain/count/length-framed v2, tag bound in canonical full HMAC; deny legacy v1/None before source read/effects at `_verified`.
- Tests required: v1 equal-hash proof/bypass RED, independent v2 vectors, wrong digest/tag/HMAC, count/name/content/empty/resource/order sensitivity, legacy zero-effect stage/rollback/launch refusal.
- Regression tests: Original signing/schema/owner/CLI/source version/readiness/data-retention assertions; full clean scripts/check and exact-head CI.
- Acceptance criteria: Required negative/positive cases and regressions PASS, exact changes/fixture audit/source-only rollback, no data/receipt migration.
- Rollback method: Disable release execution entrypoints, reverse only this source/fixture repair; preserve data/history and never re-enable weak v1 approvals.
- Risk: HIGH trust boundary; source/import mutation and dependencies still separate unverified gates.
- Status: DONE / LOCAL_VERIFIED（full scripts/check EXIT0/637.507s）；解除 BLOCKED_BY_FIX: FIX-020，v2 identity scoped VERIFIED。exact-head cloud 另驗；RI005 仍 PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION，不改其他 numbered task 歷史。

## FIX-018 — RI-006 error responses retain no-store

- Classification: MINOR_FIX.
- Source types: MISSING_INTEGRATION / TEST_GAP（本輪未發布candidate）。
- Source Task: RI-006 D55 independent review；不是舊RT regression。
- Severity: LOW.
- Problem: 新proposal GET在unexpected producer failure/錯method回應缺no-store。
- Evidence: original ASGI probe GET500/POST405 header=None；`RI-006-2026-10-13/no-store-red.log`先1FAIL；final backend24PASS/full1798PASS。[Report](../evidence/RI-006-2026-10-13/REPORT.md)。
- Expected Behavior: 該view的成功與error/auth/method回應均no-store，錯誤不echo診斷。
- Actual Behavior: 修前只成功/HTTPException加header；修後matching endpoint ASGI送出header，producerexception安全503。
- Root Cause: header設定範圍漏route-generated405與非HTTPException，已確認。
- Scope: 只新endpoint的傳輸header/error邊界，其他HTTP/WS直通且不建task。
- Files expected to change: `src/siro/services/presentation/gateway.py`、新`tests/integration/test_improvement_proposal.py`。
- Files that MUST NOT change: D41 `runs.py`/SQL、Core policy/config、SQLite/migrations、TTS/providers、原測試、release/launcher。
- Compatibility requirements: 原GET/WS/stream/認證語意、cancellation保留；不catchBaseException、不回假proposal成功。
- Proposed repair: endpoint限定pure ASGI header；已知HTTPException保no-store，unexpected故障固定503，不讀raw recovery。
- Tests required: 原無header反例，POST405 producercalls0；GETfailure503/no-store/privatecanary absent。
- Regression tests: 原gateway/auth/WS及fullscripts/check；新D55source/UI取消、D41及TTS unchanged。
- Acceptance criteria: 全上述PASS、無其他response/globalmiddleware task改動，精確sourcehash綁定。
- Rollback method: 撤D55整個additive view/caller，不保留新view卻去掉header；保canonical資料/原介面。
- Risk: LOW，header與safe failure projection；不證明任意部署/智能品質。
- Status: DONE / LOCAL_VERIFIED（fullcheck EXIT0/499.591s）；new exact-head cloud另記。已解除本candidate BLOCKED_BY_FIX: FIX-018。

## FIX-019 — RI-006 preserves standalone inventory and speech fragments

- Classification: MINOR_FIX.
- Source types: IMPLEMENTATION_BUG / REGRESSION（本輪未發布candidate）。
- Source Task: RI-006 D55 first full clean check；old3fragment tests。
- Severity: LOW.
- Problem: 新activity clearing hook讓原inventory/speech片段開始依賴proposal module。
- Evidence: `clean-check-first-failure.log`原3ReferenceError/1795PASS；只修newhook後`fragment-regression.log`142PASS，finalfull1798PASS。[Report](../evidence/RI-006-2026-10-13/REPORT.md)。
- Expected Behavior: 原可獨立執行的inventory/speech保持獨立；fullpage新增proposal仍能清除stale卡。
- Actual Behavior: 修前unconditional clear function未被片段載入；修後optionalhook guard、fullpage清除行為保持。
- Root Cause: new direct dependency未沿optional feature boundary；已確認原片段截取與ReferenceError。
- Scope: 只existing fragment的新optional清除hook，不改inventory/語音演算法或既有test harness。
- Files expected to change: `src/siro/services/presentation/static/index.html`、新`tests/integration/test_frontend_improvement_proposal.py`。
- Files that MUST NOT change: 原inventory/speech/control tests、provider/audio/core/runtime/DB/policy/release、D41/TTS。
- Compatibility requirements: original fragment contracts保留；原完整頁面的新turn/refresh/disconnect/unload仍清除且取消late結果。
- Proposed repair: 既有片段呼叫可選proposal hook前檢查存在；不stub、不skip、不減原asserts。
- Tests required: 原3cases＋full real-page71新cancel/freshness/malformed/timeout-independent cases。
- Regression tests: capability/speech cancel/queue/原control；fullscripts/check及actual main/browser來源更正→舊card撤除。
- Acceptance criteria: 原132testfiles bytes全保持、95newcases通過、完整1798PASS且view hook真正被執行。
- Rollback method: 撤D55 source6/caller/panel整體；不只移guard重啟已知壞candidate；保原journal/memory/data。
- Risk: LOW，optional feature integration；還需原真voice品質/SLO個別驗收。
- Status: DONE / LOCAL_VERIFIED（fullcheck EXIT0/499.591s）；new exact-head cloud另記。已解除本candidate BLOCKED_BY_FIX: FIX-019。

## FIX-017 — owner rejection must precede optional voice SDK initialization

- Classification: REQUIRED_FIX.
- Source types: IMPLEMENTATION_BUG / MISSING_INTEGRATION / TEST_GAP (existing eager import, not attributed to new RT).
- Source Task: FIX-016 actual GitHub2324b35 run38389536976; D50 owner invariant verification.
- Severity: MEDIUM.
- Problem: importing Gateway requests ONNX via optional Kokoro before acquiring data owner; Busy path can emit hardware discovery or fail on broken SDK.
- Evidence: actual job115269605525 busy contender has exact desired exit/message plus ONNXwarning; fresh-process guard reports requested kokoro_onnx and zero owner acquisitions. call presentation/__init__.py→gateway.py43→audio/tts.py22→kokoro_onnx.__init__→onnxruntime. All diagnostics synthetic/public CI.
- Expected Behavior: import and Busy rejection do not initialize optional inference SDK; when authorized owned render occurs, same Kokoro SDK/model runs offloop with existing args and caching.
- Actual Behavior: SDK/device discovery occurs during module import, before main takes owner; ImportError can bypass fixed Busy result.
- Root Cause: CONFIRMED module-top Kokoro import in leaf TTS eagerly imports ONNX. No source/tests/scripts caller relies on public tts.Kokoro alias.
- Scope: defer only existing Kokoro import to existing lazy rendering branch; annotation TYPE_CHECKING; new meaningful contract tests.
- Files expected to change: src/siro/services/audio/tts.py; new tests/integration/test_tts_import_boundary.py; contracts/docs/evidence.
- Files that MUST NOT change: Gateway/owner/Core/SQLite/permissions/oldtests, rendering/TTS config/output/cancel semantics, Qwen/Live2D, other audio/providers, dependency/pin/locks, private data/models/config/keys/live8026.
- Compatibility requirements: same Kokoro constructor/create/voice args and cached model; same exceptions and worker ownership; no silent fallback, new APIs or warning suppression.
- Proposed repair: TYPE_CHECKING annotation plus local runtime import inside existing _render_sync if _model is None; preserve rest verbatim.
- Tests required: before fresh-process importguard RED/no-owner; after import no optional SDK, Busy zero initialization; synthetic SDK positive render inside worker thread/cache/typedfailure, existing timeout/cancellation unchanged.
- Regression tests: audio/native speech/owner caller/launcher integrations and complete offline gate; remote supported-environment actual checks. No real voice efficacy claim.
- Acceptance criteria: importguard and existing exact Busy diagnostic invariant PASS; normal existing SDK path retained; precise TTS-only local diff, all other existing source untouched for this card; final source-bound checks.
- Rollback method: disposable exact TTS/newtest reverse/reapply, preserve all data and prior FIX-016 source; source rollback reopens owner initialization gate and is not authorization to deploy unsafe state.
- Risk: optional SDK errors appear at first owned render; propagate original errors, existing offloop cancellation still owns actual render. No promise to cancel third-party blocking imports beyond existing worker contract.
- Status: DONE / VERIFIED (D54 scoped owner/import leaf; 5RED→PASS/34focusedPASS/exact2rollback/localfull1702 and remote1702PASS). Removes only FIX-017 owner-import gate; FIX-016 CI now independently DONE / VERIFIED at exact4811db2 Actions38395186441; source/production gates remain scoped. RI-005/006 onward no longer BLOCKED_BY_FIX: FIX-016/FIX-017; original release-integration/product gates remain; no RT history renumber/reopen.


## FIX-016 — clean checkout CI bootstrap / public-pin verification

- Classification: REQUIRED_FIX (broken CI gate); six public hashes are FALSE_POSITIVE.
- Source types: MISSING_INTEGRATION / INCOMPLETE_TASK / TEST_GAP.
- Source Task: latest push d1f5d07 / check run38356354040; T01/T21 check bootstrap, RT-011 pinned tokenizer provisioning. No evidence attributes this to one new RT task.
- Severity: MEDIUM.
- Problem: fresh runner lacks cargo-fmt/clippy; original final secret gate rejects audited public tokenizer hashes.
- Evidence: ../evidence/FIX-016-2026-10-13/toolchain-probe.json (cold minimal failures, manifest-only fix success), scan-original-gate.log (exit1/six locations), scan-public-primary-pins.json (five official downloads match). Actual GitHub job115160055433 fails before regressions. No existing PR found; this is push-triggered Actions.
- Expected Behavior: fresh checkout runs all existing checks; exact audited public fingerprints pass while any new/changed suspected secret fails.
- Actual Behavior: initial remote exits1 at fmt; independently reproduced old secret gate exits1. Prior local suites did not certify CI.
- Root Cause: CONFIRMED missing toolchain components declaration; final gate had no precise public-fingerprint review handling; old Rust unit fixture required a distro-specific interpreter location absent on the actual Ubuntu runner. Runtime behavior is not implicated.
- Scope: one manifest line; build-only secret-report helper called from existing check; meaningful synthetic/actual-scanner tests and documentation/evidence.
- Files expected to change: rust-toolchain.toml, scripts/check, new scripts/check_secrets.py and tests/integration/test_ci_secret_gate.py; docs. Remote refinement additionally allows only three Python executable literals in runtime/siro-runtime/src/linux.rs cfg(test) fixture (production prefix and all assertions unchanged). Further actual-cloud evidence permits .github/workflows/check.yml supported native Ubuntu26.04 prerequisites only, and the quoted-numeric-key intermediate fixture expectations in tests/integration/test_unknown_effect_approval.py; all policy/effect assertions unchanged.
- Files that MUST NOT change: all production source for FIX-016 (separate FIX-017 TTS leaf correction tracked independently), old tests except the three cfg(test) literals and quoted-key intermediate expectation above, workflow except supported runner prerequisites, Python/Rust versions, Cargo.lock/uv.lock, schemas/migrations, providers/voice/UI/permissions/Memory, launcher/release/owner, private data/models/config/keys/live8026.
- Compatibility requirements: no runtime/API/DB change; same scanner scope and check order; all unknown findings still exit1. Exact public profile changes require fresh explicit audit, not automatic extension.
- Proposed repair: declare rustfmt/clippy in existing pinned minimal toolchain; allow six exact detector findings only when whole audited profile matches; validate JSON structure/finding binding, fixed diagnostics; tests precede helper.
- Tests required: cold empty tool homes before/after; actual scanner positive, new synthetic credential in profile/other file, profile-byte change, altered fingerprint/path/type/line/verified flag, malformed reports; helper type/lint/format.
- Regression tests: full scripts/check in clean public archive; all Rust checks and Python tests, schemas and secrets; exact new GitHub head run. No private workspace scan.
- Acceptance criteria: required checks remain enabled; local full check and remote exact head succeed; all production/old tests/locks/pins byte-identical; exact source rollback; owned temporary children/files cleaned.
- Rollback method: disposable exact four-file reverse/reapply; revert two build files/remove helper and newtest only. Preserve data, prior source/Git backup; rolling back reopens FAILED_VERIFICATION, cannot claim gate removed.
- Risk: public pins change needs re-audit; strict malformed rejection can expose scanner format changes. Does not certify real providers/product quality/deployment.
- Status: DONE / VERIFIED (D53). Exact4811db2 Actions38395186441 SUCCESS; trueGitcheckout/fetch fullscripts/checkEXIT0/492.046s,1703PASS/5opt-inSKIP/7warnings. Original102extraenvironment-skips gone; all6Rust/static/schema/scanner gates pass. Removes only FIX-016 CI blocker; RI-005 releaseintegration and productquality gates remain. Exact9combinedrollback and finalsourcehashes verified; existingRTDONE history unchanged.


## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

本卡是RI-005原remaining MISSING_INTEGRATION / INCOMPLETE_TASK / TEST_GAP的限定實作，未發現新正式runtime IMPLEMENTATION_BUG，不另造重複FIX或ARCHITECTURE_CORRECTION。D52selector/identity/ready VERIFIED；oldwriter/immutablehandoff仍BLOCKED_BY_RELEASE_INTEGRATION。

新增DTO永久negativecases補TEST_GAP；processjson/hashlib import與rollbackevidence欄位錯誤皆fixture-only已修並重跑，不能要求production重構。FIX-012–015原scopedDONE保持。

95新cases；最終相鄰335 PASS／3既有warnings／25.63s，完整 **1,673 PASS／5 real_provider未選／3既有warnings／199.58s**。Ruff315、mypy250（含launcher）、schema、source/tests/docs diff PASS。

273baseline中270不改；exact7 source-only disposable reverse/reapply PASS，保所有資料與Git歷史。D48 schema helper抽出前後AST相同；D51 backup/CLI四檔與D50 owner/operations source保持。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## FIX-015 — ZIP backup cancellation must not recreate cleaned staging

- Classification: REQUIRED_FIX; same-card CLI teardown/selector corrections MINOR_FIX.
- Source types: IMPLEMENTATION_BUG / MISSING_INTEGRATION / TEST_GAP; first CLI selector defect additionally REGRESSION, fixed before final acceptance.
- Source Task: RI-005 D50 independent true ZIP backup-stage cancellation review; existing T34 backup_to/create_backup_bundle. D51 local repair.
- Severity: MEDIUM for retained snapshot; LOW for same-card pending task / selector integration.
- Problem: canceled backup coroutine let ZIP staging unwind before its actual SQLite thread completed, so late mkdir recreated snapshot/WAL/SHM; initial local CLI handler also failed to wake a blocked selector.
- Evidence: original D50 zip-joint-signal-probe.json; this card signal-before*.json, signal-after-progress.json (data safe but pending-task stderr), signal-cli-wakeup-before.json (8 timing failures), focused-before-wakeup.log/full-before-wakeup.log (2 original D50 caller failures), final signal-final.json/source-freeze.json. operations.py TemporaryDirectory→await backup_to; SQLite backup_to→worker mkdir/copy; cli.py _backup→Runner/temporary SIGINT handler. All synthetic actual IO; pauses/faults explicitly controlled.
- Expected Behavior: owned IO and both connections resolve before writer/ZIP cleanup; no late staging resurrection, prior output/input retained when publication has not happened, committed raw backup outcome honest; repeated SIGINT completes coroutine cleanup and preserves handler/error.
- Actual Behavior: original staged orphan reproduced; initial SQL-only three-SIGINT preserved data but pending coroutine warning; first CLI temporary handler blocked selector. Final actual8 has exit130, zero stderr, exact handler restored, joined IO/children, staging absent, allkeys held until join and next-owner data retained.
- Root Cause: confirmed bare await to_thread did not own running worker duration; sqlite3 transaction contexts did not close connections; default repeated SIGINT could abandon coroutine cleanup; first temporary handler omitted stdlib Runner's blocked-selector wakeup. No model/filesystem inference.
- Scope: existing SQLiteStore backup_to/_backup_sync and existing CLI _backup composition wrapper only; two focused test files plus contracts/docs/evidence. No general backup/executor/owner manager.
- Files expected to change: src/siro/persistence/sqlite.py (backup only), src/siro/cli.py (_backup plus threading imports), new tests/integration/test_sqlite_backup_lifecycle.py, tests/integration/test_backup_cli_cancellation.py; documentation/evidence.
- Files that MUST NOT change: D49 restore body/migrations/schema, operations, D50 adapter/Gateway/main/old tests, Core, ReleaseManager, grants/policy/identity/memory, providers/voice/UI, launcher/systemd/dependencies and private DB/chat/config/WAV/keys/models.
- Compatibility requirements: same successful public API/raw/ZIP format/CLI arguments; private cancel optional; context propagation preserved; plain cancellation/primary typed errors unchanged; signal cancellation remains KeyboardInterrupt/130. No retry, auto rollback or new permission.
- Proposed repair: retained current-default-executor Future with copy_context, asyncio.wait/result and local cancellation Event; actual progress/publication fences, explicit source/target close and safe primary/secondary cleanup errors. Backup-only temporary SIGINT cancels owned task and wakes same loop, waits IO cleanup, finally restores exact handler. Implemented locally; original operations and owner unchanged.
- Tests required: 19 SQLite lifecycle + 6 CLI cases; true8 child SIGINT covering raw/ZIP1/3, actual64-of-124-page in-flight copy and post-publication cancellation; controlled primary/close/unlink failure distinct. Original D50 callers remain unchanged and rerun.
- Regression tests: final240 focused including D49 restore, T34 operational CLI, D48 release/signing/retention, D50 owner and caller lifecycle; full1,578 offline PASS/5real_provider unselected/3existingwarnings; Ruff311/mypy245/schema/diff PASS.
- Acceptance criteria: all final actual cancellation/staging/key/next-owner/connection/error invariants PASS; final source-bound full/focused gates completed; original D49/D50 and 269 other baseline files retained; no claimed private or deployment acceptance.
- Rollback method: exact4 source-only patch reverse/reapply in disposable directory; baseline271→269 unchanged, before SQLite/CLI restored and two newtests removed then all4 reapplied/hash-identical. Keep all data/latest rows/archives/owner keys/Git backup; no live rollback invocation of unsafe behavior.
- Risk: committed output may coexist with exit130; readback before retry. OS refusal/no-limit IO cannot be called cleaned/canceled. Original staged dir0700→0775 but actual files0600; no measured other-UID exposure. Powerloss, ZIP multfile atomic, old/nonmanaged writer and approved exact launcher/handoff remain outside this card.
- Status: DONE / VERIFIED for FIX-015/D51. Removes only BLOCKED_BY_FIX: FIX-015 canceled-staging/teardown gate. RI-005 remains PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION; D50/FIX-014 scopedDONE preserved. First24 controlled PASS is historical, not final OS acceptance. [Final report](../evidence/FIX-015-2026-10-13/REPORT.md).

## FIX-014 — RI-005 D50 managed write-target coverage

- Classification: REQUIRED_FIX
- Source types: IMPLEMENTATION_BUG / MISSING_INTEGRATION / BAD_INTERFACE / TEST_GAP
- Source Task: RI-005 D50 verification; T34 backup/ZIP restore callers
- Severity: HIGH
- Problem: source-only ownership permits backup to overwrite another managed live database, or overwrite its own database/settings with a snapshot/ZIP; restore config can overwrite a managed foreign DB or its own DB/source archive. Deterministic ZIP .tmp can also overwrite/delete input or alias final into a selfloop.
- Evidence: ../evidence/RI-005-owner-2026-10-12/backup-destination-probe.json: actual target child still owns lease/open connection, CLI backup0, target inode/value replaced while child old connection unchanged. write-target-before.log/all-write-targets-before.log9FAIL and temporary-target-before-all.log8FAIL actual caller RED; cli.py main only source key; SQLiteStore._backup_sync os.replace destination and operations._atomic_write config. Synthetic data only.
- Expected Behavior: all explicit write targets are held before any body effects; invalid input/output role collisions refuse without modifying DB/settings/backup.
- Actual Behavior: source-only guarded CLI returns success while foreign target stays leased and its path is overwritten; own ZIP destination can turn siro.db into ZIP; config collision can destroy restored DB/archive.
- Root Cause: confirmed missing destination/config ownership and missing canonical input/output collision checks at caller; lower IO operations correctly follow their provided paths, so do not redesign them.
- Scope: existing new D50 resource may own one/two deduplicated canonical FDs, one owned-IO join before any release; CLI maps explicit backup/config write target and rejects role aliases.
- Files expected to change: src/siro/adapters/data_ownership.py, src/siro/cli.py; same two D50 focused test files; evidence/contracts/status only.
- Files that MUST NOT change: D49 SQLiteStore, operations, releases.py, integrated.py, scripts/launcher/systemd, Core/SQL/schema/policy/grants/providers/voice/UI/identity/private data/dependencies.
- Compatibility requirements: successful valid CLI and helper default unchanged; new failclosed busy/invalid-target statuses only; no new grant, forced stop, automatic retry or hidden data rollback.
- Proposed repair: optional write_target and temporary_write_target in same local resource; sort/dedupe canonical byte identities; partial acquire cleanup; one joint IO fence; caller canonical source/settings/archive collision guard before effects.
- Tests required: actual raw/ZIP foreign target busy zero effects/inode preserved; self source/config/archive refusal; ZIP fixed-temp input/final/ownDB aliases and busy foreign temp preserve artifacts; partial acquisition releases held prefix; canonical alias dedupe; IO join refusal retains both actual locks; repeated SIGINT keeps destination locked until IO joined.
- Regression tests: D50 actual Gateway/CLI ownership/lifecycle plus D49 restore, T34 operations, D48 releases/signing/launcher and full offline baseline.
- Acceptance criteria: every named write target guarded until all owned IO completes; all rejected targets retain latest data/config/source artifacts; no reintroduction of D49; final source binding/full checks/exact rollback pass.
- Rollback method: final D50 exact scoped source-only reverse/reapply in disposable copy; preserve actual DB/config/backup and operational lockfiles. Do not restore source-only unsafe caller into operation.
- Risk: cooperative sameUID/localFS only; old/raw/unmanaged writers, hostile path races, ZIP multi-file atomicity, powerloss and runtime launcher handoff remain separate gates.
- Status: DONE / VERIFIED for D50's named source/explicit/deterministic-ZIP-temp write-target profile;70 new cases/215 focused/1553 full/exact5-source rollback PASS. FIX-014 gate remains removed. Separate FIX-015 ZIP cancellation staging cleanup is now D51 DONE / VERIFIED; existing signed-launcher/adoption/handoff gates remain BLOCKED_BY_RELEASE_INTEGRATION; no deployment.

## 2026-10-12 — D49 / FIX-013 explicit restore 局部修復 VERIFIED

真正 temporary SQLite 證明舊路徑先覆蓋 live 再拒 migration/checksum，且 cancellation 提前釋放 writer lock。只改既有 SQLiteStore：mode=ro/query_only source→owned candidate→known prefix/checksum/既有遷移/integrity→SQLite backup promotion；不replace live/WAL。原 per-store writer lock 持有到 offloop thread/explicit connection close/cleanup joined；取消中止未完成 copy，DONE後取消誠實保留已commit資料。原typed error保留、cleanup refusal可見，不假稱已移除。獨立review先RED修掉Python3.14 shield重複error，只改owned await asyncio.wait/job.result，沒有新restore/schema/updater抽象。

41新cases；exact original source **30FAIL/11PASS**（5.61s）；最終專項 **145PASS**（4.95s），完整 **1,483PASS/5 real_provider未選/3既有warnings**（156.51s）；Ruff306/mypy240/schema/diff PASS。真raw/ZIP CLI、舊schema/WAL/來源唯讀、取消/queued writer/ledger retention驗收；IO/清理/進度timing標controlled。三份獨立review重綁final source後無scoped blocker。266 baseline中265不改、新2tests，exact3 source-only reverse/reapply PASS，D47/D48保留；final source3/docs12掃描0；evidence55inputs/277逐項capturedSHA256誤報/unresolved0，cutoff 2026-10-11 17:58:09 UTC（audit outputs與此後結果annotation排除）。

FIX-013 **DONE/VERIFIED**，只解除此explicit-restore failure gate；RI-005整體 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：activepointer不等於真正版本，stopped writer／實際launcher/version/readiness／人工批准還未驗。成功明確data restore可替換近期資料，code rollback仍只切版本；commit後取消/cleanup failure需readback再決定，不重送。沒有live8026 restart、privateDB/chat/WAV/key/model/GPU或發布；FIX-002/005/006產品gate與RT-011/013/015 scopedDONE不變。

Architecture YELLOW；restore元件YELLOW、合成測試/evidence GREEN；運行DB/migrations／權限／發布RED。ZIP DB/config跨檔atomic、multiprocess lease、powerloss不算本卡驗收；candidate disk-capacity／舊backup retention為TECH_DEBT/DEFER，不建新manager。KEEP RI-005、SPLIT stopped-owner與actuallauncher；接續三窄切片RI-005 owner、RI-005 approved launcher/version/readiness、RI-006唯讀提案（非ranking、不重編）。Hermes REJECT重複restore/evolution abstraction，DEFER任意自改/發布直到接入有證據；本卡無new scoped blocker。

[驗收、限制、精確回退](../evidence/FIX-013-2026-10-12/REPORT.md)。

## 2026-10-11 — RI-005 D48 / FIX-012 code-only回退限定切片 VERIFIED

原T32把版本回退與wholeDB restore綁一起，舊測試要求新寫入消失，是ORIGINAL_DESIGN_ERROR／REQUIRED_FIX HIGH，不是新Sol regression。[最小架構更正](ARCHITECTURE_CORRECTION.md)。只改既有ReleaseManager：新staged版本保存完整D39signedmanifest sidecar並拒順序同版覆寫，health後再驗來源；rollback驗精確target/signature/alias＋實際readonly schema prefix，unknown/incompatible拒絕，只切active pointer、從不讀舊backup還原或migrate/replay。既有獨立siro restore保持分開，移除只被舊rollback使用的private restore helper。API/CLI/簽章格式保持，危險資料回退語意明確撤銷；沒有自動信任升級/新updater/schemaengine/lockservice。

新51cases＋原release/signing/launcher/operations94PASS（3.75s）；完整1,442PASS、5 real_provider未選、3既有warnings（157.59s）。真temporary SQLite/WAL晚寫/原writer仍可用、conversation/memory/完成ledger保留、real migratedDB CLI、schema/receipt/source/path負向；pointer/receipt錯誤為controlled injection，沒有實際啟動另一version或真人產品驗收。全repo Ruff304／mypy238／schema/diff PASS；baseline265中263未改、exact3 source-only reverse/reapply PASS，D47十一檔保持；3source/13publicdocs敏感掃描0；evidence 273逐項SHA256誤報、unresolved0；cutoff 2026-10-11 15:53:57 UTC（audit outputs與後續status/count annotation另排除）。

另外真合成probe確認SQLiteStore explicit restore在migration/checksum failure前已覆蓋live：**FIX-013 REQUIRED_FIX/HIGH PLANNED，該failure path FAILED_VERIFICATION**，此卡未改SQLite/migrations。RI-005整體PARTIAL，full activation／data-restore acceptance標BLOCKED_BY_FIX: FIX-013與原BLOCKED_BY_RELEASE_INTEGRATION；active pointer≠真正執行版本，launcher仍需consume/readiness與stopped-writer gate。元件source rollback不授權重新呼叫舊危險DB回退。沒有live8026/privateDB/chat/WAV/key/model/GPU/發布。三個分派審查turn碰帳戶limit，最終獨立review NOT_RUN，root直接source/實測不冒充獨立批准。

Architecture overall YELLOW；ReleaseManager元件YELLOW、合成測試/docs GREEN；運行中的DB/migration/權限/發布仍RED。順序immutableversion/read-schema snapshot不等於concurrent owner lease、powerloss或實際loader相容。保留舊backup但不自動用其回退是TECH_DEBT retention，不擴全局抽象。KEEP剩餘RI-005並SPLIT stopped-writer/actuallauncher；下一三張接續範圍FIX-013局部prevalidation、RI-005剩餘接線、RI-006唯讀提案（非ranking）；RT-011/013/015 DONE保持，FIX-002/005/006產品限制不解除。

[完整驗收與回退](../evidence/RI-005-2026-10-11/REPORT.md)。

## FIX-013 — explicit restore prevalidation before live data replacement

- Classification: REQUIRED_FIX
- Source types: IMPLEMENTATION_BUG / BAD_INTERFACE / TEST_GAP
- Source Task: RI-005 D48 restore-path verification; T34 SQLiteStore.restore_from
- Severity: HIGH
- Problem: explicit restore originally replaced latest live data before migration rejection; unknown future metadata was accepted, and cancellation released writer ownership while the thread continued.
- Evidence: D48 restore-failure.json and D49 before/src/siro/persistence/sqlite.py exact original; final original-projection30FAIL/11PASS; independent boundary/current probes. D49 final src/siro/persistence/sqlite.py:361 restore_from→owned job→_restore_sync(candidate validation before live backup). ../evidence/FIX-013-2026-10-12/REPORT.md.
- Expected Behavior: rejected/incompatible/migration-failed backup must leave latest live DB unchanged; successful explicit data restore remains intentional and separately authorized.
- Actual Behavior: Before: old snapshot became live on checksum failure/future metadata; canceled thread could erase queued writes. After: rejected candidate preserves latest rows/source; cancellation joins under writer lock, primary typed errors retained, committed restore never described as rolled back.
- Root Cause: confirmed validation-after-promotion ordering, apply_migrations lacking unknown-version rejection, and bare to_thread cancellation not owning the continuing thread. Intermediate shield duplicate-error race independently reproduced1FAIL and fixed by wait/result without changing ownership.
- Scope: prevalidate/migrate an owned temporary candidate before the live replacement boundary in existing SQLiteStore; retain current writer lock and API. Do not redesign DB/operations/release.
- Files expected to change: exact3: src/siro/persistence/sqlite.py; tests/integration/test_sqlite_restore_validation.py; tests/integration/test_sqlite_restore_lifecycle.py; public evidence/contracts/decisions/status only.
- Files that MUST NOT change: releases.py D48/D39, launcher/Gateway/UI, existing SQL migrations, schemas/identity/memory/policy/skills/providers/voice, private/live state, dependency locks.
- Compatibility requirements: same restore_from API and successful explicit data restore intent; rejected candidate yields original typed failure and zero live changes. Backup original remains unchanged; no hidden automatic data rollback.
- Proposed repair: fully validate/migrate candidate away from live DB before any live overwrite; failures clean owned temporary files and retain live bytes/rows/WAL. Preserve atomic writer/cancellation ownership and primary error. Use existing SQLite backup/transaction abstractions, no new restore service.
- Tests required: completed41 actual-DB cases with controlled timing/IO/cleanup: checksum/name/future/gap/type metadata, migration SQL failure, schema0/1/3/10/12/13 upgrade, WAL/source readonly+explicit closes, both copy-stage cancellations, waiting-lock/repeated cancel/queued writer, postcommit cleanup cancel, primary-error/cleanup refusal/no duplicate-log.
- Regression tests: SQLite store/migration/backup tests, explicit CLI ZIP restore, D48 code-only rollback and original operational/launcher tests.
- Acceptance criteria: met for scoped trusted-operator/per-store profile: validation failures preserve canonical latest DB/ledger and source; successful restore upgraded off-live; owned connections/candidate cleanup joined or visible typed refusal;145 adjacent/1483 offline final PASS; no deployment/private artifacts. Commit-after-cancel and config cross-file atomicity excluded.
- Rollback method: exact3 repair.patch reverse/check/reapply in disposable copy PASS;266 baseline/265 existing unchanged/D47D48 preserved. Keep latest actual DB; do not execute old unsafe restore against private/live data.
- Risk: per-store owner only; external writers/transactions, ZIP DB/config atomicity, hostile-schema attestation, OS-blocked IO SLO and powerloss unverified. At SQLite DONE, cancellation/cleanup error may coexist with committed data: inspect before retry.
- Status: DONE / VERIFIED (D49/FIX-013 bounded explicit-restore repair). Removes only BLOCKED_BY_FIX: FIX-013; RI-005 remains PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION for stopped owner/actual launcher/version/readiness/approval. No deployment.

## FIX-012 — RI-005 D48 / latest data retained on code rollback

- Classification: REQUIRED_FIX
- Source types: ORIGINAL_DESIGN_ERROR / BAD_INTERFACE / TEST_GAP (not demonstrated REGRESSION)
- Source Task: T32, FIX-009 D39 retained behavior, RI-005/current verification review
- Severity: HIGH
- Problem: code rollback silently restores old whole DB and loses later committed data.
- Evidence: releases.py rollback→_restore_database→temporary.replace(live DB); test_release_manager.py late UPDATE followed by required before-release value. Actual synthetic RED probes/tests are saved in ../evidence/RI-005-2026-10-11/.
- Expected Behavior: revert code only; keep latest conversation/memory/ledger and refuse unknown/incompatible target/schema.
- Actual Behavior: old snapshot replaces live main database before pointer switch; backup missing blocks even a harmless code rollback.
- Root Cause: confirmed conflation of code rollback and data restore in original T32 contract and matching implementation/test.
- Scope: unique ReleaseManager pointer path, complete existing manifest sidecar and actual readonly schema snapshot; local immutable-version guard needed to preserve the stored rollback identity.
- Files expected to change: src/siro/core/releases.py; tests/integration/test_release_manager.py; new tests/integration/test_release_data_retention.py; contract/decision/review evidence.
- Files that MUST NOT change: launcher, Gateway/UI, SQLiteStore/migrations, conversation/identity/memory/skills/policy, providers/voice/build dependencies, live8026/private files.
- Compatibility requirements: same public signatures/CLI/status JSON and full signing format. Old destructive semantic intentionally withdrawn; no legacy re-sign/fallback. Explicit data restore remains separate.
- Proposed repair: never restore DB in rollback; read actual schema, verify captured signed target, atomically select code pointer. Store verified sidecar at staging; refuse existing version overwrite. No runtime launch/deploy.
- Tests required: actual temp SQLite late writes/WAL, target/receipt/schema negatives, missing old backup, immutable-version zero effects, pointer interruption, real CLI; controlled seams labeled separately.
- Regression tests: original release/signing and explicit restore/launcher baselines; full non-real_provider suite, format/type/schema/diff, exact3source rollback/preservation.
- Acceptance criteria: latest rows/ledger retained, writer connection remains usable; rejection has zero active pointer/data effects; no restore/migration/check/replay; actual CLI parseable; D47 hashes unchanged.
- Rollback method: exact3file temporary reverse/reapply only; keep latest data. Do not invoke obsolete source's automatic DB-restoring rollback after developer source rollback.
- Risk: scalar signed schema compatibility does not prove launcher/loader/readiness; snapshot is not a stopped-writer lease. Legacy release without receipt requires separate trusted validation. Core/DB/release operational gate remains RED.
- Status: DONE / VERIFIED for FIX-012/D48 component: 51 new cases, 94 focused, full1,442 offline PASS; exact3 rollback and265 baseline preservation. Final scoped3source/13docs zero-findings and273 individually reviewed digest findings/unresolved0; recorded cutoff with annotation-only deltas excluded. RI-005 full runtime switch remains BLOCKED_BY_RELEASE_INTEGRATION / BLOCKED_BY_FIX: FIX-013 until explicit restore, launcher/single-writer/latest-data/health acceptance. No downstream automatic deploy.


## 2026-10-11 — RI-004 D47 固定技能產品接入（限定切片 VERIFIED）

既有D44準備/真驗證＋D46strict worker接進同一registry/catalog/orchestrator/dispatcher：server-held review900s/完整identity→人工安裝disabled→另一步明確enable→原對話tool批准→revoke；沒有模型自批、任意code/依賴、第二套registry/scheduler/schema。新facade/CAS不覆寫同版，queued/active jobs先fence再join，取消offloop交易補disabled，cleanupfailure仍嘗試durable revoke、保留typed error。Startup只恢復精確固定模板/receipt/row，tools-off持久停用，shutdown保留原owner明確批准供exact restart。

最後真畫面發現準備紀錄與已安裝狀態矛盾，補2個RED→局部history-label修復，不改匯出原始事實。最終189專項PASS（17.12s）／完整1,391PASS、5 real_provider未選、3既有warnings（154.61s）；Ruff302／mypy237／lint／schema PASS。真CUA/HTTP/SQLite/bwrap走通安裝disabled→明確enable→填入不送出→revoke/readback，fixture退出0、owned jobs0、暫存清除。最後exact11 source回退/reapply與獨立綁定PASS，baseline258中254不變，D46七檔/Core/policy保留。11source/10publicdocs敏感掃描0，evidence356逐項digest誤報/unresolved0（02:10:44UTC cutoff；後續僅狀態/計數annotation）。最後console一則無來源MutationObserver錯誤，origin UNKNOWN，已留證據，未宣稱零錯或猜測修復。實際產品驗證只temporary18034，不讀私人DB/chat/WAV/key、不碰模型/GPU、不重啟live8026或正式部署。

RI-004整體仍PARTIAL，但固定builtin checklist人工批准/strict執行/撤銷切片的局部caller接入gate已解除。RI-005 launcher/single-writer/latest-data-preserving rollback保持BLOCKED直到各自驗收；RI-006 KEEP，FIX-002有用搜尋/FIX-005速度人耳/FIX-006真理解保持既有產品限制。RT-011/013/015 DONE不重開、不重編、不ranking。Gateway/registry/catalog保持YELLOW（新owner生命週期），D46已驗限定profile可GREEN，Core/permission/release仍RED freeze；sameUID/任意生成/multiprocess/aggregateRAM不算通過。沒有original design correction或新全局state manager。

[完整變更與驗收](../evidence/RI-004-activation-2026-10-11/REPORT.md)。

## 2026-10-11 RI-004 strict worker gate 更新

FIX-011局部VERIFIED保持；D46 fixed stdlib worker OS/cancel/resource切片已VERIFIED，51新cases／完整1,202PASS及exact7回退。[證據](../evidence/RI-004-worker-2026-10-11/REPORT.md)。卡內typedmetadata/queueadmission/absolutedeadline三問題分類REQUIRED_FIX／IMPLEMENTATION_BUG／TEST_GAP，先RED→最小同檔修復完成；不是已確認privateproduct regression，不另造重複未完FIX或改RT歷史。沒有originaldesignerror，無ARCHITECTURE_CORRECTION。

**BLOCKED_BY_SKILL_INTEGRATION**現收斂為server-heldreview／package-bound owner安全審閱與明確批准、disabledinstall／exactidentityCAS／sameversioncollisionrefusal、enable/revoke停止queued+active並join、既有catalog/chat接入；不能用strictworkerPASS替approve。一般deps/multiprocess/其他OS/aggregateRAM仍獨立未驗，release和產品品質gates不變。

## 2026-10-11 FIX-011 — worker 洪水／取消生命週期

- Classification: REQUIRED_FIX；Source kind: IMPLEMENTATION_BUG／TEST_GAP；Severity: HIGH。
- Status: **DONE／VERIFIED**；限定trusted worker lifecycle。不是目前已發生的私人runtime regression，existing worker尚無generated產品caller。
- Evidence: 合成實測stdout/stderr洪水在manifest1.5s仍不返回、外層5s才TimeoutError；合法100k-byte輸出single-read誤報invalid JSON；cancel during spawn／stdin留下owned程序；fork child可setsid離開舊PGID。詳細 [repair-definition](../evidence/FIX-011-2026-10-11/repair-definition.md)。
- Minimal repair: D45 single bounded owner重用到lower adapter、read-only owned bounded request檔、PIDnamespace／移除第二session、offloopprep/cleanup及取消join。既有registry/hash/dispatcher、trusted runtime依賴與對話/語音/DB不重構。
- Verification: 新24PASS、完整1,151PASS／5real_provider未選／3既有warnings／132.76s；独立review UTF-8／privatecaller及cleanup precedence先RED→local修復，exact5回退與252baseline保存PASS。[報告](../evidence/FIX-011-2026-10-11/REPORT.md)。
- Affected roadmap: **FIX-011局部block解除**，RI-004可開始strict worker驗證；D44已驗candidate/review仍有效；worker OS／review／明確批准gate独立保留。不改原RT歷史，無original design error證據。

## 2026-10-10 RI-004 待審候選 gate 更新

D44 explicit-owner fixed-template candidate／真隔離驗證／review-export切片已VERIFIED；整卡PARTIAL。獨立review的catalog-order alternative遺漏（MINOR_FIX／IMPLEMENTATION_BUG）與service/UI失敗碼不一致（MINOR_FIX／MISSING_INTEGRATION）均屬本卡尚未啟用的局部實作缺陷，已root-cause local repair／反例與actual payload follow-up PASS，不新增重複待辦或修改RT歷史。[證據](../evidence/RI-004-2026-10-10/REPORT.md)。

88新cases、完整1,127PASS、真Chrome23checks與exact6source回退解除這個prepare/review切片的缺口；**BLOCKED_BY_SKILL_INTEGRATION**仍限實際worker boundary／security review／package-bound explicit批准／install-enable-revoke／catalog接入。不能以patch profile PASS批准generated worker。FIX-002／005／006保持PARTIAL，FIX-007–010限定VERIFIED與RI-005 release/資料保留gate不變。没有新增original design error，不建立ARCHITECTURE_CORRECTION。

## 2026-10-10 RI-003 接入 gate 更新

原 same-user patch copy 的 untrusted 接入缺口，現由 RI-003 明確 owner／Linux single-process profile 局部驗收完成；整體仍 PARTIAL。**不是把舊 copy API 放行**，而是新增固定 source-only／OS filter profile，unsupported拒絕，不允許 host fallback。[驗收與局部反例](../evidence/RI-003-2026-10-10/REPORT.md)。

RI-003 尚未啟用候選的 IPC creation／取消清理／late SIGINT 缺陷分類為 REQUIRED_FIX（IMPLEMENTATION_BUG／TEST_GAP），已在同卡先 RED→最小局部修正→PASS／independent follow-up。沒有證據指向原 RT task 或正式產品 regression；不另造重複 FIX、不改 RT DONE 歷史。General multi-process/deps、enabled worker、review/explicit enable與release/data-preserving rollback gates仍保留。FIX-010 VERIFIED；FIX-002／005／006保持 PARTIAL。

## 2026-10-09 Runtime Intelligence 稽核／修復定義

2026-10-10現況：**FIX-007／008／009已在各自限定範圍修復VERIFIED；自主接入／發布gates仍保留**。下方2026-10-09反例與40測試為原review證據；不能當最新修復驗收。依 [現況稽核](CURRENT_ARCHITECTURE_AUDIT.md)、[能力矩陣](CAPABILITY_MATRIX.md)、[合成反例報告](../evidence/RI-architecture-2026-10-09/REPORT.md) 與 [原始結果](../evidence/RI-architecture-2026-10-09/safety-probe.json)。本輪相關現有測試 40 PASS／9.49s 不覆蓋這三個反例，不能當安全修復已通過。Source Task 為原 T22／T31／T32 與本輪 review；沒有證據把問題歸因某個 RT，因此沿 FIX 編號，不改既有 RT 的 DONE 歷史。

| Issue | Classification | Source | Evidence／處置 |
|---|---|---|---|
| approved skill 身分未綁 executable package | REQUIRED_FIX | IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP | `load_skill` hash 僅三個 JSON，Dispatcher 只查 id/version；合成換 plugin 碼 hash 不變且達 recording supervisor。建立 FIX-007；不是已確認 REGRESSION |
| protected file deletion 漏過 diff path 判定 | REQUIRED_FIX | IMPLEMENTATION_BUG、TEST_GAP | protected delete 加一般檔案修改，PatchVerifier 回 passed、changed_paths 漏刪除路徑。建立 FIX-008；rename 等未驗格式需保守拒絕，不猜都已遭利用 |
| release 相容欄位沒有納入簽署 | REQUIRED_FIX | IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP | 原 schema1–2 不相容；只改 max_schema=8、不重簽仍 activated。建立 FIX-009；沒有已確認真部署事故 |
| same-user patch copy 不等於 OS sandbox | DEFER（接入前硬 gate） | MISSING_INTEGRATION、TEST_GAP | 合成 candidate 可寫 copy 外 temporary marker；本次不建立大型 sandbox 修復。由 RI isolated-check 小卡驗實際檔案／env／network／process／resource 邊界；未通過不得執行不可信候選 checks |
| active pointer 與 launcher 未接、資料保留式 rollback 尚未成立 | DEFER（發布前硬 gate） | MISSING_INTEGRATION、TEST_GAP | ReleaseManager 的 active.json 未由 launcher 消費；whole-DB rollback 會回復較新寫入之前的內容。由 RI release 小卡分別處理 launcher／停止 writer／資料策略，不混入 FIX-009 |
| 9/30 文件稱 native未接、summary missing、Rust未接／無背景owner | DOCUMENTATION_ONLY（本輪已更正） | DOCUMENTATION_DRIFT | 10/09 audit／matrix 指出實際 caller 與驗證限制；保留歷史。沒有理由重做已存在 implementation |

以上是局部實作／介面與接入 gate，不足以推翻 Runtime Evolution 的 ports、proposal、permission、single-owner 設計；**不建立 ARCHITECTURE_CORRECTION.md**。既有 FULL mode 不解開 generated-code／patchcheck／release 的人工與隔離 gate。三卡按最小根因獨立驗收，不得為其中一個缺陷重寫 subsystem。

| 受影響範圍 | Gate | 仍可繼續 |
|---|---|---|
| Generated skill activation／將已安裝 skill 接到可執行產品 catalog | FIX-007局部已VERIFIED；BLOCKED_BY_SKILL_INTEGRATION：RI sandbox／review／explicit enable gates | 開發期 source index、唯讀 catalog inventory、disabled candidate spec、既有可信測試 |
| 自動 patch checks／protected-path 驗證 | FIX-008局部gate已解除；untrusted checks仍受RI OS isolation與可信check allowlist gate | source analysis／proposal／人工審閱、可信合成 fixtures；不能把 copy 當 sandbox |
| Release promotion／自動發布 | FIX-009局部已VERIFIED；BLOCKED_BY_RELEASE_INTEGRATION：launcher／人工批准／data-preserving rollback gates | 獨立 release fixtures、相容性設計；不對運行中服務部署或還原 DB |

## 2026-10-08 最新實作狀態

使用者已授權「照著這三個文件開始實作，記得驗收很重要」。FIX-003、FIX-004 現 **DONE / VERIFIED**，證據見 [003 REPORT](../evidence/FIX-003-2026-10-07/REPORT.md)、[004 REPORT](../evidence/FIX-004-2026-10-07/REPORT.md)。004含真瀏覽器306.581秒、最終整體554 PASS／5 real_provider未選、隔離回退；只解除session lifecycle gate。FIX-005 A／B已實作：原聲線基線功能已驗，速度不合格；CUDA SDPA有實測收益，最後版本真機功能已驗；671項回歸、精確回退與證據見 [005 REPORT](../evidence/FIX-005-2026-10-07/REPORT.md)，速度／人工語意仍未達標。FIX-002／005／006尚未完成，桌寵／自主技能仍須各自真實驗收。已載入本機candidate並驗健康／auth plan；沒有將產品gates一起解除或宣稱全產品發布。

## 2026-10-07 規劃快照（實作狀態以上節與各卡為準）

本輪依「只規劃就好」，新增 **FIX-002：瀏覽器失敗原因與搜尋驗證**，以及 **FIX-003–006：文字完整性、session 續期、語音長文與延遲、自身故障情境**，均為 PLANNED，未執行修復／測試。既有三張 FIX 的 DONE 歷史保留。近期對話／語音的匿名檢視與證據界限見 [CONVERSATION_VOICE_REVIEW](CONVERSATION_VOICE_REVIEW.md)。編號不代表排名，不將既有 RT 的 DONE 自動改為失敗。

使用者回報的 Bing ScopeViolation 根因尚未確認，不能只憑畫面上的 Markdown 字串判定為 URL bug，也不能直接歸因 RT-012。

桌寵、主動行為、安全技能成長的整合規劃見 [COMPANION_EVOLUTION_PLAN](COMPANION_EVOLUTION_PLAN.md)。自動網路研究的產品 promotion 為 **BLOCKED_BY_FIX：FIX-002＋必要的搜尋行為修復與端到端驗收**；FIX-002 的診斷改善單獨完成不代表搜尋已恢復。桌寵外殼與本機唯讀任務追蹤可繼續各自規劃。原 RT-012 DONE 保留，未重跑原 acceptance，無證據將整卡改為 FAILED_VERIFICATION。

下方 10-04 的日期／PLANNED／DEFER 表格為當時歷史快照，最新 RT 交付狀態以 RUNTIME_EVOLUTION_ROADMAP 的 10-06 交付區與 STATUS 為準。

日期：2026-10-04（Asia/Taipei）。三張 REQUIRED_FIX 已逐張完成：FIX-001、RT-003-FIX-01、RT-005-FIX-01 均 DONE。修前 Problem／Evidence／Actual／Root Cause 與原 review 保留作歷史；當前修復、驗收、限制與回滾見各卡 Status 連結。編號用於識別，不表示排名。沒有開始後續 RT。

## 判讀依據

- [Architecture Review](ARCHITECTURE_REVIEW.md) AR-01–05。
- [可重現 probe](verification/architecture_review_2026-10-03/probe.py)、[觀測結果](verification/architecture_review_2026-10-03/probe-result.json)、[source digests](verification/architecture_review_2026-10-03/source-digests.json)。probe exit 0 表示缺陷重現，不能算修復通過。
- [RT-008 independent verification](verification/RT008_2026-10-03/REPORT.md) §7 已指出 call-ID 問題在 RT-008 前存在。
- [SPEC](RUNTIME_EVOLUTION_SPEC.md) Run 與訊息契約、Execution、Provider；[Compatibility plan](COMPATIBILITY_PLAN.md)；`docs/CONTRACTS.md` 的 RT-005/008 限定範圍。
- 前次 review 實跑 285 passed／5 skipped、ruff／mypy PASS，但 probe 仍失敗於產品不變條件。最初修復定義輪僅重查 evidence、code 與 source digest；當時未重跑測試。後續三張 FIX 的實跑結果各見 completion report。

## 問題分類與來源

來源可複選；TEST_GAP 表示既有套件沒有涵蓋反例，不等同根因。沒有證據支持把所有問題稱為 REGRESSION。

| Issue | 分類 | 來源 | Evidence／判定與處置 |
|---|---|---|---|
| AR-01 跨 run tool identity 衝突 | REQUIRED_FIX | BAD_INTERFACE、IMPLEMENTATION_BUG、ARCHITECTURE_DRIFT、TEST_GAP | `_seen_calls[session_id]`、011 unique key 與 013 run key 不一致；probe 第二 run 被拒、restart IntegrityError。建立 RT-003-FIX-01；RT-008 匹配修補包含在同卡，不拆成互相不完整的修復 |
| AR-02 arguments-only handler 不受取消等待管理 | REQUIRED_FIX | MISSING_INTEGRATION、BAD_INTERFACE、TEST_GAP | orchestrator 只有 contextual task 進 `_active`；probe CANCELLED 後仍有 list effect。建立 RT-005-FIX-01；原卡已明列 browser 限制，不能誤稱原 argv acceptance 失敗 |
| AR-03 provider FAILED 後仍 dispatch／最後 completed | REQUIRED_FIX | IMPLEMENTATION_BUG、TEST_GAP | Core 保留 partial calls，controller 先檢查 calls；HEAD 已有相同邏輯。建立 FIX-001，不能歸因 RT-009 尚未實作或 RT-008 regression |
| AR-04 terminal RAM retention | TECH_DEBT | ARCHITECTURE_DRIFT、TEST_GAP | source 無 eviction；兩 terminal runs 後仍有 2 contexts／2 terminated IDs。未量測長時 RSS 或 OOM；不立刻造 cache/state-manager 修復卡。AR-01 的去重 scope 修補可局部清理該 map，不能順帶全面 retention 重構 |
| AR-05 repositories 互讀／mutable journal_hook | TECH_DEBT | BAD_INTERFACE、ARCHITECTURE_DRIFT | `journal_owner`、`reconcile`、`_ensure_core` hook assignment；未證明 single-owner 下失效。精確 owner matching 已併 AR-01；不另建 repository framework task |
| 過時 DOCUMENT_STATUS／舊 baseline 時點不清 | DOCUMENTATION_ONLY | DOCUMENTATION_DRIFT | DOCUMENT_STATUS 仍稱全部 PLANNED，baseline 為 09-30。由本 register／roadmap 明示本次狀態；歷史測量保留，後續可整理索引，不建立立即 code fix |
| RT-010 重做 run recovery、RT-011 摘要及 RT-013/015 擴張建議 | DEFER | ROADMAP_ERROR（潛在重複 scope） | RT-008 已有 run journal/readback，尚無 session hydration；無證據取消 RT-010 整卡。只收斂卡內 scope，不建立新 abstraction 修復卡 |
| 真 provider／部署 rollback／soak／commit-failure coverage 缺口 | DEFER | TEST_GAP | evidence 明列未驗；不能當成已發生 production bug。保留 promotion／release gates，受本次修改影響的 failure injection 併入各 FIX 驗收 |
| operational test 曾寫 default DB | DEFER | IMPLEMENTATION_BUG、TEST_GAP（歷史已修正） | RT-008 README 記錄事故，測試已隔離且 launcher 回歸通過。事故前後私人資料完整性仍未獨立驗證；不重修已修測試，不自行 downgrade DB |
| 「新增 global singleton／import-time cycle／雙 ledger 必須合併」 | FALSE_POSITIVE | ARCHITECTURE_DRIFT（已排除的指控） | 實際為 instance maps；Gateway local import 相依既有；agent_steps 與 journal 用途不同。無立即修復 task |

無 CRITICAL_FIX：目前反例足以證明 HIGH 的行為違反，但沒有已確認的跨使用者破壞、資料毀損或不可回復事故可支持 CRITICAL。也不為湊分類建立 MINOR_FIX。

## Architecture error 判定

**本輪不建立 ARCHITECTURE_CORRECTION.md。**SPEC 已要求每 run ownership、取消傳遞及有界 cleanup、輸出後 provider failure 停止；反例沒有推翻這些決策。舊 011 session-wide unique constraint 是與新 run 模型不一致的既有介面，並非證據顯示 Runtime Evolution 的 run 模型應被取消。arguments-only 相容可以透過既有 adapter 包裝，不必放棄相容設計。

若 RT-003-FIX-01 的局部映射／binding 無法同時保留資料與 pairing，先保存最小反例，才提出窄幅 ARCHITECTURE_CORRECTION，內容須含 original decision、invalidating evidence、impact、smallest correction、affected/valid/cancel-or-modify tasks、compatibility/migration impact。不能直接重寫 proposal subsystem，亦不能把未知的設計選擇寫成已確認 root cause。

## 共用施工與回滾規則

每次只做一張 FIX。先核對 dirty tree 與本卡 source，保存精確修改範圍；先把對應反例改成驗證 expected behavior 的正式測試，確認失敗，再做局部修補。不得用現在 probe 的 defect assertions 作為 acceptance。跨契約修補先更新 DECISIONS／CONTRACTS 與測試。

共用禁止修改：既有 migrations 001–013、公開必填欄位／enum、full authorization defaults、argument hash／grant 語義、Rust wire／driver、device／firmware、identity／affect／relationship 算法、memory facts schema、Qwen worker／reference／模型、Live2D assets、依賴／lockfile、原 T 任務歷史。每卡例外必須明列；本 register 沒有授權功能擴張。

測試一律 temporary data、合成資料；不得對 `.siro-data` 或運行中服務做 migration／rollback 測試。相關 suite 加 ruff/mypy；跨身份／持久格式交界需完整 Python gate。skip 不算 PASS。

回滾先停止接收受影響的新工作、fence 新 dispatch、清理可取消 owned jobs，保留不能確認的 unknown 及 journal。只撤本卡範圍，不 reset dirty tree。**source reverse check 不是部署回滾成功證據**。schema/readers 已有新資料時不得自行退版或還原舊備份；保留相容 reader/guard，必要時停止工具 dispatch，文字入口是否可用另驗。保留缺陷的舊 binary 不能自動成為安全回退目標。

---

## RT-003-FIX-01 — 修正跨 run tool identity 與 proposal ownership

- Classification：REQUIRED_FIX
- Status：DONE（2026-10-04；docs/evidence/RT-003-FIX-01/REPORT.md）
- Sources：BAD_INTERFACE、IMPLEMENTATION_BUG、ARCHITECTURE_DRIFT、TEST_GAP
- Dependencies：現有 RT-002/007/008 實作作為基線；不等待 RT-010。

### Source Task

RT-003 的 session-wide dedup；Architecture Review AR-01；RT-008 independent verification §7。011 約束早於 RT-003；RT-008 recovery matching 是本卡必須一起保持正確的受影響 caller。

### Severity

HIGH。

### Problem

合法的新 run 因舊 run 用過同一 provider call ID 而被拒；重啟後轉為未處理 DB exception。若只清 RAM 去重，持久 constraint 與 owner matching 仍錯。

### Evidence

- `src/siro/services/presentation/integrated.py:645`：`_seen_calls.setdefault(session_id, set())`；callback 約 480 行亦依當前 session run＋call ID，需驗 exact proposal ownership。
- `src/siro/persistence/migrations/011_tool_proposals.sql:14`：`UNIQUE(session_id, call_id)`；013 `PRIMARY KEY(run_id, call_id)`。
- `src/siro/services/tools/orchestrator.py:222` journal_owner、`services/agent/runs.py:reconcile`：跨表匹配 session＋call ID。
- probe keys `call_id_reused_next_run`、`call_id_reused_after_restart`：`duplicate_or_excess_tool_calls`／`UNIQUE constraint failed`。失敗在真 SQLite/controller 路徑，不是 provider network 推測。

### Expected Behavior

不同 run 可合法使用相同 provider call ID；同一 run 的重複 call 不再次 dispatch。tool result 配對原 provider ID，舊 proposal／late callback 永遠不能被視為新 run 的結果。重啟不重播 unknown。

### Actual Behavior

同 session 第二 run 被拒；重啟清空 `_seen_calls` 後，proposal INSERT 仍撞 unique key。API/模型沒有跨 session lifetime 永不重用 call ID 的契約。

### Root Cause

已確認：provider-local identity 被當成 session-wide persistent operation identity；RAM dedup 與 DB 約束重複延長其 lifetime。journal／callback owner lookup 缺少精確 run/proposal 關係，單純更改 dedup key 不能完整修根因。

### Scope

只修 candidate 的 call identity 映射、proposal binding、dedup、callback 與 recovery matching；保留 legacy rows/API。不得改 native model transport、另造 run repository、加入 resume API。

### Files expected to change

- `src/siro/services/presentation/integrated.py`
- `src/siro/services/tools/orchestrator.py`
- `src/siro/services/agent/runs.py`
- `tests/integration/test_agent_batches.py`、`test_run_journal.py`、`test_tool_orchestrator.py`、`test_integrated_companion.py`
- 若正式 HTTP approval 需呈現既有 provider ID：僅 `gateway.py` 的 proposal serialization/approval caller 與對應測試；不可改 main 組裝。
- DECISIONS、CONTRACTS、STATUS、本 register／roadmap、獨立 FIX evidence。
- 新 additive migration **不是預設修改**；僅局部映射無法保留全部相容性且有反例時，先提出精確資料設計修正與 upgrade/rollback tests，不修改 011/013。

### Files that MUST NOT change

共用禁止區全部適用；另外不得改 `ports/models.py` public pairing 語義、provider adapters、`execution.py` 或 TTS。不得清空舊 proposals／journal 以通過測試。

### Compatibility requirements

provider request/response 保留原 call ID；既有 proposal_id approval URL、public call_id 意義與 arguments hash 不變。舊 rows 可讀、舊 pending candidate proposals 仍被 fence；新 binary 的 legacy 模式仍不能執行 recovered candidate proposal。不能靠要求 provider 產全球唯一 ID 解決。

### Proposed repair

1. 先固定跨 run／restart／舊 callback 三類反例，確認哪些 caller 使用 storage ID 或 provider ID。
2. 在既有 proposal 邊界使用 run-scoped internal identity，dedup 以 run 為單位；優先用現有 run_journal_calls 的 proposal_id 關聯保存原 provider ID，避免 schema 變更。這是候選修法，須先驗證 public serialization 與舊 reader。
3. proposal 建立與 journal binding 必須 atomic，或提供可證明不誤配的 crash-gap recovery；不得取消原 proposal-insert→bind crash 測試來迴避。
4. dispatch、callback、reconcile 優先精確 proposal/run binding；legacy fallback 只能處理明確 legacy rows，不能遇到歧義就任取一筆。
5. 只清理本卡 dedup state；不順帶解 AR-04 全域 retention。

### Tests required

同 session 兩個獨立 run 重用 `call-0` 各執行一次；重啟後再用相同 ID 正常；同 run／batch 重複 ID 零重複 dispatch；A/B session 隔離；新 run 活躍時注入舊 proposal callback 不改新 journal/UI；manual approve/deny；proposal 建立／binding 前後 crash，恢復零重播；新舊 row 混合與 unknown readback。

### Regression tests

agent_batches、agent_runs、run_journal、tool_orchestrator、tool_catalog、integrated_companion、gateway_terminal_fence、gateway_main、model adapter contracts；sqlite_store／upgrade/old-reader。跨持久 ownership 修改後跑完整 Python suite。

### Acceptance criteria

上述 counterexample tests 修前 FAIL／修後 PASS；三個合法 run（含一次 restart）各一次 effect、零 IntegrityError；同 run duplicate 零額外 effect；所有 observations 有且只有一個正確 owner；舊 approval／late callback／crash 零重播或新 run 污染；HTTP 與 provider payload 相容；013 checksum 不變。

### Rollback method

先在 temporary DB 演練。未產生新格式 rows 時可撤本卡 source；已有映射 rows 時保留可讀映射與防重播 guard，停止 candidate 新 dispatch，再以經驗證的相容版本／legacy profile接新 run。不能因無新 migration 就假定舊 binary 理解新 storage ID；需實測舊 reader、approval fencing 與 readback。若必須保留少量 compatibility code 才安全，回滾包須明列，禁止刪 rows／降版 DB。

### Risk

HIGH：最容易修掉碰撞卻破壞 pairing、manual approval、crash-gap ownership。以一張有界跨 caller 修補完成，不拆成只改 `_seen_calls` 的症狀修復。不需改架構；局部映射不可行才提出窄設計修正。

---

## RT-005-FIX-01 — 納管 candidate arguments-only handler 的取消

- Classification：REQUIRED_FIX
- Status：DONE（2026-10-04；docs/evidence/RT-005-FIX-01/REPORT.md）
- Sources：MISSING_INTEGRATION、BAD_INTERFACE、TEST_GAP
- Dependencies：現有 RT-005/007/008；不等待持續 browser session 功能。

### Source Task

Architecture Review AR-02；RT-005 optional contextual executor 與 RT-007 descriptor 接合。RT-005 的 owned argv PASS 保留，此卡補較廣 runtime lifecycle 缺口。

### Severity

HIGH。

### Problem

arguments-only handler 未被 `_active` 管理，cancel_run 能先結束並送 terminal，而 handler 仍可繼續執行。

### Evidence

`orchestrator.py:343–356,442–469`；`gateway.py:1245–1257` 只有 computer.execute 設 contextual executor。probe `arguments_only_executor_cancel` 顯示 terminal_before_handler_finished=true，之後有 `after-cancel` effect。合成 handler 證明 ownership 缺口；真 browser/GUI 殘留或其精確 cleanup failure 為 **UNKNOWN — NEEDS INVESTIGATION**，不能冒稱已重現。

### Expected Behavior

candidate 的每個 foreground handler 都有 owner、取消傳遞及有界 cleanup。已確認 detach 不因 run cancel 被殺；無法證明外部效果停止時保存 unknown／cleanup failure，不回報「全部停止」。terminal 後無 late UI、無新 dispatch。

### Actual Behavior

arguments-only handler 只被直接 await；cancel token 沒有 task bridge，run 不等待該 handler。journal 的 unknown 不會自動停止執行。

### Root Cause

已確認：task registration／取消等待位於 contextual branch，而非共同 dispatch boundary；legacy callable 相容入口沒有 candidate ownership wrapper。不是 token 或 argv process-group cleanup 實作失效。

### Scope

在既有 orchestrator 納管 candidate arguments-only invocation；只補目前 browser/application caller 必需的取消清理與 lifetime 描述。不得加入 persistent browser、通用 supervisor、程序掃描或管理其他使用者程序。

### Files expected to change

- `src/siro/services/tools/orchestrator.py`
- `src/siro/services/presentation/gateway.py` 的既有 browser/application handlers（僅必要 cleanup／detach boundary）
- `src/siro/services/presentation/integrated.py`（僅必要 cleanup failure → terminal 映射）
- `src/siro/adapters/browser.py` 僅當 fixture 證明 context-manager close 在取消時不完整；先重現再改。
- `tests/integration/test_execution_lifecycle.py`、`test_tool_orchestrator.py`、`test_gateway_main.py`、`test_gateway_terminal_fence.py`、`test_run_journal.py`；必要 browser cleanup regression。
- DECISIONS、CONTRACTS、STATUS、register／roadmap、FIX evidence。

### Files that MUST NOT change

共用禁止區；額外固定 `execution.py` 既有 argv output cap、PGID cleanup、ack detach 語義；無資料 schema 需求。不得將所有 tool handler 強制改成新公開 signature。

### Compatibility requirements

舊 executor(arguments) constructor／callable 繼續可用；legacy behavior 保留。candidate 新增 task ownership 不擴大 OS 授權；full mode、switch/readiness/arguments hash gate 不變。保留 journal dispatch-before-effect、未知結果不重試、writer fence。

### Proposed repair

1. 先加入有 Event barrier 的 arguments-only cancellation test；把 task ownership 移到 candidate 共用 invocation 邊界，contextual handler 的 token/cleanup 行為保持。
2. arguments-only callable 由既有 adapter/task wrapper 接收取消，不向舊 callable 增加必要參數。取消先 fence，再要求 owned task 停止並等待有界 cleanup；不把 asyncio cancellation 當成 OS effect 已回收的證據。
3. 逐一驗目前 browser context-manager、application launcher 在取消前／spawn 中／ack 前後的 cleanup。只處理本次 owned handles；ack 後保持既有 user-managed lifetime。
4. 超過既有 cleanup 上界（run 4.75 秒、外部可見不超過 5 秒）使用既有 failed/error／unknown 表達；不再無限 await、不重派，保留必要 handle／late-output fence。若 backend 無法證明停止，明確保留限制。

### Tests required

自動與手動 approval 的 arguments-only handler：queued cancel 零進入；running cancel 執行 finally 且 barrier 後零 effect；同時 completion/cancel；拒絕或延遲取消時在 5 秒內明報 cleanup failure、unknown，不假稱外部停止；shutdown cleanup；browser close 與 owned launcher fixture；ack detach 不誤殺；session B handler 不受 A cancel 影響。

### Regression tests

execution_lifecycle、bounded_execution、agent_batches、tool_catalog、tool_orchestrator、gateway/main/terminal_fence、run_journal。相鄰 argv parent-child／100 races／late UI 測試保留。真 browser 只跑隔離本機 fixture；不能用 mock 宣稱 GUI cleanup 全完成。

### Acceptance criteria

review cooperative handler 反例修前 FAIL／修後 PASS；cancel terminal 前已完成受控 handler cleanup；測不到停止的 case 在 5 秒內明確 failure/unknown；零新 dispatch、零 late UI、零跨 session 誤取消；contextual argv、manual approval、ack detach 與 restart unknown 行為不退步。外部 cleanup 未驗者明列，不能擴大 DONE 語義。

### Rollback method

停止 candidate 新工具、fence／清理已 owned jobs，不能把未完成 task 移交舊 wrapper。資料格式不變，保留 journal/unknown 後撤本卡 local patch；回退後 arguments-only cancellation 缺口重新存在，故該路徑不得重新開放 candidate promotion。temporary fixture 演練停止、回退、啟動及無重播，禁止廣泛 pkill。

### Risk

HIGH：取消過早釋放 owner、外部程序未停卻回成功、誤殺 detach，以及 shared-task 取消污染別的 session。先 wrapper 與現有 caller 局部修補；未證明 backend defect 不改 driver。

---

## FIX-001 — 失敗／取消 generation 不得接受新工具 batch

- Classification：REQUIRED_FIX
- Status：DONE（2026-10-04；修復與驗證見 docs/evidence/FIX-001/REPORT.md）
- Sources：IMPLEMENTATION_BUG、TEST_GAP
- Dependencies：現有 RT-002/003/008；不等待 RT-009。

### Source Task

Architecture Review AR-03。dispatch 優先順序在 HEAD 已存在；RT-003 未消除此舊缺陷，RT-009 尚未實作，所以採獨立 FIX 編號。

### Severity

HIGH。

### Problem

provider 在 tool intent 後失敗，controller 仍執行該 generation 的工具，再用下一 round 把整個 run 標 completed。

### Evidence

`core/conversation.py:157–175` exception → FAILED，但 TurnResult 帶已有 tool_calls；`presentation/integrated.py:385,601` 先判斷 calls；`core/companion.py` 將結果追加 message history。probe `provider_failure_after_tool_intent`：ConnectionError 後 effects=1、final_state=completed。HEAD 相同順序支持「既有 bug」，不支持新 regression 歸因。

### Expected Behavior

只有成功 generation 可提交待執行 batch。FAILED／CANCELLED 必須收斂至一致 terminal，零新 dispatch，保留可辨識失敗及已發生工具結果；不得新開 round 掩蓋錯誤。

### Actual Behavior

`result.tool_calls` 的存在優先於 result.state/error；收到 partial tool stream 後的失敗被當正常工具請求。

### Root Cause

已確認：orchestration 缺少 generation state 的 accepted-batch gate。Core 保留 partial observations 本身不是錯誤；只丟掉 exception 或讓 provider 不回 tool calls 會掩蓋根因。

### Scope

修第一 round／continuation 的相同 gate，以及失敗 partial messages 的 terminal journal 相容處理。candidate 與 legacy 都不應 dispatch failed generation；正常成功路徑不變。不新增 retry、fallback 或新 error taxonomy。

### Files expected to change

- `src/siro/services/presentation/integrated.py`
- `src/siro/core/companion.py` 僅當需防止 failed partial batch 被當 accepted history；不得改 memory assembly 邏輯。
- `src/siro/services/agent/runs.py` 僅當既有 terminal API 無法保存明確 not_dispatched 配對；先測局部 caller 處理是否已足夠，不預設變更 schema。
- `tests/integration/test_agent_batches.py`、`test_integrated_companion.py`、`test_run_journal.py`、`test_conversation.py`；DECISIONS/CONTRACTS、STATUS、register／roadmap、FIX evidence。

### Files that MUST NOT change

共用禁止區；另外 provider adapters／FailoverModel、LanguageModel public port、ConversationEngine generation/stream transport、execution backend、catalog、配置及 DB migrations 不改。RT-009 新功能不混入本卡。

### Compatibility requirements

成功 tool loop、prompt-only caller、manual approval、full authorization 與原 terminal enum 保留。failed generation 的 dispatch 停止是明確 bug correction，不用相容性理由保留錯誤。既有已完成 batch 的 observation 不抹除；partial text 不被重送或假裝成功。

### Proposed repair

1. 把兩個 caller 的 state/error 裁決置於新 batch dispatch 前，沿用現有 terminal path；不更動 provider transport。
2. 明確區分 partial tool intent 與 accepted batch：零 proposal dispatch，terminal journal 仍可讀。不能把未登記 calls 直接交 `_paired_messages` 導致 unregistered-call error；優先沿用現有 checkpoint/finish 契約保存 not_dispatched 配對，或在既有 final/error 中保存 failed intent、排除 canonical accepted history，並以契約測試固定選擇。
3. error/state 保留、一次 terminal、禁止下一 round；continuation 先前已 committed 的正常 observations 保留，不 rollback 真實效果。

### Tests required

第一 round 及 continuation：tool_request 後 ConnectionError／timeout、partial text＋tool 後失敗、cancellation 保留 partial calls；均零新 dispatch／零自動下一 round、一次 failed/cancelled terminal。正常成功 tool batch 作對照。terminal journal readback／restart 不因 unregistered call 崩潰，無效 intent 不重播。legacy/candidate 雙 profile。

### Regression tests

conversation、integrated_companion、agent_batches、run_journal、gateway_terminal_fence、model adapter contracts；既有 partial streaming／取消／唯一 terminal／manual approve/deny cases。未改 fallback，只保留現有 contract，新的 retry 驗收仍屬 RT-009。

### Acceptance criteria

probe 同情境修前 effect=1/completed，修後 effect=0/failed 且保留 ConnectionError；取消情境保持 cancelled；初次失敗模型只呼叫一次、continuation 失敗後不再多一 round；零 orphan pairing、零額外 terminal；已完成 observations 不遺失；兩 profile 正常工具、文字與取消 regression 通過。

### Rollback method

無新 schema；排空／停止受影響工作並保留 journal，撤本卡精確 caller patch，不能重送失敗 batch。若回退版本仍會執行 failed intents，停用工具 dispatch，RT-009 維持 BLOCKED_BY_FIX；不能將恢復危險行為當回滾成功。以 temporary fixtures 驗 reader、terminal 與 no-replay。

### Risk

MEDIUM（修補變更風險；問題 severity HIGH）：只加 state 判斷可能讓 partial history 引發另一個 journal exception，或遺失前一批已完成結果。因此 accepted history／readback 測試與本卡不可分；不需重構整個 loop。

## Roadmap gates 與狀態裁決

| Task | 新狀態／gate | 理由與解除条件 |
|---|---|---|
| RT-003 | DONE / VERIFIED | RT-003-FIX-01 修前反例與全部原 acceptance 回歸通過 |
| RT-005 | DONE（owned argv＋受控 candidate arguments-only lifecycle） | RT-005-FIX-01 通過；不外推任意 GUI/escaped processes |
| RT-008 | DONE（local readback 範圍） | exact ownership/crash/no-replay 回歸保留 |
| RT-009 | PLANNED | FIX-001 gate 已解除，未開始 retry/fallback |
| RT-010 | PLANNED | identity gate 已解除，未開始 session hydration |
| RT-011 | PLANNED（budget）；summary DEFER | FIX gates 已解除；summary 仍須 RT-010 與需求驗證 |
| RT-012 | PLANNED | identity/lifecycle gates 已解除，未開始 persistent browser |
| RT-013 | DEFER | FIX gate 已解除；仍需 scoped caller/parity 證據 |
| RT-014 | BLOCKED（dependency RT-010） | identity FIX 已解；仍須 session hydration，不繞過來源隔離 |
| RT-015 | DEFER（另待 RT-014） | 三 FIX 已解；retention/single-owner expansion gate 保留 |

Sol 只能選 PLANNED 且依賴已滿足的 FIX；**不得跳过 BLOCKED_BY_FIX 開發新功能**。目前沒有未解 FIX；本輪完成停止，不自動開始 RT。文件補充與獨立驗證可繼續，不代表允許功能開發。

解除 gate 需 FIX evidence：修前反例、修後 desired-behavior tests、相關 regression、相容與 rollback 結果、剩餘限制，以及獨立 verification。只提交 patch 或 tests 全綠不自動解除。被 DEFER 的卡解除 FIX 後仍維持延期。AR-04/05 不轉成立即 FIX，待測得資源超限、確認單 owner 故障或新增 background owner 需求時再分類。

---

## FIX-002 — 保留可判讀的瀏覽器失敗原因並驗證搜尋路徑

- Classification：REQUIRED_FIX
- Origin：BAD_INTERFACE、TEST_GAP
- Status：**PARTIAL（2026-10-10）**。A typed診斷／B partial主頁／C teardown callback局部修復已實作與專項驗收；useful public search未通過、間歇4s cleanup根因UNKNOWN。
- Blocking scope：自動網路研究 promotion；不阻擋桌寵／本機唯讀任務追蹤的規劃。

### 2026-10-10 實作與現況

本卡依D37先完成A/B真Chrome修前重現，再保留scope／hash／FAILED／native與legacy相容做6檔局部修復。新傳遞契約21PASS，UI12PASS／真Chrome18情境，主frame／redirect／partial／session origin reset／取消均覆蓋。新owned-teardown listener錯誤真Chrome修前2FAIL／修後2PASS；只增加driver closing旗標與關閉期間Error消化，沒有提前unroute、擴origin或延長deadline。最後完整回歸結果見[REPORT](../evidence/FIX-002-2026-10-10/REPORT.md)。

真configured provider閉環：Bing僅頁首；DuckDuckGo為human challenge，都沒有搜尋結果。沒有bypass；DDG模型的不當繞驗證建議保留為FIX-006負向語意evidence。自動網路研究仍**BLOCKED_BY_FIX：FIX-002**。原私人事件根因仍UNKNOWN。

新增blocker：公網cleanup兩次4.001s失敗、一次自有Playwright child殘留；後續instrumented current／before正常，最終guard版無模型cleanup0.069s、零殘留。這些成功不足以證明間歇問題已消失，具體阻塞步驟／是否regression仍UNKNOWN。不改正式4s限制、不殺非自有程序；保留完整修前失敗與PID/start-time evidence。沒有正式deployment／8026重啟／DB restore，原RT DONE歷史保留。

### Source Task

使用者 2026-10-07 的真實產品回報；工具畫面為「開啟並讀取頁面」，目標顯示 Markdown Bing 查詢連結，結果 ScopeViolation。相關能力為 T24、RT-007 catalog、RT-012 persistent browser；尚無引入 commit／runtime trace 證據可指定 RT-XXX-FIX，使用獨立 FIX-002。不判定為已確認 REGRESSION。

### Severity

MEDIUM。使用者查詢受阻、模型不能分辨失敗原因；沒有已確認越權／資料外洩或毀損證據。

### Problem

瀏覽器 driver 提供的拒絕情境在 orchestrator 被縮成 exception 類名，模型與 UI 只見 ScopeViolation，無法分辨主 URL 越界、轉址越界、子資源被擋或參數問題。現有本機單 origin 驗收不足以證明公共搜尋頁面可讀。

### Evidence

- 使用者畫面顯示的 url 為 `[https://www.bing.com/search?q=今天+天氣](https://www.bing.com/search?q=今天+天氣)`；這是回報內容，不是已取得的 raw provider arguments／wire trace。本輪未讀私人 run／聊天紀錄。
- [orchestrator.py](../../src/siro/services/tools/orchestrator.py) 的 DEFAULT_MODEL_TOOLS 使用 browser.navigate+read；_valid_arguments 的 uri 檢查要求 http／https＋netloc，ToolCatalog.require 在 proposal 前驗參數。如果 raw arguments 確為整段 Markdown，candidate 應先回 ValueError，不能因此推論實際 ScopeViolation 根因已確認。
- [browser_session.py](../../src/siro/services/tools/browser_session.py) 的 navigate 從 URL 建立單一允許 origin，並使用既有 ScopedBrowserDriver。
- 修前[browser.py snapshot](../evidence/FIX-002-2026-10-10/before/src/siro/adapters/browser.py) 的 _route_request 對任何越界請求設 _blocked_url；navigate 隨後拋 ScopeViolation 並 replace page。這包含圖片／script 等子資源，不只主 frame；屬於已確認的 strict scope 行為，尚未證明是當次 Bing 失敗原因。
- 修前orchestrator execute 的 except Exception 僅 journal／持久化 type(error).__name__；[integrated.py](../../src/siro/services/presentation/integrated.py) 的 continue_after_tool 將其轉回 error 字串，未保留可判讀的受限原因。
- [test_browser_driver.py](../../tests/integration/test_browser_driver.py)、[RT-012 report](../evidence/RT-012/REPORT.md) 證據為本機合成頁面／真 Chromium；未證明乾淨 Bing URL 已成功。本輪未執行測試或重放使用者查詢。

### Expected Behavior

工具只接受無展示標記的 HTTP／HTTPS URL。正常授權主頁可回傳來源、title 與內容；拒絕時模型／UI 收到穩定、脫敏的情境 reason，能清楚告知哪一階段被限制。主頁／轉址越界仍拒絕，私人 query／credentials 不進錯誤回饋或診斷 evidence。

### Actual Behavior

使用者查詢失敗，只見 ScopeViolation。可確認不同 driver 拒絕情境在現有 consumer 回路皆被抹成同一名稱；實際 raw URL、當次 runtime profile、被擋主 frame／子資源與 provider 回應未確認。

### Root Cause

**錯誤不可判讀：CONFIRMED** — orchestrator execute 丟棄 typed failure 情境，只保留 exception 類名，continuation 因此無法辨別原因。

**當次 Bing 搜尋失敗：UNKNOWN — NEEDS INVESTIGATION**。Markdown 顯示不等於 raw arguments；跨 origin 子資源整頁失敗是候選機制，不是已證實當次根因。

### Scope

先以隔離合成 fixtures 分別重現參數拒絕、主 frame／redirect 拒絕、子資源拒絕；保留已有 failure 契約的穩定名稱，補最小允許清單 reason。不要全面重做 browser 或 tool error framework。若證據需要改載入政策或 URL ingress，另定局部修復切片後施工；不在本卡憑推測更改 scope 行為。

### Files expected to change

- src/siro/services/tools/orchestrator.py：有界、脫敏 reason mapping 與 observation 傳遞。
- src/siro/adapters/browser.py：只在必要時加入 typed reason，不改允許 origin 的語義。
- src/siro/services/presentation/integrated.py／static/index.html：只有既有 observation／錯誤顯示無法帶出 reason 時，做最小 consumer 接線。
- tests/integration/test_browser_driver.py、test_tool_catalog.py、test_browser_sessions.py；受影響的 integrated companion／tool batch fixture。
- docs/CONTRACTS.md、DECISIONS.md（若跨 observation 契約）、STATUS.md 與本卡 evidence。

### Files that MUST NOT change

Core 的 identity／memory／affect；authorization defaults、argument_hash／grant、computer.execute；Rust／device drivers；DB schema／舊 migrations；model provider transport；Live2D／音色；依賴／lockfile。既有工具名與必填參數不變。不改 browser allowlist 來掩蓋失敗。

### Compatibility requirements

保留 ScopeViolation 等既有 error 名稱、FAILED／terminal／journal 語義與 legacy callers；新增 reason 若需對外傳遞，只能是 optional、有界、固定 vocabulary，不回傳 str(exception)／完整 URL。參數 hash 仍綁定真正 dispatch 的原始參數；不在授權之後偷偷剝除 Markdown 或改 URL。catalog feature-off 不繞過 driver scope。BrowserSessions 收到已授權的明確新 navigate(B) 時，仍依原契約關閉 A driver、建立 B scope；不能把「固定 A scope 越界拒絕」誤改為禁止所有合法新目的地。

### Proposed repair

1. 用精確合成輸入走 catalog→proposal→resolve→driver→observation→continuation，記錄本輪需要的 profile／階段與固定 reason，不記私人 query。
2. 保留 malformed URL 在 proposal 前拒絕、零 browser dispatch；若確認模型確實產出 Markdown，另做最小提示／參數回饋修復，要求模型提出乾淨 URL，重新按原路徑授權，不能在 driver 寬鬆抽取任意文字中的網址。
3. 對 confirmed browser failure 加最小 typed reason，例如 invalid_url、main_origin_denied、redirect_denied、subresource_denied；由可信程式映射，不能把任意 exception 文本送模型。只處理已有情境，不新增通用抽象。
4. 若合成證據確認 public-page 需求與現有整頁失敗政策衝突，定義局部後續修復：主 URL／redirect 越界仍 fail-closed；非必要越界子資源維持阻擋，可回傳帶 partial／blocked-resources 標記的可讀主頁。需另驗 iframe／script／credentials／導向等情境，不能把主 frame 拒絕吞成成功。
5. 以合成公開查詢補真 provider→browser→來源回讀→自然回覆驗收；不得直接重放私人已保存 run。搜尋若仍失敗，保持產品 gate，不以診斷改善宣稱已修復。

### Tests required

- 精確 Markdown url 在 proposal 前拒絕、executor 呼叫數零；乾淨 HTTP／HTTPS schema 接受，錯誤 scheme／空 host 拒絕。
- 同一個固定 A scope 的 ScopedBrowserDriver：A 主頁成功、B 主頁拒絕、A→B redirect 拒絕。BrowserSessions 的獨立已授權 navigate(B) 則重建 B scope 並成功，保留原 origin reset 契約與 session 隔離。
- A 主頁含 B 圖片／script 的獨立 fixture，可辨別 subresource_denied；本卡先保留拒絕行為，行為改動另有契約與驗收。
- 跨 tool batch／native continuation 保留一個 terminal、正確 tool pairing；模型與 UI 可見受限原因。
- query 中放合成 secret／userinfo，輸出只含固定 reason，不洩漏 URL／任意例外文字；若新增 HTTP／WS 欄位驗證舊 consumer 可讀。

### Regression tests

既有 scope／redirect、session ownership、stale-screen、TTL／cap／close、取消／shutdown、argument hash 與 grant、工具關閉、feature-off／legacy、failed observation／no-replay；相關 Ruff／mypy。跨 public 契約時擴跑對應 Python integration，不以 mock 當真 provider／網站驗收。

### Acceptance criteria

- 三種拒絕情境有可重現的修前／修後 evidence；failure 不再只有不可判讀類名，且無增加允許範圍或私人資料外送。
- 精確 malformed URL 零 dispatch，主 URL／redirect 越界仍拒絕，argument binding 與取消／session invariants 不變。
- 當次回報 root cause 未證實前仍寫 UNKNOWN；明確區分診斷修復完成與搜尋功能恢復。
- 自動網路研究 gate 只在必要行為修復與實際乾淨公開查詢閉環通過後解除；不能只以本機單 origin pass 或 FIX-002 診斷 tests pass 解除。

### Rollback method

排空受影響 browser jobs，關閉 owned sessions，只撤本卡精確 patch；保留 DB／journal／已完成結果。沒有 migration，不回復舊 DB、不放寬 scope、不重播失敗查詢。若 reason consumer 不相容，回既有 error 名稱並保留自動研究 gate；source reverse check 不等於部署回退已驗。

### Risk

MEDIUM。新增錯誤細節可能洩漏 query／credentials；過度寬鬆的 partial-success 可能掩蓋主 frame／redirect 越界。以固定 reason、最小 consumer 修改與分開的載入政策驗收控制；拒絕擴張 origin allowlist 作為捷徑。

### Architecture error 判定

目前證據不推翻「受限 origin、參數綁定、前景取消」原決策，不建立 ARCHITECTURE_CORRECTION.md。若證據要求調整非必要子資源的整頁失敗政策，先記錄窄幅契約修正與相容影響，不重新設計整個瀏覽器 subsystem。

## FIX-003 — 文字生成終止原因與未完成裁決

Status：**DONE / VERIFIED（2026-10-07；限定 provider 終止／partial／UI／取消／清理）**。[修前反例、81項最終驗收、真配置模型與回退證據](../evidence/FIX-003-2026-10-07/REPORT.md)。未部署私人服務，歷史截斷根因仍未知；FIX-004／005／006 不因此解除。以下 Problem／Actual／repair 規格保留修前時點。分類：REQUIRED_FIX。來源：IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP；沒有證據確定從哪個 RT 引入，不強行歸責或改原編號。

### Source Task

2026-10-07 對話檢視 CV-01；相關 RT-002／003 的 model／terminal 契約與 RT-011 budget。原切片 DONE 保留。

### Severity

MEDIUM。

### Problem

provider 回覆未完整結束時，非空文字仍可能被標為 completed，使用者看到半句、語音也只收到半段。

### Evidence

[CONVERSATION_VOICE_REVIEW](CONVERSATION_VOICE_REVIEW.md)：至少 3 個 completed 持久 final 句中結束。[adapter](../../src/siro/adapters/models/openai_compatible.py) 不讀 finish_reason、非空 SSE EOF 也 yield finished；[Core](../../src/siro/core/conversation.py) 預設 completed；[ModelRequest](../../src/siro/ports/models.py) 預設 512 output tokens，當前 caller 未覆寫。

### Expected Behavior

區分完整正常停止、達上限、非正常中斷與取消；保留 partial，未完成不能宣告成功或執行 failed intent。正常文字／工具與 legacy provider 契約相容。

### Actual Behavior

終止資訊遺失；有非空 output 且沒有 exception 就可能完成。實際 3 個樣本的終止原因無從回查。

### Root Cause

已確認：adapter 丟棄 provider 終止原因，SSE 無有效終止的 EOF 未報錯。**實際樣本截斷根因 UNKNOWN — NEEDS INVESTIGATION**，不能宣稱全部由 512 引起。

### Scope

僅 provider 邊界的終止裁決、必要的有界 output reserve 設定、partial UI／journal 狀態與相關測試；不重寫 conversation loop。

### Files expected to change

`src/siro/adapters/models/openai_compatible.py`；`tests/contract/test_model_adapters.py`、`tests/integration/test_conversation.py`、`test_gateway_terminal_fence.py`。僅當現有 typed exception／result 無法表達時，有限修改 `ports/models.py`、`core/conversation.py` 與相應 caller；先證明必要性。必要 UI 提示限 `services/presentation/static/index.html`。文件與合成 evidence。

### Files that MUST NOT change

Identity／Memory schema、RT-011 counting／privacy 規則、工具授權／effects ledger、其他 provider 或 body／音訊引擎；私人 DB／設定。不得為本卡加一般 retry framework。

### Compatibility requirements

HTTP／WS terminal enum、call pairing、一次 terminal、取消與既有正常 stop／tool_calls 保留。終止規則依 adapter／profile，不要求其他合法 provider 一律送 OpenAI SSE marker。不能無條件拒絕所有省略 finish_reason 的舊 provider，需固定其有效完成契約。

### Proposed repair

先用 fixtures 重現 length、stop、tool_calls、非正常 EOF／斷線；優先在 adapter 以現有錯誤路徑拒絕未完成。保留已收到文字與原因；只有必要時補 optional typed metadata。再根據合成樣本調小範圍 output reserve／簡潔回覆設定，最終仍通過 native budget。禁止標點猜測完成、盲目加大上限或重送含工具 run。

### Tests required

stream／non-stream 正常停止、length／filter、非空 EOF、usage-only／空 output、正常 tool_calls、partial tool＋失敗／取消；未完成零新 dispatch。驗 partial readback 與 UI 未完成提示，不能把舊 assistant 當本輪回覆。

### Regression tests

model adapter contracts、conversation、agent_batches、gateway terminal fence、session restore、native context budget；正常 legacy／candidate、取消與此前 FIX-001 failed-intent invariant。

### Acceptance criteria

反例修前 completed、修後 failed／cancelled 並保留 partial 與固定原因；正常合法終止仍 completed、正常 tools 仍可用；無額外 terminal／dispatch／重播。實際截斷原因若未重現，限制明記，不能稱近期所有問題根因已修。

### Rollback method

drain 受影響 run，撤精確 adapter／caller patch；保留最新 DB／journal，不重送。若舊版仍誤判，維持相關完整性 promotion gate 與明確未完成提示；不用舊 DB 覆蓋新資料。

### Risk

MEDIUM：過嚴完成規則可能拒絕合法 provider；output reserve 變更可能壓縮 input。以 profile fixtures、native budget 及正常對照防止擴散。

## FIX-004 — 頁面 session 憑證續期與連續使用

Status：**DONE / VERIFIED（2026-10-07；session lifecycle限定驗收，未部署私人服務）**。[真UI跨300秒、554項整體回歸、反例與回退證據](../evidence/FIX-004-2026-10-07/REPORT.md)。分類：REQUIRED_FIX。來源：MISSING_INTEGRATION、IMPLEMENTATION_BUG、TEST_GAP；既有 auth 設計有效，缺 consumer lifecycle。下方 Problem／Evidence／Actual 保留修前時點。

### Source Task

2026-10-07 對話檢視 CV-02；現行 Companion 頁面與 Gateway session 整合。無證據指定某張 RT 是唯一引入點。

### Severity

HIGH。

### Problem

頁面長時間開啟後仍使用過期 token，文字、語音或設定請求遭 401，產品無正常恢復路徑。

### Evidence

[SessionTokens](../../src/siro/services/presentation/gateway.py) 預設 ttl_seconds=300，session API 回傳 expires_in_seconds；[UI boot](../../src/siro/services/presentation/static/index.html) 只取一次，headers 永遠用原 token，未續期。受檢服務紀錄有 4 筆 turns POST 401；與上游 HTTPStatusError 不混為一談。

### Expected Behavior

同一合法 loopback／Origin 頁面跨 TTL 仍可使用；暫掛喚醒／服務重啟能受控恢復。維持短效 token、授權及唯一 socket／body owner。

### Actual Behavior

token 過期後請求失敗，頁面無法透明換證；WebSocket 驗證在建立時，HTTP 與 socket 生命週期也不一致。

### Root Cause

已確認 UI 未使用 session API 的 expiry，缺 refresh／失效處理。每個歷史 HTTPStatusError 的上游原因仍 UNKNOWN — NEEDS INVESTIGATION。

### Scope

沿用現行 bootstrap 的單一續期 owner、到期／401 分流與必要重連；不得重做 auth subsystem。續期新增的 server token retention 一併有界處理。

### Files expected to change

`src/siro/services/presentation/static/index.html`；`src/siro/services/presentation/gateway.py` 僅必要的過期 token 清理／界限。`tests/integration/test_gateway.py`、`test_frontend_companion.py`、`test_gateway_terminal_fence.py` 與相鄰 owner／speech tests；文件與合成 evidence。

### Files that MUST NOT change

Core、model provider keys／fallback、Origin allowlist、工具 grants／scope、DB migrations、action ledger、私人設定；不能改 TTL 為永久或略過 require_token。

### Compatibility requirements

原 `/v1/session`、Bearer headers 與 TTL 保留；所有 fetch 包含 STT／TTS／取消／設定同用有效 token。新 socket 先正確認證與交接，舊 socket close 不能拆掉新 owner；重連只恢復狀態，不重播語音或 effects。

### Proposed repair

用 expires_in_seconds 與本機單調計時維護單一 single-flight 續期；只在頁面需要使用時補證，處理暫掛與 server restart，有限重試避免 bootstrap storm。已確認 401 在接收 run／effects 前拒絕才可補證後重送；其他 ambiguous timeout 先 readback，禁止盲目重 POST。SessionTokens 在 issue 時清理過期紀錄並驗證有界策略，避免背景續期變成無限 token 保留。

### Tests required

fake clock 跨 300 秒、同時多請求只續期一次、暫掛喚醒、bootstrap 拒絕／失敗與 Gateway 重啟；過期前／後文字與語音成功。401 pre-accept 可恢復；已接受／不明是否接受不能再做 effects。持續換證 token retention 有界。

### Regression tests

Origin／非 loopback 拒絕、過期與錯誤 Bearer 拒絕、unique body owner／舊 socket close、terminal fence、speech cancel、新 turn 不復活舊音訊；一般 grants 與 computer tool pairing 不變。

### Acceptance criteria

真 UI 合成 session 超過 TTL 後正常交談／朗讀；不需手動重整；無 bootstrap storm／owner 競爭／重複 turn、重複工具或語音；受拒絕來源仍拒絕。fake clock 不能取代至少一次真持續使用驗收。

### Rollback method

停止續期 timer／pending bootstrap，drain UI owned 工作後撤精確 patch；必要時要求一次重新登入／重整、維持 gate。保留 DB／授權紀錄，不能撤銷 security check 或重播請求。

### Risk

MEDIUM：重送造成重複效果、token 累積、socket 交接競爭。以 pre-accept 證據、single-flight、retention 與舊 owner fence 驗收控制。

## FIX-005 — 有界分句朗讀、首段延遲與全文完整性

Status：**PARTIAL / IN_PROGRESS（2026-10-08；A／B實作，原聲線基線完整性／取消已驗；速度FAIL、人工語意聽驗NOT_RUN。僅CUDA採已量測SDPA，最後671項回歸／source回退已PASS，最終真機功能PASS、首播仍22.446s／RTF約1.75；維持體驗gate）**。分類：REQUIRED_FIX。來源：MISSING_INTEGRATION、BAD_INTERFACE、TEST_GAP；不將RT-006已驗owned-worker lifecycle宣告失敗。下方Problem／Actual保留修前時點。

### Source Task

2026-10-07 對話檢視 CV-03／05；現行 Companion audio caller；沿用 RT-006 的 worker 所有權、取消、request_id／epoch 成果。

### Severity

MEDIUM。

### Problem

語音整段等待，長回覆沒有完整朗讀保證；達生成限制的音檔可能被當成功快取。使用者明確要求保留語音、降低生成等待並講完長文。

### Evidence

[UI](../../src/siro/services/presentation/static/index.html) terminal→整段 speech POST→blob→play；[Gateway](../../src/siro/services/presentation/gateway.py) 等完整 bytes、每次 text≤4,000 字；[worker](../../scripts/qwen_tts_worker.py) 整段生成且 codec max_new_tokens=512，只按文字 hash 快取；[segmenter](../../src/siro/services/audio/tts.py) 尚未接入這條產品路徑。兩個近期 WAV header 同為 40.88 秒；不等於已證明尾端被截斷。

### Expected Behavior

先播已完整生成的第一段、後段有序接續；全文／故事在明示總資源上限內完整朗讀，取消或失敗清楚呈現。精簡朗讀須明示，全文入口仍保留；不能暗中省略尾段。

### Actual Behavior

必須等全段文字及音檔；無逐段隊列／進度、EOS／上限辨別，HTTP 200 後一律視為音訊成功。

### Root Cause

已確認：產品未使用既有 segmenter，完整音檔交付是播放前置，worker 無完整性回報且快取未綁生成設定。實際缺失尾句及目前冷／暖延遲瓶頸 **UNKNOWN — NEEDS INVESTIGATION**；不能僅靠 40.88 秒認定全部觸頂。

### Scope

分三個可獨立回退的局部步驟：A 分段完成判定／版本快取；B final 後有界順序生成播放；C 只有現有契約能辨識已提交 final-answer 句子時才提早排程。A／B 已可改善完整性與整篇音檔等待，不能將 C 假裝已完成。

### Files expected to change

`scripts/qwen_tts_worker.py`、`src/siro/services/audio/tts.py`、`services/presentation/static/index.html`、`services/presentation/gateway.py` 僅必要的 optional segment identity／completion 回報。`tests/integration/test_qwen_lifecycle.py`、`test_frontend_speech_cancel.py`、`tests/test_audio_pipeline.py`、`tests/real/test_speech_providers.py`、必要 audio contract fixtures；文件與合成 evidence。若 C 需要新跨層契約，另審窄幅修正，不擴張本卡。

### Files that MUST NOT change

Identity／Memory、Core planning／工具授權、RT-011 budget、schema／private DB、既有角色 reference／聲線與授權素材；不得增加第二個音訊 owner、無界 GPU workers 或自動換 OS voice。

### Compatibility requirements

舊單次 speech caller 可用；既有 prosody、嘴型與 cancel／close／reap 保留。segment 邊界不改原意，canonical 文字保留 code-block 語義，不能從重排 DOM 誤讀程式。每次低於 4,000 字，總工作／隊列也有界。超過總額或失敗須明示，不能謊稱全文已播完。

### Proposed repair

重用 speech_segments，實測決定每段字數與 codec 上限；一個 worker、順序播放、最多一段預取，turn／segment／epoch fence。把生成終止／疑似達上限視為未完成，必要時在 owned adapter 邊界取得 generation metadata；不能只升上限或翻 non_streaming_mode。快取綁 model／voice／生成／分段版本，未確認完整不寫成功快取。保留原 voice，實測 cold／warm 分項後才決定受控預熱或推論優化；無資料先不換 backend。

### Tests required

合成短句、長中文、英數、故事、超過單次 4,000 字；驗 segment 完整覆蓋、最後一句、順序／進度、hit／miss／舊 cache 隔離、達上限／worker 失敗。首段／播放／預取中 cancel、新 turn／owner 切換／重連；晚回應不復活。真聲音首尾驗收與冷／暖非快取延遲、RTF／間隙量測，不能只做 mocked WAV。

### Regression tests

RT-006 owned lifecycle／bounded queue／poisoned worker／disconnect／reap、audio protocol、frontend speech cancel、Gateway switches／session auth、Live2D affect／mouth owner；一般文字與工具不等待 TTS。

### Acceptance criteria

不需等整篇音檔即可播首段；全部要求朗讀內容覆蓋且首尾可聽驗，取消／失敗有明確結果；無跳段／重播／交錯／晚到復活；記錄目標硬體上的 latency 門檻與修前／後實測，cache hit 不充當暖生成。第一切片仍等 final 文字則如實記錄，不能宣稱真逐音塊串流。

### Rollback method

停止播放並取消／reap 預取，逐步撤 C／B／A 精確 patch；保留舊 API、資料與原聲線。新版 cache 使用獨立 namespace，不將新舊格式互讀，不刪使用者資料。必要時退到單次短句並明示長文限制；語音相關 promotion gate 未通過前保留。

### Risk

MEDIUM：分句語調斷裂、首段仍慢、GPU 爭用或取消漏播；只按字數不能保證完成。以單 worker／一段預取、真合成聽驗、metadata 與分項量測控制。無法取得 EOS 時須記錄缺口，不能把時長或空 exception 當完整證明。

## FIX-006 — 自身故障情境與合成多輪理解驗證

Status：**PARTIAL／局部事實投影 VERIFIED；理解品質未完成**。分類：REQUIRED_FIX。來源：MISSING_INTEGRATION、TEST_GAP；不將一般「笨／卡」直接定為 ORIGINAL_DESIGN_ERROR。

2026-10-10 D41：實際同配置provider paired synthetic先驗；只2production檔＋1新tests，既有repository的latest recorded dialog五欄摘要、同session/privacy/15min/UUID/closed error/byte bounds；新run前取樣、failed calls不復活，原每則語音/連線保證改為需觀測。40修前FAIL→55專項/adjacentPASS，全套946PASS／5real_provider未選／3既有warnings（114.33s）、format224/mypy214/lint/schema/零scoped secrets、228既有source僅2變／exact3filetemp rollback SHA PASS。獨立review找到invalid-time排序/NUL length並修復。**Own failure事實增益限定成立；voice correction仍truncated、unknown-effect重做語意FAIL、記憶cloud區別/style/CAPTCHA各有限制，BLOCKED_BY_FIX保留。** 沒有廣泛prompt/framework／budget/provider改動，沒有live8026restart/私人data/deployment。[證據與回退](../evidence/FIX-006-2026-10-10/REPORT.md)。

### Source Task

2026-10-07 對話檢視 CV-04；RT-010 的有界對話恢復與現行 Companion runtime facts 整合。failed intents 不恢復的原設計保留。

### Severity

MEDIUM。

### Problem

使用者在追問本產品剛發生的故障／更正語音需求時，回覆偏離當前情境，給外部 API／TTS 一般教學並反覆索取資料，沒有根據自身可驗證狀態承接。

### Evidence

匿名現象見 [review](CONVERSATION_VOICE_REVIEW.md)。[runs.recent_session_messages](../../src/siro/services/agent/runs.py) 只選 completed final pairs；[integrated runtime facts](../../src/siro/services/presentation/integrated.py) 有能力說明，但沒有同 session 最近 failed run 的安全 operational 摘要。部分回覆另受 FIX-003 的截斷影響。

### Expected Behavior

分清「自己剛發生的錯誤」與第三方服務問題；根據實際證據說明已知／未知，延續使用者更正，做已授權的可行觀察或明確說明目前限制。不得假裝已修好、捏造診斷或索取憑證。

### Actual Behavior

缺少自身故障 context，出現一般 checklist／外部 TTS 建議；尚未量到模型、prompt、截斷對理解品質各自的影響。

### Root Cause

已確認 own-runtime failure context 沒進下一輪；**整體對話品質落差的 root cause UNKNOWN — NEEDS INVESTIGATION**。先以合成 ablation 驗證，不能把全部問題歸給模型或記憶。

### Scope

先建立小型合成多輪案例與修前對照，再只補必要 composition facts／對話指引；不先換模型、重做 Memory 或擴張 history。無證據支持的 prompt 改寫不進 production patch。

### Files expected to change

`tests/integration/test_integrated_companion.py`、`test_session_restore.py` 與獨立合成 provider 評估紀錄；`src/siro/services/presentation/integrated.py` 僅必要的 bounded operational facts；`services/agent/runs.py` 僅既有 readback 不足時的唯讀同 session 摘要，先確認不需修改。文件與不含私人內容的 evidence。

### Files that MUST NOT change

Core／Identity／Memory schema、原 privacy／source revision 規則、工具執行／grants、provider secrets／backend、DB migrations；不恢復 failed executable intents，不把 raw log／tool payload 當 system prompt。

### Compatibility requirements

只取同 owner／session、符合當前 privacy、限量且固定欄位的 server 狀態；error 類名不臆測成特定 HTTP code／根因。其餘 completed history、summary、native budget 與 cloud egress 限制保留。UI 文字與網頁內容是未信任資料，不能當成權限或診斷真相。

### Proposed repair

合成重現語音需求更正、自身 UI 失敗追問、代詞承接、閒聊與工具後 final 失敗；先對照正確終止狀態／operational facts 的增量效果。若確認有效，以現有 runtime-facts 接入短摘要：最近動作狀態、固定 error 類別、已完成效果需回讀、原因未知；不拷貝整個 failed journal。保留使用者想聽語音的意圖，不靠關聲或長客服清單消除問題。

### Tests required

mock 驗 facts wiring／privacy／字數／隔離，不同 session／local-only／secret 不外送；真實同配置 provider 以合成多輪獨立評估理解與更正，對照未加 facts 與有 facts。遇未知原因不能聲稱已修／已觀察；失敗恢復不產生新 effects。

### Regression tests

integrated companion、persistent/session restore、summary／native budget、cloud privacy／preferences、greeting 與記憶能力、failed-intent fence、正常文字／工具與取消。

### Acceptance criteria

合成案例可承接自己剛失敗的情境、保留語音需求更正、提出具體可行下一步且誠實說未知；沒有憑證索取、假修復、私人資料外送或效果重送。單純 prompt 變長／mock PASS 不算理解改善；若 ablation 無效，停在 evidence 與下一個窄幅假設，不合併無效 abstraction。

### Rollback method

只移除新增 operational facts／已證明必要的局部指引，保留既有能力 facts、資料與 completed history；不回退 DB、不重播 failed run。保留合成測試與未解限制，對話品質 gate 不自動解除。

### Risk

MEDIUM：故障資訊可能越 session／privacy，模型可能把 error 類名當根因或因更多 context 更囉唆。以固定字段、來源／未知標記、有界長度與 ablation 控制；無證據不做通用 health-agent framework。

## 2026-10-07 產品 gates（追加，不改 RT 歷史）

| 產品交付範圍 | Gate | 不阻擋的工作 |
|---|---|---|
| 自動網路研究 promotion | BLOCKED_BY_FIX：FIX-002 及必要行為修復／搜尋端到端驗收 | 桌面素材、場景原型、本機唯讀整理 |
| 宣告回覆完整／長文語音完整 | BLOCKED_BY_FIX：FIX-005；FIX-003終止裁決已驗 | 合成重現、素材、獨立 scene prototype；既有短句功能不宣稱全面驗證 |
| 長時間連續互動與語音 | FIX-004 session gate已解除；語音仍BLOCKED_BY_FIX：FIX-005 | 正常換證／受控重連已驗；不代表完整聲音或真服務重啟全驗 |
| 自主對話／自身故障可理解品質 promotion | BLOCKED_BY_FIX：FIX-006；完整性需 FIX-003 | 本機唯讀整理、桌面純呈現與合成評估 |

使用者後續已授權依三份文件施工；逐卡局部修復、驗證、回退，不讓後續產品宣稱跨過相關gate。沒有證據推翻原Runtime Evolution核心設計，不建立ARCHITECTURE_CORRECTION.md。

---


### 2026-10-10 新增真provider負向驗收來源

FIX-002的[公開DDG probe](../evidence/FIX-002-2026-10-10/public-search-duckduckgo.json)在fresh synthetic owner／同一configured provider／native tool observation下，模型知道網站是human challenge且無結果，但自然回覆仍建議「繞過驗證機制」。未執行任何bypass或其他工具；這是限制說明品質的真反例，不表示已確認permission bypass。具体prompt／模型原因仍UNKNOWN，併入本卡semantic負向場景；不得因partial read成功就讓模型假稱search成功或建議違反access controls。

## FIX-007 — 綁定已批准技能與實際執行 package 身分

- Classification：REQUIRED_FIX
- Sources：IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP
- Status：**DONE / VERIFIED（2026-10-10，限定D40完整package identity）**
- Gate：FIX-007局部identity gate解除；generated skill activation／skill executable catalog仍 **BLOCKED_BY_SKILL_INTEGRATION**，需獨立sandbox／review／explicit enable驗收。

### Source Task

T22 的 SkillManifest／SQLiteSkillRegistry／SkillDispatcher；2026-10-09 Runtime Intelligence review。來源明確在既有技能元件，沒有證據歸因任何 RT task 或 REGRESSION。

### Severity

HIGH。

### Problem

啟用狀態只綁 skill id/version，沒有可靠綁定實際執行程式碼。已批准 package 的 plugin 或依賴描述變動後，仍可能沿用舊 enable 身分交給 worker。這會使「批准的是哪份程式」失去意義。

### Evidence

- `src/siro/core/skills.py:65–74`：`load_skill` 的 manifest_hash 只 hash manifest／input schema／output schema，沒有 plugin code。
- `src/siro/persistence/skills.py:15–35` 儲存 hash/path；`:51–60 is_enabled` 只查 id/version/state。
- `src/siro/adapters/skill_worker.py:138–141`：Dispatcher 只問 registry.is_enabled，再交 supervisor。
- [safety-probe.json](../evidence/RI-architecture-2026-10-09/safety-probe.json) `skill.code_change_preserves_manifest_hash=true`、`changed_code_object_reaches_supervisor=true`；僅 recording fake supervisor，沒有執行生成碼。可重現程式：[safety_probe.py](../evidence/RI-architecture-2026-10-09/safety_probe.py)。

### Expected Behavior

批准／啟用綁定固定 package 內容與 id/version。未批准的換碼、換 schema、換 executable dependency metadata 或換 package 路徑不能沿用舊 enable 執行。合法未變更 package 仍可透過既有 worker 執行；拒絕不造成副作用。

### Actual Behavior

plugin 變更不改現有 hash；同 id/version enabled 的 changed-code object 可到 supervisor。registry 儲存的 hash/path 未成為 dispatch 的完整身分檢查。

### Root Cause

已確認：hash 範圍未包含可執行內容，dispatch authority 又退化為 id/version boolean。TEST_GAP 是未涵蓋此反例的驗證缺口，不是 root cause；沒有證據宣稱現有套件更新造成 regression。

### Scope

只補現有 package digest、registry enabled identity 與 dispatch 前驗證。定義 deterministic package file set／相對路徑／symlink 規則及 executable dependency metadata；不建立新 registry、installer、dependency resolver 或 skill-generation pipeline。不在本卡擴 network／filesystem／hardware 權限。

### Files expected to change

- `src/siro/core/skills.py`：package identity／digest 計算與必要的內部 InstalledSkill 欄位。
- `src/siro/persistence/skills.py`：查驗 enabled id/version/hash/path 的既有 registry 方法。
- `src/siro/adapters/skill_worker.py`：dispatch 前比較完整 package identity；僅避免 checked identity 與交付 worker package 不一致所需的小範圍修改。
- `tests/integration/test_skill_registry.py`：換碼／換包／enable identity 反例與相容 fixtures。
- 受影響契約／ADR、此卡與獨立驗收證據；先確認是否可沿用現有 hash 欄位，不預設 schema migration。

### Files that MUST NOT change

Gateway／IntegratedCompanion／ToolOrchestrator、Memory／Identity／affect、Rust grant/RPC、device／firmware、Qwen／Live2D、原 migrations、provider／model routing、dependency／lockfile、運行中 DB。不得接 runtime skill catalog、批次 enable、修改 network denied 或新增 background owner。

### Compatibility requirements

保留 SkillManifest v1 的公開必填欄位與原技能名稱／版本／I/O 合約、預設 disabled、enable/disable 及 bwrap resource/cancel 行為。舊 manifest-only hash 不得自動升格為已批准 executable digest；明確回報須重新驗證／批准的狀態，保留原 rows／檔案、不清資料來通過測試。新 digest 語義若需版本標記，先寫最小契約，不能靜默接受未知格式。

### Proposed repair

1. 先將本輪換 plugin 碼反例改為 expected rejection 的正式測試，確認修前失敗；另驗同 id/version 不同 package root。
2. 沿用 `load_skill`／InstalledSkill，對可執行 package 與必要依賴描述建立 deterministic、path-bound、版本可辨識的 digest；明確排除 transient cache，不忽略可執行檔。
3. 既有 registry enabled check 改為查驗批准的固定內容身分；dispatch 前重新查驗實際內容，不能信任 caller 提供的舊 hash 或只查 id/version。
4. worker 使用已驗證的同一 package；若偵測來源變動或無法保證一致就拒絕。不要引入通用 sandbox 架構，剩餘 hostile host／OS 隔離另 gate。
5. 保留已安裝舊 package；只有可信 owner control flow 可重新驗證／批准。這張卡不替 owner 批准或執行任何生成技能。

### Tests required

同內容重載 digest 穩定；plugin 改碼、schema／entrypoint／dependency metadata 改動、同 id/version 不同路徑、symlink/path escape、偽造 InstalledSkill hash、準備期間來源改動／交付不一致拒絕且 supervisor 零呼叫；handoff後来源改动不替換已批准frozen snapshot。舊 hash row 明示需重新批准；預設 disabled／撤銷後拒絕；未變更已批准 fixture 正常。package 含多個 Python module 的修改也需被偵測，不能只 hash entrypoint 檔。

### Regression tests

`test_skill_registry.py` 全部，含 network／host files／secret environment、timeout／cancel／CPU／memory／output／concurrency；`test_procedural_candidates.py`、`test_tool_catalog.py`。既有 runtime boundary／普通對話與 body 不受新增技能行為影響；依改動範圍執行 ruff/mypy，來源 hash與真 bwrap結果分列。

### Acceptance criteria

已批准 id/version 不能執行任何未批准的 changed package；每個換碼／換包反例修前失敗、修後 supervisor 零呼叫。未變更合法 fixture、停用、原 sandbox/resource/cancel 回歸全過；沒有 runtime caller／權限擴張或 DB 資料修改。記錄完整 digest 範圍、舊 row 相容方式與已知 host race 限制。只重算 hash而不比較批准身分不算完成。

### Rollback method

先停止新的技能 dispatch，取消／收束 owned worker，再精確撤本卡 patch；保留 package／registry rows與批准證據，不 downgrade 或覆蓋 DB。舊 binary不識新 identity 時保持技能 disabled／fail closed，不能為了回退重新放行已知換碼漏洞。用合成資料演練來源回退與拒絕行為。

### Risk

HIGH：不完整 package file set、TOCTOU、舊批准誤認、新 digest 造成合法技能拒絕。以 deterministic fixtures、整包 executable coverage、dispatch-bound identity 與 fail-closed 相容控制。安全 fallback 是暫停技能，不能直接 import；完成本卡不代表任意敵意 skill 已可安全啟用。

### Implementation and verification — 2026-10-10

三個既有production檔、43新tests；完整versioned framed package digest＋stored root/hash identity、legacy拒絕不清rows、owned frozen byte snapshot＋取消清理／8 admission slots、worker semaphore綁package hash。Exact原三source42FAIL／1PASS→新舊/adjacent66PASS，全套906PASS／5real_provider未選／3既有warnings（113.93s）；真bwrap正/負向fixture PASS。227existing hashes只3production改，原tests及前序卡不動、精確4檔temp reverse/reapply SHA PASS。沒有runtime catalog/auto enable/deploy/live DB/私聊/WAV/key；trusted host/deps與idle semaphore retention限制保留，不以全套解开generated-code gate。[完整證據](../evidence/FIX-007-2026-10-10/REPORT.md)。

## FIX-008 — 完整辨識 patch 的 protected delete／rename 路徑

- Classification：REQUIRED_FIX
- Sources：IMPLEMENTATION_BUG、TEST_GAP
- Status：**DONE / VERIFIED（2026-10-10；限D38支援dialect／path preflight）**
- Gate：FIX-008局部protected-path gate已解除；**untrusted checks／自動promotion仍BLOCKED_BY_OS_ISOLATION與可信check allowlist**，不因本卡完成而启用。

### 2026-10-10 實作／驗收

只修evolution.py的bounded完整text-diff path preflight，收集舊／新聯集、驗metadata一致、按hunk counts消耗body；protected來源／目的、alias／歧義與unsupported格式在copy/apply/check前拒絕，原保護清單／checks／public report不改。新增62 tests：精確舊source46FAIL／16PASS，修後新舊63PASS；独立17 parser反例未找到證實bypass。全套829PASS／5 real_provider未選／3既有warnings（112.86s），lint／mypy211／schemas PASS。225基準檔僅1 production變動，精確兩檔temp SHA反向／重套PASS。

[交付／格式限縮／真命令／回退](../evidence/FIX-008-2026-10-10/REPORT.md)。沒有runtime caller／正式服務／DB／private輸入或候選live apply，same-user copy不是sandbox。FIX-007／009、生成技能review/enable與自動發布gate保持獨立。

### Source Task

T31 的 PatchProposal／PatchVerifier；2026-10-09 Runtime Intelligence review。本輪證明 delete 漏洞，其他格式依 fixtures 查證；不將未重現 rename 細節猜成已發生事故。

### Severity

HIGH。

### Problem

protected-path 判定沒有取得 diff 的完整變更集合，刪除 protected file 可以被漏掉。若 diff 同時有一般修改，整份候選能通過現有保護檢查並執行 checks。

### Evidence

- `src/siro/core/evolution.py:35` `_PROTECTED`、`:42–48` 僅用 `_changed_paths` 結果判斷 policy change。
- `src/siro/core/evolution.py:84–95` 只接受 `+++ b/`，忽略 `+++ /dev/null` 的刪除來源。
- [safety-probe.json](../evidence/RI-architecture-2026-10-09/safety-probe.json) `patch.protected_delete_status="passed"`、reported paths 只有 `calc.py`；synthetic authorization deletion與合法calc修改在 temp copy內完成，真 source 未碰觸。

### Expected Behavior

對整份候選取得新增／修改／刪除／rename 的來源與目的路徑，任何 protected path 受到影響都在 apply／checks 前拒絕。不能辨識、路徑有歧義或不支持的 diff 格式保守拒絕，不漏列後放行。

### Actual Behavior

刪除行使用 `+++ /dev/null`，被忽略；有另一個普通變更時 `changed` 非空、protected check 未命中、驗證回 passed。changed_paths 報告也不完整。

### Root Cause

已確認：自製 parser 將所有 changed path 等同新檔 header `+++ b/`，沒有處理舊 path／delete語義。不是需要更大 protected blacklist，也不是 temp workspace 本身造成此 parser bug。

### Scope

只修現有 PatchVerifier 的完整變更路徑取得與 fail-closed 判定；沿用已有 git／現有合法 unified diff輸入。完整格式不必全部支持；明確拒絕無法安全辨識的格式即可。OS sandbox、policy protection清單擴充、candidate生成、trusted checks內容、release流程不在本卡。

### Files expected to change

- `src/siro/core/evolution.py`：`_changed_paths`／驗證前的必要有限解析，可能用既有 git 支援取得 source/destination 的可靠集合；禁止新增大型 parser 依賴。
- `tests/integration/test_patch_verifier.py`：delete／rename／混合diff／不支持格式／拒絕前零check fixtures。
- 必要的 verifier輸入契約／ADR、此卡與合成驗收證據。

### Files that MUST NOT change

`core/authorization.py`、`config.py` protected source 本身、Gateway／Core conversation／ToolOrchestrator／skills／release manager、Memory／SQLite／migrations、Rust／devices、Qwen／Live2D、依賴／lockfile。不得藉本卡建立新 sandbox／evolution service 或直接套 patch 到 production。

### Compatibility requirements

原正常 unified modification仍能驗證；PatchProposal／VerificationReport 公開必填欄位不變。拒絕狀態保持既有明確語意；changed_paths 完整且穩定。不得把 unsupported格式當空patch成功，不執行 rawdiff中攜帶的程式或shell字串。若需限縮之前意外接受的格式，明列並提供明確拒絕，不能靜默跳過。

### Proposed repair

1. 將 protected delete＋一般修改反例改成 `rejected_policy_change`、零checks／零apply的正式測試，修前必失敗。
2. 以舊／新路徑聯集判定變更；rename 同時判 source/destination。保留原根目錄／`.git`／absolute／`..` 拒絕，不信任僅新 header。
3. 對 header不一致、quoted／特殊路徑、binary／rename-only等格式，先驗是否能安全取得集合；不能則 `rejected_invalid_diff`，不猜 path。
4. 完整集合通過保護判定後才進既有 temp-copy apply／trusted checks；這不是 untrusted sandbox完成。

### Tests required

protected刪除單獨／搭配一般修改皆拒絕；protected rename from／to、普通檔rename、普通新增／刪除與修改；舊新header混淆、`/dev/null`、路徑逃逸、absolute／`.git`、quoted／空白路徑、畸形／unsupportedbinary與rename-only格式。允許或拒絕須符合宣告契約；拒絕時 apply/check spy 零呼叫、真正 fixture source不變。

### Regression tests

`test_patch_verifier.py` 的 passing／failing trusted checks、unappliable diff、workspace cleanup、production tree unchanged。固定 runtime fixtures與ruff/mypy；本卡不需真 provider／GPU／硬體。OS isolation counterexample仍記為未解，不將其吞掉或改成假PASS。

### Acceptance criteria

任何 protected source/destination修改、新增、刪除、rename都在執行前拒絕；changed_paths完整且不越界；unsupported或歧義格式fail closed。原合法非protectedfixture仍可驗pass/fail並清理workspace，production source保持一致。只加對`/dev/null`字串特判卻未處理完整path集合不算完成。

### Rollback method

停用自動 patch checks／promotion，精確撤 parser patch；保留失敗fixture與證據。不對 live tree套／撤候選，不改DB。回退舊verifier時保留所有候選的人工審核／禁止自動checks gate，不能將已知漏保護版本當安全fallback。

### Risk

HIGH：不同diff格式、quoted path與rename來源可能造成誤拒或漏判。優先縮小支持格式、完整路徑集合與零副作用負向驗收，避免重寫整個verifier。即使本卡通過，same-user checks仍不隔離不可信程式。

## FIX-009 — 將 release 相容欄位綁入完整簽署

- Classification：REQUIRED_FIX
- Sources：IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP
- Status：**DONE / VERIFIED（2026-10-10，限定完整 manifest 簽署）**
- Gate：FIX-009局部gate解除；release promotion／自動發布仍 **BLOCKED_BY_RELEASE_INTEGRATION**，launcher與人工批准／資料保留式回退gate獨立保留。

### Source Task

T32 的 ReleaseManifest／ReleaseManager、CLI release staging caller；2026-10-09 Runtime Intelligence review。尚未發現真部署或 DB 事故，不能標 REGRESSION。

### Severity

HIGH。

### Problem

版本與source digest受到 HMAC保護，但控制schema相容性的min/max欄位沒有簽署。只改相容範圍即可使原本應拒絕的包被當有效release啟用。

### Evidence

- `src/siro/core/releases.py:17–24`：manifest包含min_schema/max_schema；`:45–48`以相容檢查與signature檢查決定是否進staging。
- `src/siro/core/releases.py:103–113`：HMAC訊息只有`version:digest`；`_compatible`另外信任manifest範圍。
- [safety-probe.json](../evidence/RI-architecture-2026-10-09/safety-probe.json) `original_schema_compatible=false`、`schema_bounds_changed_without_resigning=true`、`altered_manifest_activation_status="activated"`。全為temporarysyntheticbundle，沒有真部署或DB。

### Expected Behavior

任一release決策欄位被更改（含schema範圍）都使signature驗證失敗，staging/healthcheck/DBbackup/activepointer不改。只有完整有效簽署且確實相容的固定包能進既有staging流程。

### Actual Behavior

原min1/max2在current_schema8不相容；將max改8但沿用signature後，source digest與version仍匹配，驗證通過並在temporaryfixture回activated。

### Root Cause

已確認：驗簽訊息只涵蓋version/source內容，未涵蓋控制相容性的manifest欄位；signingfixture沿用相同不完整訊息，因此現有tests未覆蓋tamper。不是需要改signature演算法或更換發布框架。

### Scope

只定義canonical、版本可辨識的完整manifest signing payload並在既有驗簽／可信產生fixture caller使用；排除signature本身，綁定version/source_sha256/min_schema/max_schema及明確格式版本。合法schema範圍校驗在同卡。不要接launcher、改activepointer、改DBbackup／restore、加autodeploy或重做signingkey管理。

### Files expected to change

- `src/siro/core/releases.py`：canonical signed payload／schema-rangevalidation與驗簽。
- `tests/integration/test_release_manager.py`：合法簽署fixture與各欄位tamper反例。
- 如有實際本機manifest產生helper，僅該helper與其fixture；先搜尋確認，不假設repo已有signingCLI或新造service。
- 必要的release manifest契約／ADR、此卡與隔離驗收證據；CLI parsing只在明確格式版本必要且有相容測試時局部調整。

### Files that MUST NOT change

`scripts/launch_companion.py`與其他launcher、ReleaseManager activation/backup/rollback流程（本卡只在驗證前拒絕）、運行中service／active.json／DB／migrations、Gateway／AgentRuntime／skills／policy、Memory／Identity／grants、Rust／devices、Qwen／Live2D、dependency／lockfile。不得在本卡deploy或聲稱data-preservingrollback已完成。

### Compatibility requirements

原releaseversion／source digest／schema語意保留；明確區分完整簽署與舊不完整簽署，不允許新驗簽失敗後靜默fallback舊HMAC而重新放行schema tamper。未版本化舊artifact需在可信owner維護流程重新驗證／重簽；讀取與明確拒絕保留，不能自動批准／覆寫既有檔案。若新增格式version，先ADR與版本化fixture，不任意改其他公開API。

### Proposed repair

1. 先新增schema範圍tamper的expected rejection測試，保留原signed包、只改範圍；修前必失敗。
2. 用deterministic canonical serialization組成完整signingpayload，將schema bounds納入現有HMAC；先檢查合法range與格式版本，再驗簽。
3. 信任的測試／產生helper共用明確payload契約，測試要獨立驗證tamper而非僅呼叫同一helper自證一致。
4. 新驗簽不接受舊訊息fallback；舊artifact重簽另需明確可信操作。完整簽署／相容兩者皆成立才走既有stage流程，不能借本卡接自動發布。

### Tests required

合法manifest／bundle驗通；version、source digest、min_schema、max_schema各自tamper皆拒絕，新增未知field／invalidrange／unknownformat拒絕；JSONkey順序不改canonical語意；舊incomplete-signatureartifact不能在fallback下成功。拒絕須證明healthcheck零執行、active/LKG與DBbackup未動；全部temporaryfixtures。

### Regression tests

`test_release_manager.py`的schema拒絕、bad bundle、healthcheckfail、activationinterruption、原有效staging/rollbackfixture；`test_operational_cli.py`僅受影響release命令。ruff/mypy與範圍適當的合約回歸。本卡的rollback正向fixture只驗原行為，不能被用來宣稱較新memory/ledger不丟失。

### Acceptance criteria

完整決策manifest內容綁signature；任何schema範圍換值在sideeffects前拒絕；合法固定release通過原流程。舊簽署安全拒絕與可信重簽策略明確，不用fallback吞漏洞。既有activepointer／data-backup語意未改，相關未解gate仍顯示。只在`_compatible`增加另一個範圍判斷、不把範圍綁signature不算完成。

### Rollback method

先停releasepromotion，精確撤本卡驗簽／fixturepatch，保留bundle／manifest／audit證據；不回退運行中DB或已產生新資料，不觸碰使用者service。若回退到只支援舊signature的binary，仍保持promotiondisabled，不為兼容重啟不安全schema接受。以temporarybundle驗source回退與停止發布行為。

### Risk

HIGH：canonicalization不一致造成合法包拒絕、舊artifact相容fallback重新開漏洞、錯誤以為完整簽署已解決部署／資料回退。明確格式版本、獨立tamperfixtures、zero-sideeffect拒絕與分開promotiongate控制；不擴充成新releaseframework。

### Implementation and verification — 2026-10-10

只改 releases.py 與原 fixture、新增34 tests。修前 legacy schema tamper 真 activated；新集19FAIL／15PASS→新舊36PASS，全套863PASS／5 real_provider未選／3既有warnings（111.19s）。D39完整format/payload、strict range/type、typed entry revalidation、legacy拒絕與zero-effect/真CLI通過。226既有檔僅production與fixture變動，精確3檔temporary reverse/reapply SHA PASS；沒有 key/private data/live service/deploy。launcher／OS／最新資料回退仍保留。[完整驗收與限制](../evidence/FIX-009-2026-10-10/REPORT.md)。

## FIX-010 — 結果未知的同參數新call不可自動重做

Status: DONE / VERIFIED（2026-10-10，D42；限定本卡邊界）。Classification: REQUIRED_FIX。Origin: IMPLEMENTATION_BUG、MISSING_INTEGRATION、TEST_GAP。

### Source Task
FIX-006合成unknown-effect驗證與独立code review；未有證據指定單一歷史RT引入，不改RT編號。
### Severity
HIGH。
### Problem
舊proposal拒絕replay，但模型以新call/proposal UUID提出相同副作用時，full模式仍自動批准，即使上一筆派送結果outcome_unknown。
### Evidence
[合成反例](../evidence/FIX-010-2026-10-10/counterexample-before.json)：同session/capability/arguments hash、prior fenced dispatched、freshcall不同proposal、fullmode計數器handler實際1次（expected0）；真OS effects0。orchestrator.propose生成新UUID、resolve/transition未查prior unknown；integrated auto path直接resolve/execute。
### Expected Behavior
已記錄unknown效果的同內容新動作不能自動重送；先標明未知與可能重複，再由現行human approval明確決定。其餘不相關新操作／trusted read仍沿原權限。
### Actual Behavior
新UUID逃過舊proposal fence，自动計數器執行並final completed。不是已證實私人事故。
### Root Cause
CONFIRMED：原replay fence綁proposal owner/id，但auto approval完全不查同session先前fenced action ledger的unknown與content identity。
### Scope
既有SQLite approval transaction內查固定unknown ledger、現有resolve的明確automatic旗標與controller auto path/UI warning。只exactcap/hash；binding未知則同cap保守manual。不是semantic idempotency／新ledger或planner。
### Files expected to change
services/tools/orchestrator.py、presentation/integrated.py、static/index.html；新transaction/controller/frontend驗收與文件。
### Files that MUST NOT change
Core/auth/config protections、DB migrations/私有資料、model/provider/voice/sessiontoken、Memory/history/summary、browser scope、skill/release/patch原修復；不外送舊args，不擴grants。
### Compatibility requirements
manual resolve automatic=False保持原hash/CAS/kill switch/舊replay fence。full auto只有特定unknown hold。只信任當前trusted descriptor.effect=read免額外hold，risk/名稱/model/optionalmetadata不免。判斷跨舊privacy route但僅same-owned-store/session，無內容egress。無任意TTL/history cutoff放行。
### Proposed repair
先驗pending expected-state；BEGIN IMMEDIATE內LEFT JOIN valid old proposal/agent ownership，candidatev1/fenced/dispatched1/exact observation.error=outcome_unknown、NULL或invalid receipt；samecap且合法binding hash相同，或binding NULL/orphan/ownership/payload mismatch則hold。两側byte bounded合法object JSON在SQLite递迴decoded key paths驗內容；巨大integer保留lexeme，duplicate keys／無法抽取numeric拒絕binding。fixed PriorOutcomeUnknown不改pending。controller先作auto決定，再發唯一tool_proposal的fixedblocked原因；UI fullmode也顯示unknown/可能重複與manual一次按鈕，不假稱已auto批准。manual新批准不清old unknown。
### Tests required
原反例RED、同/不同args/cap/session/route、bound/null/orphan/mismatch、未dispatch/known-result/readtrusted/fakerisk；CAS／批准前fence、manual/denial/cancel/batch；DOM/真Chrome held警告/按鈕/零autoeffect與一次manual/控制reconnect。
### Regression tests
agent_batches/run_journal/ownership/approval、catalog availability、gateway/frontend、history/native pairing/取消與browser/session/voice相鄰；完整離線。
### Acceptance criteria
反例0auto handler effects、pending單一proposal與fixed warning；explicitmanual最多一次、取消後不復活；正常新操作不誤阻；approval內容檢查在同transaction。全套PASS≠語意品質DONE。
### Rollback method
先切safe/manual模式並drain ownedturns，精確reverse本卡patch；不以oldfull自動路徑處理unknown，不清ledger/回DB/重送。保留D41與前序dirty source，temp reverse/reapply SHA驗證。
### Risk
MEDIUM：保守hold與永久unknown可能增manual摩擦；只exact身份/同cap缺binding，非全局freeze。現行singlecontroller先supersede/finish再新run；不認證任意多controller更新在批准後的新unknown。語意等價不同args不在此卡。頁reload不恢復舊提案是既有debt，不得宣稱本卡已完整recovery。

Affected roadmap: FIX-010局部gate解除；RI-004／RI-006執行仍需各自RI-003／批准／FIX-006等gates，未因此解鎖自主執行／發布。read-only研究、靜態proposal、sandbox驗證可继续。FIX-006整體品質與FIX-002/005 gates保留。


### 2026-10-10 修復與驗收結果

原source最終45新cases全FAIL（3.19s）；修後新舊相鄰122PASS，全套991PASS／5real_provider未選／3既有warnings（118.71s）。真Chrome21checks PASS：唯一held卡/警告、pending零auto效果、WS reconnect不重送、人工一次/duplicate404、原unknown ledger不變、cleanup/source hashes。独立postreview修正候選payload／Unicode／number／duplicate邊界，未留本卡已確認blocker。229既有source只有3production變；2新test／exact5file reverse/reapply SHA PASS；format226/mypy216/lint/schema/零scoped secrets通過。無8026restart／private資料／發布。 [完整報告](../evidence/FIX-010-2026-10-10/REPORT.md)。

剩餘問題分類：old unknown人工resolution／無期限scan/retention為TECH_DEBT；gateway active snapshot vs waiting_tool及page reload pending-card recovery為既有MISSING_INTEGRATION，先列DEFER待專卡，不假稱本卡修好；numeric特殊key保守manual為DOCUMENTATION_ONLY限制。無原design error，不新增架構改正。
