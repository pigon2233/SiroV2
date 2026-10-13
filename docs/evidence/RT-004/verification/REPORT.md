# RT-004 Independent Verification — 2026-10-01

Final verdict: **PARTIAL**. 建議 roadmap 的 DONE 改為 PARTIAL；本輪不修改 roadmap、production code 或既有測試。只有此 verification 目錄新增證據。

## Target / intent

最新 DONE 是 RT-004（RT-001–004 DONE；RT-005–015 PLANNED，同日以 roadmap 順序識別最新完成卡）。已重讀 roadmap、migration/spec/compatibility/baseline、F10/F06 與實作證據，沒有僅採信 completion report。

任務目標：Gateway computer.execute 封裝同介面候選 bounded drain；兩 pipe 持續 drain，保存總 raw cap ≤64KiB、RSS 增量目標 <32MiB、無死鎖、保留 returncode/truncated。保留 legacy callers/defaults/HTTP/WS，run 期間不得切換實作。禁止改 Rust RPC、browser、授權預設、state/config 格式。Rollback：排空 candidate，僅新 run 使用 legacy，不重播既有副作用。

## Actual code / consumer

- gateway.py:1005–1038：原 argv/cwd/timeout/detach 與權限檢查後，candidate 呼叫 execute_bounded_argv；1071 註冊到 ToolOrchestrator。
- execution.py：真 create_subprocess_exec、兩 reader task、共享 budget、持續 discard、實際 returncode；沒有 TODO/pass/NotImplemented stub，沒有失敗後偷偷改 backend。
- orchestrator.py:203–221：executor 結果存入 observation；integrated.py:461–480/663–681 消費並送回模型、傳送 tool_result。main profile 對照測試使用真 subprocess/Core/SQLite/HTTP callback；provider 和 uvicorn server 被替換。
- legacy communicate 分支刻意保留供 rollback；固定 candidate 下沒有繞過 facade。新行為不是預設啟用：缺省 legacy，必須選 candidate。沒有宣稱全部署已修復記憶體問題。
- candidate 共享 raw 64KiB，legacy 每 pipe 64KiB；D14 已記錄差異。非法 UTF-8 replacement 重新編碼可超過 raw cap，不等於 raw retention 超標。

## Acceptance / compatibility

| Criterion | Result | Evidence |
|---|---|---|
| 100MiB 保存 raw ≤64KiB | PASS | 3 次獨立實測皆 retained 65536、returncode 0、truncated true；正式 helper 真子程序 |
| Parent 額外 RSS <32MiB | PASS | 3 次 438272 / 262144 / 159744 bytes；1ms 採樣 142/157/194 次，child RSS 排除；僅本機 synthetic 範圍 |
| 兩 pipe drain 無 deadlock | PASS | 3 次 100MiB，0.200/0.226/0.328 秒；silent/flood timeout 1.007/1.004 秒 |
| 同介面、returncode/truncated、小輸出相容 | PASS | exit7、6byte boundary、legacy/candidate main observation 對照 |
| Main caller / consumer 真接入 | PASS | 真 HTTP callback→orchestrator→subprocess→native tool observation，非 detached implementation |
| 不在進行中 run 切換實作 | FAIL | profile_probe.py：candidate controller 建立後，synthetic provider 改 server 內 os.environ 為 legacy；run 完成，bounded_calls=0 |
| Public HTTP/WS / authorization default / state/config 格式 | PASS（此次局部 source+fixtures） | candidate binding 位於既有檢查之後，沒有新增 endpoint/schema；gateway/agent regression 通過 |
| 完整逐卡 scope provenance | NOT VERIFIED | dirty tree 無 RT-003→RT-004 獨立提交/diff；不能把 HEAD 全部變更歸給此卡 |

## Rerun tests / baseline

Command：`.venv/bin/pytest -q tests/integration/test_bounded_execution.py tests/integration/test_gateway_main.py tests/integration/test_gateway.py tests/integration/test_agent_batches.py tests/integration/test_integrated_companion.py tests/integration/test_computer_driver.py`

