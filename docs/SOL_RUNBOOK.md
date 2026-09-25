# 使用 Sol 完成專案的操作手冊

本手冊的 Sol 指使用者在 Codex 選用的 GPT-5.6 Sol。它是開發執行者，和 SIRO 的對話模型分開；不必把 SIRO runtime 綁定 Sol，也不需要把全部規劃再交給另一模型重做。

這是一套降低遺漏、穩定接續工作的流程，不是對任何模型零錯誤的保證。驗收證據比「看起來完成」更重要。

## 1. 使用者第一次啟動

在 SiroV2 專案中選擇 Sol，貼上以下內容：

```text
請依本專案既有計劃開始實作 SIRO 2。
先讀 AGENTS.md、docs/STATUS.md、docs/SOL_RUNBOOK.md，
再讀 docs/TASKS.md 的 T00、它引用的 PLAN/CONTRACTS/EXPERIENCE/
SECURITY_PRIVACY/ACCEPTANCE。
先檢查 git status，保留現有變更。完成 T00 的實際產出與驗收，
完成後更新 STATUS.md 和證據，列出下一張可開始的任務。
日常可逆工程決策自行處理，沿用已選架構；遇到真正缺少帳號、硬體、
人格偏好或外部授權時才提出具體問題，並繼續不依賴該項的工作。
不要把規劃狀態當成產品實作完成。
```

不需要一次貼入所有文件。入口與任務卡帶出所需契約，避免模型每次重讀歷史對話。原分享連結僅作來源，後續進度以 repo 文件和實際 code 為準。

## 2. 一般續作

```text
繼續 SIRO 2。讀 AGENTS.md 和 docs/STATUS.md，核對目前程式與 Git 狀態。
完成下一張依賴已滿足的任務卡；依 docs/CONTRACTS.md 實作，
用 docs/ACCEPTANCE.md 的相關案例驗收。
每張卡完成後更新狀態、執行命令與結果、已知缺口、下一個具體動作。
如果外部條件卡住，標示 blocked-external，改做依賴已滿足的其他卡。
不重選架構、不以 mock 成功代替真實整合。
```

若希望連做一個階段，可補「連續做到 P2 gate，保留逐卡證據；遇到需要使用者資料的步驟才暫停該部分」。如果是新 task，仍在同一 repo 讀狀態，無需人工重新講完整故事。

## 3. Sol 每張任務卡的工作循環

1. **恢復上下文**：STATUS、task、契約、最近 diff；若文件與實作矛盾，先核查證據。
2. **說明範圍**：用一段話說要完成哪張卡、它解決什麼、要驗證哪個結果。
3. **確認外部介面**：新 SDK/provider/API 用官方文件確認，不猜 import 與參數。
4. **建立可驗證情境**：優先覆蓋契約、取消、資料一致性與新失敗模式；不為低風險文案改動造測試。
5. **實作最小完整切片**：真實流經該模組的輸入→結果，而不是只新增空 class。
6. **驗證**：跑必要 lint/type/unit/contract；受影響的 integration/real test 分開跑。
7. **檢查交付物**：沒有 TODO 代替核心功能，無 secret/大型資料混入，無不相關改動。
8. **保存進度**：STATUS、evidence、必要 ADR；說明下一步，保留可接續狀態。

## 4. 預計開發指令介面

下面是 T01、T34 應建立的統一入口，**在它們完成前不能假裝已存在或已跑過**。Sol 應先檢查檔案及 `--help`。

| 入口目標 | 作用 |
|---|---|
| `scripts/check` | 依目前存在的模組跑 lint/type/unit/contract；失敗非零退出 |
| `scripts/test-integration` | 開啟測試 broker/runtime、執行整合、清理 |
| `scripts/demo --profile mock` | 不依賴 key/GPU 的最小可展示閉環 |
| `scripts/start --profile companion` | 啟動指定 services，失敗可定位 |
| `scripts/stop` | graceful stop，清理工作程序 |
| `siro doctor` | 檢查依賴、配置、硬體、schema、service readiness |
| `scripts/benchmark --suite realtime` | 輸出有量測邊界的結構化結果 |
| `scripts/backup` / `scripts/restore` | 一致備份、指定目錄還原 |

實際命令參數在建立時固定到 README；不得每張卡重造不同入口。

## 5. 出錯時的提示詞

```text
本任務目前未通過驗收。請讀 STATUS 與最新 evidence，先重現錯誤，
列出最直接的根因證據，再做最小修復。保留原驗收門檻。
不要略過測試、吞掉例外、改成固定回傳成功、用 mock 取代原本真實整合。
完成後重跑失敗案例及受影響的相鄰案例，更新證據。
```

相同原因连续三次失敗：停下擴大重構，建立 `docs/evidence/Txx/blocker.md`，列重現步驟、已試方法、排除項、需要的最小資訊。若是架構不成立，先提 ADR 與受影響卡，不讓 fallback 靜默變成永久實作。這不代表任務完成。

## 6. 變更需求時的提示詞

```text
新增需求：[具體需求]。
請先對照 SOURCES 的需求矩陣，列出影響的契約、資料 migration、
任務依賴、驗收與現有功能。更新 DECISIONS 與 TASKS 後實作最小切片。
保留已完成成果，除非證據顯示它與新需求衝突。
```

小型可逆選擇記錄即可；跨平台/外部服務/付費支出等超出已有範圍時才需要具體決策。已獲授權的範圍不重複詢問。

## 7. 階段驗收提示詞

```text
請驗收 P[編號]，不是只確認檔案存在。
逐項對照 TASKS、CONTRACTS 與 ACCEPTANCE，執行可執行的案例。
產出功能→實作→測試證據對照，分 PASS、FAIL、BLOCKED-EXTERNAL。
檢查取消/背壓/重送/權限/資料持久化等跨模組行為。
缺陷先修；沒有真實證據的能力不可列為已完成。
```

## 8. 交接紀錄格式

```text
目前任務：Txx / 子步驟
已完成：功能與檔案
驗收：命令、exit code、mock 或 real、證據路徑
尚未驗證：原因和外部條件
決策：ADR 編號／維持既定基線
工作区：分支、commit、未提交內容（不包含 secret）
下一步：檔案/模組＋具體動作＋预期驗收
阻礙：需要使用者提供的最小資訊，或無
```

新對話開始，先按這份紀錄核查檔案，不假定前一輪所有敘述都正確。模型 context 可以消失，但 repo 內的任務、規格與測試證據必須足以恢復。

## 9. 全專案完成提示詞

```text
請進行 SIRO 2 v1.1 的最終驗收，使用 SOURCES 需求矩陣、
TASKS T00–T40 與 ACCEPTANCE A01–A24，核對每項真實證據。
重跑受最近變更影響的整合測試，確認 24 小時運行、真雙節點、
真語音/Live2D/設備、安裝、備份還原與回滾報告。
對未完成的外部條件清楚標示；不要提前宣告全部完成。
最後交付使用手冊、啟動方法、能力矩陣、已知限制與維護流程。
```
