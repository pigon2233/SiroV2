# Companion CP-P05：有 scope 的工作情境 — 2026-10-23，PARTIAL

新增 `services/context/work_context.py`：來源分開開關（主人自己說的／app metadata／選定畫面，後兩者預設關，`work-context-scope.json` 重啟保留，損壞視為全關）。每筆 observation 有 source／kind（stated／seen／inferred 分開）／observed_at／expires_at／privacy／permission_revision；關來源或改 revision 立即失效，視窗標題不存，鎖屏／敏感視窗（密碼、銀行、無痕等）不留紀錄並丟掉前一筆，編輯器只推測並反問「你是在寫程式嗎？」，更正後不再猜，Focus／全螢幕時 P04 排程不啟動自主活動，雲端模型拿不到任何情境。端點 `/v1/work-context`（GET／scope／shared／app／{id}/retract|correct）；關閉後 adapter 回報得 409。

命令與結果：`test_work_context.py` 9 PASS，加 self_activity／self_interests 共 24 PASS；新檔 Ruff／format／mypy PASS（`integrated.py` 既有 2 個 E501／format 問題非本卡）。本機 commit，未 push。

限制：沒有真的 OS 前景視窗 provider 與螢幕擷取 provider（只有 adapter 介面、`/v1/work-context/app` 推送端點與 `ScreenObserver`，gateway 未組裝擷取來源）；沒有 UI 開關頁、情境也未接進對話 prompt（`prompt_lines` 已備、未被 caller 使用）；Windows／WSLg 未驗。回退：撤 commit；無觀察時聊天不受影響。

# Companion CP-O01：程序層網路監測 — 2026-10-23，PARTIAL

新增 `adapters/process_network.py`：Linux 免權限取樣 `/proc`，把 subprocess 的外送連線歸屬到它的 process group；其他平台回 unsupported。實測持有中的連線可歸屬，短連線看不到，因此只標 sampled，不能稱完整稽核。見 [REPORT](evidence/CP-O01-2026-10-23/REPORT.md)。

限制：只在 WSL2 測；Windows 原生／macOS 無免權限方法；尚未接進 `computer.execute` 或監測頁，監測頁仍標「沒有網路監測」。下一步：決定是否接線。

# Companion CP-P04：她自己的活動、研究筆記與分享 — 2026-10-22，PARTIAL

Owner 決定：可讀任何網頁；興趣清單由她自己找。本機 commit（未 push）：`473b8a6` 背景 owner：保留 session `siro.self`，一次一件、只准 `browser.navigate+read`、只用本機請求、不說話、不寫 owner facts；新 turn、全域停止、工具開關、`POST /v1/activities/stop-background` 會取消；`PUT /v1/self-activity` 暫停（目前這步做完再停）。`778851a` 她自己挑題目：線索為三天內對話、她的 committed 喜好、舊筆記「待查」；本機模型選一題或選擇等待；排程每 10 分鐘，owner 安靜 10 分鐘、距上一件 45 分鐘（失敗也算）、一天最多 6 件；理由存成 `self_topic` 步驟並顯示在活動頁。`7d07dc1` 修 owner 回報：氣象查詢開了已停用的 `www.cwb.gov.tw`，失敗只回 `Error`，模型因此說自己不能上網；改為 `NavigationFailed`＋原因（DNS 查詢區分找不到網站），工具說明提示換站與維基搜尋（DuckDuckGo 有 CAPTCHA、Bing 讀不到結果）。本次：研究筆記從完成的 self run 讀回，來源只列 journal 中確實讀成功的頁面（模型自己寫的連結不算），`GET /v1/self-notes`；氣泡「查好了，要聽嗎？」，按「聽」才把筆記與來源放進對話並說一句短話，Esc 標成已看；活動頁「看細節」顯示她的筆記與讀過的頁面。

命令與結果：相關 633 PASS（活動、前端、contract、self activity／interests、桌寵）；Ruff／mypy 只剩 gateway 既有 create_task 型別錯誤；隔離 candidate 服務（8765）啟動、三個新 API 回應、正常關閉。`test_gateway_main` 因本環境沒有 `.venv/bin/siro-gateway` 無法執行。

限制：qwen3:4b 挑題目、叫工具與換站的能力未在真環境驗；背景推論與前景共用 GPU；暫停狀態與「已告訴主人」清單（`self-notes-shared.json`）不在 DB，暫停重開會重置；筆記不進記憶服務；分享不寫入對話歷史，她之後不記得說過。下一步：owner 重開後閒置觀察真紀錄，再決定 P05 或調整排程參數。

# Companion CP-P03：活動監測頁、停止與桌寵氣泡 — 2026-10-21，PARTIAL

依 V05 規格實作，三個本機 commit（未 push）：`02707ce` 新增 `POST /v1/activities/{id}/stop`，停正在跑的 run（取消工具、語音、動畫並關瀏覽器分頁）或擋下待確認的單獨提案；已結束 409、找不到 404、這個程序沒有 owner 的 run 409 not_owned。run id 本身就是 generation，所以不另帶 revision。`1364847` 主畫面新增「活動」頁（`#/activity`）：快照＋每 3 秒 cursor 增量，只在頁面打開且已連線時讀；gap 重讀快照；斷線保留舊資料並停用停止；401／紀錄不可用只顯示橫幅；沒用工具的已完成回覆只計數不列出。`d47ecb3` 桌寵頭上一行氣泡，讀同一份紀錄；只有 journal 有 running 工具才寫「正在…」，聊天開、說話中、打字中不出；「看看」用 `desktop.console` 的 `page: "activity"` 打開控制台活動頁。

命令與結果：`test_activity_monitor.py` 14 PASS（新 3）；前端＋桌寵＋活動相關 441 PASS（新增活動頁 reflow／導航與 2 個氣泡測試）；Ruff check／format PASS；mypy 只剩 gateway 既有的 create_task 型別錯誤。合成資料截圖：桌面、320 px、200% 縮放皆無橫向捲動。2026-10-21 owner 重開服務後，以 curl 確認線上停止 API 回 `not_found`、`index.html` 與 `desktop.js` 已是新版；真資料與氣泡位置尚待 owner 看過。

限制：「暫停 SIRO 自己找事做」「停止所有背景工作」沒做，目前沒有背景 producer，等 P04；夜間／專心模式只顯示重要氣泡等 P05；停止一件事時 body cancel 是 `active`，同時有兩個前景 session 時也會停到另一個的動畫語音；氣泡固定在角色區頂端 8px，可能蓋到頭。下一步：owner 試用確認後，CP-P04。

# Companion CP-00：Claude runtime 接收 — 2026-10-18

接收 Codex `design/companion-cp00-20261018`@`feda8bc` 的視覺基線與資產交接 v0，見[接收紀錄](companion-workflow/CP-00-CLAUDE-RECEIPT.md)。source 對映核對：audio owner 與 finish_journal 位置更正；**ProactivityRules 只有測試中的 RoomAutomation 在用，companion 主動性沒有 production caller**。提供 V01 用的 Haru 實檔路徑、digest、expression／motion 清單；目前 renderer 是 repair v2，gesture／stopSiroMotion 沒有 caller，嘴型沒有音訊驅動，第一次 cancel 後會固定閉嘴（source 推論）。更正：下方 T10 修正已在 `2f68d50` 提交並推送，計畫文件已由 `ddeabdd` 進 main。

命令：只做 source／檔案讀取與 sha256；沒有跑測試、沒有啟動或連線服務。限制：Codex 尚未回覆、未建立 GitHub Issue／PR（本機無 gh），CP-00 PARTIAL。下一步：CP-P00 需重啟服務並由 owner 做第二輪重測；Codex 可開始 V01。

# Companion CP-P02：活動與網路實際紀錄 — 2026-10-19，PARTIAL

新增 migration 015 `activity_events`：只記變更順序，與 proposal、run、journal dispatch、reconcile 的寫入在同一個 transaction，審計寫不進去就不執行工具。唯讀投影 `GET /v1/activities`（快照＋cursor）與 `/v1/activities/changes`（增量、has_more、gap），提供契約狀態（取消但已 dispatch → unknown）、網路覆蓋（browser adapter／shell unobserved）與脫敏。順帶修正 browser adapter：連線被拒原本會卡 30 秒並關閉整個 browser pool。見 D78、[REPORT](evidence/CP-P02-2026-10-19/REPORT.md)。

命令與結果：新測試 33 PASS（真 Chrome HTTP 故障、競態停止、重送、cursor 補讀／gap、真 SIGKILL 重啟、審計寫入故障、脫敏、分頁上限、舊 schema 相容）；突變檢查 3 種都被抓到；browser 相關 71 PASS；全套 2443 PASS／1 FAIL（origin/main 既有，另一對話修正中）／5 SKIP；Ruff／mypy／export_schemas／diff check PASS。

限制：沒有 UI（P03）；HTTP status／method／子資源與 shell 網路拿不到，標 unknown／unobserved；連線失敗的錯誤類別仍是通用 `Error`；使用中 8000 服務跑 P01 分支，沒有這些 API；schema 15 之後 `max_schema` 14 的 release 需先還原備份。下一步：CP-P03 需要 Codex 的 V05 畫面稿。

# CI 修復 — 2026-10-18

使用者回報 push 後 Actions 紅燈。查閱 run 39102841020：scripts/check 的 pytest 為 2406 passed、3 failed、5 skipped；三項皆是前端測試擷取範圍過廣，帶入導航 DOM 註冊或記憶搜尋事件並污染測試 harness。縮小 capability、terminal fence、recovery notice 的擷取範圍，保留原行為斷言，未更改產品程式。

驗證：使用相鄰 SiroV2 既有 Python 3.14 環境執行三個完整測試檔，25 passed／3 既有 warnings（6.60s）；相關 Ruff check／format 與 git diff --check 通過。完整 scripts/check 未在本機重跑；推送後須以新 remote CI 結果確認完整檢查。T10 人工驗收狀態不變。下一步：確認修正提交的 Actions 結果。

# SIRO 2 目前進度與接續點

## 2026-10-18 — T10-UI-01 第二輪重測：三個優先問題使用者回報PASS

使用者重測：側邊欄可點；記憶回答正常；按停止後不再出現舊「等待完成」。先前看到的「等待完成」是只重新整理、沒按停止：重新整理不是取消，工作在後端照常完成並送出結果，屬預期行為，不是缺陷。限制：8000服務仍是10/17的程序，記憶提示詞修改尚未載入，重啟後需再確認一次記憶回答。T10-UI-01仍PARTIAL，剩無提示真人三輪、讀屏、WSLg、麥克風、跨機、後端重啟自動重連等人工項目。可改善項（未做）：重新整理後提示「上一個工作仍在執行」。

## 2026-10-18 — T10-UI-01 側邊欄第二次修正（真Firefox重現）

使用者回報側邊欄仍按不到。真headless Firefox 158在不捲動時，`2f68d50`只做到「可捲動」：Linux的Firefox會隱藏捲軸，使用者看不出要捲，所以等於沒修好。改為寬度大於900、高度不超過600時使用既有的頂部導覽列，Firefox五種尺寸與Chromium八種尺寸都PASS（舊兩版FAIL）。另修正squash合併造成的test_capability_product擷取終點衝突。相關497 PASS。8000服務仍未重啟，記憶回答正常與「等待完成」都是在舊後端上的觀察，需重啟後重測。[REPORT](evidence/T10-OWNER-FIXES-2026-10-18/REPORT.md)。未commit。

## 2026-10-18 — T10-UI-01 真人驗收後修正，整卡PARTIAL待重測

使用者真人驗收（測試分支`62064cf`）為PARTIAL。依建議順序處理：
- **取消後工具卡停在「執行中…」**：已重現並修正。run非完成結束時，前端依stream把卡片改成「已停止」或「未完成、請確認」。
- **刷新後出現舊「等待完成」**：隔離main三種情境都無法重現，取消後程序在1.5秒內終止。
- **200%縮放時技能／設定按不到**：960×470重現，原因是sticky側邊欄不能捲動，已改為可捲動。
- **雲端模型說沒有記憶**：local-only記憶依設計不送雲端，但NO_SOURCE提示與雲端說明衝突。改為照實說明看不到，隱私邊界不變。
- **上一輪漏掉的3個回歸**：只搬移程式位置，已修正。

注意：8000服務自10/17未重啟，實測時是新前端配舊後端，需重啟後依[手動指南第二輪](evidence/T10-INTEGRATION-2026-10-18/MANUAL_TEST_GUIDE.md)重測。

命令與結果：前端相關＋桌寵485 PASS；記憶12 PASS；全套2410 PASS／5 SKIP／1 flaky（browser_sessions TTL，單獨3/3 PASS）；真main整合9/9；Ruff／mypy／node --check／diff check／detect-secrets PASS。[REPORT](evidence/T10-OWNER-FIXES-2026-10-18/REPORT.md)。

限制：舊輸出在舊後端上的根因未定；Firefox與真Groq未自動驗；full scripts/check與部署rollback未跑；未commit／未push、未重啟使用中服務。下一步：重啟服務後人工重測第二輪與其餘人工項目。

## 2026-10-18 — T10-UI-01 整體整合：自動可驗項目完成，整卡PARTIAL待人工

使用者要求整張T10做完，本輪連續處理REFLOW之後的對比、鍵盤／焦點、錯誤／等待／取消、三條日常流程與真Live2D整合。實測修正9項，皆只在static/index.html：輸入框外框對比、真renderer上不可讀的標語、iframe佔Tab、焦點被sticky工具列遮、停止開關失敗被吞且照樣reload、記憶更正／刪除錯誤寫在看不到的收合區、**main重啟後已開頁面約5分鐘無法重連（控制WS沿用舊token）**、記憶搜尋表單間距。

新accessibility 2＋state_feedback 8 PASS（修改前8 FAIL）；相關525 PASS、桌寵69 PASS；lint／type／JS syntax／secret scan PASS。真main（合成loopback模型、授權本機Haru Live2D、自有Rust／SQLite）9/9 PASS：三條日常流程、取消不復活、同頁斷線重連不重送、重啟保留狀態、換頁零重送／socket／renderer重載。[REPORT](evidence/T10-INTEGRATION-2026-10-18/REPORT.md)。

T10-UI-01仍PARTIAL：真人三輪15分鐘、讀屏、WSLg桌寵實機、真TTS／麥克風／真模型、跨機需人工，步驟見[手動驗收指南](evidence/T10-INTEGRATION-2026-10-18/MANUAL_TEST_GUIDE.md)。full scripts/check與部署rollback未跑；未推送、未改使用中服務。下一步：依指南人工驗收，回報結果後再決定DONE或修正。

## 2026-10-18 — T10-UI-01-REFLOW DONE／LOCAL_VERIFIED

沿T10 Scope選窄窗／200%等效reflow切片：真Chrome量production HTML六viewport（320／375／414／768／640×400／960×540）×九頁＋detail。預設內容0溢出；以production renderer灌合成長資料，只發現權限頁未知長kill-switch key按鈕超出視窗，且因html/body overflow-x:clip被直接裁掉。新增一行`#switches button`換行CSS，無JS／API／授權變更。

新test_frontend_reflow.py 2 PASS（原版stress FAIL）；相關514 PASS、桌寵69 PASS（各3既有warnings）；Ruff／format／mypy／diff check PASS；source-only回退→FAIL、還原逐byte相同→PASS。修正前後截圖與量測JSON在[證據](evidence/T10-REFLOW-2026-10-18/REPORT.md)。

限制：file://預覽量測，未在真main服務頁重跑；只驗水平reflow；對比／讀屏／完整真人流程、真WSLg／Live2D、full scripts/check與部署rollback未跑。T10整體PARTIAL，下一卡未開始。

## 2026-10-18 — T10-UI-01-KEYBOARD DONE／LOCAL_VERIFIED

沿T10剩餘可及性選keyboard bypass切片：首個Tab顯示「跳到主要內容」，Enter focus目前visible heading（含detail UUID），缺heading回既有main。preventDefault防hash誤切chat，沒有新增router／request／owner／授權；原search／detail／settings／desktop工作保持。

原版新3 FAIL→3 PASS，相關512 PASS／桌寵69 PASS（各3既有warnings）；scoped lint／format／mypy兩檔、inline syntax／diff PASS。真CUA tasks與直接detail的Tab／Return、四AX／三JPEG確認focus與route保持；後端read0、無goal mutation／switch PUT／speech request；owned程序／temp／tab已清理。精確source-only rollback/reapply保先前功能與資料。[完整驗收](evidence/T10-KEYBOARD-2026-10-18/REPORT.md)。

T10整體PARTIAL；對比／窄窗／讀屏／完整真人流程仍待各自驗收，真WSLg／voice／Live2D／設備／soak／部署rollback與full scripts/check未在本輪跑。不推送、不改另一台運行服務，下一卡未開始。

## 2026-10-18 — T10-UI-01-SETTINGS DONE／LOCAL_VERIFIED

沿roadmap選下一有界切片「設定與權限用語」：permissions顯示既有mode，與computer共用說明；原cloud／tools／microphone按鈕改中文名稱／已開啟關閉／下一操作title，原PUT／body／session／reload完全保持。沒有後端／DB／protocol／config／預設授權變更，先前D68／D69／D70保留。

最終相關509 PASS／3既有warnings；Python3.12相容64 PASS（重疊），Ruff／format／明確3.12 no-incremental mypy287／inline syntax／diff PASS。初次local type檢查缺faster_whisper的診斷保留，僅在自有locked3.12環境重驗，沒有放寬ignore或改依賴。真CUA三步：中文labels與mode→tools一次PUT後關閉→computer同mode，後端snapshot保持cloud/mic=false、full不變，Rust read0，所有owned資源已清理。source-only本卡與串接DETAIL回退／重套通過。[證據](evidence/T10-SETTINGS-WORDING-2026-10-18/REPORT.md)。

T10整體PARTIAL；完整可及性／真人流程仍未完成，不啟動下一卡。真Live2D／語音／WSLg／設備／soak／正式部署回退與full scripts/check未於本輪驗，不推送、不改另一台運行配置。

## 2026-10-18 — T10-UI-01-DETAIL 驗證證據修補完成

收到獨立PARTIAL後先降級，未改production。重跑真CUA detail／reload／back／forward／missing snapshot等8步，AX與原始JPEG逐步保存並重驗；public product-receipt現為PASS且指向同批證據。真main／SQLite／Rust navigation後零read，明確批准一次read1；owned程序／temp／tab已清理。

回退package提供baseline commit、D69 dirty before／DETAIL after、標準checksums與兩方向patch；目前checkout正常rollback --check與隔離實撤／重套PASS，drift／tamper負例拒絕且不寫checkout。REGRESSION_BASELINE加入專項；本輪107 PASS／7.24s，verifier lint／format／mypy PASS。原480／150沒有重跑，歷史結果保持。[修補報告](evidence/T10-TASK-DETAIL-2026-10-18/REPORT.md)／[回退操作](evidence/T10-TASK-DETAIL-2026-10-18/rollback/README.md)。

僅恢復本切片DONE／LOCAL_VERIFIED供獨立重驗，T10整體PARTIAL不變。真active child動態取消、正式部署rollback／真人跨機／GPU與soak仍NOT VERIFIED；沒有新增功能、推送或改動另一台運行設定。

## 2026-10-18 — T10-UI-01-DETAIL DONE／LOCAL_VERIFIED

自動選中roadmap第一個依賴滿足的未完成產品項T10-UI-01，續作其單任務詳情。新增#/tasks/<UUID>、返回清單、標題／焦點／history，詳情只見所選任務並隱藏建立表單。沿既有validated snapshot／readback／revision-bound controls，直接開啟或reload不自動批准／執行；缺ID只稱目前20筆快照未提供。Core／Gateway／DB／protocol／owner／模型／語音／WSL不改，D68／D69舊修改保持。

功能後新11 PASS、相關480 PASS（含11）與桌寵／語音／記憶150 PASS；Ruff／format／mypy／JS syntax／diff及source-only精確reverse/reapply通過。真CUA→main/Core/SQLite/Rust：proposed零read→詳情reload／後端重啟仍零read→明確批准一次read→完成來源顯示→返回／back／forward無重播。兩輪owned程序／temp／分頁已清理。[完整證據及限制](evidence/T10-TASK-DETAIL-2026-10-18/REPORT.md)。

T10-UI-01整體仍PARTIAL；下一具體切片是設定用語或完整可及性／真人流程，未開始。本輪未跑full scripts/check／真GPU與owner WSLg／正式部署，原硬體、品質與release gate不解除。沒有推送或重啟私人服務。

## 2026-10-18 — T／RT盤點與T10記憶搜尋切片 LOCAL_VERIFIED

依使用者要求先核對未完成範圍再實作；RT-001–015均有scoped DONE，不重開歷史DEFER。尚缺T10任務詳情／設定、T12追加完整素材與自由活動、T15品質速度、T27–29真設備、T35／39／40及RI-003–006剩餘整合，見 [完整盤點](evidence/T10-MEMORY-SEARCH-2026-10-18/OPEN_TASKS.md)。舊「本機缺口全清」段落是歷史敘述，不能當目前全產品完成結論。

本輪只新增T10-UI-01記憶搜尋：重用既有authenticated memory API／SQLite，保留來源、revision、更正／刪除；清除／零結果／5s逾時／斷線／latest-query fence。功能後相關回歸476 PASS，新專項12 PASS（有重疊）；Python3.12目前source相容54 PASS，最終合併專項20 PASS；Ruff／format／mypy通過。真瀏覽器連隔離main／SQLite顯示2筆→搜尋1筆→清除2筆→無匹配0筆。未改正在另一台運行的配置／服務；T10-UI-01整體仍PARTIAL。[驗收與回退](evidence/T10-MEMORY-SEARCH-2026-10-18/REPORT.md)。下一切片：任務詳情，未開始。

前段已做D68桌寵影像隱私修復，獨立證據見 [REPORT](evidence/T12-SNAPSHOT-PRIVACY-2026-10-18/REPORT.md)。原先隔離完整Python3.12 check在MQTT階段中止，1212 PASS後exit2，不列全check通過；使用者澄清驗證應在功能修改之後。真WSLg／B聲線聽感、設備、soak與正式部署原gate保持。

## 2026-10-18 — T27 ESP32 HTTP 光度／PIR 現場驗收 PARTIAL

使用者提供實際 ESP32 草稿並回報已完成遮光及 PIR 動作測試、結果正常。草稿以 HTTP POST 向電腦端 `/event` 送 `light_update`（含 lux）、`motion_detected`／`motion_cleared`；這是使用者的現場回報，尚未取得序列埠 HTTP 狀態碼或接收器保存的 payload。電腦端實測 8765 有 Python 程序監聽、LAN 位址可連通；30 秒觀測窗內有 7 筆來自同一區網對端的新連線。這些是連線證據，尚不能證明接收器成功解析 lux 或動作事件。

目前專案 T27/T29 正式設備路徑為 MQTT；本次 HTTP 接收器來源／事件紀錄未定位，不能宣稱感測值已進入 SIRO World State，也不能將此驗收視為 A18 L3 ESP32+HA 或 LED/actuator 閉環通過。沒有對設備發送指令或合成 POST。證據與可重現檢查見 [T27 HTTP 感測器驗收](evidence/T27-HTTP-SENSORS-2026-10-18/REPORT.md)。下一步：取得電腦端接收器路徑或事件紀錄，核對實際 lux 數值、時間與動作事件，再決定 HTTP ingress 契約或沿既有 MQTT 路徑接入 World State。

