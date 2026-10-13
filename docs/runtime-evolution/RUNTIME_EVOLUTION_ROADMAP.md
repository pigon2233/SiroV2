# Runtime evolution roadmap

## 2026-10-13 — actual cloud verification follow-up

FIX-016 local final five-file scripts/checkPASS（1697PASS/5opt-inSKIP/3warnings；419.283s）但remote54FAIL暴露supportedrunner不足、SQLite反例不portable與FIX-017 eager optional SDK import。整体FAILED_VERIFICATION；不是以skip/mute放行。先完成窄FIX-017 owner invariant、沿官方supportedrunner补齐验证环境及正确SQLite反例；RI-005/006继续BLOCKED_BY_FIX，不重做RT DONE、不重編/ranking。


## 2026-10-13 — FIX-016 clean CI repair IN_PROGRESS

FIX-016 REQUIRED_FIX/MEDIUM；只修既有bootstrap與精確public-pin gate。RI-005/RI-006後續實作標 **BLOCKED_BY_FIX: FIX-016**，完整scripts/check與新head Actions通過前不往後擴張。原RT DONE/編號/產品與發布gates保持；不做ranking。Python預裝不一致為TECH_DEBT，本卡不改pin/lock。


## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

**KEEP RI-005 / SPLIT remaining gates**：D52signedsource選擇、actualloadedversion與同schemaHTTPready切片VERIFIED。95新cases；最終相鄰335 PASS／3既有warnings／25.63s，完整 **1,673 PASS／5 real_provider未選／3既有warnings／199.58s**。Ruff315、mypy250（含launcher）、schema、source/tests/docs diff PASS。

| 既有scope | 決定 | 現況 |
|---|---|---|
| RI-005 D52 source launch | VERIFIED限定切片 | 真1→2→rollback1、保最新data、wrongABI/tamper拒、無hostfallback |
| RI-005 full adoption/handoff | KEEP / SPLIT / PARTIAL | old/unmanagedwriter、immutable exactpackage/verify gap、approved maintenance→runtimehandoff保留BLOCKED_BY_RELEASE_INTEGRATION |
| RI-006 | KEEP | 下一唯讀來源失敗提案，不自批或執行 |
| RT-011/013/015 | 原scopedDONE保持 | 不重做、不重編號 |
| FIX-002/005/006 | PARTIAL保持 | 搜尋／語音速度人耳／理解產品gate |

下一三既有範圍（非ranking）：RI-005oldwriter/adoption；RI-005exact immutable approvedhandoff；RI-006唯讀proposal。沒有新增重編/硬CANCEL抽象任務理由。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：舊／非受管writer停止、parent驗簽後sameUID換包、maintenance→exec CLOEXEC空窗與人工批准handoff未解除。D52只證同schema／D52-compatible src package，任意deps/ABI/migration/其他OS/powerloss/正式deployment未證。FIX-002/005/006產品gates、RT-011/013/015原scopedDONE不變。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

**FIX-015 DONE / VERIFIED**：backup cancellation staging/connection/CLI teardown的最小修復已驗；原D50/FIX-014 DONE保留。新25 cases、相鄰240 PASS（17.60s）；完整 **1,578 PASS／5 real_provider 未選／3既有 warnings／198.40s**。Ruff311／mypy245／schema／diff PASS。

| 既有卡／範圍 | 決定 | 依賴與現況 |
|---|---|---|
| FIX-015 | DONE / VERIFIED | 解除ZIP取消cleanup局部BLOCKED_BY_FIX |
| RI-005 | KEEP / SPLIT / PARTIAL | first-adoption停止舊writer；actual signed launcher/version/readiness/批准handoff仍BLOCKED_BY_RELEASE_INTEGRATION |
| RI-006 | KEEP | 已有來源失敗到唯讀proposal；不能自批執行／部署 |
| RT-011 / RT-013 / RT-015 | 原scopedDONE保持 | 已實現能力不重做、不修改編號歷史 |
| FIX-002 / FIX-005 / FIX-006 | PARTIAL保持 | 有用搜尋、語音速度／人耳、理解各自產品gate |

Recommended next 3既有續作範圍（不是ranking）：RI-005舊writer停止證據；RI-005批准的exact版本launcher/readiness/handoff；RI-006唯讀proposal。沒有實證支援硬CANCEL、MERGE或額外抽象擴張。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：first-adoption舊／非受管writer停止、真正signed launcher/version/readiness與人工批准handoff仍待各自驗收。FIX-002有用搜尋、FIX-005語音速度／人耳、FIX-006理解產品gate保持；RT-011/013/015原scopedDONE及編號不改。

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

## 2026-10-11 RI-004 fixed strict worker 切片已驗收

**KEEP RI-004／SPLIT product activation**：D46 Linux x86_64/systemPython3.14/stdlibsingleprocess已VERIFIED，真D44候選→strictworker正確解析、51新cases／完整1,202PASS／exact7rollback。[證據](../evidence/RI-004-worker-2026-10-11/REPORT.md)。局部workerOS/取消gate在此profile解除；整卡PARTIAL，下一步server-heldreview／package-bound人工批准／disabledinstall／explicit enable/revoke／既有catalog。不能以workerPASS自行批准；一般依賴/多程序/其他OS/aggregateRAM仍未驗。RI-005/006與FIX-002/005/006門檻不變，不改RT編號／ranking／原DONE。

## 2026-10-11 RI-004 實際worker接入前驗證

實際synthetic worker lifecycle audit確認洪水wait deadlock、合法output single-read、spawn/stdin cancel ownership缺口。**FIX-011 REQUIRED_FIX／HIGH已DONE／VERIFIED**（D45），24新case／完整1,151PASS及exact5回退解除此局部block；RI-004可開始strict worker窄驗證；原D44待審切片VERIFIED仍有效，不撤原RT DONE／不重編號。修復只恢復owned lifecycle，trusted profile不因此變成安全generated runtime；strict profile與人工批准仍另驗。[定義](../evidence/FIX-011-2026-10-11/repair-definition.md)／[驗收](../evidence/FIX-011-2026-10-11/REPORT.md)。

## 2026-10-10 RI-004 待審候選切片已驗收

RI-004整體PARTIAL，D44 fixed-template／typedcatalog／realverification／review-export切片VERIFIED；1,127full、真Chrome23checks與exact6回退PASS。**KEEP RI-004，SPLIT**下一個fixed read-only worker OS/cancel/permission驗收與package-bound securityreview／ownerapproval／registry/catalog／撤銷；當前不安裝啟用。**KEEP RI-005**原launcher/singlewriter/latestdata gate；FIX-002/005/006品質gate保持，RT歷史與DONE不重編／不重開。[報告](../evidence/RI-004-2026-10-10/REPORT.md)。

## 2026-10-10 RI-003 有界隔離切片已驗收

RI-003 整體 PARTIAL；Linux x86_64／system CPython 3.14／stdlib synchronous unittest／explicit owner CLI 切片 VERIFIED（D43）。48 新 cases 修前 FAIL → 111 新舊專項 PASS，完整 1,039 PASS／5 real_provider 未選／3 既有 warnings，獨立 source review、真 OS／SIGINT 與 exact 六檔 source 回退 PASS。[報告](../evidence/RI-003-2026-10-10/REPORT.md)。不新增排序／改 RT 編號或重開 DONE。

**KEEP RI-004、SPLIT 接入 gate**：可依已驗 profile 做一個 disabled read-only candidate／verification／review；實際 enabled worker 必須另外驗其隔離、權限與明確批准，不繼承 patch-check PASS。一般 multi-process／dependencies profile 仍 BLOCKED_BY_OS_ISOLATION；AS/file-data caps 不宣稱 aggregate kernel RAM。RI-005 原 launcher／single-writer／latest-data rollback gate 保留。FIX-002／005／006 品質 gates 不被 1,039 PASS 解開。

## 2026-10-10 FIX-010 局部修復已 VERIFIED

既有auto approval交易補unknown-effect跨新UUID的exact content guard、同cap無法驗binding保守manual；真Chrome21checks、45修前FAIL→122相鄰PASS、完整991PASS與exact5file回退已驗。FIX-010 DONE/VERIFIED解除此局部gate；RI-004/RI-006執行仍需RI-003／批准/各自依賴，不能用本卡PASS推成自主重試或整體理解DONE。無RT重編/重開原DONE；FIX-006／002／005保持各自PARTIAL。原完成usage/reasoning實驗已REJECT production effort變動。[報告](../evidence/FIX-010-2026-10-10/REPORT.md)。

接續RI-003的明確Linux single-process隔離切片：先驗supported OS/bwrap/seccomp/source-only mount與trusted profile，缺條件fail closed；不把現有copyverifier稱untrusted sandbox。多程序aggregate cgroup限額未驗，原OS gate尚未解除。不新增排序／RT編號。


## 2026-10-10 FIX-006 局部修復與實際理解差距

FIX-006 **PARTIAL**（D41），latest recorded same-session安全故障摘要與truthful接口facts已驗；40反例→55專項/adjacentPASS、完整946PASS。Configured provider合成paired有自身故障事實收益，但voice-correction截斷／unknown-effect重做語意未PASS，產品理解仍**BLOCKED_BY_FIX：FIX-006**。下一步窄幅usage/reasoning診斷，不先換provider/提高budget或新增intelligence service。原RT號碼與DONE歷史不變，不重做已解決greeting/summary/Rust/organizer。[證據](../evidence/FIX-006-2026-10-10/REPORT.md)。

FIX-006補充量測已完成：[8次synthetic allocation](../evidence/FIX-006-2026-10-10/COMPLETION_ALLOCATION.md) 支持reasoning與visible verbosity混合；low仍有length與錯誤語意，REJECT本輪改production effort，不提高budget/換backend。新429有量到但不回推原事件，零自動重試。

