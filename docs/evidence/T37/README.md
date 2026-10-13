# T37 驗收證據

日期：2026-09-26｜結果：PASS（L1 + loopback L2 simulator）

`JobLeases` 驗證輸入上限、lease retry、cancel、epoch fencing 及 late/duplicate result 拒絕。
`siro-compute-worker` 提供 bounded JSON-lines TCP executable；integration 驗證 ordered stream、job/epoch/
SHA-256 result、temporary artifact cleanup 與 `crash_after_chunk` fault。memory commit 由 Core accept fence 控制。
