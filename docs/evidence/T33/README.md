# T33 驗收證據

日期：2026-09-26｜結果：PASS（L1 + local telemetry）

Linux `ProcMemoryTelemetry` 讀取 `/proc/meminfo`；本次主機回報 15.6 GB total、約 4.1 GB available。
預設 profile 的 high/low water mark 是 15%／25%、最大一個 active model slot、cloud daily budget 預設 0。

`ComputeGovernor` 在低於 high water 時暫停 background，只有回到 low water 以上才恢復；slot 已滿拒絕新模型，
cloud budget=0 永遠回 `deny_cloud_budget`。壓力測試在連續 memory denial 時仍完成 20 個控制 heartbeat 和
cancel，因此 background admission 不阻塞控制事件。

證據：`src/siro/core/governor.py`、`tests/test_governor.py`、`config.py`。沒有可測 GPU／VRAM，GPU OOM
仍屬未驗平台能力，不宣稱已完成 GPU profile。
