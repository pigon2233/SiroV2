# RT-007 Independent Verification — 2026-10-02

**Final verdict：VERIFIED_WITH_MINOR_ISSUES。建議保留 RT-007 的 DONE，限已驗證的 candidate catalog/effective-diagnostic 範圍。**

重新讀取當前 roadmap/source，而非沿用前輪 RT-006 結論。三項 task acceptance 有 production call-path、錯誤/相容性及本輪實測證據；未在相關 baseline 發現 regression。真 browser/provider 效能與部署 rollout/rollback 仍未驗，不將「可路由」解讀成所有實際後端成功。

本輪未修改 production code、既有 tests、roadmap、私人 env/DB/模型/reference；只新增本目錄的獨立測試、report、logs 與 provenance/source snapshot。沒有開始 RT-008。

## 1. Identify task / reconstruct intent

Roadmap 當前 RT-001–007 DONE，RT-008–015 PLANNED；最新完成 task 是 **RT-007 工具 catalog 與有效配置**，completion date 2026-10-02。

讀取 roadmap 所有本卡 Objective / Problem / Audit evidence / Scope / Acceptance / Compatibility / Tests / Rollback；F06；RUNTIME_EVOLUTION_SPEC catalog段；COMPATIBILITY_PLAN；REGRESSION_BASELINE；DECISIONS D19；CONTRACTS RT-007；STATUS、SOL_RUNBOOK、AGENTS。README/patch/digests 僅用於定位及比對實作聲明，PASS 來自實際 source 與本輪執行。

- Objective：一個 descriptor 驅動 schema/handler/readiness，實際 profile 可查。
- Problem/F06：既有 catalog/handler 分離、JSON config/env 分立，使用者設定與實際 runtime 限制難以核對。
- Scope：orchestrator、integrated tools、Gateway composition/diagnostic。不得改 SiroSettings 原欄位語義、Rust protocol、skills install 與共用 freeze zones。
- Implementation intent：包現有 descriptors；每 round 可用 schema snapshot、dispatch 再查 readiness；去密鑰 effective config；env priority 保留。
- Acceptance：模型 catalog 中所有可用工具可路由；tools off 不 dispatch；不泄漏 key。
- Tests：disabled/unavailable/wrong schema、full mode、legacy env parity；既有文字/工具/取消 fixtures、ruff/mypy。
- Compatibility：舊 arguments-only executors/callers、預設 full/kill switches、HTTP/WS、state/config/schema 與 startup profile 保留；candidate opt-in，legacy static path。
- Rollback：停止新 candidate work並drain，讓新run以legacy重啟；不切中途profile、不重播副作用；必要時只reverse本卡patch，不reset其他dirty工作。

## 2. Verify actual code / callers / consumers

| 檢查 | evidence / 結果 |
|---|---|
| code 存在、非 stub | orchestrator.py:101 ToolDescriptor、:111 ToolCatalog；definitions/require/snapshot 真讀 descriptors、deepcopy schemas、檢查 readiness/arguments。無 TODO/pass/NotImplemented 代替功能；test fake model/browser 的 pass 只是替身初始化/cleanup |
| descriptor 是 dispatch source | Gateway main:1224 readiness、:1231 catalog、:1255 注入 orchestrator；descriptor持有 definition/executor/contextual_executor/available/backend/effect。execute優先使用descriptor.executor，而非舊 handler map；wrong-backend sentinel fixture通過 |
| 真 model runtime | integrated.py:130 _model_tools，:365/:538 初始及continuation都取新 snapshot → Core/ModelRequest.tools → model ToolCall → catalog.require → proposal/authorization → descriptor dispatch → observation/continuation |
| dispatch readiness | propose、execute、scheduled contextual invoke 再查；tools switch false時definitions不再曝光、require拒絕，contextual task入口再查抑制排程後撤銷；不撤銷已開始的副作用 |
| error path到controller | integrated.py:613–621捕獲proposal ValueError/RuntimeError，candidate finish FAILED；execute readiness失效以既有FAILED/error記錄。獨立schema/revoked tests確認單terminal、persistent run failed、零handler effect |
| output 被 consumer 使用 | model收到可用ToolDefinition；paired tool observation含call_id回下一round；/v1/runtime由授權HTTP caller取得profile/routes/switches/tool status。未加入前端診斷頁，但「可查」不是未接caller的unused registry |
| config 真啟用 | main捕捉SIRO_RUNTIME_PROFILE並決定candidate catalog；constructor/ASGI與真獨立network startup確認catalog_enabled=true。既有port8000部署進程未改/未重啟，不宣稱它已載新程式 |
| effective config與secret | gateway.py:593 authenticated GET /v1/runtime；profile/source/catalog flag/JSON-applied flag/auth mode及明列switch/routes/tools，不dump env/settings/keys。canary/unauthorized/profile-change fixture通過 |
| detached / hidden fallback | production main candidate有catalog；舊注入式orchestrator沒有catalog時model_tools仍可用fallback，診斷catalog_enabled=false。legacy靜態alias保持，是明示相容fallback，非candidate失敗後偷降級；沒有side-effect retry |
| duplicated logic | 兩個schema從Integrated移至DEFAULT_MODEL_TOOLS，_AGENT_TOOLS僅alias；legacy handler maps仍保留但candidate執行descriptor。沒有第二份未同步候選schema；fallback存在不等於新catalog被繞過 |
| API/config/state | 新GET diagnostic是additive且有D19/CONTRACTS紀錄；舊URL/payload必填欄位/enum/observation/SQLite格式保持；SiroSettings未改 |