## 2026-10-18 — T10 WSLg 注音引擎修復 LOCAL_VERIFIED，真人按鍵待驗

使用者確認「注音根本打不出來」後，發現上一輪 Enter 組字修正只處理送出競爭，真正缺口是 WSLg 未轉送 Windows 注音且 E 槽 Ubuntu 沒有注音引擎。已安裝 IBus／Chewing／`setxkbmap` 所需 Ubuntu 套件，並把 Chewing 啟動、選用及 GTK IME 環境接進桌寵入口；缺服務時顯示可理解錯誤。原有 Windows 輸入法不更動。[驗收及失敗修復過程](evidence/T10-ZHUYIN-2026-10-18/REPORT.md)。

最終快照 `27a4c652b551` locked sync／compileall／Cargo build與來源同一性核對通過；桌面入口及 HTML IME 聚焦回歸 **42 PASS／7.10s**，Ruff、格式與 Bash 語法檢查通過。合成 IBus 鍵產生注音 preedit 與「北市」commit。關閉 IBus daemon 後，Windows `Start-SIRO.cmd` 真冷啟 PASS：healthy、唯一 native PID 102270、`ibus engine=chewing`、原生程序有 `GTK_IM_MODULE=ibus` 和 `XMODIFIERS=@im=ibus`，原模型／STT／B 聲線路由正常；目前留給使用者使用。

限制：尚未由真人在 WebKit 視窗按實體注音鍵、檢查候選字位置與選字手感；合成探針與環境檢查不能代替此項。完整 `scripts/check`／remote CI 未跑，T10-UI-01 仍 PARTIAL。下一步是使用者在「聊聊」輸入框試打一段注音；若仍有特定按鍵問題，沿原生焦點與候選字顯示追查，不再把 Enter 回歸當成全部修復。

## 2026-10-18 — T10 中文 IME 輸入修復 LOCAL_VERIFIED

修正聊天輸入框把部分輸入法的選字 Enter 當成送出的問題：明確追蹤 compositionstart/end，並兼容 `isComposing`、舊版 `keyCode/which=229`；composition 中不攔截 Enter，正常 Enter 送出、Shift+Enter 保持換行。回歸測試在新部署快照 **3f50058d4538** 通過，所有 `test_frontend_*.py` **352 PASS／39.30s**；Ruff、格式、source hash、locked uv sync、compileall、Cargo build 均通過。8000 正式頁確認送出修正版，Windows `Start-SIRO.cmd` 重啟後 ready healthy，唯一 native PID **87599**；模型、音訊、Live2D、TTS 路由沿用原設定。報告：[T10 IME 驗收](evidence/T10-IME-2026-10-18/REPORT.md)。

限制：測試使用合成 composition/keyboard events，尚未由真人在原生視窗輸入法選字驗收；Windows 本機 `uv` 無可用 Python 3.14 且設定為 offline，因此驗收都在實際執行產品的 WSL Python 3.12 部署副本完成。請使用者在新視窗試打中文確認體感；若仍無法輸入，再依輸入法與按鍵時序追查。未跑完整 `scripts/check`／remote CI，未操作私人對話或開啟麥克風。

## 2026-10-17 — D67 / T08 一般對話避免冗長並實際部署 LOCAL_VERIFIED

依使用者反映回覆太長、常生成到上限，補強 `assemble_prompt` 的日常回覆規則：普通聊天直接回答 1–3 句、通常最多 120 個中文字；只有明確要求或任務需要時才展開，答完即停，不重複或自行續寫。保持 512 token 上限、`done_reason=length` 未完成標記、partial 保留與不自動重送；停止按鈕沿用 D64 已驗取消路徑。

真實本機 `qwen3:4b-instruct` 候選訊息格式、合成問題「你可以做什麼？」、相同 seed／temperature／512 預算的單次前後 probe：既有提示 115 tokens／120中文字／4句；更新提示 23 tokens／30中文字／2句；兩者皆 `done=true`、`done_reason=stop`，沒有到生成上限。這是合成單題的提示效果驗證，不代表每一題都固定長度，也未讀取或寫入私人對話。

語意提示更新後相關副本回歸 **436 PASS／1既有 Starlette warning／34.73s**。新環境首輪431 PASS／5 FAIL 是 Jieba 初次編譯產生原有 SyntaxWarning；保留失敗，照標準 compileall 後原命令通過。再修正單純英文字元以符合 Ruff 後，最終實際部署副本 `7f8a0034fb1d` 完成 locked uv sync／compileall／Cargo build；精確最終副本人格回歸 **5 PASS／0.19s**，Ruff、format、mypy均通過。兩份報告均不把初輪失敗說成成功。

已由 Windows `Start-SIRO.cmd` 重新啟動此副本：正式8000 healthy、唯一native桌寵 PID 80741、模型 `ollama:qwen3:4b-instruct`、Live2D及 B 聲線路由正確。另以合成文字經授權 speech API 預熱 B worker 20.616s，產生3.68秒 WAV；沒有建立對話、開啟麥克風或播放喇叭。驗收與命令見 [D67 報告](evidence/T08-REPLY-LENGTH-2026-10-17/REPORT.md)／[機讀結果](evidence/T08-REPLY-LENGTH-2026-10-17/RESULTS.json)。完整 `scripts/check`、remote CI 與更多真人長回覆體驗未跑；真人再試後可回報是否仍常碰到上限。未commit／push。

## 2026-10-17 — D66 / T15 使用者選定 B 聲線已套用 LOCAL_VERIFIED

使用者聽選 B「甜柔、親切」後，已固定該原創合成音檔及對應台詞，以官方 Qwen3-TTS0.6B Base／既有可取消 worker 產生新對話語音。新增有界嚴格本機 voice profile、明確 voice_id/cache 分流、無錯誤靜默退回 Kokoro；selected profile 在 legacy 模式同樣啟用 owned lifecycle。worker固定本機模型／offline，Origin、session、唯一播放owner、舊completion／cap裁決保持。原始B不是私人錄音或既有原個人聲線。

已建立並啟動新 ext4 副本 `80c1ebe93ae2`：locked sync／compileall／Cargo build成功，372份非文件來源與manifest一致。最終相關 **431 PASS／1既有warning／26.54s／exit0**，保留原5秒啟動gate；來源聚焦158PASS、最後profile／選單53PASS（有重疊）。Ruff／format／mypy五檔通過。初次副本426PASS／5FAIL來自第三方Jieba在清空環境的subprocess缺canonical bytecode而發出SyntaxWarnings；只補正常dependency compileall，保留stderr要求／原tests／warning filter／第三方source，失敗留證後重跑全431通過。

真新台詞 clone3.68s、PCM peak0.3555／削波0；cold18.848s，同句cache0.003s；真推論中取消0.093s、舊worker已reap／owner清空、取消後可重啟及close。真原生WebKit經speech HTTP播放至ended／全文完成，Pulse sink被觀察、sandbox保持、server及worker關閉。新副本真Ollama／Haru整合PASS：ready1.018s、正確B route、短句completed、長文取消0.076s、0工具效果，native及backend清理完成。

私有設定與SQLite一致備份後，僅正常TERM關閉舊指定桌寵，更新wrapper／選單並經Windows入口重開。**目前healthy且唯一新副本gjs，tts=`local:qwen3-tts-0.6b-base:siro-sweet-b-v1`**；另經正式8000授權speech API合成合成台詞PASS（12.44s含模型啟動，未建立對話／未開麥／未播喇叭），保留worker warm供使用者。第一次入口檢查早於ready連線被拒，隨後正常PASS，未將初次拒連說成通過。

完整來源／命令／模型revision／結果／限制見 [B套用報告](evidence/T15-VOICE-B-2026-10-17/REPORT.md)／[RESULTS](evidence/T15-VOICE-B-2026-10-17/RESULTS.json)。下一步是使用者實際新對話聽感、破碎聲及設備聽驗；目前數位檔案無削波不代表所有主觀破音已解決。Cold與新句合成較慢，首音SLO仍未通過；全scripts/check／remoteCI／硬體與正式發布未跑，未commit／push。D65試聽歷史保留，其「未套用」由本節後續結果取代。

## 2026-10-17 — D65 / T15 三段角色聲試聽已產出，待真人聽選

使用者真人回報 D64 Kokoro 備用聲線機械、音色不好且破碎；希望動漫感、可愛活潑。D64 只代表功能／取消的驗證，**聲音品質未通過**。沿 D65 先做本機元氣／甜柔／俏皮三種角色聲試聽，待真人聽選後才接入；正式入口暫仍保持 D64 副本，不修改私人資料或正在使用的聲線。

已用合成台詞檢查舊 Kokoro raw float／PCM16，energy0.5及1.0皆 finite、over-full-scale0／PCM saturation0；不能由此排除原生播放、分段接縫或感知失真，未宣稱破音已解決。官方 Qwen VoiceDesign 固定 revision 與所有檔案已核對上游 SHA／Git blob，獨立 E 槽 WSL 模型及環境；首次 CUDA index 的 cuDNN 下載 timeout 留證，改同版本官方 PyPI wheel 後成功。未外送真人錄音／私人文字，未改 production 或專案 lockfile。

隔離 SDK0.1.1／Torch2.8.0／Transformers4.57.3 在 RTX3050 成功載入；三段真 offline 24kHz PCM16 試聽已產出，A元氣8.56s／B甜柔8.00s／C俏皮7.84s。生成14.599／11.498／12.089s、各一個 EOS、未達512 cap、無非有限值／削波，實際連線嘗試0；5ms頭尾fade，沒有改音高。真本機 ASR 三段都有 coherent final（仍有省略／同音差異，不稱品質通過），worker均回收；GPU推論程序已退出並釋放顯存。

本機腳本 `.siro-data/wsl-setup/prepare_anime_voice.py`、`inspect_voice_quality.py`、`audition_anime_voice.py`、`check_anime_auditions.py`；三個音檔及freeze留同目錄 `voice-quality`（Git ignored），只公開合成 metadata。[證據及重現命令](evidence/T15-VOICE-2026-10-17/REPORT.md)。下一步：使用者聽 A／B／C 選音色及回報是否仍破音，選定後接入可重用角色聲及重驗原播放／取消契約；正式 D64 聲線尚未替換。生成耗時不是首音 SLO，本輪沒有跑全 pytest／CI、沒有將未驗品質寫成 DONE。

## 2026-10-17 — D64 桌寵／語音／長回答停止 LOCAL_VERIFIED，真人操作待驗

依使用者回報及「繼續」，完成同一 T12 桌面體驗修復切片：麥克風可見開關、原生 audio-only 許可、WebM Opus 錄製與本機 Whisper small 辨識；修 WebKit 有聲播放政策，保留既有 Kokoro 朗讀。聊天改獨立側欄，控制列位於角色下方；可直接拖角色、用－／＋／百分比還原作 60%–150% 有界縮放。單一 WebView／session／renderer／audio owner、sandbox／Origin／kill switches 保持。[使用方式](WSL_SETUP.md)。

停止修復涵蓋 HTTP 尚未回 headers、UI 提交尚未取得 turn_id、晚到串流／terminal、錄音／辨識／播放的取消。取消 ACK 不當作完成，未確認時保持明確狀態及提交阻擋，不自動重送；既有 512 輸出上限與 D63 截斷失敗裁決保持。真 Chromium／Ollama 長回答途中按停止：**cancelled／0.072s／0 工具效果**，後續文字穩定且顯示已停止；這不是模型 GPU 資源釋放 SLO 的量測。

最終 ext4 副本 `218c21940570` 相關 **327 PASS／1 既有 warning／21.01s／exit0**，包含未修改的 5 秒啟動 gate；來源前端／session 全回歸 **381 PASS／1 warning／54.28s／exit0**，兩組有重疊、不加總。HTTP 新 7、前端停止新 10、麥克風新 5 與本機 STT 新 14 案例均通過，各有實作前失敗證據。相關 Ruff／format／mypy、locked sync／compileall／Cargo build 通過；沒有冒稱本輪完整 scripts/check 或 remote CI。

真 native WebKit：audio-only 裝置開啟後立即停止、未錄音；合成語音經原錄製／轉 WAV／真本機 ASR／stub submit 全程通過，tracks／controller／worker 回收；真 speech HTTP→原播放器→Pulse sink／ended 通過。Whisper small CPU 冷辨識 9.094s，合成「本機」被辨為「本集」，保留品質缺口。GTK／Haru 實測聊天與角色／控制列分離，60%／100%／150% 均可見，唯一 iframe；Chromium 真 pointer events 送一次拖曳請求，**實體 Windows 滑鼠拖動、真人收音及聽感未驗**。

補 Ubuntu 官方 GStreamer Bad Plug-ins（缺 uritranscodebin），診斷用 Pulse／GStreamer tools；模型與依賴官方來源／授權核對，新增 faster-whisper 1.2.1、PyAV 相容鎖 16.1.0，uv.lock 103 packages。模型僅顯式設定的本機路徑、offline、單一短生命 worker、原音不保存；未配置仍 disabled，不新增 cloud key。詳 [依賴](DEPENDENCIES.md) 與 D64 決策。

本機設定與 SQLite 先以一致備份保存在 Ubuntu 私有目錄，沒有讀取對話或複製到 Git。更新本機 wrapper／選單後，**已經 Windows `Start-SIRO.cmd` 實際啟動並留給使用者操作**：healthy、model／audio／tts 路由正確、唯一指定副本 gjs。371 份非文件來源與副本 manifest 再核對一致，驗收後文件更新不冒稱已進入舊副本。完整命令、根因、失敗與證據見 [D64 報告](evidence/WSL-UX-2026-10-17/REPORT.md)／[機讀結果](evidence/WSL-UX-2026-10-17/RESULTS.json)。

下一步是使用者實際說一句／聽回覆及操作拖曳，沿 T12／語音品質 gate 補真人證據；原個人聲線、Haru 新動作／自由漫遊、24h／其他硬體／完整 CI／正式發布仍未驗。未改 Core／Policy／DB schema、未 commit／push；前輪變更保持。本項限定 local 修復通過，不代表全產品或 L3 體驗完成。

## 2026-10-17 — E 槽 WSL 本機補齊 LOCAL_VERIFIED；文字／角色可啟動

依使用者「幫我補好／繼續」，完成本機 Ollama0.34.3＋官方qwen3:4b-instruct、已明確同意授權的Cubism Web5-r.5／Haru、GJS／GTK／WebKit與中文字型、Kokoro本機備用素材。原source留E槽，執行副本／專用Python3.12.14／cache／資料位於E槽Ubuntu VHD。新增`Start-SIRO.cmd`、本機wrapper／設定／開始選單；**已實際經Windows入口開啟並留在執行中**，healthy、正確模型／TTS路由、唯一gjs，未退回offline demo。[啟動說明](WSL_SETUP.md)。

修Windows腳本換行、外置venv桌寵入口及data/log路徑；以hash核對ext4副本解原DrvFS載入問題，未改DB或放寬5秒gate。真QA另發現Ollama截斷假completed，依D63先RED後修唯一adapter葉節點：length／EOF失敗、partial保留、工具完整終止及cleanup後才下放，取消／重試邊界保持；一處舊測試工具chunk預期經審核調整，其他原安全斷言保持。

最終副本`8fb7636d6e98`的`check_ext4.py`實跑 **261 PASS／1既有warning／17.34s／exit0**，含原未改5秒測試。adapter來源回退31FAIL／6PASS→新37PASS，相鄰177PASS；桌面腳本51PASS，相關Ruff／format／mypy／Bash syntax通過。最終副本locked安裝／compile／Cargo build exit0；較早Rust24PASS，不冒稱最終再跑。真Chromium／Ollama／Haru／GJS合成整合 **PASS**：ready0.913s、回覆「你好呀！😊」、completed、0工具／0pageerror；原生ready／alpha／sandbox均true、snapshots3，關閉／stop／PID／source資料隔離通過。完整本機manifest、精確命令與機讀結果見 [驗收報告](evidence/WSL-SETUP-2026-10-17/REPORT.md)。

SDK外置build lock相容修補後audit0／build成功；原archive pin／renderer source不變。Kokoro合成中文24kHz、2.432s、cold4.7425s、連線嘗試0；非真人聽驗，原Qwen reference未提供。現有native worker取消限制、原生EGL warnings及minimal doctor缺項均如實留證。最初兩輪QA診斷路徑／metadata複製EPERM及程序檢查fixture錯誤保留，不將其當產品PASS或刪掉。

**仍待配置／驗收**：語音辨識provider（目前audio disabled，可打字）、原個人聲線、真人播放／麥克風／語意／首音SLO、Haru新動作與自由漫遊、24h／硬體／完整check／remoteCI／正式發布。未新增cloud key、改Core／Policy／schema／Python或Cargo lock；使用者與其他工作變更保留，未commit／push。下一步：使用者試用文字／角色操作與備用語音，沿T12／桌面體驗卡補互動證據，再獨立配置語音辨識／原聲線；其餘既有產品gates保持。

## 2026-10-17 — Windows／WSL 新版執行驗證 PARTIAL

