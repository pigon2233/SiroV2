# T10-UI-01 真人驗收後修正（2026-10-18）

**結果：使用者驗收列出的三個優先問題已修，或已定位並修掉可重現的部分。T10-UI-01 整卡仍是 PARTIAL**：必須在重新啟動的服務上人工重測，其餘人工項目也還沒做完。

輸入：使用者實測總表（測試分支 `test/t10-owner-acceptance-20261018`，commit `62064cf`，見該分支的 `docs/evidence/T10-OWNER-ACCEPTANCE-2026-10-18/SUMMARY.md`）。建議修復順序：取消後舊輸出 → 200% 導覽 → 記憶回答不一致。

## 重要前提：實測時的後端不是目前的程式碼

8000 服務是 2026-10-17 00:21 啟動的（唯讀查 `ps`），之後沒有重啟。網頁 `index.html` 每次從磁碟讀取，所以使用者測到的是新版前端；但 Python 後端仍是啟動當下的程式碼。之後 `c1727e5` 改了 `adapters/models/http.py`（模型串流的取消）、`gateway.py` 與 `core/memory.py`。只讀了 `/proc/<pid>/environ` 裡的 `SIRO_RUNTIME_PROFILE`（`candidate`）和模型路由主機（`api.groq.com`，模型 `openai/gpt-oss-20b`），沒有讀其他環境值、資料庫或私人對話，也沒有連線或重啟該服務。

## 1. 取消後的工具卡與舊輸出

**重現**（`cancel_repro.py`）：使用隔離的實際 main（D57 fixture：複製的 src、合成帳號／工作目錄、自有 Rust runtime 與 SQLite）、合成的本機 OpenAI 相容模型（它要求 `computer.execute sleep 2N`，拿到結果後回「等待完成」）以及真 Chrome，跑三種情境：停止後原頁等待、停止後立刻重新整理、停止後送新訊息再重新整理。

| 觀察 | 修正前（`cancel-before.json`） | 修正後（`cancel-after.json`） |
|---|---|---|
| 停止 1.5 秒後的 sleep 程序 | 0（已終止） | 0 |
| 原頁工具卡 | **一直停在「執行中…」** | 「已停止：這次工作已取消，這個操作沒有完成，也不會自動重送。」 |
| 舊「等待完成」出現在畫面或 WebSocket | 三種情境都是 0 | 0 |
| 工具結果送回後的模型呼叫 | 0 | 0 |

- **工具卡（已修，根因確認）**：工作被取消後，後端會以 `assistant_terminal`（cancelled／failed）結束這段串流，之後不會再送 `tool_result`；前端只會在收到 `tool_result` 時更新卡片。修正方式：前端記錄每張執行中卡片屬於哪條串流，收到該串流**非完成**的結束事件時，只把這條串流的卡片改成明確狀態：cancelled 顯示「已停止」，其他狀態顯示「未完成…請先確認實際狀態」並附錯誤類別。已完成的卡片和其他串流的卡片不受影響。後端、API 與事件格式都沒有改。
- **舊「等待完成」重新出現（目前程式碼上無法重現）**：三種情境都沒有出現，取消後程序也確實被終止。在使用者那台未重啟的舊後端上，根因仍未確定。可能原因包括舊後端的程式碼差異、真實模型的行為，或步驟時序不同。這裡不宣稱已修好，必須在重啟後的服務上重測（見手動指南第二輪）。若重測仍會發生，需要讀取那幾筆測試對話的 run／journal 紀錄（只讀合成測試內容）才能定位，這需要使用者同意。

## 2. 200% 縮放時「技能／設定」按不到（已修）

**重現**：用真 Chrome 量測每個導覽連結中心點是否可點、是否在可視範圍內。在 960×470（約 1920 寬螢幕放大 200%）時，技能、設定按不到；960×400 與 901×420 連「電腦」也按不到；1100×500 按不到設定。原因是側邊欄 `position:sticky; height:100dvh` 且不能捲動，超出視窗高度的項目永遠看不到。先前的 REFLOW 只量了水平溢出，所以漏掉了。

**修正**：`.sidebar` 加上 `overflow-y:auto; overscroll-behavior:contain`，只多一行 CSS。新測試 `test_every_navigation_link_is_reachable_on_short_zoomed_viewports` 涵蓋六種短視窗，修正前 FAIL（就是上面那些按不到的連結），修正後 PASS。也會檢查側邊欄沒有水平捲軸。

