# T18 驗收證據

日期：2026-09-24

已完成：

- migration 006 的 consolidation run/output 與 trait projection。
- 每批最多 100 個獨立 source、預設 60 秒、cooperative cancellation、持久 checkpoint。
- candidate key 與 deterministic memory ID；kill/cancel 後同 run key 續跑，同批再跑不重複。
- inferred candidate 少於三個獨立來源時保持 `candidate`，不進 FTS committed recall。
- trait 每次最多 0.01、同週最多 0.05、至少三個獨立來源。
- relationship 只新增 revision，保存 source IDs；Immutable Core 未修改。
- 30 天合成事件 A12：第一筆後取消、恢復完成、全批再跑，最終只有 5 個 outputs/5 個 memories。
- scheduler 只在 idle 且資源允許時啟動；同一 run 不重複排程，wait/close 清理 task 與 cancellation token。

完整 gate：69 passed、3 個真 provider opt-in skips。
