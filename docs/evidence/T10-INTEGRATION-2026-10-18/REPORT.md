# T10-UI-01 整體整合驗收（2026-10-18）

**結果：可自動驗證的部分全部 LOCAL_VERIFIED；T10-UI-01 整卡仍 PARTIAL**，因為真人三輪體驗、讀屏、WSLg 桌寵實機、真聲音／真模型、跨機需要人工操作，見 [MANUAL_TEST_GUIDE](MANUAL_TEST_GUIDE.md)。

使用者要求「整個 T10 做完」，因此本輪連續處理 T10-UI-01 Acceptance 中剩餘的子項（REFLOW 已另見 [REFLOW REPORT](../T10-REFLOW-2026-10-18/REPORT.md)），不在子項間停下。

## 範圍與 MUST NOT CHANGE

只改 `static/index.html`（CSS＋前端回饋／重連邏輯）與新增測試。Core／Gateway／DB／schema／wire／API／config／授權、provider／voice 路由、renderer 資產、desktop／WSL 與使用中的 8000／Ollama 服務皆未改、未連線。

## 發現與修正

| # | 子項 | 實測發現 | 修正 |
|---|---|---|---|
| 1 | 對比（WCAG 1.4.11） | 四個文字輸入框外框只有 1.19–1.29:1（需 ≥3:1） | 新 `--field-line:#77849a`（白底 3.78:1）只用於 input／textarea／聊天框邊框 |
| 2 | 對比（真 renderer） | 角色區標語「今天，也陪著你。」為深藍字疊在 Live2D 深紫背景上，幾乎看不見；靜態頁因無 renderer 背景而漏抓 | `--stage` 改為與 renderer 一致的深色 `#2b2638`，標語改淺色（≥7.49:1）加淡陰影 |
| 3 | 鍵盤 | 角色 iframe 佔一個 Tab 停靠點但無焦點框、內部無可操作元件 | iframe `tabindex="-1"`（renderer 只有 canvas，已查證） |
| 4 | 焦點不被遮 | 窄窗下焦點元素可能停在 sticky 工具列下方 | `scroll-padding-top` 100px（≤480px 為 160px） |
| 5 | 錯誤／等待 | 停止開關 PUT 沒有處理中狀態；失敗被吞掉、非 2xx 仍重新整理 | 處理中鎖住按鈕並顯示「正在關閉…」；失敗顯示「可能尚未關閉，沒有自動重送」且不重新整理；只在確認成功後才 reload |
| 6 | 錯誤／等待 | 記憶更正／刪除失敗訊息寫進收合的「閒置整理」區，記憶頁看不到；處理中可連點 | 錯誤與處理中狀態改寫到記憶頁 `#memory-search-status`，處理中停用兩個按鈕 |
| 7 | 錯誤 | 「重新整理記憶」失敗只寫進收合區 | 同時在記憶頁狀態列顯示可重試的說明 |
| 8 | 斷線重連 | main 重啟後，已開頁面的控制 WebSocket 持續用快取的舊 token 認證，被 1008 拒絕，最長約 5 分鐘無法重連 | 只在**認證前**收到確切 `1008 invalid session token` 時丟掉該快取 token，下次重連取新 token；比照既有 HTTP 401 規則，不重送任何工作 |
| 9 | 版面 | 記憶搜尋表單無樣式，標籤黏住輸入框 | 只加間距 CSS |

靜態稽核另查：文字對比全頁通過（只剩停用中按鈕 3.24:1，WCAG 豁免）；語意色在所有背景 ≥5.25:1；所有彩色狀態都附文字，不只靠顏色。

## Tests run／Regression results

| 層級 | 命令／結果 |
|---|---|
| 新 `test_frontend_accessibility.py` | 2 PASS：九頁＋detail 文字對比／輸入框外框／placeholder；1280 與 320 寬整圈 Tab 有可見焦點、不在隱藏頁、不被完全遮住、iframe 不在 Tab 順序。修改前版本 2 FAIL |
| 新 `test_frontend_state_feedback.py` | 8 PASS：開關處理中→確認成功才 reload；503／網路失敗可見、只 1 次 PUT、不 reload；記憶更正／刪除失敗顯示在記憶頁、只 1 次請求；取消對話框不送出；重啟後只換被拒 token。修改前版本 6 FAIL（取消對話框與「其他原因不換 token」兩例本來就 PASS，用來守住原行為） |
| `test_frontend_reflow.py` | 2 PASS（REFLOW 切片） |
| 相關回歸 | `pytest -q tests/integration/test_frontend*.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/integration/test_goal_task_api.py tests/integration/test_goal_task_loop.py tests/integration/test_memory_search_api.py`：**525 PASS／3 既有 warnings／44.70s** |
| 桌寵相容 | `pytest -q tests/integration/test_desktop*.py`：**69 PASS／3 既有 warnings** |
| 靜態 | 新測試三檔＋acceptance.py：Ruff check／format、mypy PASS；inline JS `node --check` PASS；`git diff --check` PASS；detect-secrets 掃描新檔無發現 |

