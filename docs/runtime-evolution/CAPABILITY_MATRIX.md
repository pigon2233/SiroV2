# Capability matrix

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

## 2026-10-11 fixed strict worker 能力更新

D46 explicit `WorkerSupervisor(profile="python-stdlib-single")` 可用於固定四檔stdlibsingleprocess developer驗證：真D44候選→正確中文清單output，51新cases／完整1,202PASS／exact7回退。[驗收](../evidence/RI-004-worker-2026-10-11/REPORT.md)。RI-004整體PARTIAL；仍無已啟用chat skill／registryinstall/enable/revoke產品入口，不自行批准。OS/runtime/profile有限、無trustedfallback，一般deps／multiprocess／其他OS／aggregateRAM未認證。

## 2026-10-11 worker lifecycle 更新

FIX-011的trusted-local worker有界輸入、continuous stdout/stderr drain、manifestms timeout、spawn/repeatedcancel/PIDnamespace cleanup及strictJSON輸出已限定VERIFIED；24新case／完整1,151PASS／exact5回退。[證據](../evidence/FIX-011-2026-10-11/REPORT.md)。沒有新增對話可執行技能；D44待審候選仍不install/enable。RI-004下一步strict worker＋人工批准/撤銷接原registry/catalog，不能把trustedprofile認成敵意generatedruntime。

## RI-004 completion addendum — 2026-10-10

候選技能產品接入 **Partially Implemented**；explicit-owner fixed Markdown checklist candidate／real isolated verification／safe review與手動JSON export切片 **Implemented and Verified**。入口candidate profile「電腦協助→學習新能力」，同一catalog查全部typed aliases，無既有能力executor effects；固定四檔package、complete hash、獨立trustedtests與report binding、取消/關閉已驗。88新增、完整1,127PASS、temporary Gateway／真Chrome23checks與exact6source回退PASS。[驗收與回退](../evidence/RI-004-2026-10-10/REPORT.md)。

這不表示SIRO已能在聊天中使用新技能：不安裝／啟用／查installed registry、不做任意model生成或repeated-work intake；registry/dispatcher/worker原模組保留。未審核永遠unreviewed/disabled。真正worker boundary／explicitapproval／撤銷及RI-005 release gates保持，不能把新入口當自主進化DONE。

## RI-003 completion addendum — 2026-10-10

不可信候選驗證：**Partially Implemented**；Linux x86_64／system CPython3.14／`python-unittest-single`／explicit owner CLI的有限切片 **Implemented and Verified**。實際入口 `siro verify-patch`與async service，Core只提供pure preflight；source-only/no-follow、固定trusted runner、真OS/network/filter/resource/cancellation已驗。48新cases、111相鄰與完整1,039PASS；原copy verifier保持trusted-only，不混同新backend。[證據](../evidence/RI-003-2026-10-10/REPORT.md)。

這不代表已有產品自主生成／啟用／部署：一般multiprocess／pytest/deps profile、enabled skill worker與release接線未驗，candidate tests不可信任為批准。下方2026-10-09的「same-user copy不是sandbox」仍適用舊trusted入口；FIX-007/008/009的局部缺陷已由各卡後續修復，不當成現存未修漏洞。

## RI-002 completion addendum — 2026-10-10

唯讀能力inventory現為Implemented and Verified（限定candidate、本機synthetic整合＋真Chrome）：既有catalog /v1/runtime/UI/模型首輪與續輪均接通；availability／safe reason／typedoptionalmetadata、單capture、深拷貝、unknown拒絕與原批准重驗已驗。output契約／未宣告timeout仍unknown，不表示skill generation／MCP runtime或自主部署完成。下方原盤點保留為施工前快照；詳 [RI-002 REPORT](../evidence/RI-002-2026-10-09/REPORT.md)。


## 2026-10-09 現況（取代下方 2026-09-30 的狀態判讀）

此表以現有 dirty working tree 的 caller／source／測試與實測限制為準。狀態僅使用：`Implemented and Verified`、`Implemented but Unverified`、`Partially Implemented`、`Planned Only`、`Missing`、`Deprecated`、`Duplicated`、`Unknown`。

