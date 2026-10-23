# CP-I01 Claude 側驗證（階段 1：回歸與摘要）— 2026-10-23，PARTIAL

只含 Claude 的 source／測試證據。Codex 視覺證據、owner 實機試用（見 `docs/companion-workflow/CP-I01-OWNER-TRIAL-DRAFT.md`）尚未取得，I01 不可標 DONE。

## 套件摘要（git 內容 hash，與換行無關；不含 secret）

- source commit：`7ff0996e4b67470c3ef25bc04a382f2491a3fb42`（分支 `claude/cp-o01-process-network`，未 push）
- `git ls-files -s <path> | sha256sum` 前 16 碼：assets `ff71c3c4dbf0b2a2`、config `2c80d255c01b415b`、src `006015831ccb4d64`、renderers `5794f912b2013e60`、全 repo `7b994fc8a3e904a7`
- 注意：該分支共用 checkout 另有其他串的未 commit 修改（process_execution、monitor、gateway、index.html 等），本摘要與測試只涵蓋已 commit 的 HEAD，不含那些修改。

## 測試

環境：WSL，`git archive HEAD` 匯出到乾淨目錄，`UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2 uv run --offline pytest -q`。

結果：**2494 passed／47 failed／20 skipped**（291 秒）。skipped 多為缺 cargo 產物、`npm ci`（renderers/vrm）、opt-in 外部供應商測試。

失敗比對：把同一批 47 個失敗的檔案放在 P05 之前的 `b382c0c` 同樣匯出方式重跑，**失敗的測試完全相同（47 個）**，所以不是 P05／P06 之後引入的回歸。失敗集中在 test_native_context_budget、test_skill_registry、test_skill_worker_lifecycle、test_goal_task_*、test_desktop_snapshot_privacy、test_gateway_main、test_tool_catalog、test_runtime_product、test_workspace_runtime、test_capability_product、test_skill_package_identity。

## 限制

- 先前 P05 回報的「33 失敗」與這次 47 不同：兩次環境不同（這次是不含 ignored 檔案的匯出，缺 rust 產物、`.venv/bin/siro-gateway`、node 依賴），失敗根因沒有逐一判定，只確認「P05 前後相同」。這 47 個是否在 owner 完整環境也失敗，未驗；I01 前需在完整 checkout 重跑。
- 只在 WSL 跑。Windows 原生、WSLg 之外的環境、跨機沒驗。
- 沒有啟動服務、沒有 journal／工具／音訊／程序層實測，也沒有已知失敗（T10 取消／刷新）的真環境重測。
