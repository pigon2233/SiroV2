# RT-009 Independent Reverification — 2026-10-05

**VERIFIED_WITH_MINOR_ISSUES**。建議保留 roadmap DONE。先前 selected-provider durable metadata regression 已修復並經原獨立案例重驗；本轮未觀測到新的相關 regression。結論限定本卡與下列測試層級，不是 release/promotion。未修改 production code、既有測試、roadmap、STATUS 或私人 runtime DB。

## 1. Identify target

重新讀取 RUNTIME_EVOLUTION_ROADMAP 的 DONE / completion date，最新仍是 RT-009（2026-10-05），含當日 provider-metadata-fix。RT-010 仍 PLANNED。本輪保留原 REGRESSION_DETECTED 報告與失敗 logs 作歷史 evidence，不覆寫它們。

## 2. Reconstruct intent

讀取完整 RT-009 Objective / Problem / F07 / Scope / Acceptance / Compatibility / Tests / Rollback；核對 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX、REGRESSION_BASELINE、RUNTIME_EVOLUTION_SPEC、COMPATIBILITY_PLAN、CONTRACTS、D24/D25 與修補實際 diff。

目標：符合 privacy/budget、尚無 text/tool intent 的 generation 才可有限重試；初試加 retry/fallback 最多兩次；cancel 可中斷 backoff；保留原 provider priority、legacy callers、HTTP/WS、port、schema、授權與前卡 FIX。沒有費用 budget 時不新增 cloud requests。Rollback 使用 drained startup 的 SIRO_MODEL_RETRY_ENABLED=0，保留原單 provider 與既有 journal/fences。不是自動加入雲端路由、USD/day accounting 或 RT-010 session hydration。

## 3. Code / production wiring / output consumers

gateway.main:1015–1052：先按既有 env priority 選 Ollama / authorized cloud / offline，再於 candidate 及 retry switch=1 時包 FailoverModel；startup switch有0/1 validation，profile/choice不途中切換。legacy及feature-off直接使用原 provider，屬明確 compatibility，不是 hidden fallback。

failover.stream 的 range(2) 為唯一 attempt tier；第二次 request僅更新private generation ID，保留prompt/native messages/privacy/tools/output budget。nonempty text、任何tool_request（含空intent）及finished阻止任何下一attempt。OpenAI下層buffered tool fragment遇exception會加標記，wrapper將其視為nonretryable，保留原error class。token/task/pre-cancel/backoff與ConversationEngine整體deadline的caller均存在。

wrapper輸出由ConversationEngine→Core→Integrated消費；只有accepted COMPLETED generation可提案/dispatch。FIX-001 failed initial/continuation intent gate仍有效。main測試包含真Core/SQLite/ASGI及真Python檔案副作用；model provider為synthetic。沒有detached implementation、核心stub、TODO/NotImplemented。except TimeoutError: pass是backoff等待到期後繼續有限attempt，不是未實作。adapter與wrapper分別處理緩衝/可見intent，不存在另一個重試tier。

**Metadata修補已接入consumer**：FailoverModel constructor捕捉models[0].name。Integrated.respond沿原runtime_backend=self._model.name→repository atomic start→run_journal.backend→authenticated readback流程；名稱不隨fallback/共享wrapper的last attempt改動。語義是selected-primary identity，不是逐attempt trace。標準local/cloud retry on/off測試檢查live API、raw SQLite及fresh-store reopen；原獨立test直接查SQLite亦PASS。

## 4. Scope discipline

scope.json：五個目前source/test digests符合原task加repair evidence。在temporary copy先reverse repair.patch，再reverse implementation.patch；pre-repair五個及pre-task三個digests全吻合，兩次reverse exit0。實際工作目錄未reverse。此方法避免把已有dirty tree全算作本卡。

原task：failover/gateway與必要OpenAI buffered-intent adapter增量（D24記錄）。Repair唯一production增量為constructor的name capture；兩個測試補assertions。無mass rename/move、不必要refactor、port/signature/required HTTP fields/protocol/config JSON/state schema/既有migration/權重/identity/Rust變更。Core/Integrated/repository無新增具體provider耦合。新增optional startup env switch保持legacy缺省與provider priority。

沒有以修改schema、consumer assertion或猜測歷史資料掩蓋regression；historical backend=failover rows未改寫。既有public instance .name仍是字串；selected-primary metadata的修正符合D25與原journal consumers。

## 5. Tests / discovery / quality

本輪related.log：**186 passed、0 skipped/xfail、3 dependency warnings、60.02s，exit0**。含failover_policy、model_adapters、provider_retry、conversation、integrated_companion、agent_batches、run_journal、gateway、gateway_main、execution_lifecycle、tool_catalog、gateway_terminal_fence，及原未修改的獨立test_main_preserves_selected_backend_in_durable_journal。