`Implemented and Verified` 必須看範圍：L1/mock、L2/實際程序、L3/人工產品體驗不可互相替代。**本輪窄測 40 passed／9.49s、3 existing warnings**；[命令與安全反例](../evidence/RI-architecture-2026-10-09/REPORT.md)。其他列的現有測試／歷史 evidence 只作已知依據，不冒稱本輪重演了真 provider、renderer、GPU、硬體或長時間產品驗收。整體 T1–T40 矩陣另列，這張表不將 task DONE 直接等同 verified product。

| Feature | Expected Behavior | Existing Implementation | Evidence | Status | Dependencies | Risks | Recommendation |
|---|---|---|---|---|---|---|---|
| Agent loop／native tool messages | 同批工具完成後成對 observation、逐回合有界續作、失敗 intent 不執行 | candidate native histories／batch／run-call ownership／terminal fence 已接；legacy 保留 | `integrated.py:166/554/755/881`、`companion.py:77`；`test_agent_batches.py`、`test_gateway_terminal_fence.py`、FIX-003 evidence | Partially Implemented | ToolOrchestrator／journal／provider contract | 接通不等於長任務理解正確；FIX-006 理解仍未完成 | KEEP 已驗 loop，補具體失敗，不重構另一個 agent |
| Provider abstraction／stream | 同一 ModelRequest，取消／終止可判定 | ConversationEngine → configured adapter；FIX-003 completion 邊界保留 | `conversation.py:90`、`gateway.py:1146`；`test_model_adapters.py`、`test_provider_completion.py` | Partially Implemented | 實際 provider/network／privacy | 真 backend 與模型輸出品質不能由 mock 推論 | KEEP；現有 provider opt-in 實測另記 |
| Provider retry／routing | 未輸出前有限 retry，不能重試已接受 intent／跨 privacy | candidate 已用 FailoverModel 單 provider；Router/compute selection 仍獨立元件 | `gateway.py:1164`、`adapters/models/failover.py`；`test_provider_retry.py`、`test_failover_policy.py` | Partially Implemented | provider metadata／budget | 非通用多 provider 動態路由；未取得額外成本授權不能擴 cloud routes | KEEP RT-009，勿重造 router |
| Product ToolCatalog／availability | definitions／schema／executor／readiness 同源，讀 inventory 無動作 | candidate ToolCatalog 已接 main，definitions 每次 request 過 availability | `orchestrator.py:146–199`、`gateway.py:1516–1565`；本輪 `test_tool_catalog.py` PASS | Implemented and Verified | trusted readiness predicates | 此驗證為 L1＋真 main composition fixture；browser executable 存在不等於頁面一定可讀 | REUSE；只補缺 metadata |
| Complete capability inventory | 如實列 identity/schema/output/permissions/effects/risk/version/source/timeout/failure | ToolDescriptor 僅部分欄位；snapshot 只有 name/available/backend/effect/model_visible | `orchestrator.py:146/189`、`integrated.py:789/443` | Partially Implemented | 上列 catalog／adapter contracts | risk 顯示與 effect 分離；固定「已驗能力」prompt 可能高估實際 readiness | EXTEND 同 catalog；unknown 不授權 |
| Tool permission／execution ownership | proposal args 不可改、跨 run 拒絕、取消不復活 | args hash／proposal state／ExecutionContext；Rust workspace有短效一次 grant；一般 argv 為 owner process | `orchestrator.py:503/537`、`workspace.py:103`；`test_tool_orchestrator.py`、`test_execution_lifecycle.py` | Partially Implemented | owner control／backend scope | 沒有通用 OS sandbox；full mode 不等於自我部署批准 | KEEP；新高風險 capability另立 gate |
| Session／restart history | 同 session 完成 turns 有界恢復，不重播外部效果 | candidate SQLite completed native history hydration與read-only journal recovery | `integrated.py:174/1044/1063`、`runs.py:359/444/502`；`test_session_restore.py`、`test_run_journal.py` | Partially Implemented | SQLite schema13／privacy／session ID | 不是所有任務跨重啟自動續作；unknown action不得重送 | KEEP；避免原 working deque 重做 |
| Context summary（RT-011 切片） | 長歷史有來源的有界壓縮，不捏造工具結果 | local extractive completed-turn summary，session48 messages／budget compaction已接 | `gateway.py:1159/1219`、`integrated.py:181`、`services/agent/summary.py:11`；本輪 `test_context_summary.py` PASS | Implemented and Verified | completed history／ContextBudgetModel | 只驗固定extractive範圍；不是語意摘要／無限記憶 | KEEP；原「MISSING」過時，不再造 summary service |
| Native token／byte budget | serialized request送出前守budget、unknown tokenizer拒絕 | ContextBudgetModel 與 GPTOSSBudget 具實際 caller | `gateway.py:1185–1225`、`context.py:61`、`native_context.py`；`test_native_context_budget.py` | Partially Implemented | 指定 GPT-OSS profile/tokenizer | verified native profile有限；換 backend 不能沿用 token guess | KEEP 已完成budget，不任意解禁其他model |
| Memory read/write/correct/delete | 有來源、scope/privacy、revision、撤銷失效 | candidate明確owner ingress；既有 MemoryService/SQLite/Memory API；更正/刪除清摘要 | `integrated.py:374`、`memory.py:125/164`、`gateway.py:870/918/953`；`test_memory_ingress.py`、`test_memory_v2.py` | Partially Implemented | 原 UserTextEvent／route privacy／SQLite | 不是每輪自動變facts；cloud不能讀local-only；使用者體驗仍需驗 | KEEP；舊「未接 ingress」與舊migration failure不作目前結論 |
| Idle memory organization（RT-015 切片） | idle整理既有來源，前景取消、single owner、可丟棄 | MemoryOrganizer 已接lifespan，100source／5s，exact-duplicate digest不寫facts | `gateway.py:1593/1603/776`、`organization.py:23/98`；本輪 `test_memory_organization.py` PASS | Implemented and Verified | MemoryService／foreground busy／kill switch | 現況不是通用排程、semantic merge或自主活動 | KEEP 已完成切片，擴張先驗 retention／owner |
| Proactive companionship／goals | quiet/busy/cooldown下合適提醒，前景優先，能停止 | ProactivityRules／Planner／jobs／rooms元件存在，Gateway未接其message pump | `proactivity.py:34`、`scripts/t29_room_demo.py`；本輪 `test_proactivity.py` PASS；`test_goals.py` | Partially Implemented | 可信事件／已有 owner／明確用途 | component PASS不能聲稱現在會主動陪伴或走路 | REUSE；只接單一產品用途，不造第二scheduler |
| PC argv control | 已批准命令有界輸出/timeout/取消/readback | candidate bounded argv＋owned process group，已ack detach有不同生命周期 | `gateway.py:1390`、`execution.py:79`；`test_bounded_execution.py`、`test_computer_driver.py` | Partially Implemented | Linux user權限／execution context | 並非host sandbox；只去兩個model envkey不足以宣稱所有secret隔離；真OS範圍有限 | KEEP並如實列scope；不與generated code安全等同 |
| Rust scoped read/list（RT-013） | owner workspace內小檔唯讀，越界拒絕，單owner清理 | candidate WorkspaceRuntime → LocalRuntimeClient → Rust grant/driver已接 | `gateway.py:1468/1505`、`workspace.py:59/103`；`test_workspace_runtime.py`、`test_runtime_product.py` | Partially Implemented | Rust binary／grant wire／指定root | 能力範圍明確；不等於所有PC操作已經Rust或可讀整台機 | KEEP原slice；避免再次「對接」同caller |
| Browser multi-step | session read/fill/click fresh screen_version、origin、TTL/capacity/取消 | candidate BrowserSessions＋ScopedBrowserDriver，非每步關頁 | `gateway.py:1490–1514`、`browser_session.py:37/125`；`test_browser_sessions.py`、`test_browser_driver.py` | Partially Implemented | 真browser／origin scope／screen readback | FIX-002搜尋ScopeViolation尚未確認rootcause；不因URL Markdown症狀就取消scope | KEEP邊界；最小failure診斷／reproduction |
| Web Live2D／affect／relationship | 同一持續狀態更新renderer，斷線恢復emotion而不重播speech | 既有licensed Webrenderer與body transport；affect/preferences/relationships持久化 | `web.py:41/102/118`、`integrated.py:360`、`index.html:48`、renderer scripts；`test_body_failure_isolation.py` | Partially Implemented | 外部合法資產／WebGL／bodychannel | 本輪未真人視覺驗收；全身走路／自由螢幕活動未交付 | KEEP Live2D；REJECT重新引入Unity |
| Desktop free movement／new motions | 角色可在螢幕活動、有真動作與中斷控制 | Companion evolution plan有場景與asset gate；現有renderer不是已完成桌寵 | `COMPANION_EVOLUTION_PLAN.md`「桌寵體驗／缺少動作」；既有 body contract | Planned Only | 可編輯合法角色assets／sceneowner／新motion驗收 | 沒有原model腿部rig不能用假切換宣稱walking | 按原plan小卡製作／驗收，勿重寫Core |
| Speech／completion／segmented playback | 全文可分段朗讀，cancel/replay；首段快速且內容完整 | FIX-005 A/B已有plan/orderedqueue/EOS/cap/cleanup；CUDA SDPA有實測 | `audio/tts.py`、`qwen_tts_worker.py`、`static/index.html`；`docs/evidence/FIX-005-2026-10-07/REPORT.md` | Partially Implemented | 原Qwen模型/聲線／CUDA／native audio | 歷史firstaudio22.446s仍慢、人耳聽驗NOT_RUN；不能稱產品完成 | KEEP FIX-005 PARTIAL，先體驗gate不加新voice架構 |
| Installed skill registry／isolated trusted worker | versioned manifest、disabled預設、sandbox/resource/cancel | SQLiteSkillRegistry＋SkillDispatcher＋WorkerSupervisor存在；本輪bwrap負面fixturePASS | `skills.py:35/65`、`persistence/skills.py:15`、`skill_worker.py:23/132`；本輪 `test_skill_registry.py` PASS | Partially Implemented | Linux bwrap／固定可信package | 新反例：換plugin碼hash不變、sameenabledid/version可到supervisor；無Gatewaycaller | FIX package identity後才接skill；不造registry |
| Skill discovery in product | owner可看purpose/source/version/trust/tests，model只見enabled且可用能力 | manifest部分欄位與registry狀態存在，產品catalog未從registry取得skill | 上列source；全repo SkillDispatcher callers在tests | Partially Implemented | packageintegrity／policy／ToolCatalogprojection | installed≠approved≠enabled≠available；缺source/trust/teststatus | 小範圍擴metadata，disable預設保留 |
| Skill generation／automatic registration | 先existingsearch再candidate/static/sandbox/review/approval | 未找到可生成可審批skill code並接registry的產品鏈；procedural只產candidatefixture | `procedural.py:55`、`test_procedural_candidates.py`；現有plan | Missing | 已修完整hash／隔離／驗證／人工批准 | 不能把proceduralcandidate或LLMcodeblock叫已學會新技能 | P2先只到候選／合成固定skill，不自動enable |
| Self-improvement proposals／verification | 不碰livecore，isolatedtest、review、approvediff | PatchProposal／PatchVerifier與tests存在，無產品proposalclosedloop | `evolution.py:17/34`；本輪 `test_patch_verifier.py` PASS＋[反例](../evidence/RI-architecture-2026-10-09/REPORT.md) | Partially Implemented | 完整changedpaths／OSsandbox／trustedchecks | protecteddelete被漏、sameusercheck能寫copy外；不是untrustedsandbox | FIX invariant；先reviewableproposal，不deploy |
| Release／rollback | 完整簽署相容manifest，launcher用驗證release，DB新寫入不丟 | ReleaseManager與CLI standalone；activepointer未被launcher消費 | `releases.py:42/87/103`、`cli.py:114`、`scripts/launch_companion.py`；本輪release tests＋schema反例 | Partially Implemented | 人工維護／stoppedwriters／compatdata策略 | schema界線未簽；rollback整DB可覆蓋新memory/ledger；不能自動部署 | RED gate，拆小卡修整，不接runtimeautodeploy |
| Runtime MCP tools | 已授權servers的list/call/cancel/limits與policy | `src/siro`未找到runtime MCP client／tooladapter；devMCP另列 | source搜尋 `MCP/mcp`、Gatewayhandlers／ToolCatalog | Missing | serverallowlist／session/env/network/outputcontracts | devclient可用不等於SIRO可用；不得外送私碼／秘密 | P1先design與read-onlymetadata；不本輪新runtime |
| ESP32／HA／device catalog | 配對descriptor、TTL、ACK≠readback、expiry/idempotency | DeviceRegistry／MQTTprotocol／HAadapter／firmware存在，未接Gatewaymodeltool | `devices.py:30/74`、`mqtt.py:19/47/84`、`home_assistant.py:217/275`；本輪registry/HAfixturePASS | Partially Implemented | 實體板／HA／networkpairing／明確action | 未做真hardware動作；勿宣稱smarthomeready | REUSE契約，禁止rawpin探測；L3另驗 |
| Software reverse engineering | 授權下優先官方API/CLI/docs/source/GUI | 現有pc/browser可作部分interaction；沒有binaryanalysis產品流程 | 現有adapters、此輪`RUNTIME_INTELLIGENCE_DESIGN.md` | Planned Only | 具體受權caller／工具收益／sandbox | 新大依賴無即時產品收益；decompile不是原source/license | P3研究；不安裝Ghidra/LSP平行工具 |
| Unity presentation | 歷史方案不能推回已運作Webbody | 現有caller指向Webbody；無Unity產品runtime接線 | `gateway.py:1121/1136/1583`、renderer scripts、使用者最新要求 | Deprecated | 無 | 歷史docs可能誤導 | REJECT重引入Unity |

