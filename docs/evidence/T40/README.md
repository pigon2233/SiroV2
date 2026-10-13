# T40 v1.1 完整基線發布稽核

日期：2026-09-26｜狀態：BLOCKED-EXTERNAL

## 已有可驗證基線

- T00–T34：各任務的 L1/L2、Linux 限定 L3 或 simulator/mock 證據依 `docs/evidence/Txx/`。
- Compute fabric L1：T36 node pairing/privacy/heartbeat/revocation、T37 bounded job lease/epoch、T38 hard-gated router 已有 deterministic tests。
- 完整本機檢查最後一次通過為 Python 131 passed、5 external opt-in skipped、Rust 6 passed，包含 T36–T38 的 deterministic tests。

## v1.1 發布阻礙

| 阻礙 | 需要的直接證據 |
|---|---|
| T35 v1.0 完整驗收 | 24-hour soak、真人 UX 三輪、真實 HA/ESP32、正式 provider profile。 |
| T39 | 第二台真實節點、LAN 斷網／恢復、epoch late-result、取消與 latency 證據。 |
| T40 24-hour distributed soak | 有效雙節點後的兩節點 workload、rollback、distributed walkthrough。 |
| 跨平台 | Windows/macOS 實測主機。 |

因此目前不可建立 v1.1 release，也不可將單機 deterministic tests 表述成分散式產品交付。解除後需重跑
A01–A24 受影響項、完整 `scripts/check`、T35/T39 演練及 rollback，再更新本稽核。
