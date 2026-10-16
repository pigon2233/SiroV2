# RT-006 Independent Verification — 2026-10-01

**Final verdict：PARTIAL。建議 roadmap 的 RT-006 DONE 改為 PARTIAL。**

candidate adapter/worker lifecycle 已進 runtime path，故障/取消/回收與真 GPU 样本通過；但 compatibility plan 的人工音色/畫面/取消驗收仍未完成，不能將資產 hash、WAV 格式及 backend task.cancel 視作完整音色與使用者取消驗收。另獨立重現現有 UI 取消不 abort TTS request；implementation report 關於 frontend cancel-fetch 的前提不成立。沒有證據將這個既有 UI 缺口歸因為 RT-006 新引入 regression，故不使用 REGRESSION_DETECTED。

本輪只新增本驗證目錄；沒有修改 production code、既有 tests、roadmap、模型/reference 或使用者 runtime data。GPU測試使用合成文字及 temporary cache，音訊沒有保存進 evidence。

## 1. Target / reconstruct intent

重新讀 roadmap 全部 status：RT-001–006 DONE、RT-007–015 PLANNED，最新完成為 **RT-006 Qwen worker 生命周期（candidate lifecycle）**，不是前輪 RT-005。

重建依據：roadmap 的 Objective、Problem/F05、Scope、Acceptance、Compatibility、Tests、Rollback；ARCHITECTURE_FRICTION_MAP F05；RUNTIME_EVOLUTION_SPEC Qwen lifecycle；COMPATIBILITY_PLAN audio/body gate；REGRESSION_BASELINE；CONTRACTS RT-006；DECISIONS D17；STATUS、SOL_RUNBOOK、AGENTS。completion README/patch/digests 用來比對聲明及範圍，PASS 來自當前 code/測試/本輪實測。

- Objective：request 配對、失敗隔離、Gateway 關閉確實回收。
- Problem：舊 worker 無 close/response ID，timeout 後舊 pipe 可重用、startup failure/EOF ownership 不完整。
- Scope：audio/tts.py、scripts/qwen_tts_worker.py、Gateway lifespan/必要 HTTP cancel caller；禁止改 reference WAV、模型、Live2D、對話算法與 freeze zones。
- Implementation intent：request_id/epoch；startup failure 清理；close terminate/wait；取消後重建；bounded queue；不換音色/訓練/改 streaming TTS。
- Acceptance：無錯配、無 owned 殘留、單 GPU worker、v1 reference 音色/WAV 相容。
- Tests：fake worker 延遲/亂序/EOF/timeout；真 GPU render/cancel/restart；文字/工具/取消 regression 與 lint/types。
- Compatibility：candidate opt-in、legacy caller/protocol 不破壞，render bytes/public HTTP/state/config 保留。audio/body gate 明列「畫面、取消、音色人工與 audio format 驗證」。
- Rollback：drain/close 新 worker 再還原 adapter，不讓新舊 worker 同跑、不恢復中途 request、不更動 reference/DB；只撤本卡 patch，不碰其他 dirty 工作。

## 2. Actual code / wiring

