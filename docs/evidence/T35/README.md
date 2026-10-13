# T35 v1.0 整合驗收

日期：2026-09-26｜狀態：BLOCKED-EXTERNAL（完整 v1.0 發布）

## 已通過的本機基線

- `scripts/check`：Python 128 passed、Rust 6 passed；5 個 external provider opt-in tests 因未設定允許旗標／key 跳過。
- T00–T34 的 L1/L2、Linux 限定 L3 與 simulator 證據各自保存在 `docs/evidence/Txx/`。T16 speaker
  真人打斷和 T24/T25/T34 的 Linux field/integration evidence 已存在。
- clean-data demo、backup/restore、release rollback、permission/action-ledger、cancel、secret scan 均有對應 task evidence。

## 未解除的 v1.0 發布阻礙

| 要求 | 狀態 | 為何不能宣告完成 |
|---|---|---|
| 24-hour soak | PENDING | 尚未連續運行 24 小時，沒有每小時 workload／故障資料。 |
| 真人 UX 三輪 | PENDING | 必須由使用者完成，不能由測試替代。 |
| 真實 HA/ESP32 room loop | PENDING | 僅有 protocol mock/simulator，A18 L3 未完成。 |
| 真實 cloud speech/model release profile | PENDING | provider tests 是 opt-in，正式成本與憑證未設定。 |
| Windows/macOS | UNSUPPORTED | 沒有對應實測主機。 |
| GPU profile | PENDING | 主機沒有可驗證 GPU runtime。 |

因此此 repo 不是 v1.0 release；所有已完成能力的範圍以 `STATUS.md` 和各任務證據為準。
