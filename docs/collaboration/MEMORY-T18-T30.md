# MEMORY-T18-T30 — 驗證、缺陷修復與後續記憶規劃

2026-10-20 Asia/Taipei；Codex 本次 session；LOCAL_VERIFIED（元件修復）／PARTIAL（產品接線）／LOCAL_ONLY／NOT PUSHED。
使用者指示：驗證 T18/T30 後實作，再規劃上下文理解、自動記憶、主動記憶。
Branch codex/memory-t18-t30-20261020；worktree E:/coding/股票策略機器學習/SiroV2-memory-20261020。
Base b880ae9ec570d11fc5bb905c835d43445a2c6d13（本機驗收工具＋本機交付規範；產品基線137a561）。
子工作順序：T18既有驗收／反例修復→T30既有驗收／反例修復→產品入口與後續規劃。

Owned paths：src/siro/core/consolidation.py、src/siro/persistence/consolidation.py、
src/siro/core/procedural.py、src/siro/persistence/procedural.py、
tests/integration/test_consolidation.py、tests/integration/test_procedural_candidates.py、
tests/integration/test_memory_learning_guards.py、scripts/review_memory_candidates.py、
tests/integration/test_memory_candidate_review.py、docs/memory-evolution/、
docs/evidence/MEMORY-T18-T30-20261020/、本檔。
不改 Gateway/static、音訊、renderer、Runtime/skill執行、DB schema、依賴、lockfile。
原 checkout Gateway/static/音訊及相關測試有其他工作dirty，沒有接管或複製。
共享 STATUS/DECISIONS/roadmap 保留整合者，由本任務專屬文件提供狀態／設計決策交接。
不改公開產品契約；修復既有來源、獨立成功trace、secret脫敏與review-only約束。

Git fetch成功，公開issues/pulls皆空陣列，無分頁；修改前再查一次。
無遠端認領，本機紀錄非共享鎖。使用者已授權的隔離實作不推送、不開PR、不部署。
驗證使用WSL既有ext4 venv、合成資料、真SQLite，不讀私人DB或重啟服務。
每個修復須先有實際失敗反例，再跑相關回歸與lint/type；mock與SQLite/子程序各自註明。
回退本卡commit，不回復私人資料。歷史T18/T30 DONE保留，新增實證限定本輪範圍。

本輪結果：9個缺陷先重現後修復，41PASS／0SKIP、Ruff/mypy/精確secret掃描PASS。metadata-only CLI完成。
完整證據見 ../evidence/MEMORY-T18-T30-20261020/REPORT.md；後續計畫見 ../memory-evolution/PLAN.md。
Gateway/HTML尚無owner移交；使用者詢問衝突工作內容，已依實際diff說明為語音預熱／串流朗讀。未視為移交授權。