| 檢查 | evidence / 結論 |
|---|---|
| code 存在、非 stub | QwenReferenceTTS 的 _render_owned/_retire/_cleanup/close 有真 subprocess、lock、kill/wait；沒有用 TODO/pass/NotImplemented 代替核心功能 |
| runtime path / caller | main gateway.py:966 固定 runtime_profile，:1005 建 Qwen、:1012 注入 lifecycle=candidate；render 分流至 _render_owned。main constructor fixture 真呼叫 main，但以 capture adapter 取代載重 |
| 配對 | _render_owned 生成 UUID、送 request_id/epoch、檢查 response 同值；worker.py:41 與 :65/:70 在 success/error 回覆 echo identity；不匹配/EOF/error/timeout 先清理再允許重建 |
| owner / failure isolation | spawn shield 後持有 handle；startup-read failure 也 cleanup；_poisoned+lock 防止 cleanup 未完成就 dispatch/替代；故障矩陣確認舊 PID reap、下一 request 新 PID |
| queue / 單 worker | _pending 包含 active+waiting，預設最多8；lock 序列化；concurrent8 fixture 僅一 PID。單 adapter/單 Gateway owner，不是跨多個 Gateway 的 global broker |
| Gateway close | lifespan finally 呼叫 Qwen.close，再 finally hub.shutdown；close 封鎖 candidate 新/queued render、取消 active、wait/reap。active lifespan fixture 真持有 fake worker 子程序並回收 |
| HTTP取消接線 | gateway.py:533 render_owned_speech 監看 request.is_disconnected；:568 僅 candidate Qwen 使用此路徑；disconnect/task cancellation 取消 render 並等 cleanup。真 ASGI disconnect + 真 fake worker 測試通過 |
| frontend取消接線 | **未接入**。index.html:203 speech fetch 沒有 AbortSignal；:253 取消按鈕只 POST turn cancel，沒有 abort speech fetch/停止 TTS。terminal handler 又清除 currentTurn。詳獨立 Node 重現 |
| output consumer | Qwen回 bytes→HTTP Response media_type→index.html:206 Audio；正常音訊有實際 consumer。但 backend identity 不等於 frontend current-turn/audio fence；不宣稱 UI stale speech 問題已解決 |
| detached implementation | candidate render/lifespan/HTTPdisconnect 的新方法有 caller；前端 user-cancel 不會觸發 disconnect 是 caller integration 缺口，非 wrapper 不存在 |
| legacy / hidden fallback | constructor lifecycle=False、main legacy default 明示保留舊 render；worker接受無ID request。沒有 candidate protocol failure 偷轉 legacy/retry音訊。Qwen資產缺失時 main 原有 Kokoro/Edge selection 仍在，不是本卡新增 fallback |
| duplicated logic | legacy exchange 與 owned exchange 共存為相容過渡；_ensure_worker 保留舊 path，candidate 在 _render_owned 自行掌握 spawn ownership；不是以 unused _ensure_worker 修補假稱 runtime已接 |
| config/state/protocol | 新 optional lifecycle/max_pending 不改公共 config/state；只在 worker私有 JSONL加optional request_id/epoch；public render/HTTP/WAV欄位保持。當前已部署使用者服務是否candidate NOT VERIFIED，未讀私人env或擅自重啟 |

## 3. Scope discipline / provenance

工作區包含其他未提交改動，未用全 repo dirty diff 歸責 RT-006。四個 task source/test SHA-256 均符合 source-digests；在臨時副本 reverse implementation.patch exit0，三個 production source符合 before-digests。見 [provenance.json](provenance.json)。不是對未提交紀錄時間的 Git 認證。

patch 僅 audio/tts.py、worker.py、gateway.py、新增 task test。Gateway 的 profile提前固定、HTTPdisconnect與lifespan均為必要 caller。未發現無關 subsystem修改、mass rename/move、unnecessary refactor、新 dependency、Core OS coupling、public API破壞、DB/config/state格式改動。worker音訊生成/cache/voice prompt算法未改；只增加reply identity。reference hash本輪前後一致且符合原GPU evidence。

legacy也取得成功owned worker的shutdown close，屬本卡回收目標；其timeout/startup failure弱路徑依candidate策略保留，不當成全部profile皆修復。

## 4. Tests / independent evidence

| 本輪執行 | 結果 | 層級與限制 |
|---|---|---|
| 相關 pytest suite | **78 passed**、3 dependency deprecation warnings，17.93s，exit0 | [relevant-tests.log](relevant-tests.log)；無 skip/xfail；包含全部14 Qwen lifecycle cases |
| ruff src/tests/worker | PASS，exit0 | 未更改code以通過check |
| mypy | PASS，170 files，exit0 | typed source/test gate |
| RTX3050 CUDA probe | cuda_available=True | NVIDIA RTX3050 Laptop GPU；測前無compute worker，14MiB usage |
| 真GPU measure_gpu.py | **PASS**，exit0 | [gpu.log](gpu.log)；temporary cache、真Qwen模型、合成文字，非fake推論 |
| 真frontend函式 Node重現 | **FAIL**，exit1 | [frontend-cancel.log](frontend-cancel.log)；actual playTts+onclick，pending fetch port合成；不是GUI瀏覽器 |
| isolated reverse patch | PASS，exit0 | scope可逆與before hashes一致；非部署rollback |

