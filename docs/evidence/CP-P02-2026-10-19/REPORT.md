# CP-P02：活動與網路實際紀錄（2026-10-19）

**結果：PARTIAL。** 紀錄、讀回 API 與契約要求的故障情境都已實作，並以自動測試驗證（含真 Chrome 與真 SIGKILL）。
還沒有 UI（CP-P03），也沒有在使用中服務上由 owner 實際查看，因此不標 DONE。

- Branch：`claude/companion-p02-20261019`，base `2f68d50`（origin/main）。不依賴未合併的 CP-P01。
- 決策：DECISIONS D78（跳過 D76／D77，已由 CP-P01 分支使用）。

## 做了什麼

| 部分 | 檔案 | 內容 |
| --- | --- | --- |
| 變更順序 | `persistence/migrations/015_activity_events.sql`、`persistence/activity_events.py` | 只記順序的 append-only 事件表；7 天／10,000 筆保留 |
| 寫入點 | `services/tools/orchestrator.py`、`services/agent/runs.py` | proposal 建立／轉換、run 開始／狀態改變、journal dispatch、reconcile，都與原寫入在同一個 transaction |
| 唯讀投影 | `services/activity/monitor.py` | 快照＋cursor 增量、契約狀態對映、網路覆蓋、脫敏 |
| API | `services/presentation/gateway.py`、`integrated.py` | `GET /v1/activities`、`GET /v1/activities/changes?after=`；需 session token；store 未就緒回 unavailable，不在讀取時初始化 |
| adapter 修正 | `adapters/browser.py` | 連線失敗的 route 改為 abort 且不 raise（見下） |

## 驗收情境與證據（自動測試）

`tests/integration/test_activity_monitor.py`（11）、`tests/contract/test_activity_projection.py`（22）：

| 契約要求 | 測試 | 結果 |
| --- | --- | --- |
| 受控本機 HTTP 故障 | 真 Chrome＋本機 server：同源 302（帶私密 query）、HTTP 500、連線被拒，之後再正常瀏覽 | redirect 偵測到且 query 已移除；500 頁面完成但 status 誠實標 unknown；拒絕 → failed，約 1.5 秒；之後同一 pool 仍可用 |
| 競態停止 | 兩個工具，第一個執行中取消 | 已 dispatch 的 → **unknown**（不假稱已取消）；未執行的 → cancelled；事件 seq 嚴格遞增，終態不回退 |
| 亂序／重送 | 重送已終態的轉換、重複 dispatch、對已結束 run 追加 | 全部被拒，事件數不變 |
| 斷線補讀 | 分頁 limit=3 與一次讀完相同；舊 cursor 重讀只多出重疊；cursor 超前或已被清理 → gap | PASS |
| 進程 crash／重啟 | 子進程 dispatch 後 `SIGKILL`，重開同一資料庫 | run=unknown（outcome_unknown）、tool=unknown（已 dispatch）；reconcile 事件可讀；重啟後沒有重送 |
| 儲存故障 | 測試用 trigger 讓 dispatch 的審計寫入失敗 | handler **從未執行**；工具未 dispatch |
| 脫敏 | URL 帳密／query／fragment、非 http scheme、填寫值、頁面文字、argv | 都不出現在 view；shell 只留程式名與參數數量 |
| 分頁／保留有界 | 103 筆活動、超大 limit | 快照最多 100 筆並標 truncated；changes 每頁最多 100 筆，has_more |
| 舊版相容 | 只套用前 14 個 migration 再寫入 | 不出錯；舊版寫入沒有事件，但快照正確 |

突變檢查：拿掉 dispatch 審計 → 3 FAIL；取消一律算 cancelled → 2 FAIL；拿掉 URL 脫敏 → 3 FAIL（契約測試，不需瀏覽器）。都已還原。

## 順帶修正的既有 bug

P02 的連線拒絕情境抓到：`ScopedBrowserDriver._route_request` 的 `route.fetch` 失敗時直接 raise，導覽會卡滿 30 秒的 session 逾時，
而且 Playwright 會在 `Browser.close()` 重新丟出這個例外 → 收尾失敗 → **整個 browser pool 被關閉**，之後所有瀏覽都失敗。
改為以 `connectionfailed` abort 並 return：導覽立刻以網路錯誤失敗（錯誤仍可見），pool 繼續可用。
修正前，新的真 Chrome 測試與調整後的單元測試都會失敗（32 秒）；修正後通過。
既有單元測試 `test_live_route_fetch_error_remains_visible` 固定的正是「從 handler 丟例外」，依實際行為改名並改斷言。

## 其他回歸與檢查

- browser 相關（driver／failure contract／pending cleanup／scope／sessions／frontend result）＋新測試：71 PASS。
- run／journal／fence／integrated 相鄰回歸：94 PASS。
- 全套（本分支獨立 venv，`uv sync --locked --offline`）：**2443 PASS／1 FAIL／5 SKIP**。唯一失敗
  `test_capability_product::test_frontend_inventory_is_read_only_refreshable_and_uses_text_content` 在 origin/main 上同樣失敗，
  主 checkout 已有另一個對話的未提交修正，不屬本卡。
  共用主 checkout 的 venv 時，另有 skill worker／release 子進程測試失敗：子進程會載入主 checkout 的 src（14 個 migration），
  改用本分支自己的 venv 後全部通過。未跑完整 `scripts/check`（含 cargo）。
- Ruff check／format、mypy（296 檔）、`export_schemas --check`、`git diff --check` PASS。
- secret gate：本分支只剩 `test_desktop_entry_scripts.py` 3 項，那是 origin/main 既有問題，已在 CP-P01 分支修正（合併後消失）。

## 未做／限制

- 沒有 UI；CP-P03 要以快照＋cursor 消費這兩個 API。
- HTTP status、method、子資源清單、shell 子程序網路都拿不到，標 unknown／unobserved；程序層監測是 CP-O01。
- 連線被拒時工具錯誤類別是 Playwright 的通用 `Error`，對 owner 不夠清楚。
- 結果摘要（例如頁面標題）刻意不放進 view，避免外洩頁面內容；P03 若需要再定規則。
- 目前所有活動的 origin 都是 owner_request；自主活動的來源欄位等 CP-P04。
- 使用中的 8000 服務跑的是 CP-P01 分支，還沒有這些 API。

## 回退

撤回本分支程式即可；`activity_events` 表留著無害，不需要反向 migration。
注意：資料庫一旦套用 schema 15，`max_schema` 14 的已簽署 release 會依既有規則被拒，要先還原備份。
