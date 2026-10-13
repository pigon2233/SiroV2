# RT-006 acceptance follow-up — 2026-10-02

## Selected Task / Why this task was selected

RT-006 Qwen worker生命周期。selection.json核對全部RT-001–015；RT-001–005 DONE、RT-006 PARTIAL且依賴RT-001滿足，因此仍是排序最前未完成卡。不跳RT-007。

## Current implementation / callers / risk

QwenReferenceTTS candidate已實作request_id/epoch、bounded queue、startup/render cleanup/close；worker echo identity。Gateway main固定profile注入，speech HTTP監看disconnect並取消render，lifespan close。實際index.html stopTts由cancel button/新speech/新turn呼叫；generation fence擋late結果。真runtime callers已存在，非detached stub。

roadmap原「Current implementation無close/response id」是原始稽核描述而非現在code，這一輪補標原始基線及當前candidate狀態。未新增production功能，避免已修部分重作及無關refactor。模型/reference/Live2D/Core/state/config不得改。

## Files changed / Implementation summary

只更新roadmap、STATUS與本輪evidence；production/test code不改。RT-006保留PARTIAL，剩owner人工聲線、聽覺停止與畫面相容性回報，不以自動測試或前一日GUI screenshot代替。

## Tests run / Regression results

- `.venv/bin/pytest -q tests/integration/test_frontend_speech_cancel.py tests/integration/test_qwen_lifecycle.py tests/integration/test_gateway_terminal_fence.py`：25 passed，2.35s，exit0；tests.log。实际前端Node、真子程序fake worker/ASGI、Gateway writer相關fixtures。
- `.venv/bin/ruff check src tests`：exit0 PASS；ruff.log。
- `.venv/bin/mypy`：exit0 PASS，171 source files；mypy.log。
- `curl -fsS --max-time 2 http://127.0.0.1:8000/health/live`：exit0，state=alive。前一輪隔離candidate驗收服務可用。

本輪沒有code改動，不重跑完整repo/真GPU/外部provider。前一輪257 passed/5 skipped及GPU/GUI結果是歷史證據，不稱本輪執行。未外送私人資料/key，保留dirty tree。

## Acceptance criteria / Remaining issues

| criterion | current evidence | remaining |
|---|---|---|
| request無錯配 | 指定自動矩陣PASS | 非任意race窮舉 |
| owned回收 | 指定fake-worker/ASGI/shutdown矩陣PASS；GPU歷史PASS | 本輪未再跑GPU |
| 單worker | 單adapter並行矩陣PASS、歷史GPU PID | 非跨process broker |
| v1音色/WAV相容 | format/reference歷史PASS | owner人工聲線/聽覺取消/畫面確認NOT VERIFIED |

已請owner在http://127.0.0.1:8000輸入「測試聲音」，比較聲線、播放按取消確認立即停止且不復活、確認角色正常；尚無新的明確驗收回覆。不能將「繼續實作」當作人工驗收通過。PARTIAL維持，未開始其他RT卡。

## Architecture deviations / Rollback method

無本輪架構偏離、沒有新增production diff，無需本輪code rollback。上一輪UI/worker回滾仍按各evidence scoped patch操作，先close owned worker/停新render；部署rollback未驗。不用廣泛pkill、不回退私人DB。文件可只撤本輪follow-up，但人工gate未完成的PARTIAL應保留。