本機dc7382e起始clean；新版Windows checkout重新帶入scripts CRLF，首輪62PASS／2FAIL，實際bash\\r啟動拒絕。僅補scripts/* eol=lf並正規化換行，無production邏輯變動；外置WSL helper沿既有override設定Rust binary。修後相關Python **73PASS／1FAIL**，限流／桌面交接／語音計畫為合成；原5秒啟動gate兩次重驗仍失敗，根因UNKNOWN，依runbook停止並留blocker，未放寬門檻。

真Cargo build exit0、Rust **24PASS**；Python3.12.14的99套件相容。隔離合成資料真scripts/start --demo＋HTTP／Chromium：4.084s ready200、JS errors0、離線訊息收送PASS，stop／PID清、事後無程序或listener殘留；不冒稱真provider或完整graceful log驗收。正式入口實測缺模型exit1，桌寵缺GJS／GTK／WebKit exit2、無renderer的/desktop503。使用者確認目前沒有模型設定或Live2D素材，**完整Companion BLOCKED-EXTERNAL**。

尚缺provider設定、合法Cubism／Live2D資產、native桌寵依賴與其外置venv接入、原聲線／真音訊驗收；5秒gate另待定位。未跑完整check／全Python／remoteCI／硬體／發布，不改Core／DB／權限或私有資料。[本輪命令與限制](evidence/WSL-RUN-2026-10-17/REPORT.md)／[啟動blocker](evidence/WSL-RUN-2026-10-17/blocker.md)。

## 2026-10-16 — FIX-026 / D62 掃描誤報 DONE / CLOUD_VERIFIED

已重現940bdb7的真cloud失敗：2129 Python／24 Rust與靜態／schema皆PASS，末secret gate1332項誤報。只在原helper加入13個已審核歷史檔的exact path＋完整blob SHA256＋完整detector tuple batch SHA256/count綁定；保留所有檔案bytes／links、原六pins／scanner範圍／excludes與production。不將一般hex或整個資料夾放行。

原版新測試2FAIL／34PASS；最終原25＋新37 **62PASS／12.60s**。改blob／tuple／同數量duplicate、path／symlink／讀取錯誤、真scanner新增合成credential於snapshot／舊test／source／workflow皆拒絕。owned clean candidate原掃描1338 findings **gate EXIT0／6.869s**；Ruff338／完整候選mypy268／helper及tests mypy2 PASS。獨立review無blocker，另12個同數量duplicate反例全拒絕。

修復5e4506a已推送，exact-head [Actions38868369775](https://github.com/pigon2233/SiroV2/actions/runs/38868369775) **SUCCESS**：完整scripts/check完成，2166 Python PASS／5原opt-in SKIP／7warnings／261.93s，24 Rust、Ruff338／mypy268／schema／原scanner與strict gate全PASS。解除本卡交付阻擋；只提交本卡，其他startup／UI及前輪文件保持未提交。最後cloud驗收紀錄已另存本機，正式發布／硬體／產品品質gates保持。[本卡證據與回退](evidence/FIX-026-2026-10-16/REPORT.md)。

## 2026-10-16 — D61 清單重驗／T27 真交叉編譯 PASS；Git 交付另有阻擋

依使用者重申清單核對：FIX-022–025本卡16份source／test／firmware hash與前輪完整合格候選相同；本次五組新回歸實跑 **111 PASS／19.55s／EXIT0**。MQTT拒絕ACK／unknown／bounded回收、模型安全錯誤、SQLite關閉及Rust回收保持。WAL／NORMAL／5000原已有；strict Python缺件明確拒絕、無host fallback，維持原認證profile，其他平台未認證。只補文件證據，沒有再次修改production。

ESP32以自建暫存PlatformIO Core6.1.19、原pinned esp32dev設定完成**真cross-compile EXIT0**；RAM45276／327680、Flash777901／1310720。example帳密、未燒錄／操作實板；真NTP／目視LED及A18仍HARDWARE PENDING。[編譯與清理證據](evidence/T27-firmware-build-2026-10-16/REPORT.md)。

續作發現本機新提交940bdb7（非本輪根代理建立），同時納入大量舊驗證快照。owned clean clone的原scanner／strict gate **EXIT1，1332項**：1331個摘要／來源指紋、1個合成fixture。未識別真credential，但40張舊圖未視覺公開審查；故交付 **BLOCKED_BY_DELIVERY_REVIEW**，沒有push、重寫提交、刪資料或放寬gate。323份全域source先核對相同後，另有並行UI／啟動修改；本卡PASS不涵蓋那些新工作。

接續：先單獨收斂940bdb7的公開範圍／metadata檢查，再驗exact-head遠端CI；硬體依既有單次probe指南驗收。四卡local DONE保持，正式部署與其他產品品質gate不解除。[清單重驗與界限](evidence/D61-resilience-2026-10-16/CURRENT_HEAD_RECHECK.md)。

## 2026-10-16 — D61 / FIX-022–025 DONE / LOCAL_VERIFIED

已核對使用者六項急修，完成四項局部修復：MQTT wire status／unknown ACK／terminal fence／1024 RAM cap與prune；模型壞JSON／Unicode安全分類及Ollama error envelope拒絕；SQLite明確close而非改原PRAGMA；Rust Execute reap／活group ownership／cap+1完整輸出判定。最終review另修late duplicate false-negative及不可signal group假stopped，均有真Broker或無特權kernel反例。Core／ports／DB schema／權限／UI／failover政策／固定sandbox profile與D60 firmware保持。

最終owned隔離Git candidate（public HEAD＋明確修改／9新檔、323 source/test/build hash一致）完整 `scripts/check` **EXIT0／545.074s**：**2129 PASS／5原opt-in SKIP／7既有warnings／253.93s**；Rust24、fmt/build/clippy、Ruff337／mypy267、schema及原scanner/strict gate全部PASS。初輪dirty工作區雖2129PASS，scanner掃到ignored caches與舊untracked驗證檔而EXIT1，完整保留失敗，不改門檻、不刪原資料；最終不是remote CI／正式發布。

Root source-only before24FAIL/3PASS→修後全PASS；model24FAIL/1PASS→25PASS；Rust11PASS/9FAIL→24PASS。三store同SQLite同時20MQTT／20合成對話／20來源記憶，數量／最新state／integrity正確。89 sandbox原測試亦PASS；「缺WAL」「整eventloop崩潰」「共享cloud budget未扣」「靜默無sandbox」等過廣指控已依契約分類，不照單改架構。

解除本四卡local BLOCKED_BY_FIX；T27實板／PlatformIO／真provider、其他OS strict profile及remoteCI／release仍各自未驗。RI005與FIX002／005／006品質gate保持，不重編RT、不撤原限定DONE。Architecture YELLOW/CONDITIONAL，無新owner／scheduler／schema。接續既有T27真板、T19/T20結果判定與產品品質驗收。[修復登錄](runtime-evolution/FIX_REGISTER.md)／[完整證據與回退](evidence/D61-resilience-2026-10-16/REPORT.md)。

## 2026-10-16 — T27-FIX-01 MQTT／ESP32 時間相容 LOCAL_VERIFIED，真板仍待驗

命令保留 ISO 並加整數 expires_at_epoch，simulator 僅接受核對一致的已知 mirror；state 支援 UTC int／float epoch，ISO 優先，無效時間先拒再寫入。firmware 對時最多等30秒，未就緒 restart＋return，loop 亦阻擋。新增 aiomqtt 單次 LED 驗收腳本，沿既有 tracker／projector／registry／臨時 SQLite，applied ACK＋新鮮無矛盾 power:true 才 CONFIRMED；不自動重送或改正式資料。

原版5 RED／28 PASS；新時間格式33 PASS。真 Broker＋合成 ESP32、既有裝置／World／HA／邊界等 **71 PASS／18.38s**，host 實際 clock/setup/loop 的9控制流程 PASS，Ruff／format／mypy／diff PASS。唯讀review發現 ACK-only 狀態與同秒矛盾誤確認，已在 probe 局部修正並加真 Broker 回歸，不改 Core 或 World 排序。

實際本機1883無 Broker，嘗試 exit1／unknown／publish0；沒有 PlatformIO，真板編譯／燒錄／NTP／LED及 A18 **HARDWARE PENDING**。T27維持 simulator 通過、真硬體未驗，完整 CI／發布未跑。只改兩個 production 檔；前輪 UI SHA 保持，DB／權限／依賴／RT 歷史不變。[操作指南](ESP32_MQTT_VERIFICATION.md)／[完整證據與回退](evidence/T27-mqtt-time-2026-10-16/REPORT.md)。

## 2026-10-15 — T10-UI-01 網頁改版首切片 LOCAL_VERIFIED，整體 PARTIAL

已將對話、任務、記憶、能力、電腦、技能、設定、權限、系統分成九個獨立 hash 工作畫面，重做視覺與導覽；共用停止／語音控制、單一 session／socket／renderer，非目前畫面 hidden＋inert，不將全部功能折疊在單長頁。電腦／技能捷徑返回對話；操作更新提示不搶頁。直接 file 開啟明示唯讀預覽，不冒充服務已連線。

只改 production index.html，新增24導航／生命周期案例；**全部前端333 PASS／21.21s**，原 tests／後端／DB／授權／providers／依賴不變。Ruff／format／mypy／diff PASS。真 main／Rust／SQLite 三次啟動與 CUA 點擊驗待審0讀取、明確批准1讀取、跨頁／重啟保結果且不自動執行；24 DOM檢查含四種窄窗12案例、鍵盤、草稿／歷史。source-only隔離回退 RED→PASS，三輪join／temp／自建tabs清理完成。

**T10-UI-01仍PARTIAL**：真Live2D恢復／表情／嘴型及桌面宿主／新動作未驗，fixture明示synthetic renderer；file分支有合成測試，瀏覽器工具政策拒file直接操作。完整CI／200%zoom／完整無障礙／真人體驗／Git發布／部署未跑，不套用前輪PASS。新fixtures兩次錯誤與新test harness修正留原證據；獨立review只到初審，final受帳戶限制，root實測不冒充final批准。

接續：T12現有真renderer的切頁重繪／唯一owner驗收，再沿任務詳情、記憶搜尋、設定用語補完。自由桌寵／全身動作仍明列未完成；RT歷史與RI-005／FIX-002／005／006 gates保持。沒有live8026／私人資料操作。[完整驗收與回退](evidence/T10-UI-01-2026-10-15/REPORT.md)。

## 2026-10-15 — T10-UI-01 介面重設計 TODO / Planned Only

依使用者要求將 UI 全面重設計加入未完成工作，研究 frontend-design、Hallmark 與官方 VPet；已整理 [畫面分工、視覺草案、最小切片與驗收](runtime-evolution/INTERFACE_REDESIGN_PLAN.md)。對話、任務、記憶、能力、設定分開，詳細診斷移到次層；不能把全部功能折疊在單長頁。角色以 VPet 式活動／小氣泡喚起專頁，沿既有 Companion plan 完成真桌面宿主與全身／動作，不借 VPet 的 Windows／PNG 實作宣稱 Live2D 已完成。

同步 TASKS 的 T10-UI-01、EXPERIENCE §4、D59、Companion plan 與 Runtime Roadmap。保留現有 session、批准／取消、持久任務與 renderer／音訊唯一 owner，網頁分頁不等待完整桌寵或自主更新。缺少動作仍是我們的交付責任；沒有重開或重新延期已完成 RT。

本輪範圍是規劃文件，**未修改 production、未安裝依賴／素材、未操作私人服務／資料**。`git diff --check` EXIT0；七份文件的空白／新規劃本機連結與修改範圍檢查 EXIT0（缺失連結0、非預期 tracked 修改0），只讀獨立檢閱無 blocker，已補網頁／桌面分開驗收的澄清。原型、真瀏覽器視覺、Live2D／原生桌面及真人體驗驗收均 **NOT_RUN**，不能套用前輪 CI 為改版 PASS。下一步：T10-UI-01 對話／任務兩個獨立可操作原型，再逐頁移轉；RI-005 與 FIX-002／005／006 gate 保持。

## 2026-10-15 — D57 / FIX-021 + RT-005-FIX-02 DONE / LOCAL_VERIFIED

「電腦協助 → 交給 SIRO 的任務」已接通既有GoalService/Planner：選1–5exact文字檔，建立待審不讀取，明確批准後有界盤點TODO/未勾選待辦，保存檔案/行/實際SHA/time。可停/取消，前景與tools-off優先，重開保進度/未知意圖而零autoexecute。讀取完成不代表待辦已執行，未稱自主產生目標或學習策略。

完整clean public fetchedGit `scripts/check` **EXIT0 /578.090s**：**1,994PASS /5原opt-inSKIP /7既有warnings /259.88s**（collected1,999）；Rust13/fmt/build/clippy、Ruff328、mypy261、schema、原scanner/strictgate全部實際完成。15source/testhash保持，134原Python與13SQL不變，唯一journalfixture固定13slot/name、其餘原assert保留；495observedownedprocess全gone、rootsremoved。

真正main/HTTP/Rust/SQLite/IAB三次啟動PASS：原結果/待審0steps保留，correctedsource新舊觀測分開，crosssession404/錯revision409零extra reads；三組parent/Rust正常TERM/drain/join、temp/tab清。D57exact8source-onlyrollback保schema14/latestTask/legacydata與3SQLdump；RT005timeoutleaf另reverse真RED→reapplyGREEN。

完整第3次4FAIL留原證據：schemafixture最新13假設最小改固定journal13identity；cancel5.090748s違反原5s。受控baseline/candidateterminaldelay均重現既有budget缺陷，D58只soleallargumentswait4.0留1s，contextual/mixed4.75和backend4.5保持，原25cases與新2/精確leafrollback通過。額外fullwalltime來源仍未定位，不怪goal/schema邏輯、不放寬SLO/skip。

Architecture YELLOW/CONDITIONAL；FIX021/RT013FIX01/RT005FIX02限定localVERIFIED，解除本localBLOCKED_BY_FIX。exactnewheadcloud/公開範圍另驗，RI005正式發布與FIX002/005/006智慧/語音/搜尋gates保持；T19/T20原L1不冒稱整體自主DONE。下一三原scope（非ranking）：T19/T20結果完成判定；FIX002/005/006可核對品質；T21/T32/RI005擴權/發布交接。CodebaseMemory不可呼叫/reindexNOT_RUN。沒有live8026/privateDB/chat/WAV/key/config/models/GPU/deploy。[報告](evidence/T19-goal-loop-2026-10-14/REPORT.md)。

## 2026-10-14 — FIX-020 / D56 release source identity DONE / LOCAL_VERIFIED

RI-005 immutable-source 研究證明原 source digest 的檔名/內容串接有歧義：不同檔案能共享同一批准摘要。分類 REQUIRED_FIX/HIGH、ORIGINAL_DESIGN_ERROR，不是 SHA256 密碼學碰撞。先修唯一 production `core/releases.py`：明確 v2 domain/count/path/content length framing，完整 HMAC 綁新 tag。v1 payload/hash 歷史語意保留，但不能授權 stage/launch/rollback；無自動重新簽署、receipt 改寫或 DB migration。新批准需新 immutable version。

原漏洞15 RED→PASS；final216相鄰PASS、196原assertions保留、v1固定向量與獨立source-selection oracle保持。真五個自有子程序驗 1→2→1、HTTP readiness/source origins/key不進child、正常TERM/drain/join、保三批最新conversation/memory/ledger；wrongABI/tamper拒、零DB改動。精確source-only reverse→15FAIL、reapply→15PASS，原source其他136檔保持，無production回退。

最終真正publicGitcheckout完整 `scripts/check` **EXIT0 / 637.507s**，**1,813 PASS / 5原opt-in SKIP / 7既有warnings / 303.43s**。Rust6/fmt/build/clippy、Ruff321/mypy254、schema與原scanner/strictgate通過；9個source/test hash保持、childrenjoined/tempremoved。171原source/build/schema檔170不變，134原Python test/helper檔127不變。first clean run為修復oracle獨立性先中止並清理，列NOTPASS，不混入final。

FIX-020解除其source-format blocker；RI-005仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**。tiny kernel projection已驗，但directbwrap monitor TERM不graceful及mutable destination alias仍需caller接入修正；沒有在本卡擴loader/owner/SDK/權限/DB/UI。Architecture YELLOW；identity tests/evidence GREEN，runtime元件YELLOW，live data/migration/permissions/formalrelease RED。

下一三既有scope（非ranking）：RI-005 exact captured source/import window；RI-005 approved maintenance handoff/adoption；RI-006 safe定位證據→最小真修復提案。RT-011/013/015 scopedDONE、D39/D48–D55其他結果與FIX002/005/006產品品質gates保持，不重編/重做已解問題。

CodebaseMemory工具不可呼叫、graph/reindex NOT_RUN；所有probe使用公開/合成、自有temporary資料，無live8026/privateDB/chat/WAV/key/config/models/GPU/formaldeploy。Git推送與exact-head cloud另驗，不把localPASS等同remote。[完整驗收、限制與回退](evidence/FIX-020-2026-10-14/REPORT.md)。

## 2026-10-14 — RI-006 / D55 唯讀改善提案切片 VERIFIED

電腦協助新增「改善建議」手動入口：重用D41同session/route/latest/900s事實，failed + HTTPStatusError→有來源的調查/測試/相容/回退計畫。根因UNKNOWN、分類DEFER、patch=null，不能自批、重試、改碼或deploy。每GET重查canonical來源，無新cache/schema/scheduler/owner；unstarted/legacy/restoreoff不initialize/reconcile/read。no-store涵蓋auth/錯方法/安全503；UI owned取消/5s deadline/epoch撤除過時卡，textContent/完整closedshape驗證。

最終truepublicGitcheckout含FETCH_HEAD的scripts/check **EXIT0 / 499.591s**；**1,798 PASS / 5原opt-in SKIP / 7既有warnings / 211.70s**；Rust6/fmt/build/clippy、Ruff320/mypy253、schema與原scanner/strictgate保持。原完整firstcandidate3FAIL（inventory/speech fragment新增依賴）先留證，僅optional新hook局部修→142focusedPASS，不改舊測試；95newcases，原132testfiles bytes全保持。獨立review的no-store1RED已修；reviewer最後turn/前端agent遇quota，不假稱independent final approval。

真正main/D50 composition、自有SQLite/randomloopback/In-appbrowser：手動click顯示source/UNKNOWN/計畫，fixture更正來源→重查撤舊card；最終SIGTERM exit-15/actualshutdowncomplete/joined/temp/tabcleaned。第一harness143原因UNKNOWN、已人工清理，不列gracefulPASS；兩次隔離child session的重驗正常。exact6source-only reverse/reapply、D41/TTS保持。CodebaseMemory不可呼叫/graphreindex NOT_RUN。

RI006整體 **PARTIAL**，D55 singleclass caller局部 **VERIFIED**；真rootcause定位/patch/自主執行另驗。RI005 **PARTIAL/BLOCKED_BY_RELEASE_INTEGRATION**；RT011/013/015 scopedDONE、FIX002/005/006產品gate保持。Architecture YELLOW：tests/evidence GREEN；proposal/Core/Gateway/UI YELLOW；liveDB/migration/permissions/release RED。沒有額外scopedblocker、RT重編/ranking或新全局abstraction。

下一三既有scope（非ranking）：RI005 exact captured package/import window；RI005 approved maintenance→runtimehandoff/adoption；RI006 safe定位證據→最小真提案。無live8026/privateDB/chat/WAV/key/config/models/GPU/formaldeploy。Git發布與new exact-head CI結果另記，不把localPASS當remote。

[完整驗收、限制、回退](evidence/RI-006-2026-10-13/REPORT.md)。

## 2026-10-13 — FIX-016 / FIX-017 DONE / VERIFIED

Exact source4811db2 [Actions38395186441 SUCCESS](https://github.com/pigon2233/SiroV2/actions/runs/38395186441)。Remote1703PASS/5原opt-inSKIP/7既有warnings/206.05s；原102environment-skippedcases全執行。Rust6/fmt/build/clippy、Ruff318/mypy251、schema、原scanner/strictgate全PASS。TruepublicGitcheckout/fetch含FETCH_HEAD：local1703PASS/5opt-inSKIP/7warnings/207.90s、scripts/check全EXIT0/492.046s。未mute、新增skip或放寬隔離。

FIX016只修existingtool声明、exact6publicpins、Rustcfgtest3literal、supportednativeCI環境、SQLitequoted-keyportable中間fixture與exact.git adminmetadata範圍。FIX017只修TTSoptionalKokoroSDK在owner前eagerimport：移既有offlooplazyrender，5RED→PASS/34related/exact2rollback；Gateway/owner/SQL/權限/其他production保持。

303baseline297不改、6existing改/3new、onlyproductionTTSleaf；finalexact9source-onlyrollback/hashPASS、ownedchildren/temp全部清理。CodebaseMemory不可呼叫/graphreindexNOT_RUN，以source/actualtest/hash作證。Actual查無PR，本次修push Actions。

OverallarchitecturehealthYELLOW；recentimprovements為CI可重現與原owner-before-provider不變量恢復，沒有新runtimeabstraction/cycle/globalowner。Regressionrisk原coldbootstrap、supportedprofile及Gitmetadata盲區已補；真voice/LLM品質不由CI代證。Technicaldebt仍publicpin變動需re-audit、extra3.12preinstall、general3.12matrix/nativehardcancel未驗。

Freezezone：testedLinuxCI/tests/evidenceGREEN；TTS與其他runtimeYELLOW，liveDB/migrations/permissions/releaseRED。NewscopedblockersNONE。解除BLOCKED_BY_FIX: FIX016/FIX017；RI005仍PARTIAL/BLOCKED_BY_RELEASE_INTEGRATION，原RT011/013/015scopedDONE、FIX002/005/006產品gates保持。KEEP/SPLIT RI005remainingadoption/approvedhandoff，KEEP RI006readonlyproposal；REJECT duplicateSDKloader/owner/updater，無RT重編/ranking。

Recommendednext3原scope（非ranking）：RI005old/unmanagedwriterabsence；RI005immutableapprovedexacthandoff；RI006source-boundreadonlyproposal。沒有formaldeploy或live8026/privateDB/chat/WAV/key/config/model/GPU操作。

[CI證據](evidence/FIX-016-2026-10-13/REPORT.md)／[TTSleaf](evidence/FIX-017-2026-10-13/REPORT.md)。


## 2026-10-13 — supported full regression PASS / final Git-metadata CI gate

FIX-017 D54 scopedDONE/VERIFIED：Kokoro optionalSDK延後既有offlooprender，5RED→PASS/34focused/exact2rollback；combinedlocal1702PASS/5opt-inSKIP/3warnings（200.57s；scripts/check全437.331s）。SupportedUbuntu26.04 actual56d0683 run38392435450也1702PASS/5opt-inSKIP/7warnings（189.07s），原102environment-skippedcases全執行，Rust/static/schemaPASS。

整體CI尚FAILED_VERIFICATION：唯一最後.git/FETCH_HEAD publiccommit descriptor誤報。FIX-016只補exact.git administrative-directory排除，保application/.github/.gitignore檢查；realquotedfixture old1FAIL→new25PASS、原checks全留。新的truepublicGitcheckout/fetch-bycommit fullcheck和newheadActions仍PENDING；不能把fullpytestPASS當wholeCI。

RI-005/006暫僅BLOCKED_BY_FIX: FIX-016；原RTDONE/RI-005releaseintegrationPARTIAL/搜尋voice理解品質gates不變。ArchitectureYELLOW，TTSleafgate已解除但voice產品品質不改；CIpendingYELLOW、synthetictestsGREEN、liveDB/permissions/releaseRED。Next3原scope（非ranking）：oldwriterabsence、approvedimmutablehandoff、readonlyproposal。不重編/不加抽象/不deploy。

[CI報告](evidence/FIX-016-2026-10-13/REPORT.md)；[one-leaf repair](evidence/FIX-017-2026-10-13/REPORT.md)。


## 2026-10-13 — actual cloud CI / FIX-016 + FIX-017 final acceptance IN_PROGRESS

GitHub確實是push Actions（查無PR）。原cargo-fmt缺工具與六publicpins gate已修；前一五檔clean full1697PASS/5opt-inSKIP/3warnings、whole419.283s已驗。但actual2324b35 cloud54FAIL揭露supportedLinux環境不足、SQLitefixture假設與busy前optionalSDK eagerimport，不能放行。

FIX-016最小補nativeUbuntu26.04官方CI環境/realnamespacepreflight；不關全局AppArmor/不rootpytest/不新增skip。quoted-key中間assert只接受None或correctexactvalue；原productionSQL/manualhold/effects/DBdump保持，两真SQLite版本各44PASS。FIX-017單一TTSleaf延後Kokoro import到原offlooprender，不改Gateway/owner/logging；5fresh RED→PASS、34relatedPASS、exact2rollback。

兩卡最終合併9source/build/test的完整clean scripts/check正在跑；newexactheadcloud待驗。原RTDONE/RI-005PARTIAL/搜尋voice理解發布gates不變。架構YELLOW；CI及TTS本卡YELLOW到完整驗收，合成testsGREEN，liveDB/migrations/permissions/releaseRED。RI-005/006後續暫BLOCKED_BY_FIX: FIX-016/FIX-017；不排名/不重編。

下一三既有scope：RI-005oldwriterabsence、immutableapprovedhandoff、RI-006readonlyproposal。CodebaseMemory不可呼叫/reindexNOT_RUN；無live8026/privateDB/chat/WAV/key/config/model/GPU/deploy。

[CI evidence](evidence/FIX-016-2026-10-13/REPORT.md)；[owner/import repair](evidence/FIX-017-2026-10-13/REPORT.md)。


## 2026-10-13 — FIX-016 / D53 clean CI repair LOCAL CHECK RUNNING

回應push-triggered Actions失敗（repo查無PR），只修buildtooling：pinnedminimalRust明確宣告rustfmt/clippy；原secretgate只允許六個經官方download驗明、綁完整profileblob的publicpins。既有所有checks/production/oldtests/workflow/版本/locks保留。24新actualscanner/syntheticcredential/變更/錯誤JSON cases PASS，coldisolatedRust RED→PASS，focusedRuff/type/source-docdiff及exact5source-onlyrollback PASS。303baseline中300不改。

完整乾淨公開source scripts/check仍在跑，remoteexact-head尚待驗：**FIX-016 IN_PROGRESS / FAILED_VERIFICATION**，RI-005/006後續實作暫BLOCKED_BY_FIX: FIX-016。前兩次中斷與wrongPython3.12harness不算PASS；環境已尊重原.python-version，actual本機3.14.4，GitHub版本另核對。錯誤harness的MQTT停滯rootcauseUNKNOWN，不改product或測試門檻。

原RTscopedDONE與RI-005PARTIAL/gates不变；下一三既有範圍（非ranking）oldwriterabsence、exactapprovedimmutablehandoff、RI-006readonlyproposal。沒有live8026/privateDB/chat/WAV/key/config/model/GPU/deploy；CodebaseMemory工具不可呼叫/reindexNOT_RUN。

[驗收報告](evidence/FIX-016-2026-10-13/REPORT.md)。


Remote refinement：f253dec已過fmt/build，cargo unit fixture硬編/usr/bin/python3.14而failed；只允許cfg(test)三個literal改/usr/bin/python3，所有asserts/productionprefix保持。完整Rust checks/6tests與exact5rollbackPASS；final完整local與newheadremote仍PENDING，不能把先前4file驗收稱成finalsourcePASS。

## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

D52限定signed source launch／actualloadedidentity／ready切片 **VERIFIED**；RI-005不是DONE。只改既有ReleaseManager/read-schema fact、productlauncher與Gateway composition/ready；新增4份tests。complete manifest/CLI stage-rollback、D49/D50/D51、Core人格/記憶/權限/模型/語音/UI/SQL/deps保留。

operator明確SIRO_RELEASE_ROOT＋原signing-key opt-in；bounded complete signed active package與actualreadonlyschema→fresh-I/-B selectedsrc→existing D50 owner內實際SIRO/Core/Gateway來源及schemaepoch重驗→startup完成後HTTPready version/digest。簽署key不進childenv；originalcwd/data/assets保持，signedmode不provision、不fallback，不隱含migrate。

95新cases；最終相鄰335 PASS／3既有warnings／25.63s，完整 **1,673 PASS／5 real_provider未選／3既有warnings／199.58s**。Ruff315、mypy250（含launcher）、schema、source/tests/docs diff PASS。 真HTTP1.0.0→2.0.0→code rollback1.0.0共3正常child（SIGTERM exit-15、actualshutdowncomplete/joined），每次loaded3origins/childkeyabsent/readyexactdigest、packageunchanged/零pycache；三批conversation/memory/completedledger保留。unsupportedABI／tamper2負向child exit1、零DBeffects/nohostfallback；5childrenjoined/temporaryrootsremoved。

另真oldWALwriter9checks證明新advisorylease與SQLiteBEGIN成功仍不能證旧writer停；managedcontender拒絕、明確close/join才可接入。這是gate證據，不是假停機批准。273baseline中270不改；exact7 source-only disposable reverse/reapply PASS，保所有資料與Git歷史。D48 schema helper抽出前後AST相同；D51 backup/CLI四檔與D50 owner/operations source保持。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：舊／非受管writer停止、parent驗簽後sameUID換包、maintenance→exec CLOEXEC空窗與人工批准handoff未解除。D52只證同schema／D52-compatible src package，任意deps/ABI/migration/其他OS/powerloss/正式deployment未證。FIX-002/005/006產品gates、RT-011/013/015原scopedDONE不變。

Architecture YELLOW；release selector/launcher/Gateway YELLOW、合成tests/evidence GREEN；liveDB/migration/permission/release RED。KEEP RI-005並SPLIT stopped-old-owner/immutable approvedhandoff；KEEP RI-006唯讀proposal；REJECT第二updater/owner/globalstate abstraction。不排名/不重編/不重做DONE。

Git前輪e1bea33已remoteverified；本輪source發布若執行另核對精確commit，Gitpush不等於runtime更新。CodebaseMemory MCP本輪無可呼叫工具，graph/reindex NOT_RUN，原source/真測試/精確hash作證。

沒有重啟live8026／讀privateDB/chat/WAV/key/config/models/GPU或正式deploy；全部程序/DB/HTTP為self-owned合成fixture，只讀health，無provider/TTS請求或效果重播。

[D52報告](evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

FIX-015 **DONE / VERIFIED**，解除ZIP取消後staging遺留的局部BLOCKED_BY_FIX；D50/FIX-014 scopedVERIFIED保持。

只改SQLiteStore既有backup方法與CLI `_backup` wrapper，新增兩份專項tests；operations、D49 restore body/SQL、D50 owner/Gateway/原tests、Core/權限/providers/voice/UI/launcher/deps不變。retained executor Future＋copy_context＋backup-local cancel Event讓writer lock持有至真正IO／明確connection close／cleanup完成；ZIP沿原context順序清理。CLI單次backup在main thread把SIGINT轉成owned task.cancel並喚醒同loop，反覆中斷等待收尾，finally恢復原handler；primarytypederror優先，plainCancelledError不改，signal cancellation才轉KeyboardInterrupt/130。

新25 cases、相鄰240 PASS（17.60s）；完整 **1,578 PASS／5 real_provider 未選／3既有 warnings／198.40s**。Ruff311／mypy245／schema／diff PASS。 真8程序SIGINT（含三次中斷／64-of-124-page複製中／真正發布後）全部130、stderr零、handler恢復、IOjoined、staging無遺留、3keys持到join、next-owner成果保留。

初版CLI controlled24PASS漏selector喚醒，真8 timing FAIL與原D50 backup init2 FAIL先留RED；只補stdlib既有threadsafewakeup，不改舊tests或門檻。269/271既有baseline bytes保持，exact4 source-only temporary reverse/reapply PASS；保留所有資料與Git歷史，source rollback不授權再用舊危險取消路徑。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：first-adoption舊／非受管writer停止、真正signed launcher/version/readiness與人工批准handoff仍待各自驗收。FIX-002有用搜尋、FIX-005語音速度／人耳、FIX-006理解產品gate保持；RT-011/013/015原scopedDONE及編號不改。

Architecture YELLOW；backup/owner/Gateway YELLOW、合成tests/evidence GREEN；running DB/migration/權限/發布 RED。KEEP RI-005並SPLIT剩餘adoption/handoff，KEEP RI-006只到唯讀提案；REJECT第二backup/owner/executor manager，不因抽象美觀重做DONE。

GitHub Desktop OS-vault認證已接到repository-local Git helper；LFS用既有Desktop binary，hooks保留。public checkpoint `7892ecc`已推送／remote核對；原unpublished歷史留在local-backup/pre-public-push-2026-10-13，私有models/audio/cache未上傳。D51發布若執行，另核對其commit，不把7892稱為包含本修復。

沒有操作live8026、私人DB/chat/WAV/key/config/models/GPU或正式部署。所有DB/OS probes是自有合成資料；pause/fault injection明示，不能冒充真人產品或power-loss驗收。

[完整本輪驗收與回退](evidence/FIX-015-2026-10-13/REPORT.md)。

## 2026-10-12 — RI-005 D50 owner / FIX-014 限定切片 VERIFIED

受管Gateway與CLI demo/backup/restore/有DBrelease在實際操作前取得同一canonical data owner，持有到startup/server drain/owned SQLite IO完成；備份來源、explicit目的地、ZIP固定.tmp共同有序去重（最多3keys）、一份IOjoin fence。真正foreignowner/alias與連續SIGINT反例先RED→局部修復；禁止output/tmp覆寫sourceDB/inputsettings/archive或tmp指向final，不改Core/SQLite/operations/release/權限/voice/UI/launcher/deps。沒有第二套registry/restore/lockmanager或globalstate。FIX-014 **DONE/VERIFIED**。

70新cases；最終相鄰**215PASS/10.58s**，完整**1,553PASS/5 real_provider未選/3既有warnings/157.81s**；Ruff309/mypy243/schema/diff PASS。真offline Gateway HTTP、kernel contention/fork/exec/aliases、raw/demo/ZIP三次SIGINT、3FD join/partialcleanup；fault/timing控制明示。baseline268中266不改、exact5source-only temporary reverse/reapply PASS、D47/D48/D49保留。獨立contract16PASS並重綁final5，lifecycle reviewer最後turn碰accountlimit，不假稱三份final批准；final OS probe另列。敏感掃描與cutoff見報告。

另真ZIP backup-stage probe確認未改的backup_to取消早退→TemporaryDirectory先清理→late IO重建staging，command join後仍留snapshot/sidecars：**FIX-015 REQUIRED_FIX/MEDIUM PLANNED / FAILED_VERIFICATION**，不是D50 lease失效。原dir0700、重建0775，實測DB/sidecars0600，沒有其他UID可讀內容證據。只要求既有backup局部canceljoin/明確close，不在本卡擴全SQLite。RI-005整體**PARTIAL / BLOCKED_BY_FIX: FIX-015 / BLOCKED_BY_RELEASE_INTEGRATION**；ZIP完整cleanup、firstadoption舊owner停止、signedlauncher真正版本/readiness/批准handoff仍未驗，禁止用source切片PASS放行發布。

Architecture **YELLOW**；owner/Gateway **YELLOW**、合成tests/evidence **GREEN**；runningDB/migration/權限/發布 **RED**。KEEP RI-005並SPLIT remaininglauncher/handoff，KEEP RI-006只到唯讀提案；REJECT重複owner/restore abstraction，未證任何 numberedtask冗餘，不硬CANCEL。RT-011/013/015原scopedDONE/編號不變，FIX-002/005/006產品gate保持。接續三窄卡（非ranking）：FIX-015局部backup cleanup、RI-005人工批准version/readiness/handoff、RI-006來源失敗→唯讀提案。沒有live8026重啟、私人DB/chat/WAV/key/config/model/GPU或發布。

[實際驗收、限制與精確回退](evidence/RI-005-owner-2026-10-12/REPORT.md)。

## 2026-10-12 — D49 / FIX-013 explicit restore 局部修復 VERIFIED

真正 temporary SQLite 證明舊路徑先覆蓋 live 再拒 migration/checksum，且 cancellation 提前釋放 writer lock。只改既有 SQLiteStore：mode=ro/query_only source→owned candidate→known prefix/checksum/既有遷移/integrity→SQLite backup promotion；不replace live/WAL。原 per-store writer lock 持有到 offloop thread/explicit connection close/cleanup joined；取消中止未完成 copy，DONE後取消誠實保留已commit資料。原typed error保留、cleanup refusal可見，不假稱已移除。獨立review先RED修掉Python3.14 shield重複error，只改owned await asyncio.wait/job.result，沒有新restore/schema/updater抽象。

41新cases；exact original source **30FAIL/11PASS**（5.61s）；最終專項 **145PASS**（4.95s），完整 **1,483PASS/5 real_provider未選/3既有warnings**（156.51s）；Ruff306/mypy240/schema/diff PASS。真raw/ZIP CLI、舊schema/WAL/來源唯讀、取消/queued writer/ledger retention驗收；IO/清理/進度timing標controlled。三份獨立review重綁final source後無scoped blocker。266 baseline中265不改、新2tests，exact3 source-only reverse/reapply PASS，D47/D48保留；final source3/docs12掃描0；evidence55inputs/277逐項capturedSHA256誤報/unresolved0，cutoff 2026-10-11 17:58:09 UTC（audit outputs與此後結果annotation排除）。

FIX-013 **DONE/VERIFIED**，只解除此explicit-restore failure gate；RI-005整體 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：activepointer不等於真正版本，stopped writer／實際launcher/version/readiness／人工批准還未驗。成功明確data restore可替換近期資料，code rollback仍只切版本；commit後取消/cleanup failure需readback再決定，不重送。沒有live8026 restart、privateDB/chat/WAV/key/model/GPU或發布；FIX-002/005/006產品gate與RT-011/013/015 scopedDONE不變。

Architecture YELLOW；restore元件YELLOW、合成測試/evidence GREEN；運行DB/migrations／權限／發布RED。ZIP DB/config跨檔atomic、multiprocess lease、powerloss不算本卡驗收；candidate disk-capacity／舊backup retention為TECH_DEBT/DEFER，不建新manager。KEEP RI-005、SPLIT stopped-owner與actuallauncher；接續三窄切片RI-005 owner、RI-005 approved launcher/version/readiness、RI-006唯讀提案（非ranking、不重編）。Hermes REJECT重複restore/evolution abstraction，DEFER任意自改/發布直到接入有證據；本卡無new scoped blocker。

[驗收、限制、精確回退](evidence/FIX-013-2026-10-12/REPORT.md)。

## 2026-10-11 — RI-005 D48 / FIX-012 code-only回退限定切片 VERIFIED

原T32把版本回退與wholeDB restore綁一起，舊測試要求新寫入消失，是ORIGINAL_DESIGN_ERROR／REQUIRED_FIX HIGH，不是新Sol regression。[最小架構更正](runtime-evolution/ARCHITECTURE_CORRECTION.md)。只改既有ReleaseManager：新staged版本保存完整D39signedmanifest sidecar並拒順序同版覆寫，health後再驗來源；rollback驗精確target/signature/alias＋實際readonly schema prefix，unknown/incompatible拒絕，只切active pointer、從不讀舊backup還原或migrate/replay。既有獨立siro restore保持分開，移除只被舊rollback使用的private restore helper。API/CLI/簽章格式保持，危險資料回退語意明確撤銷；沒有自動信任升級/新updater/schemaengine/lockservice。

新51cases＋原release/signing/launcher/operations94PASS（3.75s）；完整1,442PASS、5 real_provider未選、3既有warnings（157.59s）。真temporary SQLite/WAL晚寫/原writer仍可用、conversation/memory/完成ledger保留、real migratedDB CLI、schema/receipt/source/path負向；pointer/receipt錯誤為controlled injection，沒有實際啟動另一version或真人產品驗收。全repo Ruff304／mypy238／schema/diff PASS；baseline265中263未改、exact3 source-only reverse/reapply PASS，D47十一檔保持；3source/13publicdocs敏感掃描0；evidence 273逐項SHA256誤報、unresolved0；cutoff 2026-10-11 15:53:57 UTC（audit outputs與後續status/count annotation另排除）。

另外真合成probe確認SQLiteStore explicit restore在migration/checksum failure前已覆蓋live：**FIX-013 REQUIRED_FIX/HIGH PLANNED，該failure path FAILED_VERIFICATION**，此卡未改SQLite/migrations。RI-005整體PARTIAL，full activation／data-restore acceptance標BLOCKED_BY_FIX: FIX-013與原BLOCKED_BY_RELEASE_INTEGRATION；active pointer≠真正執行版本，launcher仍需consume/readiness與stopped-writer gate。元件source rollback不授權重新呼叫舊危險DB回退。沒有live8026/privateDB/chat/WAV/key/model/GPU/發布。三個分派審查turn碰帳戶limit，最終獨立review NOT_RUN，root直接source/實測不冒充獨立批准。

Architecture overall YELLOW；ReleaseManager元件YELLOW、合成測試/docs GREEN；運行中的DB/migration/權限/發布仍RED。順序immutableversion/read-schema snapshot不等於concurrent owner lease、powerloss或實際loader相容。保留舊backup但不自動用其回退是TECH_DEBT retention，不擴全局抽象。KEEP剩餘RI-005並SPLIT stopped-writer/actuallauncher；下一三張接續範圍FIX-013局部prevalidation、RI-005剩餘接線、RI-006唯讀提案（非ranking）；RT-011/013/015 DONE保持，FIX-002/005/006產品限制不解除。

[完整驗收與回退](evidence/RI-005-2026-10-11/REPORT.md)。

## 2026-10-11 — RI-004 D47 固定技能產品接入（限定切片 VERIFIED）

既有D44準備/真驗證＋D46strict worker接進同一registry/catalog/orchestrator/dispatcher：server-held review900s/完整identity→人工安裝disabled→另一步明確enable→原對話tool批准→revoke；沒有模型自批、任意code/依賴、第二套registry/scheduler/schema。新facade/CAS不覆寫同版，queued/active jobs先fence再join，取消offloop交易補disabled，cleanupfailure仍嘗試durable revoke、保留typed error。Startup只恢復精確固定模板/receipt/row，tools-off持久停用，shutdown保留原owner明確批准供exact restart。

最後真畫面發現準備紀錄與已安裝狀態矛盾，補2個RED→局部history-label修復，不改匯出原始事實。最終189專項PASS（17.12s）／完整1,391PASS、5 real_provider未選、3既有warnings（154.61s）；Ruff302／mypy237／lint／schema PASS。真CUA/HTTP/SQLite/bwrap走通安裝disabled→明確enable→填入不送出→revoke/readback，fixture退出0、owned jobs0、暫存清除。最後exact11 source回退/reapply與獨立綁定PASS，baseline258中254不變，D46七檔/Core/policy保留。11source/10publicdocs敏感掃描0，evidence356逐項digest誤報/unresolved0（02:10:44UTC cutoff；後續僅狀態/計數annotation）。最後console一則無來源MutationObserver錯誤，origin UNKNOWN，已留證據，未宣稱零錯或猜測修復。實際產品驗證只temporary18034，不讀私人DB/chat/WAV/key、不碰模型/GPU、不重啟live8026或正式部署。

RI-004整體仍PARTIAL，但固定builtin checklist人工批准/strict執行/撤銷切片的局部caller接入gate已解除。RI-005 launcher/single-writer/latest-data-preserving rollback保持BLOCKED直到各自驗收；RI-006 KEEP，FIX-002有用搜尋/FIX-005速度人耳/FIX-006真理解保持既有產品限制。RT-011/013/015 DONE不重開、不重編、不ranking。Gateway/registry/catalog保持YELLOW（新owner生命週期），D46已驗限定profile可GREEN，Core/permission/release仍RED freeze；sameUID/任意生成/multiprocess/aggregateRAM不算通過。沒有original design correction或新全局state manager。

[完整變更與驗收](evidence/RI-004-activation-2026-10-11/REPORT.md)。

## 2026-10-11 — RI-004 strict worker 限定切片 VERIFIED（最新）

D46已走通真D44候選準備／驗證→完整四檔hash→actual strict WorkerSupervisor→中文清單結果。重用RI-003的最小mounts/不可逆restrictions到loweradapters，只有explicit stdlib single-process profile；defaulttrusted/D45/Dispatcher原body與Core/registry/Gateway/UI保留。原待審UI仍不install/enable，這一段是developer verification，沒有正式對話caller或部署。

獨立反例確認typedmetadata equality／零concurrencyadmission／delayedspawn absolute期限缺口，全部先RED→同檔最小修復：canonicalJSON用Python-mode保留型別、實際captured schemas/limits作authority、queue前staticguard、原ExecutionContext共用期限。新 **51PASS**、相鄰120PASS，完整 **1,202PASS／5real_provider未選／3既有warnings／132.67s**；全repo Ruff295／mypy230／schema/diff PASS。真OS私檔/env/network/fork/exec/session/limit/kernelobject/resource負向fixtures與probe/run repeatedcancel回收PASS；受控timing與actualOS分開。baseline254中251不變、3既有source／4新增，exact7temporary回退PASS；source secrets0、evidence316逐項hash誤報／unresolved0。[完整驗收](evidence/RI-004-worker-2026-10-11/REPORT.md)。

RI-004整體PARTIAL，workerprofile局部gate已驗，下一窄切片接server-held review／明確package-bound owner批准／disabled install／explicit enable/revoke／原catalog→orchestrator→dispatcher；排隊撤銷、sameversion衝突／exactCAS與IOcanceljoin不能略過。不新增registry／scheduler／schemaengine。沒有privateDB/chat/WAV/key／GPU/model／8026重啟／registryactivation或正式部署；一般deps/multiprocess/其他OS/aggregateRAM／releasegates與FIX-002/005/006保持。RT-011/013/015原DONE不重做。

## 2026-10-11 — FIX-011 有界 worker 生命週期 VERIFIED（最新）

RI-004 接實際執行前的合成 audit 抓到既有 worker 洪水阻塞、100k合法 JSON 誤拒、spawn/stdin 取消遺留程序。D45 先契約與RED，再局部重用唯一bounded process owner到adapter；services facade保留所有舊caller/type/privatehooks。request offloop/read-only/64KiB，PIDnamespace與單一session owner，worker strict UTF-8，repeated/latecancel join並保留primary cleanupfailure。原完整package/hash/registry/permissions/concurrency與其他產品source保留；trustedprofile不變成generated-code安全證明。

24新cases PASS，完整 **1,151 PASS／5 real_provider未選／3既有warnings／132.76s**；全repo Ruff291／mypy226／schema／diff PASS。獨立review新增反例均局部修復；baseline252中249不變、3既有source修改／2檔新增，exact5 temporary reverse/reapply PASS；source secrets0，owned evidence278逐項SHA identity誤報／unresolved0。沒有live8026／私人DB/WAV/key／模型/GPU／registry effects／正式部署。

[FIX-011完整證據](evidence/FIX-011-2026-10-11/REPORT.md)。FIX-011 DONE／VERIFIED解除RI-004此lifecycle局部block；下一張仍在RI-004驗fixed stdlib single-process worker真OS／權限／資源／取消，之後接server-held review／package-bound人工批准／disabled install／explicit enable/revoke／既有catalog。D44切片仍有效；RI-004整體PARTIAL，FIX-002/005/006及RI-005 release/data gates保持，RT-011/013/015原DONE不重開。

## 2026-10-10 — RI-004 待審候選產品切片 VERIFIED（最新）

RI-004 整體 **PARTIAL**；D44 的明確 owner「existing typed catalog → 固定 Markdown checklist candidate → complete package capture → 真 RI-003 sandbox → review/export」切片已 VERIFIED。產品入口是 candidate profile 的「電腦協助 → 學習新能力」；目前準備待審技能，還不能直接在對話執行。固定 template 無 host import／任意生成；全部 inventory 的隱藏／停用／unknown 同樣匹配，已有 typed 能力不重造。單一 active task、offloop IO、取消join、tools-off／shutdown與late-response fences保留。任何PASS都installed=false／enabled=false／unreviewed，沒有registry寫入或approve/enable路徑。

88新cases（service23／Gateway32／UI33），完整 **1,127 PASS／5 real_provider未選／3既有warnings／130.97s**；真temporary Gateway→Chrome154→bwrap固定候選→手動匯出23checks PASS（取消 timing gate synthetic），JS errors0。独立review兩個局部銜接缺口先證據後修復、follow-up無剩餘confirmed blocker。全repo Ruff289format／lint、mypy224／schema／diff、exact6source secrets0；248既有hashes中246不變，只有Gateway/index兩檔預期變動、四檔新增，temporary六檔reverse/reapply完整SHA PASS。

沒有8026重啟、私人chat/DB/WAV/key、模型/GPU／registry install／正式部署。本輪切片僅固定builtin template，exact typed gap不是語意能力搜尋；installed registry未查、不持久化候選。實際enabled worker／依賴與安全審查／明確批准／版本撤銷仍BLOCKED_BY_SKILL_INTEGRATION；下一窄步驟在RI-004先驗fixed read-only skill的worker runtime boundary及取消，再接package-bound approval與既有catalog。RI-005 launcher／single-writer／最新資料保留回退不變；FIX-002／005／006仍PARTIAL；原RT-011／013／015 DONE不重開。[完整證據](evidence/RI-004-2026-10-10/REPORT.md)。

## 2026-10-10 — RI-003 單程序隔離驗證入口已 VERIFIED（最新）

RI-003 整體 **PARTIAL**；Linux x86_64／system CPython 3.14 的 `python-unittest-single` 切片 **VERIFIED**（D43）。新增明確 owner `siro verify-patch`／async 入口，source-only no-follow 投影、固定 trusted unittest runner、真 namespace/env/network/filter、single-process AS/CPU/file-data/output/process deadline 與取消清理。Core 只抽 pure preflight，原 trusted API／報告五欄／protected paths 相容；沒有模型自啟用／發布接線。

48 新 cases 對精確修前 source **48 FAIL／2.09s** → 新舊 patch/path／CLI **111 PASS／11.50s**；最終完整離線 **1,039 PASS／5 real_provider 未選／3 既有 warnings／127.78s**。實測惡意 import、alias／source 上限、network/fork/exec/session、memory/CPU/file/output、單／雙 SIGINT 完整 owned PID tree 消失、late cancel／typed cleanup failure。獨立 read-only review 抓到 IPC allocation／late SIGINT status 兩缺口，先 RED 後局部修復並 follow-up 確認。Format230／mypy220／lint/schema/diff／六檔零 secrets；231 既有 hashes 僅兩檔預期變更、四檔新增，exact 六檔 temporary reverse/reapply PASS。

限制：只認證 stdlib synchronous unittest 單程序，AS/scratch 不等於 aggregate kernel RAM；一般 pytest／依賴／threads／多程序／其他 OS 尚未認證，unsupported 不降級到 host。Candidate tests 可偽造，passed 不給批准權；路徑 allowlist 不偵測 source 中的秘密，blocked host IO SLO 未驗。原服務 8026 未重啟，沒有 private DB/chat/WAV/key 或部署。

下一張独立小卡 **RI-004**：沿既有 catalog／procedural／registry，先一個符合已驗 profile 的本機唯讀 **disabled candidate → verification evidence → review** 入口；已有能力不得重造，任何 enable 必須另驗實際 worker boundary 與 explicit owner approval。RI-005 launcher／single-writer／最新資料保留回退 gate 不變。FIX-002／005／006 仍各自 PARTIAL；RT-011／013／015 原 DONE 不重開。[驗收、限制與回退](evidence/RI-003-2026-10-10/REPORT.md)。

以下各日期段落保存當時交付結果，以本節與各卡報告的有效範圍為最新接續依據。

## 2026-10-10 — FIX-010 未知效果自動重送邊界已 VERIFIED

實際controller合成反例證實換call UUID能逃old replay fence；現在auto pending→approved原交易查同session/cap的unknown dispatch，same hash或binding不明需manual。只有orchestrator/integrated/UI三production＋44backend/1frontend新cases，原manual/grants/ledger/DB/模型/語音不變。45修前FAIL→122專項相鄰PASS，全套991PASS／5real_provider未選／3warnings（118.71s）；真Chrome21/21驗警告、零auto效果、WS reconnect不重送、explicit一次與duplicate404、exact ledger不變/cleanup。獨立review＋RED修正payload/Unicode/numeric/duplicate邊界；format226/mypy216/lint/schema/零scoped secrets，229oldsource只3變、exact5file source回退PASS。

FIX-010局部gate解除，不代表FIX-006語意DONE、FIX-002搜尋或FIX-005速度／人耳完成。頁reload卡恢復/active snapshot差異與unknown resolution/retention仍有局限；不增加新state manager。沒有8026restart/私人DB/WAV/key/部署。下一張RI-003先確認可支援的真Linux single-process profile、source-only projection／可信checks／取消，有實證才接入口；完整multiprocess需aggregate资源界線另驗。[證據與回退](evidence/FIX-010-2026-10-10/REPORT.md)。


## 2026-10-10 — FIX-006 局部故障事實已驗；理解仍PARTIAL（最新）

修復下一轮無自身失敗事實的缺口，並撤除每則文字都能念完/Live2D必連線的錯誤保證。只既有runs/integrated兩檔＋40專項；fixed五欄同session/privacy/15min摘要、原restore gate與failed-intent fence不變，無raw payload/效果/DB改動。獨立review抓到invalid-time排序及SQLite NUL length並局部修復。40修前FAIL→55新舊PASS，全套946PASS／5real_provider未選／3warnings（114.33s），format224／mypy214／lint/schema PASS；228現有檔僅2production變，exact3file reverse/reapply SHA PASS。

同配置真模型的合成對照支持「知道自己的HTTPStatusError/原因UNKNOWN」，**不支持整體理解DONE**：語音需求更正仍ProviderOutputTruncated、unknown-effect重做語意FAIL、memory cloud區別/style/CAPTCHA仍未全驗。FIX-006保持PARTIAL與產品gate，不換backend/加tokens/廣泛prompt/執行模型新指令；下一步僅量completion usage與reasoning allocation的窄幅假設。FIX-002有用搜尋、FIX-005語音速度/人耳驗收與RI-003–005接入gates原樣保留；沒有8026restart／私人DB/WAV／發布。 [完整證據](evidence/FIX-006-2026-10-10/REPORT.md)。

FIX-006補充量測已完成：[8次synthetic allocation](evidence/FIX-006-2026-10-10/COMPLETION_ALLOCATION.md) 支持reasoning與visible verbosity混合；low仍有length與錯誤語意，REJECT本輪改production effort，不提高budget/換backend。新429有量到但不回推原事件，零自動重試。

## 2026-10-10 — FIX-007 技能 package identity 已 VERIFIED（最新）

只在既有skills/registry/dispatcher三檔修復：完整versioned digest、批准root/hash、legacy fail closed、owned byte snapshot、取消/清理不復活、最多8副本與worker concurrency綁內容。原source43新cases42FAIL／1PASS；最終新舊/adjacent66PASS、全套906PASS／5real_provider未選／3既有warnings（113.93s），format223／mypy213／lint／schemas PASS。227既有來源中只3production變動、原skill tests未改、精確4檔temp reverse/reapply SHA PASS。

FIX-007／008／009局部gates已解除；**generated skill接入仍需sandbox/review/明確enable，untrusted checks真OS隔離與可信check allowlist、發布launcher／批准／最新資料保留回退仍未驗**。沒有runtime skill catalog/自改/自動發布，也沒讀私人資料或重啟8026。保留既有RT/voice/session；下一張FIX-006，優先驗文字對話是否能正確描述能力與當次故障，避免無來源全知/繞驗證建議。[交付与回退](evidence/FIX-007-2026-10-10/REPORT.md)。
## 2026-10-10 — FIX-009 完整簽署已 VERIFIED（最新）

已修復 release schema bounds 未簽署漏洞：明確版本化 canonical 全 manifest HMAC、strict bounds、legacy無fallback與入口重驗。只1個production檔、舊fixture＋34新tests；修前真activated反例→新舊36PASS，全套863PASS／5 real_provider未選／3既有warnings（111.19s），format222／mypy212／lint／schema PASS。226份existing hash中只本卡production／fixture變動，精確3檔temp reverse/reapply SHA PASS。

FIX-008／009局部gate解除；**FIX-007技能身份、untrusted checks真OS隔離與可信check allowlist、launcher／人工批准／最新資料保留回退仍阻擋相關自主執行／發布**。沒有live service/key/私人資料/deployment；原whole-DB rollback語意未變，不能當保留最新記憶。既有搜尋／語音速度／理解產品gate仍保留。下一張繼續FIX-007，修既有registry/dispatcher的完整package identity，不新增另一套技能系統。[驗收與回退](evidence/FIX-009-2026-10-10/REPORT.md)。
## 2026-10-10 — FIX-008 path保護已VERIFIED（最新）

完成protected delete／rename來源與目的完整辨識、canonical path與whole-input preflight。只改core/evolution.py，支援的text dialect明示D38；歧義格式拒絕、hunk內標頭文字按counts正常處理。精確舊source46FAIL／16PASS→新舊63PASS；獨立17反例未找到證實bypass；全套829PASS／5 real_provider未選／3既有warnings（112.86s），mypy211／lint／schemas PASS。225基準檔僅1production變動、兩檔精確temp reverse/reapply SHA PASS，前序RI-002／browser／voice/session保留。

FIX-008局部gate解除，**untrusted checks的OS隔離／可信checks、FIX-007技能身份、FIX-009發布簽署及launcher/資料回退仍各自阻擋promotion**。沒有正式服務、private資料或live候選apply。FIX-002搜尋PARTIAL／FIX-005速度／FIX-006理解仍保留；下一張繼續FIX-009，不重編或重做RT。[交付與驗收](evidence/FIX-008-2026-10-10/REPORT.md)。


## 2026-10-10 — FIX-002局部修復驗收；搜尋仍PARTIAL（最新）

完成safe browser reason、同一failed observation投影、可讀主頁partial、主frame／redirect拒絕與關閉期callback收束；只6個production檔，沒有scope／hash／授權／DB／依賴變動。新51專項納入離線全套767PASS／5 real_provider未選／3既有warnings（111.45s）；真Chrome10 scope fixtures、18 UI renderer情境、2 slow-route close/cancel均PASS。精確10檔temp reverse/reapply SHA回退與221既有source保存PASS，原RI-002／voice/session工作保留。

真configured provider→批准browser→native續談已驗，但Bing僅頁首、DDG human challenge，沒有有用search結果；自動研究保持BLOCKED_BY_FIX：FIX-002。原私人事件root cause及兩次public4s cleanup的具體阻塞步驟仍UNKNOWN；最後一次close0.069s、零殘留不能抵銷原失敗。模型不當繞驗證建議保留為FIX-006負向case，未實際bypass。沒有重啟8026／讀私人DB、WAV或輸出credentials；source需之後啟動載入，不稱deployment。

[FIX-002交付、真結果與回退](evidence/FIX-002-2026-10-10/REPORT.md)。使用者要求一直做；下一張獨立已確認局部漏洞為FIX-008 protected delete/rename辨識，仍先測試、局部修復與回退，不讓不可信checks或自主發布越過各自gate。


## 2026-10-10 — RI-002 能力說明已實作與驗收（最新）

完成既有ToolCatalog純metadata／單次capture：保留name/schema/executor來源，optional欄位缺失明示null；安全availability/reason只描述當次可用性，exception不外送，unknown不向模型提供工具也不能dispatch。沒有新增registry／executor／endpoint／worker／DB migration／依賴，沒有更改批准或full-mode語意。

candidate首輪與工具續輪用同次capture提供ToolDefinition與capability context；在既有checkpoint更新首system message末端唯一SIRO-owned block，無message累積、不動user/assistant/tool pairing或memory。legacy原schema/prompt保持。authenticated /v1/runtime沿原tools欄位加metadata，UI「電腦協助→我現在能做什麼」顯示能力與停用原因，刷新只讀取狀態，metadata以textContent呈現。

驗收：15新專項PASS（1.03s）、既有相鄰26PASS、完整離線716PASS／5 real_provider未選／3既有warnings（98.91s）；Ruff271格式檔／lint、mypy206、export_schemas --check PASS。真Chrome154／HTTP13checks PASS，停用／恢復／未授權401／HTML injection／零executor與零pageerror；readiness/provider為合成，不包裝成人工模型語意、聲音或Live2D驗收。初次產品fixture漏LanguageModel.name導致1FAIL，僅補fixture並保留失敗log；未改production門檻。

只改4個production檔與新增2個tests；本輪前256份source/test/script/locks除明列4檔外全部SHA不變，保留既有voice/session dirty work。精確6檔temp反向／重套SHA回退PASS；既有8026 health/root/live2d HTTP200，未重啟、未讀私人DB／WAV／key。新後端需下次啟動載入；不稱正式deployment。

[RI-002交付／驗收／回退](evidence/RI-002-2026-10-09/REPORT.md)。MCP本輪被既有owner lease占用，未關owner／繞鎖／重索引；重用同source hash的RI-001 graph，source/AST補callers並誠實記NOT_RUN。下一張可開始FIX-002搜尋診斷與公開查詢驗收；FIX-005語音速度／人工語意與FIX-006理解仍未完成；生成技能／自改／發布仍受FIX-007–009及真隔離／批准／資料回退gate。


## 2026-10-09 — Runtime Intelligence現況盤點與開發期MCP（最新）

使用者本輪要求Preserve First／Understand Second／Extend Third／Verify Always，已完成RI-001的低風險開發切片。原main／c1d2d41與FIX-003／004／005 dirty source、私人資料和聲線都保留；未改production source／API／schema／runtime dependencies，原251個source/tests/locks雜湊零變。本機8026 health、首頁、Live2D mount仍HTTP200；沒有重啟服務或對私人對話送測試訊息。

官方Codebase Memory v0.11.0固定archive checksum核對後手動安裝；本機受限stdio MCP已initialize/tools-list/query成功，250 source files、3092 nodes、16700 edges。只讀analysis profile＋client allowlist、source-only投影、真無網路／只讀mount、乾淨env、watcher／auto-index／UI停用；無遺留程序。這不是SIRO長期記憶，也不是自主部署。current workspace設定已由Codex CLI讀到；nested Git root project trust未更改，本輪chat工具清單仍待重載，不聲稱已hot reload。升級/手動index/排除/資源樣本/回滾見CODEBASE_MEMORY_INTEGRATION_REPORT。

唯一ROADMAP_RECONCILIATION已逐項核對T01–T40：8個限定元件Implemented and Verified、4個Implemented but Unverified、25個Partially Implemented、3個Planned Only；未把歷史DONE等同正式產品。CURRENT_ARCHITECTURE_AUDIT、CAPABILITY_MATRIX與Runtime Intelligence設計已對齊native messages/catalog/session memory/summary/Rust/organizer實際caller；不重做已解決RT。新增RI-001–006小卡及P0–P3分類，原T／RT編號與歷史不變。

合成反例證明skill code未綁完整package identity、protected deletion漏判、same-user copy不是sandbox、release schema bounds未簽署。FIX-007／008／009已定義REQUIRED_FIX／HIGH／PLANNED，尚未修production；只阻擋各自generatedskill／patchcheck／release promotion。OS驗證、launcher consume與保留最新資料回退另設接入gate；沒有證據推翻整體Runtime Evolution設計，不新增ARCHITECTURE_CORRECTION或平行registry／scheduler／memory DB。

本輪基線671PASS；最後全套701PASS／5 real_provider未選／3既有warnings／147.01s，新增30個開發tool測試；Ruff269 files、mypy204、schemas、Rust6 tests PASS。真bubblewrap12項隔離與開發MCP停用／恢復回滾PASS。另140／40項離線子集與四類安全反例不是額外相加的產品完成數。證據 [runtime-intelligence REPORT](evidence/runtime-intelligence-2026-10-09/REPORT.md)；安全反例 [RI architecture REPORT](evidence/RI-architecture-2026-10-09/REPORT.md)。未跑真provider／新GPU／人耳／真人Live2D／真HA或ESP32／24h／遠端CI／attestation；沒有以HTTP200取代實際互動驗收。

下一個可開始窄切片為RI-002既有catalog純metadata與唯讀inventory；既有FIX-002搜尋、FIX-005語音速度／人工語意、FIX-006自身故障理解仍未完成，應按產品問題各自驗收。任何生成技能／不可信checks／發布接入先滿足FIX-007–009與隔離／批准／資料回退gate。此處列接續關係，不表示另建或重排原RT。

---

以下為原先各時點的歷史進度；與上方矛盾時以最新現況與實碼證據為準。

更新：2026-09-26

## 當前狀態

**T00–T34、T36–T38 與 R02–R03 已完成各列所標示的驗證層級。** T36–T38 已補持久節點設定、資源 heartbeat、可執行 loopback worker、lease/cancel/stream/result fence，以及 A23 假雙節點路由；同機 simulator 不取代 T39 真雙節點。原 repo 初始 commit `c060f1b`，所有新工作仍未提交。

已完成：分享對話解析與需求追蹤、架構與介面規格、使用體驗、威脅/隱私與資料生命週期、41 張實作任務卡、3 張研究卡、24 個驗收情境、Sol 啟動/續作/除錯手冊、初始 ADR，以及逐項規劃完成度稽核。

尚未完成：T35–T40、R01、R03 完整產出、完整產品驗收與其他平台／ESP32 與真實 Home Assistant instance 測試。AIRI 已完成鎖定 source/license/API 稽核。

## 下一個具體動作

本機可完成的已知缺口已清除；下一步需外部條件到位後執行 T35（24 小時／真人／真設備）或 T39（第二台真實節點），最後才是 T40。

## 外部條件清單

| 項目 | 目前狀態 | 最遲影響任務 |
|---|---|---|
| 最終部署 OS/CPU/RAM/GPU | 第一開發基線已盤點；最終部署仍未確認，NVIDIA driver 不可用 | T33 |
| 模型 backend 認證與費用上限 | Groq 免費 API 與本機 Ollama 已完成 L2；正式費用上限未設定 | 發布前 |
| Live2D/聲音資產與授權 | Cubism Web SDK 5-r.5/Haru 與 Orpheus 條款已接受並通過本機驗收；發布前另確認 Publication License | 發布前 |
| 麥克風/喇叭測試環境 | speaker AEC 與 20 次真人打斷通過；實體 headset 未測 | T16 完成，headset 未宣稱已驗 |
| ESP32/HA instance 與設備 | ESP32 及真實 HA instance 未確認；T28 mock integration 已通過 | T27–T29 |
| 第二台算力節點 | 未確認 | T39 |
| Windows 支援範圍和實測主機 | 未確認 | T24/T25 |

## 任務狀態

T00–T34 已完成相應 L1/L2、限定平台 L3 或 simulator/mock gate；其餘狀態如下。不能從文件數推算產品完成百分比。

| 範圍 | 狀態 | 證據 |
|---|---|---|
| 規劃文件包 | COMPLETE | 本 repo 的 13 份 Markdown 文件與 `docs/evidence/planning-check.json`；逐項證據見 PLANNING_AUDIT |
| T00 | DONE | `docs/ENVIRONMENT.md`、`DEPENDENCIES.md`、`DEPLOYMENT_POLICY.md`、`evidence/T00/README.md` |
| T01 | DONE | `pyproject.toml`、`uv.lock`、`src/siro`、`scripts/check`、CI、`evidence/T01/README.md` |
| T02 | DONE | `src/siro/contracts`、`schemas/events`、`tests/contract`、`evidence/T02/README.md` |
| T03 | DONE | `src/siro/ports/events.py`、`src/siro/events/local.py`、24 tests、`evidence/T03/README.md` |
| T04 | DONE | `src/siro/persistence`、migrations、SQLite integration tests、`evidence/T04/README.md` |
| T05 | DONE | identity/world、35-test gate、`evidence/T05/README.md` |
| T06 | DONE | conversation/mock/CLI、A01/A02 L1、100-race、`evidence/T06/README.md` |
| T07 | DONE | 兩 adapter/L1、Groq L2、Ollama L2、A03 backend swap，見 `evidence/T07/README.md` |
| T08 | DONE (L1) | persistent memory/persona/demo、A03 L1；D67一般回覆長度修正見 `evidence/T08-REPLY-LENGTH-2026-10-17/REPORT.md` |
| T09 | DONE | JetStream/outbox/redelivery/quarantine/replay、A04 L2、`evidence/T09/README.md` |
| T10 | DONE | loopback gateway/control UI/single writer、A05/A06 L2、`evidence/T10/README.md` |
| T11 | DONE (research + L1) | AIRI commit/license/API 阻礙、body contract、最小 Web adapter，見 `ADR-embodiment.md` 與 `evidence/T11/README.md` |
| T12 | DONE (L1 + local L2) | Cubism Web 5-r.5/Haru、真 WebGL renderer、56-file manifest、body WS、kill/restart A07，見 `evidence/T12/README.md` |
| T13 | DONE (L1 + local L2) | binary header、Python/Node golden、mic/output WS、single owner、ring buffer，見 `evidence/T13/README.md` |
| T14 | DONE (L1 + Groq L2) | VAD、partial/final、endpoint、Groq Whisper 真實 fixture，見 `evidence/T14/README.md` |
| T15 | DONE (L1 + Groq L2) | 分句、stream transport、ACK/口型/文字降級與 Orpheus→Whisper 真實閉環，見 `evidence/T15/README.md` |
| T16 | DONE (L1 + speaker L3) | barge-in、generation fence、100 races、故障矩陣、speaker AEC 與 20 次真人打斷完成；headset 明列未驗，見 `evidence/T16/README.md` |
| T17 | DONE (L1 + SQLite integration) | 五類 memory、FTS、版本/來源/scope、A10/A11、管理 API，見 `evidence/T17/README.md` |
| T18 | DONE (L1 + SQLite integration) | bounded/resumable scheduler、A12、trait clamps、relationship revisions，見 `evidence/T18/README.md` |
| T19 | DONE (L1 + SQLite integration) | Attention/Drives/Workspace、hard gates、Goal lifecycle/budgets、noise replay，見 `evidence/T19/README.md` |
## 2026-09-27／產品整合狀態

T00–T40 的完成標記只代表各任務所列的元件或測試層級，不代表使用者產品已完成。產品閉環改以
`docs/INTEGRATION_PLAN.md` 的 I01–I05 驗收。

| 整合項目 | 狀態 | 已驗證／仍缺 |
|---|---|---|
| I01 文字 Companion | DONE (L2) | 真瀏覽器經 Gateway → persistent Core → Groq 串流回答；provider 與 route 可見 |
| I02 角色與情緒 | IN-PROGRESS | `siro-affect-cpm-1` 版本化參數、混合 appraisal、時間衰減、PAD mood、homeostatic drives、coping、關係 revision、goal/action/memory contracts、room/systemd/browser/process/file readback、單一 affect decision loop、Live2D 表情抑制、瀏覽器 prosody 與 30 天模擬已接；只剩真人長期驗證尚未完成 |
| I03 語音 | DONE (L2 + owner acceptance) | mic → Groq Whisper → 對話 → TTS/Live2D 同頁閉環已通；預設改為 Qwen3-TTS 0.6B Base 使用 `qwen3-siro-anime-daughter-v1.wav` 做 zero-shot voice clone，獨立常駐 worker 與文字快取已接入。RTX 3050 已驗證 `torch 2.12.0+cu130`/CUDA；第一次 2.48 秒合成含載入約 26.8 秒，仍需優化串流首包延遲 |
| I04 電腦操作 | IN-PROGRESS | 模型 tool catalog → persistent proposal/grant → executor observation → 模型 continuation 已完成並以真 Groq 驗證；正式路徑停用關鍵字 routing，新增有界 `computer.execute` argv 執行。Migration 012 已持久化 AgentRun goal/state/step/observation，並接入現行工具回路。尚缺原生 multi-message tool protocol、持續 GUI/browser session、in-flight process cancel、authorization profiles 與 sudo broker |
| I05 設備與發布 | NOT-INTEGRATED | simulator/release 元件存在；產品 UI、真硬體與 soak 尚未完成 |

| T20 | DONE (L1) / L3 PENDING | 預設關閉、quiet/busy/speaking/cooldown/day limit、7-day replay，見 `evidence/T20/README.md` |
| T21 | DONE (L1 + L2) | Runtime clock、SQLite grant/revoke/audit/action、跨程序 A14、ASK workflow，見 `evidence/T21/README.md` |
| T22 | DONE (Linux L2) | Bubblewrap network/filesystem/env isolation、resource limits、Core heartbeat，見 `evidence/T22/README.md` |
| T23 | DONE (Linux L2) | Rust Runtime grant → filesystem/process driver、持久 action ledger、A16，見 `evidence/T23/README.md` |
| T24 | DONE (Linux Chrome L2 + visible L3) | scoped origin/redirect、stale-screen fence、form/key/pointer/screenshot readback、local pixel analyzer；Wayland desktop unsupported，見 `evidence/T24/README.md` |
| T25 | DONE (Linux L2 + A17 L3) | allowlisted user-systemd、exact-hash critical install、可視 Chrome＋PipeWire＋service failure isolation；Windows/macOS unsupported，見 `evidence/T25/README.md` |
| T26 | DONE (SQLite integration + simulators) | descriptor/schema、room edges、canonical actions、TTL/stale/unknown、light/presence/temperature/camera simulators，見 `evidence/T26/README.md` |
| T27 | DONE (authenticated broker + simulator) / HARDWARE PENDING | Argon2 auth、LWT、retained state、non-retained command、expiry/dedup/ack-readback、ESP32 source；T27-FIX-01 epoch／NTP／單次aiomqtt LOCAL_VERIFIED，見 [新證據](evidence/T27-mqtt-time-2026-10-16/REPORT.md)，原 `evidence/T27/README.md` 保留 |
| T28 | DONE (official protocol mock integration) / REAL HA PENDING | REST descriptor/snapshot/readback、WebSocket auth/state_changed、action ledger、token env-only、revoked/unavailable 降級，見 `evidence/T28/README.md` |
| T29 | DONE (L1 closed-loop simulator) / L3 PENDING | presence→world→salience→candidate→policy→light→readback、bounce/feedback/manual/offline 抑制，見 `evidence/T29/README.md`；需至少一個真 sensor 和 actuator |
| T30 | DONE (L1 + SQLite integration) | repeated trusted successful traces、secret redaction、fixture、source trace、review-only candidate persistence；不安裝或 enable，見 `evidence/T30/README.md` |
| T31 | DONE (L1 isolated workspace) | unified diff、獨立 temporary workspace、argv-only checks、pass/fail report、production digest 和 permission-policy protection，見 `evidence/T31/README.md` |
| T32 | DONE (L1 isolated release) | signed/hash manifest、SQLite backup/integrity、schema compatibility、staging healthcheck、atomic activate/last-known-good rollback，見 `evidence/T32/README.md` |
| T33 | DONE (L1 + local telemetry) | /proc telemetry、model slots、high/low hysteresis、background pause/resume、cloud budget hard gate、control/cancel pressure test，見 `evidence/T33/README.md` |
| T34 | DONE (L1 + Linux L2 A22) | locked clean install、user units、doctor、health/graceful stop、14-day logs、hashed DB+settings backup/restore，見 `evidence/T34/README.md` |
| T35 | BLOCKED-EXTERNAL | v1.0 24-hour soak、真人 UX、真 HA/ESP32、正式 provider profile，見 `evidence/T35/README.md` |
| T36 | DONE (L1 + loopback L2 simulator) | persistent pre-pair config、capability/resource heartbeat、TTL/revocation、假雙節點，見 `evidence/T36/README.md` |
| T37 | DONE (L1 + loopback L2 simulator) | worker executable、bounded stream/input、cancel/lease/epoch/result fence、artifact cleanup/fault，見 `evidence/T37/README.md` |
| T38 | DONE (L1 + loopback A23 L2 simulator) | location/privacy/model/budget hard filters、cost/latency、trace/calibration，見 `evidence/T38/README.md` |
| T39 | BLOCKED-EXTERNAL | 需要第二台真實節點，見 `evidence/T39/README.md` |
| T40 | BLOCKED-EXTERNAL | 依賴 T35/T39；發布稽核見 `evidence/T40/README.md` |
| R01 | RESEARCH-BLOCKED-EXTERNAL | 需要 T39 真雙節點與適合推論硬體 |
| R02 | RESEARCH-DONE (synthetic) | fixed-seed rules/attention/drives/dream ablation；不調整 scorer/traits，見 `evidence/R02.md` |
| R03 | RESEARCH-DONE (limited spike) | limited WoT TD translation、相容矩陣、工時比較與延期 ADR D11，見 `evidence/R03.md` |

## 2026-09-23／T00 交接

- 完成與變更：盤點 OS/CPU/RAM/GPU/audio/tooling/repo，定義 dependency 與保守 deployment policy。
- 驗收：真實 shell 查詢與官方 dependency 文件；證據見 `docs/evidence/T00/README.md`。
- 工作區：`main`，原有規劃與本次 T00 均未提交；無 secret。
- 真實／mock：環境盤點真實；模型、身體、設備、第二節點尚未驗證。
- 下一步：T01 建立 `pyproject.toml`、`uv.lock`、`src/siro/cli`、`scripts/check`、CI 與測試。

## 2026-09-23／T01 交接

- 完成與變更：Python package、settings schema v1、CLI doctor/config schema、locked dependencies、統一 checks、CI、redaction 和測試。
- 驗收：`scripts/check` 通過 format/lint/mypy/6 tests/secret scan；doctor exit 0；證據見 `docs/evidence/T01/README.md`。
- 工作區：`main`，所有規劃/T00/T01 變更仍未提交；`.venv` 已 gitignore，無 secret。
- 真實／mock：CLI 與環境診斷為真實本機；沒有模型或外部整合。
- 下一步：T02 建立 `src/siro/contracts`、`schemas/events` 和 contract/boundary tests。

## 2026-09-23／T02 交接

- 完成與變更：event envelope、9 個首批 typed events、有界 JSON validation、causal session guard、JSON Schema export/stale check、Core import boundary。
- 驗收：`scripts/check` 通過 format/lint/mypy/17 tests/schema/secret scan；證據見 `docs/evidence/T02/README.md`。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：純 deterministic contract tests；沒有 broker 或跨程序 transport。
- 下一步：T03 實作 `src/siro/ports/events` 與 bounded local bus，驗證慢 consumer、expiry、priority 和 shutdown cleanup。

## 2026-09-23／T03 交接

- 完成與變更：EventBus/Clock ports、有界 priority buffers、每訂閱者 worker、TTL/dedup、滿載結果、例外隔離及 shutdown cleanup。
- 驗收：`scripts/check` 通過 format/lint/mypy/24 tests/schema/secret scan；10,000-event、slow consumer、priority/fairness、expiry/duplicate、worker cleanup 均通過。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：asyncio 本機 bus 為真實程式，測試資料合成；沒有 broker/durability。
- 下一步：T04 建立 SQLite WAL schema/migrations、transaction、outbox/inbox 與一致 backup/restore。

## 2026-09-23／T04–T08 交接

- 完成與變更：SQLite WAL/migrations/outbox/inbox/backup、identity/world、conversation 狀態機與 durable messages、OpenAI-compatible/Ollama/failover adapters、source-backed memory、persona prompt 與 offline CLI demo。
- 驗收：`scripts/check` 通過 format/lint/mypy/47 tests/schema/secret scan，2 個真 provider tests 因外部條件明確 skip；A01 單 trace/有序 delta/唯一 terminal、A02 100 次 race、三次 DB 重啟記憶、adapter 切換 identity、unknown 無假來源均通過。證據見 `docs/evidence/T04` 至 `T08`。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：T05、SQLite 與 CLI 為真實本機程式；A01/A02 為 L1 deterministic。Groq `openai/gpt-oss-20b`、Ollama 0.34.3 + `qwen3:4b` 與 A03 backend swap 已通過 L2。
- 新決策與缺陷：雲端外送必須明示 `cloud_allowed`；failover 只准在尚未顯示文字前發生；Groq SSE 與 Ollama NDJSON 已改為真正 streaming，取消會關閉 response。
- 下一步：有 credential/model 時補 T07 L2；否則進 T09 broker/outbox replay。

## 2026-09-24／T09 交接

- 完成與變更：NATS JetStream adapter、SQLite outbox dispatcher、bounded retry/quarantine、durable inbox dedup、read-only replay runtime、broker config 與 CI broker install。
- 驗收：`scripts/check` 通過 50 tests（另 3 個明示 opt-in provider tests skip）；真實 JetStream crash-before-ack redelivery 保持單次副作用；broker outage 與 replay safety 通過。
- 工作區：`main`，所有變更仍未提交；Groq key 只在 ignored mode-600 `.env.local`，tracked prefix scan clean。
- 真實／mock：NATS server 2.15.0 與 nats-py 2.16.0 為真實 L2；故障時點由測試控制。
- 下一步：T10 gateway/session/Origin/single-writer/snapshot/reconnect 與小型控制 UI。

## 2026-09-24／T10 交接

- 完成與變更：FastAPI loopback gateway、短效 session/Origin/Bearer auth、single-writer per client、bounded urgent/normal queues、snapshot/reconnect、turn/cancel/kill-switch APIs 與小型控制 UI。
- 驗收：`scripts/check` 通過 55 tests（3 real-provider opt-in skips）；慢 client 隔離、50 producers、100 reconnect、真瀏覽器 walkthrough 及 disconnect cleanup regression 通過。
- 工作區：`main`，所有變更仍未提交；Groq key 保持於 ignored mode-600 `.env.local`。
- 真實／mock：Uvicorn/HTTP/WebSocket/browser 為本機真實 L2；Core turn handler 尚為注入 port，T10 不執行工具或音訊。
- 下一步：T11 核實 AIRI commit/license/API，完成 speech/emotion/cancel/offline adapter spike 或記錄可重現阻礙。

## 2026-09-24／T11 交接

- 完成與變更：鎖定並稽核 AIRI `595ea7260d95d25a654572cfdd52e96cb9441290`；確認 MIT；提交公開 body API 的可重現缺口；選定最小 Web renderer；建立 speech/emotion/cancel/status port 與 fail-closed adapter。
- 驗收：`tests/contract/test_body_adapter.py` 覆蓋三種控制與 offline；完整 gate 結果見 T11 evidence。
- 工作區：`main`，所有變更仍未提交；Groq key 保持於 ignored mode-600 `.env.local`。
- 真實／mock：AIRI source/license/API 稽核為真實；body adapter 為 L1 合成 transport；未使用或宣稱假 Live2D 資產。
- 新決策與缺陷：AIRI 的 body 原語是 Stage 內部 API，公開 extension protocol 無直接 speech/emotion/cancel；改採最小 Web renderer。
- 下一步：T12 先完成 renderer transport/故障隔離；真 Live2D 動作與畫面因缺合法資產保持 BLOCKED-EXTERNAL。

## 2026-09-24／T12 部分交接

- 完成與變更：新增獨立 `/ws/body`、單 owner/單 writer renderer transport、有界 queue、offline/reconnect isolation，以及可實際開啟的 `/body` renderer shell。
- 驗收：`scripts/check` 通過 61 tests（3 real-provider opt-in skips）；A07 L1 證明 body failure 後文字/記憶持續及重連；真 Uvicorn/browser 顯示 renderer online，HTTP session 與 body WebSocket 成功。
- 真實／mock：gateway/browser/WS 為本機真實 L2 transport；角色只是明示 placeholder，沒有宣稱 Live2D。
- 外部阻礙：Cubism Core 為專有授權，官方 sample models 另受 Free Material License；需要 owner 接受適用條款並由官方來源取得 SDK/模型。
- 下一步：取得合法 SDK Core 與模型後接上 motion/expression/idle/look target，執行 kill/restart A07。

## 2026-09-24／T17 交接

- 完成與變更：五類記憶、migration 005/FTS5、identity/person/time/source/kind filters、衝突 semantic facts、revision/correction/deletion/derived invalidation，以及認證管理 API。
- 驗收：A10 固定 20 組為 20/20 top-5；A11 更正、刪除、scope、FTS rebuild、backup/restore 均通過；`scripts/check` 66 passed、3 opt-in skips。
- 工作區：`main`，所有變更仍未提交；secret 維持 ignored。
- 真實／mock：SQLite、FTS5、migration、backup/restore、ASGI API 為真實 integration；資料為 deterministic 合成 L1。
- 下一步：T18 實作 bounded/cancellable/idempotent consolidation、provenance、relationship revisions 與 trait clamps。

合法實作狀態：TODO → IN-PROGRESS → VERIFYING → DONE；有問題可標 BLOCKED-EXTERNAL/FAILED，解除後回 IN-PROGRESS。若只有模擬測試完成，寫「L1 完成，L2/L3 待驗」，不改成完整 DONE。

## 每次交接追加

```text
日期／任務：
完成與變更檔案：
驗收命令、結果、證據路徑：
目前 branch/commit/dirty state：
真實／mock／尚未驗證：
新的決策與缺陷：
下一步具體動作：
```

## 2026-09-30／Phase 1 現況稽核

依使用者新要求停止 integration implementation，只做 inspect/trace/verify/document。
稽核入口：[CURRENT_ARCHITECTURE_AUDIT](runtime-evolution/CURRENT_ARCHITECTURE_AUDIT.md)，完整索引見 [DOCUMENT_STATUS](runtime-evolution/DOCUMENT_STATUS.md)。原 T00–T40 任務卡與完成表未重寫；新增 reconciliation 說明產品接入與元件完成的差異。

本次 baseline：Python 193 passed / 1 failed / 5 skipped；失敗為 migration test 期待 10、實際 12。Rust 6 passed；ruff/mypy 通過。localhost:8000 health 連線失敗，未啟動服務或聲稱真 provider/硬體通過。既有原生 ModelMessage 介面仍未接 ConversationEngine；本次不繼續修改。Phase 1 文件完成，Phase 2 未開始。

## 2026-09-30／Phase 2 Runtime Evolution 設計

使用者授權設計 Phase 2。新增 runtime-evolution 的 SPEC、COMPATIBILITY_PLAN、MIGRATION_PLAN、ROADMAP；RT-001–015 全為 PLANNED。保留現有 Core/Character/Live2D/Qwen v1 音色，分階段補工具loop、執行取消、worker lifecycle、journal/recovery，再接 session/provider/browser/memory/scheduler。未修改 production，未執行migration或重启服务。規格門檻為設計目標而非實測。下一個可實作任務 RT-001。

## 2026-10-01／RT-001 完成

核對真 migration 升級/重跑/資料保留與正式 Gateway subprocess 啟停，僅修改測試。全套 198 passed、5 skipped；mypy/ruff 通過。證據見 `docs/evidence/RT-001/README.md`。真 provider/硬體未驗；下一卡 RT-002。

## 2026-10-01／RT-002 完成

optional native messages從IntegratedCompanion/CompanionCore送到ConversationEngine/adapters；主入口candidate opt-in，legacy預設保留。兩轮assistant/tool call_id與原目標payload整合測試通過。全套199 passed、5 skipped；最後相關5 passed；ruff/mypy通過。證據docs/evidence/RT-002/README.md。history僅RAM；本轮停止，不提前做RT-003。

## 2026-10-01／RT-003完成

candidate整批terminal才續模型、callback去重、唯一final、排隊取消及late輸出fence。HTTP拒絕輸入從true-only擴充bool，拒絕不執行。相關38 passed、全套206 passed/5 skipped、mypy/ruff/format通過；100合成交錯測試。證據docs/evidence/RT-003/README.md。未做RT-004，OS running清理仍RT-005；本輪停止。

## 2026-10-01／RT-004完成

candidate computer.execute接有界argv facade，兩pipe持续drain、共用64KiB；legacy保持原binding。真main兩profile結果回歸、100MiB洪流/timeout/exit測試通過；相關41 passed、全套213 passed/5 skipped、ruff/mypy/format通過。本機parent RSS採樣delta400KiB，測量界線詳evidence/RT-004。未做RT-005；本輪停止。


## 2026-10-01／RT-001–004 verification findings修正

修正RT-004 controller/executor profile不一致，startup binding固定。正式main兩profile中途env變動回歸先兩例FAIL、修後PASS；timeout測試確認PID回收；RT-003增加100completion-first與100cancel-first順序驗證。相關43 passed、最後batch8 passed、其餘baseline69 passed；ruff/mypy/format通過。未做RT-005，未真provider/GUI/GPU驗收；證據docs/evidence/RT-004/profile-freeze-fix/README.md。舊verification報告保留歷史，RT-004 DONE附修後證據。


## 2026-10-01／RT-005完成

candidate ExecutionContext從run/proposal傳到真argv executor；cancel/timeout owned group TERM→KILL/reap/drain，有界cleanup failure明報；auto/manual tool output fence。Gateway turn→session取消避免影響其他session，unknown ID不殺程序；legacy/explicit active alias相容。相關74 passed，全套229 passed/5 skipped，最後task-specific14 passed；ruff/mypy/format通過。三次parent-child取消約0.252s，100合成context交錯零late UI。scope patch/digests/evidence見docs/evidence/RT-005/README.md。

ack detach、escaped daemon、RAM guards/recovery、真服務/GPU/GUI仍受所列限制；未做RT-006，本輪停止。下一張可執行task為RT-006，但未開始。


## 2026-10-01／RT-005獨立驗證修補

原DONE被獨立writer驗證推翻：terminal後18個queued工具事件。candidate固定UI stream identity，補唯一writer與前端consumer fence，manual proposal關聯metadata；原queue公平仲裁、legacy、DB/config保持。競態fixture啟動與2秒cancel門檻分離、增加原task異常/iteration/stack診斷；歷史超時精確原因仍NOT VERIFIED。

原獨立反例1 passed、專項重跑15 passed、最終全套237 passed/5 skipped、ruff/mypy169files/format PASS。RT-005恢复DONE限已測fixture acceptance；原FAILED_VERIFICATION報告不改，修後證據docs/evidence/RT-005/delivery-fence-fix/README.md。真provider/GUI/GPU、active shutdown與部署rollback未驗；RT-006未實作，本輪停止。


## 2026-10-01／RT-006完成

candidate Qwen worker私有request/epoch配對、有界8個render、startup/render失敗及取消回收、poisoned隔離、close；真HTTP disconnect/active Gateway lifespan接入。保留v1 reference/model/語音演算法，legacy render相容。task14 passed、相關46 passed、全套251 passed/5 skipped，ruff/mypy170files/format PASS。真RTX3050首次25.7s、cache0.0022s、cancel0.277s、restart/close reaped、WAV PCM16/24kHz與reference SHA相容。

未人工聽測/真GUI/soak/部署rollback；單adapter owner，legacy故障路徑保留。精確patch、digests、測試/GPU metrics與限制見docs/evidence/RT-006/README.md。未做RT-007，本輪停止。


## 2026-10-01／RT-006維持PARTIAL／前端取消修補

原DONE撤回。原報告「前端取消fetch」不實已更正；補每speech AbortController/generation、pause/revoke與晚到結果fence，既有button在currentTurn已清空時仍能停止speech。新actual frontend Node6cases，相關25 passed；真隔離candidate頁面觀察生成中/播放中取消返回待命、Cubism角色可見。owner人工聲線/聽覺取消/畫面相容待回報，不能算PASS。最終全套257 passed/5 skipped、ruff/mypy171files PASS；scope patch見docs/evidence/RT-006/frontend-cancel-fix。保留獨立報告歷史；未做RT-007。


## 2026-10-02／自動選RT-006／PARTIAL人工gate

讀全部RT tasks/dependencies，排序最前未完成仍RT-006（RT-001 DONE）。前端/worker接線已存在；重跑相關25 passed，ruff/mypy171files PASS，127.0.0.1:8000驗收服務alive。只補roadmap過時current implementation註記/證據，未改production/test，未做RT-007。owner人工聲線/聽覺取消/畫面確認仍待回覆，不能升DONE；詳docs/evidence/RT-006/acceptance-followup-2026-10-02/REPORT.md。


## 2026-10-02／RT-006 DONE／owner人工驗收確認

owner針對聲線、聽覺停止、角色畫面驗收問題回覆「可以」，記錄於docs/evidence/RT-006/acceptance-followup-2026-10-02/OWNER_ACCEPTANCE.md；人工gate PASS，結合修後自動/GPU/GUI證據，RT-006更新DONE。原PARTIAL與獨立報告保留歷史，本輪只改文件，未重跑測試。長期soak/跨processGPUbroker/部署rollback仍未驗；未開始RT-007。


## 2026-10-02／RT-007 DONE

依全部task狀態/依賴自動選RT-007，RT-003/004 DONE。candidate descriptor統一現有schema/handler/readiness，逐回合快照及dispatch再查（含contextual task入口）；新增授權且去密鑰/v1/runtime診斷，保留legacy/env priority/public formats。

專項16 passed、相關73 passed、全套273 passed/5 opt-in provider skipped，ruff/mypy172files PASS；真Gateway network診斷與tools-off smoke PASS，精確scope reverse patch check PASS。JSON settings未載入如實報告；browser/model測試替身、真computer子程序；真provider/GUI/GPU/soak/部署rollback未驗，既有port8000未重啟。證據docs/evidence/RT-007/README.md。只完成本卡，未開始RT-008。


## 2026-10-03／RT-008 DONE

自動選最前PLANNED RT-008，RT-003/005/007 dependencies DONE。candidate同transaction建立run/journal，canonical context在provider前checkpoint，batch先commit，common orchestrator dispatch/observation hook覆蓋auto/manual；持久round/tool預算，startup unknown/not_dispatched配對與舊提案fence，不重播。新增授權readback與前端中斷提醒；既有enum/舊migration/config/body/voice保持。

四個真process crash + real file副作用fixture、partial batch/duplicates/budget/reopen/schema相容、真installed main network recovery PASS。最終專項12+launcher1共13 passed，相關92 passed，全套285 passed/5 skipped；ruff/mypy174files/format/reverse patch check PASS。

中途full suite有launcher failure，根因舊測試沿用default data套初版013後draft SQL變動；恢復最初013，未改DB checksum/刪資料，唯讀integrity ok；測試改隔離env/data，保留default DB additive013與歷史fail evidence。無私有內容進證據。恢復僅local readback、非自動續跑/OS效果驗證；真provider/GUI/GPU/soak/power loss/部署rollback未驗，port8000未重啟。詳docs/evidence/RT-008/README.md。只完成本卡，未開始RT-009。

## 2026-10-03／RT-001–008 Architecture Review

完成 `docs/runtime-evolution/ARCHITECTURE_REVIEW.md`，依十份設計／稽核輸入、RT evidence、實際 code/diff 與隔離反例評估 drift。整體 YELLOW，成果方向正確；run/proposal identity、dispatch terminal decision、handler cancellation 交界列 RED，只允許窄修補。未修改 production、既有測試、migration 或 roadmap 編號／狀態。

本次全套 `uv run pytest -q`：285 passed、5 skipped、3 warnings，52.53s；ruff PASS、mypy174files PASS。隔離 probe 確認跨run call-ID／restart衝突、provider FAILED後仍dispatch並completed、arguments-only handler取消terminal後仍執行；probe exit0代表反例成立，不是acceptance PASS。另記run/proposal RAM retention及跨repository耦合。證據在 `docs/runtime-evolution/verification/architecture_review_2026-10-03/`，RT-008十個完成digests吻合。未重跑真provider/GPU/GUI/Rust/硬體/soak/部署rollback；既有RT-006 owner人工驗收保留。

建議下一組RT-009、RT-010、RT-011 budget切片（不排序），先滿足報告中的RT-003/005/008交界修補gate；RT-011摘要與RT-013/015 DEFER，取消RT-010重複run recovery子工作，保留其他已解決成果。新阻擋項是candidate promotion與功能擴張gate，不把有限DONE歷史改寫成整體runtime已驗收。

## 2026-10-04／Architecture review 修復任務定義

新增 `docs/runtime-evolution/FIX_REGISTER.md`：AR-01/02/03 分為 REQUIRED_FIX，分別建立 RT-003-FIX-01、RT-005-FIX-01、FIX-001，均 PLANNED／未執行。各卡含來源、確認根因、最小範圍、禁止修改區、相容、測試、驗收、rollback 與風險。AR-04/05 保持 TECH_DEBT，不建立立即改造卡；其餘文件漂移、未驗條件、已修歷史事故與排除指控逐項分類。SPEC 不變條件仍成立，無證據推翻 Runtime Evolution 設計，未建立 ARCHITECTURE_CORRECTION。

更新 RUNTIME_EVOLUTION_ROADMAP：RT-003→PARTIAL；其餘已完成卡保持限定 DONE／歷史證據；插入三張 FIX、RT-009–015 各自 BLOCKED_BY_FIX，列直接／傳遞依賴及解除條件。RT-013/015 解除 FIX 後仍延期，RT-011 摘要延期。原 RT 編號不變。

本輪只有文件變更，未修改 production、tests、migrations、私人 DB 或運行中服務；沿用 2026-10-03 review 的反例與測試結果，未重跑產品測試，不宣稱修復成功。檢查 register 必填欄位、roadmap 狀態／gate、連結、source digest 不變與 diff whitespace。下一步只能依已定義 FIX 執行窄修補及獨立驗證，不能直接開發受阻 RT 卡；本輪授權止於定義任務。

## 2026-10-04／FIX-001 DONE

只修 AR-03 failed/cancelled generation dispatch gate；第一輪／續作先判斷 COMPLETED，Core partial text 保留但 rejected calls 不進 canonical accepted history，原錯誤/取消狀態及 rejected intent 留 final 診斷，既有 observation 不抹除。production 只改 integrated.py／companion.py；不改 transport、schema、executor 或配置。

修前24正式反例FAIL；最終32專項PASS（加真generation deadline）、相關91PASS、全套317PASS/5 opt-in real-provider/speech skipped、ruff/mypy174files PASS。另組HTTP四情境＋真effect file、隔離修前caller回退reader/text-only/no-replay PASS；部署rollback/真provider/GUI/GPU/soak NOT VERIFIED。完整原失敗/fixture修正紀錄、patch、scope與逐項驗收見 docs/evidence/FIX-001/REPORT.md。108個其他review指紋與013 checksum不變，原dirty工作保留。

FIX-001 DONE；RT-009此gate解除為PLANNED但未開始；RT-011/015保留其他blockers/DEFER。RT-003維持PARTIAL，RT-002/008限定DONE不擴大。剩餘兩張FIX仍PLANNED。本輪完成停止，不自動開始下一FIX或RT。

## 2026-10-04／RT-003-FIX-01 DONE

provider-local call ID 與 candidate private storage identity 分離，既有 proposal UUID＋exact journal binding 同transaction建立；公開call ID、HTTP approval、model pairing保留。callback/reconcile精確owner、legacy crash-gap/no-replay相容；run-scoped dedup terminal清理。不新增migration/架構，production限integrated/orchestrator/runs，保留全部既有dirty與FIX-001。

修前2FAIL、專項/原source65PASS、擴大相關125PASS、全套326PASS/5 opt-in skip、ruff/mypy174files PASS。真process before/after atomic binding crash與transaction rollback、混合新舊row/unknown、manualHTTP、A/B、oldcallback、same-run duplicate PASS；獨立真file三run/restart各一次效果及保留reader/guard的caller回退無重播PASS。部署rollback/真provider/GPU/GUI/soak未驗。見 docs/evidence/RT-003-FIX-01/REPORT.md。

RT-003恢復DONE/VERIFIED；RT-010、RT-011 budget的FIX gate解除，summary/RT-014仍有原依賴。RT-012/015仍待RT-005-FIX-01。使用者本輪授權剩餘FIX逐張處理；本卡已完整通過後才開始RT-005-FIX-01，未開始任何後續RT。

## 2026-10-04／RT-005-FIX-01 DONE／剩餘 FIX 修復完成

candidate共用invocation納管arguments-only task，取消一次並最多4.75s等待；拒絕/延遲cleanup用FAILED/ExecutionCleanupError與journal unknown，保留task owner至實際結束，無late UI/新dispatch。fixture先證明browser enter取消洩漏，再修startup acquisition/close/finally stop；現有application caller保護spawn與ack前ownedgroup，ack後user-managed維持。只改orchestrator/gateway既有caller/browser；execution.py、schema、授權與其他已完成FIX保持。

修前handler/browser3FAIL；launcher spawn/pre-ack2FAIL、ackPASS。最終專項33PASS、相關147PASS、全套344PASS/5 opt-in real-provider/speech skipped、ruff/mypy174files PASS。真本機headless Chrome取消關閉connection/Playwright、GTK/Firefox caller真synthetic程序spawn/ack、A/B、HTTP manual、shutdown、5s cleanup failure/unknown與原argv/batch/races/terminal fence PASS。獨立真filecleanup前於terminal約0.027s、精確pre-FIX source legacy text-only回退保留journal/no-replay PASS。真GUI/escaped daemon/GPU/soak/部署rollback NOT VERIFIED，不能聲稱所有外部效果停止。詳 docs/evidence/RT-005-FIX-01/REPORT.md。

FIX_REGISTER三張FIX全DONE；RT-003 DONE/VERIFIED；RT-009/010/012、RT-011 budget解除FIX gate但未實作。RT-011 summary/RT-013/015仍DEFER，RT-014仍依賴RT-010，retention/single-owner與外部release gates保留。本輪依使用者授權逐張完成剩餘兩FIX後停止，沒有開始新的RT、重構或重啟私人服務。

## 2026-10-05／修復請求現況核對

使用者要求修復後，核對工作區發現三張 FIX 已於 10-04 完成；本輪閱讀修復 evidence 並查核 generation gate、run-scoped dedup／atomic proposal binding、共用 handler task ownership，未重複修改 production 或開發後續 RT。

本次執行 `uv run pytest -q tests/integration/test_agent_batches.py tests/integration/test_run_journal.py tests/integration/test_tool_orchestrator.py tests/integration/test_execution_lifecycle.py tests/integration/test_gateway_main.py tests/integration/test_gateway_terminal_fence.py`：103 passed、3 dependency warnings，42.33s，exit0。`uv run ruff check src tests` PASS；`uv run mypy` PASS／174 files。本輪未重跑全套、真provider/GPU/GUI/soak/部署rollback，先前344PASS/5skip仍為歷史結果。三FIX維持DONE，無新已確認修復缺口；技術債與其他RT保持原狀。


## 2026-10-05／RT-009 DONE

自動核對全部RT/dependencies/FIX gates，選最前PLANNED RT-009（RT-007/008 DONE、FIX-001 gate解除）。candidate main沿用原provider priority，包既有FailoverModel；每generation最多2invocations，僅transient pre-emission重試，text/tool/finished與OpenAI緩衝片段failure均禁止再attempt。取消backoff、request privacy/messages/output budget與新private generation ID保留；legacy與SIRO_MODEL_RETRY_ENABLED=0使用原單provider，startup固定。

main沒有費用budget，額外cloud request固定0，不因local旁已有key就新增cloud fallback；direct wrapper explicit request-count budget不代表USD/day會計。必要adaptererror note保留原error class；不改port/schema/FIX/core/body/audio/identity。專項32PASS、相關153PASS、全套376PASS/5 opt-in skip，ruff/mypy176files/format/reverse patch check PASS。真local HTTP transport fixture與main/Core/SQLite/ASGI＋真Python fileeffect通過；models合成，真provider/GUI/GPU/soak/部署rollback未驗，私人DB/服務不碰。詳docs/evidence/RT-009/REPORT.md。本輪只完成此卡，未開始RT-010。

## 2026-10-05／RT-009 verification repair DONE

獨立報告指出wrapper固定name=failover造成selected provider durable backend regression；已重現並先標FAILED_VERIFICATION。最小修正僅failover.py在constructor捕捉primary.name，保持Integrated→SQLite→readback原consumer鏈；名稱不隨attempt變動，無schema/API/配置格式變更。補main local/cloud retry on/off真SQLite與fresh-store readback assertions及fallback name穩定契約。修復前6FAIL/3PASS；修復後專項含原獨立test35PASS，全套378PASS/5 opt-in skip/3dependency warnings；ruff/mypy176files/scoped reverse patch dry check/diff whitespace PASS，roadmap恢復DONE。

既有failover rows不猜回provider；metadata是selected-primary、不是attempt audit。真provider/GUI/部署rollback/soak仍NOT VERIFIED，未碰私人DB或重啟8000，未開始RT-010。D25與 docs/evidence/RT-009/provider-metadata-fix/REPORT.md 保留修復diff/logs/digests；原獨立驗證與原implementation report保留歷史。

## 2026-10-05／RT-010 DONE

自動掃15張RT選最前PLANNED、dependency滿足的RT-010；RT-008 DONE且FIX gates解除，RT-009 metadata修復保留。重用completed version1 canonical journal，exact session/同privacy取最新6完整raw user/final assistant pairs（12messages），接新system/current raw user native roles。Core為單一append owner，continuation不重hydrate；不讀legacy assembled messages、不複製舊system/tool intents或unknown effects，恢復未知run仍RT-008 readback-only；無journal重建、migration/identity/memory/affect/audio變更。candidate startup固定SIRO_SESSION_RESTORE_ENABLED，0保留舊working path。必要Integrated/Gateway接線超expected清單記D26。

改4production：core/companion.py、agent/runs.py、presentation/integrated.py、gateway.py；加test_session_restore.py，native serialization舊test分restore on/off保留原pair斷言。temp pre-task source在第二startup重現缺dialogue；專項/相關15PASS，最終全套388PASS/5 opt-in skip/3dependency warnings（89.73s）、ruff/mypy177files/format/scoped reverse patch dry check/whitespace PASS。首輪full386PASS/1FAIL是舊test對candidate無跨run對話假設，已按D26新契約分on/off驗收，保留初次log；首個before launcher系統Python無pytest亦保留並修正。

驗收層級actual main/Core/SQLite/ASGI lifecycle三次重啟＋actual Python subprocess；provider/transport合成，未等同真daemon/GUI/provider/GPU/soak/power loss/部署rollback。只恢復completed recent dialogue，不含整段工具transcript、cancel/failed/direct-command history；12則不是token budget，retention/single-owner限制不擴張。私人DB/8000服務未碰。docs/evidence/RT-010/REPORT.md保存selection/source snapshots/patch/digests/logs/rollback。只完成RT-010，RT-011及其他卡不開始；下一輪重新選卡。

## 2026-10-05／RT-011 PARTIAL（byte guard實作完成）

自動核對15RT，選最前PLANNED且RT-002/010依賴滿足的RT-011 budget切片；summary仍DEFER，只此卡。D27先記discrepancy：目前無provider tokenizer/context-window metadata，byte cap不能當token-limit PASS；整卡PARTIAL不標DONE。services/agent/context.py新增最小LanguageModel wrapper，測complete logical ModelRequest compact JSON UTF-8 bytes；candidate main包在FailoverModel外，預設65536bytes，SIRO_CONTEXT_MAX_BYTES=0關guard，startup固定；name保留selected provider，無超限retry。超限ContextBudgetExceeded走原Core FAILED/terminal/journal/readback，goal/system授權來源/pending pair不截斷、不刪。必要gateway.py接線超expected清單已記；不改Core/migration/model port/音色/affect/memory，也不做summary。

test_context_budget.py專項8PASS；最終全套396PASS/5 opt-in skip/3dependency warnings（85.84s）；ruff/mypy179files/format/scoped reverse patch dry check/whitespace PASS。before main重現64-byte cap未生效仍COMPLETED；actual main/Core/SQLite/ASGI feature-on/off/legacy、exact UTF-8 boundary、request identity、cancel、provider provenance、400k工具結果先一次handler後零continuation provider、完整goal/tool pair readback通過。provider/executor合成，不能標真服務/副作用PASS。measurements.json只合成size數字；無私有資料。

Required remainder：verified selected provider tokenizer/context-window metadata、input+reserved-output budget及真token boundary gate；byte/logical-json尺寸不等於token/HTTP framing/peak RSS。真provider/GUI/GPU/soak/power loss/部署rollback仍NOT VERIFIED。SIRO_CONTEXT_MAX_BYTES=0下次drained startup回滾、DB保留；私人DB/8000未碰。docs/evidence/RT-011/REPORT.md含selection/snapshots/patch/digests/logs/measurement。只此卡並停止，未開始RT-012。


## 2026-10-05／RT-011 budget DONE／native gate補完

依使用者繼續補完授權，只補RT-011剩餘native gate。pinned GPT-OSS20b官方tokenizer/template/hash、selected Groq profile/context/output reserve、同adapter payload、thread counting/cancellation、missing/unknown fail-closed已接candidate實際路徑；byte guard獨立。D28記scope必要adapter/gateway/dependencies調整；不改Core/schema/affect/音色。Summary仍DEFER。

專項23PASS、executor34PASS、full411PASS/5 opt-in SKIP/3 dependency warnings；ruff/mypy181files/format/wheel inclusion/scoped reverse dry check PASS。官方HF四case counts一致；兩組真Groq合成probe79/83、176/170差異在256餘量內，未保存key/private dialogue。官方reference與server framing不宣稱完全相同。初次harness及synthetic fixture失敗log全部保留。

GUI/GPU/power loss/soak/deployed rollback NOT VERIFIED；其他models未profile時明報，fresh checkout需setup public assets。私人DB/8000服務未碰。Native0/byte0各自停對應guard，下次drained startup回滾；無migration。完整證據docs/evidence/RT-011/token-completion/REPORT.md。只本卡budget DONE並停止，未開RT-012。


## 2026-10-05／RT-012 DONE／持續 browser session

自動核對15RT，選最前PLANNED且RT-005/007與FIX依賴滿足的RT-012。新增service BrowserSessions wrapper包既有ScopedBrowserDriver；candidate main/catalog/contextual executor以trusted ExecutionContext.session_id擁有driver。保持navigate+read舊url契約，加read/fill/click/close candidate工具；同origin跨run保留page/sessionStorage，epoch+原DOM hash拒cross-session/recreated/stale目標，操作回fresh readback。TTL300s/cap8/action30s、token/repeated task cancel/explicit close/shutdown及cleanup failure明報；無credential persistence。driver Core、Core identity/affect/audio/model assets與DB格式未改。D29記必要caller/schema與shutdown hook；shared WS無canonical owner mapping，disconnect走idleTTL。

專項/相鄰33PASS；full419PASS/5 opt-in SKIP/3 dependency warnings（127.82s）；ruff/mypy183files/format/hash/reverse patch dry check/whitespace PASS。真headless Chromium本機合成跨頁form/A-B/stale/cancel、actual main兩run模型consumer/SQLite/lifespan及feature-off/legacy回stateless驗證PASS；model/body合成，未當成真人GUI/真provider規劃驗收。before source真main無actions/readback反例與初次inventory2FAIL保留logs。Source精確5files patch/snapshots/digests見docs/evidence/RT-012/REPORT.md。

Remaining implementation blockers：NONE。限制是ephemeral single-Gateway/browser scope、origin change reset、error close、already-performed effects不可undo；更廣GUI/long soak/power loss/private deployment屬產品release gate，不列本卡未完成feature。Rollback於下次drained startup SIRO_BROWSER_SESSION_ENABLED=0，先close owned browsers，保留DB；isolated行為已驗，私人部署未動。未重啟8000或碰privateDB、未開始RT-014/任何下一卡；下一輪重新核對roadmap。


## 2026-10-05／RT-014 DONE／有來源的 owner memory ingress

核對15RT，RT-013/015 DEFER；RT-014舊BLOCKED依賴RT-010實已DONE，記discrepancy後只選RT-014。candidate server-recorded UserTextEvent明確leading記憶要求接MemoryService/既有SQLite add/revision，固定identity siro/person owner與original source/session。UUID5 same-event去重、episodic user statement不寫SemanticFact/persona；model/tool continuation不接ingress。Commit後提供sourced verified context，失敗FAILED且零model；cancel/terminal fence保留。既有correct/delete/revisions API與active recall跨重啟通過。

D30必要Core/repository/Gateway wiring加optionalroute filter：candidate cloud僅可讀all sources cloud_allowed，local/unknown sources不外送，原user event local_only不降privacy；legacy/defaultAPI保持。SIRO_MEMORY_INGRESS_ENABLED startup固定、0停未來writes但不刪memory/撤filter。無schema/dependency/HTTPWSformat/identity/affect/relationship/retention改變。

專項/相鄰27PASS；full426PASS/5 opt-in SKIP/3 dependency warnings（152.36s）；ruff/mypy184files/6fileformat/hash/reverse dry check/whitespace PASS。actual main/ASGI/Core/SQLite四lifecycle、source/provenance及fresh model consumption、真argv malicious remember output不成fact、synthetic cloud無localmemory、failure/empty zero-provider與rollbackfixturesPASS。before main missingmemory反例與initialfixture診斷均保留。docs/evidence/RT-014/REPORT.md含精確6source/test檔patch/digests/before。

Remaining production blockers：NONE。限制為explicit markers／existingAPI mutations、owner statement非外部truth、localonlymemory不自動授cloud、memorydelete不清rawconversation；原retention維持。更廣真人GUI/longsoak/private deployment另releasegate，未假稱完成。下次drained startup flag0回滾futureingress，DB/revisions保留；私人DB/8000未碰。完成只此卡並停止，RT-015保持DEFER。

## 2026-10-06／Runtime Evolution architecture review（無 production 修改）

更新 docs/runtime-evolution/ARCHITECTURE_REVIEW.md，審查近期 RT-009/010/011/012/014 與舊 FIX，整體 YELLOW。舊 AR-01/02/03 已由三項 FIX 解決，不重開。隔離組合探針確認 AR-06：native guard 不接受多 tool_calls transcript，兩個效果完成後 continuation 失敗；native off 同案例 completed。AR-07 為靜態確認的 clean CI tokenizer provisioning 缺口，未執行 remote CI。建議完整 native integration PARTIAL、相關 rollout BLOCKED_BY_FIX；不改原 RT 編號或 DONE 歷史。本輪未改 roadmap、production、私人 DB 或服務。

10-05 本輪專項七組 81 PASS／3 warnings（23.98s）；ruff PASS、mypy 184 files PASS。未重跑 full suite；RT-014 的 426 PASS／5 SKIP 僅歷史證據。26 個近期 evidence source digest 一致。探針、結果、指紋、舊 review 歸檔與執行紀錄見 docs/runtime-evolution/verification/architecture_review_2026-10-05/。

下一範圍：RT-011 局部相容性與資產驗證修復；RT-012 pool lifecycle、RT-014/010 privacy/revision/restore 組合驗證，無排名。RT-013/015 與 summary 維持 DEFER，不為湊三張任務啟動新功能。部署 rollback、真 provider 完整閉環及長時間 soak 仍未驗證。

## 2026-10-06／三項 DEFER 規劃

新增 docs/runtime-evolution/DEFERRED_TASK_PLAN.md，定義 RT-013 caller/parity/收益、RT-015 retention/single-owner/foreground、RT-011 summary 需求與 source invalidation 的 evidence slice、解除條件、最小 scope、tests、rollback 與 CANCEL 條件。三項保持 DEFER，無排名／新 RT 編號／production 修改。Roadmap 更正 RT-015 依賴已完成，補上 AR-06/07 目前 gate 與規劃連結，不覆寫原完成歷史。本轮僅文件檢查，未執行功能測試或規劃中的量測；下一步為依各項 gate 收集隔離證據，再決定是否施工。

## 2026-10-06 / AR-06 + AR-07 repair; DEFER gate evidence

Private counting-only normalization now permits exact completed multi-call batches and conservatively counts all arguments/results; no wire/journal/executor change or effect replay. scripts/check provisions pinned public tokenizer before pytest. Before rejection now passes; actual main/Core/SQLite + real tool subprocess normal/oversized regression fixtures PASS. Native suite 19PASS; full430PASS/5 opt-in SKIP/3 dependency warnings; adjacent9PASS; product ruff/mypy184files/schema/changed-file format/shell syntax and isolated reverse-patch dry run PASS. Evidence docs/evidence/RT-011/ar06-ar07/REPORT.md.

Whole-repository lint/format remain failing due evidence artifacts and existing formatting in two unrelated tests; remote/full clean-check CI not executed. Do not report overall CI PASS. No private data/provider calls/live8000 restart.

DEFER gates checked: RT-013 has no matching scoped production caller/benefit; RT-015 retained100 completed keys after active0, cleared only onclose; RT-011 six-pair synthetic history fits6736 tokens, summary need/source gate unproven. Three remainDEFER with reasons in DEFERRED_TASK_PLAN, not merely forgotten status. Next bounded work is identifying a necessary background caller and specifying bounded owner/retention before RT-015 pump implementation; no automatic Rust/summary feature.

## 2026-10-06／DEFER 能力需求研究（無程式變更）

新增 docs/runtime-evolution/CAPABILITY_NEEDS_RESEARCH.md。對照 PLAN/EXPERIENCE 與 consolidation、memory revision/delete 實作，支持先研究 RT-015 閒置來源記憶整理；第一步限定候選與來源核對，不直接啟用目前可 committed 的 consolidator。記錄 event provenance 與 parent-memory derivation/revision 的差異，須驗證更正刪除閉環。RT-013 尚缺真 caller／目錄需求；RT-011 用合成案例分辨窗口遺失、超限及 AR-06，不直接採摘要。三項維持 DEFER，未寫程式、未跑新功能測試、未使用私人資料；CI 格式未驗，與 AR-07 資產問題區分。

## 2026-10-06／RT-013、RT-015、RT-011 summary 產品交付 DONE

依使用者「不要延期了，都做，要看到產品成果」明確授權，完成 D31 有界切片。RT-013：專用工作目錄，signed scoped Rust read/list，同時供模型 orchestrator 與明確 owner UI 讀取；中文路徑、越界、tools switch、取消與程序收尾已驗。RT-015：單一 lifespan owner、本機有來源記憶歸組、100筆/5秒、合併trigger、前景取消、更正／刪除後來源核對與可丟棄view；不自動寫facts／人格或送cloud。RT-011：24組bounded restore、本機extractive source-hash摘要、保留目標/system/pending/latest，最終仍經原budget；memory mutation fence/cutoff，raw journal保留。三張原編號保留，DEFER解除；通用semantic consolidation／無限歷史不在完成宣稱。

新控制頁提供工作目錄讀取、整理開關、記憶更正刪除、摘要狀態。scripts/start-runtime-product 可啟動；PRODUCT_QUICKSTART.md 記設定與回滾。隔離離線預覽 http://127.0.0.1:8026 已啟動，只有合成資料；未取代私人服務、未動私人DB／key／GPU／角色資產。

最終 full suite 437 PASS／5 opt-in SKIP／3 warnings（93.84s）；last stat-check refinement後 workspace 2 PASS；Rust workspace tests PASS（library6）；ruff format/check whole repo PASS，mypy191files PASS、schema/shell syntax PASS。瀏覽器真UI Rust列檔讀檔、更正刪除、整理暫停/重整與零page errors PASS。七天fakeclock不是七天soak。初次6個舊catalog/shutdown fixture failure已修，原log保留；中文grant hash相容性另補實測。remote CI、真provider/語音/GPU/private部署rollback與長soak未驗，不把skip算PASS。

證據 docs/evidence/runtime-product-2026-10-06/REPORT.md，包含source-only patch/digests/isolated reverse dry-check、UI截圖與log。既有未提交變更保留。回滾採drained restart三個flags off，保留DB/journal/native/privacy guards；不倒回整個dirty working tree。下一步是以實際模型與使用者工作檔操作這三個入口，產品品質驗收不再以這三張DEFER為由停住。

## 2026-10-07／Companion 真實產品體驗修復

依使用者對文字、工作目錄與角色體驗的回饋，完成 D32 局部修復。正式 launcher 載入既有 allowlisted 模型設定、校驗 native profile 與本機 Live2D；缺條件明報，不再用 offline 固定回答充當產品。首頁以單一 Haru 與自然對話為主，既有 computer.execute 一般帳號能力露出，工作目錄退為次要讀檔入口。最新表情可在載入／斷線恢復，不重播 speech/effects；舊 socket 不會斷開新 owner。移除 SDK 隨機表情／切換及 sample voice，表情以真 Cubism files 套用，保留本機 licensed assets。

修正 HTTP 晚回應復活已完成 turn、多提案互相覆蓋／授權藏起、空 provider output 被誤判完成；final reply 用安全 DOM 格式化，語音可獨立關閉。補記憶保存／自動來源／bounded restore／雲端可見範圍的 runtime facts；偏好也依原來源 privacy 過濾，雲端不含本機 preference subjects 或衍生自由文字 affect reason。本機 appraisal／完整畫面不變，無新 schema／抽象／provider fallback／RT 改號。

最終 full pytest：460 PASS／5 opt-in SKIP／3 existing warnings，105.31s。整 repo Ruff check／format PASS（255 files），mypy195files PASS；schema／shell syntax／diff whitespace PASS。實際已設定模型＋隔離合成 DB＋本機真 Linux 工具＋licensed Cubism 的 greeting／記憶能力問答／uname與df→自然結果整理 PASS；F05 reload/tap與F08像素畫面變化、手機無橫向 overflow、零 page error PASS。Renderer tsc/vite build與idempotent PASS。較早一次 continuation HTTPStatusError 尚UNKNOWN，fresh合成probe與完整新run成功；未重送已完成工具，不把後續成功稱為根因已修。

原8026離線示範以 owned PID／cmd／data dir核對後正常停止；原.siro-data/siro.db已先做本機一致備份（backups/pre-companion-20261007/siro.db），新8026沿用原持久資料與設定。未將私人聊天／DB／key寫入evidence；真模型驗證只用隔離合成資料。已刷新使用者 in-app browser 並看到新版路由與 Live2D 已就緒，未對私人 store 提交測試對話。

證據 docs/evidence/companion-experience-2026-10-06/REPORT.md（沿用啟動修復時資料夾名；本輪日期10-07），含測試log、真模型合成結果、畫面、來源hash／process metadata。自動審核曾拒絕已保存對話的診斷重播，未執行；改用全新合成訊息。既有dirty內容保留。語音GPU口型、長soak、remote CI／發布與部署回滾仍未驗；雲端不自動讀本機限定記憶。下一步為產品實際使用與間歇provider錯誤可重現診斷；不以新抽象或重做既有RT代替體驗改善。

## 2026-10-07／桌寵、主動性、安全技能成長規劃與搜尋 FIX 定義

依使用者「只規劃就好」，新增 docs/runtime-evolution/COMPANION_EVOLUTION_PLAN.md，涵蓋桌寵真平台驗收、單一 body／音訊 owner 與安全換證、未完成任務主動追蹤、既有技能 catalog／worker 接入、OS 隔離的候選驗證、可信啟用與保留最新資料的程式回退。規劃沿用原 Core／Identity／Memory／Runtime，不新增平行工具框架、不重開已完成 RT、不把 helper 當成產品整合完成。

靜態確認 ProactivityRules／SkillDispatcher／procedural candidates 尚未進 Gateway 產品閉環；PatchVerifier 為同帳號目錄複製與 checks，不是 OS sandbox；技能 hash 未涵蓋執行碼／依賴；ReleaseManager 的 active pointer 尚非 launcher 部署，簽章未覆蓋全部相容欄位且 DB rollback 可能覆蓋較新寫入。這些是自主能力接線前的驗收門檻，尚未啟用或修復。本輪核對基準 c1d2d41，開始時 git status clean。

使用者另回報 Bing 搜尋 ScopeViolation。新增 FIX_REGISTER 的 FIX-002（REQUIRED_FIX／BAD_INTERFACE＋TEST_GAP／MEDIUM／PLANNED）：已確認 orchestrator 只留 exception 類名造成診斷資訊遺失；當次搜尋根因 UNKNOWN — NEEDS INVESTIGATION。畫面 Markdown 可能不是 raw arguments，candidate 完整 Markdown 理應先遭 schema 拒絕；driver 另有任何跨 origin 子資源被擋即整頁失敗的機制，尚未證明當次由此觸發。規劃以合成頁面分辨原因，不放寬 origin／redirect 邊界、不重播私人查詢。

Roadmap 只追加本輪規劃入口與 BLOCKED_BY_FIX：自動網路研究 promotion；桌寵與本機唯讀提醒不受該 gate 阻擋。RT-012 與其餘 RT 的 DONE／歷史編號保留。未建立 ARCHITECTURE_CORRECTION：目前證據未推翻原受限 Runtime／相容／來源設計。

本輪僅文件變更與靜態檢視，官方 OpenClaw／Electron 文件研究；沒有 production 修改、安裝、服務操作、私人 DB 讀取、功能測試或上述規劃驗收。git diff --check exit0；三份規劃／FIX／roadmap 的本機文件連結檢查零缺失，新規劃無尾端空白；變更範圍僅四份 Markdown。未重跑先前460PASS，不能將歷史結果算本輪通過。下一步待使用者要求實作時，先依 FIX-002 重現搜尋；桌寵按選型驗收做最小外殼，主動唯讀用途可獨立推進；自主啟用嚴守隔離與資料回退 gates。

## 2026-10-07／桌寵定義更正：自由活動與動作製作（只規劃）

使用者明確表示桌寵要能自主在螢幕走動、選擇活動，缺少動作由我們生成製作。更新 COMPANION_EVOLUTION_PLAN 與 roadmap，將自由漫遊／玩耍／休息列為正式完成條件；固定停靠、只可拖曳、站姿平移只能算降級／原型。拆清低頻活動選擇→單一 presentation 場景 owner→renderer，不將逐幀路徑／動作放入 Core、不把桌面玩耍當成任意 OS 操作權限。

唯讀檢查本機 Haru metadata：42 個現有參數無腿／膝／腳步；27 motion 中 model3 只掛 Idle2／TapBody4，無已驗 walk／play；本機資料夾無 PSD／CMO3／CAN3。未讀 binary／texture，不能據此判斷畫面裁切。新增我們負責的角色設計／圖像生成／可編輯分層／全身 rig／motion／資產包驗證流程；圖片生成不當成已完成綁定。核實官方 Haru 可編輯來源與 Cubism 製作／輸出說明、Editor Windows／macOS 支援；Linux renderer 不等於 rig 製作環境已備妥。

規劃補上情緒／身體位置／嘴型獨立控制、停止走路不清 expression、活動 generation fence、真 GNOME／Wayland 全 output 透明場景候選、動作包版本與回退。桌面場景原型、全身製作可並行，兩者與活動控制通過後才算自由桌寵。搜尋 FIX-002 gate 保留且只影響自主網路研究。

本輪仍只改規劃文件，未生成圖像／動作、改程式、安裝／啟動服務、操作私人資料或執行功能驗收；原有未提交變更保留。下一步實作時先打通場景透明／命中／漫遊與可編輯全身資產工具鏈，再以站立→起步→步行→停止／轉向→坐下／玩耍→可打斷的真畫面驗收，不將 helper 或影片預覽當完整產品。

## 2026-10-07／對話紀錄唯讀檢視與語音需求澄清（只規劃）

使用者追加授權「檢查最近的對話紀錄」，並澄清語音為生成等待太久、長文講不完。本輪依授權以 SQLite mode=ro／query_only 檢視當日15:40–16:07的14個run，另檢查服務狀態碼與8個WAV headers；未播放、生成、重播或匯出私人內容。早先條目「未讀私人DB」描述其原時點，本條為後續已授權唯讀檢視。

新增 docs/runtime-evolution/CONVERSATION_VOICE_REVIEW.md，僅存匿名現象／聚合與合成驗收。10 completed／4 failed（3 HTTPStatusError、1 ValueError）；至少3個completed final句中結束。failed journal所帶舊assistant不算本輪回覆，4個failed均無新的非空final。靜態確認adapter忽略finish_reason／非空EOF誤完成；實際截斷原因尚UNKNOWN。Gateway token TTL300秒、UI不續期，受檢log有4筆turns401；不能因此把上游HTTPStatusError全部歸因token。

語音現路徑為完整文字terminal→整段生成→完整blob→播放；現有segmenter未接此caller。Qwen worker codec max_new_tokens512，與文字output budget512不同；兩個近期WAV header同為40.88秒，未聽驗或取得EOS，僅為觸頂假設。現行冷／暖速度、尾句缺失根因未知，歷史cold25.700秒／cache hit不當成本輪效能。規劃先沿用聲線、單worker／一段預取分句播放與完成／版本快取，再有條件接final-answer完整句提早生成；保留cancel／epoch／owner，不能只翻streaming旗標或暗中省略全文。

FIX_REGISTER追加FIX-003（終止完整性）、FIX-004（session續期）、FIX-005（分段語音與延遲／尾句）、FIX-006（自身故障context與合成多輪ablation），均REQUIRED_FIX／PLANNED，每卡含evidence、未知根因、最小scope、禁改區、測試、acceptance、rollback與risk。COMPANION_EVOLUTION_PLAN及ROADMAP合併自由活動桌寵／對話／語音三項補充；搜尋FIX-002保留。BLOCKED_BY_FIX只限各相關產品promotion，不阻擋素材／場景原型／本機唯讀整理，不重編RT、不撤原DONE、不新增無證據architecture correction。

文件檢查：git diff --check PASS；四份規劃／review／register／roadmap共67個本機連結零缺失，FIX-003–006必填欄位完整，無尾端空白。只改五份Markdown；工作樹另有未追蹤本機WAV，本輪未修改、刪除或納入證據。未重跑歷史460PASS、未跑功能／真provider／語音／桌面驗收，未改production、寫DB、安裝、生成資產或操作服務。下一步待要求實作時逐卡重現／局部修復，理解品質需真provider合成對照，不能以mock或更多abstraction代替產品改善。

## 2026-10-07／FIX-003 實作與限定驗收完成

使用者已授權「照三份文件開始實作，驗收重要」。依AGENTS逐張進行，先完成FIX-003：OpenAI-compatible以typed nonretryable原因區分length/filter/不明終止/裸EOF；partial保留、工具終止前不yield，取消優先、串流確實收尾，cleanup error不洗掉主原因／buffered-intent fence；UI半句後仍顯示未完成且不朗讀成功。原Core/ports/其他provider/budget/schema不變，沒有私有DB寫入或服務重啟。

證據 docs/evidence/FIX-003-2026-10-07/REPORT.md。修前15FAIL；相鄰149PASS/3warnings；最終adapter/retry/UI/真HTTP→controller→SQLite81PASS/3existing warnings(7.05s)；mypy196files與changedRuff PASS。真配置模型只用合成新訊息，共兩輪4個有界request，最終正常短答與故意output-limit PASS；首輪發現asyncgen關閉警告後補explicit close與新反例，修後無該警告。兩個新整合fixture先誤認candidate私有call ID，已改精確proposal/journal binding、不改production契約；獨立review再指出cleanup錯誤覆蓋／取消／retry問題，新增修前3FAIL反例並修復，最終review無剩餘本卡blocker。

隔離source apply/reverse/完全恢復PASS，source.patch/digests/rollback.json保存；非部署rollback。未跑本輪full pytest/remote CI、未修改私人資料／語音快取、未驗桌寵／TTS。既有dirty文件／本機WAV保留。FIX-003 DONE/VERIFIED只限本卡，近期樣本截斷根因仍UNKNOWN；FIX-004/005/006及搜尋gate保留。下一張已獲授權FIX-004：在FIX-003 UI基線做single-flight換證、跨TTL真UI／無效果重送與token retention驗收，再推進語音與桌寵。

## 2026-10-07／FIX-004 session lifecycle 實作與驗收完成

FIX-004 DONE / VERIFIED，報告 `docs/evidence/FIX-004-2026-10-07/REPORT.md`。沿用300秒TTL／Origin／loopback／Bearer；頁面單一按需換證、5秒bootstrap timeout／3秒冷卻，只有精確pre-accept401可補證後重試一次，其他未知結果不重送。Gateway過期token清理與128有效token上限／滿額429，不驅逐有效頁面。控制連線snapshot才ready，owner／epoch／retired fence與最多三次自動重連；正常換證不動control/body。逾時／關頁清等待，取消與新輸入阻止舊的排隊發送；復原未送草稿，不將已送unknown當未送。

修前factory兩反例與control五反例均轉綠；相鄰123 PASS，獨立control18＋factory26共44 PASS。整體首輪552 PASS／2 FAIL：journal test舊擷取接點、completion-before-cancel fixture2秒等待在SQLite await逾時；局部修fixture後兩組61 PASS。前置completion wait有界10秒，取消後2秒及effects／terminal斷言保留；另Gateway直接cancel2秒仍驗。實際SQLite慢因未知，不臆測磁碟／鎖／排程問題。最終 `.venv/bin/pytest -q -m 'not real_provider'`：554 PASS／5 opt-in未選／3既有warnings，99.87秒。mypy199 files、全repo Ruff lint與261檔format PASS，未跑remoteCI或重建未改Rust。

真Chromium＋隔離Uvicorn/Gateway/index最終固定源碼跨306.581秒PASS／exit0；main-script at-load／finish hashes一致、JS errors0，三輪合成訊息與150ms靜音Audio playing／ended成功。過期只換HTTP證、不拆body/control；合成token失效401→200單次受理；斷control重連snapshot無turn/TTS重播，原body不變。browser／body／control／server／listener均清理後才PASS。第一輪306.743秒另存first-run，不混作final。這不是聲線、模型智慧、Live2D或私人服務部署驗收。

`verify_rollback.py`隔離reverse/reapply6原檔／3新測試PASS，保留FIX-003基線與最新資料；未操作8026、私人DB／快取或既有未追蹤WAV。FIX-004只解除session gate。下一張FIX-005 A完成判定／版本快取→B有界分句播放，保留原聲線；C未有已提交句子契約不能宣稱完成。搜尋FIX-002、理解FIX-006及桌寵／自主技能仍各自未完成。

## 2026-10-08 — FIX-005 A／B驗收中（尚未完成）

已實作新版Qwen正常EOS／生成上限判定、completion-v2獨立原子快取、無推論的有界語音計畫，以及前端最多預取一段、依序播完、明確停止／全文未完成／重聽。原聲線與既有worker所有權保留。複查先紅後綠修正分段空白遺失、明示無效protocol降級、empty/error音訊及零sample生成；零sample快取的紅證據亦已保存。相鄰completion最終90 PASS，前端89 PASS；這些是合成驗證，實際瀏覽器／原聲線／首段延遲／回退與全體回歸尚待執行。8026尚未重啟，私人DB與舊快取未修改，不能宣稱FIX-005 DONE。

FIX-005真聲線首輪：157字合成故事3段native playing/ended順序、EOS完整回報、最多一段預取、fresh推論中取消/reap及無晚音均PASS。RTX3050Laptop真cold短句31.195s；cache hit0.003664s（不當暖推論）；故事warm未快取30.337／36.196／21.221s，首播30.472s、段間23.289／6.387s，速度不合格，未宣稱修復完成／SLO達成，人工首尾聽驗尚未做。全體回歸669PASS／5 real_provider未選／3existing warnings；首輪中斷log的3個F未保留trace，續跑未重現，根因UNKNOWN。source隔離回退164PASS、重套279PASS，003/004基線雜湊保留。已先一致備份本機DB、graceful停原owner、隔離原聲線驗收後finally恢復8026（pid1507781），health及auth plan PASS。這是本機candidate載入，非全產品發布；未讀取私人聊天或修改原reference/舊cache。下一步同卡局部量測torch threadpool，無效就不改設定。

## 2026-10-08 — FIX-005 SDPA 最後驗收 checkpoint

同卡局部推論比較：CPU intra-op8／1／4無收益，REJECT調整；CUDA SDPA已核實SDK及實際四層配置，固定22字／seed／原聲線／512上限，正式暖未快取8.158／8.133s，對eager12.891／12.655s；63→59token、4.96→4.64s且wave hash不同，不能稱bitwise或人工語意相同。D35先補契約，production僅CUDA用SDPA、CPU保持eager，effective attention綁cache fingerprint；2個profile/cache反例先2FAIL後PASS。最終completion94PASS／10.14s；full-suite-final671PASS／5real_provider未選／3existing warnings／113.00s；mypy203(src+tests)、Ruff265 PASS。最終source reverse/reapply164PASS／281PASS，003004 baseline保留，patch f3ae57f230c7a9b7c806179dcfd99be94dbf05c3d4f7bd2eea2cb05f4b4382c5。

前次SDPA真probe被聊天中斷，僅2/3段完成、不算PASS；private8026亦停止，已用正式launch_companion入口恢復pid11535、healthPASS（interruption-recovery.json），未匯出環境密鑰。最後真probe加四production起訖hash，STALE_SOURCE拒PASS；以獨立supervisor21857執行，以免聊天中斷再次連同清理恢復被殺。續作先讀 ignored `.siro-data/verification/FIX-005-2026-10-08/controlled-check-service.json`、`sdpa-verified/result.json`、`detached-final-check.log`；若LOCAL_CHECK_RUNNING且pid仍活，勿啟第二GPU模型或擅自重啟8026，等驗收自行finally恢復。此時speed與人工語意gate未解除，card保持PARTIAL。不要把舊中斷JSON或基線PASS當成最後SDPA真機PASS。

### FIX-005最後結果（取代上方running checkpoint）

最後SDPA真Qwen／native Chromium probe PASS，四production起訖SHA一致、worker70941aca…匹配最後source回退；safe evidence real-voice-final.json。157字3段160/165/122正常EOS tokens，首次playing時只生成1/3段、最終ended才完成、fresh推論cancel/reap/no晚Audio、所有資源與temp cache cleanup PASS。cold短句24.582s；cache0.005001s獨列；warm故事22.327/22.927/16.945s、RTF約1.75；首段22.446s（原示例30.472）、gap10.053/3.719s（原23.289/6.387），仍未達體驗／SLO且人工語意聽驗NOT_RUN，不標DONE。最終671PASS／94completion／mypy203／Ruff265與source回退164/281見REPORT。

Supervisor已結束並finally恢復8026，pid22624，health與auth plan PASS；不是仍在驗收中，不需再啟第二服務。open_in_codex browser http://127.0.0.1:8026/ 返回queued，尚未確認使用者畫面已導航；避免使用file://畫面當產品入口。卡片PARTIAL／BLOCKED_BY_FIX語音體驗gate保留；005C無已提交句子契約未做，006理解、002搜尋、桌寵與自主技能各自未完成。下一個窄步驟針對已測talker瓶頸／可取消的受支持音訊chunk接入作實證，不換聲線、不擴Core；先完成合成首尾的人耳聽驗，不把EOS當語意正確。

## 2026-10-16 / Companion 正式入口修復與目前產品判定

使用者回報hello得到OfflineDemoModel固定句、Live2D替身；確認raw siro-gateway不讀.env.local／不選renderer，README/start/installer導向錯入口。正式scripts/start與新產生service現走既有launch_companion；--demo保留開發離線，首頁明示固定示範／替身與正確入口。實際8000已啟，DB先一致備份、schema14無migration，真Groq hello與真Haru視覺PASS；私人歷史／key未匯出。

真工具cat OS結果成功，但UI後續模型回覆失敗。隔離同目標兩次Groq200 completed；正式service重測安全status log確證429限流，因此不能宣稱整體可靠，早先未instrument失敗status仍UNKNOWN。新增transport只記數字status，不改HTTP exception/retry、不重播效果。

入口相關72PASS、最終operation5PASS、adapter43PASS、renderer相關38PASS、navigation/cancel32PASS（重疊不加總）；mypy268files/scopedRuff PASS。未跑本輪全套/remoteCI/真語音/桌面。詳 docs/evidence/COMPANION-STARTUP-2026-10-16/REPORT.md。

目前只是可測試的網頁整合候選，不是完整女兒產品；獨立透明VPet式桌面外殼／自由活動與動作尚未實作驗收，TTS速度、人耳與模型穩定性gate保留。RT013/015/summary限定DONE保留，不沿用舊DEFER作現在狀態。下一個產品工作應按既有plan做真native host與429有界復原，不能把頁面角色或新架構數量當成完成。

## 2026-10-16 / DESKTOP-VOICE-RECOVERY：native可啟動；語音GPU驗收BLOCKED

依owner明確三項授權，新增GJS/GTK3/WebKitGTK獨立透明桌寵（sandbox on、app-only XWayland、pixel input shape、單GtkApplication、聊天／拖曳／控制台／最小化／退出），正式8000目前有唯一native renderer；web作控制台不重複音訊。SDK desktop-only24fps及角色點擊聊天，動作仍Haru現有idle，無假走路；走路／坐下／可編輯leg rig仍未實作，整體桌寵卡PARTIAL。Manual mouse/DPI/fullscreen/native Wayland NOT VERIFIED，owner回饋pending。

原v1聲線首段24字自然切分、後段80、全文／worker／EOS／cache／取消保留；148CPU PASS、首段56→16僅工作量改善。GPU-onlygate拒絕執行：kernel7.0.0-38缺匹配NVIDIA modules（已裝只到-34）、nvidia-smi9、Torch CUDAfalse。官方signed module apt模擬成功，scripts/repair-nvidia-kernel已備妥，但sudo要求互動認證，owner需自行終端輸入密碼；沒有停SecureBoot／重開機／偽CPU benchmark。FIX005仍PARTIAL/GPU_DRIVER_BLOCKED，無新速度／人耳PASS。

429限定復原已接正式launcher：最多一個追加雲端request、Retry-After<=60秒同provider、pre-emission only、可取消等待，UI安全提示及terminal清理。真main/Core/SQLite marker effect僅一次再續作PASS；真loopback429→SSE200，daily/cap/again429仍明拒，不保證無限quota。Raw預設0不變。

最後offline全套2225PASS／5real-provider未選／3warnings（250.34s）；初次2220PASS/5FAIL為舊speech harness切片helper缺失，保留反例並修後full綠。final targeted26PASS（重疊不加總），mypy273files/Ruff/285format/Node/shell/SDKbuild PASS，23file source-onlyreverse＋byte比較PASS，保留前輪startup baseline及私人最新DB。實際native sourcehashmatch ready/alpha/sandboxtrue，3次有界avatar-only診斷不存聊天圖；隔離8028已停、8000與一個nativehost保留。詳 docs/evidence/DESKTOP-VOICE-RECOVERY-2026-10-16/REPORT.md。

下一步：owner完成signedGPUmodule修復後單worker真GPU首段/冷暖對照與人耳，再做真滑鼠／多monitor與正規角色活動素材。沒有把nativewindow或自動測試數字當成完整VPet／語音體驗DONE。無push／全產品release。

## 2026-10-17 / FIX-005：CUDA driver blocker解除，原聲線實播／取消PASS，速度仍PARTIAL

owner完成NVIDIA repair後，RTX3050Laptop 4GiB／driver595.99.02／Torch2.12.0+cu130／CUDA13可用。協調暫停managed8000，GPU-only current adapter/worker以全新temp cache測原v1聲線：cold22字20.104s；cache0.019s且bytes相等（不當暖推論）；舊planner56字21.648／21.694s，新首段16字7.781／10.109s。小樣本工作量對照，非統計或SLO。

再以CUA操作隔離current前端/Gateway/Qwen，固定合成157字故事三段真Audio playing/ended與完成時序PASS，cache全miss／正常EOS／一段預取／一個worker；cold首播18.789s、段間23.977／14.926s，長文仍不流暢。真停止按鈕同時停止首段、取消正在推論的第二段預取，0.517s owned cleanup/reap，後續87.527s無新Audio。第一段在檢查與click之間已生成，不誤稱取消時尚無音訊；未直接擷取paused屬性。故意abort HTTP在Uvicorn留下speech client disconnected CancelledError log，cleanup無錯；未當新regression或隱藏。

兩組worker已reap、temp cache刪除、isolated server/listener關閉，production source hashes起訖不變。恢復managed8000 healthy、原控制台reload已連線；舊nativehost graceful退出後用原launcher重啟一次恢復控制連線，單實例alpha/sandboxtrue、rendererowner=desktop，avatar診斷圖為真Live2D。原reference/私人DB/產品cache不變。本輪128PASS／2既有warnings、harness compile/Ruff、diff check PASS；沒有production改動，未重跑舊2225全套或cloudCI。生成WAV留ignored本機，未讀私人聊天／外送音訊。

FIX005保持PARTIAL：近即時速度FAIL、人耳待回饋；GTK/WebKit實播／桌寵滑鼠及多monitor、自由活動素材、長期soak／部署rollback未由這次in-app browser probe驗收。不是全產品DONE。詳 docs/evidence/FIX-005-first-segment-2026-10-17/REPORT.md。無push。

## 2026-10-19 — VRoid 原生重做候選：檔案／指骨蒙皮 LOCAL_VERIFIED，外觀／物理 PARTIAL

依使用者「從來一次」新建 VRoid 女性底模並實際存 `.siro-data/vroid/siro-restart-v1.vroid`，原生匯出 VRM 1.0。另拆出外套／短褲／靴與頭皮，保留獨立頭髮，新增跟隨 head 的深藍髮夾；分件版共8角色mesh、39,789三角面、128骨，雙手30指關節均有權重，57 morph targets／14預設表情／30 spring／28 collider保留。Blender真重新匯入、打包貼圖並渲染7張預覽；左手張指試驗561頂點移動，最大0.016109m，測後還原。ZIP 19 entries CRC／SHA256全驗，原生.vroid ZIP完整性通過。

交付 `.siro-data/vroid/siro-vroid-restart-v1.zip`（45,213,012 bytes），來源、分件VRM／GLB／Blend與預覽均保留。內搭／褲襪仍是身體貼圖，非獨立衣物；衣物物理及目標VRM播放器未跑，原生.vroid沒有後製髮夾。外觀未經使用者驗收，短褲長度／靴底／瀏海等與參考有差距。下一步先檢查外觀，再補獨立內搭及完整身體後驗物理。正式產品未改、未跑產品CI、未commit／push。[真實結果、失敗修復與限制](evidence/VROID-RESTART-2026-10-19/REPORT.md)。
