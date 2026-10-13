"""Bind D51 documentation to completed, frozen offline and actual-signal evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'docs/evidence/FIX-015-2026-10-13'
HEADER = '## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED'


def prepend(relative: str, body: str) -> None:
    path = ROOT / relative
    old = path.read_text()
    if HEADER in old:
        raise RuntimeError(f'D51 already recorded in {relative}')
    title, rest = old.split('\n', 1)
    path.write_text(title + '\n\n' + HEADER + '\n\n' + body.strip() + '\n\n' + rest.lstrip())


def main() -> None:
    full = (EVIDENCE / 'full-final.log').read_text()
    result = re.search(r'(\d+) passed, (\d+) deselected, (\d+) warnings in ([0-9.]+)s', full)
    assert result and result.group(1, 2, 3) == ('1578', '5', '3'), 'final offline suite incomplete'
    focused = (EVIDENCE / 'focused-final.log').read_text()
    assert '240 passed, 2 warnings' in focused
    local = (EVIDENCE / 'cli-lifecycle-final.log').read_text()
    assert '25 passed' in local
    signal = json.loads((EVIDENCE / 'signal-final.json').read_text())
    assert signal['source_unchanged_during_probe'] and len(signal['cases']) == 8
    assert all(c['child_exit'] == 130 and not c['child_stderr_present'] and c['child_joined']
               and c['synthetic_root_removed'] and c['original_sigint_handler_restored_after_command']
               for c in signal['cases'])
    rollback = json.loads((EVIDENCE / 'rollback-final.json').read_text())
    assert rollback['status'] == 'PASS' and rollback['unchanged_baseline_count'] == 269
    freeze = json.loads((EVIDENCE / 'source-freeze.json').read_text())
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == value
               for path, value in freeze['source_sha256'].items())
    assert 'All checks passed!' in (EVIDENCE / 'lint-final.log').read_text()
    assert '311 files already formatted' in (EVIDENCE / 'format-final.log').read_text()
    assert '245 source files' in (EVIDENCE / 'types-final.log').read_text()
    assert not (EVIDENCE / 'schema-final.log').read_text().strip()
    assert not (EVIDENCE / 'diff-final.log').read_text().strip()
    duration = result.group(4)
    metrics = f'新25 cases、相鄰240 PASS（17.60s）；完整 **1,578 PASS／5 real_provider 未選／3既有 warnings／{duration}s**。Ruff311／mypy245／schema／diff PASS。'
    limitation = 'RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：first-adoption舊／非受管writer停止、真正signed launcher/version/readiness與人工批准handoff仍待各自驗收。FIX-002有用搜尋、FIX-005語音速度／人耳、FIX-006理解產品gate保持；RT-011/013/015原scopedDONE及編號不改。'
    scope = '只改SQLiteStore既有backup方法與CLI `_backup` wrapper，新增兩份專項tests；operations、D49 restore body/SQL、D50 owner/Gateway/原tests、Core/權限/providers/voice/UI/launcher/deps不變。'
    repair = 'retained executor Future＋copy_context＋backup-local cancel Event讓writer lock持有至真正IO／明確connection close／cleanup完成；ZIP沿原context順序清理。CLI單次backup在main thread把SIGINT轉成owned task.cancel並喚醒同loop，反覆中斷等待收尾，finally恢復原handler；primarytypederror優先，plainCancelledError不改，signal cancellation才轉KeyboardInterrupt/130。'
    safety = '沒有操作live8026、私人DB/chat/WAV/key/config/models/GPU或正式部署。所有DB/OS probes是自有合成資料；pause/fault injection明示，不能冒充真人產品或power-loss驗收。'
    after = '269/271既有baseline bytes保持，exact4 source-only temporary reverse/reapply PASS；保留所有資料與Git歷史，source rollback不授權再用舊危險取消路徑。'
    link = '[驗收、分類、限制與回退](../evidence/FIX-015-2026-10-13/REPORT.md)。'
    status = '\n\n'.join((
        'FIX-015 **DONE / VERIFIED**，解除ZIP取消後staging遺留的局部BLOCKED_BY_FIX；D50/FIX-014 scopedVERIFIED保持。',
        scope + repair,
        metrics + ' 真8程序SIGINT（含三次中斷／64-of-124-page複製中／真正發布後）全部130、stderr零、handler恢復、IOjoined、staging無遺留、3keys持到join、next-owner成果保留。',
        '初版CLI controlled24PASS漏selector喚醒，真8 timing FAIL與原D50 backup init2 FAIL先留RED；只補stdlib既有threadsafewakeup，不改舊tests或門檻。'+after,
        limitation,
        'Architecture YELLOW；backup/owner/Gateway YELLOW、合成tests/evidence GREEN；running DB/migration/權限/發布 RED。KEEP RI-005並SPLIT剩餘adoption/handoff，KEEP RI-006只到唯讀提案；REJECT第二backup/owner/executor manager，不因抽象美觀重做DONE。',
        'GitHub Desktop OS-vault認證已接到repository-local Git helper；LFS用既有Desktop binary，hooks保留。public checkpoint `7892ecc`已推送／remote核對；原unpublished歷史留在local-backup/pre-public-push-2026-10-13，私有models/audio/cache未上傳。D51發布若執行，另核對其commit，不把7892稱為包含本修復。',
        safety,
        '[完整本輪驗收與回退](evidence/FIX-015-2026-10-13/REPORT.md)。',
    ))
    prepend('docs/STATUS.md', status)
    prepend('docs/runtime-evolution/ARCHITECTURE_REVIEW.md', '\n\n'.join((
        '**Overall architecture health — YELLOW。** 單一owner與既有backup boundary方向成立；本輪修復已證local defect，不需推翻runtime設計。'+scope,
        '**Recent improvements。** '+repair+' 真SIGINT先暴露selector盲區再局部修掉。',
        '**Architecture drift found。** 已修responsibility leakage：backup coroutine先退但thread仍寫，外層ZIP失去cleanup時間權威。未新增duplicated abstractions／Core lower dependency／global registry／circular coupling／compatibility bypass；CLI只composition-level signal lifetime。',
        '**Regression risk changes。** '+metrics+' 真8OS cancellation及25新cases成為新baseline；原D50 callers保持。actual blocking selector不能僅靠controlled task.cancel測試代替。',
        '**Technical debt introduced。** signalhandler lifetime和private optional cancel Event為最小operation-local obligation；D49restore與backup不硬抽共用manager。未知OS阻塞、cleanup refusal、備份retention與跨檔atomic仍DEFER/TECH_DEBT，無新立即重構依據。',
        '**Roadmap adjustments。** KEEP RI-005，SPLIT stopped-old-writer/actual approved launcher/handoff；FIX-015 DONE解除其局部block。KEEP RI-006唯讀proposal。CANCEL/REORDER/MERGE/額外DEFER numbered tasks無新增實證需求，不硬套動作、不重編RT。',
        '**New blockers。** 無剩餘confirmed FIX-015 scoped blocker；'+limitation,
        '**Freeze zone changes。** backup取消staging由FAILED_VERIFICATION恢復限定VERIFIED，但module仍YELLOW；owner/Gateway YELLOW，合成tests/evidence GREEN，live DB/migration/權限/發布 RED。'+after,
        '**Hermes relevance。** REJECT重複backup/owner/executor/state-manager抽象；DEFER一般自改/自動發布及更多profiles至有caller、收益和獨立gate證据。已有局部行為已解決，不再重構。',
        '**Recommended next 3 RT task scopes（不排名、不換號）。** RI-005 first-adoption stopped-old-owner證明；RI-005 exact approved signed launcher/version/readiness/handoff；RI-006 sourced-failure→唯讀proposal，不自啟用/發布。產品FIX-002/005/006保持獨立品質驗收。',
        safety, link,
    )))
    prepend('docs/runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md', '\n\n'.join((
        '**FIX-015 DONE / VERIFIED**：backup cancellation staging/connection/CLI teardown的最小修復已驗；原D50/FIX-014 DONE保留。'+metrics,
        '| 既有卡／範圍 | 決定 | 依賴與現況 |\n|---|---|---|\n| FIX-015 | DONE / VERIFIED | 解除ZIP取消cleanup局部BLOCKED_BY_FIX |\n| RI-005 | KEEP / SPLIT / PARTIAL | first-adoption停止舊writer；actual signed launcher/version/readiness/批准handoff仍BLOCKED_BY_RELEASE_INTEGRATION |\n| RI-006 | KEEP | 已有來源失敗到唯讀proposal；不能自批執行／部署 |\n| RT-011 / RT-013 / RT-015 | 原scopedDONE保持 | 已實現能力不重做、不修改編號歷史 |\n| FIX-002 / FIX-005 / FIX-006 | PARTIAL保持 | 有用搜尋、語音速度／人耳、理解各自產品gate |',
        'Recommended next 3既有續作範圍（不是ranking）：RI-005舊writer停止證據；RI-005批准的exact版本launcher/readiness/handoff；RI-006唯讀proposal。沒有實證支援硬CANCEL、MERGE或額外抽象擴張。',
        limitation, link,
    )))
    prepend('docs/runtime-evolution/REGRESSION_BASELINE.md', '\n\n'.join((
        metrics,
        '新baseline：SQLite19（raw/ZIP repeated task cancellation、queued writer、真正multi-page non-DONE/DONE-before-publication、actual publication後取消、explicit close、typed primary/cleanup refusal、ContextVar隔離）＋CLI6（normal/plaincancel/typederror/late-success/repeatedcancel/非mainthread）。真8SIGINTfixture與source5path綁定，8stderr零；原D50 initialization-stage SIGINT tests保持。',
        '曾失敗的controlled handler缺wakeup版本留在full-before-wakeup.log（2FAIL/1575PASS/5未選/3warnings），不能當final；首次24 controlled PASS也不算trueOS驗收。原SQLite16/18-case RED是階段test版本，不冒充最終25case全RED。',
        after, 'real_provider、真人語音/理解、運行8026與powerloss NOT_RUN；沒有降低gate或改mock取代真整合。', link,
    )))
    prepend('docs/runtime-evolution/RISK_REGISTER.md', '\n\n'.join((
        'FIX-015 REQUIRED_FIX / MEDIUM / IMPLEMENTATION_BUG＋MISSING_INTEGRATION＋TEST_GAP已DONE：late IO staging重建／sidecars遺留風險在已驗profile下降。MINOR_FIX / LOW初版selector／coroutine teardown問題已局部修；沒有private正式data-loss或其他UID可讀證據。',
        '剩餘風險：無界OS阻塞須保持pending/owner，不承諾新cancel SLO；close/unlink refusal可見但不能假稱cleanup完成；final os.replace後取消可能已提交，readback再決定，零自動重送。ZIP DB/config跨檔atomic、powerloss、old/nonmanagedwriter、hostile sameUID races與真正launcher仍未證。',
        metrics, limitation, 'backup/owner/Gateway YELLOW；tests GREEN；live DB/migration/grants/release RED。'+safety, link,
    )))
    prepend('docs/runtime-evolution/COMPATIBILITY_PLAN.md', '\n\n'.join((
        'Public backup_to(destination)、成功raw/ZIP格式、原CLI參數/result與既有ownedloopfactory保持；private _backup_sync(destination, cancelled=None)仍相容single-argument caller。ThreadEvent不新增permission/schema或provider/device耦合。',
        'CLI temporary main-thread SIGINT只包此backup，exactprevioushandler於finally恢復；plainCancelledError及primarytypederror保持，signal cancellation/late flag→原KeyboardInterrupt/130。Backgroundthread不改OShandler； ఇతర commands和D50 main不變。'.replace('ఇతర', '其他'),
        'raw final publication後取消仍保成果，不能將130解讀為rollback；原D49 restore全部bytes保持。'+after, link,
    )))
    prepend('docs/runtime-evolution/MIGRATION_PLAN.md', '\n\n'.join((
        '本輪是兩個既有production方法區域的incremental修復，無DB/schema/config/grant migration。'+scope,
        '每次backup只有一份ownedexecutorFuture/context/cancel flag；原ZIP TemporaryDirectory在await真正完成後cleanup，不新增adapter或永久fallback。成功既有API保持，舊不安全cancel行為明確撤銷。',
        after, limitation, safety, link,
    )))
    prepend('docs/runtime-evolution/HERMES_GAP_ANALYSIS.md', '\n\n'.join((
        '**REJECT** 為backup cancellation再造manager、executor service、第二owner registry或全域state abstraction。實測已由原SQLiteStore／CLI composition局部修復，不為完成Hermes概念清單繼續擴張。',
        '**KEEP** 來源、bounded ownership、失敗可見與驗收導向原則；**DEFER** 任意code generation／自動發布／cross-platform和multiprocess profiles到具體caller、實際收益與各自安全gate成立。'+limitation, link,
    )))
    prepend('docs/runtime-evolution/CAPABILITY_MATRIX.md', '\n\n'.join((
        '| 能力 | 已驗範圍 | 限制 |\n|---|---|---|\n| backup取消完整收尾 | SQLite19＋CLI6、真OS8SIGINT，raw/ZIP staged data與connections cleanup、3keys持至join | 合成資料/controlled timing；OS拒絕或無界阻塞不能假稱已清理 |\n| committed raw backup outcome | final publication後取消仍保有成果/readback，exit130不是rollback | 不新增retry或data rollback |\n| GitHub Desktop Git認證／public push | repository-local OS-vault helper；public7892已push/remoteverified，local backup history保留 | Git推送不等於正式runtime部署 |',
        limitation, link,
    )))
    prepend('docs/runtime-evolution/RUNTIME_EVOLUTION_SPEC.md', '\n\n'.join((
        '補強原取消invariant：backup writer lock與外層ZIP staging生命周期涵蓋actualIO、explicitconnectionclose、cleanup；不能把asynccaller cancelled或Future cancelled當作thread完成。Backup-local retainedFuture/copy_context/cancelEvent只實現既有責任，不新增runtime service。',
        'Composition entry SIGINT必须取消owned coroutine並喚醒其blockedloop；repeated SIGINT等實際backup resolve後恢復exacthandler/原interrupt。Cleanupsecondary保typedprimary＋type-onlynote，無primary失敗仍可見；publish後取消honestcommit/readback、不自retry。',
        scope, limitation, link,
    )))
    path = ROOT / 'docs/runtime-evolution/FIX_REGISTER.md'
    old = path.read_text()
    start = old.index('## FIX-015 —')
    end = old.index('## FIX-014 —', start)
    card = '''## FIX-015 — ZIP backup cancellation must not recreate cleaned staging

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

'''
    path.write_text(old[:start] + card + old[end:])
    summary = {'full_offline': {'passed': 1578, 'deselected_real_provider': 5, 'existing_warnings': 3,
                              'seconds': float(duration)},
               'focused': {'passed': 240, 'existing_warnings': 2, 'seconds': 17.60},
               'new_cases': 25, 'actual_signal_cases': 8,
               'source_sha256': freeze['source_sha256'], 'baseline_unchanged': 269,
               'baseline_count': 271, 'rollback_scope_files': 4,
               'format_files': 311, 'mypy_source_files': 245,
               'scoped_fix_status': 'DONE / VERIFIED', 'RI-005_status': 'PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION',
               'codebase_memory_callable_tools': [], 'codebase_memory_reindex': 'NOT_RUN'}
    (EVIDENCE / 'verification-final.json').write_text(json.dumps(summary, indent=2) + '\n')
    (EVIDENCE / 'REPORT.md').write_text(f'''# D51 / FIX-015 — backup cancellation and Git integration

## A. Current State

FIX-015 DONE / VERIFIED for backup cancellation/staging cleanup. D50/FIX-014 remain scopedVERIFIED. RI-005 is PARTIAL: actual approved signed-version launcher/readiness/handoff and old/nonmanaged writer adoption are not proven. RT-011/013/015 scopedDONE histories are preserved; FIX-002/005/006 retain product-quality gates. This is a source repair, not deployment or final product acceptance.

GitHub Desktop authentication now works for local Git through its existing OS credential store and a repository-local helper. No token was logged, copied into tracked files or stored as plaintext. Existing Desktop LFS binary is used; pre-push hook retained. Public checkpoint7892ecc was actually pushed and remote verified. Local unpublished history remains on local-backup/pre-public-push-2026-10-13; private audio/models/cache and uncertain historical artifacts stay local. The public checkpoint parent is the previously public remote, with no private ancestors transferred. D51 source publication is recorded separately if pushed;7892 does not contain D51.

## B. Codebase Memory Status

No callable Codebase Memory MCP tool is exposed in this session; graph connection/query/reindex/validation NOT_RUN. Existing repo integration is not equated with a successfully connected MCP or SIRO personality memory. Raw source, actual tests and exact hashes supplied the evidence.

## C. Architecture Findings

Confirmed root path: operations TemporaryDirectory→await SQLiteStore.backup_to→unowned to_thread→late _backup_sync mkdir/copy. Cancellation unwound writer/context before real IO; sqlite3 connection transaction context also did not close actual connections. The lower backup responsibility leaked into the enclosing ZIP lifetime.

SQL-only repair protected data/staging but repeated default Runner SIGINT abandoned coroutine teardown. Backup-only temporary handler initially cancelled its task without waking the blocked selector; true8 timing failures plus two original D50 init-stage test failures exposed this. Installed Python3.14 Runner._on_sigint explicitly performs cancel plus call_soon_threadsafe wakeup. The local handler now follows that same behavior. No original architecture error or need for new ARCHITECTURE_CORRECTION was found; existing single owner remains valid.

## D. Implemented Changes

- src/siro/persistence/sqlite.py: only backup methods plus copy_context import; retained default-executor Future/captured context, local cancel Event, actual copy/publication fences, writer lock retained until IO/explicit connection close/cleanup, typed primary errors preserved with type-only secondary notes.
- src/siro/cli.py: only _backup wrapper plus threading imports; one backup main-thread temporary SIGINT→ownedtask.cancel＋loop wakeup, repeated cancellation waits cleanup, finally restores exact previous handler. Signal cancellation/late successful body flag become original KeyboardInterrupt; plain CancelledError/primary typed errors remain.
- two new focused test files (19 SQLite +6 CLI); contracts/decisions updated before each production correction.

D49 restore and all other SQLite body; D50 owner/Gateway/main/original tests; operations, Core/policy/providers/voice/UI/launcher/dependencies remain unchanged. Private _backup_sync(destination,cancelled=None) preserves direct one-argument callers. Public API and raw/ZIP formats unchanged.

## E. Tests and Verification

| Evidence | Actual result | Scope |
|---|---|---|
| cli-before.log |4FAIL/1PASS | Original CLI, first5 controlled tests before implementation |
| lifecycle-before.log |14FAIL/2PASS | Original SQLite, initial16-case RED snapshot |
| lifecycle-cancellation-fences-before.log |16FAIL/2PASS | Original SQLite, expanded18-case RED snapshot |
| signal-after-progress.json |8data/staging PASS;4tripleSIGINT pending-task stderr | Intermediate SQL-only repair, not final teardown PASS |
| signal-cli-wakeup-before.json |8 timing failures | First CLI handler without selector wakeup |
| focused-before-wakeup.log |2FAIL/237PASS | Original D50 backup/ZIP init-stage callers exposed real integration bug |
| full-before-wakeup.log |2FAIL/1575PASS/5unselected/3warnings | Historical incomplete source; not final baseline |
| cli-lifecycle-final.log |25PASS | Final19SQLite+6CLI cases |
| focused-final.log |240PASS/2existingwarnings/17.60s | Final new+original restore/operations/release/signing/owner/launcher tests |
| full-final.log |1578PASS/5real_provider unselected/3existingwarnings/{duration}s | Complete final offline suite |
| signal-final.json/.log |8PASS/130/zero stderr | TrueOS single/three SIGINT: raw/ZIP beforecopy, raw afteractualpublication, actualSQLite in-flight64/124pages |
| format/lint/types/schema/diff-final.log |PASS (Ruff311/mypy245) | Actual final code/style/type/wire-schema/diff checks |
| rollback-final.json |PASS/269 of271baselineunchanged/exact4sourceonly | Disposable reverse/reapply, no live data modification |

All8 truechild probes verify exacthandler restoration, no Runner.close while backupIOpending, every repeat consumed by owned coroutine, IO/children joined, source/config/priorarchive/fixedtemp retention as applicable, staging absence after join,3data keys held to join and next-owner write retained. Raw publication after cancellation remains committed honestly. Every controlled child joined and synthetic root removed; no forced kill in final probes. Timing pauses and cleanup/copy error injections are controlled; actualSQLite, filesystem, kernellocks and processsignals are real.

Full warnings are the existing pypinyin codecs.open deprecations plus preexisting Starlette httpx TestClient deprecation, not pending backup warnings. real_provider and actual human voice/comprehension/product5026/runtime8026/private-data/deployment/powerloss are NOT_RUN. scripts/check as a single aggregate command is NOT_RUN: final offline/format/lint/mypy/schema and scoped secret gates are separately executed; Rust/dependency sync/native model setup are unchanged and not rerun by this card. Do not claim aggregate CI success from scoped checks.

Independent reviews: lifecycle-review.md/lifecycle-cli-review.md, signal-review.md, rollback-final-report.md. First controlled review missed selector wakeup; that limitation and new trueRED/final source bindings are retained. Exact four SHA values are in source-freeze.json; actual5production probe hashes match start/finish.

## F. Risk Assessment

Backup/module owner/Gateway remain YELLOW; synthetic tests/evidence GREEN; running DB/migration/permissions/release RED. Blocking OSIO can remain pending; no new bounded cancellation SLO is invented. Connection/unlink refusal remains visible and does not claim cleanup succeeded. A final published raw snapshot can exist with130; read back before retry, no automatic retry/rollback. ZIP multfile atomicity, powerloss, hostile sameUID races and old/nonmanaged writers are not proven. Backup retention/capacity remain TECH_DEBT/DEFER, not immediate abstraction expansion.

Exact4 source-only rollback restores captured prior SQL/CLI bytes and removes then reapplies two newtests in a disposable tree, retaining all user data. Source rollback does not authorize use of unsafe previous cancellation behavior.271 baseline paths have only the two intended existing modifications;269 remain byte-identical. Git-hygiene publication of previously omitted synthetic tests is separate from this repair scope.

No live8026/privateDB/chat/WAV/key/config/models/GPU or formal deploy actions occurred.

## G. Recommended Next Tasks

Three existing scopes, not a ranking or renumbering: RI-005 first-adoption stopped-old/nonmanaged writer evidence; RI-005 approved exact signed launcher/version/readiness/handoff; RI-006 source-backed failure→read-only proposal. KEEP RI-005/SPLIT remaining gates; KEEP RI-006; RT-011/013/015 DONE unchanged. No evidence demands cancelling a numbered task, redesign or new owner/backup manager.

## H. Deferred Work

REJECT duplicate backup/owner/executor/global-state abstractions. DEFER arbitrary self-modification/automatic publication and dependency/multiprocess/cross-platform certification until concrete caller/value and separate safety evidence exist. Keep real voice-speed/human perception/useful-search/comprehension gates open. Neither a public Git push nor offline PASS substitutes for those product results.
'''.replace('product5026/', 'product/'))
    print(json.dumps({'documentation_updated': True, 'full_passed': 1578, 'new_cases': 25}))


if __name__ == '__main__':
    main()