現有 model-visible 工具只有 browser.navigate+read / computer.execute；process.start descriptor為hidden compatibility handler，不能將它當新增model能力。browser readiness僅執行檔discovery，argv/application具體目標仍由handler驗證。

## 3. Scope discipline / provenance

工作區有其他RT與歷史未提交修改，未將全部dirty diff歸為本卡。四個source/test SHA-256均符合completion source-digests；在隔離副本reverse implementation.patch exit0，三個source全符合before-digests：[provenance.json](provenance.json)。這證明bytes/patch範圍一致，不是Git時間/作者認證。

本卡patch僅orchestrator.py、integrated.py、gateway.py、新test_tool_catalog.py。Schema constant集中是本卡消除catalog/handler分離的必要move；沒有mass rename/move、無關refactor、新dependency、Core OS coupling、Rust/skills、角色/audio/reference、DB/schema或SiroSettings改動。

跨HTTP邊界新增診斷已記契約/決策，未破壞舊public API。JSON/env沒有統一載入：json_settings_applied=false、configuration_source=gateway_env_and_defaults如實報告；不能將其稱已解決全部F06設定整合，但本卡沒有要求重設計SiroSettings。

## 4. Verify tests / actually executed

| 本輪執行 | 結果 | 層級與限制 |
|---|---|---|
| related pytest suite | **97 passed**，3 dependency warnings，35.08s，exit0 | [relevant-tests.log](relevant-tests.log)；包含全部16 task cases，無skip/xfail |
| 新獨立controller error tests | **2 passed**，1.00s，exit0 | [independent-errors.log](independent-errors.log)；schema錯/ready撤銷，真controller/Core/SQLite/orchestrator、synthetic model/handler/hub port |
| 真installed Gateway network smoke | PASS，exit0 | [main-smoke.log](main-smoke.log)；隔離data/port、offline provider、不執行工具或讀key；candidate diagnostic與tools off真network可查 |
| ruff check src tests | PASS，exit0 | source lint |
| mypy | PASS，172 files，exit0 | source/test typing |
| reverse patch於隔離副本 | PASS，exit0，before hashes一致 | 未實際部署rollback |

Related command：

```text
.venv/bin/pytest -q tests/integration/test_tool_catalog.py tests/integration/test_tool_orchestrator.py tests/integration/test_agent_batches.py tests/integration/test_bounded_execution.py tests/integration/test_execution_lifecycle.py tests/integration/test_gateway.py tests/integration/test_gateway_main.py tests/integration/test_gateway_terminal_fence.py tests/integration/test_integrated_companion.py tests/integration/test_conversation.py tests/test_config.py tests/integration/test_runtime_boundary.py tests/contract/test_model_adapters.py
```

Task16 cases：8 malformed arguments、descriptor dispatch/readiness撤銷、schema-copy isolation、legacy/candidate main effective config/full/auth/canary、每model round新schema、兩種工具真main路由、scheduled contextual readiness再查。本卡test在testpaths=tests內且本輪確實執行；沒有未跑卻記PASS的task case。

- 不是全mock：main/Core/SQLite/ASGI/router及computer真Python子程序production path通過，tool output實际配對回模型call_id。
- browser driver/model是synthetic替身；測出可路由與observation plumbing，沒有真browser頁面成功證據。真Network smoke使用offline model，只querydiagnostic/switch，不能當provider工具E2E。
- error tests不只測require：独立controller error fixtures都得到raised=None、run_state=failed、terminal_count=1、handler_calls=0，沒有懸掛active run。見 [test_independent_errors.py](test_independent_errors.py)。此腳本在docs不由default discovery自動執行，本輪明確指定。
- compatibility / regression-sensitive：defaultfull、envOllama優先、startup profile不因後續env修改切換、arguments-only handler、batch/denied/failed、100cancel/complete及writerterminal fences、argvbounded/timeout/session isolation均通過。
- 沒有觀察flaky/skip/xfail；部分mainfixture仍使用poll/deadline，不聲稱所有scheduler情況已窮舉。3warnings為dependency deprecation，非task failure。
- 沒有重跑整套repo/real-provider opt-in/真GUI/GPU/Rust/soak。completion273pass/5skip是歷史記錄，不算本輪全套结果。
- smoke最後child exit=-15，只證明TERM終止，不證明graceful active shutdown；報告與completion均不將此當cleanup PASS。