Result：exit0，41 passed、0 skipped、0 xfail、3 dependency deprecation warnings，20.39秒。7 個 task-specific parameterized cases 包含洪流、exit7、silent/flood timeout、detach、兩 profile main。沒有把 mock provider 當作真 provider 測試。未重新執行全套213測試；舊 implementation report 全套結果不是本輪結果。

`ruff check` 三個 task source/test：exit0。三個 RT-004 source digests 全部 MATCH。未重跑 mypy（不宣稱通過）。

獨立錯誤 probe：silent/flood timeout 後 PID 在 /proc 已消失；不存在 executable 明確 FileNotFoundError，沒有 hidden fallback。既有 timeout test 名稱聲稱 reap，assertion 卻僅檢查 TimeoutError；本輪獨立 PID probe 補足此證據，沒有修改既有 tests。

| Relevant baseline | Result | Limit |
|---|---|---|
| tool calls / observation continuation | PASS | synthetic model，真主組裝與 executor |
| PC execution bounded output/readback result | PASS | argv output/exit result；不是 GUI/browser readback |
| direct-child timeouts | PASS | 實際 silent/flood child 已退出 |
| profile compatibility / run freeze | FAIL | in-process environment mutation 可切換 executor |
| HTTP/session/conversation integration fixtures | PASS | 相關 gateway/integrated suites |
| process-tree / run cancellation / shutdown cleanup | NOT VERIFIED | RT-005 範圍，不從直接 child 測試推定完成 |
| real model/UI/voice/hardware / deployment rollback | NOT VERIFIED | 此卡未真服務驗收；legacy 新組裝是切換 smoke，不是 active-run rollback rehearsal |

## Issues / severity / fixes

1. **MEDIUM：profile 未固定。** gateway.py:1032 每次 dispatch 讀 os.environ，controller 在1081讀取的是建立時 profile。已用隔離 production-main test 重現二者分歧。一般外部 shell 改環境不影響既有 server；觸發條件是 server 內部 mutation。即使目前沒有公開切換 API，仍不符合明文 run freeze 要求，且可能把後續大量輸出導回 legacy communicate。
   Required fix：後續實作輪固定 executor profile/binding，避免在每次 dispatch 重讀 mutable process env；增加 run 中 profile 變動仍使用原 executor 的 regression test。只建議，不在本轮修正。
2. **LOW：timeout test 沒 assert reap；RSS 是採樣而非連續峰值。** Optional：把 PID disappearance assertion 納入必要測試；增加持續雙 pipe concurrent writer/invalid UTF-8 fixture。三次實測未發現 flaky，但不能證明零 flakiness。
3. **LOW：scope provenance 不完整與設計文件 stale。** Spec/migration/compatibility 仍有「尚未實作」字樣。Optional：逐卡保存 before/after diff/digest，更新歷史設計狀態說明，避免把整個 dirty diff 歸於 RT-004。

沒有在可歸屬 RT-004 的 facade/binding 發現 mass rename/move、unnecessary refactor、Rust/browser 改動、state/config/public API break 或新 package dependency；精確逐卡排除其他 subsystem 變更仍受 provenance 限制。Facade 僅依賴 asyncio/Path，controller 未增加 OS 依賴。

## Verdict / roadmap / rollback

**PARTIAL**：核心有界輸出目標通過，明文相容要求 run profile freeze 失敗。未觀測固定 legacy profile 的 regression，不使用 REGRESSION_DETECTED 當總判定。DONE 不應保留，建議改 PARTIAL，修正並重新驗證 freeze 後才恢復 DONE。

Rollback 建議維持原方案：停止新增 candidate run，排空目前 jobs 後重新啟動 legacy；不要在 active server 內改 os.environ 作 rollback，不接續中途 run、不重播副作用。此輪未執行部署 rollback、沒有修改任何 production code。
