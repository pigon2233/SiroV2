# RT-006 — Qwen worker lifecycle, 2026-10-01

## Selected task / why

讀取roadmap全部RT-001–015及migration/spec/compatibility/baseline；RT-001–005 DONE，排序最前未完成RT-006依賴RT-001已滿足。selection.json記錄施工前狀態。只實作RT-006，未開始RT-007。

## Intent / actual callers / discrepancy

原QwenReferenceTTS沒有close或response ID；startup讀取前未持有process，EOF丟掉pointer、render timeout後可重用旧pipe。main選QwenReferenceTTS，HTTP /v1/audio/speech直接await render，lifespan原先只清turn/hub。更正（2026-10-01獨立驗證）：當時Frontend取消按鈕並未abort TTS fetch。candidate route監看http.disconnect僅證明實際斷線時可取消render，不能證明按鈕已接入。UI caller缺口與人工相容性gate使RT-006應為PARTIAL。未新增endpoint/payload、未改Core/對話/角色算法。

roadmap的「new behavior candidate」落實為constructor optional lifecycle=False，main取同一startup runtime_profile。私有worker JSONL加request_id/epoch，worker仍接受無ID舊請求；render bytes介面、語音生成參數、cache digest與WAV格式不變。原reference/model/Live2D不可改，reference前後SHA一致。

## Files changed / implementation

- src/siro/services/audio/tts.py：candidate單lock owner，request UUID/epoch驗證；最多8個active+waiting request；startup所有階段持有child，timeout/cancel/EOF/error/mismatch kill/wait。spawn取消仍取得handle再回收，cleanup shield避免重複取消遺失ownership。cleanup失敗保持poisoned、不重用或dispatch。close拒絕新candidate render，取消active、等待lock及reap。legacy render private protocol保持。
- scripts/qwen_tts_worker.py：僅在success/error reply echo optional identity，不改模型/voice/generate/cache演算法。
- src/siro/services/presentation/gateway.py：main固定profile也注入Qwen；candidate HTTP disconnect/task cancel傳到render；lifespan finally close Qwen、finally清hub。legacy也增加已owned worker的shutdown close；沒有把legacy故障路徑偷換為candidate。
- tests/integration/test_qwen_lifecycle.py：14 cases，真subprocess fake worker故障矩陣、concurrent8單worker、startup取消、manual task取消、有界等待、active lifespan shutdown、legacy、main constructor接線、真ASGI disconnect取消、cleanup故障禁止重用。
- DECISIONS D17、CONTRACTS、STATUS、roadmap與本evidence。

來源精確增量見implementation.patch，before/source-digests.json；未用全repo dirty diff冒充本卡變更。保留全部原dirty修改。

## Tests run / regression results

| Command | Result | Evidence / boundary |
|---|---|---|
| `.venv/bin/pytest -q tests/integration/test_qwen_lifecycle.py` | 14 passed，1.83s，exit0 | task-final.log；真child/ASGI，模型為fake |
| `.venv/bin/pytest -q tests/integration/test_qwen_lifecycle.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/test_audio_pipeline.py tests/contract/test_audio_protocol.py tests/integration/test_body_failure_isolation.py tests/integration/test_integrated_companion.py` | 46 passed，4.08s，exit0 | related-final.log |
| `.venv/bin/pytest -q` | 251 passed、5 skipped，47.03s，exit0 | full-suite-final2.log |
| `.venv/bin/ruff check src tests scripts/qwen_tts_worker.py` | PASS | ruff.log |
| `.venv/bin/mypy` | PASS，170 files | mypy.log |
| `.venv/bin/ruff format --check`（四個本卡Python files） | PASS | 四檔已format |
| `.venv/bin/python docs/evidence/RT-006/measure_gpu.py` | PASS，exit0 | gpu.log；真Qwen/RTX3050，合成文字、temporary cache，不存audio進evidence |
| qwen環境torch CUDA probe | True，RTX3050 Laptop GPU | cuda.log |
| `git apply --check --reverse docs/evidence/RT-006/implementation.patch` | PASS | source rollback dry check，沒有實際部署回退 |