pytest 命令：

```text
.venv/bin/pytest -q tests/integration/test_qwen_lifecycle.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/test_audio_pipeline.py tests/contract/test_audio_protocol.py tests/contract/test_body_adapter.py tests/integration/test_body_failure_isolation.py tests/integration/test_integrated_companion.py tests/integration/test_gateway_terminal_fence.py tests/integration/test_conversation.py tests/integration/test_execution_lifecycle.py tests/test_config.py tests/integration/test_runtime_boundary.py
```

測試不是全mock：adapter真起 fake worker subprocess，測試timeout/錯ID/錯epoch/EOF/error/startup失败與取消、queue滿額/queued取消、8 concurrent同PID、close/active lifespan、ASGI disconnect/restart/cleanup失敗禁止重用。main接線fixture攔截Qwen constructor，不代表真 main載重；fake audio用text bytes而非WAV，因此音訊格式另以GPU驗證。cleanup failure是fault injection，不是實際kernel拒絕signal。

本輪GPU首次冷啟動+render **16.243s**，第二次cache hit **0.00157s**；兩次render同PID。cancel **0.29652s**；old_reaped=true，restart不同PID，final_reaped=true。WAV/PCM16/24000Hz；cache及restart音訊hash相同；reference_before/after相同。GPU前後inventory無compute child殘留。這是單次样本，不是p95/長期soak或跨多Gateway單GPUbroker。

Node重現從實際index.html擷取playTts與cancel handler；fetch合成pending speech，按cancel後記錄只有speech與turn-cancel URLs，speech_has_abort_signal=false、speech_aborted=false。測試僅驗證現有consumer code，沒有修改frontend或真的發網路請求。可重跑：

```text
.venv/bin/python docs/runtime-evolution/verification/RT006_2026-10-01/verify_frontend_cancel.py
```

14 task cases在testpaths=tests內且實際執行；沒有skipped/xfail。未重跑完整repo/real model/Groq opt-in/長時間soak/Rust；completion的251pass/5skip不是本輪結果。GPU measurement script不在default pytest discovery，本輪明確執行。未人工聽測、未真GUI/DOM/owner product session驗收；不能算PASS。

## 5. Relevant regression baseline

| baseline | 判定 | 本輪evidence / 邊界 |
|---|---|---|
| conversation/streaming與工具/取消fixtures | PASS | integrated/conversation/Gateway/execution/lifecycle與RT005 writer回歸；不是外部模型完整E2E |
| character/body/audio protocol與failure isolation | PASS | contract/audio/body fixtures；真Cubism/口型/播放未驗 |
| cancellation/timeouts：Qwen task/HTTP disconnect | PASS | startup/render/fault matrix、ASGI断線、GPUcancel/restart |
| cancellation：現有UI使用者停止→TTS request取消 | **FAIL** | actual frontend Node反例與source；既有接線缺口，不認定RT006新regression |
| shutdown：active Qwen / hub | PASS | Gateway lifespan + active真fake workerreap、GPUclose；不是正式network server長期shutdown |
| TTS GPU／WAV/reference資產 | PASS | 本輪真GPU、PCM16/24kHz、reference hash不變 |
| TTS音色人工／真GUI取消 | NOT VERIFIED | compatibility要求人工/產品驗收，非metadata可替代 |
| config/profile/public HTTP compatibility | PASS | main/profile/Gateway/config/legacytextonlyworker fixtures |
| deployment rollout/rollback、soak | NOT VERIFIED | patch reverse於副本可逆不等於部署演練 |

沒有已定位的RT006新引入regression。UIcancel缺口原frontend未在本卡修改，不能把現有失敗說成新增回歸；也不能從backend green推定產品cancel可用。

## 6. Acceptance criteria

