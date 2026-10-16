# RT-005 Independent Reverification — 2026-10-01

**Final verdict：VERIFIED_WITH_MINOR_ISSUES。建議保留 roadmap 的 RT-005 DONE，限本卡受控程序及合成 runtime/transport fixtures 的驗收範圍。**

前輪 FAILED_VERIFICATION 是修補前的有效歷史結論；本輪重新讀取當前 source、契約、task 與測試，未直接採信修補報告。原 writer 反例已通過，未在本輪相關 regression gates 發現 regression。這不是正式部署、真模型、GUI/GPU 或全部 runtime 能力完成的結論。

本輪沒有修改 production code、既有 tests、roadmap 或 private runtime data；只新增本目錄的報告、log、provenance 與 source snapshot。

## 1. Identify target / reconstruct intent

Roadmap 當前 RT-001–005 DONE，RT-006–015 PLANNED；最新完成卡仍為 **RT-005 run cancellation 傳到程序**，包含 2026-10-01 delivery-fence 修補。沒有開始 RT-006。

依據：RUNTIME_EVOLUTION_ROADMAP 的 Objective / Problem / Audit evidence / Scope / Acceptance / Compatibility / Tests / Rollback；ARCHITECTURE_FRICTION_MAP F03；RUNTIME_EVOLUTION_SPEC 的 run cancellation、executor/process-group 與有界 cleanup；COMPATIBILITY_PLAN；REGRESSION_BASELINE；CONTRACTS RT-005；DECISIONS D15/D16；STATUS/SOL_RUNBOOK 與 AGENTS。前輪報告用於重現歷史反例，completion/repair README 用於比對其聲明，不用作 PASS 的唯一證據。

- Objective：取消先停止新 dispatch，再清理 owned foreground process group；晚到結果不得復活 UI。
- Problem：舊取消只到 LLM/body，executor 沒有 process handle/token。
- Scope：execution、orchestrator、integrated；Gateway 為必要 caller。新增 writer/frontend consumer fence 為本卡 zero-late-UI 邊界，並非其他功能開發。
- Acceptance：受控 child 2 秒停止；cleanup 失敗 5 秒內明報；100 races 零 late UI。
- Compatibility：舊 arguments-only handler、授權 defaults、HTTP routes/required fields、observation/state/config/schema 不變；缺省 legacy、candidate opt-in、profile 固定。optional WS stream_id 為已允許 metadata 增量。
- Tests：parent/fork-child、timeout、完成/取消、無關程序、legacy/candidate、error/manual/auto paths；修補加真 writer 100×2 排隊優先序與實際前端 JS。
- Rollback：停止新 candidate run，先清理 owned child，再讓新 Gateway 使用 legacy；禁止廣泛 pkill、接續半途 run 或重播未知副作用。修補撤回要回標 FAILED_VERIFICATION。

## 2. Actual code / runtime path

