# SIRO 2 規劃完成度稽核

> **歷史快照（2026-10-24 標註）**：2026-09-23 的規劃完成度稽核快照（只證規劃交付）。目前進度以 `STATUS.md` 頂部「狀態總覽」為準。

稽核日期：2026-09-23。範圍是「提供一份足以讓 Sol 按階段實作整個 SIRO 2 的完整規劃」，不是產品程式完成。本文件逐項證明規劃交付，不使用未執行的實作或未取得的硬體作證據。

## 1. 規劃交付需求

| 規劃要求 | 權威證據 | 判定 |
|---|---|---|
| 保留原對話完整目標 | SOURCES U01–U14 | 已覆蓋 Bridge、陪伴、電腦、技能、設備、進化、效能及多機 |
| 定義完成邊界 | PLAN §1、v1.0/v1.1、研究 R 系列 | 已區分產品、研究與非意識承諾 |
| 定義架構與 ownership | PLAN §3–4、CONTRACTS | 已定程序、核心模組、資料與 transport 邊界 |
| 解決舊 Bridge 風險 | PLAN §7、CONTRACTS §3–5、ACCEPTANCE §4 | 已有 single writer、分流、取消、背壓與回歸場景 |
| 定義人格、記憶與主動性 | PLAN §6、CONTRACTS §6、TASKS T17–T20 | 已有狀態、來源、Dream、目標與抑制規則 |
| 定義語音與 Live2D | CONTRACTS §4–5、TASKS T11–T16、A07–A09 | 已有 PoC 停損、媒體 owner、口型與真機 gate |
| 定義完整電腦控制與 skill | PLAN §8–9、CONTRACTS §7、T21–T32 | 已有能力分級、grant、worker、更新/回滾 |
| 定義智慧環境與視覺 | CONTRACTS §8、T24/T26–T29、A18 | 已有 capture/analysis、設備模型、MQTT/HA/ESP32 閉環 |
| 定義效能與分散式算力 | PLAN §10、CONTRACTS §9、T33/T36–T40、R01 | 已區分 Governor、task routing 與切層研究 |
| 定義使用者端流程 | EXPERIENCE | 已有 setup、日常、權限、記憶、設備、錯誤與畫面入口 |
| 定義安全與資料生命週期 | SECURITY_PRIVACY、A04/A11/A14–A24 | 已有 trust zones、威脅、分類、retention、kill switches |
| 任務可依賴順序執行 | TASKS T00–T40 | 每卡有依賴、輸入、步驟、產出、驗收；程式檢查無 dependency cycle |
| 驗收能證明而非自評 | ACCEPTANCE A01–A24 | 已分 L1/L2/L3、SLO、真機、長時間運行與 UX 評分 |
| Sol 能跨對話續作 | README、AGENTS、SOL_RUNBOOK、STATUS | 已有首次/續作/除錯/變更/交接提示詞和單一進度來源 |
| 研究引用不誇大 | SOURCES、PLAN §10.3 | 已區分 GPipe、Switch、Mensa、EdgePipe 與工程推論 |

## 2. 文件一致性證據

`docs/evidence/planning-check.json` 由本機檢查生成，驗證本地 Markdown 連結、code fences、T/R/A identifiers、任務必要欄位、依賴循環、交叉引用與行尾空白。這只能證明文件結構一致，不能證明未來程式功能。

## 3. 仍需在實作期間決定的項目

完整規劃允許把只有真實環境才能決定的值放進 T00/T11 等 discovery gate，但必須給預設、責任與停損：

- 目標主機和 OS：T00 盤點；Linux 為第一實測基線。
- Provider、花費及資料外送：mock 預設，T07 依使用者提供條件接入。
- AIRI 是否能作外部身體：T11 最多兩個工作單元完成 PoC/退出決策。
- Live2D/聲音資產：需合法資產，未提供時不能完成 L3。
- ESP32/HA/第二節點：先 simulator，T27–T29/T39 需要實體證據。
- 精確 latency/resource 門檻：已有初值，T00/T33 依指定硬體校準並留下 ADR。

這些是有 owner、時間點和驗收的實作輸入，不是規劃遺漏。Sol 不應因此停下所有其他任務。

## 4. 完成結論

規劃交付已涵蓋需求、邊界、架構、契約、資料、安全、體驗、任務依賴、驗收、研究界線和跨對話執行方法。規劃狀態可標為 COMPLETE；產品狀態維持 NOT IMPLEMENTED。下一個工作屬於實作 T00，不能把它混入「規劃是否完整」的判定。
