# R06 設計：checkpoint 與安全續做（草案，只讀調查後）

狀態：DESIGN／LOCAL_ONLY／NOT PUSHED。Base：1ff57b2。分支：claude/r06-checkpoint。
注意：計畫書 `AUTONOMOUS-AGENT-PLAN.md` 在本機不可讀，以 AUDIT 06/04/07 卡片的 R06／G05 條文為準。

## 1. 現況（已讀程式碼）

- `agent/runs.py`：`run_journal`（整體訊息）＋`run_journal_calls`（每個 tool call：`dispatched`、`observation_json`）。
  `record_dispatch` 在 handler 之前寫入（orchestrator `invoke()` 的 journal_hook "dispatch"）；`record_observation` 在效果之後。
- `reconcile()`（啟動時，`IntegratedCompanion._ensure_core`）：未完成 run 一律標 `interrupted`＋run `failed`；
  `dispatched=1` 且無 observation → `outcome_unknown`；未派工 → `not_dispatched`。**不呼叫 handler/模型，也不續做。**
- `ToolOrchestrator.execute`：已有 recovered-proposal 不得 replay 的防護；`transition(... automatic=True)` 對
  非 read 的相同 capability＋參數擋 `PriorOutcomeUnknown`（owner 需手動核准）。
- `goal_tasks.ReadTaskOwner.start`：RUNNING/READY 的目標一律 `paused(interrupted_restart)`，無續做。

缺口（G05）：無「已完成步驟」的持久化、重啟後無法續做剩餘只讀步驟。

## 2. Checkpoint 資料結構（新表，不改既有表）

migration `019_run_checkpoints.sql`（需與 schema 兄弟序列化）：

```
run_checkpoints(
  run_id TEXT, seq INTEGER,            -- 單調遞增，PRIMARY KEY(run_id, seq)
  plan_id TEXT NULL, step_id TEXT,     -- R05 契約出現前 step_id = call_id
  effect TEXT CHECK(effect IN ('read','write','unknown_class')),
  phase  TEXT CHECK(phase IN ('planned','dispatched','acked','saved')),
  idempotency_key TEXT NOT NULL,       -- hash(run_id, step_id, capability, 正規化參數)
  outcome TEXT CHECK(outcome IN ('success','failed','unknown','not_dispatched')) NULL,
  observation_json TEXT NULL, created_at TEXT,
  UNIQUE(run_id, step_id)              -- 一步一列，phase/outcome 只能前進
)
```
- phase 單向：planned → dispatched → acked(效果已有 observation) → saved(結果已併入 journal 訊息)。
- `outcome` 一旦為 success/failed 不可被改成 unknown；`unknown` 只能被「查結果成功」或 owner 明確處置改寫（寫新列事件，不覆蓋）。
- effect 來源只信 `ToolDescriptor.effect`（目錄當前分類），缺失視為 `unknown_class`＝有副作用。

## 3. 三個 crash 點與恢復規則

| crash 點 | 磁碟狀態 | 恢復動作 |
|---|---|---|
| A 派工前 | phase=planned（或無 dispatched） | 確定沒執行過 → `not_dispatched`；read/write 都可在續做時（write 需仍有有效授權）正常派工，一次。 |
| B 效果後、ACK 前 | phase=dispatched、無 observation | **outcome unknown**。read：可重跑（冪等）；write/unknown_class：**不重送**，先走「查結果」(readback) handler，查不到→維持 unknown 並等 owner。 |
| C 保存後 | phase=saved/acked 有 observation | 已完成；續做直接採用既有 observation，不再執行。 |

通則：unknown 永不轉 success；`reconcile` 仍不呼叫 handler；續做由獨立 `ResumeWorker` 在 reconcile 之後、
僅對 effect=read 的剩餘步驟排程；write 步驟→ 產生 owner 待辦（沿用 unknown_effect_approval 流程）。
同一 `idempotency_key` 只允許一次成功派工（DB UNIQUE＋`record_dispatch` 原子更新）。

## 4. 模組切分

1. `services/agent/checkpoints.py`（新）：儲存層＋狀態機＋`ResumePlan` 計算（純函式，輸入 checkpoint 列，輸出每步 action：
   `adopt` / `run` / `readback` / `await_owner` / `skip`）。不依賴 R05。
2. `tests/support/crash_injection.py`（新）：在 phase 邊界注入崩潰（raise `CrashPoint` 後以相同 DB 重開），
   並以計數 executor 驗證零重複副作用。
3. 接線（等 R05 契約＋與 Gateway/Integrated 兄弟序列化）：`_journal_event` 同步寫 checkpoint；
   `_ensure_core` reconcile 後啟動 ResumeWorker；`goal_tasks.start` 對可續做的 read-only 目標不再一律 pause。
4. 回退：flag 關閉 ResumeWorker，checkpoint 保留，退回人工 resume；不刪資料。

## 5. 驗收

`pytest tests/integration/test_run_journal.py tests/integration/test_goal_task_loop.py tests/integration/test_unknown_effect_approval.py -q`
不退步＋新增 `tests/integration/test_run_checkpoints.py`：三 crash 點 × (read, write)，斷言副作用計數 ≤1、unknown 不成 success。

## 6. 風險／待決

- R05 契約（plan/step id、依賴）未出現：step_id 先用 call_id，契約出現後加 plan_id 對映。
- 「查結果」handler 目前只有部分工具具備；沒有者一律 await_owner。
- migration 編號 019 需與其他執行緒確認不衝突。
