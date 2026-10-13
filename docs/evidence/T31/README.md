# T31 驗收證據

日期：2026-09-26｜結果：PASS（L1 isolated workspace）

`PatchVerifier` 的不可信 proposal 只接受 unified diff；驗證命令由可信任 verifier 建構時設定。它先擷取
所有目標路徑並拒絕 `authorization.py`、設定 policy 檔、`.git` 或 path traversal，再將專案複製到
temporary workspace，在副本以 `git apply --check`/`git apply` 套用；原工作樹在前後做完整 tree digest 核對。

`tests/integration/test_patch_verifier.py` 實測：一個修正通過、一個壞 patch 失敗、以及一個
修改 permission policy 的 patch 在套用前拒絕。三者都不改 production fixture。完整
`scripts/check`：Python 124 passed、5 external opt-in skipped；Rust 6 passed。

2026-09-26 全面稽核修正：`workspace_removed` 現在在回傳報告中正確為 `true`；Python 的
`finally` 會在呼叫者收到報告前刪除 temporary workspace。proposal 原可自帶任意 check command，可能
從隔離目錄外產生副作用；現已移除該欄位，測試命令只能由可信任 verifier 注入。
