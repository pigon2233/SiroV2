# Regression baseline

## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

95新cases；最終相鄰335 PASS／3既有warnings／25.63s，完整 **1,673 PASS／5 real_provider未選／3既有warnings／199.58s**。Ruff315、mypy250（含launcher）、schema、source/tests/docs diff PASS。

新95cases=selector70＋launcher7＋ready/DTO/owner15＋actualprocess3。Original source: selector70FAIL因缺API（不是70舊漏洞）；initialcaller12為10FAIL/2PASS。現有可用negative behavior保持，不重構；actualprocess原fixturejson/hashlib import錯誤另留歷史FAIL，修fixture再凍最終source/test，不當productionbug或finalPASS。

True3cases包含5actualchildren：1→2→rollback1＋unsupportedABI/tamper。三批actualconversation/memory/completedledger保留，所有childjoined/rootsremoved，childsigningkeyboolean=false/無值紀錄；normalSIGTERMexit-15與shutdowncomplete明示。clone內namespace/loaded-origin telemetry是controlled instrumentation，不取代真HTTP/SQLite/sourceimport。

273baseline中270不改；exact7 source-only disposable reverse/reapply PASS，保所有資料與Git歷史。D48 schema helper抽出前後AST相同；D51 backup/CLI四檔與D50 owner/operations source保持。

全repo aggregate scripts/check、Rust重建/依賴sync/nativeprivate模型、real_provider/真人產品/8026/正式deployment未跑，不冒稱aggregateCI或whole-evidence whitespace PASS；格式/diff gate針對code/tests/docs，原始pytestlog/patch保verbatim。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

新25 cases、相鄰240 PASS（17.60s）；完整 **1,578 PASS／5 real_provider 未選／3既有 warnings／198.40s**。Ruff311／mypy245／schema／diff PASS。

新baseline：SQLite19（raw/ZIP repeated task cancellation、queued writer、真正multi-page non-DONE/DONE-before-publication、actual publication後取消、explicit close、typed primary/cleanup refusal、ContextVar隔離）＋CLI6（normal/plaincancel/typederror/late-success/repeatedcancel/非mainthread）。真8SIGINTfixture與source5path綁定，8stderr零；原D50 initialization-stage SIGINT tests保持。

曾失敗的controlled handler缺wakeup版本留在full-before-wakeup.log（2FAIL/1575PASS/5未選/3warnings），不能當final；首次24 controlled PASS也不算trueOS驗收。原SQLite16/18-case RED是階段test版本，不冒充最終25case全RED。

269/271既有baseline bytes保持，exact4 source-only temporary reverse/reapply PASS；保留所有資料與Git歷史，source rollback不授權再用舊危險取消路徑。

real_provider、真人語音/理解、運行8026與powerloss NOT_RUN；沒有降低gate或改mock取代真整合。

[驗收、分類、限制與回退](../evidence/FIX-015-2026-10-13/REPORT.md)。

## 2026-10-12 — RI-005 D50 owner / FIX-014 限定切片 VERIFIED

受管Gateway與CLI demo/backup/restore/有DBrelease在實際操作前取得同一canonical data owner，持有到startup/server drain/owned SQLite IO完成；備份來源、explicit目的地、ZIP固定.tmp共同有序去重（最多3keys）、一份IOjoin fence。真正foreignowner/alias與連續SIGINT反例先RED→局部修復；禁止output/tmp覆寫sourceDB/inputsettings/archive或tmp指向final，不改Core/SQLite/operations/release/權限/voice/UI/launcher/deps。沒有第二套registry/restore/lockmanager或globalstate。FIX-014 **DONE/VERIFIED**。

70新cases；最終相鄰**215PASS/10.58s**，完整**1,553PASS/5 real_provider未選/3既有warnings/157.81s**；Ruff309/mypy243/schema/diff PASS。真offline Gateway HTTP、kernel contention/fork/exec/aliases、raw/demo/ZIP三次SIGINT、3FD join/partialcleanup；fault/timing控制明示。baseline268中266不改、exact5source-only temporary reverse/reapply PASS、D47/D48/D49保留。獨立contract16PASS並重綁final5，lifecycle reviewer最後turn碰accountlimit，不假稱三份final批准；final OS probe另列。敏感掃描與cutoff見報告。

