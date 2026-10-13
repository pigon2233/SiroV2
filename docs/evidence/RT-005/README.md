# RT-005 completion — 2026-10-01

## Selected task / intent

RT-005 run cancellation 傳到程序。讀取全部RT-001–015 status/dependencies，RT-001–004 DONE；RT-005是排序最前且RT-003/004依賴均滿足的未完成卡。只實作RT-005，RT-006以後未開始。根據F03、migration/spec/compatibility/baseline及既有caller source核對。

目標：取消先封鎖新dispatch，停止owned foreground process group；有界cleanup，late assistant/tool UI fence。Acceptance：controlled child 2秒停止、cleanup failure 5秒內明報、100 cancellation/completion交錯無late UI。禁止碰其他session/使用者程序、Rust grants、schema/state/config公開格式及原角色/音色。

## Actual runtime / implementation

main Gateway startup profile保持RT-004固定。candidate run建立ExecutionContext，proposal綁定run/session/epoch/token/call/proposal；ToolOrchestrator仍支援原arguments-only executors，新增optional contextual_executors。approved→running後才傳authorized metadata；Gateway原argv/cwd/timeout/detach/privileged/shell/env檢查不變，timeout轉monotonic deadline。context只RAM，不新增migration/enum/HTTP欄位。

foreground helper用start_new_session取得owned PGID。token或deadline/直接task取消觸發TERM→250ms grace→KILL、持續drain、wait/reap直接child。group leader已退出仍清理該group的pipe持有後代；不按名稱掃描/pkill、不信模型提供PID。cleanup自身最多4.5s，cancel_run最多4.75s；重複task取消不放棄已取得的process ownership。無hidden fallback或side-effect retry。

IntegratedCompanion先唯一terminal claim阻擋UI/新dispatch，cancel_run傳token並等待executor cleanup，cleanup失敗以現有FAILED/error=ExecutionCleanupError顯示；cancelled proposal以既有FAILED/ExecutionCancelled記錄。late結果不進下一model round。manual HTTP approval也依proposal的cancelled context抑制tool_result。

Gateway candidate cancel callback以既有turn_id從active_turns映射session，指定turn A不能取消B；unknown ID不殺任一run。既有explicit active alias保留全active取消，legacy行為保留。owner/global stop與service shutdown不等同任意使用者程序掃描。

## Files changed

Production：
- src/siro/services/tools/execution.py：ExecutionContext/errors、token/deadline、owned group cleanup。
- src/siro/services/tools/orchestrator.py：optional contextual dispatch、run/proposal binding、cancel wait/fence。
- src/siro/services/presentation/integrated.py：run/proposal context接入、cleanup前terminal claim、session定向cancel。
- src/siro/services/presentation/gateway.py：context/deadline executor composition、manual output fence、turn/session mapping。

Tests：新增tests/integration/test_execution_lifecycle.py。文件：DECISIONS D15、CONTRACTS、STATUS、RUNTIME_EVOLUTION_ROADMAP與本evidence。保留全部原dirty修改。

before-digests.json / source-digests.json及implementation.patch保存本卡source/test精確增量，不用全repo dirty diff冒充task scope。原before copies已轉patch，未保存私人runtime/DB/key。

## Discrepancy / architecture deviations

roadmap沒有列Gateway，但真main backend注入、manual approve late-output及turn/session路由必須修caller；記錄為本卡必要範圍。沒有public endpoint/payload破壞、mass rename/move、Hermes dependency或Core OS coupling。

Detach沿用原started/pid/argv契約：ack前取消cleanup；ack後應用交付給既有session/使用者管理，run取消不殺。**現行沒有session teardown hook，未實作detach自動session-close cleanup。** 這是相容性保留與設計中managed run/session lifetime的限制，不宣稱新的GUI ownership manager完成。

## Tests / results

- 最後task-specific `.venv/bin/pytest -q tests/integration/test_execution_lifecycle.py`：14 passed，2 dependency deprecation warnings，13.23s，exit0。
  - 真parent/fork-child cancel、timeout、direct task cancel；TERM-ignoring child、direct child reap，unrelated process存活。
  - pre-cancel/deadline不dispatch；ack前/後detach；permission failure與signal no-effect的cleanup timeout。
  - 真Core/SQLite/Orchestrator/helper取消，第二工具不dispatch；context IDs/authorized metadata。
  - 真main組裝+ASGI HTTP cancel兩session，A stopped/B alive/unknown不殺；synthetic provider/uvicorn server，非真模型。
  - manual HTTP approve執行中cancel，零late tool_result；cleanup failure到run DB/UI terminal。
  - 100 context-aware完成/取消scheduler交錯，零late assistant_delta/tool_started/tool_result、單terminal、零排隊後續dispatch。此矩陣使用合作式synthetic executor，不宣稱100真OS程序/任意race窮舉。
  - delayed spawn + repeated task cancellation，真child仍reap。