| criterion | 判定 | evidence |
|---|---|---|
| 無錯配 | **PASS（backend指定矩陣）** | request/epoch不符拒絕，EOF/error/timeout清理重建，concurrent8序列化、真GPU回覆ID驗證；不是任意frontendaudio順序保證 |
| 無owned殘留 | **PASS（實際觸發task/HTTPdisconnect/shutdown的矩陣）** | startup/render取消/失敗、ASGI斷線、active lifespan、GPUold/finalreap。使用者UI取消沒傳到這些路徑，另列FAIL/接線缺口，不推稱已停止 |
| 單GPU worker | **PASS（單adapter/Gateway owner）** | lock+8concurrent僅1PID；GPU重複render同PID，舊workerreap後restart。跨多Gatewayglobal唯一性NOT VERIFIED/非現有設計 |
| v1 reference音色與WAV相容 | **PARTIAL** | reference資產與生成算法保持、真WAV PCM16/24kHz、bytes介面PASS；人工音色/可視播放與取消compatibility gate NOT VERIFIED |

分項：reference資產PASS；WAV格式PASS；人工音色NOT VERIFIED。沒有用「reference沒變」等同「人工音色驗收已完成」。Gateway關閉/失敗隔離objective有本輪證據；end-user cancellation接線與compatibility gate尚不足以支持無條件DONE。

## 7. Issues / Severity / Required fixes / Optional improvements

### I1 — MEDIUM：frontend取消fetch聲明不實、產品取消接線缺口

Evidence：index.html:203沒有AbortSignal；:253按鈕只POST turn cancel；terminal handler清currentTurn後仍啟動playTts。controller cancel到conversation/body，沒有cancel這筆speech render request。Node反例確認在仍有currentTurn的較有利場景也不abort；不能以ASGI人工inject disconnect通過推論使用者cancel能觸發。

Required fixes：修正completion README「Frontend取消fetch」的錯誤前提，明列實際trigger。若task交付繼續聲稱使用者取消已能清理Qwen，需以最小caller接線使現有cancel能取消對應speech request，並驗證待生成與已播放路徑；不需要藉此重設計global TTS broker。本輪不修code。此為既有整合缺口，非新regression。

### I2 — MEDIUM：音色/畫面/取消人工compatibility gate未完成

Evidence：COMPATIBILITY_PLAN audio/body gate明列人工音色、畫面、取消與audio format；本輪與completion都沒有人工聽測/真GUI。硬體生成與asset hash證據只支持結構/格式相容。

Required fixes：完成owner product session的v1聲音比對與播放/取消驗收，記錄實測證據；在這之前保留PARTIAL，不把NOT VERIFIED改PASS。若正式縮小task acceptance，需明確修改契約/roadmap的完成範圍，不能只靠implementation report自行縮限。

### I3 — LOW：測試與owner邊界

14tests沒有完整真GPU長期concurrency、重複close/spawn cancellation壓力、multipleGatewayglobal ownership或人工實際worker亂序。現有matrix先錯ID隔離，不能當任意時序窮舉。無本輪flaky/skip/xfail，但短readinesssleep等fixture不構成永不flaky證明。

Optional improvements：以barrier取代sleep-based entry；補corrupt JSON/base64/oversize reply與repeated cancel/spawn/close診斷；真GPU長期多request與active network-server shutdown、部署rollback演練。不得將這些當已發生production defect。

## 8. Verdict / DONE / rollback

**PARTIAL；不建議保留無保留DONE，建議改PARTIAL。** backend/worker主要實作有真路徑、真子程序/真GPU證據；缺口是consumer取消及明列compatibility驗收，不是整張卡不存在。沒有三次外部阻礙，不標BLOCKED；未定位新regression，不標REGRESSION_DETECTED。本輪不直接修改roadmap。

原patch在隔離副本可reverse並符合before hashes；沒有實際部署rollback。rollback仍須停止candidate新render、awaitclose確認workerreap，停Gateway後只撤本卡增量，再給新請求legacy，不能保留新舊worker同跑或恢復半途request。reference/model/DB不回退，不碰其他dirty工作。