另真ZIP backup-stage probe確認未改的backup_to取消早退→TemporaryDirectory先清理→late IO重建staging，command join後仍留snapshot/sidecars：**FIX-015 REQUIRED_FIX/MEDIUM PLANNED / FAILED_VERIFICATION**，不是D50 lease失效。原dir0700、重建0775，實測DB/sidecars0600，沒有其他UID可讀內容證據。只要求既有backup局部canceljoin/明確close，不在本卡擴全SQLite。RI-005整體**PARTIAL / BLOCKED_BY_FIX: FIX-015 / BLOCKED_BY_RELEASE_INTEGRATION**；ZIP完整cleanup、firstadoption舊owner停止、signedlauncher真正版本/readiness/批准handoff仍未驗，禁止用source切片PASS放行發布。

Architecture **YELLOW**；owner/Gateway **YELLOW**、合成tests/evidence **GREEN**；runningDB/migration/權限/發布 **RED**。KEEP RI-005並SPLIT remaininglauncher/handoff，KEEP RI-006只到唯讀提案；REJECT重複owner/restore abstraction，未證任何 numberedtask冗餘，不硬CANCEL。RT-011/013/015原scopedDONE/編號不變，FIX-002/005/006產品gate保持。接續三窄卡（非ranking）：FIX-015局部backup cleanup、RI-005人工批准version/readiness/handoff、RI-006來源失敗→唯讀提案。沒有live8026重啟、私人DB/chat/WAV/key/config/model/GPU或發布。

[實際驗收、限制與精確回退](../evidence/RI-005-owner-2026-10-12/REPORT.md)。

## 2026-10-12 — D49 / FIX-013 explicit restore 局部修復 VERIFIED

真正 temporary SQLite 證明舊路徑先覆蓋 live 再拒 migration/checksum，且 cancellation 提前釋放 writer lock。只改既有 SQLiteStore：mode=ro/query_only source→owned candidate→known prefix/checksum/既有遷移/integrity→SQLite backup promotion；不replace live/WAL。原 per-store writer lock 持有到 offloop thread/explicit connection close/cleanup joined；取消中止未完成 copy，DONE後取消誠實保留已commit資料。原typed error保留、cleanup refusal可見，不假稱已移除。獨立review先RED修掉Python3.14 shield重複error，只改owned await asyncio.wait/job.result，沒有新restore/schema/updater抽象。

41新cases；exact original source **30FAIL/11PASS**（5.61s）；最終專項 **145PASS**（4.95s），完整 **1,483PASS/5 real_provider未選/3既有warnings**（156.51s）；Ruff306/mypy240/schema/diff PASS。真raw/ZIP CLI、舊schema/WAL/來源唯讀、取消/queued writer/ledger retention驗收；IO/清理/進度timing標controlled。三份獨立review重綁final source後無scoped blocker。266 baseline中265不改、新2tests，exact3 source-only reverse/reapply PASS，D47/D48保留；final source3/docs12掃描0；evidence55inputs/277逐項capturedSHA256誤報/unresolved0，cutoff 2026-10-11 17:58:09 UTC（audit outputs與此後結果annotation排除）。

FIX-013 **DONE/VERIFIED**，只解除此explicit-restore failure gate；RI-005整體 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：activepointer不等於真正版本，stopped writer／實際launcher/version/readiness／人工批准還未驗。成功明確data restore可替換近期資料，code rollback仍只切版本；commit後取消/cleanup failure需readback再決定，不重送。沒有live8026 restart、privateDB/chat/WAV/key/model/GPU或發布；FIX-002/005/006產品gate與RT-011/013/015 scopedDONE不變。

Architecture YELLOW；restore元件YELLOW、合成測試/evidence GREEN；運行DB/migrations／權限／發布RED。ZIP DB/config跨檔atomic、multiprocess lease、powerloss不算本卡驗收；candidate disk-capacity／舊backup retention為TECH_DEBT/DEFER，不建新manager。KEEP RI-005、SPLIT stopped-owner與actuallauncher；接續三窄切片RI-005 owner、RI-005 approved launcher/version/readiness、RI-006唯讀提案（非ranking、不重編）。Hermes REJECT重複restore/evolution abstraction，DEFER任意自改/發布直到接入有證據；本卡無new scoped blocker。

