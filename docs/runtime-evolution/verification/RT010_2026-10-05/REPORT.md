# RT-010 Independent Verification — 2026-10-05

**Final verdict: VERIFIED.** 建議保留 roadmap DONE，限定於 completed canonical recent dialogue hydration。未觀測到本卡相關 regression；不是全產品、完整session transcript或部署驗收。本輪只新增本目錄 evidence/fixtures，未修改production code、既有tests、roadmap、STATUS或私人runtime DB。

## 1. Identify target

重新讀取目前RUNTIME_EVOLUTION_ROADMAP，最新DONE為 **RT-010，completion 2026-10-05**。RT-009同日完成但其後RT-010已DONE且有獨立completion/evidence；RT-011仍PLANNED。不沿用前輪RT-009結論代替本輪。

## 2. Reconstruct intent

核對完整task的Objective、Problem/F08、audit evidence、scope、acceptance、compatibility、tests、rollback，及ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX、REGRESSION_BASELINE、CONTRACTS、D26。F08指出RAM working context不恢復、legacy conversation可能保存assembled prompt；本卡處理recent session dialogue，不完成long-term memory ingress。

目標：重用RT-008 journal，從completed candidate version1 canonical資料還原同session近期raw user/final assistant pairs；重建fresh system context；session/privacy隔離、上限、legacy不解析。不能重建第二journal/reconciliation owner、重播tools/unknown副作用、更動identity或long-term memory facts。Rollback為下一次drained startup SIRO_SESSION_RESTORE_ENABLED=0保留DB/舊working path，禁止自動降DB或restore舊backup。

## 3. Actual code / runtime / consumers

* Gateway main:1318起讀candidate startup switch，0/1 validation後傳Integrated constructor；缺省candidate啟用，legacy不進新hydrate path，switch在startup固定。
* Integrated.respond先ensure existing Core/reconcile，僅candidate、enabled、非direct command新run讀recent_session_messages；讀取在assistant_started/new run creation前。Continuation走同run history，不重新hydrate。
* repository query exact session + same privacy + completed run + terminal/version1/candidate journal，ORDER created_at/rowid，default LIMIT6 rows。逐row取last raw user（strip後等immutable goal）及final assistant且無tool_calls，構造最多12完整messages，不把legacy assembled text或舊system當user。
* CompanionCore optional recent_messages保持舊callers default None；fresh system + prior native user/assistant pairs + current raw user。提供canonical messages時排除RAM recent以免重複；Core為append owner。on_messages_ready在provider前checkpoint，ConversationEngine與provider實際消費messages。
* 未見detached helper/stub/TODO/NotImplemented或未完成pass替代hydration。舊working path是explicit compatibility/feature-off，不偷偷fallback解析legacy。沿用唯一canonical journal/reconciliation，無duplicated恢复loop。
* output經native model request、journal checkpoint及原readback consumer使用；標準native serialization測試檢查restore-on/off、同run工具pair、舊tool intent/result不混入新run。前卡selected-provider metadata修補保持通過。

## 4. Scope discipline

scope.json：四production及兩test目前digest全吻合task evidence。僅temporary copy reverse scoped patch；before digests全吻合，new test回復不存在，reverse exit0。沒有回退實際working tree。已有dirty tree不全部歸因本卡。

Core/runs是預期變更；Integrated/Gateway為necessary runtime caller wiring，超原expected清單有D26記錄。memory.py/conversation repository未改，因重用journal不需要raw prompt解析。沒有mass rename/move、unnecessary refactor、public API required欄位/port/protocol/schema/state format/既有migration/identity/long-term memory變更。新增optional Core参数和startup env switch屬相容增量，Core沒有引入provider/UI/具體持久層。

原RT-002測試對新run沒有歷史對話的假設與RT-010目標衝突；檢查實際diff確認不是刪弱pair assertions：保留restore-off舊assertion，restore-on新增prior raw goal/final assistant，仍禁止歷史工具意圖與tool result。這是明確契約演進，不是把fail改成skip。

## 5. Tests actually rerun / quality

related.log：**180 passed、0 skipped/xfail、3 dependency warnings，55.70s，exit0**。包含session_restore、integrated_companion、run_journal、agent_batches、agent_runs、provider_retry、failover_policy、model_adapters、conversation、gateway、gateway_main、gateway_terminal_fence、execution_lifecycle。

