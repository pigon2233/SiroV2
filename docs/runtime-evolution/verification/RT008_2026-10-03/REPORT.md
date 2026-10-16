# RT-008 Independent Verification — 2026-10-03

Verdict: **VERIFIED_WITH_MINOR_ISSUES**. 建議保留 roadmap DONE，限定於本卡的 local journal / read-only recovery 與既有 round/tool budget；不代表產品發布、外部副作用 exactly-once、自動續跑或硬體驗收。本輪未修改 production code、roadmap、既有測試或私人 DB；新增資料僅在此 verification 目錄。

## 1. Target / intent

依目前 roadmap 的 DONE 與 completion date 自動選取 RT-008（2026-10-03）；RT-009 仍 PLANNED。讀取本卡完整 Objective、Problem/F04、scope、tests、acceptance、compatibility、rollback，以及 ARCHITECTURE_FRICTION_MAP、REGRESSION_BASELINE、RUNTIME_EVOLUTION_SPEC、COMPATIBILITY_PLAN、D20、CONTRACTS。Implementation README 僅提供證據索引。

目標是恢復 durable canonical context、已完成 observations、剩餘配對與 budget counters；dispatch 已發生但結果未提交時須 unknown，不能重送。恢復後不重新呼叫 model/executor、不綁定 live execution context。既有 migration/enums/identity 不改；candidate opt-in；回滾保留 reader/schema、禁止 DB 自動降版。設計較廣的 token/cost/elapsed policy 尚未新增，本卡與 CONTRACTS 的具體 budget 是 model rounds / tool-call counts，既有 max_steps 仍存於 agent_runs。

## 2. Actual runtime path

* Gateway main 傳 controller.startup / recovery_readback 到 create_app；lifespan 在 yield 前執行 startup。candidate _ensure_core 初始化 migration、建立 repository、reconcile、安裝 journal_hook。缺省 legacy；legacy 不 reconciliation，但 persistent proposal guard 仍避免重播 candidate 舊提案。
* respond 的 AgentRun 與 journal 在同一 SQLite transaction 建立；reserve_round 在 generation 前提交。CompanionCore optional on_messages_ready 在 canonical context 組裝後、ConversationEngine 前 checkpoint；不是 detached implementation。
* accepted assistant batch 在 _propose_tool_calls 中先 checkpoint，再 propose/bind。共同 ToolOrchestrator.execute 的 contextual 與 arguments-only 路徑均於 executor 前提交 dispatch intent；於 proposal completion / delivery 前提交 observation。manual denial 與 partial callback 亦寫入 canonical call row。
* reconcile 不呼叫 handler/provider；包含 proposal insert→bind gap、RUNNING-without-intent 的保守 unknown；fence pending/approved/running proposals；canonical readback 由 call rows 重建一對一 ordered tool observations。重跑 reconciliation 具冪等性。
* authenticated GET /v1/agent-runs/{session_id} 使用 repository readback；boot 真正 fetch browser session 並用 recoveryNotice 顯示中斷/unknown。已執行 actual JS function，未宣稱 GUI rendering。
* runs.py 未發現 TODO/pass/NotImplemented 或 stub。legacy 無 journal 是明確 compatibility path，readback 顯示 legacy_unrestorable，沒有偷偷從 prompt 偽造 canonical context。start_journal 是直接 repository 測試入口，production 使用 atomic start(runtime_backend=...)。canonical journal 與舊 steps 各負責 context / 相容 ledger，不是舊路徑繞過新路徑。

## 3. Scope discipline

scope.json：目前十個 task source/test digests 全吻合 evidence；只在 temporary copy reverse implementation.patch，七個 before digests 全吻合。實際工作目錄沒有 reverse patch。與既有 dirty tree 分開歸因。

變更包含 runs、additive 013、integrated、orchestrator、Core optional callback、Gateway/UI caller、隔離 operational test。後四項超原 expected 三檔清單，但 D20 記錄且是 pre-provider checkpoint、HTTP approval journal、startup/readback、consumer 顯示的必要 caller。沒有 mass rename/move、API 移除、旧 enum/migration 改寫、config format 或 Rust protocol 改變；HTTP 新增 authenticated readback，既有契約測試通過。Core 只依賴 optional async callback，沒有導入具體 persistence/UI/executor。

## 4. Tests / evidence

本輪執行 related gate：test_run_journal、agent_runs、agent_batches、tool_catalog、integrated_companion、gateway、gateway_main、gateway_terminal_fence、execution_lifecycle、sqlite_store、operational_cli、contract/model_adapters，**104 passed，3 dependency warnings，36.41s**，無 skipped/xfail。沒有重跑全套，implementation 的 285 passed/5 skipped 不冒充本輪結果。

另保存本輪 task.log：**12 passed**（包含 parametrization），main-smoke.log：actual installed Gateway + temporary DB + HTTP recovery + unchanged real effect file + served UI + graceful shutdown 全 PASS；ruff.log PASS；mypy.log 174 files PASS。main smoke 的 provider 為 offline/synthetic，沒有呼叫真 provider。

