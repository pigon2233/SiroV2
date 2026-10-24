# SIRO 2 全面稽核（2026-09-26）

> **歷史快照（2026-10-24 標註）**：2026-09-26 的稽核快照。其後狀態以 `STATUS.md` 頂部「狀態總覽」為準；T10 之後的整合稽核見 `runtime-evolution/`。

## 稽核範圍

本次從 `AGENTS.md`、README、TASKS、ACCEPTANCE、STATUS 逐項核對到實作、測試、證據目錄、Git 狀態與
secret hygiene。完成判定以任務卡列出的步驟、產出和驗收為準，沒有把單元測試通過等同整張任務完成。

## 結論

| 範圍 | 判定 | 說明 |
|---|---|---|
| T00–T19 | 維持既有 DONE／限定層級 | 每張卡有 evidence；完整 local gate 覆蓋目前實作。外部 provider 測試仍為 opt-in。 |
| T20 | DONE (L1)，L3 PENDING | 合成 replay 已有；真人長期主動性體驗未驗。 |
| T21–T26 | 維持既有 DONE／限定平台 | Linux、本機 integration 或 simulator 範圍已清楚標示。 |
| T27–T29 | DONE（simulator/mock），硬體 L3 PENDING | ESP32、真 Home Assistant sensor/actuator 尚未驗。 |
| T30 | DONE (L1 + SQLite integration) | 候選維持 review-only。 |
| T31 | DONE (L1 isolated workspace) | 修正 workspace cleanup 報告，並移除 proposal 自帶任意驗證命令的權限。 |
| T32 | DONE (L1 isolated release) | 補上資料庫 rollback restore 與 activate 中斷 fault test；實際執行要求停止其他 DB writer。 |
| T33 | DONE (L1 + local telemetry) | 未宣稱缺少的 GPU profile。 |
| T34 | DONE (L1 + Linux L2 A22) | 稽核後補齊 locked install、user units、log retention、graceful in-flight state 與 DB+settings restore。 |
| T35 | BLOCKED-EXTERNAL | 缺 24-hour soak、真人 UX、真 HA/ESP32、正式 provider profile、GPU profile。 |
| T36 | DONE (L1 + loopback L2 simulator) | 稽核後補持久設定、完整 resource heartbeat 與假雙節點 integration。 |
| T37 | DONE (L1 + loopback L2 simulator) | 稽核後補 worker executable、stream/cancel/artifact cleanup、結果校驗與 fault simulator。 |
| T38 | DONE (L1 + loopback A23 L2 simulator) | 稽核後補 location hard filter、latency/cost、decision trace、校準器及 A23。 |
| T39–T40 | BLOCKED-EXTERNAL | T39 要第二台實機；T40 依賴 T35/T39。 |
| R01 | BLOCKED-EXTERNAL | 缺適合推論的真雙節點。 |
| R02 | RESEARCH-DONE (synthetic) | 固定 seed 的合成消融只支持「目前不調整」，不支持產品效益推論。 |
| R03 | RESEARCH-DONE (limited spike) | translator、相容矩陣、工時比較與延期 ADR D11 已完成。 |

## 本次修正

1. T31：`workspace_removed` 改為反映實際 cleanup；驗證命令從不可信 proposal 移到可信任 verifier 設定。
2. T32：last-known-good 記錄對應的 SQLite snapshot；rollback 驗證並恢復資料後才切版本；加入 activate
   中斷測試。
3. T34：`scripts/start PID_FILE` 現在建立、清理 PID file 並轉送 TERM，可與 `scripts/stop PID_FILE` 配對。
4. README、STATUS、T34/R03 evidence 改正過度宣稱，新增 T36–T38 的部分完成證據。

## 尚存風險與下一順序

1. 外部條件到位後執行 T35 的 24 小時、真人 UX、真 HA/ESP32 與正式 provider profile。
2. 取得第二台真實節點後執行 T39，最後才可做 T40。

## 儲存庫狀態

工作樹仍有大量未提交變更；本次沒有 commit。`.env.local` 由 `.gitignore` 的 `.env.*` 規則排除，tracked
files 未找到 Groq `gsk_` key。發布或交接前仍應先整理 commit，避免把多個任務的改動混在同一提交。
