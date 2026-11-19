# CHECK-PYTEST-MYPY-RUFF-20261116

- Task: 修 `scripts/check` 在 ruff format 之後的三個 Python 阻擋：pytest 收集、mypy 重複模組、ruff check。不修約 69 個既有失敗測試，不改電腦操控路徑。
- Owner: Cursor cloud agent。時間：2026-11-16 UTC。狀態：PARTIAL（檢查可跑完；mypy / ruff check 仍被禁止路徑擋住）。
- Base SHA: `74c60f2e4f42a27208254df0ea4c61aad04d65d3`（PR #14，`cursor/ruff-format-non-computer-use-0942`）。
- 分支：`cursor/check-pytest-mypy-ruff-0919`。新 PR 的 base 是該分支，並 stack 在 #14。不合併。
- 排除：`src/siro/services/computer_use/`、`desktop-win/computer-*`、`input-helper.ps1`、`src/siro/core/computer.py`、`tests/unit/test_computer_use_*.py`。沒有為這些路徑加 ruff / mypy exclude。
- 沒有改 `docs/STATUS.md`（PR #13 列為擁有路徑）。交接在這份文件與 PR 說明。
- 與 PR #15（`cursor/claude-shared-budget-bbf9`）在獨立 worktree 試合併：只有 `src/siro/services/presentation/gateway.py` 一處內容衝突（`ProfileService` 的 `ClaudePlannerModel` 呼叫）。沒有改 #15，也沒有把合併留在本分支。
