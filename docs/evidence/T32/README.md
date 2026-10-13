# T32 驗收證據

日期：2026-09-26｜結果：PASS（L1 isolated release）

`ReleaseManager` 先驗證 bundle tree SHA-256 與 HMAC signature，拒絕不相容 schema，並在 staging 前以
SQLite backup API 產生 integrity-checked snapshot。healthcheck 只在 staging 副本執行；成功才原子寫入
`active.json`，先前 active 與其啟用前資料庫 snapshot 會保存於 `last-known-good.json`。回滾先驗證並
恢復該 SQLite snapshot，再切回舊版。失敗 healthcheck、不相容 migration、無效 manifest 或 activate
中斷均保持舊版 active。

`siro release stage --release-root … --bundle … --manifest … --healthcheck '["argv"]'` 從指定環境變數
讀 signing key；`siro release rollback` 回到 last-known-good。key 不寫入 manifest、輸出或報告。

`tests/integration/test_release_manager.py` 實測 v1 成功、v2 healthcheck 失敗、不相容 schema、v2 成功和
rollback 到 v1，並檢查啟用前 SQLite 資料的備份。完整 `scripts/check`：Python 125 passed、5 external
opt-in skipped；Rust 6 passed。

2026-09-26 全面稽核新增資料變更後 rollback 驗證，以及 activate 寫入中斷的 fault injection；兩者均
保持 last-known-good 與資料一致。執行 release manager 前必須停止其他資料庫 writer。