| 檢查 | evidence 與判定 |
|---|---|
| 實作存在、非 stub | execution.py:24 ExecutionContext、:47 cleanup、:79 execute_bounded_argv；真 spawn/drain/TERM/KILL/wait，沒有用 TODO/pass/NotImplemented 代替功能。exception docstrings 不是 stub |
| caller / runtime 使用 | integrated.py:209 start_run、:632 bind_proposal → orchestrator.py:253 contextual dispatch → gateway.py:1158 contextual executor registration、:1104 candidate branch、:1115 bounded argv。main HTTP 真程序 fixtures 通過 |
| cancellation/deadline/epoch | shared token、monotonic deadline 實际使用；epoch 是 run_id metadata，並非 durable epoch protocol。producer terminated gate 与每次 run context 隔離晚到结果；RAM-only 不等於重啟恢復 |
| owned process group | start_new_session=True、killpg(process.pid)，TERM→250ms→KILL；直接 child wait/reap，持續 bounded drain；helper 4.5s / run wait 4.75s，cleanup failure 明報 |
| 新 dispatch fence | cancel_run 第一個 await 前取消 token；context.check 在 executor dispatch 前；controller terminated gate 阻擋第二工具/continuation。相關測試真正執行此 production path |
| writer 真啟用 | candidate controller constructor 呼叫 hub.enable_terminal_fencing；既有 channel 同時啟用，新 channel 從 hub 繼承；沒有僅新增可選 class 卻忘記 caller |
| delivery identity | integrated.py:155 _broadcast_stream、:168 建固定 UUID；run/proposal/continuation 使用同 stream；:712 捕獲並清 mapping，:740 terminal 使用捕獲 ID，沒有清除後換 ID 的 detached path |
| manual events | hub.broadcast 依 proposal_id 加 stream_id；HTTP approval 在執行前後仍檢查 is_fenced（gateway.py:624、:630），取消後不新增 manual result。已有 queue events 在入 queue 時取得 ID |
| writer / frontend consumer | ClientChannel 唯一 writer 在送出 terminal 後淘汰同 stream progress/duplicate terminal；index.html:65 createTerminalFence，onmessage 在 log/render/tool/TTS 前套 fence。新 stream/其他 session 仍通過 |
| output 真被使用 | proposal observation/error → SQLite/UI/continuation；cleanup error → FAILED DB/terminal。正常 frontend tool handlers 仍使用 result，fence 控制何時允許進入 consumers |
| hidden fallback / bypass | candidate main computer.execute 真有 context；legacy closure、arguments-only fallback 為明示相容路徑，browser/process.start 不是本卡 foreground cleanup。沒有偵測到執行失敗後偷轉 legacy 或 side-effect retry |
| duplicated logic | legacy argv closure 與 candidate helper 是 profile 保留，不是新增無 caller 的複本；writer/frontend 雙 fence 分別守 transport/consumer，非業務邏輯複製 |
| detach | ack 前清理，ack 後保留舊 started/pid/argv 語義；不宣稱 session teardown 已完成，也不把 detach launch 當 dead implementation |
| config 實际啟用 | main:1073 捕捉 profile，controller/backend 同值；相關 main tests 真的使用 candidate 及 legacy。當前使用者部署服務的 profile NOT VERIFIED，沒有讀 private env/key 或擅自重啟服務 |

## 3. Scope discipline / provenance

工作區包含其他歷史 dirty 修改，不能把全部 diff 歸到本卡。核對原 task + repair 最終八個 source/test digest，全部一致；在臨時副本依序 reverse repair.patch、原 implementation.patch，兩次 exit 0，所有保存 before-digests 一致。見 [provenance.json](provenance.json)。這是 byte/scope consistency 與可逆檢查，不是未提交改動的 Git 時間認證。

原 task 改 execution/orchestrator/integrated/gateway；repair 改 gateway/integrated/index.html 及兩個 test。Gateway/frontend 屬 late-output acceptance 必要邊界。沒有 mass rename/move、無關 refactor、新 dependency、Core OS coupling、Rust grants/protocol、既有 migration、角色演算法或 audio/reference 修改。

public API 的原必填欄位及 state/config 格式保持；ClientChannel 增加 optional terminal_fencing，candidate WS 增加 optional stream_id，符合 COMPATIBILITY_PLAN 並有 D16 紀錄。legacy payload 不加 metadata；沒有新 HTTP endpoint。queue capacity 與 4:1 仲裁未改。

## 4. Tests executed / test quality

**本輪 99 passed、3 dependency deprecation warnings，29.60s，exit 0；無 skipped/xfail。** 完整輸出：[relevant-tests.log](relevant-tests.log)。ruff check src tests exit 0；mypy exit 0（169 files）。沒有把修補報告的全套 237/5 當成本輪執行結果。

執行命令（同一批）：

