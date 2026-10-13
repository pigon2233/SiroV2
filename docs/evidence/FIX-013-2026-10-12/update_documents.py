"""Write verified D49 progress only after final full regression succeeds."""
from pathlib import Path
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
log = (OUT / 'full-final.log').read_text()
match = re.search(r'1483 passed, 5 deselected, 3 warnings in ([0-9.]+)s', log)
assert match, 'final full suite has not passed'
seconds = match[1]
paths = [
    'docs/STATUS.md',
    *['docs/runtime-evolution/' + name for name in (
        'RUNTIME_EVOLUTION_ROADMAP.md', 'REGRESSION_BASELINE.md', 'FIX_REGISTER.md',
        'CAPABILITY_MATRIX.md', 'CURRENT_ARCHITECTURE_AUDIT.md', 'RISK_REGISTER.md',
        'ARCHITECTURE_REVIEW.md', 'ROADMAP_RECONCILIATION.md', 'RUNTIME_INTELLIGENCE_DESIGN.md',
    )],
]
for name in paths:
    destination = ROOT / name
    text = destination.read_text()
    link = 'evidence/FIX-013-2026-10-12/REPORT.md' if name == 'docs/STATUS.md' else '../evidence/FIX-013-2026-10-12/REPORT.md'
    summary = f'''## 2026-10-12 — D49 / FIX-013 explicit restore 局部修復 VERIFIED

真正 temporary SQLite 證明舊路徑先覆蓋 live 再拒 migration/checksum，且 cancellation 提前釋放 writer lock。只改既有 SQLiteStore：mode=ro/query_only source→owned candidate→known prefix/checksum/既有遷移/integrity→SQLite backup promotion；不replace live/WAL。原 per-store writer lock 持有到 offloop thread/explicit connection close/cleanup joined；取消中止未完成 copy，DONE後取消誠實保留已commit資料。原typed error保留、cleanup refusal可見，不假稱已移除。獨立review先RED修掉Python3.14 shield重複error，只改owned await asyncio.wait/job.result，沒有新restore/schema/updater抽象。

41新cases；exact original source **30FAIL/11PASS**（5.61s）；最終專項 **145PASS**（4.95s），完整 **1,483PASS/5 real_provider未選/3既有warnings**（{seconds}s）；Ruff306/mypy240/schema/diff PASS。真raw/ZIP CLI、舊schema/WAL/來源唯讀、取消/queued writer/ledger retention驗收；IO/清理/進度timing標controlled。三份獨立review重綁final source後無scoped blocker。266 baseline中265不改、新2tests，exact3 source-only reverse/reapply PASS，D47/D48保留；sensitive final audit另見report snapshot（不把未掃項冒充PASS）。

FIX-013 **DONE/VERIFIED**，只解除此explicit-restore failure gate；RI-005整體 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：activepointer不等於真正版本，stopped writer／實際launcher/version/readiness／人工批准還未驗。成功明確data restore可替換近期資料，code rollback仍只切版本；commit後取消/cleanup failure需readback再決定，不重送。沒有live8026 restart、privateDB/chat/WAV/key/model/GPU或發布；FIX-002/005/006產品gate與RT-011/013/015 scopedDONE不變。

Architecture YELLOW；restore元件YELLOW、合成測試/evidence GREEN；運行DB/migrations／權限／發布RED。ZIP DB/config跨檔atomic、multiprocess lease、powerloss不算本卡驗收；candidate disk-capacity／舊backup retention為TECH_DEBT/DEFER，不建新manager。KEEP RI-005、SPLIT stopped-owner與actuallauncher；接續三窄切片RI-005 owner、RI-005 approved launcher/version/readiness、RI-006唯讀提案（非ranking、不重編）。Hermes REJECT重複restore/evolution abstraction，DEFER任意自改/發布直到接入有證據；本卡無new scoped blocker。

[驗收、限制、精確回退]({link})。
'''
    assert '## 2026-10-12 — D49' not in text, name
    first, remainder = text.split('\n', 1)
    destination.write_text(first + '\n\n' + summary + '\n' + remainder.lstrip('\n'))