限制：用 Chromium 量測；使用者用的是 Firefox，本機沒有 Playwright 用的 Firefox。原理相同（sticky＋固定高度），仍需人工在 Firefox 200% 重測。

## 3. 記憶頁有紀錄，SIRO 卻說沒有

**定位**：使用者的服務走雲端模型（Groq）。依 D32 與記憶寫入決策，聊天建立的記憶來源是 local_only，雲端路由的記憶檢索會**刻意排除**它們（隱私邊界，不改）。所以模型確實拿不到這筆記憶。現有的雲端說明（「This cloud model cannot read local-only memory contents…」）埋在 "Verified preferences" 區塊裡，而模型讀記憶的地方是 `NO_SOURCE: If the answer needs memory, say you do not know.`，兩者互相拉扯，gpt-oss-20b 最後回答「沒有記錄」。

**修正**（`core/memory.py`、`core/companion.py`）：
- 雲端路由沒有可用記憶時，記憶欄位直接寫明：local-only 記憶不會送給這個雲端模型，所以這裡看不到；記憶可能仍然存在，要照實說明並指向記憶頁，不能說什麼都沒存。
- 本機路由沒有相關記憶時，改成「這次沒找到相關記憶，不要說使用者什麼都沒存，可到記憶頁查看」。
- 只送邊界說明，不含記憶內容或筆數；隱私過濾不變。既有測試 `test_actual_main_local_memory_not_disclosed_to_cloud` 加上斷言：新說明會出現，合成的私人記憶仍然不會出現在請求裡。

限制：真實模型是否照做，屬於模型行為，這裡沒有呼叫 Groq，無法驗證。必須人工重測。另外，記憶檢索是字詞比對，像「你的記憶有什麼」這種問句本來就找不到具體記憶，這次沒有改檢索。

## 4. 上一輪漏掉的回歸（本輪發現並修正）

全套測試時發現有 3 個測試在 HEAD（`3c7ee58`）就已經 FAIL，在 `bd63f28` 是 PASS：`test_capability_product::test_frontend_inventory…`、`test_gateway_terminal_fence::test_actual_frontend_terminal_consumer`、`test_run_journal::test_actual_frontend_recovery_notice`。原因是 T10 加入的跳過連結綁定與記憶搜尋區塊，落在這些測試擷取的程式片段範圍內。上一輪的「相關 525 PASS」沒有包含這三個檔案。修正方式是只搬移程式位置、不改行為：跳過連結的綁定移進 `initializePageNavigation()`（boot 時執行），記憶搜尋區塊移到 `renderCapabilities` 之前。三個測試都恢復 PASS，測試本身沒有改。

## Tests run

| 層級 | 結果 |
|---|---|
| 新增／加強的專項 | 工具卡 1、導覽可達 1、記憶提示 2 處斷言；工具卡與導覽測試在修正前的版本上 FAIL |
| 前端相關＋桌寵 | `test_frontend*.py`、`test_capability_product.py`、`test_gateway_terminal_fence.py`、`test_run_journal.py`、`test_desktop*.py`：**485 PASS** |
| 記憶 | `test_persistent_companion.py`、`test_memory_ingress.py`：12 PASS |
| 全套 `pytest tests` | **2410 PASS／5 opt-in SKIP／1 FAIL**。失敗的是 `test_browser_sessions::test_real_chrome_cross_run_form_isolation_stale_ttl_close`（真 Chrome TTL 計時測試），單獨重跑 3/3 PASS，前一次全套也是 PASS，判定為既有 flaky；本輪沒有改到它涉及的檔案 |
| 真 main 整合（重跑 T10 acceptance） | **9/9 PASS**（`integration-rerun/`），舊證據目錄未覆寫 |
| 取消重現 | 修正前／修正後各三情境，結果見上表 |
| 靜態 | Ruff check／format、mypy（改動的 Python 檔與 repro）、inline JS `node --check`、`git diff --check`、detect-secrets：PASS |

未跑：完整 `scripts/check`、Firefox 實機、真 Groq、使用中服務重啟後的人工重測、部署 rollback。

## Rollback

撤回本輪對 `static/index.html` 的增量（`runningTools`／`settleRunningTools`、`.sidebar` 一行、兩處程式搬移）、`core/memory.py` 的 NO_SOURCE 文字與 `cloud_route` 參數、`core/companion.py` 一行、測試新增內容與本目錄。沒有 DB、migration、API、wire 或設定變更。
