# T01-ACCEPTANCE-01 認領

2026-10-20 Asia/Taipei，owner：本次 Codex session，DONE／LOCAL_VERIFIED／LOCAL_ONLY。
使用者指定自動化測試與驗收框架，僅本機 commit，不 push。
Base：34860f1d3ac6decf8c8708ea355d89eae9f3aefa（含前次規範；產品基線 origin/main 137a561）。
Branch：codex/acceptance-receipts-20261020。
Worktree：E:/coding/股票策略機器學習/SiroV2-acceptance-20261020。
Owned paths：scripts/run_acceptance.py、tests/test_acceptance_runner.py、
docs/testing/ACCEPTANCE_RUNNER.md、docs/evidence/T01-ACCEPTANCE-01/REPORT.md、本檔。
不修改 scripts/check、CI、共享 STATUS/TASKS、renderer、Runtime、依賴與 lockfile。
共享狀態交由整合者由本任務 evidence 納入。

現況：scripts/check 已包含 locked sync、Rust、lint/type、pytest、schema 與 secret checks；
缺少可供局部驗收統一記錄 commit/dirty、命令、證據層、skip 與非成功退出的機讀 receipt。
本卡作 T01 工程工具補強，不新增 CP 產品功能、不繞過 CP-00 的產品依賴。
GitHub issues/pulls 公開 API 均空陣列；已 fetch。已知 Claude 視覺分支仍視為占用。
開始實作前核對兩次遠端並檢查 worktree；未做遠端認領，本機文件不是共享鎖。

驗收：真 pytest subprocess 的通過、失敗、skip/xfail、空收集、收集錯誤、
無效目標與避免覆寫舊證據；同一 runner 執行既有 deterministic 測試。
不得以 pytest rc=0 就把 skip 算 PASS，不將 L1 宣稱 L2/L3，禁止空結果 PASS。
無新依賴／安裝，重用 WSL 現有 Python/pytest，cache 留 ext4。
回退：revert 本卡 commit，不影響產品資料。

結果：19項工具測試＋14項既有測試＝33 PASS；lint/type通過。完整證據見 ../evidence/T01-ACCEPTANCE-01/REPORT.md。
