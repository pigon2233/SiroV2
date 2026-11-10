# UI-PET-03 桌寵快捷列

- Task：把桌寵快捷從鋪在角色身上的文字膠囊，改成側邊圓鈕與一塊磨砂面板。疊在未合併的 UI-MOTION-03（`cursor/motion-cues-1cc5`，PR #10）。
- Owner／session：Cursor cloud agent，2026-11-10 UTC。
- 狀態：實作完成。PR https://github.com/pigon2233/SiroV2/pull/12 ，base 是 `cursor/motion-cues-1cc5`，疊在 PR #10 上。開始時該分支工作區乾淨，HEAD `cc203911b5cc69bf3f3d7f8c3c94877ec6bd4c00`。當時開放 PR 為 #7、#8、#10、#11。#11 是主人的 VRM 模型，沒有改桌寵頁。本檔是交接，不是鎖。
- Base SHA：`cc203911b5cc69bf3f3d7f8c3c94877ec6bd4c00`（`cursor/motion-cues-1cc5`）。
- Branch：`cursor/pet-dock-259d`。實作 commit：`8c987d2deb8c020a0a5d3bb70eefbec9f800dce1`。Worktree：這個 cloud agent checkout。
- 推送：使用者這次明確要求開一個新的 PR，base 為 `cursor/motion-cues-1cc5`，並疊在 PR #10。這是對 `docs/AI_COLLABORATION.md`「不得 push」的偏離，只針對這個分支與這一個 PR。不合併、不部署。

## 允許修改

- `src/siro/services/presentation/static/pet.html`、`pet.css`、`pet.js`
- `tests/integration/test_desktop_web.py`
- `docs/STATUS.md`（開頭一節）、本交接

## 排除

`desktop-win/computer-*`、`input-helper.ps1`、`src/siro/services/computer_use/`、`src/siro/core/computer.py`。後端與 VRM 動作邏輯不改。`siro.gesture`／`siro.sfx` 的 postMessage 維持 PR #10 的接法。

## 行為

- 圓鈕在角色旁邊，用 `screenSide()`：視窗在螢幕右側時靠左，否則靠右。不蓋臉、不蓋身體。
- 說話、聊聊、更多常駐。停止只在聆聽、辨識、回覆、工具或朗讀時出現，在說話鈕上面。
- 滑過或聚焦後約 2 秒淡出。選單開著、麥克風錄音中、或回覆／工具／朗讀進行時保持可見。過渡約 180ms，`prefers-reduced-motion` 時不做位移與過渡。
- 更多面板：語音（麥克風、免手動、朗讀、再聽一次）用 `aria-pressed` 表示開或關，不再寫「：開／關」。大小維持 －／百分比／＋。動作預設收在 `<details>`。視窗一列：移動、控制台、暫藏、退出，退出較淡。
- 右鍵角色仍只開這一個選單。Esc 仍停止並收起。點角色（左鍵）或點面板外面會收起選單。
- 既有按鈕 id 與點擊／拖曳處理都還在。頁面背景維持透明。

## 驗收

- `PYTHONPATH=src python3 -m pytest tests/integration/test_desktop_web.py`：29 passed。
- `ruff check` 與 `ruff format --check` `tests/integration/test_desktop_web.py`：通過。
- `node --check src/siro/services/presentation/static/pet.js`：通過。
- `tests/integration/test_desktop_entry_scripts.py`：42 passed，1 failed。失敗是安裝腳本要求 `uv`，這個環境沒有 `uv`，不是這次的介面。
- `test_desktop_host.py` 未跑：沒有專案 venv，`create_app` 的匯入鏈不完整。
- 無頭 Chrome 420×640、深色底。角色是佔位，不是 VRM。沒有真的麥克風、TTS、Electron 或 GTK。

## 回退

撤掉這個分支即可。快捷又回到 PR #10 的文字膠囊。
