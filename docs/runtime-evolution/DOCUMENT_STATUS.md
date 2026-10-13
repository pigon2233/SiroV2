# Document status

Phase 1 文件稽核已完成；Phase 2 設計已於 2026-09-30 經使用者授權完成，implementation 未開始。這不等同 SIRO 功能驗收完成。可信範圍是當前 source/caller 地圖與本次 automated baseline；真硬體、provider、畫面、24h 與第二節點仍未驗證。

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
- RUNTIME_EVOLUTION_ROADMAP.md：RT-001–015 小型任務卡，全部 PLANNED。

Phase 1 報告保持當時的歷史敘述；本頁是最新文件階段狀態。此次只改文件，未完成或執行任何 RT 任務；實作應從 RT-001 開始。
