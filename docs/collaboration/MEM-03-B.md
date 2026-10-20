# MEM-03-B：離線內容篩選與有來源候選生成

Codex，2026-10-20 Asia/Taipei，LOCAL_VERIFIED（離線組件）／LOCAL_ONLY／NOT_WIRED。
Base d1e7d6b2216dd7d3120dac4b355f72d7bfade587；managed worktree
E:/coding/Worktrees/memory-mem03-candidates/SiroV2；branch codex/memory-mem03-candidates-20261020。
已讀STATUS／SOL_RUNBOOK／PLAN／MEM03-A契約／SECURITY_PRIVACY／EXPERIENCE／ACCEPTANCE。
fetch完成，公開issues/pulls均空、無分頁；原checkout八個音訊dirty檔保留。
本機認領非跨機共享鎖，開改前工作區clean。

Owned：src/siro/core/memory_candidates.py、tests/integration/test_memory_candidates.py、
tests/fixtures/automatic_memory_candidates.json、本檔、docs/memory-evolution/MEM-03-B-CONTRACT.md、
docs/evidence/MEM-03-B-20261020/。不改其他Core／Gateway／UI／schema／依賴／共享STATUS與PLAN。
狀態由整合者納入共享文件；不改運行服務、不讀私人DB、不push／PR／merge／部署。

按一次一子任務拆出必要內容篩選層：MEM03-A→來源→有界本機規則→原句候選→來源／Policy重驗。
只離線合成測試，MEM02未過27/30，仍禁止正式producer／自動保存啟用；主MEM03依賴不豁免。
本卡不取代主MEM03：持久審核／編輯／拒絕／刪除／關閉UI、啟用類型／retention、batch owner／
cancel join、原子採用／MEM01 lineage、真Auth adapter仍是後續必做，不能把本卡完成當產品完成。

結果：固定64組內容＋6個混合中英漏判反例、144本卡測試，最終284回歸PASS／0 skip，
兩種runtime故障注入被12／6個負例抓到。Ruff／scoped mypy／schema check PASS，
scoped secret scan零finding；全庫checker結果依REPORT補充，不能宣稱全套check通過。
source marker與Policy仍未接正式服務，主MEM03／MEM02 gate不解除。證據與限制見
../evidence/MEM-03-B-20261020/REPORT.md；只本機commit，未push／PR／部署。

驗收：至少60組合成正反例與真SQLite來源整合；無寫入／無外送，來源失效／Policy改變／
TTL／錯scope／偽造候選拒絕，取消傳遞；候選不自證fact／completion／write grant。
