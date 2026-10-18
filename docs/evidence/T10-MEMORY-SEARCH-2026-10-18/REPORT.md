# T10-UI-01：記憶搜尋切片

2026-10-18。基線：使用者提交 c1727e5／bd63f28。結果：**搜尋切片 LOCAL_VERIFIED；T10-UI-01 整體 PARTIAL**。

## 選擇與接線

RT-001–015 已各有 scoped DONE，沒有下一個未完成的 RT 編號；舊章節的 DEFER 是歷史狀態，不覆蓋 2026-10-06 的解除及完成紀錄。T10-UI-01 明列記憶搜尋未完成，依賴 T10 與既有記憶 API 均已滿足，故選本切片。未完成盤點見 [OPEN_TASKS](OPEN_TASKS.md)。

實際既有路徑：index.html → authorizedFetch/session → Gateway GET /v1/memories?query=…&limit=100 → MemoryService.recall/browse → SQLiteMemoryRepository。後端搜尋已存在，本卡只補產品入口；不重做索引或 Core。

前端加入標示清楚的搜尋表單／清除按鈕、結果筆數／零結果／錯誤／逾時狀態。來源與 revision、更正及刪除 callback 保持；變更後重新查詢目前條件。新查詢先 abort 舊 request，以 epoch、connection、page-close fence 拒絕忽略取消的晚到結果；5 秒有界等待。字串以 textContent 顯示，query 不放頁面 hash 或 localStorage。最多顯示100筆，不聲稱是全資料庫總筆數或語義理解搜尋。

## 功能完成後的驗證

| 層級 | 實際執行與結果 |
|---|---|
| 前端 production script，合成 DOM／transport | 新增11例 PASS：授權與UTF8/特殊符號編碼、零結果／清除、latest query、timeout／disconnect／close、HTTP／network／malformed錯誤後恢復、更正／刪除重查、長度限制、來源與文字安全 |
| 真 main/Core/SQLite，合成模型 | 新增1例 PASS：owner記憶建立、401、搜尋、person隔離、更正後舊詞無結果／新詞revision2、刪除後不再命中與未刪項保持 |
| 相關回歸 | `pytest -q tests/integration/test_frontend*.py tests/integration/test_memory_ingress.py tests/integration/test_memory_v2.py tests/integration/test_memory_organization.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/integration/test_desktop*.py`：476 PASS，3 dependency warnings，38.42s。含搜尋11例；與下列12例重疊，不能相加 |
| 新功能最終專項 | `pytest -q tests/integration/test_frontend_memory_search.py tests/integration/test_memory_search_api.py`：12 PASS，3 dependency warnings，1.62s |
| Python3.12相容 | 以隔離候選的3.12.14直譯器、PYTHONPATH=src指向目前修改後source，搜尋／main API／IME／桌面入口54 PASS、1 dependency warning、9.46s。初次命令誤用不存在的test_desktop_entry.py而exit4／零測試；改為實際test_desktop_entry_scripts.py後執行通過 |
| 最終合併專項 | 搜尋11＋main API1＋D68隱私8＝20 PASS、3 dependency warnings、2.02s |
| 靜態檢查 | 新增三份測試 Ruff／format、mypy PASS；desktop/host.js Node syntax PASS |
| 實際瀏覽器→正式 main→SQLite | 僅隔離隨機 loopback／臨時資料。啟用既有memory ingress，以合成 remember 要求建立2筆；頁面顯示2筆，搜尋orchid顯示1筆含來源／revision，清除回2筆，無匹配顯示零結果且無舊卡。截圖 [search.png](search.png) |

瀏覽器使用目前source的隔離副本、實際main及SQLite。renderer為明示placeholder；沒有使用私人聊天、真provider、TTS或另一台電腦。測試結束正常清理source bundle、子程序、臨時DB與分頁。既有product-probe receipt仍保留其預設browser_acceptance NOT_RUN標籤，人工CUA結果記在本報告，不能把該標籤改當全UI自動驗收。

初次新測試1 FAIL／10 PASS原因為測試錯把 Headers 當plain object；改用Headers.get後11 PASS，未削弱production要求。第一次瀏覽器harness缺輸出目錄，第二次使用原fixture關閉memory ingress所以零筆；已清理並明確開啟既有flag後重驗，沒有改production預設或私人配置。

## 相容與限制

覆蓋的聊天、頁面導航、IME合成事件、麥克風／TTS停止、session、任務、記憶及桌寵回歸沒有觀察到退化。**不是所有實際平台功能已驗的保證**：另一台WSLg實體輸入法、B聲線聽感／GPU、真Live2D、ESP32/HA、長期soak、正式部署仍需原各卡證據。未改Core／Gateway／DB schema／wire／授權／模型聲線／WSL入口，未推送或重啟正在使用的服務。

先前修改前即已啟動的完整Python3.12 check在MQTT套件停留後，依使用者「不用現在驗證」轉向實作而中止：1212 PASS後KeyboardInterrupt／exit2，整條check **NOT COMPLETED**，且快照不含本搜尋功能，不能當本卡完整check PASS。隔離log保留在 .siro-data/verification/T12-SNAPSHOT-20261018/full-check.log；未變更或放寬測試／secret gate。

## 檔案與回退

production僅 index.html 的搜尋接線；測試 test_frontend_memory_search.py、test_memory_search_api.py；D69、TASKS、STATUS與本證據。先前D68 desktop/host.js獨立修改另見其證據，不算本搜尋功能。

回退只撤 index.html 的本卡diff並保留最新DB／記憶／任務；原無搜尋的瀏覽入口恢復。無資料migration或部署動作。下一可執行切片：T10-UI-01任務詳情；本輪未開始。