[驗收、限制、精確回退](../evidence/FIX-013-2026-10-12/REPORT.md)。

## 2026-10-11 — RI-005 D48 / FIX-012 code-only回退限定切片 VERIFIED

原T32把版本回退與wholeDB restore綁一起，舊測試要求新寫入消失，是ORIGINAL_DESIGN_ERROR／REQUIRED_FIX HIGH，不是新Sol regression。[最小架構更正](ARCHITECTURE_CORRECTION.md)。只改既有ReleaseManager：新staged版本保存完整D39signedmanifest sidecar並拒順序同版覆寫，health後再驗來源；rollback驗精確target/signature/alias＋實際readonly schema prefix，unknown/incompatible拒絕，只切active pointer、從不讀舊backup還原或migrate/replay。既有獨立siro restore保持分開，移除只被舊rollback使用的private restore helper。API/CLI/簽章格式保持，危險資料回退語意明確撤銷；沒有自動信任升級/新updater/schemaengine/lockservice。

新51cases＋原release/signing/launcher/operations94PASS（3.75s）；完整1,442PASS、5 real_provider未選、3既有warnings（157.59s）。真temporary SQLite/WAL晚寫/原writer仍可用、conversation/memory/完成ledger保留、real migratedDB CLI、schema/receipt/source/path負向；pointer/receipt錯誤為controlled injection，沒有實際啟動另一version或真人產品驗收。全repo Ruff304／mypy238／schema/diff PASS；baseline265中263未改、exact3 source-only reverse/reapply PASS，D47十一檔保持；3source/13publicdocs敏感掃描0；evidence 273逐項SHA256誤報、unresolved0；cutoff 2026-10-11 15:53:57 UTC（audit outputs與後續status/count annotation另排除）。

另外真合成probe確認SQLiteStore explicit restore在migration/checksum failure前已覆蓋live：**FIX-013 REQUIRED_FIX/HIGH PLANNED，該failure path FAILED_VERIFICATION**，此卡未改SQLite/migrations。RI-005整體PARTIAL，full activation／data-restore acceptance標BLOCKED_BY_FIX: FIX-013與原BLOCKED_BY_RELEASE_INTEGRATION；active pointer≠真正執行版本，launcher仍需consume/readiness與stopped-writer gate。元件source rollback不授權重新呼叫舊危險DB回退。沒有live8026/privateDB/chat/WAV/key/model/GPU/發布。三個分派審查turn碰帳戶limit，最終獨立review NOT_RUN，root直接source/實測不冒充獨立批准。

Architecture overall YELLOW；ReleaseManager元件YELLOW、合成測試/docs GREEN；運行中的DB/migration/權限/發布仍RED。順序immutableversion/read-schema snapshot不等於concurrent owner lease、powerloss或實際loader相容。保留舊backup但不自動用其回退是TECH_DEBT retention，不擴全局抽象。KEEP剩餘RI-005並SPLIT stopped-writer/actuallauncher；下一三張接續範圍FIX-013局部prevalidation、RI-005剩餘接線、RI-006唯讀提案（非ranking）；RT-011/013/015 DONE保持，FIX-002/005/006產品限制不解除。

[完整驗收與回退](../evidence/RI-005-2026-10-11/REPORT.md)。

## 2026-10-11 — RI-004 D47 固定技能產品接入（限定切片 VERIFIED）

既有D44準備/真驗證＋D46strict worker接進同一registry/catalog/orchestrator/dispatcher：server-held review900s/完整identity→人工安裝disabled→另一步明確enable→原對話tool批准→revoke；沒有模型自批、任意code/依賴、第二套registry/scheduler/schema。新facade/CAS不覆寫同版，queued/active jobs先fence再join，取消offloop交易補disabled，cleanupfailure仍嘗試durable revoke、保留typed error。Startup只恢復精確固定模板/receipt/row，tools-off持久停用，shutdown保留原owner明確批准供exact restart。