- 相關gate（新增最後spawn測試前）：`.venv/bin/pytest -q tests/integration/test_execution_lifecycle.py tests/integration/test_bounded_execution.py tests/integration/test_tool_orchestrator.py tests/integration/test_agent_batches.py tests/integration/test_gateway_main.py tests/integration/test_gateway.py tests/integration/test_integrated_companion.py tests/integration/test_conversation.py tests/integration/test_computer_driver.py tests/integration/test_sqlite_store.py`：74 passed，3 warnings，45.96s，exit0。
- 全套gate（新增最後spawn測試前）：`.venv/bin/pytest -q`：229 passed、5 skipped、3 warnings，48.56s，exit0。新增最後測試後只重跑完整task-specific14case，不宣稱全套230已重跑。
- `.venv/bin/ruff check src tests` PASS；`.venv/bin/mypy` PASS（168files）；五個task source/test format check PASS。
- 5 skip仍為opt-in真model/speech provider；沒有讀key或外送真provider，不算真服務PASS。Rust未修改未重跑。body/identity/memory/relationship等完整fixture gate沒有regression，真視覺/音色/GPU未驗。

Development failures也保留事實：初版asyncio.wait使用預設ALL_COMPLETED，導致cancel需等timeout，被真程序測試揭露；改FIRST_COMPLETED後通過。獨立測量的/proc exists/read競態曾ProcessLookupError，修measurement/test observer為捕捉程序已消失，不放寬2秒門檻。type/lint初次錯誤已修正，沒有把失敗run當PASS。

## Measurement / acceptance

`.venv/bin/python docs/evidence/RT-005/measure_cancellation.py`：exit0，三次cleanup約0.25255/0.25229/0.25219秒；direct_child_reaped=true，descendant_stopped=true，見measurement.json。合成fork-child忽略TERM，由group KILL停止。後代不是Python直接child，stopped判斷含zombie狀態，不能將此解讀為Python wait/reap所有後代；直接child確實從/proc消失。init接手orphan reaping。

| Acceptance | Result | Evidence |
|---|---|---|
| owned controlled child 2秒停止 | PASS | 三次實測約0.252s，真parent/child/timeout/group test |
| cleanup failure 5秒內明報 | PASS | permission與signal-no-effect故障注入；4.5s helper/4.75s run上限；FAILED+ExecutionCleanupError到DB/UI |
| 100 races零late UI | PASS（指定fixture範圍） | context-aware合作executor交錯100次；manual真process HTTP單次並行取消；不宣稱全部race/OS程序100次 |
| 其他session/使用者程序不受指定cancel影響 | PASS | A/B真main HTTP與unrelated process fixtures；explicit active仍為明示global stop |
| legacy/fields/output cap保持 | PASS | bounded/legacy/candidate/Gateway/proposal/adapter等full fixtures；no schema/protocol change |

## Remaining issues / regression boundaries

- 只停止owned同PGID foreground group；刻意setsid離開group的daemon、特權阻止signal、kernel不可中斷狀態不能保證停止；有界failure明報，不掃描殺其他程序。
- ack detach不由run cancel清理，session teardown未接入，沿用相容行為。
- Context/epoch/fence guards僅RAM，長sessionretention與crash recovery仍RT-008；沒有journal/replay/盲目重送。
- 舊arguments-only handler相容但不會自動获得OS cancellation；candidate computer.execute真接context。browser/Qwen生命周期另卡。
- token/deadline有效executor擁有handle後cleanup有界；delayed spawn repeated cancellation已驗，不宣稱kernel創建程序永遠可中斷。
- 100合成交錯及單次真HTTP控制不等同真模型/可視GUI/voice/24h soak驗收。

## Rollback

先停止新增candidate run，透過已知turn或active明示停止其owned foreground child，確認cleanup結果後讓新Gateway以legacy啟動；不接續中途run、不重播未知副作用、不pkill。

需要撤回本卡source/test：先核對source-digests且停止服務，`git apply --check --reverse docs/evidence/RT-005/implementation.patch`已exit0檢驗可逆；確認後可用同patch --reverse，只撤此卡不碰其他dirty工作。**本輪未實際撤回/部署rollback**，dry check不是真部署演練。DB沒有變更，不需還原資料。文件completion另留歷史或手動回標。