ruff.log PASS；mypy.log **176 files PASS**。未重跑full suite；repair報告378 passed/5 skipped是歷史結果，不當作本輪PASS。

Production wrapper contract cases覆蓋two/three/same backends、request preservation、transient/permanent errors、text/tool/finished emission、local_only/cloud_allowed/explicit extra-request budget、pre/token/task cancel、backoff cancellation。actual localhost HTTP server + actual Ollama/OpenAI adapters/Httpx transport覆蓋429 retry及fragment premature EOF fence；是synthetic server，不是真model provider。

Actual main tests保留原構建路徑，僅provider與uvicorn serving替換；ASGI/Core/SQLite與成功tool file-write subprocess真實。涵蓋retry成功/耗盡、legacy/switch-off、env startup freeze、failed initial/continuation intent、cloud原單次request，現在也檢查metadata三層consumer。Name-after-fallback contract固定selected-primary，不偽裝實際fallback provider。

Dedicated cases位於tests，pytest可收集；獨立test位於verification目錄，已顯式加入命令，沒有當作默認suite會自動執行。未發現本卡skip/xfail；未做長期repetition，不能聲稱排除所有flaky。真model/speech opt-ins本輪未跑。原獨立test檔未修改，但其引入的production-main標準fixture已新增metadata assertions；本輪直接SQL assertion仍存在並通過。

## 6. Relevant regression baseline

| Baseline | Result | Evidence / practical limit |
|---|---|---|
| fallback/retry main wiring與output/tool fence | PASS | actual main、two-attempt、buffered fragment真HTTP EOF、initial/continuation failed intent |
| provider adapter contracts | PASS | raw/native messages與localhost transport；真provider NOT VERIFIED |
| conversation/streaming/terminal | PASS | Conversation/Integrated/Gateway/terminal fence cases；GUI/provider E2E NOT VERIFIED |
| tool calls、pairing與cancel | PASS | actual subprocess成功effect、failed intent零新effect、batch/execution/journal suites |
| cancellation/timeouts | PASS | pre/token/task cancel、backoff、existing engine/execution gates；非音訊硬體驗收 |
| config/legacy/feature-off/cloud policy | PASS | priority不變、startup env flip、default extra-cloud budget0、redacted diagnostics |
| restart/readback與durable backend identity | PASS | 原獨立case、API/rawSQL/freshStore local/cloud retry on/off、既有四crash tests |
| 真provider/GUI/soak/部署rollback | NOT VERIFIED | 沒有外部provider calls、GUI或服務部署，不觸碰8000私人服務 |

## 7. Acceptance criteria individually

| Criterion | Result | Evidence |
|---|---|---|
| 最多2attempt，含首試 | PASS | range(2)、same backend/three backend contracts、actual-main失敗最多兩次；tool continuation為另一generation |
| emission後零fallback | PASS | nonempty text/tool/empty intent/finished、buffered fragment error note、realHTTP premature EOF；failed-generation無新effect |
| 無未設定cloud外送 | PASS | LOCAL_ONLY gate、extra-request budget0、main不compose cloud fallback、primary cloud僅原authorized一次 |

上述PASS以實測production路徑與synthetic/local層級為限；未以「tests綠燈」替代真provider/部署驗收。

## 8. Issues / severity / fixes / roadmap

* **先前P2 metadata regression：已解決。** 原獨立失敗案例及新consumer assertions PASS。沒有需要再次修改production的已確認blocker。
* **P3文件不一致：** 原implementation REPORT說「Protocol/validation/permission ... without retry」，但本輪protocol-classification.json證明LocalProtocolError、RemoteProtocolError、UnsupportedProtocol均被_retryable判True，因為屬httpx.TransportError。這符合目前CONTRACTS較廣的transport分類，兩attempt/privacy/emission限制仍有效；不能把原報告該句當作已驗證行為。建議更正報告描述，另補精確protocol錯誤政策測試。此probe是production classifier的直接驗證，不是真protocol-error network experiment。
* **歷史資料限制：** 已寫為failover的舊rows仍缺provider證據；本輪修補阻止新資料持續流失，不恢復歷史身分。禁止無證據猜測改写私人DB。這項不是尚存的新run regression。

Required fixes：本卡production acceptance/compatibility無新增blocker；修正上述文件說法以免誤讀。

Optional improvements：補protocol分類邊界、attempt audit（若另行授權）、真provider與drained deployment feature-off驗證；不將本卡擴為monetary budget/session hydration。

**Final verdict：VERIFIED_WITH_MINOR_ISSUES。建議保留DONE**，並保留historical metadata缺口與真provider/GUI/soak/部署rollback NOT VERIFIED的限制。舊REGRESSION_DETECTED報告代表修補前快照，勿刪除或改成成功。