## 2026-10-10 FIX-007 approved identity 已驗

FIX-007 DONE/VERIFIED（D40）：既有digest/registry/dispatcher局部補齊，完整package、root/hash授權一致、frozen delivery、取消cleanup／8副本與concurrency metadata通過；全套906PASS。FIX-007–009局部修復均已驗，**RI-003真OS隔離/可信checks、RI-004生成／review/explicit enable、RI-005 launcher／批准／資料保留仍未完成**，不把安全元件修好當自主產品接入。原RT編號與DONE歷史保留；接續FIX-006產品文字理解，FIX-002／005仍各自PARTIAL。[證據](../evidence/FIX-007-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-009 完整簽署局部驗收

FIX-009 DONE/VERIFIED：相容範圍與完整 manifest 綁版本化HMAC、舊格式拒絕、zero effects與真CLI temporary fixtures通過；全套863PASS。只改既有驗證邊界，不接launcher／自動發布、不改backup/rollback。RI-005仍 **BLOCKED_BY_RELEASE_INTEGRATION**（人工批准／single writer／launcher／最新資料保留），不是簽章修好就可部署。FIX-008保持已驗、下一卡FIX-007；原RT號碼／DONE歷史不改。[證據](../evidence/FIX-009-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-008 protected-path局部修復已驗

FIX-008 DONE/VERIFIED：原PatchVerifier完整old/new集合與有限text dialect，46修前失敗消除、新舊63專項與全套829PASS。只改1 production檔，無新abstraction／依賴／runtime接入。FIX-008本身gate解除；RI-003的**untrusted checks仍需真正OS isolation及可信check allowlist**，RI-004另需FIX-007/review/enable，RI-005另需FIX-009/launcher/資料保留回退。原RT DONE及編號不變，不把元件修复當自動進化已可發布。[證據](../evidence/FIX-008-2026-10-10/REPORT.md)。下一張獨立已確認修復為FIX-009完整簽署相容欄位。


## 2026-10-10 FIX-002 局部修復與保留gate

FIX-002改為PARTIAL：typed reason／可讀主頁partial／關閉時pending-route錯誤已局部修復，原origin、hash、批准、DB及RT歷史不改。真Bing只讀頁首、DuckDuckGo human challenge，useful public search未PASS；自動網路研究仍BLOCKED_BY_FIX：FIX-002。另兩次4s public cleanup逾時的根因尚UNKNOWN；最終單次cleanup成功不抵銷。詳見[交付與驗收](../evidence/FIX-002-2026-10-10/REPORT.md)。

可繼續獨立已確認FIX-007／008／009，不能讓生成技能／untrusted checks／release越過各自gate。FIX-005聲音與FIX-006理解仍各自未完成；未用搜尋fixture替代整體產品驗收。以下2026-10-07 PLANNED是歷史快照，以本節與FIX_REGISTER現況為準。


## 2026-10-09 Runtime Intelligence incremental plan（現況優先）

使用者本輪授權現況盤點、開發期 Codebase Memory 與必要低風險改善；不是授權正常運作中的 SIRO 自改核心或部署。沿用原 T01–T40／RT-001–015／FIX 歷史，新增 RI 識別碼不表示排名。不重新延期或重做已完成 RT-011／013／015。

產出入口：[現況與 call chains](CURRENT_ARCHITECTURE_AUDIT.md)、[唯一 T1–T40 矩陣](ROADMAP_RECONCILIATION.md)、[Codebase Memory](CODEBASE_MEMORY_INTEGRATION_REPORT.md)、[Runtime Intelligence 契約設計](RUNTIME_INTELLIGENCE_DESIGN.md)。既有桌寵／動作／主動追蹤沿 [COMPANION_EVOLUTION_PLAN](COMPANION_EVOLUTION_PLAN.md)，不另造平行產品計畫。

| Phase | 保留／新增工作 | 狀態與接入條件 |
|---|---|---|
| P0 現況、穩定性、開發理解 | RI-001；既有 FIX-002／005／006；新 FIX-007／008／009 | 先驗真問題。005仍PARTIAL；FIX-008已局部驗收，FIX-007／009局部已驗，接入／发布gates保留。全套PASS不能解開自主安全gate |
| P1 工具理解與探索 | RI-002 | 擴現有ToolCatalog唯讀metadata，不新增registry／executor。探索不得啟動CLI/API/MCP副作用 |
| P2 候選技能與安全測試 | RI-003、RI-004 | RI-003 Linux single-process patch profile VERIFIED、整體 PARTIAL；FIX-007/008已驗。disabled candidate/review可沿該profile；實際skill worker／其他profiles與explicit批准仍獨立gate，未批准不可enabled |
| P3 受控改善、發布、軟體理解 | RI-005、RI-006；授權軟體分析後續切片 | FIX-009局部已驗；BLOCKED_BY_RELEASE_INTEGRATION：正式啟用另需launcher、人工批准與最新資料保留回退。proposal可與發布分離 |

**本輪不 CANCEL 原T卡或RT卡**：已有成果保留，未找到整張原需求被現實否定的證據。拒絕新增平行memory DB/vector DB/scheduler/registry/model router；不用未接線helper作為擴張理由。高耦合先記債，不按檔案行數重構。沒有證據支持重開已完成native messages／summary／Rust scoped caller／bounded memory organizer。

### RI-001

- Task ID: RI-001
- Title: 開發期受限 Codebase Memory 與真實現況核對
- Current State: Implemented and Verified（限定本機開發工具與離線驗證）
- Objective: 使後續開發可查真source graph，排除私人資料並消除過期DONE推論。
- Affected Modules: 開發launcher／project MCP config／現有audit與matrix；不接production runtime。
- Dependencies: 固定版官方來源/checksum、Linux bubblewrap、Git inventory、原dirty baseline。
- Implementation Scope: readonly analysis profile、source-only projection、乾淨env、無網路、watcher/auto-index/UI關閉；直接MCP protocol驗證；補排除與stale tests。
- Acceptance Criteria: source/hash/exclusions可追溯；tool mutations被拒；真MCP查詢與source交叉核對；私人資料不可見；原runtime hashes與health不變。
- Tests: 30個developer tool負面／相容測試、12項真OS隔離探針、全套離線回歸；實際數值與限制見report。
- Risks: 靜態解析缺動態callback；初次startup成本；平台限定Linux；checksum不等於attestation；當前chat tool catalog未hot reload。
- Rollback: project config設enabled=false或移除本輪server；移除新增開發helper/lock/tests及可丟棄cache/source；不重啟SIRO、不回復私人DB；保留本輪前dirty files。
- Status: DONE（開發工具／protocol verified；目前chat須重載後確認新MCP tools，本輪未驗證顯示）

### RI-002

- Task ID: RI-002
- Title: 既有catalog的能力說明與唯讀inventory
- Current State: Implemented and Verified（限定candidate唯讀inventory與本機synthetic整合／真Chrome）
- Objective: SIRO能正確辨識已註冊能力與不可用原因，減少錯選工具／誤稱權限。
- Affected Modules: ToolDescriptor／ToolCatalog／既有模型工具描述；需要時既有UI snapshot。
- Dependencies: RT-007既有catalog；FIX-002搜尋診斷仍獨立；不依賴新MCP runtime。
- Implementation Scope: 先補typed純metadata投影：identity/description/schema/I-O/permissions/effects/risk/availability/version/provenance/timeout/failure；未知值明示。保持原definition及executor來源唯一。
- Acceptance Criteria: inventory與definitions/executor/availability一致；無探索副作用；未註冊能力不捏造；metadata不是grant；unknown不自動放行。
- Tests: schemas、缺依賴／停用／stale availability、沒有executor invocation、原tool/batch/cancel回歸。
- Risks: metadata重複或risk誤分類；不得為UI顯示改授權語意。
- Rollback: 撤純metadata/讀取入口，保留既有catalog、proposal、grant與journal。
- Status: DONE（2026-10-10；2026-10-09開始）。716 offline PASS／5 deselected／3既有warnings；15新專項與真Chrome13checks PASS，零executor discovery。initial／continuation用同次capture，原schema／legacy／批准／dispatch重驗保留；optional未知output/deadline明示null。回退temp reverse/reapply精確SHA PASS。詳 [RI-002 REPORT](../evidence/RI-002-2026-10-09/REPORT.md)。未測真provider語意／GPU／真人Live2D／soak，8026未重啟，新後端需下次啟動載入；不是自主技能或產品發布。

### RI-003

- Task ID: RI-003
- Title: 不可信候選的有界隔離驗證
- Current State: Partially Implemented（明確owner的Linux single-process patch profile已VERIFIED；其他profiles不在認證範圍）
- Objective: 候選程式跑測試時無法讀私人資料、改host／政策或繞過取消。
- Affected Modules: 既有PatchVerifier與WorkerSupervisor測試入口；重用現有bwrap經驗。
- Dependencies: FIX-008局部已VERIFIED；Linux x86_64／system CPython3.14／bwrap／libseccomp與固定stdlib unittest profile已驗；一般多程序／dependencies profiles仍BLOCKED_BY_OS_ISOLATION。
- Implementation Scope: 一個OS驗證backend；最小source/deps mounts、private scratch、無network／credential、process tree cancel、CPU/RAM/time/output caps。缺隔離即拒絕，不以cwd冒充。
- Acceptance Criteria: 惡意import讀host/寫外部/網路/子程序與洪水全部拒絕；cleanup；原source不變；trusted/unsupported狀態明確。
- Tests: 跨邊界負面fixtures、timeout/cancel/kill／OOM／output flood、原patch/worker回歸；實際OS測試不以mock代替。
- Risks: dependencies供應鏈與kernel邊界；不把本輪開發MCP sandbox當成此能力完成。
- Rollback: 停用untrusted candidate checks；保留proposal/static review；不需資料schema回退。
- Status: PARTIAL（2026-10-10，D43）；Linux `python-unittest-single`／explicit owner CLI切片VERIFIED。48新cases修前FAIL→111專項PASS、完整1,039PASS；真OS／單雙SIGINT／cleanup、獨立source audit與exact六檔source回退PASS。[驗收](../evidence/RI-003-2026-10-10/REPORT.md)。候選可偽造tests，passed非批准；一般multiprocess/threads/pytest/deps與aggregate kernel RAM gate未解除。

### RI-004

- Task ID: RI-004
- Title: 從缺能力到待批准的skill候選
- Current State: Partially Implemented（manifest／registry／dispatcher／procedural candidates已有）
- Objective: 真的缺能力才生成可審核候選，保留擁有者啟用與撤銷。
- Affected Modules: 既有procedural、skill registry/dispatcher、catalog extension point。
- Dependencies: RI-002已VERIFIED；RI-003 Linux single-process patch profile已VERIFIED、其他profile未驗；FIX-007局部已VERIFIED。BLOCKED_BY_SKILL_INTEGRATION限實際enabled worker／review／explicit enable；disabled candidate可先接。批准者與候選程式權限分離。
- Implementation Scope: request→existing tool search→spec→candidate→static→sandbox→review→approval→registry；先一個唯讀本機用途。禁止下載即執行／自授權。
- Acceptance Criteria: 已有tool不重造skill；package與批准digest一致；未批准永不enabled；取消／撤銷有效；來源／測試／trust level可見。
- Tests: 既有能力命中、不明來源/篡改/缺依賴、負向權限、重複註冊、撤銷、worker cancel；catalog/registry相容回歸。
- Risks: candidate及網頁內容注入；不將test PASS等同review批准。
- Rollback: 停用新增capability註冊與該版本；保留原工具、approval audit和使用者資料。
- Status: PARTIAL（2026-10-10，D44）；fixed Markdown checklist typed candidate／真RI-003 verification／待審UI與手動匯出切片VERIFIED：88新cases、完整1,127PASS、真Chrome23checks與exact6source回退。零registry install/enable／model生成；實際enabled worker的OS／permissions與security review/explicit enable／撤銷仍BLOCKED_BY_SKILL_INTEGRATION，不用patch profile代替。[證據](../evidence/RI-004-2026-10-10/REPORT.md)。

### RI-005

- Task ID: RI-005
- Title: 可辨識啟動版本與保留最新資料的人工發布回退
- Current State: Partially Implemented（D52 complete-signed source選版、actual loaded identity及same-schema ready已VERIFIED；full adoption/handoff未完成）
- Objective: 區分active pointer、真正執行版本與資料恢復；不因code rollback覆蓋後來的對話／記憶。
- Affected Modules: 既有ReleaseManager、operations／companion launcher；不重做update framework。
- Dependencies: FIX-009/013/014/015與D52sourceidentity/同schemaready局部VERIFIED；T34產品readiness；BLOCKED_BY_RELEASE_INTEGRATION：人工maintenance窗口／firstadoption舊writer／immutable exact package驗簽到import／維護到runtime交接與獨立migration政策。
- Implementation Scope: 先設計code rollback保持live data的測試；單一stopped-writer gate；驗launcher實際consume版本／last-known-good readiness。schema不兼容就拒自動回退；資料還原為獨立明確操作。
- Acceptance Criteria: 兩版啟動source identity可讀；新寫入在code rollback後仍在；中斷/migration失敗無雙writer；已完成效果不重播；未批准不deploy。
- Tests: 暫存DB晚寫、WAL/active writer、schema incompat、activation crash、launcher實際版本與health；不使用私人DB。
- Risks: migration與資料生命週期屬RED；沒有證據不可降低gate。
- Rollback: 撤新發布接入／保持舊可信launcher及最新DB；人工復原不能靜默restore舊backup。
- Status: PARTIAL（D48 data retention、D49 restore、D50 namedowner、D51 backup、D52 signedsource/actualversion/same-schema ready均局部VERIFIED）。BLOCKED_BY_RELEASE_INTEGRATION：firstadoption舊／非受管writer、exactimmutablepackage verify/import gap、人工maintenance→runtimehandoff與formaldeployment未驗。[D52證據](../evidence/RI-005-launcher-2026-10-13/REPORT.md)；原D48–D51歷史保持。

### RI-006

- Task ID: RI-006
- Title: 基於可追溯失敗的唯讀改善提案
- Current State: Planned Only
- Objective: 依現有latency/run/tool outcomes提出可驗證最小修復，不在對話中修改Core。
- Affected Modules: 現有AgentRun/journal/metrics、procedural candidates、開發期code graph。
- Dependencies: 可靠去識別觀測、RI-001；FIX-006自身已知／未知辨識；實作與發布分開。
- Implementation Scope: 一個已測失敗類別→evidence→UNKNOWN或已確認root cause→最小proposal＋tests/rollback；只到reviewable patch提案。全鏈沿Analysis→Proposal→Isolated Implementation→Testing→Review→Approval→Deployment→Monitoring→Rollback。
- Acceptance Criteria: 不讀secret／私聊作公開evidence、不因模型推測宣稱根因；無exec/deploy effect；proposal能對照原症狀與驗收。
- Tests: evidence不足／錯誤分類／來源更正撤銷／私密欄位脫敏；原journal與權限回歸。
- Risks: 無可靠觀測即盲目自改；不是再建一個Agent scheduler。
- Rollback: 停用提案producer；刪可丟棄提案view，保留原journal與canonical memory。
- Status: PLANNED；readonly proposal不必等release接線，但任何執行／部署仍受RI-003／005及人工gate。

授權軟體分析目前只保留P3研究入口：先有具體caller與使用者軟體授權，再依API→CLI→docs→MCP→source→GUI→authorized static/decompile選最小切片。不安裝Ghidra/LSP等全套，不聲稱可還原完整原始碼。ESP32/HA繼續沿原T27–29配對、observation／command／readback，真設備條件未到不直接開底層命令。


## 2026-10-08 實作與逐卡驗收

使用者已授權依三份規劃施工。**FIX-003、FIX-004 DONE / VERIFIED**：[003真配置模型與回退](../evidence/FIX-003-2026-10-07/REPORT.md)、[004真UI306.581秒、整體554 PASS／5 real_provider未選與回退](../evidence/FIX-004-2026-10-07/REPORT.md)。provider終止／partial及session lifecycle gates已解除；長文語音仍BLOCKED_BY_FIX：FIX-005，自身故障理解仍FIX-006，搜尋仍FIX-002；桌寵／自主技能各自驗收。FIX-005 A／B已實作並完成671項回歸與最終source回退；原聲線基線功能PASS但速度FAIL，CUDA局部SDPA已量到收益、最後真機功能已PASS（首播30.472→22.446s，仍未達1秒目標），保持PARTIAL，人工語意聽驗NOT_RUN。[005證據](../evidence/FIX-005-2026-10-07/REPORT.md)。C仍需已提交句子契約，不能以B冒充完成。已載入本機candidate，非全產品發布。依既有卡片逐張施工、不重編RT／做排名。

## 2026-10-07 規劃快照：產品方向、對話／語音檢視與修復 gates

使用者追加三件體驗補充已合併：**自由活動桌寵與動作製作、近期對話理解品質、語音生成太慢與長文講不完**。依「檢查近期對話」授權唯讀檢視有界樣本，匿名結果與限制見 [CONVERSATION_VOICE_REVIEW](CONVERSATION_VOICE_REVIEW.md)。未重播私人資料／工具、未生成聲音／動作、未改 production；維持只規劃。

新增 [FIX_REGISTER](FIX_REGISTER.md) 的 FIX-003（終止原因／未完成裁決）、FIX-004（300 秒 session 換證）、FIX-005（分句生成播放／全文／取消）、FIX-006（自身故障 context／合成多輪評估），均 REQUIRED_FIX／PLANNED。根因已確認與未知部分分開，不把 Gateway 401、provider HTTPStatusError、文字 token limit、語音 codec limit 混為一件事。沒有證據指定單一原 RT 引入，保留既有 DONE 與編號。

| 後續產品宣稱／接入 | 狀態與解除條件 |
|---|---|
| 回覆完整性與長文語音完成 | BLOCKED_BY_FIX：FIX-003＋FIX-005；終止裁決、全文尾句、真聲音與取消驗收 |
| 長時間連續互動 | BLOCKED_BY_FIX：FIX-004；真 UI 跨 TTL、喚醒／重啟、無效果重送；語音另需 FIX-005 |
| 自主對話／自身故障可理解品質 promotion | BLOCKED_BY_FIX：FIX-006；自身已知／未知、口語更正合成對照，不能以 mock wiring PASS 代替理解 |
| 桌面素材、場景原型、本機唯讀整理 | 不受上述跨功能全面阻擋；依各自 owner／取消／平台 gate 規劃，不能因此宣告完整桌寵 DONE |

這些是局部產品 gates，不是重新延期 RT-011／013／015，也不重排／重編 roadmap。實作時 A 語音完成判定／版本快取、B final 後有界分句播放、C 已提交 final-answer 句提早生成可分開交付／回退；不只翻 streaming 旗標、不先換聲線、不無界加 output limit。當前無新功能施工授權。

使用者後續澄清：桌寵必須能在螢幕中**自主選擇去處、真正走動、玩耍與休息**，缺少動作由我們規劃生成與製作。COMPANION_EVOLUTION_PLAN 已將桌面場景原型／全身與動作製作／自由活動驗收分開；透明常駐窗、固定停靠或站姿平移不等於此需求 DONE。現有 Haru 的參數／動作 metadata 沒有可驗證的腿部步態，需素材→分層→rig→motion→場景合成的完整交付。此更正仍是 PLANNING_ONLY，不啟動美術生成、改 production 或重編 RT。

使用者本輪明確要求「只規劃」。新增 [COMPANION_EVOLUTION_PLAN](COMPANION_EVOLUTION_PLAN.md)：桌寵薄外殼、明確任務的主動追蹤、既有 catalog／worker 擴充、隔離候選與有界技能成長。這是 PLANNING_ONLY，不是新增 RT 編號、DONE 宣告或自動施工授權；既有 RT-011／013／015 的有界產品交付保留。歷史 LATER 的 skills 接入已有此具體產品切片，不能僅據舊 LATER 一直延期。

新增 [FIX-002](FIX_REGISTER.md#fix-002--保留可判讀的瀏覽器失敗原因並驗證搜尋路徑)，REQUIRED_FIX／MEDIUM／PLANNED：靜態確認 browser failure 情境被縮成 exception 名稱；當次 Bing ScopeViolation 根因 **UNKNOWN — NEEDS INVESTIGATION**。先做合成重現與最小脫敏診斷，不放寬 origin scope，不將畫面 Markdown 當已取得的 raw arguments。

**BLOCKED_BY_FIX：自動網路研究 promotion**，須 FIX-002 與必要行為修復、乾淨公開查詢的端到端驗收一起解除；診斷 tests 通過不等於搜尋可用。桌寵與本機唯讀任務追蹤不受此 gate 阻擋，仍依各自 owner／取消／資源驗收推進規劃。RT-012 DONE 保留，沒有原 acceptance 已失敗的證據，不改為 FAILED_VERIFICATION。

自主程式候選／技能啟用需先驗 OS 保護、完整 artifact hash、獨立 verifier／activator；Core 發布另外驗真啟動版本與保留最新資料的回退。不因 helper 已存在就視為這些產品 gates 已完成。下方各日期紀錄保留原時點與編號，不做排名。

## 2026-10-06 最新交付狀態（取代下方歷史 DEFER）

使用者明確要求三項全部實作。RT-013、RT-015、RT-011 summary 的有界產品切片現為 **DONE**，不改原編號。入口：[PRODUCT_QUICKSTART.md](PRODUCT_QUICKSTART.md)；[驗證證據](../evidence/runtime-product-2026-10-06/REPORT.md)。下方各日期的延期／舊阻擋說明保留為歷史，不能當成目前狀態。

RT-013 已有 workspace UI 與模型 caller，實際 Rust 執行／授權／scope 測試成立；RT-015 已接單一 lifespan owner 的本機記憶歸組 view，前景取消、source revision invalidation 與有界清理完成；RT-011 summary 採本機摘錄，保留 user/system/pending，最終仍經 budget gate。沒有導入自主事實寫入、語意 consolidation 或新 provider profile。AR-06/07 的先前局部修復保留，whole-repo 格式／lint 入口另排除歷史證據和本機資產，未跳過產品 tests。


2026-10-04：FIX-001、RT-003-FIX-01、RT-005-FIX-01 均已逐張完成修復與驗證（完整證據見 FIX_REGISTER 與各 FIX report）。初始 triage 的 RT-003 PARTIAL／RT-009–015 FIX blockers 保留為歷史；RT-003 現恢復 DONE / VERIFIED，所有已確認 FIX gates 解除。RT-009及RT-010於2026-10-05逐輪完成；RT-012於2026-10-05完成DONE；RT-011 budget現DONE（byte/native GPT-OSS gate完成；summary仍DEFER）；RT-011 summary、RT-013/015 保持 DEFER，RT-014 原依賴 RT-010 已完成，2026-10-05本輪RT-014完成DONE。2026-10-04未開始後續RT；2026-10-05先完成RT-009及其修復；後續本輪只完成RT-010。原完成日期／RT 編號／原 T00–T40 歷史全部保留。LATER 維持真設備、多節點、sudo broker、主動人格長期驗證與 skills 動態安裝。

各卡禁止無關 rename/move/rewrite。實際施工前重查路徑和 signature；新增路徑是設計候選，不能視為已存在。每卡共用 regression：原文字/工具/取消 fixtures、ruff/mypy；schema變更加upgrade/rollback；body/audio相關加真機回歸。既有 private runtime data 不做破壞性測試。

## 2026-10-06 延期項規劃更新

RT-013、RT-015 與 RT-011 summary 仍為 **DEFER**。各自的 evidence slice、最小接入、解除條件、驗收與 rollback 見 [DEFERRED_TASK_PLAN.md](DEFERRED_TASK_PLAN.md)。沒有新增 RT 編號或授權自動施工。

RT-015 的 RT-008/014 依賴均已完成；目前 gate 是 retention／single-owner／foreground 優先，不能再以等待 RT-014 說明延期。RT-013 需具體 scoped-read caller 與實證收益。RT-011 summary 需先證明需求，不因 budget DONE 解凍。

10-04 三項 FIX 已完成屬歷史；10-06 review 新增 AR-06（native × multi-call）與 AR-07（clean CI 資產）已於本輪修復其局部根因，見文末 repair follow-up。全樹 check 仍有既有 lint/format 失敗，遠端 CI 未驗；不能宣稱整體 rollout gate 通過。詳 [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) 與修復報告。

## RT-001 基線與 migration invariant

- Status：DONE（2026-10-01）；證據 `docs/evidence/RT-001/README.md`
- Objective / Target behavior：測試驗證真正 schema invariant，main 組裝可在隔離目錄驗證。
- Problem / Audit evidence：F11；REGRESSION_BASELINE，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：測試期待 10，DB 有 12；create_app 測試不等於 main。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：tests/integration/test_sqlite_store.py；tests/integration/test_gateway.py；tests/integration/test_integrated_companion.py。
- Files/subsystems that MUST NOT change：production 全部檔案；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：核對 001–012 表/索引與升級順序；補 empty/upgrade/reopen cases；隔離 env 啟動 main smoke。
- Tests：空 DB/10→12/重跑；無 key offline main startup/shutdown。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：已知 migration failure 消失且表/索引 assertions 保留；真服務 skip 不算 pass。
- Rollback strategy：回退本卡測試；不改 migration 或 runtime。
- Risk level：MEDIUM。
- Dependencies：無。

## RT-002 原生工具訊息接入

- Status：DONE（2026-10-01）
- Objective / Target behavior：完整 assistant/tool pairing 送 provider，既有 prompt caller 相容。
- Problem / Audit evidence：F01，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：ModelMessage/serializer 已有，ConversationEngine 只傳 prompt。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/core/conversation.py；src/siro/core/companion.py；src/siro/services/presentation/integrated.py；src/siro/ports/models.py；src/siro/adapters/models。
- Files/subsystems that MUST NOT change：memory/identity schema、body/audio；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：先捕捉現有 context；加 optional messages passthrough；固定每 run 原始目標；保留舊 prompt path。
- Tests：capture provider payload；多輪 pair/角色；prompt fallback。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：每個 tool result call_id 配對、tool output 不當 user；舊 text fixture 一致。
- Rollback strategy：只對新 run 關 candidate messages；進行中 drain。
- Risk level：HIGH。
- Dependencies：RT-001。

- Completion files：core/conversation.py、core/companion.py、presentation/integrated.py、presentation/gateway.py、test_integrated_companion.py；契約/決策/STATUS 與 docs/evidence/RT-002/README.md。
- Completion tests：全套199 passed/5 skipped；最後相關5 passed；ruff/mypy通過。
- Known limitations：candidate opt-in、history僅RAM；batch RT-003與restart RT-008尚未做。

## RT-003 工具 batch 與終止狀態

- Status：DONE / VERIFIED（2026-10-04；RT-003-FIX-01 通過；原 PARTIAL 為歷史）
- 修復 gate：RT-003-FIX-01 已解除。跨 run call-ID 反例不符合 run-scoped 去重；batch barrier 已完成成果保留，詳 FIX_REGISTER.md。
- Objective / Target behavior：當批全 terminal 才繼續，一個 run 只有一次 final。
- Problem / Audit evidence：F02，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：每個 tool 完成後遞迴 continuation。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/services/presentation/integrated.py；src/siro/services/tools/orchestrator.py。
- Files/subsystems that MUST NOT change：provider transports、角色算法；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：建立 batch tracking；循序 dispatch；denied/failed 也產 observation；預算與 final 去重。
- Tests：兩工具 mixed results、重复 ID、step limit、cancel race 100 次。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：零漏配/重複執行；一個 assistant batch 一次 continuation。
- Rollback strategy：新 run 用 legacy；已開始 batch 收尾或 unknown，不重播。
- Risk level：HIGH。
- Dependencies：RT-002。

- Completion files：presentation/integrated.py、tools/orchestrator.py、presentation/gateway.py、test_agent_batches.py；DECISIONS/CONTRACTS/STATUS及evidence RT-003。
- Tests passed：相關38 passed；全套206 passed/5 skipped；ruff/mypy/format通過。
- Known limitations：candidate僅RAM；running程序停止RT-005、recovery RT-008；HTTP false為必要相容擴充。完整證據 `docs/evidence/RT-003/README.md`。

## RT-004 有界程序執行 facade

- Status：DONE（2026-10-01）
- Objective / Target behavior：既有 computer.execute 可透過同介面有界 drain，觀測格式相容。
- Problem / Audit evidence：F10；F06，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：Gateway closure communicate 完才截斷。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/services/presentation/gateway.py execute_computer；src/siro/services/tools/execution.py（新增候選）。
- Files/subsystems that MUST NOT change：Rust RPC、授權 defaults、browser；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：封裝 argv backend，不改能力集合；stdout/stderr bounded drain；保存 returncode/truncated。
- Tests：100MiB 合成輸出、兩 pipe 同時 flood、exit nonzero。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：保存 cap≤64KiB（或配置值）；額外 RSS 目標<32MiB，無 deadlock。
- Rollback strategy：executor binding 回舊 handler；不接續正在跑的 job。
- Risk level：MEDIUM。
- Dependencies：RT-001。

- Completion files：tools/execution.py、presentation/gateway.py、test_bounded_execution.py；DECISIONS/CONTRACTS/STATUS與evidence RT-004。
- Tests passed：相關41 passed；全套213 passed/5 skipped；ruff/mypy/format通過。100MiB retained64KiB、RSS delta400KiB，本機採樣證據。
- Known limitations：candidate共享raw cap（legacy各管道cap）；process tree/run取消RT-005；RSS為合成fixture採樣。證據 `docs/evidence/RT-004/README.md`。
- Verification repair（2026-10-01）：修正dispatch重讀profile，Gateway controller/executor共用startup binding；兩profile中途env變動、直接child reap及batch兩種終止順序驗證通過。DONE保留；修後檔案/測試/限制見 `docs/evidence/RT-004/profile-freeze-fix/README.md`。

## RT-005 run cancellation 傳到程序

- Status：DONE（2026-10-01；獨立驗證缺口修補後fixtures通過）
- 2026-10-04 repair follow-up：RT-005-FIX-01 已 DONE；保留原 owned argv acceptance，candidate arguments-only 受控 lifecycle／真本機 browser cleanup 通過，任意 GUI/escaped effects 仍不得宣稱已全回收。
- Objective / Target behavior：取消停止新 dispatch 並清理 owned foreground process group。
- Problem / Audit evidence：F03，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：LLM/body cancel 沒有 process handle。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/services/tools/execution.py；src/siro/services/tools/orchestrator.py；src/siro/services/presentation/integrated.py。
- Files/subsystems that MUST NOT change：其他 session/使用者程序、Rust grants；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：ExecutionContext 傳 token/deadline/epoch；owned group TERM/KILL/reap；late output fence；記錄 detach lifetime。
- Tests：父子程序 cancel、timeout、完成同時取消、其他程序存活。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：受控 child 2秒停止；cleanup失敗5秒內明報；100 races 零 late UI。
- Rollback strategy：關 candidate executor；先清理所屬 child，不使用廣泛 pkill。
- Risk level：HIGH。
- Dependencies：RT-003、RT-004。

- Completion date：2026-10-01。
- Completion files：tools/execution.py、tools/orchestrator.py、presentation/integrated.py、presentation/gateway.py（必要caller）；新增test_execution_lifecycle.py；DECISIONS/CONTRACTS/STATUS與evidence RT-005。
- Tests passed：相關74 passed；全套229 passed/5 skipped；最後task-specific14 passed；ruff/mypy（168files）/format通過。三次group取消約0.252s、cleanup失敗5秒內明報、100合成交錯零late UI。
- Known limitations：context僅RAM；停止owned同PGID foreground，escaped daemon不保證；ack detach保留使用者管理、未接session teardown；真provider/GPU/GUI未驗；完整證據 `docs/evidence/RT-005/README.md`。

- Verification repair date：2026-10-01。先重現18筆late工具事件，再補candidate固定stream_id、writer/consumer terminal fence；歷史FAILED_VERIFICATION報告保留。
- Repair files：presentation/gateway.py、integrated.py、static/index.html；test_gateway_terminal_fence.py、test_agent_batches.py；DECISIONS D16、STATUS與delivery-fence-fix evidence。
- Repair tests passed：原獨立反例1 passed；writer/consumer/batch專項15 passed；最終全套237 passed/5 skipped；ruff/mypy169files/format及scope patch reverse dry check PASS。
- Repair known limitations：歷史entered timeout精確原因NOT VERIFIED，已分離初始化與2秒取消門檻、補task異常診斷；真provider/GUI/GPU/active shutdown/deployment rollback仍未驗。證據 `docs/evidence/RT-005/delivery-fence-fix/README.md`。

## RT-006 Qwen worker 生命周期

- Status：DONE（2026-10-02；前端修補及owner人工驗收確認）
- Objective / Target behavior：request 配對、失敗隔離、Gateway 關閉確實回收。
- Problem / Audit evidence：F05，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：原始稽核基線為無close/response id、timeout後舊pipe可重用；現有candidate生命周期與前端abort已接入，2026-10-02收到owner人工相容性確認。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/services/audio/tts.py；scripts/qwen_tts_worker.py；src/siro/services/presentation/gateway.py lifespan。
- Files/subsystems that MUST NOT change：reference WAV、模型、Live2D、對話算法；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：加入 request_id/epoch；finally 清理 startup fail；close terminate/wait；取消後重建；bounded queue。
- Tests：fake worker 延遲/亂序/EOF/timeout；真 GPU render/cancel/restart。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：無錯配、無 owned 殘留、單 GPU worker；v1 reference 音色與WAV相容。
- Rollback strategy：drain並關閉新worker，還原 adapter；不保留新舊worker同跑。
- Risk level：HIGH。
- Dependencies：RT-001。

- Completion date：2026-10-02（原實作2026-10-01，人工gate完成2026-10-02）。
- Files changed：audio/tts.py、scripts/qwen_tts_worker.py、presentation/gateway.py；test_qwen_lifecycle.py；DECISIONS D17/CONTRACTS/STATUS/evidence。
- Tests passed：task-specific14 passed；相關46 passed；最終全套251 passed/5 skipped；ruff/mypy170files/format與scope reverse check PASS。真RTX3050冷啟動/重複render/cancel/restart/close通過，取消約0.277s，old/final reaped；WAV PCM16/24kHz，reference SHA不變。
- Known limitations：candidate新增生命周期；legacy故障路徑保留；單adapter owner非跨Gateway global broker；長時間soak/部署rollback未驗；人工聲線/取消/角色由owner確認，GUI有修後觀察證據，cleanup failure明報且不重用。完整證據 `docs/evidence/RT-006/README.md`。

- Independent verification correction：原前端取消fetch聲明不成立、人工音色/畫面gate未驗，DONE撤回為PARTIAL。修後補index.html每speech abort/generation/player取消、test_frontend_speech_cancel.py；專項25 passed、全套257 passed/5 skipped、ruff/mypy171files PASS；真GUI生成中/播放中取消與Cubism顯示觀察通過；owner人工聽感/畫面仍待回報，不自動升DONE。證據 `docs/evidence/RT-006/frontend-cancel-fix/README.md`。

- Acceptance follow-up（2026-10-02）：自動排序仍選RT-006，依賴RT-001滿足；現有相關25 passed、ruff/mypy171files PASS、驗收服務alive。未新增production code；owner聲線/聽覺停止/畫面回覆尚缺，保留PARTIAL。證據 `docs/evidence/RT-006/acceptance-followup-2026-10-02/REPORT.md`。

- Owner acceptance（2026-10-02）：針對聲線、聽覺取消與角色畫面驗收問題，owner回覆「可以」，人工gate記PASS，DONE恢復；未新增測量或重新跑測試，未開始RT-007。證據 `docs/evidence/RT-006/acceptance-followup-2026-10-02/OWNER_ACCEPTANCE.md`。

## RT-007 工具 catalog 與有效配置

- Status：DONE
- Objective / Target behavior：一個 descriptor 驅動 schema/handler/readiness；可查實際 profile。
- Problem / Audit evidence：F06；tool availability matrix，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：candidate descriptor 驅動 schema/handler/readiness，逐回合快照與 dispatch 再查；legacy 靜態相容。JSON settings 未載入，effective config 如實報 env/defaults。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/services/tools/orchestrator.py；src/siro/services/presentation/integrated.py _AGENT_TOOLS；src/siro/services/presentation/gateway.py composition。
- Files/subsystems that MUST NOT change：SiroSettings 原欄位語義、Rust protocol、skills install；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：包現有 descriptors；readiness 快照與 dispatch 再查；去密鑰 effective config；保留 env 優先。
- Tests：tool disabled/unavailable/錯 schema；full mode；legacy env parity。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：模型 catalog 中所有可用工具可路由；工具關閉後不 dispatch；不泄漏 key。
- Rollback strategy：回靜態 catalog/profile；保留原 env 行為。
- Risk level：MEDIUM。
- Dependencies：RT-003、RT-004。

- Completion date：2026-10-02。
- Files changed：orchestrator.py、presentation/integrated.py、presentation/gateway.py、tests/integration/test_tool_catalog.py；DECISIONS D19、CONTRACTS、STATUS、本 roadmap 與 docs/evidence/RT-007。
- Tests passed：最終專項16 passed；相關73 passed；最終全套273 passed/5 opt-in provider skipped；ruff PASS、mypy172files PASS；真Gateway network startup/diagnostic/tools-off smoke PASS；scope reverse-patch check PASS。
- Acceptance：兩個模型可見工具經真main/Core/SQLite/ASGI路由及配對observation PASS（model/browser合成，computer真子程序）；取消readiness/工具關閉不得dispatch PASS；診斷授權/secret canary PASS。
- Known limitations / discrepancy：JSON/env未合併，診斷json_settings_applied=false；browser readiness只驗現有executable discovery；validator限現有schema subset；舊port8000服務未重啟；真provider/GUI/GPU/soak與部署rollback未驗。精確patch、logs、逐項gate與回復方式見 docs/evidence/RT-007/README.md；未開始RT-008。

## RT-008 durable journal 與恢復

- Status：DONE
- 2026-10-04 review follow-up：DONE 限 local journal/readback；精確 proposal ownership 修補與回歸併 RT-003-FIX-01，不另建重複 journal 修復卡。
- Objective / Target behavior：重啟能重建已完成 context；不明副作用標 unknown。
- Problem / Audit evidence：F04，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：candidate atomic run/journal、canonical checkpoints/batch/dispatch/observation及持久round/tool budget已接入；startup只讀回並封鎖舊提案，unknown可見，無自動重播。legacy rows仍unrestorable。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/services/agent/runs.py；src/siro/services/presentation/integrated.py；src/siro/persistence/migrations/下一號 additive SQL。
- Files/subsystems that MUST NOT change：既有 migration、既有 enum values、identity資料；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：版本 journal/batch/dispatch intent；transaction checkpoint；startup reconciliation；readback only；持久 budget。
- Tests：四個 crash points、reopen、duplicate callback、舊 schema、side effect fixture。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：零盲目重送；unknown 可見；所有 tool pairs與預算可恢復。
- Rollback strategy：關 recovery feature 保留新 reader/schema；備份回復須保存新增資料，禁止自動降版 DB。
- Risk level：HIGH。
- Dependencies：RT-003、RT-005、RT-007。

- Completion date：2026-10-03。
- Files changed：agent/runs.py、migration013、presentation/integrated.py、tools/orchestrator.py；必要caller core/companion.py optional callback、Gateway startup/readback、index.html notice；test_run_journal.py、crash fixture、operational_cli隔離data；D20/CONTRACTS/STATUS/evidence。
- Tests passed：最終全套285 passed/5 opt-in provider skipped；RT-008專項12加launcher反例1共13 passed；相關92 passed；ruff/mypy174files/format PASS；真installed Gateway network startup recovery/readback/unchanged side-effect PASS；scope reverse patch check PASS。
- Acceptance：四個真process abrupt crash零盲目重送 PASS；unknown HTTP/UI函式可見 PASS；partial batch/完整tool pairing及round/tool預算reopen可恢復 PASS；schema0/10/12→13/idempotent/old loader相容 PASS。
- Known limitations / discrepancy：恢復只做local journal readback，非OS結果查證或自動續跑；single Gateway owner，power loss/真provider/GUI/GPU/soak/部署rollback未驗。必要caller檔案超原expected清單已記D20。舊operational測試誤用default DB先套初版013，後draft SQL變動導致checksum拒啟；已恢復最初013、唯讀驗完整性，未改DB checksum/刪資料，測試改隔離data；default DB的additive013保留。完整歷史fail/final pass及限制見 docs/evidence/RT-008/README.md。未做RT-009。

## RT-009 provider bounded retry/fallback

- Status：DONE
- Blocking fixes：NONE（FIX-001 已驗證 DONE；2026-10-05已完成RT-009）。保留 RT-007/008 與 retry/fallback 原驗收。
- Objective / Target behavior：符合隱私/費用且尚無 text/tool 意圖時才能有限重試。
- Problem / Audit evidence：F07，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：candidate main 包現有選中provider，單一policy最多兩attempt；text/tool/finished及緩衝tool片段均fence；legacy/env priority保持，未設budget不得增加cloud requests。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/adapters/models/failover.py；src/siro/services/presentation/gateway.py provider composition。
- Files/subsystems that MUST NOT change：provider public port、模型權重；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：定義可重試錯誤/最多2次attempt含首試；取消中斷backoff；固定budget；stream/tool emission fence。
- Tests：429/timeout/partial text/tool request failure；local_only；cancel backoff。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：最多2attempt；emission後零 fallback；無未設定cloud外送。
- Rollback strategy：關 retry/fallback 使用原單provider。
- Risk level：MEDIUM。
- Dependencies：RT-007、RT-008。

- Completion date：2026-10-05。
- Files changed：adapters/models/failover.py、presentation/gateway.py；必要scope addition openai_compatible.py（buffered tool fragment error note，原error type不變）；test_failover_policy.py、test_provider_retry.py；D24/CONTRACTS/STATUS/evidence。
- Tests passed：專項32 passed；相關153 passed；最終全套376 passed/5 opt-in provider skipped；ruff/mypy176files/format PASS；真local HTTP429/retry與SSE fragment EOF fence PASS；scope reverse patch check PASS。
- Acceptance：≤2 total attempts PASS；emission後零fallback、failed initial/continuation intent零新effect PASS；local_only/unconfigured cloud零額外外送 PASS；原selected cloud一次request保留，不額外重試。主路徑main/Core/SQLite/ASGI＋真computer subprocess閉環通過（models合成）。
- Known limitations：main未有monetary budget故額外cloud request budget固定0；direct caller explicit request-count budget不是USD/day accounting。不新增cloud fallback路由，local只retry原provider；fixedbackoff不讀Retry-After；真provider/GUI/GPU/soak/部署rollback未驗，port8000未重啟。精確patch/logs/逐項gate/回復見 docs/evidence/RT-009/REPORT.md。未開始RT-010。

- Verification repair（2026-10-05）：獨立真main/SQLite regression已重現，修復前 FAILED_VERIFICATION；現 wrapper startup固定 selected provider.name，live API/raw SQLite/fresh-store readback local/cloud retry on/off全部PASS。修正檔案 failover.py、test_provider_retry.py、test_failover_policy.py；D25/STATUS/evidence。專項含原獨立案例35PASS；全套378PASS/5 opt-in skip/3dependency warnings；ruff/mypy176files、scoped reverse patch dry check、diff whitespace PASS；三項原acceptance仍PASS。歷史failover rows不猜測改寫，provider metadata是selected-primary而非逐attempt trace；真provider/GUI/soak/部署rollback仍NOT VERIFIED。詳 docs/evidence/RT-009/provider-metadata-fix/REPORT.md。只修本卡，未開始RT-010。

## RT-010 session context 恢復

- Status：DONE
- Blocking fixes：NONE（RT-003-FIX-01 DONE）。重用 RT-008 canonical journal；取消重建 run journal/reconciliation 的重複子工作，保留 session hydration 目標。
- Objective / Target behavior：新session journal可還原對話；legacy紀錄不誤解析。
- Problem / Audit evidence：F08，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：candidate從RT-008 completed canonical journal取同session/同privacy近期user與final assistant native pairs，最多12則；新system context重建，legacy/env feature-off保留舊working path。舊 messages 不作raw解析。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/core/companion.py；src/siro/core/memory.py；src/siro/persistence/conversation.py；src/siro/services/agent/runs.py。
- Files/subsystems that MUST NOT change：long-term memory facts、identity；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：restore canonical messages；session隔離；legacy標記；上限保留。
- Tests：三次重啟、session A/B、legacy assembled prompt。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：新session重啟仍保留目標/近期對話；零跨session混入。
- Rollback strategy：停restore，保留DB；舊working path繼續。
- Risk level：MEDIUM。
- Dependencies：RT-008。

- Completion date：2026-10-05。
- Files changed：core/companion.py、services/agent/runs.py、presentation/integrated.py、presentation/gateway.py；test_session_restore.py、test_integrated_companion.py；D26/CONTRACTS/STATUS/evidence。
- Discrepancy / scope：必要Integrated/Gateway runtime caller wiring超原expected清單；重用原journal/reconcile，無第二owner或schema變更。原RT-002測試新run不含舊對話的假設與本卡衝突，保留restore-off原斷言並加restore-on及無歷史tool intent/result。
- Tests passed：專項/相關15PASS（新卡9cases）；最終全套388PASS/5 opt-in provider/speech skip/3dependency warnings，89.73s；ruff/mypy177files/6files format/scoped reverse patch dry check/whitespace PASS。前版temp source重現第二次startup缺對話1FAIL；首輪full386PASS/1FAIL為舊candidate fixture假設，歷史log保留。
- Acceptance：三次main重啟保留raw goal/近期native user-assistant dialogue PASS；A/B零混入 PASS；12則完整pair上限/legacy_unrestorable/privacy隔離/未知動作不hydrate與tool零重播 PASS。實際main/Core/SQLite/ASGI、實際Python subprocess；models/transport合成。
- Known limitations：只hydrate completed dialogue，不含完整工具transcript、failed/cancelled/interrupted或direct command history；這些既有readback/流程保留。最多12messages不等於token budget，RT-011/014未做；同privacy篩選不把local_only舊資料送cloud；retention/single-owner仍既有限制。真provider/GUI/GPU/power loss/soak/部署rollback NOT VERIFIED，私人DB/8000未改或重啟。SIRO_SESSION_RESTORE_ENABLED=0為下次drained startup回滾；DB保留。證據 docs/evidence/RT-010/REPORT.md。本輪只完成RT-010並停止。

## RT-011 context budget 與可撤銷摘要

- Status：DONE（budget 2026-10-05；extractive summary 2026-10-06，D31 有界產品切片）
- Blocking fixes：NONE（歷史 FIX 與 AR-06/07 已修）；budget／summary 原分開驗收。summary 現完成，採 source-hashed extractive view、24-pair restore、mutation cutoff，不新增 RT 編號或永久摘要儲存。
- Objective / Target behavior：長度有界，保留pending tool pair與來源。
- Problem / Audit evidence：context compression matrix；F08，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：candidate main外層ContextBudgetModel在provider/retry前套獨立byte及native guard；Groq openai/gpt-oss-20b使用同adapter payload、pinned官方tokenizer/template，input+output reserve+256需在131072 startup window內。未知profile/缺資產明報Unavailable，超限Exceeded，不刪改goal/system/pairs/journal。legacy保留舊路徑；byte0不關native。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/core/memory.py context assembly；src/siro/services/agent/context.py（新增候選）。
- Files/subsystems that MUST NOT change：affect算法、long-term memory schema；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：先量測token；設定provider limit；摘要已完成區段；provenance/hash失效；summary失敗明報。
- Tests：巨大tool output、pending pair、summary timeout、source correction。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：不送超限request；目標/授權/pending完整；摘要不寫入人格facts。
- Rollback strategy：關摘要用有界錯誤/舊recent模式；不删除journal。
- Risk level：MEDIUM。
- Dependencies：RT-002、RT-010。

- Implementation date：2026-10-05；Completion date：2026-10-05（budget切片；下列原PARTIAL紀錄保留歷史，完成補記優先）。
- Files changed：services/agent/context.py新增；presentation/gateway.py必要caller組裝（超原expected清單，D27記錄）；test_context_budget.py新增；D27/CONTRACTS/STATUS/evidence。
- Tests passed：專項8PASS；最終全套396PASS/5 opt-in skipped/3 dependency warnings（85.84s）；ruff/mypy179files/3files format/scoped reverse patch dry check/whitespace PASS。temp pre-task main在同64-byte案例仍呼叫provider且COMPLETED，修後零provider與FAILED；保留before.log。
- Acceptance：logical byte cap前不送超限request PASS；provider-native tokens/window不送超限 NOT VERIFIED，因此此criterion及整卡PARTIAL。raw goal/system授權來源/pending pair完整 PASS；巨大tool result不再呼叫provider、完整SQLite readback與一次tool effect PASS；summary不寫人格facts PASS（本切片未實作summary）。models/executor合成，main/Core/SQLite/ASGI真路徑。
- Discrepancy / required remainder：目前無provider tokenizer/context-window metadata，bytes不能等同tokens或真HTTP framing；需綁已驗證selected model tokenizer、context window/input+output reserve並驗真token邊界，完成後才評DONE。summary依既有SPLIT仍DEFER，不提前實作。
- Known limitations / rollback：byte metric包含完整logical request，非exact provider payload/token/費用/peak RSS；不刪history或摘要，超限明報；JSON/asdict量測仍有temporary allocations，retention unchanged。candidate下次drained startup設SIRO_CONTEXT_MAX_BYTES=0回舊path，保留DB，無schema rollback；只dry check未部署演練。真provider/GUI/GPU/power loss/soak/部署rollback NOT VERIFIED；私人DB與8000服務未動。完整證據 docs/evidence/RT-011/REPORT.md。本輪停止，不開RT-012。


- Native completion follow-up（2026-10-05）：D28綁selected Groq GPT-OSS20b官方immutable assets/hash及window；同request_payload量測/發送、thread counting/cancel fence、input+requested output+256 policy；unknown/missing/tampered/unsupported shape fail closed。原provider-token remainder已補完，summary仍DEFER。
- Completion files：context.py、native_context.py、gpt_oss_profile.json、openai_compatible.py、gateway.py、setup_context_tokenizer.py、pyproject/uv.lock/.gitignore、native tests及六個synthetic fixture設定；roadmap/CONTRACTS/D28/STATUS/evidence。精確16source/config/test paths/hash見token-completion/digests.json。
- Completion tests：task23PASS；executor34PASS；full411PASS/5 opt-in SKIP/3 dependency warnings（114.70s）；ruff/mypy181files/format PASS；官方HF四種reference一致；兩組真Groq合成probe reference/server79/83、176/170，256餘量覆蓋；wheel資源與source reverse dry check PASS。
- Completion acceptance：configured byte/native reference budget gate PASS；goal/authorization/pending pair完整PASS；summary不寫facts PASS（DEFER未實作）。不是Groq內部framing完全相同的保證；僅支援已驗profile，其他shape明報。
- Completion limitations / rollback：GUI/GPU/power loss/soak/deployed rollback NOT VERIFIED；私人DB/8000未動。fresh checkout需先setup public tokenizer；native0只關native，另byte0才回pre-budget path，下次drained startup生效；journal保留無migration。精確scoped rollback及所有初次失敗紀錄保留於 docs/evidence/RT-011/token-completion/REPORT.md。只完成本卡budget，不開RT-012。

## RT-012 持續 browser session

- Status：DONE（2026-10-05）
- Blocking fixes：NONE（兩張 FIX 均 DONE）；先驗 arguments-only cleanup 及跨 run ownership，再擴持續 browser session。
- Objective / Target behavior：同session可navigate/read/fill/click/readback且可清理。
- Problem / Audit evidence：F09，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：candidate session-owned BrowserSessions wrapper已接main/catalog/contextual executor；同origin跨run保留狀態、read/fill/click/close接既有driver；epoch+DOM screen fence，TTL/cancel/shutdown cleanup；legacy及feature0保留stateless。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/adapters/browser.py wrappers；src/siro/services/presentation/gateway.py browser composition；tool catalog。
- Files/subsystems that MUST NOT change：OS desktop全面控制、登入憑證保存；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：session-owned driver；暴露現有動作；screen-version fence；TTL/close；不改driver核心。
- Tests：本機合成跨頁表單、A/B隔離、stale screen、cancel/close。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：跨步狀態保留；操作後readback；過期目標拒絕。
- Rollback strategy：停止接新browser jobs並close，再回stateless navigate。
- Risk level：MEDIUM。
- Dependencies：RT-005、RT-007。

- Completion date：2026-10-05。
- Files changed：新增services/tools/browser_session.py；gateway.py必要caller/lifespan；orchestrator.py candidate工具schema及enum驗證；新增test_browser_sessions.py、更新test_tool_catalog.py inventory（原route/pair/kill-switch斷言保留）；D29/CONTRACTS/STATUS/evidence。
- Tests passed：專項/相鄰33PASS；full419PASS/5 opt-in SKIP/3 dependency warnings（127.82s）；ruff/mypy183files/5files format/source digest/scoped reverse dry check/whitespace PASS。temp before-source actual main缺工具無成功observations反例FAIL；所有初次diagnostics/31PASS2FAIL inventory紀錄保留。
- Acceptance：真headless Chromium跨頁fill→next→save、跨run保持state PASS；actual main/Core/catalog/SQLite/model consumer操作後readback PASS；DOM改變/cross-session/recreated driver/TTL過期拒絕PASS。A/B隔離、capacity、task/token/repeated cancel、active close/shutdown、deadline/cleanup failure明報與legacy/feature0 stateless rollback fixtures PASS。
- Discrepancy / scope：原adapter wrapper候選改為service wrapper、不改driver核心；新增shutdown optional callback及四個candidate schema為必要接線，D29記錄。RT-014歷史BLOCKED仍指已完成RT-010，selection.json記錄，本輪未變該卡。
- Known limitations：每Gateway8個ephemeral session、idleTTL300s、action30s；shared WS沒有conversation owner mapping，斷線由TTL清理；切origin重建scope/state、任意error關受影響session；不保存登入憑證，不宣稱跨restart browser恢復或undo外部effects。L2真Chromium/local form＋合成model/body，不等同public-site login或owner GUI驗收。
- Rollback：下次drained startup SIRO_BROWSER_SESSION_ENABLED=0，關新工具並回stateless navigate；先shutdown清owned browsers，無DB/schema回退。isolated main feature-off/legacy兩call兩driver回收及source reverse dry check PASS；私人部署未切換。docs/evidence/RT-012/REPORT.md完整logs/selection/snapshots/digests/patch。只完成本卡並停止，未開始下一RT。

## RT-013 Rust read-only execution backend 對接

- Status：DONE（2026-10-06；workspace read/list，D31）
- Blocking fixes：NONE。Caller：控制頁的明確 owner 讀取、模型 filesystem.read/list；專用 workspace、signed grant 與真 Rust 執行已接入。一般 computer.execute 權限另計，不宣稱全電腦 sandbox。
- Objective / Target behavior：facade可選既有Rust只讀能力；同份result/permission語義。
- Problem / Audit evidence：F06；IPC matrix，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：WorkspaceRuntime 已由 main 擁有，模型 read/list 與 owner UI 使用同一 signed scoped Rust service。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Actual files/modules affected：src/siro/services/tools/workspace.py；Gateway composition／owner readback；控制頁與實際 Rust integration tests。既有 LocalRuntimeClient／Rust wire 保持。
- Files/subsystems that MUST NOT change：Rust wire/schema、sudo、write/install actions；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：能力逐項map；先health/scoped read/list；保持grant；不支援能力明報；不自動降級較弱backend。
- Tests：Rust離線、invalid grant、path escape、Python/Rust只讀parity。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：已暴露能力有backend证據；Rust離線文字照常；無失敗後偷轉無scope執行。
- Rollback strategy：drained restart 設 SIRO_WORKSPACE_ENABLED=0，先關閉 owned Rust process；移除新讀檔入口，不自動轉較弱 backend，原本其他工具保持。
- Risk level：HIGH。
- Dependencies：RT-005、RT-007。

- Completion：services/tools/workspace.py、Gateway composition／authenticated readback、控制頁；Unicode paths、scope escape、approval、kill switch、missing runtime、shutdown、real model-to-tool fixture PASS。無 wire/schema 修改，正常文字路徑不因 binary 缺失停止。完整證據見 runtime-product-2026-10-06/REPORT.md。

## RT-014 有來源的 memory ingress

- Status：DONE（2026-10-05；原RT-010 dependency blocker為落後狀態，已核對DONE）
- Blocking fixes：NONE（identity gate及RT-010 dependency已滿足）；保留來源/identity隔離。
- Objective / Target behavior：明確記憶要求形成來源候選並用既有revision流程。
- Problem / Audit evidence：F08，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：candidate trusted user entry的明確leading記憶要求已接MemoryService.ingest_owner_request與既有source/revision transaction；Core route privacy recall、correct/delete/restart readback接通，legacy/feature0保持舊入口。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Expected files/modules affected：src/siro/core/companion.py；src/siro/core/memory.py；src/siro/services/presentation/integrated.py。
- Files/subsystems that MUST NOT change：immutable persona、relationship計算、資料保存政策；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：source event→candidate；來源/身份驗證；使用既有commit/correct/delete；不寫推測facts。
- Tests：記住/更正/刪除/重啟查詢；惡意tool文字不自動成fact。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：指定合成事件跨重啟可查，更正/刪除生效且保留來源。
- Rollback strategy：停新candidate ingress；保留revision，按既有撤銷接口撤回測試資料。
- Risk level：MEDIUM。
- Dependencies：RT-010。

- Completion date：2026-10-05。
- Files changed：core/memory.py、core/companion.py、persistence/memory.py、presentation/integrated.py、gateway.py；新增test_memory_ingress.py；D30/CONTRACTS/STATUS/evidence。
- Discrepancy：RT-014原BLOCKED依賴RT-010實已DONE，selection.json記錄；RT-013/015仍DEFER不開工。實際memory recall無source privacy gate，必要optional repository/Core route filtering與Gateway startup flag超tentative files；D30記錄，無public API break/schema/state/protocol改變。
- Tests passed：專項/相關memory/session/Core27PASS；全套426PASS/5 opt-in SKIP/3 dependency warnings（152.36s）；ruff/mypy184files/6files format/hash/scoped reverse dry check/whitespace PASS；temp before-source actual main記憶query反例FAIL。初次fixture/native-message assertion/required turn_id/新增cloud參數診斷保留。
- Acceptance：actual main/ASGI/Core/SQLite四lifecycle記住/重啟/更正/刪除/重啟query PASS；來源event/session/revision保留 PASS；fresh session模型消費corrected memory PASS；真argv tool observation不自動成fact PASS；synthetic cloud request無local-only記憶 PASS；寫失敗/空命令FAILED且零provider、legacy/feature0入口 rollback PASS。
- Known limitations：僅explicit leading記住：/請記住：/幫我記住：（或ASCIIcolon）與remember:/please remember:，不做廣義LLM抽取；更正/刪除走既有API。記憶為episodic owner statement非獨立外部truth/persona；維持local_only來源，不自動授cloud讀記憶。刪除影響memory recall，不purge歷史raw conversation；retention unchanged。L1/main真localSQLite/argv＋合成provider/body，release-level真人GUI/長測/私人部署未冒稱通過。
- Rollback：下次drained startup SIRO_MEMORY_INGRESS_ENABLED=0停未來chat寫入，保留既有memory/revisions及safe candidate privacy filter；legacy舊入口。isolated main feature0/legacy已驗，精確6file source reverse dry check PASS；無migration/DB rollback。docs/evidence/RT-014/REPORT.md完整logs/selection/before/digests/patch。只完成本卡並停止，不啟動RT-015。

## RT-015 既有排程的有界接入

- Status：DONE（2026-10-06；本機有來源記憶整理 view，D31）
- Blocking fixes：NONE；RT-008/014 已完成。實際 read-only pump 不建立持久工作／效果重播；coalesced trigger、cap 100、foreground cancellation、single-owner lifecycle 已驗。
- Objective / Target behavior：可配置背景候選，foreground優先，預設不主動打擾。
- Problem / Audit evidence：capability scheduling/goal matrix，見 ARCHITECTURE_FRICTION_MAP、CAPABILITY_MATRIX 與 REGRESSION_BASELINE。
- Current implementation：Gateway lifespan 已啟動單一 MemoryOrganizer；採本機 read-only 歸組 view，不啟用既有 consolidator 的自動 committed 寫入。
- Exact scope：只完成本卡目標；不連帶接入其他 subsystem。
- Actual files/modules affected：services/agent/organization.py、Gateway lifespan／controls、Integrated foreground 狀態、控制頁與 organization/main integration tests。既有 Core consolidation/proactivity 不需修改。
- Files/subsystems that MUST NOT change：ESP32/HA、真設備副作用、core scoring公式；共用 freeze zones 同樣適用。
- Backward compatibility：遵守 COMPATIBILITY_PLAN；保留舊 callers、預設授權、資料與HTTP/WS契約。新行為先 candidate，不更動進行中run版本。
- Implementation steps：注入clock/取消；coalesced trigger／100 source cap；foreground 優先；停機清理；只讀本機候選 view，不產社交訊息，因此不改 quiet/day scoring。
- Tests：fake clock七天、trigger flood、foreground active-read cancel、source revision／delete invalidation、restart rebuild。
- Regression tests：本卡 tests 加既有受影響 integration；舊/新 profile 對照。完整測試只在跨邊界gate或新增風險時擴跑，不把mock當真服務。
- Acceptance criteria / measurable benefit：預設零主動訊息；quiet/busy零違規；無重複候選、無shutdown task殘留。
- Rollback strategy：SIRO_MEMORY_ORGANIZATION_ENABLED=0，drain owned task，保留原 memories/revisions；view 可丟棄重建，無新 durable cursor 或積壓效果需 replay。
- Risk level：MEDIUM。
- Dependencies：RT-008、RT-014。


- Completion：services/agent/organization.py、Gateway lifespan、authenticated controls、原記憶更正／刪除 UI；七天 fake-clock、active-read preemption、洪水合併、source invalidation、restart/flags PASS。整理不寫新 facts，不使用原 consolidator 的自動 committed 路徑；既有 consolidation/revision 資料保持。

## 修復任務（2026-10-04 插入；三張均已完成）

以下三卡的完整 Source/Severity/Problem/Evidence/Expected/Actual/Root Cause/Scope/Files/Compatibility/Repair/Tests/Acceptance/Rollback/Risk 見 [FIX_REGISTER.md](FIX_REGISTER.md)。先選一張依賴滿足的 FIX，保留逐卡證據，不同時擴張後續 RT 功能。

### RT-003-FIX-01 — 跨 run tool identity 與 proposal ownership

- Status：DONE（2026-10-04；docs/evidence/RT-003-FIX-01/REPORT.md）；Classification：REQUIRED_FIX；Severity：HIGH。
- Source：AR-01、RT-003、RT-008 independent verification；包含既有 011 約束與 RT-008 matching 相容。
- Scope：run-scoped internal identity、exact proposal binding、callback/reconcile 隔離；不改既有 migrations 或 provider public pairing。
- Acceptance：不同 run/restart 可重用 provider ID，同 run 零重複 dispatch，old approval/late callback/crash 零重播與新 run 污染。
- Rollback：保留必要 identity reader/guard，停止新 dispatch 後回退相容 local patch；不能刪 journal 或假定舊 binary 理解新 rows。
- Dependencies：現有 RT-002/007/008 基線；不等待 RT-010。獨立驗證通過才恢復 RT-003 DONE。

### RT-005-FIX-01 — candidate arguments-only handler cancellation

- Status：DONE（2026-10-04；docs/evidence/RT-005-FIX-01/REPORT.md）；Classification：REQUIRED_FIX；Severity：HIGH。
- Source：AR-02，RT-005/007 integration gap；原 RT-005 owned argv DONE 保留。
- Scope：共用 task ownership、arguments-only cancellation bridge、必要現有 caller cleanup；不加 persistent browser 或新 supervisor。
- Acceptance：受控 handler 在 terminal 前完成 cleanup；不能確認停止時 5 秒內明報 failure/unknown；零新 dispatch/late UI/跨 session 誤取消，ack detach 相容。
- Rollback：先 fence/cleanup owned jobs，保留 unknown，撤本卡 patch；舊路徑缺口未解時禁止 promotion。
- Dependencies：現有 RT-005/007/008；不等待 RT-012。

### FIX-001 — failed/cancelled generation dispatch gate

- Status：DONE（2026-10-04；修復與驗證見 docs/evidence/FIX-001/REPORT.md）；Classification：REQUIRED_FIX；Severity：HIGH。
- Source：AR-03；HEAD 已存在的 implementation bug，不歸因尚未開發的 RT-009。
- Scope：第一 round/continuation 先裁決 state，再接受 batch；partial history/readback 保持有效，不混入 retry/fallback。
- Acceptance：tool intent 後 failure 零 effect/零新 round、唯一 failed/cancelled terminal；既有 observation 不遺失，restart 不重播。
- Rollback：保留 journal 後撤局部 patch；若恢復會執行 failed intents 的版本，工具 dispatch 保持關閉，RT-009 不解鎖。
- Dependencies：現有 RT-002/003/008；不等待 RT-009。

## 開始順序

原始歷史順序為 RT-001 → RT-002 → RT-003，再 RT-004/005、RT-006、RT-007、RT-008；保留作設計歷史，不能當作目前可直接進 RT-009 的指令。

目前沒有未解 FIX；本輪修復完成停止，後續 RT 需另行授權。任何仍有 dependency/DEFER 的卡不得自動往後開發；修復必須有反例轉 PASS、相關 regression、相容/rollback 與獨立 verification 才解除對應 gate。RT-013/015 解除修復阻擋後仍 DEFER；RT-011 summary 不因 budget 完成而自動開工。文件與唯讀驗證可繼續。

若後續 evidence 證明 task 已無必要，取消相應整卡或重複子工作並保留理由；不要為完成原計畫硬加 abstraction。現有已通成果保持，不把 technical debt 自動升格成立即修復。

## 2026-10-06 AR-06/AR-07 repair follow-up

AR-06 多工具 completed batch counting 已修復：只轉換計數視圖，wire／journal／executor 不變；真 main/Core/SQLite + subprocess 續作及超限零重播測試通過。AR-07 缺少 pinned tokenizer provisioning 已修復：scripts/check 在 pytest 前執行 hash-checked setup，空目錄下載與 production asset loader 通過。證據與限制見 [repair report](../evidence/RT-011/ar06-ar07/REPORT.md)。

這解除兩項已確認局部缺陷，不代表整體 CI gate 通過：目前 checkout 的全樹 lint/format 包含既有 evidence probes 與兩個既有產品測試格式問題，仍失敗；未修改那些不相關檔案。遠端 CI 未執行。RT-011 summary、RT-013、RT-015 仍 DEFER，解除理由需各自滿足；本輪 gate evidence 見 DEFERRED_TASK_PLAN.md follow-up。既有歷史結果保留，不以局部修復覆蓋其他未驗項。
