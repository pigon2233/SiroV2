# RT-005 Independent Verification — 2026-10-01

**Final verdict：FAILED_VERIFICATION。RT-005 的 DONE 不應保留，建議改為 FAILED_VERIFICATION。**

程序取消的主要路徑成立，但「零 late UI」有可重現反例。沒有證據將這個問題歸因為 RT-005 新引入的 regression；writer 仲裁與前端未過濾行為為既有程式，所以不使用 REGRESSION_DETECTED。既有測試另有一次未穩定重現的超時，不隱藏首次失敗。

本輪只新增本目錄的驗證報告、獨立測試、log 與 provenance；沒有修改 production code、既有 tests、roadmap、設定、migration 或私人 runtime data，也沒有啟動真 provider/GPU/GUI。

## 1. Target 與 intent

從 `docs/runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md` 自動辨識：RT-001–005 DONE、RT-006–015 PLANNED，因此最新完成卡是 **RT-005 run cancellation 傳到程序**（2026-10-01）。沒有以最近文件修訂的 RT-004 repair 取代最新完成 task。

重建依據：roadmap 的 Objective、Problem、Audit evidence、Scope、Acceptance、Compatibility、Tests、Rollback；F03；RUNTIME_EVOLUTION_SPEC 第 55、61、65、92 行；COMPATIBILITY_PLAN、MIGRATION_PLAN、REGRESSION_BASELINE；CONTRACTS 的取消契約及 RT-005 段；DECISIONS D15；ACCEPTANCE A02/A05/A16；EXPERIENCE 取消要求。另讀 AGENTS、STATUS、SOL_RUNBOOK、實際四個 production modules 與測試；completion README 僅用於索引、比較聲明及重建改動。

- Objective：停止新 dispatch，取消 owned foreground process group，等待有界清理，禁止 late output 復活。
- Problem/F03：舊取消只到 conversation/body，程序 executor 沒有 token/handle。
- Scope：execution、orchestrator、integrated；Gateway 為必要 caller。禁止碰其他 session/使用者程序、Rust grants 與 freeze zones。
- Acceptance：受控 child 2 秒停止；cleanup 失敗 5 秒內明報；100 races 零 late UI。
- Compatibility：預設 legacy、candidate opt-in；舊 arguments-only executor；既有授權 defaults、HTTP/WS、observation、config/state/schema 保持；新 run 使用固定 profile。
- Tests：parent/child cancel、timeout、完成與取消、其他程序存活；受影響文字/工具/取消 fixtures 與 lint/types。
- Rollback：先停止新增 candidate run 並清理已知 owned child，再以 legacy 啟動新 run；不接續中途 run、不 pkill、不重播未知副作用。

## 2. Actual code 與 runtime wiring

| 檢查 | 結果與 evidence |
|---|---|
| code 存在且有真正實作 | execution.py:24 ExecutionContext、:47 cleanup、:79 execute_bounded_argv；實際 spawn/drain/signal/wait，非 stub |
| runtime caller 使用 | integrated.py:195 start_run、:613 bind_proposal；orchestrator.py:253 contextual dispatch；gateway.py:1096 candidate contextual_executors、:1042 candidate argv facade |
| token/deadline/epoch | token 共享，Gateway timeout 轉 monotonic deadline；epoch 為 run_id metadata，非獨立 epoch 比較器；新 run UUID/context 隔離與 terminated gate 生效。RAM-only，重啟隔離未實作 |
| authorization | proposal hash/approval/state transition 保留；approved→running 後傳 authorized=True。不是新增 policy engine，沒有改 full/tools default |
| ownership / cleanup | start_new_session=True；僅 killpg(process.pid)，TERM→250ms→KILL；wait/reap 直接 child，持續 drain；helper 4.5s、cancel_run 4.75s。不是 reap 所有非直接後代 |
| cancelled output consumer | auto path 檢查 terminated；manual HTTP 檢查 is_fenced；proposal error/observation 進 SQLite，正常結果進 UI/continuation。cleanup error 到 FAILED terminal/DB |
| detached implementation | cancellation facade 確實被 candidate computer.execute 使用，非 dead code。detach=True 為另一種實際 launch 行為：ack 前清理、ack 後保留，相容性限制已明列 |
| hidden fallback / 舊 path 繞過 | candidate main 的 computer.execute 有 context，legacy 預設與 arguments-only fallback 為明示相容路徑；沒有失敗後 retry/偷轉 legacy。browser/process.start 不具備本卡 foreground cancellation，不將其算本卡實現 |
| duplicated logic | Gateway legacy closure 與 candidate helper 同時存在，是 profile 相容保留；本卡沒有另建無 caller 的 executor |
| TODO/pass/NotImplemented | task production modules 沒有以這些代替核心實作；exception classes 的 docstring body 不是 stub。測試 socket.close 的 pass 僅為合成 port |
| config 真的啟用 | main startup 捕捉 SIRO_RUNTIME_PROFILE，controller/executor 共用 binding；candidate/legacy main fixtures 實際通過。未查部署使用者服務是否啟用 candidate，不宣稱目前服務已啟用 |
| output 被 consumer 使用 | index.html:83 處理 terminal、:92–93 無條件更新 tool_started/tool_result；這也是 late delivery 反例能影響 UI 的 source evidence |

