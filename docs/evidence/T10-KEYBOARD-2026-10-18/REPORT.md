# T10-UI-01-KEYBOARD — 鍵盤略過導覽

Completion date：2026-10-18（Asia/Taipei）。**DONE / LOCAL_VERIFIED：只限鍵盤bypass切片**。T10-UI-01整體PARTIAL。

## Selected Task／Why selected

roadmap最新SETTINGS／DETAIL及D69搜尋皆已限定DONE；下一個依賴滿足的未完成產品範圍是T10-UI-01可及性。既有plan要求鍵盤／焦點，實際body從品牌與九頁導航開始，沒有略過重複導覽的入口；本輪拆原keyboard要求的有界bypass子切片，沒有新增RT號／重排架構／宣稱全可及性完成。RI與平台／發布門檻保持。

## Before coding／Actual runtime path

原showPage已以hidden＋inert區分工作頁、heading皆tabindex=-1、已有focus-visible；主landmark已存在，但缺skip入口。新path：body首anchor → onclick preventDefault → 從現有visible page取heading → focus；不存在heading時focus既有main。刻意不呼叫showPage／navigate／renderGoalTasks，因此不清draft／重建task卡／寫history或發request。

MUST NOT CHANGE：Core／Gateway／DB／schema／wire／config／授權、現有導航與session／single writer、模型／語音／body／desktop／WSL及舊dirty改動，全部保持。本卡只改HTML，無新的後端／依賴。

## Implementation summary

第一個Tab可到「跳到主要內容」標準anchor。平時以CSS移到畫面外，focus後顯示於左上方，沿原focus outline；按Enter直接focus目前工作標題，包括#/tasks/<UUID>。main補tabindex=-1供fallback。使用href=#main-content作標準目標，但activation preventDefault，避免原hash router誤切回chat。

## Tests run／Regression results

| 層級 | 結果 |
|---|---|
| 新專項test_frontend_keyboard_skip.py | 3 PASS／0.19s；原版3 FAIL／0.21s。production HTML script＋真body階層，synthetic DOM：九頁heading正確、preventDefault、零history/request/socket/timer、draft不變；detail UUID與已顯示card物件不變；缺heading回main |
| 相關logic unit／integration | `pytest -q tests/integration/test_frontend*.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/integration/test_goal_task_api.py tests/integration/test_goal_task_loop.py`：**512 PASS／3既有dependency warnings／34.12s**，含新3例，不相加 |
| 桌寵相容 | `pytest -q tests/integration/test_desktop*.py`：**69 PASS／3既有warnings／9.11s**；不是實體桌寵完整驗收 |
| 靜態 | 新test及rollback verifier Ruff／format PASS，mypy兩檔PASS；實際inline script node --check及git diff --check PASS。本輪無Python production改動，未重新聲稱全repo mypy／scripts/check通過 |
| 真browser | CUA實際Tab／Return：tasks第一Tab focus skip，截圖確認入口可見；Enter focus tasks-heading，路由不變。直接detail→reload後再Tab／Return，focus同heading且UUID不變。4份AX／3張原始JPEG已保存，從檔案重驗focus尾段及route header一致 |
| 真main／runtime | 隔離正式main／Core／SQLite／owned Rust；navigation檢查read0，服務log無goal mutation／kill-switch PUT／speech request。原fixture renderer明示placeholder、無真provider／TTS／私人資料。所有owned child／temp／tab正常清理 |
| 回退 | 含baseline commit、dirty before／after與標準checksums的[package](rollback/README.md)。當前checkout rollback --check PASS；真正rollback／reapply只在自有temp執行，逐byte回到原本含search／detail／settings的檔案，latest-data sentinel保持，checkout不寫 |

本輪沒有新增skip／xfail或抑制warnings。[receipt](product-receipt.json)的browser_acceptance=PASS來自本輪CUA與保存觀測；server_fixture_drives_browser=false單獨說明server helper不操作browser，不再把server預設NOT_RUN當browser結論。current source與實際fixture host source hash相同。

## Acceptance criteria

| Criterion | 判定／evidence |
|---|---|
| 第一Tab到可見入口 | PASS；01-first-tab.ax.txt焦點尾段與[截圖](01-first-tab.jpg) |
| Enter到目前工作heading | PASS；02-enter.ax.txt；九頁專項loop全部檢查 |
| detail保留UUID／不重建snapshot | PASS；04-detail-enter.ax.txt header與03相同、focus heading；production JS case保原card物件 |
| 不改hash/history、零請求／tool/audio效果 | PASS；synthetic calls/history/timer斷言＋真backend read0與無相關mutation／speech logs |
| heading缺失有fallback | PASS；專項動態移除heading後main焦點且tabindex=-1 |
| 舊功能相容與可逆 | PASS；512／69 regression、source-only精確回退／重套 |

## Remaining issues／Architecture deviations

本切片無已確認缺陷或regression，architecture deviations：NONE。這不是全可及性驗收：全頁窄窗／200%縮放／對比、讀屏、真人WSLg／實體IME與全部日常流程仍需既有T10計畫驗收；真Live2D／聲線／GPU／設備／soak與正式部署rollback未於本輪驗。完整scripts/check與全repo型別未跑，不列PASS。

尚未驗項不阻擋本限定keyboard bypass交付，也不被本卡DONE解除。未改另一台運行設定、未push／deploy／重啟私人8000服務；不自動啟動下一卡。

## Files changed／Rollback method

production：src/siro/services/presentation/static/index.html。新增tests/integration/test_frontend_keyboard_skip.py。文件：D72、roadmap、STATUS、TASKS、Interface plan、Regression baseline與本證據。原D68／D69／D70／D71修改保持。

只撤本卡[rollback.patch](rollback/rollback.patch)／新test與文件增量，保留最新資料與先前功能；不git checkout HEAD、不DB restore。未來若source漂移先審新diff，不硬套舊package。正常檢查與temp驗證指令見README。