本輪沒有證據把 ToolCatalog／SkillRegistry／DeviceRegistry 判為 `Duplicated`；三者責任不同。沒有具體來源／caller可確認的外部能力為 `Unknown`，不能因表格想填滿就寫 `Missing` 或 `Implemented and Verified`。本表中的 Missing 有 source搜索與composition查證範圍，並不宣稱整台主機不存在任何第三方工具。

---

## 2026-09-30 歷史分類（保留來源，不作目前完成判斷）

分類以正式 Gateway 整合能力為範圍。PARTIAL 可包含完整且通過測試的子元件；不代表每個子元件都需改。Confidence 高＝caller/source 明確；外部 runtime 驗證仍可未知。

## Agent loop / Tool calling

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/services/presentation/integrated.py`
- Entry point / Caller：Gateway on_turn/on_tool_result
- Callee / Runtime wiring / output consumer：respond → _propose_tool_calls → continue_after_tool；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：tool catalog + auto_authorize
- Tests：`tests/integration/test_integrated_companion.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：單工具 fake executor 閉環已測；多工具逐一遞迴 continuation，可能在同批工具完成前結束 run；原生 messages 未接入。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## LLM invocation / Provider abstraction

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/conversation.py`; `src/siro/adapters/models/openai_compatible.py`; `src/siro/adapters/models/ollama.py`
- Entry point / Caller：Gateway main → Core
- Callee / Runtime wiring / output consumer：ConversationEngine.respond → LanguageModel.stream；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：SIRO_OLLAMA_MODEL 或 SIRO_OPENAI_*
- Tests：`tests/contract/test_model_adapters.py; tests/real/test_model_providers.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：adapter/stream contract 通過；5 個真服務測試總計跳過，不能確認現在真 backend 可用。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Provider routing / Provider fallback

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/router.py`; `src/siro/adapters/models/failover.py`
- Entry point / Caller：測試 caller；Gateway 僅 if/elif 選模型
- Callee / Runtime wiring / output consumer：Router / FailoverModel.stream；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：Gateway env startup selection
- Tests：`tests/test_router.py; tests/contract/test_model_adapters.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：演算法與 fallback 存在；正式 main 未使用。Failover emitted 只追 text，tool_request 後失敗是否重試需專測。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Tool registry / Tool availability

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/services/tools/orchestrator.py`; `src/siro/core/skills.py`; `src/siro/persistence/skills.py`
- Entry point / Caller：Gateway main registration；SkillRegistry 為獨立路徑
- Callee / Runtime wiring / output consumer：ToolOrchestrator.propose → executors dictionary；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：兩個模型 tool definitions、三個 executor
- Tests：`tests/integration/test_tool_orchestrator.py; tests/integration/test_skill_registry.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：catalog 與 executor 分開；無環境健康動態 availability；skill install/enable 不會自動加入模型工具。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Tool permissions

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/authorization.py`; `src/siro/services/tools/orchestrator.py`; `runtime/siro-runtime/src/rpc.rs`
- Entry point / Caller：Gateway executor 和 Rust RPC 為兩條路
- Callee / Runtime wiring / output consumer：proposal hash/state；Rust grant validate；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：full mode + tools switch；Rust secret/roots
- Tests：`tests/integration/test_runtime_boundary.py; tests/integration/test_tool_orchestrator.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：兩條權限路徑未統一；不是缺授權確認，而是執行邊界不一致。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Streaming / Incremental rendering

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/conversation.py`; `src/siro/services/presentation/gateway.py`; `src/siro/services/presentation/static/index.html`
- Entry point / Caller：IntegratedCompanion.delta / WebSocket consumer
- Callee / Runtime wiring / output consumer：ModelChunk → on_delta → GatewayHub → DOM；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：selected provider；control WS
- Tests：`tests/integration/test_integrated_companion.py; tests/integration/test_gateway.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：文字閉環注入測試通過；真 browser/provider 本次未驗；TTS 完整音訊才回傳。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Live2D / character rendering / Character state