**關鍵缺口：controller broadcast 的 fence 只阻止新增事件，不能阻止已排入 Gateway queue 的舊事件在 terminal 之後送達。**

## 3. Scope discipline / provenance

現有工作區包含其他未提交任務改動，不將全部 dirty diff 歸給 RT-005。驗證四個 source 加 task test 的 SHA-256 均符合 completion source-digests；在臨時隔離副本 reverse implementation.patch，四個 source 均符合 before-digests。結果見 [provenance.json](provenance.json)。這證明保存 patch 與當前 bytes/before snapshot 一致；不是 Git commit history 的獨立時間認證。

該 patch 僅四個 production modules 與一個新增 test。沒有 mass rename/move、unnecessary refactor、Rust/schema/identity/body/audio 改動。Gateway 增量為 executor context、manual fence、turn→session 定向取消，符合必要 caller 範圍。新增 optional contextual_executors/context 不破壞舊 signature；existing enum/observation/payload 格式保留。services 層依賴 ExecutionContext，沒有把 OS driver coupling 引入 Core。

未發現本卡越界修改。不能從 task patch 推定其他既有 dirty 修改沒有風險。

## 4. Tests：實際執行及覆蓋

| 本輪執行 | 結果 | 層級與限制 |
|---|---|---|
| 10 個相關 integration 檔第一次執行 | **74 passed、1 failed**，55.60s，exit 1 | test_agent_batches 的 completion-first 100 次測試在 :187 等 entered 超過 2 秒；非斷言實際 late output |
| 單獨重跑上述失敗 case | 1 passed，5.83s，exit 0 | 第一次失敗仍保留；未確認根因，可能排程/I/O 時序敏感，不能當成永遠穩定 |
| 同一相關 suite 第二次完整重跑 | **75 passed**，28.97s，exit 0 | [relevant-tests.log](relevant-tests.log)；包含 task-specific 全部 14 cases；沒有 skip/xfail |
| body adapter/failure、audio pipeline/protocol、config、runtime boundary | **16 passed**，0.88s，exit 0 | [related-baseline.log](related-baseline.log)；合成/本機 fixtures，非真 GUI/GPU |
| 獨立 transport 反例 | **1 failed**，1.09s，exit 1 | 預設 GatewayHub/真 ClientChannel writer/真 controller-orchestrator-SQLite；synthetic model/executor/socket port；[independent-test.log](independent-test.log) |
| ruff check src tests | PASS，exit 0 | 沒有 lint 修改 |
| mypy | PASS，168 source files，exit 0 | 沒有 type 修改 |
| reverse patch check | PASS，exit 0 | 隔離副本撤回及 before digest 比較；未實際部署 rollback |