最後真畫面發現準備紀錄與已安裝狀態矛盾，補2個RED→局部history-label修復，不改匯出原始事實。最終189專項PASS（17.12s）／完整1,391PASS、5 real_provider未選、3既有warnings（154.61s）；Ruff302／mypy237／lint／schema PASS。真CUA/HTTP/SQLite/bwrap走通安裝disabled→明確enable→填入不送出→revoke/readback，fixture退出0、owned jobs0、暫存清除。最後exact11 source回退/reapply與獨立綁定PASS，baseline258中254不變，D46七檔/Core/policy保留。11source/10publicdocs敏感掃描0，evidence356逐項digest誤報/unresolved0（02:10:44UTC cutoff；後續僅狀態/計數annotation）。最後console一則無來源MutationObserver錯誤，origin UNKNOWN，已留證據，未宣稱零錯或猜測修復。實際產品驗證只temporary18034，不讀私人DB/chat/WAV/key、不碰模型/GPU、不重啟live8026或正式部署。

RI-004整體仍PARTIAL，但固定builtin checklist人工批准/strict執行/撤銷切片的局部caller接入gate已解除。RI-005 launcher/single-writer/latest-data-preserving rollback保持BLOCKED直到各自驗收；RI-006 KEEP，FIX-002有用搜尋/FIX-005速度人耳/FIX-006真理解保持既有產品限制。RT-011/013/015 DONE不重開、不重編、不ranking。Gateway/registry/catalog保持YELLOW（新owner生命週期），D46已驗限定profile可GREEN，Core/permission/release仍RED freeze；sameUID/任意生成/multiprocess/aggregateRAM不算通過。沒有original design correction或新全局state manager。

[完整變更與驗收](../evidence/RI-004-activation-2026-10-11/REPORT.md)。

## 2026-10-11 RI-004 strict worker baseline

完整 **1,202PASS／5real_provider未選／3既有warnings／132.67s**，原1,151保留加51strictcases；focused120不重複相加。正式2constructorRED；exactprecard只收集41當時cases，沒有OSchecks執行，不稱41FAIL。Identity3RED／admission1RED／deadline1RED後localrepair、所有51PASS；actual D44parser→strictworker／privatehost/env/network/process/session/limits/kernelobjects denial／資源／outputflood／probe/run/prepare/cleanupcancel與PID回收。[REPORT](../evidence/RI-004-worker-2026-10-11/REPORT.md)。Ruff295／mypy230／schema/diff、254baseline保存／exact7rollbackPASS。只developerexplicitprofile、不驗產品owner批准／registryactivation或chatcaller；未驗其他OS/deps/multiprocess/aggregateRAM／blockedIO SLO，品質/releasegates保留。

## 2026-10-11 FIX-011 baseline 更新

完整離線 **1,151 PASS／5 real_provider未選／3既有warnings／132.76s**，保留原1,127加24 lifecycle案例；focused不重複相加。原worker RED5FAIL／9deselected，後續UTF-8／privatecaller與primarycleanup precedence各反例先RED後local修復。真bwrap洪水／100k合法JSON／fork+setsid descendants取消與timeout，受控prep/spawn/cleanup repeatedcancel／typedfailure、legacy boundedstdin、samepackage／facade保持。全repo Ruff291／mypy226／schema/diff、252baseline保存及exact5回退PASS。[完整證據](../evidence/FIX-011-2026-10-11/REPORT.md)。trusted profile仍不是敵意generated worker認證；strictOS／批准／撤銷、其他OS／aggregateRAM／blockedIO SLO仍需下一切片，原產品品質gates不變。

## 2026-10-10 RI-004 baseline 更新

完整離線 **1,127 PASS／5 real_provider未選／3既有warnings（130.97s）**，保留原1,039 cases、追加88（service23／Gateway32／frontend33）。不與focused或Chrome重複相加。初始RED：service21FAIL／frontend28FAIL／Gateway31FAIL；額外snapshot1FAIL與catalog order1FAIL/1PASS分別保存。最終pre-card projection因service不存在collection return2，沒有功能測試執行，不能稱88FAIL。[驗收與回退](../evidence/RI-004-2026-10-10/REPORT.md)。