全套5 skips仍為3 model/2 Groq speech opt-in；不算真provider PASS，未讀key或新增外送。文字/工具/cancel/session/profile/body/audio受影響fixtures PASS，含RT-005真writer排隊取消回歸。未改Rust未跑Rust。full-suite.log/final.log為较早版本；以final2為最終source gate。

开发失敗：第一次fake worker不認識prepare_spoken_text既有補句尾標點，7 assertions失敗；修fixture處理既有標點，不改production文字準備。一次相關命令錯寫不存在test_audio.py，exit4/no tests，修成現有test_audio_pipeline.py再跑，不當PASS。mypy起初指出closure stdin optional，固定捕获已驗證stdin後通過。

## Acceptance criteria

| Criterion | Verdict | Evidence |
|---|---|---|
| request無錯配 | PASS（指定矩陣） | mismatch/epoch/EOF/error/timeout拒絕+reap+restart、concurrent8；success/error實際workerGPU配對成功 |
| 無owned殘留 | PASS（指定矩陣） | startup timeout/fail/cancel、render cancel/failure、真ASGI disconnect、active lifespan、GPU old/final reaped |
| 單GPU worker | PASS（單Gateway adapter owner） | 同lock concurrency8僅一PID；真GPU兩次render同PID，先reap舊PID再restart；不宣稱跨多個另啟Gateway instance的global broker |
| v1 reference／WAV相容 | PASS（資產、演算法與格式） | reference SHA前後相同；仍相同voice/generate/cache；GPU輸出WAV/PCM16/24000Hz；cache/restart audio hash相同 |

真GPU冷啟動+首render25.700s；第二次cache hit0.00218s；取消0.2773s；old reaped=true、restart不同PID、final reaped=true。這些是本次樣本，非p95效能承諾。measure在最後加poisoned錯誤隔離/HTTP disconnect guard前執行；正常GPU生成程式未再改，追加guard由最終全套覆蓋。

## Remaining issues / architecture deviations

- 未做人工聽測、真Live2D畫面、外部模型整合；不宣稱聲音更自然或產品發布完成。
- cancel是render task/HTTP client disconnect，而非新增session-wide TTS broker；不存在的global voice owner不在本卡重設計。HTTP取消路徑已真ASGI驗證，尚無真GUI操作驗收。
- 單adapter owner；多個另啟Gateway process各自owner，不提供跨進程GPU租約。
- cleanup最多5秒wait；若signal/OS異常無法回收明報且poisoned隔離，不能保證kernel永遠可中斷。subprocess spawn本身的kernel延遲仍不設虛假硬實時保證。
- legacy timeout/startup失敗路徑保留以符合candidate遷移策略；只有成功owned worker在shutdown取得close。不要宣稱legacy也全面修復。
- queue滿額adapter明報RuntimeError；HTTP維持原generic speech failed 502與文字退路，未改public error schema。
- rollout/rollback部署演練未執行；已驗active Gateway lifespan但不是正式長時間server shutdown/GPU多client soak。

無額外architecture redesign。必要HTTP disconnect接線為同卡cancel path；main將既有profile讀取提前讓TTS/controller/executor使用同一startup值，無新config格式。

## Rollback method

停止candidate新增render，await close回收owned worker；停Gateway、核對source-digests，再reverse-check本卡implementation.patch並reverse apply，只撤本卡source/test增量，不回退其他dirty工作。舊worker script相容無IDrequests；切回legacy時不讓新舊worker同跑，不恢復中途請求。DB/config/reference/模型無變動。文件保留歷史，回退後task回PARTIAL。只做reverse dry check，未實際部署回退。


## Independent verification correction

原DONE聲明撤回；人工音色／畫面／取消未驗，reference hash/格式不能替代。詳verification/RT006_2026-10-01/REPORT.md及frontend-cancel-fix修後證據。