- Status：IMPLEMENTED_UNVERIFIED
- Evidence / Relevant files：`src/siro/adapters/body/web.py`; `src/siro/services/presentation/gateway.py`; `src/siro/services/presentation/static/body.html`
- Entry point / Caller：IntegratedCompanion → body；UI iframe
- Callee / Runtime wiring / output consumer：body intent → WebSocket transport → renderer；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：SIRO_LIVE2D_DIST；否則 placeholder
- Tests：`tests/contract/test_body_adapter.py; tests/integration/test_body_failure_isolation.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：transport/mount test 有；本次沒有真 WebGL、動作、重連可視驗證。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Emotion state / Relationship state

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/affect.py`; `src/siro/core/relationships.py`; `src/siro/core/expression.py`; `src/siro/services/presentation/integrated.py`
- Entry point / Caller：IntegratedCompanion.respond
- Callee / Runtime wiring / output consumer：user event → appraisal/update → persistence → expression/context；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：owner/self preferences、SQLite state
- Tests：`tests/integration/test_affect_persistence.py; tests/integration/test_relationships.py; tests/integration/test_integrated_companion.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：live user-text branch 存在；AffectDecisionLoop goal/action path 主要在 test，長期真人效度未知。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Session / Context management / Short-term memory

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/memory.py`; `src/siro/core/companion.py`; `src/siro/persistence/conversation.py`
- Entry point / Caller：CompanionCore.respond
- Callee / Runtime wiring / output consumer：WorkingMemory deque(12) → assemble_prompt；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：session_id；UI 使用 browser
- Tests：`tests/integration/test_conversation.py; tests/integration/test_persistent_companion.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：12 messages 不是 token budget；重啟不重建 working context；多分頁固定 session 有衝突風險。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Context compression

- Status：MISSING
- Evidence / Relevant files：`src/siro/core/memory.py`
- Entry point / Caller：CompanionCore
- Callee / Runtime wiring / output consumer：只有 bounded recent deque；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：無 compression config
- Tests：`tests/integration/test_persistent_companion.py（不驗 compression）`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：在已查正式路徑未找到 token-aware summary/compression；不把 Dream consolidation 當成 context compaction。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Long-term memory / Persistence

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/memory.py`; `src/siro/persistence/memory.py`; `src/siro/persistence/sqlite.py`
- Entry point / Caller：CompanionCore + Gateway memory API
- Callee / Runtime wiring / output consumer：recall / browse / correct / delete → SQLite；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：SIRO_DATA_DIR；migrations 001–012
- Tests：`tests/integration/test_memory_v2.py; tests/integration/test_sqlite_store.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：repository 豐富；正式聊天自動寫長期記憶未接；migration test 現在失敗。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Goal state

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/persistence/goals.py`; `src/siro/core/cognition.py`; `src/siro/services/agent/runs.py`
- Entry point / Caller：IntegratedCompanion 用 AgentRun，未用 cognition Planner
- Callee / Runtime wiring / output consumer：goal repository；AgentRun.start/append；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：max_agent_steps=8
- Tests：`tests/integration/test_goals.py; tests/integration/test_agent_runs.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：兩種 goal/state 分立；AgentRun persistence 不代表已可恢復任務。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Proactive behavior / Task scheduling / Background tasks

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/proactivity.py`; `src/siro/core/consolidation.py`; `src/siro/core/jobs.py`; `src/siro/core/rooms.py`
- Entry point / Caller：room demo、tests；Gateway 未建立 scheduler
- Callee / Runtime wiring / output consumer：rules.choose / scheduler / job lease；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：SiroSettings enabled=false，但 Gateway 不載入 JSON settings
- Tests：`tests/test_proactivity.py; tests/integration/test_consolidation.py; tests/test_jobs.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：有規則/排程元件；無正式主動訊息 pump，勿宣稱自主陪伴已運作。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Event system

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/events/local.py`; `src/siro/events/nats.py`; `src/siro/events/replay.py`
- Entry point / Caller：獨立 tests；IntegratedCompanion 直接 record_event
- Callee / Runtime wiring / output consumer：publish/subscription / outbox / replay；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：NATS broker configuration
- Tests：`tests/test_local_event_bus.py; tests/integration/test_nats_delivery.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：本機 bus 與 durable bus 有測試；正式 Gateway 不經 bus 驅動所有模組。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## PC control / OS interaction / File access

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/services/presentation/gateway.py`; `src/siro/adapters/computer.py`; `runtime/siro-runtime/src/linux.rs`
- Entry point / Caller：Gateway main closures；Rust independent RPC
- Callee / Runtime wiring / output consumer：computer.execute → subprocess；另有 scoped LinuxDriver；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：direct argv/cwd/timeout/detach
- Tests：`tests/integration/test_computer_driver.py; Rust Linux tests`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：Driver tests 不驗 main closure；取消 process tree、持久 execution session、sudo bridge 不完整。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Browser/web integration

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/adapters/browser.py`; `src/siro/services/presentation/gateway.py`
- Entry point / Caller：ToolOrchestrator
- Callee / Runtime wiring / output consumer：execute_browser → ScopedBrowserDriver.navigate → close；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：origin from requested URL；catalog only navigate+read
- Tests：`tests/integration/test_browser_driver.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：driver 有 fill/click/screenshots；產品僅 navigate/read，不能維持跨步 page。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## External APIs

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/adapters/models/openai_compatible.py`; `src/siro/services/audio/stt.py`; `src/siro/adapters/home_assistant.py`
- Entry point / Caller：model/STT Gateway；HA test/demo
- Callee / Runtime wiring / output consumer：HTTP/SSE-like model lines、STT REST、HA REST/WS；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：provider env；HA credentials external
- Tests：`tests/real; tests/integration/test_home_assistant.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：真 provider 未重驗、真 HA 未驗；存在 adapter 不代表都啟用。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Device abstraction / ESP32 / Smart-home readiness

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/devices.py`; `src/siro/adapters/devices.py`; `src/siro/services/devices/mqtt.py`; `firmware/esp32/src/main.cpp`
- Entry point / Caller：simulator/tests/demo
- Callee / Runtime wiring / output consumer：descriptor/projector → room actions；MQTT commands/ACK；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：broker/device secrets example；room opt-in
- Tests：`tests/integration/test_device_registry.py; tests/integration/test_mqtt_gateway.py; tests/integration/test_room_automation.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：有 firmware 與協定，無本次真板/真 HA/真 sensor-actuator 或 Gateway 接入證據。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## IPC / Rust runtime

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/adapters/runtime.py`; `runtime/siro-runtime/src/main.rs`; `src/siro/services/compute/worker.py`
- Entry point / Caller：tests/standalone commands；Gateway 未用 RuntimeClient
- Callee / Runtime wiring / output consumer：local RPC serve_once；compute TCP JSON-lines；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：SIRO_RUNTIME_SOCKET/SECRET/DB/ROOTS
- Tests：`tests/integration/test_runtime_boundary.py; tests/integration/test_compute_fabric.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：真 local boundary tests 通過；不是產品所有工具已使用 Rust。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Process lifecycle / Process supervision / Shutdown behavior

