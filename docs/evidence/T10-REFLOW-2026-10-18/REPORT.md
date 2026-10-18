# T10-UI-01-REFLOW — 窄窗與 200% 等效 reflow

Completion date：2026-10-18（Asia/Taipei）。**DONE / LOCAL_VERIFIED：只限窄窗／200% 等效寬度的水平 reflow 切片**。T10-UI-01 整體 PARTIAL。

## Selected Task／Why selected

T10-UI-01 是 roadmap 第一個依賴滿足的未完成產品項。其 Scope 依序列「窄窗／200% reflow、對比、鍵盤、錯誤／等待／取消狀態」；KEYBOARD／SETTINGS／DETAIL／搜尋已限定 DONE，reflow 是下一個尚無證據的有界子項，Acceptance 明列「320／375／414／768 及 200% 等效 reflow 不遮必要控制」。本卡不含對比、讀屏、真人流程或 Live2D。

## Before coding／Actual runtime path

- 現況：`static/index.html` 已有 1100／900／480px 斷點，窄窗時側欄改為頂部換行導覽、toolbar 換行、角色與對話堆疊。
- 風險點：`html, body { overflow-x:clip }` 會把超出視窗的內容**直接裁掉而不是可捲動**，所以溢出不會出現水平捲軸，肉眼與 scrollWidth 都不易察覺；全域 `button { white-space:nowrap }` 使資料決定文字的按鈕無法換行。
- 量測方法：production HTML 以 Chrome（Playwright，本機 `google-chrome`）開啟，六種 viewport × 九頁＋單任務詳情，逐一檢查所有可見元素是否超出視窗邊緣且不在可捲動容器內。200% 等效：1280×800→640×400、1920×1080→960×540 CSS px。
- 壓力資料：全部合成，透過 production 的 `renderGoalTasks`／`renderCapabilities`／`renderSnapshot`／`renderToolProposal`／`appendMessage`／`refreshMemories`（stub `productRequest`）渲染長中文、長 URL、512-byte 路徑、未知 kill-switch key。
- MUST NOT CHANGE：Core／Gateway／DB／schema／wire／config／授權、導航與 session／single writer、任何 JS 行為、模型／語音／body／desktop／WSL 與既有未提交改動。

## 量測結果（修改前）

| 情境 | 結果 |
|---|---|
| 預設內容 60 組 | 0 溢出；每頁皆可達、detail heading 正確 |
| 合成長內容 60 組 | 唯一缺陷：權限頁 `#switches` 中未知長 key 的開關按鈕超出視窗（320／375／414 寬時右緣達 459–532px），被 `overflow-x:clip` 裁掉，控制項文字看不全。[修正前截圖](before-320x568-permissions-stress.jpg) |
| 頁面標題 nowrap | 只有人為塞長標題才溢出；實際 `pageTitles` 皆為固定 ≤7 字，不是缺陷，未修改 |

## Implementation summary

`index.html` 新增一行 CSS：`#switches button { max-width:100%; white-space:normal; overflow-wrap:anywhere; text-align:left; }`。只作用於唯一由後端資料決定標籤的按鈕群組；三個已知開關標籤仍是單行，外觀不變。未改全域 button 規則（避免非換行 flex 列如「送出」被壓成直排）。沒有 JS／API／DOM 結構變更。

## Tests run／Regression results

| 層級 | 結果 |
|---|---|
| 新 `tests/integration/test_frontend_reflow.py` | 2 PASS（~7–11s）。原版：base PASS、stress FAIL（權限頁開關溢出）。另驗所有導航零 `/v1/` request |
| 相關 frontend／gateway／main／goal | `pytest -q tests/integration/test_frontend*.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/integration/test_goal_task_api.py tests/integration/test_goal_task_loop.py`：**514 PASS／3 既有 warnings／60.87s**（含新 2 例） |
| 桌寵相容 | `pytest -q tests/integration/test_desktop*.py`：**69 PASS／3 既有 warnings** |
| 靜態 | 新測試 Ruff check／format、mypy PASS；`git diff --check` PASS。CSS-only，inline JS 未變 |
| source-only 回退 | 移除該行 CSS→新 stress 測試 FAIL；還原後 `cmp` 與修改後檔案逐 byte 相同，2 PASS |
| 修改後量測 | [measurements-after.json](measurements-after.json)：base 60／stress 60 組，0 溢出 |

截圖（合成資料）：[修正前 320 權限](before-320x568-permissions-stress.jpg)、[修正後 320 權限](after-320x568-permissions-stress.jpg)、[320 任務詳情](after-320x568-tasks-detail-stress.jpg)、[320 對話](after-320x568-chat.jpg)、[640×400 記憶](after-640x400-memory-stress.jpg)、[768 設定](after-768x1024-settings.jpg)。

## Acceptance criteria

| Criterion | 判定 |
|---|---|
| 九頁與 detail 在 320／375／414／768 可達 | PASS（60 組，heading／page 斷言） |
| 200% 等效（640×400、960×540）不遮必要控制 | PASS（水平方向） |
| 長中文／長路徑／未知 key 不被裁切 | PASS（修正後） |
| 導航不觸發 request／不改行為 | PASS（零 `/v1/` request；CSS-only） |

## Known limitations

- 以 file:// 預覽模式量測 production HTML（控制項 disabled、模板佔位字未替換、無後端）；版面 CSS 相同，但未在真 main／SQLite 服務頁重跑。
- 只驗水平 reflow。窄窗 sticky toolbar 在 320×568 佔約 25% 高度、對話區為固定高度內捲動，仍可用但未做真人可用性評估；未測真瀏覽器縮放 UI、文字間距（WCAG 1.4.12）、讀屏、對比、真 Live2D／WSLg／WebKit 桌寵視窗。
- 合成 renderer／預覽不代證真角色或語音；full `scripts/check`、正式部署 rollback NOT_RUN。

## Rollback

只撤 `index.html` 的一行 `#switches button` CSS 與新測試／本目錄文件；無 DB／migration／部署。先前 KEYBOARD／SETTINGS／DETAIL／搜尋／D68 改動不受影響。Baseline commit `bd63f28`；修改後 index.html sha256 `fdaee13ace9c55513bf0bee0b0efcf4111f478a7ae85f0aae620462e73ae5f79`。