新基線：全部typed inventory／aliases包含hidden/unavailable/unknown、不執行executor、fixed schema/package/fullhash、actual sandbox六個parser cases、報告UUID/path/cleanup/output binding、不授權、單active/busy/noqueue、重複取消及latecleanup/typedfailure；owner Origin/token/legacy/tools/shutdown；actual service→pagePASS與binding mismatch、safe rendering/export、double click、unknown network／stale reply／reconnect不重送。真Chrome+temporary Gateway23checks PASS，cancellation timing gate synthetic。全repo lint/format289、mypy224、schema/diff與exact6source rollbackPASS。

本輪不驗LLM任意生成／installed registry discovery／實際worker enable/revoke、真模型／TTS速度／Live2D／桌面漫遊／其他OS。原安全與品質基線仍有效；不能把固定template新PASS解除FIX-002/005/006或RI-005 gates。

## 2026-10-10 RI-003 baseline 更新

最終完整離線 **1,039 PASS／5 real_provider 未選／3 既有 warnings（127.78s）**；原 991 cases 保留，新增 48 API／CLI cases，沒有本機 profile skip。精確 pre-card dirty source／兩新 backend 不存在的 projection：48 FAIL／2.09s；新舊 patch/path 111 PASS／11.50s。專項與 full 不重複相加。[報告](../evidence/RI-003-2026-10-10/REPORT.md)。

新基線包括真 namespace malicious import、source no-follow／alias／bounds／post-apply expansion、網路／fork／exec／session／kernel IPC denial、AS／CPU／file-data／output flood；actual API cancellation/deadline 與 CLI 單／雙 SIGINT 的 owned PID tree／workspace 消失。Late task/token cleanup／primary cleanup failure／late completed-task signal 用受控 fixture 驗 status，不把 fixture 當 OS 壓力測試。獨立 source review findings 先 RED 再修復。

Format230／mypy220／lint/schema/diff／六檔零 secrets；231 既有 hashes 僅兩個預期 source 改變、四檔新增；exact 六檔 temp rollback PASS。一般 multiprocess／pytest/deps／其他 OS／aggregate kernel RAM／blocked host IO SLO／遠端 CI 未驗；candidate tests 可以偽造，PASS不是批准。5 external model cases、GPU／人耳／真人 Live2D／devices／24h soak 未執行。FIX-002／005／006 原 gate 不變，不用 full PASS 宣稱全產品完成。

## 2026-10-10 FIX-010 baseline更新

完整991PASS／5real_provider未選／3既有warnings（118.71s）。新增44backend＋1 actual renderer cases；精確三檔dirty修前45FAIL／3.19s→新舊batch/journal/catalog122PASS／20.71s。覆蓋unknown同hash新UUID、wrong/orphan/crossowner/payload、NULL/invalid receipts、Unicode/order/hugeinteger/duplicate/無法抽取numeric、privacy/age、CAS/manual/denial/readtrusted/cancel/batch、ledger readonly與一次emit。真Chrome21checks另驗同頁WS重連、401/403、手動一次/duplicate404/cleanup；不冒充真OS效果/provider或reload recovery。

Format226/mypy216/lint/schema/零allowlisted secrets PASS；229old source僅三production變，兩tests新建，exact5filetemp rollback PASS。前序946基線所有測試保留；FIX-006理解/FIX-005速度/FIX-002搜尋仍未完成。[報告](../evidence/FIX-010-2026-10-10/REPORT.md)。


## 2026-10-10 FIX-006 baseline補充

新增40真正失敗反例：跨session/route/legacy/off/direct、最新無效row遮蔽、aware time0..900sec與offset/UUID、raw/unknown/NUL canary、readonly dump/固定投影、failed executable messages仍不恢復及completed pairs不變。精確修前40FAIL／1.79s→新舊55PASS／3.05s；全套946PASS／5real_provider未選／3warnings／114.33s。Format224/mypy214/lint/schemas PASS。真provider合成逐項另列：[REPORT](../evidence/FIX-006-2026-10-10/REPORT.md)，own failure factual增益有限，voice-correction/unknown-effectFAIL，不以mock或946PASS替代產品理解。原RI/skill/release/browser/voice/session source保留。