Crash cases 是真 subprocess os._exit(42)，四個 dispatch / observation 邊界都經真 Core/SQLite/controller/orchestrator；executor 寫入並 fsync 真 synthetic file。恢復的 model/handler 若被呼叫即 raise。另涵蓋 partial batch、duplicate/conflicting observation、queued approval fence、budget exhaustion after reopen、journal finish→run final crash window、legacy rows、auth、manual approval、schema 0/10/12→13、idempotence、old loader/table reader、integrity。不是只測 mock method；外部 model / PC effect 是 synthetic。

測試沒有 skipped/xfail 或 sleeps-as-correctness 的核心斷言；subprocess/network 有 timeout，未做長期 flaky/soak 統計。testpaths=tests，dedicated tests 會自動收集；fixtures/run_journal_crash.py 由 parametrized tests 顯式 subprocess 執行；本目錄的獨立診斷案例必須顯式執行，不列入標準 suite。

## 5. Relevant regression baseline

| Baseline | Status | Evidence / limits |
|---|---|---|
| restart/repository recovery、不能重播副作用 | PASS | 四 crash points、repeat startup、real main HTTP、effect file unchanged |
| tool proposal/approval、batch、denial/error/cancel | PASS | dedicated + agent_batches/tool_catalog/execution_lifecycle/integrated suites；synthetic executor |
| conversation/streaming/terminal | PASS | integrated、gateway、terminal fence、model adapter contracts；真 provider/browser streaming NOT VERIFIED |
| session isolation / persisted context readback | PASS | other-session None、canonical messages/pairs；跨分頁 GUI context reload NOT VERIFIED |
| memory/state/schema compatibility | PASS | sqlite suite、0/10/12 upgrade、old reader、integrity；不是更改 memory algorithm |
| config default/legacy/candidate、shutdown | PASS | gateway_main、operational isolated launcher、network smoke shutdown |
| deployed rollback / power-loss / real OS reconciliation | NOT VERIFIED | 只驗 synthetic old loader/source reverse 與 process abrupt exit；不等同部署 rollback/斷電/OS結果查證 |

沒有觀測到由 RT-008 引入的 regression；這個結論只涵蓋上列路徑。

## 6. Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| 零盲目重送 | PASS | 四 crash cases、forbidden recovery handler/model、unchanged fsynced effect、repeat reconciliation、queued old approval fence、actual main startup |
| unknown 可見 | PASS | dispatched / persisted running 未提交 observation → outcome_unknown；AgentRun error、paired tool observation、authenticated HTTP、actual recoveryNotice JS；GUI NOT VERIFIED |
| 所有 tool pairs 與預算可恢復 | PASS | ordered canonical pairs、partial batch committed result retained、missing pair explicit、duplicate idempotence/conflict rejection、round/tool counts/limit reopen、reserve exhaustion；限定既有預算，不涵蓋未新增 token/cost/elapsed policy |

## 7. Issues / severity / fixes

1. **P2，既有問題，非 RT-008 regression**：同一 session 的不同 run 重用 provider call ID，第二輪 FAILED。獨立 test_independent.py 在本版及驗證過 before digests 的前版皆失敗（current.log / before.log；before.log 顯式驗證 import 來源為 temporary reversed src）。根因既有 integrated.py:645 session-wide _seen_calls 與 migration011:14 UNIQUE(session_id,call_id)。最初懷疑新增 journal_owner，對照後撤回歸因。這個失敗不算本卡 PASS，也不能據此宣稱 RT-008 regression。可另卡處理 run-scoped tool identity，並同步精確 proposal ownership/reconcile matching；保留本案例。
2. **P3，驗證層級限制**：真正 browser rendering、power loss、真 provider/OS reconciliation、multi-owner、soak、部署 rollback 尚未驗。現有文件已明列，未發現假裝通過。若要擴張 DONE 語義，須先補相應實驗。
3. **P2，歷史測試隔離事故**：implementation 時舊 operational 測試誤套 migration013 到 default private DB；本卡 README 保留事故與 checksum fail。此次只檢查修正後 env/data 隔離及成功 launcher，未讀私人資料或自行 downgrade。無法獨立證明私人 DB 在事故前後完全無資料變化；該項 NOT VERIFIED。未再發生於本轮隔離測試。

Required fixes：本卡限定 acceptance 沒有新增 production blocker；若進行部署/資料回滾，先完成一致 backup / integrity / 保留新增資料的程序。不得把上述未驗層級當發布完成。

Optional improvements：另外處理跨 run call-ID 既有限制；補 checkpoint/observation commit failure 注入、真 browser reload、部署 feature-off rollback 及 power-loss durability 實驗。不要在此 verification 偷改 production。

## 8. Roadmap recommendation

**保留 RT-008 DONE**，保留既有 scope/limitations。Verdict 為 VERIFIED_WITH_MINOR_ISSUES。若日後將「所有預算可恢復」解釋為新增 token/cost/elapsed policy，或將恢復解釋為外部結果查證/續跑，應改 PARTIAL；目前 task/CONTRACTS 明確限定 local readback 與 round/tool counters，未以缺少未授權功能判失敗。
