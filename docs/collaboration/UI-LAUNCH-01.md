# UI-LAUNCH-01 Windows 桌寵單一入口

- Task：Phase 1 UI cleanup。單一使用者入口 `Start-SIRO-VRM-Win.cmd`，修正活動頁路由與系統匣／工作列不一致。
- Owner／session：Cursor cloud agent，2026-11-10 UTC。
- 狀態：實作完成，待 PR。GitHub 未結 Issue 與未合併 PR 在開始時皆為空。沒有遠端認領鎖；本檔是交接。
- Base SHA：`36bbb806c6f22c8054dc6426554b45c963a5e5cb`（`origin/main`）。
- Branch：`cursor/win-launcher-cleanup-b58f`。Worktree：這個 cloud agent checkout。開始時工作區乾淨。
- 推送：使用者這次明確要求開一個 pull request，cloud agent 作業也要求推送。這是對 `docs/AI_COLLABORATION.md`「不得 push」的偏離，只針對這個分支與這一個 PR。不合併、不部署。

## 允許修改

- `Start-SIRO-VRM-Win.cmd`、`Stop-SIRO-Win.cmd`
- `scripts/start-win-backend`、`scripts/stop-win-backend`、`scripts/relaunch-win-hidden.ps1`、`scripts/show-win-notice.ps1`
- `scripts/start-esp32-broker.ps1`（只改 broker `.cmd` 的路徑）
- `scripts/legacy/`（由根目錄移入的舊啟動器）
- `scripts/launch_companion.py`（只加 `SIRO_VRM_VARIANT=candidate`）
- `src/siro/services/presentation/static/index.html`（`#/activity` 別名）
- `src/siro/services/presentation/static/desktop.js`（暫藏提示、控制台只在點擊時開）
- `desktop-win/main.js`（桌寵 `skipTaskbar` 與活動頁註解；不動 computer-use）
- `desktop-win/preload.js`（標示 electron host）
- `README.md`、`docs/WSL_SETUP.md`、`docs/runtime-evolution/PRODUCT_QUICKSTART.md`
- `docs/STATUS.md`（本任務只在開頭加一節）
- 對應測試與本交接

## 排除

`desktop-win/computer-*`、`input-helper.ps1`、`src/siro/services/computer_use/`、`src/siro/core/computer.py`、`Play-SIRO.cmd`、`scripts/computer-play.sh`、`enable-computer-control.sh`、`_start_capture.sh`、`*undertale*`、`verify_computer_*`。`ensureCaptureHost` 與既有 ComputerControl 接線保持原樣。

## 驗收

- `bash -n scripts/start-win-backend scripts/stop-win-backend`：通過。
- 相關 pytest（啟動器、companion launcher、desktop、navigation、activity）：65 passed。
- `scripts/check` 的 cargo fmt／build／test／clippy：通過（24 runtime tests）。
- `ruff format --check` 與 `ruff check .`：失敗在既有檔，含電腦操控檔。這次沒有改那些檔。
- 完整 mypy：既有重複模組名錯誤。這次四個測試檔 mypy 通過。
- `PYTHONPATH` 下全套 pytest：3362 passed、59 failed、126 skipped。失敗不在這次改的測試。
- 未驗：Windows 上雙擊 `.cmd`、隱藏主控台、Electron、MessageBox、真的 ESP32 broker。