## 5. Relevant REGRESSION_BASELINE

| baseline / 本卡影響 | 判定 | evidence / 邊界 |
|---|---|---|
| conversation/streaming | PASS | Core/SQLite + fake model、integrated/Gateway文字fixtures；真provider/browser delta NOT VERIFIED |
| provider request serialization | PASS | model adapter contracts + model_tools payload；real-provider成功call NOT VERIFIED |
| tool calls / proposal / batch / continuation | PASS | main兩工具路由、paired observations、orchestrator/batch/denied/error fixtures |
| cancellation/timeouts/session fence | PASS | 真程序lifecycle、batch/controller、writer100×2、session/main回歸；不含任意OS/GUI行為 |
| PC main bounded argv | PASS | bounded output/timeout/exit、真main computer subprocess；true desktop readback未驗 |
| config / auth / effective runtime profile | PASS | configunit、legacy/candidate/envpriority、auth/canary、networkdiagnostic/tools-off |
| JSONsettings與Gatewayeffective env整合 | NOT VERIFIED | source明确未載JSON；本卡不聲稱統一生效 |
| real browser readiness/navigation | NOT VERIFIED | 只有executable discovery與mock driver路由；不是頁面健康檢查 |
| shutdown/rollback deployment | NOT VERIFIED | related既有fixtures通過，但smoke -15非active graceful cleanup，patchreverse非部署演練 |

已驗證範圍沒有FAIL或可重現新regression。identity/memory/devices/Rust/audio/GPU不是本卡修改subsystem，不用本輪catalog green替其未驗功能背書。

## 6. Acceptance criteria（逐項）

| Criterion | Verdict | 本輪evidence |
|---|---|---|
| 模型catalog中所有可用工具可路由 | **PASS（production wiring）** | browser.navigate+read與computer.execute都從真main→Core/ModelRequest→proposal→descriptor→observation→continuation；handler source sentinel驗證未繞catalog。computer真子程序，browser為synthetic driver，real browser/provider成功NOT VERIFIED |
| 工具關閉後不dispatch | **PASS（candidate）** | readiness於proposal/execute/scheduled invoke撤銷、零handler effect；每roundtools變空；真network關tools全部catalog unavailable；獨立model生成後撤銷也FAILED單terminal零dispatch。已執行副作用不是新dispatch，此卡不宣稱switch能撤銷它 |
| 不泄漏key | **PASS（diagnostic已定義範圍）** | endpoint需token、明列field whitelist、secret canary/API_KEY/unused cloud值不在回應；不序列化env或settings。未讀真secret，未將此延伸成整套PC工具輸出security audit |

Objective的「descriptor schema/handler/readiness」及「可查實際profile」有caller/network證據。JSONsettings仍unapplied不是hidden fallback，來源如實揭露；不是未達上述三項acceptance的自動FAIL。

## 7. Issues / Severity / Required fixes / Optional improvements

1. **LOW：browser readiness與成功執行的界線。** executable存在只表示可選backend，不保證browser能launch/navigation；本輪browser路由替身沒有真頁面證據。已在CONTRACTS/roadmap明列，未發現本卡錯誤或隱藏成功fallback。
2. **LOW：schema validator限現有subset。** 支援當前兩工具實際用到的object/array/string/uri/integer/boolean等；不是一般plugin JSON Schema validator。現有schema負向fixture通過，任意future schema不在本卡驗收範圍。
3. **已有架構限制：JSON配置未載入。** F06全部configuration alignment仍未完成，但diagnostic如實報false、SiroSettings語義保持。不能聲稱JSON配置影響main；也不應借本卡重寫設定模型。
4. **NOT VERIFIED：部署profile/真provider/browser/rollback。** 本輪只啟動隔離Gateway，原owner服務不變；scope可逆不是正式回退演練。

**Required fixes：本卡已定義acceptance目前沒有blocking production修正。** 對外說明須保留上述readiness/schema/config/部署限制；將來若擴張schema或backend readiness承諾，需另補實際證據。

Optional improvements：真loopback browser page走main路由與failure隔離；readiness診斷提供明確失敗原因；在新增descriptor時測duplicate/name mismatch/未知capability與schema新語法；profile rollout/rollback rehearsal。這些不是本輪發現的production regression，也不擴張本輪工作。

## 8. Final verdict / DONE / rollback

**VERIFIED_WITH_MINOR_ISSUES；建議保留RT-007 DONE。** 三項acceptance已獨立重跑，negative controller paths可終止、相關baseline及scope/provenance通過。限制使本卡不能被稱為全runtime正式部署完成，因此不給無保留VERIFIED。

本輪沒有修改roadmap。若後續選rollback，先drain/清理owned工作、停Gateway，再用已固定legacy profile給新run；patch只撤RT007，不能reset其他dirty改動或恢復半途中間工作。isolatedreverse/before hashes已核對，部署rollback仍NOT VERIFIED。