```text
.venv/bin/pytest -q tests/integration/test_execution_lifecycle.py tests/integration/test_bounded_execution.py tests/integration/test_tool_orchestrator.py tests/integration/test_agent_batches.py tests/integration/test_gateway_main.py tests/integration/test_gateway.py tests/integration/test_integrated_companion.py tests/integration/test_conversation.py tests/integration/test_computer_driver.py tests/integration/test_sqlite_store.py tests/integration/test_gateway_terminal_fence.py tests/contract/test_body_adapter.py tests/integration/test_body_failure_isolation.py tests/test_audio_pipeline.py tests/contract/test_audio_protocol.py tests/test_config.py tests/integration/test_runtime_boundary.py docs/runtime-evolution/verification/RT005_2026-10-01/test_independent.py
```

- **真程序**：全部 14 lifecycle cases 在本輪執行。包含 parent/fork-child、TERM-ignore、timeout/task cancel、直接 child reap、unrelated process 存活、pre-cancel/deadline、detach ack 前後、delayed spawn/repeated cancellation。
- **錯誤路徑**：permission/no-effect signal 故障注入；cleanup error→DB/UI 使用合成 executor；兩種層級分開解讀，不聲稱 kernel 不可中斷情況已驗。
- **runtime 接入**：main 組裝 + ASGI HTTP + 真 OS child；provider/uvicorn.run 為合成替換，不等於真 network/provider E2E。auto/manual/其他 session/unknown turn ID 路徑皆執行。
- **late delivery**：重跑未修改的前輪獨立反例，通過；新 production ClientChannel test 100 次×urgent/normal terminal 兩種 priority，排隊/duplicate terminal/new stream/other session assertions 通過。不是只測 RecordingHub/mock writer。
- **consumer**：Node 直接執行從實際 index.html 擷取的函式；並確認 onmessage 在 log/render 前使用它。不是只測另寫的 JS mock，也不是完整 GUI/DOM/瀏覽器驗收。
- **regression-sensitive compatibility**：batch success/failure/denial/limits、old arguments-only handler、legacy/candidate profile freeze、text streaming、body/audio adapter、HTTP fixtures 均通過。
- **歷史 flaky**：前輪一次 entered 2s timeout 未定位精確原因；現在 prewarm/readiness 10s 與產品停止 2s 分離，監看原 task exception/iteration/stack，且補診斷 helper 測試。取消後原 2s assertion 保留，不是放寬停止門檻。本輪未重現 failure，不能推論永不 flaky。
- **未執行**：完整 repo suite、real-provider opt-in、真 GUI/GPU、active-main shutdown、deployment rollback、24h soak/Rust。既有 task/repair test files 在 testpaths=tests 內；前輪 docs 獨立測試不在 default discovery，但本輪明確指定執行，沒有漏算成「自動已跑」。

## 5. Relevant REGRESSION_BASELINE

| baseline / 受影響行為 | 判定 | evidence / 限制 |
|---|---|---|
| conversation/streaming | PASS | Core/SQLite + synthetic model、HTTP fixtures；真 main+provider+browser delta NOT VERIFIED |
| tool calls / continuation / batch / denied / old executor | PASS | orchestrator/batches/integrated/Gateway tests |
| cancellation/timeouts / owned process cleanup | PASS | 真 parent/child/timeout/reap 與 error-path cases；不保證 escaped daemon |
| cancellation / late UI delivery | PASS | 原獨立反例 + 100×2 production writer + actual JS consumer；不是任意 race 窮舉 |
| session A/B / unknown ID cancellation isolation | PASS | main HTTP 真子程序 A stop/B alive/unknown 不殺；完整多分頁 UI 未驗 |
| PC control / bounded output / main binding | PASS | bounded flood/cap/nonzero/timeout/main fixtures；本輪未另量測 RSS/readback GUI |
| config / profile freeze / authorization compatibility | PASS | config/orchestrator/Gateway/main tests；JSON/env effective-config 系統整合仍 RT-007 |
| body/audio protocol / cancellation / failure isolation | PASS | contract/body/audio fixtures；真音色、gesture、GPU NOT VERIFIED |
| shutdown 既有 hub/callback 與 idle main | PASS | Gateway/main 既有 fixtures |
| active-main executor shutdown / Qwen lifecycle | NOT VERIFIED | 沒有這個 E2E；Qwen lifecycle 屬 RT-006 |
| restart active-run recovery / deployment rollback | NOT VERIFIED | RAM guards；兩層 patch 在臨時副本可逆不等於部署演練 |

