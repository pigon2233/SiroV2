# R05 介面契約 — 有界任務拆解與規劃（供 R06 使用）

程式：`src/siro/services/agent/planning.py`（契約）、`coordinator.py`（協調器）、`planning_adapters.py`（接 ToolOrchestrator／journal／雲端模型）。
旗標：`SIRO_AGENT_PLANNER_ENABLED`（預設 `0`；Gateway/Integrated 最後才最小接線）。關閉＝完全走既有 tool loop。
不新增資料庫：持久化只走既有 `run_journal`（每個子任務一個 child journal run）＋ checkpoint hook。

## 狀態列舉

```
PlanState:    planning | running | completed | failed | cancelled
SubtaskState: pending | running | verified | failed | blocked | cancelled
```
- `completed` ＝ 全部子任務 `verified`；任一 `failed/blocked` ＝ `failed`（報告仍含已驗證部分）；`cancelled` 由 `cancel()`。
- `blocked` ＝ 其相依子任務未 `verified`（失敗傳遞），**不執行工具**。
- 終態不可回頭；`unknown` 不會被轉為 success。

## 資料型別（皆 frozen dataclass；`PlanReport/PlanCheckpoint` 有 `to_json()`）

```
Subtask(subtask_id, title, capability, arguments, depends_on: tuple[str,...], expect: str)
Plan(plan_id, goal, subtasks: tuple[Subtask,...] (1..3), planner_model, degraded: bool)
Source(capability, ref, excerpt)            # excerpt 必為原始 observation 的子字串
Verdict(verified: bool, reason, quotes: tuple[str,...], verifier_model, degraded)
SubtaskResult(subtask_id, state, run_id|None, proposal_id|None, observation, sources, verdict|None, error|None)
PlanReport(plan_id, state, results: tuple[SubtaskResult,...], summary, models: tuple[str,...], degraded)
PlanCheckpoint(plan_id, point, state: PlanState, plan, results)   # 完整快照，可直接落盤
```
- `subtask_id` 在 plan 內唯一（`s1..s3`），`run_id` 為子任務的 journal run（child ID）。
- 只允許 `capability` ∈ 注入的 `read_tools`（目前由 catalog `effect=="read"` 決定）；其他＝plan 驗證失敗，不執行。
- `depends_on` 只能指向較前的子任務（DAG、無環）；最多 3 個子任務；每任務 1 次工具呼叫。

## Checkpoint hook 點

`CheckpointHook = Callable[[PlanCheckpoint], Awaitable[None]]`，由協調器在下列 `point` 呼叫（先寫 hook 再繼續）：

| point | 時機 | R06 恢復語意 |
|---|---|---|
| `plan_created` | planner 回覆且驗證通過後 | 可重新開始 |
| `subtask_dispatch` | 該子任務 journal `dispatch` 之前 | 未 dispatch → 可安全重跑 |
| `subtask_observed` | 觀察已寫入 journal（`record_observation`）後、驗證前 | 已有 observation → 只重驗，不重跑工具 |
| `subtask_verified` | verifier 判定寫入後（verified/failed） | 完成，不重做 |
| `subtask_blocked` | 因相依失敗而 blocked | 完成 |
| `plan_finished` | 終態（含 cancelled） | 完成 |

已 dispatch 但無 observation ＝ 結果未確認：協調器標 `failed(error="outcome_unknown")`，**不自動重送**（由 R06 的 unknown-effect 流程處理）。
Resume 入口（R06 可呼叫）：`await coordinator.run(session_id, goal, resume=checkpoint)`：以快照中 `verified`／已有 observation 的子任務為準，只補剩餘 read-only 步驟。

## 協調器 API

```
Coordinator(planner: PlannerModel, tools: SubtaskToolPort, *, read_tools, hook=None, max_subtasks=3)
await coordinator.run(session_id, goal) -> PlanReport
await coordinator.cancel(plan_id)            # 立即擋新 dispatch，取消進行中子任務，狀態 cancelled
```
- `PlannerModel.complete(role: "planner"|"verifier"|"reporter", prompt) -> ModelReply(text, model_name)`；模型走 `Privacy.CLOUD_ALLOWED`；回報**實際**模型名，若不在預期雲端名單（降級）→ `degraded=True` 並寫入 report.models。
- `SubtaskToolPort.run_read(plan_id, subtask, session_id) -> ToolRunResult(run_id, proposal_id, observation, error)`：實作 `OrchestratorToolPort` 走 `propose → bind_proposal/bind_call → resolve(automatic=True) → execute`，journal 由 orchestrator 的 `journal_hook` 寫入（即既有 approval/grant 規則，不繞過）。
- Verifier 必須引用原始 observation 的逐字片段（`quotes`），協調器以子字串檢查；引用不存在 ＝ 判失敗（防捏造來源）。

## 不做
任意 GUI／部署／寫入工具、無限子 Agent、自動擴權、平行 DB owner。
