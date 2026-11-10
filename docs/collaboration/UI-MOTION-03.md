# UI-MOTION-03 回覆動作 cues 與程序化動作

- Task：Phase 3。回覆驅動的動作／表情 cue，以及可和片段疊加的程序化動作。疊在未合併的 UI-PET-02（`cursor/desktop-pet-page-24cc`，PR #8；其下是 PR #7）。
- Owner／session：Cursor cloud agent，2026-11-10 UTC。
- 狀態：實作完成，待 PR。開始時該分支工作區乾淨，HEAD `b3605c3c47c90d741b34559071645dda8195db5f`。開放 PR 只有 #7 與 #8，沒有另一張卡認領 renderer 動作或 body cue。本檔是交接，不是鎖。
- Base SHA：`b3605c3c47c90d741b34559071645dda8195db5f`（`cursor/desktop-pet-page-24cc`）。
- Branch：`cursor/motion-cues-1cc5`。實作 commit：`6832269f50deadf9ecf4928d23747eca1cf90f54`。Worktree：這個 cloud agent checkout。
- 推送：使用者這次明確要求開一個 PR，目標分支 `cursor/desktop-pet-page-24cc`，並寫明疊在 PR #8。這是對 `docs/AI_COLLABORATION.md`「不得 push」的偏離，只針對這個分支與這一個 PR。不合併、不部署。

## 允許修改

- `src/siro/core/motion_cues.py`（新）、`src/siro/core/companion.py`、`src/siro/core/conversation.py`、`src/siro/core/memory.py`
- `src/siro/ports/body.py`、`src/siro/adapters/body/web.py`
- `src/siro/services/presentation/integrated.py`
- `src/siro/services/presentation/static/pet.js`、`index.html`
- `renderers/vrm/src/main.js`、`renderers/vrm/src/procedural.js`（新）、`renderers/vrm/test/procedural.test.js`（新）、`renderers/vrm/BEHAVIOUR.md`、`renderers/vrm/package.json`
- `tests/test_motion_cues.py`（新）、`tests/contract/test_body_adapter.py`（這次沒改它；cue 對應在 `tests/test_motion_cues.py`）
- `tests/integration/test_desktop_web.py`（走路橋接的斷言改成只數 `siro.desktop.walk.state`，因為頁面現在也會送 `siro.attention`）
- `docs/STATUS.md`、`docs/DECISIONS.md`、本交接

## 排除

`desktop-win/computer-*`、`input-helper.ps1`、`src/siro/services/computer_use/`、`src/siro/core/computer.py`、`Play-SIRO.cmd`、`scripts/computer-play.sh`。不新增動作片段，也不改 `assets/companion/siro-vrm` 的授權檔。

## 驗收

- `uv run pytest tests/test_motion_cues.py tests/contract/test_body_adapter.py tests/integration/test_desktop_web.py tests/integration/test_persistent_companion.py::test_runtime_offline_does_not_disable_core_conversation`：通過。cue 測試含標記拆開、不進聊天／記憶／turn 紀錄、旗標關閉、後備手勢、body 訊息。
- `uv run ruff check` 與 `ruff format --check` 這次改的 Python 檔：通過。
- `uv run mypy` 對 `motion_cues.py`、`companion.py`、`conversation.py`、`ports/body.py`、`adapters/body/web.py`：通過。`integrated.py` 仍是原先的 reply bool／`unavailable_hint`，不在這次新增的函式。
- `node --test renderers/vrm/test/procedural.test.js`：4 passed。`node --check` 過 `main.js`、`procedural.js`、`pet.js`；`index.html` 的 script 可被 `new Function` 解析。
- `prepare_vrm_renderer.build_renderer`（暫存目錄）：成功，輸出含 `src/procedural.js`。
- 沒有改 Rust，沒有跑 cargo。沒有呼叫 Groq、Claude 或本機分類器。

## 未驗

Linux 沒有載入主人的 VRM、真的麥克風、TTS、Electron 或 GTK。無頭 Chrome 只畫了程序化手臂（點與伸手），不是角色本體。SpringBone、片段交叉淡化與聽的時候的歪頭沒有在畫面上看過。`wave`／`bow`／`bye` 仍是 CC BY-NC，沒有替換。

## 回退

撤掉這個分支即可。`SIRO_MOTION_CUES=0` 讓提示、刪標記與後備 cue 都停，renderer 回到用正文猜手勢。