- Status：PARTIAL
- Evidence / Relevant files：`operations.py`; `scripts/start`; `scripts/stop`; `src/siro/services/presentation/gateway.py`; `src/siro/services/audio/tts.py`
- Entry point / Caller：operator CLI/scripts + Uvicorn
- Callee / Runtime wiring / output consumer：systemd Restart；lifespan on_cancel + hub.shutdown；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：user unit/env；Qwen lazy child
- Tests：`tests/integration/test_operational_cli.py; tests/integration/test_gateway.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：Qwen 無 close；startup timeout 可留下 child；render timeout 後同 pipe 有讀到上次回覆風險。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Retry / Fallback / Error recovery

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/adapters/models/failover.py`; `src/siro/core/jobs.py`; `src/siro/services/tools/orchestrator.py`
- Entry point / Caller：tests；active tool path 僅 generic failure observation
- Callee / Runtime wiring / output consumer：component fallback/leases；executor error → type name；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：provider timeout/step cap
- Tests：`tests/contract/test_model_adapters.py; tests/test_jobs.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：無正式通用 retry policy；Qwen/Kokoro/Edge 是啟動選擇，不是執行錯誤 fallback。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Cancellation / Timeout handling

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/core/conversation.py`; `src/siro/adapters/models/http.py`; `src/siro/services/presentation/integrated.py`; `src/siro/services/audio/tts.py`
- Entry point / Caller：HTTP cancel → controller callback
- Callee / Runtime wiring / output consumer：cancel token → provider；IntegratedCompanion.cancel → active sessions/body；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：conversation 120s；argv 1–120s；Qwen 900s
- Tests：`tests/integration/test_conversation.py; tests/contract/test_model_adapters.py; tests/test_barge_in.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：LLM 已測；executor 無 token/process handle 傳遞，TTS render 與 browser fetch 取消未形成一致鏈。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Logging / Observability

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/services/presentation/gateway.py`; `src/siro/core/conversation.py`; `src/siro/services/agent/runs.py`; `src/siro/redaction.py`
- Entry point / Caller：log handler optional；UI control
- Callee / Runtime wiring / output consumer：rotating log / signals / run steps / UI events；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：SIRO_LOG_DIR，14-day rotation
- Tests：`tests/test_redaction.py; tests/integration/test_agent_runs.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：trace/error details 分散；不可把持久 observation 直接當 secret-safe 記錄。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Config management / Secrets/config separation

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/config.py`; `src/siro/services/presentation/gateway.py`; `operations.py`
- Entry point / Caller：CLI/doctor；Gateway separate config
- Callee / Runtime wiring / output consumer：load_settings CLI vs env main；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：JSON schema v1 + SIRO_* env
- Tests：`tests/test_config.py; tests/integration/test_operational_cli.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：配置未統一；child_env 只移除兩個 key；本次未讀 secret；runtime cache/model 仍有 untracked 項。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Testing / Regression testing

- Status：PARTIAL
- Evidence / Relevant files：`tests`; `scripts/check`
- Entry point / Caller：developer/CI
- Callee / Runtime wiring / output consumer：pytest/ruff/mypy/cargo；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：real provider opt-in
- Tests：`193 pass / 1 fail / 5 skip；Rust 6 pass`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：真 main/executor、多工具、Qwen recovery、真硬體未被本次套件完整驗證。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## Restart recovery

- Status：PARTIAL
- Evidence / Relevant files：`src/siro/services/agent/runs.py`; `src/siro/persistence/conversation.py`; `src/siro/core/companion.py`
- Entry point / Caller：continuation only；無 startup reconciliation
- Callee / Runtime wiring / output consumer：SQLite data survived；latest run lookup；輸出是否接至產品請對照 DATA_FLOW。
- Configuration：data dir / user unit
- Tests：`tests/integration/test_agent_runs.py; tests/integration/test_persistent_companion.py`。本次套件結果見 REGRESSION_BASELINE；不自動代表真 main 整合。
- Known gaps / failure / cancellation：沒有 pending effect reconcile 或 persisted tool message reconstruction；自動重播有副作用需避免。
- Confidence：高（source/caller）；真服務、硬體、跨重啟產品體驗未證實部分為 UNKNOWN。

## 16 項驗證規則的共用判讀

上述每列已辨別 production library、正式 caller、constructor/registration、配置、consumer 與 tests。沒有 main caller 的元件標 PARTIAL，不能因 import 存在升級完成。SOURCE_INVENTORY 提供全檔 symbols/import。

TODO/pass 掃描：未發現用 NotImplemented 填補主要功能的證據。pass 多為 exception class 或 exception handling，不能單凭 pass 判定 stub。新舊路徑與活動實作見 DEAD_OR_UNUSED_CODE；failure、shutdown、cancel 缺口逐列及 friction map 記錄。缺少真服務證據保持 UNKNOWN，不猜測帳號/硬體可用性。