未在上述已執行範圍發現 FAIL 或新 regression。其他 devices/Rust/長期 memory 子系統不屬本輪變更，不用全功能結論覆蓋其未驗狀態。

## 6. Acceptance criteria

| roadmap criterion | 判定 | 本輪 evidence |
|---|---|---|
| 受控 child 2 秒停止 | **PASS** | cancel/timeout/task_cancel 的真 parent/fork-child、TERM-ignore、reap 與 controller cancel assertions 全部通過。停止後直接 child 已 reap，其他程序存活 |
| cleanup 失敗 5 秒內明報 | **PASS** | permission/no-effect 故障注入測試確認 <5s + ExecutionCleanupError；controller fixture 確認 FAILED/error 到 DB/terminal；cleanup code 4.5s/run wait 4.75s |
| 100 races 零 late UI | **PASS（指定 fixture 範圍）** | context races 100、completion/cancel 各 100、writer 排隊 100×2、原獨立反例及 actual frontend JS；修補前 queued late events 在本輪反例已被抑制 |

Objective 的「停止新 dispatch」「只清理所屬群組」有實際程序/第二工具未執行/session 隔離證據。不能將上表延伸為 escaped daemon、真模型/可視 GUI、worker/crash recovery 或任意 kernel/spawn delay 的保證。

## 7. Issues / Severity / Required fixes / Optional improvements

1. **LOW：歷史 entered timeout 精確根因 NOT VERIFIED。** 診斷與 readiness 隔離已實際接入，2 秒停止門檻保持，當前 gates 全通過。因此不是已重現 production defect，不再保留前輪 HIGH late-UI 問題為當前 failure。若再發生，需保留原 task exception/iteration/stack 並定位，不能直接調寬產品門檻。
2. **LOW：RAM guards 的長 session retention 仍未界定。** writer/frontend 新 fence 有容量界線，event_streams 會清除；但 orchestrator run/proposal contexts、controller terminated/seen guards 仍保留，非 durable recovery。此限制已在原 task 明列，沒有本輪測得的短期 regression；可安排後续 retention/cleanup 設計及量測，避免借驗證擴張本卡。
3. **驗證限制：真 provider/GUI/GPU、active shutdown、deployment rollback NOT VERIFIED。** Node actual consumer 與 synthetic port 不等於可視產品體驗。這些是未驗證條件，不是假定存在 production failure。

**Required fixes：本卡目前未發現阻擋已定義 fixture acceptance 的必要 production 修正。** 保留歷史超時與未驗證條件，不把 DONE 描述成正式部署/全功能驗收。

Optional improvements：一次真 provider+UI+foreground-process cancel walkthrough；active main lifespan cleanup 測試；實際 profile rollback rehearsal；長 session guard retention 量測。GUI/voice/Qwen/escaped daemon/recovery 維持各自 task 範圍。

## 8. Verdict / roadmap / rollback

**VERIFIED_WITH_MINOR_ISSUES；建議保留 RT-005 DONE。** 理由是三項明文 task acceptance 已重新執行，歷史 late-output 反例已修復，相關 baseline 沒有觀察到 regression。上述 LOW 與 NOT VERIFIED 限制仍保留，故不使用無保留 VERIFIED。

前輪 `RT005_2026-10-01/REPORT.md` 保留原 FAILED_VERIFICATION，不覆寫歷史。本輪未修改 roadmap。

rollback：兩層 source/test patch 已在隔離副本依序 reverse 並核對 before digests，資料/schema 不需要還原；沒有在使用者工作區真正回退或切換服務。撤掉 repair 會重新暴露原 late-UI failure，必須回標 FAILED_VERIFICATION；服務 rollback 仍要先停止新 candidate、清理已知 owned foreground child，再啟動 legacy 給新 run，禁止 pkill/重送未知副作用。
