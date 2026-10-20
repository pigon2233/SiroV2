# MEM-02 認領

2026-10-20 Asia/Taipei；Codex；PARTIAL／HARD_GATES_LOCAL_VERIFIED／WAITING_MODEL_CONFIGURATION／LOCAL_ONLY／NOT PUSHED。
使用者持續目標「一直做下去」，延續MEM01後的整個記憶計畫，不以本卡取代全目標。
Base 259fddacb9c585de3c5c4a7ae3ac6a111539cd00；branch codex/memory-mem02-20261020；
worktree E:/coding/股票策略機器學習/SiroV2-mem02-20261020。
Owned paths：src/siro/core/{context.py,companion.py,conversation.py,memory.py}、
src/siro/persistence/memory.py、tests/integration/test_context_understanding.py、
tests/fixtures/context_understanding.json、scripts/evaluate_context_understanding.py、
docs/DECISIONS.md D77附錄、docs/CONTRACTS.md附錄、docs/memory-evolution/PLAN.md、
docs/evidence/MEM-02-20261020/、本檔。
不改Gateway/static/音訊/renderer/依賴/lockfile/schema；原checkout的8個語音dirty檔保留。
共享STATUS留整合者由本報告納入。Git fetch成功，issues/pulls公開API空陣列；修改前再查。
本機紀錄不是共享鎖；無遠端認領，不push、不PR、不部署、不讀私人對話DB。

目標：typed/data-only上下文、中文／追問的有界語境檢索、短期privacy隔離、
pre-dispatch來源重驗、原native history/pending tools不裁改。接現有Core caller，無第二planner或memory store。
固定30組合成多輪資料，確定性capture與來源/授權硬gate；語義模型評測單獨報，不把mock答案算理解。
驗收：來源更正/撤銷在checkpoint與dispatch間變更時零provider dispatch、cloud不含local資料、
原cancel/session restore/context budget/native tools相鄰回歸。真provider只用合成資料與已有授權profile，
若缺配置或quota誠實保留語義gate，繼續其他可執行工作，不自造綠燈。

結果：Core接線／來源fence與30case capture已驗，114回歸＋44專項＋5switch通過（有重疊）。
模型27/30未跑；見 ../evidence/MEM-02-20261020/REPORT.md。持續目標active，不重定義完成。

續作：2026-10-20，基線1a45022；修正真模型聚合讓29/30掩蓋虛構授權／錯報完成的漏洞。
認領路徑不擴張；遠端issues/pulls空、fetch已查，原八個dirty檔保留。
新增五反例、整檔49 PASS；capture30/30、real仍BLOCKED_CONFIG；報告有可重現證據。
依原零越權要求明訂獨立semantic hard gate，不降低27/30理解目標。LOCAL_ONLY／NOT PUSHED。
