# RT-005 delivery-fence repair — 2026-10-01

本輪只修RT-005獨立驗證問題，未實作RT-006。歷史verification/RT005_2026-10-01/REPORT.md與原completion證據保留；本文件補充並取代原「producer fence足以證明zero late UI」的結論。

## Analysis / actual path

重現獨立test_independent.py：真GatewayHub/ClientChannel writer被snapshot阻塞，Core/SQLite/Orchestrator產生10工具batch；urgent/normal公平仲裁送terminal後仍送18工具事件。producer已排入queue的內容不能由producer檢查撤回。

candidate IntegratedCompanion.respond建立固定UI stream UUID；工具propose/auto execution/continuation/terminal沿用ID。GatewayHub以proposal→stream關聯補上HTTP手動事件；ClientChannel唯一writer送terminal後丟棄同stream queued progress及重複terminal。前端真onmessage在log/render/tool/TTS consumers之前套用同樣stream fence。legacy不啟用writer fence且不加metadata；無ID舊訊息照常消費。stream非DB run/state欄位，HTTP routes、config/DB格式未改；optional WS metadata為必要相容擴充。queue capacities與4:1公平仲裁不改。

controller active stream mapping在run完成清除。writer retired stream IDs有界（5×queue容量合計+2），frontend保留最近1024個terminal IDs；不宣稱跨重啟或任意久遠惡意訊息的永久去重。既有producer run fence仍阻止run結束後新dispatch/結果，delivery fence負責排隊內容。其他session/new stream保持送達。

競態fixture原entered等待包含Core/SQLite啟動，且不監看respond task異常。新增prewarm，entered readiness 10秒與產品取消後2秒分離；同時監看respond，原異常直接呈現，超時顯示iteration/stack並取消fixture task。原取消門檻未放寬。歷史那次2秒entered超時的精確I/O原因沒有足夠證據復原：NOT VERIFIED，不能說已定位特定production race。

## Files changed / scope

- src/siro/services/presentation/gateway.py：writer fence、candidate開關、manual proposal metadata關聯。
- src/siro/services/presentation/integrated.py：固定stream identity及傳遞。
- src/siro/services/presentation/static/index.html：consumer fence。
- tests/integration/test_gateway_terminal_fence.py：真writer100次×兩種priority、真controller buffered batch、manual關聯、直接Node執行實際前端函式。
- tests/integration/test_agent_batches.py：readiness診斷/error/cleanup測試。
- DECISIONS D16、STATUS、roadmap及本證據。

Gateway/frontend是本卡late UI acceptance所需consumer邊界，不是其他功能重構。無mass rename/move、Core OS coupling、新dependency、state/config格式改動。保留原dirty修改。

## Tests actually run

| Command | Result / evidence |
|---|---|
| `.venv/bin/pytest -q -s docs/runtime-evolution/verification/RT005_2026-10-01/test_independent.py` | 最終1 passed，1.06s；independent.log中LATE=[] |
| `.venv/bin/pytest -q tests/integration/test_gateway_terminal_fence.py tests/integration/test_agent_batches.py` | 最終15 passed，11.35s；repeat-final.log |
| `.venv/bin/pytest -q` | 最終237 passed、5 skipped，46.47s；full-suite-final.log |
| `.venv/bin/ruff check src tests` | PASS；ruff.log |
| `.venv/bin/mypy` | PASS，169 files；mypy.log |
| `.venv/bin/ruff format --check`（四個修改Python files） | PASS |
| `git apply --check --reverse docs/evidence/RT-005/delivery-fence-fix/repair.patch` | PASS；僅可逆dry check，未實際rollback |

5 skips為3 model、2 Groq speech opt-in，未呼叫真provider。Node測實際前端函式但不是GUI端到端瀏覽器。真parent/child、cleanup failure、session/main/manual cancellation、profiles、body/audio合成fixtures均在全套中重新通過。100 writer iterations每次固定阻塞snapshot後排queue，另兩種completion/cancel各100迭代：指定fixture範圍，不宣稱窮舉race或100真OS程序。

開發失敗保留：初次修正清掉stream mapping後terminal誤用fallback run ID，獨立測試仍18 late；修為捕获的同一stream ID後PASS。related.log/repeat.log的新manual測試最初假設三urgent必先於terminal，忽略正常4:1仲裁；調整fixture terminal在normal queue以確立順序，未改仲裁或產品門檻。full-suite.log是早期235pass版；以final237pass版本為準。

## Acceptance / regression

| Item | Result | Evidence |
|---|---|---|
| controlled child停止<2秒 | PASS | full suite含execution_lifecycle真程序cancel/timeout/reap tests |
| cleanup failure<5秒明報 | PASS | 同suite故障注入、DB/terminal FAILED/error tests |
| 100 races zero late UI | PASS（合成排隊場景） | 100×2真writer排隊、controller runtime批次、原獨立反例、實際consumer JS |
| text/tools/session/profile compatibility | PASS（fixtures） | 全套及新stream/其他session送達assertions |
| body/audio | PASS（fixtures） | 全套合成adapter/audio tests；真GPU/GUI聲音未驗 |
| historical flaky timeout exact cause | NOT VERIFIED | 原報告只有首次超時摘要；診斷與readiness隔離已補 |
| real provider/GUI/GPU、active shutdown、deployment rollback | NOT VERIFIED | 本輪沒有這些驗收 |

## Rollback / limitations

先停止candidate新run並清理owned child，停服務，核對after-digests.json後對repair.patch執行reverse check再reverse apply，只撤本輪source/test增量，保留其他dirty工作。DB無變動。文件應保留修補歷史；撤回後RT-005回FAILED_VERIFICATION。此流程未實際部署演練；不要使用廣泛pkill。

RT-005三項task acceptance在現有fixture層級通過，可恢復DONE並附本修補證據；DONE不表示歷史flaky原因已定位或真provider/GUI/GPU完成。未開始下一卡。