相關 suite 明確檔案：test_execution_lifecycle、test_bounded_execution、test_tool_orchestrator、test_agent_batches、test_gateway_main、test_gateway、test_integrated_companion、test_conversation、test_computer_driver、test_sqlite_store。

Task tests 有真 asyncio subprocess/fork/process group、TERM-ignoring child、direct child reap、unrelated process、pre-cancel/deadline、detach ack 前後、delayed spawn/repeated cancel。error path 有 permission/no-effect signal fault injection，UI/DB cleanup failure 使用 synthetic executor；兩者證據沒有被混稱為全真 E2E。main test 真組裝 main + ASGI HTTP + 真 subprocess，但 provider/uvicorn run/hub 被替換，非真網路 server/provider。

100 races 使用 cooperative synthetic contextual executor，確認 controller broadcast 呼叫順序、單 terminal/後續 dispatch；沒有經過真 ClientChannel writer。manual HTTP 程序測試也使用記錄 hub。**因此既有綠燈無法證明真 UI 接收順序。** 本輪獨立測試補上 writer 邊界並失敗。

沒有在所跑 suite 發現 skipped/xfail；pytest testpaths=tests，既有 task 檔在 discovery 範圍。沒有重跑全 repo suite、real-provider opt-in tests、Rust、24h soak 或真 GUI/GPU；completion 的全套數字不當成本輪結果。

## 5. Regression baseline（只列相關部分）

| REGRESSION_BASELINE 項目 / 受影響行為 | 判定 | evidence / 邊界 |
|---|---|---|
| conversation/streaming 的既有 Core/SQLite + fake model fixtures | PASS | conversation / integrated / Gateway 相關 suite；真 provider/browser delta 未驗 |
| tool calls：single/batch/denied/failed/continuation/legacy handler | PASS | orchestrator、batches、bounded、integrated 既有 fixtures |
| cancellation/timeouts：受控 owned group、queued tool fence | PASS | lifecycle 全 14 cases、bounded timeout/child reap |
| cancellation：UI terminal 之後不得復活 | **FAIL** | 獨立 production writer 反例；不是把已入 queue 的舊 output 當新 dispatch |
| session：定向 A cancel 不停止 B/unknown 不殺 | PASS | main HTTP 真程序 A/B fixture；不是完整 UI 多分頁驗收 |
| PC control：main argv binding/64KiB bounded drain/非零 exit | PASS | bounded/executor/main fixtures；本輪未再量測 RSS |
| config / 授權：legacy/candidate 固定、full/tools/argument hash | PASS | main profile fixture、config/orchestrator/Gateway；JSON/env effective-config 整合尚屬 RT-007 |
| audio/body：adapter cancellation 與 failure isolation、protocol | PASS | 額外 16-case gate 中相關 fixtures；非視覺/聽測 |
| shutdown：既有 Gateway callback/hub cleanup | PASS | Gateway/main idle shutdown fixtures |
| shutdown：真 main lifespan 帶 active owned executor / Qwen cleanup | NOT VERIFIED | 本輪沒有 active-process shutdown E2E；Qwen lifecycle 屬 RT-006 |
| restart/recovery 與 deployment rollback | NOT VERIFIED | RAM guards，recovery 屬 RT-008；reverse patch 成功不等於部署演練 |

目前沒有可歸因 RT-005 的新增 regression 證據。第一次 test timeout 是驗證可靠性問題，尚未定位為 production regression。

## 6. Acceptance criteria（roadmap 三項逐一判定）

| Criterion | 判定 | evidence |
|---|---|---|
| 受控 child 2 秒停止 | **PASS** | 本輪 lifecycle cancel/timeout/task_cancel parent/fork-child、TERM-ignore、direct child reap assertions 均通過；controller 真 group cancel 通過。只代表指定受控 fixture，不保證 escaped daemon |
| cleanup 失敗 5 秒內明報 | **PASS** | permission/no-effect 測試明確 <5s + ExecutionCleanupError；controller failure fixture 確認 failed/error 進 DB 與 terminal。不是 kernel 不可中斷或無限 spawn 的普遍保證 |
| 100 races 零 late UI | **FAIL** | 100 次 broadcast-level fixture 通過，但真 writer 可在 terminal 後送達 6 個 tool_result、6 個 tool_started，以及 6 個 tool_proposal。單一有效反例已否定整條 UI 保證 |

