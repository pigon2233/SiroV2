# T10 中文 IME 輸入修復

日期：2026-10-18。使用者回報 SIRO 無法輸入中文。聊天輸入框原本只檢查 `KeyboardEvent.isComposing`；有些 Chromium/WebKit 輸入法在選字 Enter 上沒有可靠地設此旗標，會觸發 `requestSubmit()`，並清空輸入內容。

## 修改

`src/siro/services/presentation/static/index.html` 現在追蹤輸入框的 `compositionstart`／`compositionend`，blur 時清除組字狀態；組字期間、`isComposing` 為真或舊事件 `keyCode/which` 為 229 時，不攔截 Enter。正常 Enter 仍送出，Shift+Enter 仍保留換行。

新增 `tests/integration/test_frontend_ime.py`，執行正式頁面內的按鍵監聽器，涵蓋組字期間 Enter、兩種 229 相容欄位、`isComposing` 旗標、組字完成後 Enter 和 Shift+Enter。

## 驗收

| 證據 | 結果 |
|---|---|
| 新部署快照 `3f50058d45381eedf0093322991760408708327682d4bbabe296d45b78bd5e07` | 三方 source identity verified；`uv sync --locked --all-groups --python 3.12 --compile-bytecode`、source/scripts/tests compileall、`cargo build --workspace --locked` 均 exit 0。 |
| 精確快照 IME 回歸 | `pytest -p no:cacheprovider -q tests/integration/test_frontend_ime.py`：**1 PASS／0.16s**。 |
| 精確快照前端整合回歸 | `pytest -p no:cacheprovider -q tests/integration/test_frontend_*.py`：**352 PASS／39.30s／exit 0**。 |
| 靜態檢查 | Ruff check、Ruff format check、`git diff --check` 均 exit 0。 |
| 服務實際送出的 `/desktop` 頁面 | HTTP 200；119,236 bytes；`chatInputComposing` 與 `event.keyCode === 229` 均存在。 |
| Windows `Start-SIRO.cmd` | 部署入口檢查 PASS；health `healthy`；唯一 native PID 87599；模型 `ollama:qwen3:4b-instruct`、audio `local:faster-whisper-small`、body `websocket`、TTS `local:qwen3-tts-0.6b-base:siro-sweet-b-v1`。使用原本資料目錄與 Live2D 資產。 |

舊 backend PID 80765 與 native PID 80741 先依來源快照確認 ownership，再以 SIGTERM 正常關閉；切換後服務仍使用同一 WSL 使用者資料、模型與 Live2D 資產。rollback 設定和入口副本保存在本機忽略資料 `.siro-data/wsl-setup/ime-rollback-20261018/`。沒有讀寫私人對話、開啟麥克風或更動授權／provider 設定。

## 限制

鍵盤測試使用合成 DOM events，已驗證按鍵判斷與送出行為，但沒有在原生視窗以真人實際操作注音／拼音候選字。請使用者在目前已重啟的視窗試打；若問題仍在，需取得輸入法名稱及「組字、選字、按 Enter」哪一步失效，再追查 WSLg/WebKit 輸入法整合。Windows `uv` 因沒有本機 Python 3.14 且設定 offline 無法執行；產品與測試實際以 WSL 專用 Python 3.12 執行。完整 `scripts/check`、remote CI 未跑。

部署快照建立於本報告及最後 `STATUS.md`／`TASKS.md` 更新之前；快照包含 production HTML、回歸測試與當時 workspace，其 hash 及部署實況已在本報告記錄。
