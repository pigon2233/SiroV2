# MEM-01 認領

2026-10-20 Asia/Taipei，Codex本次session，DONE／LOCAL_VERIFIED（本機儲存契約）／LOCAL_ONLY／NOT PUSHED。
使用者授權依後續計畫實作；一次完成MEM-01，依賴4b901ac T18/T30修復已滿足。
Base 4b901ac3a21f327a984fa9c7d0e8f8b42c60417a；branch codex/memory-mem01-20261020；
worktree E:/coding/股票策略機器學習/SiroV2-mem01-20261020。
精確owned paths：core/memory.py、persistence/memory.py、persistence/consolidation.py、
persistence/migrations/016_memory_derivation_bindings.sql（皆位於src/siro/）、
tests/integration/test_memory_derivation_bindings.py、docs/DECISIONS.md本輪附錄、
docs/CONTRACTS.md本輪附錄、docs/memory-evolution/PLAN.md狀態、
docs/evidence/MEM-01-20261020/、本檔。
共享STATUS.md留整合者依本任務evidence更新；不改Gateway/static/音訊/renderer/依賴/lockfile。
目前原checkout仍有語音常駐worker／串流朗讀的8個dirty檔，未接手。
Git fetch成功、公開issues/pulls皆空陣列；不是遠端認領或共享鎖。

目標：真SQLite記憶→衍生候選／摘要鏈，correct/delete/source revoke後失效；
採用前交易核對parent revision/hash、scope、原event、時間／隱私；無自動啟用寫入producer。
先寫契約／ADR與失敗測試，再實作。新schema16不改舊migration；舊release須服從actual-schema gate。
驗收包含升級、重啟、重建索引、來源變更與adopt競態、雲端不可見、不跨scope與不留半寫入。
只用合成資料與既有WSL/ext4環境，不讀私人DB、不部署、不push。

結果與限制：../evidence/MEM-01-20261020/REPORT.md；MEM02–06仍PLANNED。原語音dirty檔保持。
