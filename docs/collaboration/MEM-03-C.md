# MEM-03-C 持久審閱認領

Codex／2026-10-20 Asia/Taipei，LOCAL_VERIFIED（L1組件）／LOCAL_ONLY／NOT_WIRED。
Base96cd2e21194d6c47a0d6cdc0906c7e68d622e362，codex/memory-mem03-review-20261020，
managed worktree E:/coding/Worktrees/memory-mem03-review/SiroV2。原B worktree clean。
已讀STATUS、SOL_RUNBOOK、PLAN、A/B契約、EXPERIENCE、SECURITY_PRIVACY、ACCEPTANCE與協作規則。
fetch成功，公開issues/pulls空、無Link分頁；本機認領非共享鎖。原checkout其他owner dirty檔保留。

Owned：src/siro/core/memory_review.py、src/siro/persistence/memory_review.py、
src/siro/persistence/memory_sources.py（提取同交易inspect helper）、
src/siro/persistence/migrations/017_memory_candidate_review.sql、tests/integration/test_memory_review.py、
本檔、docs/memory-evolution/MEM-03-C-CONTRACT.md、docs/evidence/MEM-03-C-20261020/、
CONTRACTS／DECISIONS僅MEM03-C附錄。不改舊migration、其他Core／SQLiteStore／Gateway／UI／
音訊／release／依賴／lockfile／STATUS／PLAN。共享狀態交整合者更新；不讀私人DB、不改運行服務，
不push／PR／merge／部署。新schema17只測合成DB，舊manifest的schema上限仍阻擋。

目標：既有Memory candidate＋審閱metadata／action readback；stage／approve／reject／withdraw／
以新owner來源替換編輯，scope＋revision CAS、原子來源重驗、索引／revisions一致、失效不復活。
可信Policy lease預設拒絕，持有到SQLite交易完成，取消join、未知結果不盲目重送。
MEM02與主MEM03 gate不解除；無真Policy lease adapter／Gateway／UI正式啟用。

相鄰411 regression首輪410 PASS／1 FAIL：MEM01升級fixture仍只預期最後一版16。
擴充owned tests/integration/test_memory_derivation_bindings.py，僅15→17版本列表與舊release
schema測試的實際DB版本／命名；保留舊checksums、資料／衍生邊、舊manifest拒絕與DB不變檢查。
該檔是本聊天MEM01原成果、原checkout無該路徑dirty／新競爭認領，未移除或降低負例。

交付：44專項、最終411回歸PASS／0 skip；source binding與取消join故障注入被2／1負例攔下。
Ruff／scoped五檔mypy／schema export PASS，十個路徑secret scan零finding；非全庫check成功。
新增schema17，只測合成DB；明確owner approve才索引，原子ledger／版本、來源重驗與取消readback已驗。
真Policy lease／Gateway／UI未接線，MEM02及主MEM03 gate保留。共享STATUS／PLAN交整合者更新；
完整證據、失敗歷程、限制、回退及下一步見../evidence/MEM-03-C-20261020/REPORT.md。
