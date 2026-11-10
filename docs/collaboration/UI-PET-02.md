# UI-PET-02 桌寵獨立頁

- Task：Phase 2。桌寵不再載入整份控制台，改成自己的輕量頁，契約不變。
- Owner／session：Cursor cloud agent，2026-11-10 UTC。
- 狀態：實作完成，待 PR。這張卡疊在未合併的 UI-LAUNCH-01（`cursor/win-launcher-cleanup-b58f`，PR #7）上。開始時該分支工作區乾淨。沒有另一張遠端鎖認領這範圍；本檔是交接。
- Base SHA：`58acf5b8b6f4dafdef68ecd6541a5eabada99541`（`cursor/win-launcher-cleanup-b58f`）。
- Branch：`cursor/desktop-pet-page-24cc`。實作 commit：`992affbbed858ceb77fb3e40fad672023624f128`。Worktree：這個 cloud agent checkout。
- 推送：使用者這次明確要求開一個 pull request，並寫明可疊在 PR #7。這是對 `docs/AI_COLLABORATION.md`「不得 push」的偏離，只針對這個分支與這一個 PR。不合併、不部署。

## 允許修改

- `src/siro/services/presentation/static/pet.html`、`pet.css`、`pet.js`（新）
- `src/siro/services/presentation/static/desktop.css`、`desktop.js`（刪除；只服務舊的控制台遮罩）
- `src/siro/services/presentation/gateway.py`（`/desktop` 改送 pet 頁；靜態檔改 `pet.css`／`pet.js`）
- `desktop/host.js`、`desktop-win/main.js`（註明 `/desktop` 是桌寵頁；網址不變。`main.js` 只動 `loadURL` 旁的註解，ComputerControl 接線不動）
- `tests/integration/test_desktop_web.py`、`tests/integration/test_desktop_host.py`
- `README.md`（桌寵操作一句）
- `docs/STATUS.md`（開頭一節）
- 本交接

## 排除

`desktop-win/computer-*`、`input-helper.ps1`、`src/siro/services/computer_use/`、`src/siro/core/computer.py`、`Play-SIRO.cmd`、`scripts/computer-play.sh`。`ensureCaptureHost` 與既有 ComputerControl 接線保持原樣。`renderers/vrm` 的動作邏輯不改。`index.html` 沒有桌寵專用 CSS／JS，控制台維持原樣，這次不改它。

## 行為

- 預設只有角色、偶爾一行氣泡，以及聽／想／說／錯誤的小狀態點。狀態來自連線、回合與播放，不再觀察隱藏 DOM。
- 說話、停止、更多只在滑過或右鍵時出現。免手動、朗讀、縮放、移動、控制台、暫藏、退出收在「更多」。
- 雙擊角色或 F2 打開半透明對話；Esc 停止並收起。
- 文字、按住說話、免手動、逐句朗讀與嘴型包絡、取消、活動氣泡、拖曳、縮放、走路、暫藏、開控制台、退出都還在。
- `/ws/body` 仍由 `/vrm/?presentation=desktop`（或 Live2D）iframe 自己連。父頁再連一次會搶走 desktop owner，所以沒有第二條 body socket。

## 驗收

- `uv run pytest tests/integration/test_desktop_web.py tests/integration/test_desktop_host.py`：34 passed。
- `uv run pytest tests/integration/test_desktop_entry_scripts.py tests/integration/test_desktop_settings.py tests/integration/test_frontend_navigation.py`：63 passed。
- `uv run pytest tests/integration/test_frontend_speech_cancel.py tests/integration/test_frontend_speech_queue.py tests/integration/test_frontend_microphone.py tests/integration/test_frontend_control.py tests/integration/test_frontend_mouth_sync.py`：75 passed。
- `uv run ruff check` 上述改過的 Python 檔：通過。
- `uv run mypy src/siro/services/presentation/gateway.py tests/integration/test_desktop_host.py tests/integration/test_desktop_web.py`：仍是 gateway 既有的 `render_stream`（1277）、`create_task`（2298）、`ProfileService`（2837）。這次新增的函式沒有新錯誤。
- 沒有改 Rust，沒有跑 cargo。
- 無頭 Chrome 對本機 gateway 截了兩張圖：連上後的佔位角色，以及滑過／選單打開的樣子。VRM 沒有載入，漸層背景只存在截圖裡。

## 未驗

Windows 上的 Electron 視窗、系統匣、拖曳與縮放；GTK／WebKit 桌寵；真的麥克風、免手動、TTS 播放與嘴型對真實角色。Linux 沒有這些執行環境。
