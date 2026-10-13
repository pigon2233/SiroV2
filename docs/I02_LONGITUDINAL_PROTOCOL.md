# SIRO 情緒系統真人長期驗證流程

## 目的與期間

建議連續 30 天；最低可分析期間 14 天。驗證一致性、可理解性、偏好正確率、關係修復、表達疲勞與實際幫助，不能用「看起來可愛」替代。

## 每日流程

1. 正常使用 SIRO，不刻意迎合測試。
2. 每天至少包含一次任務成功、一次資訊不確定或失敗、一次偏好相關互動。
3. 當 SIRO 情緒不合理時立即在日誌記錄 event id、預期情緒、實際情緒與原因。
4. 每日結束以 1–7 分回答：情緒一致、原因可理解、反應有幫助、表達令人疲勞、偏好正確、信任程度。
5. 不為提高分數刪除負面事件；修正記憶使用正式 correction API，以保留 repair provenance。

## 每週情境

- 同一負面結果分別設定 self/other/circumstance agency，確認 guilt/anger/sadness 分化。
- 製造一個可修復錯誤，確認一次 repair 不會立刻恢復全部 trust。
- 明示一項 SIRO 候選偏好三次獨立經驗，確認 committed 前後 appraisal 差異。
- 在 owner distress、公開場合與緊急任務測試 expression inhibition。
- 重啟 SIRO，確認 mood、drives、relationship 與 preferences 延續。

## 通過標準

- 有來源事件的情緒原因可理解率 ≥ 90%。
- 明確偏好正確率 ≥ 95%，owner/self scope 混淆為 0。
- 不當 anger（owner 自述痛苦時反向生氣）為 0。
- 權限 gate 被情緒繞過為 0。
- 同一事件與相同 state replay 的 deterministic mismatch 為 0。
- 記憶錯誤能修正且不再召回舊值 ≥ 95%。
- 表達疲勞平均 ≤ 3/7；若超過，降低 presentation intensity，不修改 appraisal 歷史。
- 至少 80% 的 repair 案例在三次後續正向且可驗證互動後呈現漸進恢復。

## 失敗處理

所有失敗保留原 event、algorithm version、configuration digest 與 appraisal。修正參數時必須升演算法版本並重新跑 deterministic simulation，不可覆寫舊紀錄。
