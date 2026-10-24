# I02 情緒系統完成稽核

> **歷史快照（2026-10-24 標註）**：2026-09-28 的情緒系統稽核快照（此處 I02 指整合項目「角色與情緒」，不是 Companion CP-I02 發布與回退）。目前進度以 `STATUS.md` 為準。

日期：2026-09-28。範圍依 `RESEARCH_EMOTION_ARCHITECTURE.md` 的 E01–E07，以及「SIRO 自己的情緒與偏好」要求。`完成` 只表示已有實際整合證據；純介面、計畫或單元函式列為部分完成。

| 要求 | 狀態 | 權威證據 | 尚缺 |
|---|---|---|---|
| E01 持久化 emotion/mood/drive/coping/preferences | 完成 | migration 009/010；`test_affect_persistence.py` 跨重啟測試 | 無 |
| Appraisal 不由 LLM 任意指定 | 完成 | `AffectSystem` 接收 typed appraisal；`AffectCoordinator` 只處理 versioned events | 自由文字入口仍是保守詞彙規則，需持續擴充語意覆蓋 |
| Goal/action/readback 影響情緒 | 部分完成 | `action.result.v1`、`goal.transition.v1`；room/systemd/browser/process/file readback 測試 | 尚未有統一 goal lifecycle emitter；少數未使用 built-in wrapper 的第三方 executor 無事件 |
| SIRO 自有偏好影響情緒 | 完成 | `SelfConcern` 的 polarity × outcome value；整合測試以 identity-core 探索偏好產生正 valence | 長期隱含偏好仍需更多真人資料 |
| Owner 與 SIRO 偏好隔離 | 完成 | scope `owner`/`siro`；錯誤問句不寫入偏好；分開 prompt context | UI 尚無完整偏好編輯器 |
| Mixed emotion | 完成 | `emotion_activations` 保存所有超過門檻的 activation | 無 |
| PAD mood 與實際時間衰減 | 完成 | versioned time constants；elapsed-time restore；12 小時衰減測試 | 參數仍需真人校準 |
| Homeostatic drives | 完成 | 六項壓力、自然累積、verified regulation、30 天無飽和模擬 | 真實休息／探索 action 尚未全部有明確 satisfaction mapping |
| Coping 改變 planner | 完成 | 持久化 mismatch → repair → `AffectAwarePlanner` 選擇修正候選；hard gate 保留 | 無 |
| Drives 改變 attention | 完成 | `AffectDecisionLoop` 統一 attention 與 planner；無 attention 不規劃，cancel 強制 no-action | 無 |
| Relationship rupture/repair | 完成 | sourced immutable revisions；負面更新快於 repair；跨重啟測試 | 真人合理性校準 |
| Live2D 表情與抑制 | 完成 | owner distress、critical/public context policy 與測試 | 模型本身可用 expression 數量有限 |
| 語言 coping policy | 完成 | prompt 明定 repair、seek-information、problem-solve、support 行為 | 生成模型仍可能偏離，需真人與模型 eval |
| 語音韻律 | 完成 | `SpeechIntent` 與 renderer message 有 rate/pitch/energy；Live2D 與 fallback renderer 的 Web Speech API 實際消費三值；cancel 同步停止語音 | 作業系統可用語音種類會影響音色 |
| 演算法版本與重現 | 完成 | `siro-affect-cpm-1`、完整 configuration 寫入 appraisal、configuration/trajectory digest | 版本升級 migration policy 尚待第一次調參時驗證 |
| E07 30 天模擬 | 完成 | `affect-simulation-30d.json`：120 events、0 bounds、0 不當 anger、0 instant repair | 無 |
| E07 真人 longitudinal diary | 未完成 | 尚無真人日誌 | 至少 14–30 天 owner 使用資料與量表 |

## 現階段結論

核心演算法、持久化、主要輸入事件、單一決策入口、關係和呈現 policy 已形成閉環。現有產品程式沒有繞過 facade 的裸 planner 呼叫；未來工具迴圈以 `AffectDecisionLoop` 為唯一產品入口。尚不能宣稱整個 I02 完成，因為真人長期驗證沒有資料。