## 真 main 整合驗收（`acceptance.py`）

隔離環境：重用 D57 fixture，複製目前 src、合成帳號／工作目錄、自有 Rust runtime 與 SQLite（temp，結束後刪除並驗證複製的 source 未被改動）。模型是本腳本起在 127.0.0.1 的**合成 loopback OpenAI 相容 SSE**（固定回覆，不外送）。Renderer 是 Owner 依授權下載、存於 gitignored `models/` 的 Cubism Haru 範例（真 WebGL，headless Chrome＋SwiftShader）。

**9/9 PASS**（[STEPS.json](STEPS.json)、[SUMMARY.json](SUMMARY.json)、[run/RESULTS.json](run/RESULTS.json)）：

1. 真 Live2D 就緒、canvas 渲染；只有 1 條 `/ws/body`、1 條 `/ws/control`，renderer 只載入 1 次。
2. 九頁＋上一頁／下一頁換頁：0 個非 GET 請求、0 條新 socket、0 次 renderer 重新載入、沒有播放音訊。
3. 流程 1：對話→建立任務（讀取 0 次）→詳情→批准→閱讀完成（讀取 1 次，第 2／4 行來源可見）→返回清單→回對話，對話紀錄不變、無副作用。
4. 流程 2：聊天「記住：」建立記憶→搜尋 1 筆含來源與版本→更正（API 確認第 2 版）→刪除→API 確認為 0。
5. 流程 3：設定→權限→停止工具（伺服器端任務 `available=false`、建立鈕停用）→恢復（`available=true`），共 2 次 PUT、未觸發讀取。
6. 取消：串流中按「停止回覆與語音」，等 4.5 秒後半段未出現，模型只被呼叫 1 次。
7. 同頁斷線：停掉 main→顯示「連線中斷」→重啟→按重新連線→「已連線」，0 次重送、0 次額外模型呼叫。
8. 重啟後用 375px 新瀏覽器：已完成任務保留、讀取 0 次、已刪除記憶仍為 0、無重播。
9. 全程 0 個頁面 JS 錯誤。

修改前版本重現：第 7 步重連逾時（前 6 步 PASS），見 [prefix-reconnect-reproduction.txt](prefix-reconnect-reproduction.txt)。截圖：[01 真 Live2D](01-chat-live2d.jpg)、[02](02-task-detail-proposed.jpg)／[03 任務詳情](03-task-detail-completed.jpg)、[04 記憶搜尋](04-memory-search.jpg)、[05 刪除後](05-memory-deleted.jpg)、[06 停止工具](06-tools-stopped.jpg)、[07a 斷線](07a-disconnected.jpg)、[07](07-restart-375-tasks.jpg)／[08 重啟 375](08-restart-375-chat.jpg)。

## Acceptance criteria（T10-UI-01）

| Criterion | 判定 |
|---|---|
| 九頁與 detail 可達 | PASS（瀏覽器＋真 main） |
| 320／375／414／768 及 200% 等效 reflow | PASS（水平方向；REFLOW 切片） |
| 文字／功能對比、keyboard／focus | PASS（自動檢查範圍）；讀屏 NOT_VERIFIED |
| 三條日常流程可用 | PASS（自動操作）；「無工程師指導的真人」NOT_VERIFIED |
| 無導航重送／body 重啟／舊音 | PASS（真 main＋真 Live2D；音訊以「無播放中元素」判定，未開 TTS） |
| 舊 transport／cancel／session 相容 | PASS（525 回歸＋取消／重連真路徑） |
| 真人三輪 15 分鐘、跨機、讀屏 | NOT_VERIFIED → 整卡 PARTIAL |

## Known limitations

- 合成模型與 headless SwiftShader 不能代表真模型品質、GPU 效能或 WSLg WebKit 桌寵視窗；TTS／麥克風未開。
- 窄窗 sticky 工具列在 640×400 下，比可視高度還高的對話區會被部分遮住（WCAG AA 允許）。
- 停用中按鈕對比 3.24:1（WCAG 豁免），未調整。
- full `scripts/check`、正式部署 rollback、soak NOT_RUN。

## Rollback

只撤 `static/index.html` 本輪增量與三個新測試／本目錄。無 DB、migration、API 或部署變更；使用者資料不受影響。Baseline commit `bd63f28`；本輪結束時 index.html sha256 `7911ef2ffad5f4c54c1735d59cbe3c6bdf5485c498804805d4d5defbcc5e210e`。各修正可獨立撤回（CSS 變數、iframe tabindex、`#switch-status` 與 onclick、記憶 `change()`、`sessionAccess.invalidate`）。
