# Document status

（2026-10-24 更新）Phase 1 稽核與 Phase 2 設計（2026-09-30）已完成，RT-001–015 均已實作（RT-001–014 DONE；RT-011/013/015 為有界產品切片 DONE，見 RUNTIME_EVOLUTION_ROADMAP.md 各卡 Status）。全專案任務現況：T/RT/CP 卡除 T35／T39／T40（需真硬體、第二台機器、24 小時運行）外均已完成，I01 已由 owner 於 2026-10-24 實機試用驗收；總覽見 docs/STATUS.md 頂部。Phase 1 各報告是當時（2026-09-30 前）的歷史快照，只保留設計脈絡與證據，結論不代表現況。真硬體、真 provider、24h 與第二節點仍未驗證。

| 文件 | 狀態 / 用途 |
|---|---|
| CURRENT_ARCHITECTURE_AUDIT.md | 結論、證據邊界、freeze zones、Python/Rust、NOW/NEXT/LATER |
| RUNTIME_CALL_GRAPH.md | 正式入口、獨立程序、caller/callee、transport |
| DATA_FLOW.md | 輸入、state ownership、持久化、output consumer |
| CAPABILITY_MATRIX.md | 要求的能力逐組分類；有相同 caller 的能力同列 |
| ROADMAP_RECONCILIATION.md | T00–T40 全 41 項對照；未修改原卡 |
| DEAD_OR_UNUSED_CODE.md | detached/legacy/duplicate 候選；未刪除 |
| ARCHITECTURE_FRICTION_MAP.md | 12 個問題，source inference 與重現分開 |
| HERMES_GAP_ANALYSIS.md | 官方固定 commit 參考，15 個 concept；不採依賴 |
| REGRESSION_BASELINE.md | 實際命令、FAIL/SKIP、真實驗證缺口 |
| RISK_REGISTER.md | production 與 audit confidence 風險 |
| SOURCE_INVENTORY.json | 來源 digest、symbols/line、imports；補充證據 |

## Phase 2 設計文件

- RUNTIME_EVOLUTION_SPEC.md：責任、run/message/tool/state/lifecycle 契約與提議量測門檻。
- COMPATIBILITY_PLAN.md：舊API、配置、schema、音色、授權與回滾相容。
- MIGRATION_PLAN.md：G0–G5 分段、故障注入、切換與停止條件。
- RUNTIME_EVOLUTION_ROADMAP.md：RT-001–015 小型任務卡，設計時全部為 PLANNED，現已全數實作完成（以 roadmap 各卡 Status 為準）。

Phase 1 報告保持當時的歷史敘述；本頁是最新文件階段狀態。（舊版此處寫「實作應從 RT-001 開始」，已過時，2026-10-24 更正。）