fix = ROOT / 'docs/runtime-evolution/FIX_REGISTER.md'
text = fix.read_text()
start, end = text.index('## FIX-013 —'), text.index('## FIX-012 —')
entry = text[start:end]
replacements = {
    '- Problem:': 'explicit restore originally replaced latest live data before migration rejection; unknown future metadata was accepted, and cancellation released writer ownership while the thread continued.',
    '- Evidence:': 'D48 restore-failure.json and D49 before/src/siro/persistence/sqlite.py exact original; final original-projection30FAIL/11PASS; independent boundary/current probes. D49 final src/siro/persistence/sqlite.py:361 restore_from→owned job→_restore_sync(candidate validation before live backup). ../evidence/FIX-013-2026-10-12/REPORT.md.',
    '- Actual Behavior:': 'Before: old snapshot became live on checksum failure/future metadata; canceled thread could erase queued writes. After: rejected candidate preserves latest rows/source; cancellation joins under writer lock, primary typed errors retained, committed restore never described as rolled back.',
    '- Root Cause:': 'confirmed validation-after-promotion ordering, apply_migrations lacking unknown-version rejection, and bare to_thread cancellation not owning the continuing thread. Intermediate shield duplicate-error race independently reproduced1FAIL and fixed by wait/result without changing ownership.',
    '- Files expected to change:': 'exact3: src/siro/persistence/sqlite.py; tests/integration/test_sqlite_restore_validation.py; tests/integration/test_sqlite_restore_lifecycle.py; public evidence/contracts/decisions/status only.',
    '- Tests required:': 'completed41 actual-DB cases with controlled timing/IO/cleanup: checksum/name/future/gap/type metadata, migration SQL failure, schema0/1/3/10/12/13 upgrade, WAL/source readonly+explicit closes, both copy-stage cancellations, waiting-lock/repeated cancel/queued writer, postcommit cleanup cancel, primary-error/cleanup refusal/no duplicate-log.',
    '- Acceptance criteria:': 'met for scoped trusted-operator/per-store profile: validation failures preserve canonical latest DB/ledger and source; successful restore upgraded off-live; owned connections/candidate cleanup joined or visible typed refusal;145 adjacent/1483 offline final PASS; no deployment/private artifacts. Commit-after-cancel and config cross-file atomicity excluded.',
    '- Rollback method:': 'exact3 repair.patch reverse/check/reapply in disposable copy PASS;266 baseline/265 existing unchanged/D47D48 preserved. Keep latest actual DB; do not execute old unsafe restore against private/live data.',
    '- Risk:': 'per-store owner only; external writers/transactions, ZIP DB/config atomicity, hostile-schema attestation, OS-blocked IO SLO and powerloss unverified. At SQLite DONE, cancellation/cleanup error may coexist with committed data: inspect before retry.',
    '- Status:': 'DONE / VERIFIED (D49/FIX-013 bounded explicit-restore repair). Removes only BLOCKED_BY_FIX: FIX-013; RI-005 remains PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION for stopped owner/actual launcher/version/readiness/approval. No deployment.',
}
for prefix, value in replacements.items():
    entry, count = re.subn(r'^' + re.escape(prefix) + r'.*$', prefix + ' ' + value, entry, count=1, flags=re.MULTILINE)
    assert count == 1, prefix
text = text[:start] + entry + text[end:]
fix.write_text(text)
roadmap = ROOT / 'docs/runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md'
text = roadmap.read_text()
old = '- Status: PARTIAL（D48/FIX-012 code-only pointer＋latest data retention VERIFIED；1,442full/exact3）；BLOCKED_BY_FIX: FIX-013 explicit-restore prevalidation，且BLOCKED_BY_RELEASE_INTEGRATION：launcher真正consume/version/readiness／人工批准／stopped writer尚未驗；不是本輪deployment。[D48證據](../evidence/RI-005-2026-10-11/REPORT.md)。'
new = '- Status: PARTIAL（D48/FIX-012 code-only retention與D49/FIX-013 explicit restore局部VERIFIED；D49 final1,483full/exact3）；FIX-013 defect gate解除；BLOCKED_BY_RELEASE_INTEGRATION：stopped writer／launcher真正consume/version/readiness／人工批准未驗，非deployment。[D49證據](../evidence/FIX-013-2026-10-12/REPORT.md)。'
assert old in text
roadmap.write_text(text.replace(old, new, 1))
design = ROOT / 'docs/runtime-evolution/RUNTIME_INTELLIGENCE_DESIGN.md'
text = design.read_text()
old = 'FIX-013 explicit restore failure／stopped writer／人工批准／實際readiness仍block；不自動接線'
new = 'D49/FIX-013 explicit restore failure局部已VERIFIED；stopped writer／人工批准／launcher真正version/readiness仍block；不自動接線'
assert old in text
design.write_text(text.replace(old, new, 1))
report = OUT / 'REPORT.md'
text = report.read_text().replace('Status: IMPLEMENTED / FINAL_VERIFICATION_PENDING. Source and scoped verification are frozen; final full offline regression and final audit snapshot remain pending.', 'Status: VERIFIED — bounded explicit-restore component; final full offline regression completed. Final sensitive-audit snapshot pending.')
text = text.replace('Final full offline regression: PENDING (full-final.log).', f'Final full offline regression: **1483 PASS/5 real_provider deselected/3 existing warnings/{seconds}s** (full-final.log).')
text = text.replace('On final verification, remove only BLOCKED_BY_FIX: FIX-013', 'Final verification removes only BLOCKED_BY_FIX: FIX-013')
report.write_text(text)
(OUT / 'document-scope.json').write_text(json.dumps({'documents': paths + ['docs/CONTRACTS.md','docs/DECISIONS.md'], 'final_full_seconds': seconds}, indent=2) + '\n')
print(json.dumps({'documents_updated':len(paths),'FIX013':'DONE/VERIFIED','RI005':'PARTIAL/BLOCKED_BY_RELEASE_INTEGRATION','full_seconds':seconds}))
