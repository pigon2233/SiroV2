# T10-UI-01-SETTINGS — 設定與權限用語

Completion date：2026-10-18（Asia/Taipei）。結果：**DONE / LOCAL_VERIFIED，僅本切片**。整體T10-UI-01仍PARTIAL。

## Selected Task／Why selected

DETAIL已獨立驗證無本卡必修缺陷，原RT-001–015維持scoped DONE；roadmap最前面的未完成且依賴滿足項仍是T10-UI-01。其原plan明列設定用語，在D69搜尋與D70詳情之後，選本有界切片；不重開RT或擴RI-003–006的隔離／發布門檻。

Discrepancy：設定入口宣稱可查看目前模式，實際permissions頁沒有授權模式；三個按鈕仍是cloud/tools/microphone: ON/OFF。本卡補呈現，不變更授權或功能實作。

## Before coding／Implementation summary

既有path：control snapshot→renderSnapshot→button.onclick→authorizedFetch PUT /v1/kill-switches/{name}→GatewayState／原控制服務→reload／新snapshot。三個真實keys只有cloud／tools／microphone。確認Gateway原tools停用會進既有foreground cleanup，cloud與microphone亦有各自guard；本卡不改它們或假稱更廣泛外送控制。

production只改index.html：新增permissions的mode paragraph，與computer共用一份由authorization_mode產生的說明；按鈕改「雲端功能／電腦與工具操作／麥克風輸入：已開啟／已關閉」，title說明按一下的下一操作；增加允許與實際操作權限有別的說明。未知key仍以textContent顯示原key，Object.hasOwn避免繼承屬性當成標籤。沒有新增模式切換或保存設定。

MUST NOT CHANGE全部保持：Core／Gateway／DB／wire／schema／state／config、預設full／safe、API key名稱／PUT／enabled反轉／session／原reload與取消策略、模型／voice／Live2D／desktop／WSL。精確原button.onclick source在前後均存在。沒有unrelated refactor、沒有新增依賴；D68／D69／D70舊dirty內容保留。

## Tests run／Regression results

| 層級 | 實際結果 |
|---|---|
| 相關logic/unit及integration regression | `pytest -q tests/integration/test_frontend*.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/integration/test_goal_task_api.py tests/integration/test_goal_task_loop.py`：最終 **509 PASS／3既有warnings／34.88s**。包括production HTML script／synthetic DOM與transport、真Core／SQLite及既有callback邊界；不是509次真瀏覽器操作 |
| supported Python3.12相容 | 隔離locked/all-groups環境，既有navigation/control/gateway **64 PASS／1 warning／4.61s**；與509重疊，不相加。只建立自有type-env，原.venv與另一台部署保持 |
| 靜態 | Ruff check src tests PASS；format 287 files PASS；實際inline JS node --check PASS；git diff --check PASS |
| 全src/tests型別 | 指定隔離Python3.12 executable、`--no-incremental`後 **mypy 287 files PASS**，未改ignore或檢查規則。原本Python3.14 .venv缺faster_whisper，及第一次3.12檢查均報whisper_worker既有import-not-found／unused-ignore；完整診斷保留。鎖定安裝後確認module存在，再以明確interpreter／乾淨檢查通過，未修改whisper_worker或deps/lock來消音 |
| 真browser task-specific | CUA→目前source隔離main，3步AX／JPEG與斷言已保存：permissions初始中文labels／title／mode、按tools一次後reload顯示已關閉、computer同來源mode。完整[steps](browser-steps.json)與[receipt](product-receipt.json)均PASS，重新從檔案核對文字與JPEG格式 |
| 真HTTP readback／runtime | 該UI click僅一筆PUT /v1/kill-switches/tools（200）；GET snapshot確認tools=false、cloud=false、microphone=false、mode仍full。切頁後Rust reads=0。原callback byte-equivalent檢查PASS；非用mock推定按鈕接線 |
| 回退 | [package](rollback/README.md)含原Git commit／本輪dirty before／after／標準checksums；當前checkout正常rollback --check PASS、temp rollback/reapply精確bytes PASS。另實測先撤SETTINGS再撤DETAIL、依序重套，最終source完全相同；不改歷史DETAIL package |

低影響文字與狀態投影重用既有測試及真瀏覽器驗收，沒有新增逐字鏡像實作測試。第一次相關509 PASS（33.81s）不是最終source，加入未知key繼承屬性guard後重新完整跑到上列509 PASS。沒有skip／xfail，warnings不改為成功或抑制。

真browser使用原prepared renderer placeholder、合成帳戶／空task資料及真main／SQLite／owned Rust。沒有真provider／TTS呼叫、私人對話、開啟麥克風或雲端。三步影像是自有測試頁原始JPEG；receipt明確區分server-only fixture與CUA verdict。server child／temp／tab均已清理。

## Acceptance criteria

| Criterion | 結果／證據 |
|---|---|
| 三個中文功能名稱與狀態 | PASS；01-permissions AX／JPEG，原snapshot消費 |
| 下一操作說明隨enabled切換 | PASS；tools開啟→關閉的兩份AX title對應相反動作；未開啟實體microphone或cloud |
| permissions與computer共用原mode | PASS；同一authorizationDescription及01／03實際畫面；PUT後full值未變 |
| 原wire／權限／callback語意保持 | PASS；callback原文字未變、真PUT一次／三flags與mode回讀、509 regression |
| 導航沒有額外tool effects | PASS；UI操作後read0、API log只有一次明確tools PUT；原導航suite |
| 前功能可保留並回退 | PASS；精確本輪dirty baseline、單步與DETAIL串接source-only回退／重套 |

## Remaining issues／Architecture deviations

本切片無已確認未解缺陷或regression，architecture deviation：NONE。既有reload與mutation error-handling政策保持，本卡不重設開關協定；未知額外key未翻譯為未宣告能力。

整體T10仍有完整可及性／真人流程；真Live2D／WSLg實體IME／聲線／GPU／設備／soak／正式部署回退仍是原各卡門檻。本輪未跑整條scripts/check或聲稱另一台電腦已驗，未push／deploy／重啟私人8000服務。本slice完成不表示全部SIRO完成。

## Files changed／Rollback method

production：src/siro/services/presentation/static/index.html。文件：D71、roadmap、STATUS、TASKS、Interface plan、Regression baseline與本證據。沒有改既有tests、後端／依賴或前幾輪檔案內容。

回退只使用本卡[rollback.patch](rollback/rollback.patch)撤HTML增量，before已含D69搜尋與D70詳情，不用git checkout HEAD、不restore DB。verify.py在temp演練，不對目前checkout寫入；後續若source已變，需按README順序或先審查新diff，不強套歷史package。完成後停止，下一卡未開始。