## 2026-10-10 FIX-007 baseline 更新

最終906PASS／5real_provider未選／3既有warnings（113.93s）。43新cases＋既有/adjacent共66PASS；exact原source42FAIL／1PASS。包含真Linuxbwrap隔離/資源/取消與frozen plugin/helper positive；格式223/mypy213/schema通過。227既有來源除三production皆SHA不變，舊tests未改，精確4檔回退PASS。中間904/905結果被新反例修復後906取代，不相加、不作最終source驗收；無真人/provider/deployment證據。[驗收](../evidence/FIX-007-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-009 baseline 更新

完整離線863PASS／5 real_provider未選／3既有warnings（111.19s）。新增34 cases，簽署範圍／格式／型別／legacy／model_copy與zero-effect拒絕，以及實際CLI與temporary DB/staging；新舊release36PASS。修前新集19FAIL／15PASS，第一例證明schema tamper真activated。226既有來源除單一production與oldfixture外SHA不變，精確3檔回退PASS。不證明data-preservingrollback或deployment。[驗收](../evidence/FIX-009-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-008 baseline 更新

目前完整離線基線 829 PASS／5 real_provider 未選／3 既有 warnings（112.86s）。FIX-008 新增 62 cases，含真 Git temp apply；新舊專項 63 PASS，修前完整新集 46 FAIL／16 PASS。保留 FIX-002／RI-002／voice/session 基線，225 既有來源中僅 evolution.py 改變。測試不證明不可信執行的 OS 隔離、自動部署或真產品語意。[驗收](../evidence/FIX-008-2026-10-10/REPORT.md)。

## 2026-10-10 incremental baseline

RI-002後716PASS；FIX-002後767PASS／5 real_provider未選／3既有warnings，111.45s。新增51 case覆蓋typed reason/native/legacy、malformed URL零dispatch、真scope/partial/origin reset、UI與owned teardown；不是搜尋網站或自主研究通過。真Bing與DDG有native roundtrip，但無搜尋結果，間歇public cleanup原因UNKNOWN。

[實際證據](../evidence/FIX-002-2026-10-10/REPORT.md)。


## Current baseline — 2026-10-09 Runtime Intelligence review

基準 main / `c1d2d41` 加本輪開始前既有未提交工作；保留文字／語音／Live2D成果。下方2026-09-30失敗紀錄是歷史，不再代表目前migration／Rust／session／工具能力狀態。現況及分層驗證見 [CURRENT_ARCHITECTURE_AUDIT](CURRENT_ARCHITECTURE_AUDIT.md) 與 [ROADMAP_RECONCILIATION](ROADMAP_RECONCILIATION.md)。

| 本輪實際命令／檢查 | 結果 | 有效範圍 |
|---|---|---|
| `.venv/bin/pytest -q -m "not real_provider"` 修改前 | 671 passed／5 deselected／3既有warnings，156.91s | 既有dirty tree離線基線；不是全產品驗收 |
| 同命令，最後修改後 | 701 passed／5 deselected／3既有warnings，147.01s | 新增30個開發工具fixtures；不把before/after耗時當效能收益 |
| `.venv/bin/pytest -q tests/test_codebase_memory.py` | 30 passed | source排除／symlink／大小限制／stale／sandbox與env；包含於701，不重複相加 |
| Linux bubblewrap合成隔離probe | 12項PASS | 精確helper版本：host home不可見、source/release只讀、無網路、cache可寫；不是production PatchVerifier已隔離 |
| Ruff format/check／mypy／schema check | PASS；269格式檔、204 source files | 本機格式／lint／types／export_schemas --check；不是遠端CI |
| `cargo test --workspace --locked` | 6 library tests PASS | 既有Rust元件回歸；不是全PC／硬體實機驗收 |
| developer config停用／恢復、6檔temp reverse/reapply | PASS，SHA復原 | 不回退原有dirty source；不需重啟SIRO |
| `/health/live`、`/`、`/live2d/` | HTTP200 | readiness；未以此替代真人對話／WebGL／人耳驗收 |

新增基線只覆蓋開發期Codebase Memory整合：索引無私人資料、啟動時拒絕過期source、禁止mutation、無網路／只讀mount、缺sandbox不降級到host。已連線MCP是快照，改source後須斷開及手動重索引。production既有251個source/tests/locks SHA零變。

本輪安全反例確認FIX-007／008／009及untrusted-check OS隔離、launcher activation／最新資料回退缺口；未修前不能用上述綠燈解禁skill generation或自動部署。測試盲區仍含真provider／新GPU／人耳／真人Live2D／真HA與ESP32／第二節點／24h soak／遠端CI／attestation；原FIX-005產品語音品質仍PARTIAL。完整命令／logs／rollback見 [本輪REPORT](../evidence/runtime-intelligence-2026-10-09/REPORT.md)。

## Historical baseline — 2026-09-30

日期 2026-09-30；目前 dirty working tree。定義「正常」必須限定路徑與測試層級，不接受全部綠燈或全功能完成的籠統說法。

## 本次實際執行

| 命令 | 結果 | 層級與限制 |
|---|---|---|
| `uv run pytest -q` | exit 1：193 passed、1 failed、5 skipped，20.62s | unit/contract/integration；包含 mock/simulator；不是全部 main E2E |
| `cargo test --workspace --locked` | exit 0：6 passed | local runtime/driver tests；不代表 Gateway uses Rust |
| `uv run ruff check src tests` | exit 0 | lint |
| `uv run mypy` | exit 0：163 source files | type checking |
| `curl -fsS --max-time 3 http://127.0.0.1:8000/health/live` | exit 7，connection refused | 目前 port 8000 無回應；不推定所有 SIRO 程序均未啟動 |

失敗：`tests/integration/test_sqlite_store.py:48` 期待 migration `[1..10]`，實際多出 11、12。初始化已執行，但測試不能據此標 PASS。本次未改 assertion、migration 或 production。

跳過：3 個 model real-provider tests（缺 opt-in）、2 個 Groq speech tests（缺 opt-in key）。沒有讀取或將私有 key 放入命令/證據。不能從 skip 推定服務不支援。

## 維持既有行為的驗證基線

| 能力 | 已觀測基線 | 尚未驗證 / future regression condition |
|---|---|---|
| conversation/streaming | integrated test 真 Core/SQLite + fake model 通過 | 真 main + provider + browser delta |
| character | body adapter/mount/failure isolation 通過 | 真 Cubism 畫面/gesture/口型 |
| provider calls | adapter contract 通過 | 真後端及 failover runtime |
| tool calls | 單工具 proposal/auto-approved continuation 合成案例通過 | main argv executor、多工具 batch、執行中 cancel |
| session | turn state machine / persistent repository tests 通過 | UI 多分頁/session、context reload |
| memory/state | memory/identity/relationship/affect tests 通過 | 正式 chat memory ingress；migration test FAIL |
| restart/process recovery | repository reopen/CLI backup tests 通過 | crashed active run reconciliation；不能自動重播副作用 |
| fallback/retry | FailoverModel/job 元件測試通過 | main wiring；output/tool call 後 failover |
| cancellation/timeouts | ConversationEngine/http stream/合成 barge-in tests 通過 | Qwen timeout/cancel、程序樹停止、最新語音正確配對 |
| PC control | scoped driver/Rust isolated tests 通過 | Gateway main executor 的有界記憶體與 readback |
| devices | registry/MQTT/HA simulator或mock tests 通過 | ESP32 真板、真 HA、sensor→actuator |
| Rust | 6 unit tests + Python boundary suite 通過 | Gateway execution 接入、部署程序 supervision |
| config | JSON config tests/CLI 通過 | JSON settings 與 Gateway effective env 一致 |
| shutdown | Gateway callback/hub cleanup test 通過 | Qwen child/active executor cleanup |
| TTS | source 選 Qwen reference v1；先前 session synthesis 為歷史線索 | 本次未重新 GPU 合成或聽測，不標本次 PASS |

未執行完整 scripts/check（含安裝同步、完整 secret scanner）；未跑 24h soak、真雙節點、真硬體、真瀏覽器。Phase 1 不啟動 migration。
