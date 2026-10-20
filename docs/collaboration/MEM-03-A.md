# MEM-03-A 認領

2026-10-20 Asia/Taipei；Codex；LOCAL_VERIFIED（唯讀組件）／NOT_WIRED／LOCAL_ONLY／NOT PUSHED。
Base983012d86dd50419f8bc9dc5cfb5ee3f6d28e27b，branch codex/memory-mem03-source-gate-20261020，
managed worktree E:/coding/Worktrees/memory-mem03-source-gate/SiroV2。
原MEM02 worktree clean，原checkout八個語音dirty檔保留；fetch與公開issues/pulls空已查。
本機認領不是共享鎖；子任務依MEM01/RT014，不解除MEM02及MEM03產品gate。

Owned：src/siro/core/memory_sources.py、src/siro/persistence/memory_sources.py、
tests/integration/test_memory_source_gate.py、docs/memory-evolution/MEM-03-A-CONTRACT.md、
本檔、docs/evidence/MEM-03-A-20261020/、CONTRACTS／DECISIONS本卡附錄、PLAN本卡狀態。
不改Gateway/HTML/音訊/renderer、其他Memory程式、schema／migration／依賴／lockfile／STATUS。
STATUS由整合者更新；不push／PR／merge／部署、不讀私人DB。

目標：persisted UUID→Policy唯讀view→同交易event／session／identity／person／privacy／TTL／
撤銷及失效來源→可重驗snapshot。零候選／Memory寫入、零LLM／外送，metadata與repr無原文。
UserTextEvent.subject_id須由可信producer標明人物scope；現有未填事件拒絕，不補造owner。
Policy與Gateway adapter未接線，不能把synthetic policy／新格式fixture當現行服務整合完成。
驗收：真SQLite正反例、scope／privacy／TTL／撤銷／更正／policy變更與偽造snapshot、
無讀權不查DB、整體DB無新增資料、故障／timeout／取消；門檻與限制記入本卡REPORT。

結果：40專項與77相鄰回歸PASS（重疊）、兩種runtime mutant被4／3個負例抓到；
三檔Ruff／mypy／secret scan、schema export PASS。完整證據見../evidence/MEM-03-A-20261020/REPORT.md。
只有fake Policy＋真SQLite組件驗證，非真Auth／Gateway／完整候選流程；不解除主MEM03或MEM02 gates。