Objective 子項「取消先停止新工具 dispatch」在指定 contextual executor/第二工具不執行案例 PASS；「真正 UI 接收端沒有 late output」FAIL。Compatibility 的真選用 provider/GUI/GPU、product-session rollout 及實際 rollback NOT VERIFIED，沒有因模型 fixture 通過而補成 PASS。

## 7. Issues / Severity / Required fixes / Optional improvements

### I1 — HIGH / P1：已排隊工具事件在取消 terminal 後送達

Evidence：gateway.py:141 writer 在 urgent 連送 4 筆後挑 normal；tool events 使用 urgent，integrated.py:720 terminal 使用 normal。取消只在 producer 端 fence，queue 裡事件不帶可用於此處淘汰的 run/epoch gate。前端 index.html:92–93 無条件消費。

Reproduction：合成 model 產生 10 個 calls；9 個完成、第 10 個等待 cancel token。socket 首筆 snapshot 暫停，使正常容量內事件排隊；取消後放行 socket。production writer 送出 terminal 後仍送出 18 筆舊工具事件。未 overflow、未改 production queue，測試使用預設 urgent 32/normal 256；不是真瀏覽器測試，也不是實際 OS 再執行。

可重跑：`.venv/bin/pytest -q -s docs/runtime-evolution/verification/RT005_2026-10-01/test_independent.py`。預期目前 exit 1。完整 payload 種類順序在 log。

Required fixes：在最終送達/consumer 邊界建立 run/generation terminal fence 或安全的事件排序/清除機制，避免舊工具狀態復活；保留單 writer、有界佇列、公平性及公開協定相容。加入 production ClientChannel + buffered/slow socket cancel regression，驗證 manual/auto 路徑與不同 queue 排序；不能只將 terminal 改 urgent 就聲稱保證成立。本輪不提出或套用實作 patch。

來源判斷：writer 仲裁、工具 urgent 與 terminal normal 並非 RT-005 新增；屬本輪揭露的既有整合缺口，仍直接阻擋 RT-005 的明文 acceptance。

### I2 — MEDIUM / P2：completion-first race test 一次 timeout

Evidence：首次 74 pass/1 fail（[保留摘要](initial-run-summary.txt)）；test_agent_batches.py:187 等 entered 2s timeout；單獨及同 suite 重跑 PASS。未證明 production defect，未找到 root cause，不把失敗抹去。

Required fixes：保留首次失敗，定位當次 task exception/卡住位置、iteration 與 I/O/排程因素，讓 race gate 有可診斷、可重現的穩定結果；若調整時間限制，需區分 fixture 啟動等待與 acceptance 2 秒停止門檻，不能放寬產品門檻掩蓋問題。

Optional improvements：針對已宣告 RAM-only guards 的長 session retention 建立後續量測；補真選用 provider + UI + foreground process 取消 walkthrough、active-main shutdown、實際 profile rollback 演練。detach session teardown、escaped daemon、Qwen/browser lifecycle 維持原獨立 task 範圍，不藉驗證擴張 RT-005。

## 8. DONE 與 rollback 決定

**不保留 DONE；建議 FAILED_VERIFICATION。** 程序清理兩項已通過，不能抵銷 late UI acceptance 的確定失敗。不是 BLOCKED：反例不需要外部硬體或憑證；不是 REGRESSION_DETECTED：未建立 RT-005 新引入因果證據。roadmap 本輪未修改。

rollback 的 current patch 可逆、before source hashes 已核對；未切換實際 runtime 或回退使用者資料。若後續回退，應照卡先停接 candidate、清理所屬前景 child、確認 cleanup 結果，再讓新 Gateway 使用 legacy；不能用廣泛 pkill、重播副作用或還原私人 DB。
