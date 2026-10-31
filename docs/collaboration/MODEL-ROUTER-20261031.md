# MODEL-ROUTER-20261031

Task: 依任務選擇對話模型（Claude，其次 Groq，再次本機 Ollama）。
Owner: Cursor cloud agent（本輪）。
時間: 2026-10-31 UTC。
狀態: 實作與自動測試；使用者本輪明確要求開 PR，因此偏離預設的 LOCAL_ONLY／NOT PUSHED。

## 基線

- Base SHA: 591e1c55b3062fe516bea20280a02091a8c5e9da
- Branch: cursor/task-model-router-5c6c
- Worktree: 本 cloud agent checkout

## 允許修改

- src/siro/adapters/models/router.py
- src/siro/adapters/models/claude_cli.py
- src/siro/services/presentation/gateway.py（只接模型選擇與路由通知）
- src/siro/services/presentation/integrated.py（這一輪的隱私與通知）
- src/siro/services/presentation/static/index.html（模型狀態與通知）
- scripts/launch_companion.py（.env.local 允許讀新變數）
- tests/unit/test_model_router.py
- tests/integration/test_frontend_route_notice.py
- tests/integration/test_companion_launcher.py
- .env.example
- docs/MODEL_ROUTING.md
- docs/DECISIONS.md（D81）
- docs/CONTRACTS.md（對應小節）
- docs/STATUS.md（本段）
- 本檔

## 排除

desktop-win/computer-*、src/siro/services/computer_use/、core/computer.py、
input-helper.ps1。那些檔案這輪沒有改。

## 驗收

已跑（合成 provider，不是真 Groq／真 Claude CLI）：

- ruff check：變更的 Python 檔通過
- mypy：router.py、claude_cli.py、test_model_router.py、launch_companion.py 通過。
  gateway.py／integrated.py 仍有改動前就存在的錯誤
- pytest tests/unit/test_model_router.py tests/integration/test_frontend_route_notice.py
  tests/integration/test_companion_launcher.py tests/integration/test_provider_retry.py
  ：24 passed

遠端 Issues／PR 這輪沒有當成鎖；使用者已明確要求開 PR。