independent.log：另 **1 passed**。刻意建立corrupt completed canonical journal，經真Integrated.respond驗證ValueError在provider/new-run之前，provider invocation=0、agent_runs count仍1、active_sessions空。不是只測repository錯誤。

process-restarts.json / process_fixture.py：獨立四個全新OS Python processes，共享temporary synthetic DB，依序A→A→B→A。經actual Integrated/Core/SQLite/provider port，三次process重啟後prior messages依序0/2/0/4且內容/roles精確吻合；B不含A，回A不含B。provider是synthetic文字，不是真遠端provider。既有main tests另外覆蓋真正main composition與ASGI；多程序fixture本身不啟網路Gateway。

ruff.log PASS；mypy.log **177 files PASS**。未重跑full suite；implementation的388passed/5skipped只是歷史evidence，不寫成本輪PASS。

測試品質：三次main lifecycle重建涵蓋candidate on/off/legacy、env startup flip；repository cases覆蓋9runs→6pairs/12messages、privacy、legacy_unrestorable、非terminal/failed/cancelled/interrupted不hydrate、malformed canonical fail。成功tool案使用真Python subprocess file effect；重啟前刪marker，後續run不重新建立，history沒有tools/results。Native request serialization的provider transport為synthetic，但Core/SQLite/role construction是真production。

新tests在tests/integration可默認收集；此目錄獨立test已顯式執行，process fixture由driver顯式subprocess呼叫，沒有未跑卻標PASS。未發現本卡skip/xfail；finite timeout避免fixture永久hang。未做長期反覆soak，不宣稱排除所有flaky。

## 6. Relevant regression baseline

| Baseline | Status | Evidence / limits |
|---|---|---|
| session/context persistence / A-B isolation | PASS | main lifecycle + four freshOS processes、精確native pair斷言 |
| conversation/native streaming / same-run continuation | PASS | Integrated/native serialization/Conversation/Gateway/terminal fence；真provider/browser NOT VERIFIED |
| memory/state / legacy compatibility | PASS | rebuiltfreshsystem、bounded completed pairs、legacyunrestorable與feature-off；沒有驗long-term memory新增功能 |
| restart/process recovery / no automatic effect replay | PASS | run_journal crashsuite、readback-only exclusions、actual tool marker不重建、多程序restart |
| provider/config/privacy / metadata | PASS | sameprivacyquery、provider retry/main、switchstartup固定、metadataAPI/SQLite/reopen regression cases |
| tools / cancel / terminal | PASS | batch/execution/lifecycle/gatewayfence suites；本卡沒有增加execution重播 |
| 真provider/GUI/GPU/powerloss/soak/部署rollback | NOT VERIFIED | 未執行；無私人DB/live8000service重啟 |

## 7. Each acceptance criterion

| Criterion | Verdict | Evidence |
|---|---|---|
| 新session重啟仍保留目標/近期對話 | PASS | actualmain三次lifecycle重建、四新OSprocess的rawgoal/assistant pairs、roles/order、readback；限定completed recent dialogue |
| 零跨session混入 | PASS | A/Bquery、mainB無A、返回A無B、獨立process同樣精確內容斷言；同privacy篩選另通過 |

相關task tests亦PASS：legacy assembled prompts不解析、最多12完整messages、舊tool不hydrate、不自動續跑unknown、副作用不重播、corruptcanonical明確失敗。12messages不是token budget，RT-011不在驗收內。

## 8. Issues / severity / required fixes / optional improvements

Issues found：**未發現本卡範圍內的已確認缺陷或regression。** Severity：無新增blocker。Required fixes：無。

已知scope限制而非偷偷完成：failed/cancelled/interrupted goals仍readback-only；direct status/emotion commands無journalhistory；只取recent completed dialogue不含全工具transcript或UIsidebar；identity固定既有siro；retention/single-owner、tokenbudget/summary/long-term memory ingress未實作。真provider/GUI/部署rollback等維持NOT VERIFIED。

Optional improvements：把本輪freshOSprocess與corruptcaller案例納入標準suite；依後續RT-011測tokenbudget/latency，另做drained feature-off部署驗證。若要恢復failedrun目標或完整tooltranscript需另行明確scope，不能把目前PASS擴張成那些功能。

**Final verdict：VERIFIED。保留RT-010 DONE**，保留上述scope与未驗層級，不改寫歷史fail/logs。
