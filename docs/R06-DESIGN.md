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

---

## 7. 接線計畫（對照 R05 契約，只讀調查；未改 integrated／runs／goal_tasks）

依據：`E:\coding\Worktrees\r05-agent-planning`，分支 r05-agent-planning，4be01e4（R05 未完成，行號可能漂移）。
R05 的 `PlanCheckpoint` hook 已覆蓋我們三個 crash 點；R06 只需提供「hook → 寫 checkpoint」與「checkpoint → resume 快照」兩個轉接器，coordinator 不必改。

### 7.1 ID 對映

| R06 `run_checkpoints` | R05 |
|---|---|
| `run_id` | `plan_id`（父層；子任務各自的 journal child run 不用作 key） |
| `step_id` | `subtask_id`（`s1..s3`） |
| `plan_id` 欄 | `plan_id`（同上，保留供查詢） |
| `capability`/`arguments` | `Subtask.capability`/`arguments` |
| `effect` | 一律 `read`（R05 只允許 `read_tools`，由 catalog `effect=="read"` 決定）；write/readback 分支為未來預留，只靠單元測試涵蓋 |
| child `run_id`／`proposal_id` | 存在 ack/save 的 payload（SubtaskResult JSON）內，不另開欄位 |

### 7.2 Hook point → 儲存層操作（新檔 `services/agent/resume.py`，R06 自有）

| R05 point | 動作 |
|---|---|
| `plan_created` | 寫 plan 快照；對每個 subtask `plan(...)` |
| `subtask_dispatch`（coordinator.py ~L257，在 `run_read` 之前） | `mark_dispatched(plan_id, subtask_id)`。因 hook 在 journal 的 dispatch 之前，崩在兩者之間只會留下「dispatched 但從未執行」，對 read 是安全的保守 unknown |
| `subtask_observed` | `ack(success, observation)`（payload 含 child run_id／proposal_id） |
| `subtask_verified`（含失敗） | `save(...)`；若 `error=="outcome_unknown"`／`prior_outcome_unknown` → **不得**存成 failed，保留 unknown |
| `subtask_blocked` | 需新操作 `close_unrun(run_id, step_id, reason)`（planned→saved、outcome=failed、未經 dispatched）。這是 checkpoints.py 的小增補 |
| `plan_finished` | 寫 plan 終態快照；不再續做 |

Hook 取「目前是哪個子任務」：`PlanCheckpoint` 沒有 `subtask_id`，只能由「最後一筆 result」或「第一個尚無 result 的子任務」推斷，脆弱。**請 R05 加一個欄位 `subtask_id: str | None`**（向後相容的預設值）。這是最主要的 R05 衝突點，改動極小。

### 7.3 Resume（checkpoint → `PlanCheckpoint`）

啟動時（`runs.reconcile()` 與 `checkpoints.reconcile()` 之後）對每個未 `plan_finished` 的 plan 組出 `resume` 快照，再呼叫 `coordinator.run(session_id, goal, resume=...)`（goal/session 從 plan 快照取）。每個子任務依 `decide()`：

- `skip`（saved）→ 放入 `results`，帶完整 SubtaskResult（含 verdict）→ coordinator 直接沿用（L ~232）。
- `adopt`（acked）→ 放入帶 observation 的 RUNNING 結果 → coordinator 只重驗，不重跑（L ~253）。
- `run`（planned，或 dispatched 的 read-only unknown）→ **不放入** `results` → coordinator 當成新子任務再派工一次。
- `readback`／`await_owner`（write 類）→ R05 目前不會出現；若出現，R06 不呼叫 coordinator 續做該 plan，改走 unknown-effect 的 owner 流程。

**衝突點 2（coordinator.py ~L248–252）**：coordinator 對「`prior.observation is None` 且有 `run_id`」一律標 `failed(outcome_unknown)`。R06 對 read-only 允許重跑，所以 R06 resume 必須**過濾掉**這種 prior（不傳入），避免被 coordinator 判失敗；不需改 R05。若 `prior` 沒有 `run_id` 就不會觸發該分支，但仍建議 R06 明確過濾。write 類 unknown 則保持 coordinator 現行行為（不重送），正好符合 R06。

**衝突點 3（持久化 plan 本體）**：`PlanCheckpoint.plan` 需整份落盤才能 resume，`run_checkpoints` 沒位置放。建議在**同一個 019 migration**（尚未被任何分支使用，可直接修改）加 `plan_snapshots(plan_id PRIMARY KEY, session_id, goal, state, snapshot_json, updated_at)`。R05 的契約明說「不新增資料庫」，指的是不另立 DB owner；加表走既有 migration 序列，需 R05／schema owner 同意。

### 7.4 要改的檔案與位置（待 owner 同意才動）

| 檔 | 位置 | 改動 | 衝突 |
|---|---|---|---|
| `persistence/migrations/019_run_checkpoints.sql`（R06 自有） | 檔尾 | 加 `plan_snapshots` | 與 schema 兄弟序列 |
| `services/agent/checkpoints.py`（自有） | — | 加 `close_unrun`；`save()` 可帶 payload | 無 |
| `services/agent/resume.py`（新，自有） | — | `make_checkpoint_hook(repo)`、`build_resume(repo, plan_id, has_readback)`、`ResumeWorker` | 依賴 R05 的 `PlanCheckpoint`／`CheckpointPoint` 型別 |
| `services/agent/planning.py` | `PlanCheckpoint` | 加 `subtask_id: str | None = None` | **R05 擁有**；需 R05 同意 |
| `services/agent/coordinator.py` | `_emit` 呼叫處（`finish`、dispatch 的 `_emit`） | 傳入 `subtask_id` | **R05 擁有** |
| `services/presentation/integrated.py` | ~L1355–1374（`_journal_event`、`reconcile()` 之後）與 R05 的「最後才最小接線」處 | 組裝時以 `hook=make_checkpoint_hook(...)` 建 Coordinator；`_ensure_core` 在 `reconcile()` 後呼叫 `checkpoints.reconcile()` 與 `ResumeWorker.start()` | 與 R05 的 flag 接線、其他 integrated 改動**序列化** |
| `services/agent/runs.py` | 不改 | 既有 `reconcile()` 繼續保守標記 child runs | — |
| `services/agent/goal_tasks.py` ~L115–117 | 不改（D57 單一目標任務有自己的暫停語意） | 若 owner 要讓 D57 任務也續做，另案 | — |

Flag：續做走 `SIRO_AGENT_PLANNER_ENABLED` 之上再加 `SIRO_AGENT_RESUME_ENABLED`（預設 0）。關閉＝checkpoint 照寫、不自動續做，退回人工 resume。

### 7.5 接線後的新增測試

用 R05 的 fake planner／tool port（`tests/integration/test_agent_planning.py` 的做法）加 SQLite hook，在 hook 內拋 `CrashPoint`：
`plan_created`、`subtask_dispatch`（前／後）、`subtask_observed`、`subtask_verified` 各崩一次，重開 DB 後 `build_resume` → `coordinator.run(resume=...)`，斷言：工具執行次數 ≤1（read unknown 允許 2，且只算在「dispatched 未 ack」）、已 verified 子任務不重做、unknown 不變 success、`blocked` 不執行工具。

### 7.6 開放問題（需 owner／R05 回覆）

1. R05 是否同意加 `PlanCheckpoint.subtask_id`？
2. 是否同意在 019 加 `plan_snapshots`（或要求把 plan 存進 `run_journal` 現有欄位）？
3. integrated.py 接線視窗：誰先、何時？
