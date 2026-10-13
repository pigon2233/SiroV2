# Risk register

## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

Pointer≠actualversion的MISSING_INTEGRATION风险在D52限定profile下降：真sourceorigin與startupready綁version/digest，新95及true5child驗。無剩餘confirmed本卡productiondefect。

仍HIGH/RED發布gate：驗簽後sameUID mutablepackage/TOCTOU、CLOEXEC maintenance→exec gap與舊／非受管writer。真oldWALwriter仍能於新lease後commit；不能以SQLiteBEGIN/ready/PIDfile/TERM成功當stoppedproof。D52未自動停止現用process或增強授權。

Sharedpinnedinterpreter/deps、source-onlycompatibleABI與same-schema限制明示；sourcehash不等於livebyteattestation，無整機sandbox或自動發布證明。RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：舊／非受管writer停止、parent驗簽後sameUID換包、maintenance→exec CLOEXEC空窗與人工批准handoff未解除。D52只證同schema／D52-compatible src package，任意deps/ABI/migration/其他OS/powerloss/正式deployment未證。FIX-002/005/006產品gates、RT-011/013/015原scopedDONE不變。

95新cases；最終相鄰335 PASS／3既有warnings／25.63s，完整 **1,673 PASS／5 real_provider未選／3既有warnings／199.58s**。Ruff315、mypy250（含launcher）、schema、source/tests/docs diff PASS。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

FIX-015 REQUIRED_FIX / MEDIUM / IMPLEMENTATION_BUG＋MISSING_INTEGRATION＋TEST_GAP已DONE：late IO staging重建／sidecars遺留風險在已驗profile下降。MINOR_FIX / LOW初版selector／coroutine teardown問題已局部修；沒有private正式data-loss或其他UID可讀證據。

剩餘風險：無界OS阻塞須保持pending/owner，不承諾新cancel SLO；close/unlink refusal可見但不能假稱cleanup完成；final os.replace後取消可能已提交，readback再決定，零自動重送。ZIP DB/config跨檔atomic、powerloss、old/nonmanagedwriter、hostile sameUID races與真正launcher仍未證。

新25 cases、相鄰240 PASS（17.60s）；完整 **1,578 PASS／5 real_provider 未選／3既有 warnings／198.40s**。Ruff311／mypy245／schema／diff PASS。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：first-adoption舊／非受管writer停止、真正signed launcher/version/readiness與人工批准handoff仍待各自驗收。FIX-002有用搜尋、FIX-005語音速度／人耳、FIX-006理解產品gate保持；RT-011/013/015原scopedDONE及編號不改。

backup/owner/Gateway YELLOW；tests GREEN；live DB/migration/grants/release RED。沒有操作live8026、私人DB/chat/WAV/key/config/models/GPU或正式部署。所有DB/OS probes是自有合成資料；pause/fault injection明示，不能冒充真人產品或power-loss驗收。

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

## 2026-10-11 strict profile 風險變化

D46 Linux x86_64/systemPython3.14 fixedstdlibsingleprocess的host/env/network/process/session/limit/kernelobject/AS/CPU/file/scratch/output/cancel界線已真OS驗；51新cases／完整1,202PASS／exact7回退。[證據](../evidence/RI-004-worker-2026-10-11/REPORT.md)。Profile可局部YELLOW，syntheticdevtests GREEN；產品enable/revoke/approval與identity/DB/grants/release仍RED。已rootcause修typedmetadata False/0與True/1、zeroqueue、delayedspawn期限，沒有用timeout放大或fallback換PASS。通用nestedschema、retention/aggregateRAM/blockedIO/同UID與runtime供應鏈、其他OS/deps/multiprocess尚未認證，workerPASS不降低人工批准要求。

## 2026-10-11 FIX-011 風險變化

worker洪水阻塞、100k JSON截斷、spawn/stdin cancel遺留、outercleanup掩蓋typedfailure在限定profile已局部修復；24新case／完整1,151PASS／exact5回退支持降為受控YELLOW。[證據](../evidence/FIX-011-2026-10-11/REPORT.md)。input64KiB收斂／PIDnamespace不支援拒絕為明示兼容影響；原trusted venv/source mounts／CPUsoftlimit可提升／fork/exec仍不能作generatedsandbox。strict single-process OS與package-bound人工批准/撤銷是RI-004獨立RED gates；retention/aggregateRAM/blockedIO SLO與release最新資料保留仍未驗，不因fullPASS消失。

## 2026-10-10 RI-004 風險變化

待審控制入口的重複提交、取消／cleanup、tools-off／shutdown、package→source→trustedtests→report binding已有88新cases、1,127完整回歸與真Chrome23checks；精確source回退也已驗。候選由單一composition owner管理，不加入DB／registry／全域scheduler，沒有新增production執行權。[驗收與回退](../evidence/RI-004-2026-10-10/REPORT.md)。

仍YELLOW：固定builtin profile／exacttyped匹配只描述登錄能力，不能证明語意gap；availability不是sandbox readiness。候選不持久化，頁reload後不恢復，只能owner手動匯出。模板限制不是完整Markdown語意；未認證跨平台/dependency/aggregate kernelRAM。CODEBASE graph MCP本輪未query/reindex，source/caller直接檢查。

仍RED：generated enabled worker／security review／package-bound explicit approval／install/撤銷／自主改碼發布及DB還原。RI-003 patch sandboxPASS不證明現有skill worker可信，不能使用computer.execute繞接。無新確認originaldesign error；兩個候選local integration defects已修，未留新修復blocker。語音／搜尋／理解gate保持。

## 2026-10-10 RI-003 risk 變更

- 降低：在已驗 Linux single-process patch profile 中，候選 import 讀寫 host／network／fork/exec／逃 owner group；來源 alias／無界輸出／取消漏清理。真 OS 與 actual CLI 單／雙 SIGINT、111專項／1,039完整回歸已有證據。
- 本卡候選缺陷已局部修復：post-apply byte bounds、memfd／IPC creation、cleanup errors 假成功、late task/token cancel、第二 SIGINT 與 completed-task window。獨立 source follow-up 未找到剩餘 confirmed scoped blocker。[報告](../evidence/RI-003-2026-10-10/REPORT.md)。
- 保留：AS是 virtual address space，scratch上限是 file data；aggregate kernel RAM／cgroups／多程序不在認證。單一API caller未接 product admission；blocked arbitrary host IO cleanup SLO未驗。不得新增背景auto caller繞過這些 gate。
- 信任／測試盲區：local kernel/system runtime/source owner與固定runner；source allowlist不判 source 中的秘密，非same-UID attestation。候選可偽造tests／exit0，PASS不授權enable/deploy。遠端CI／依賴／GPU／真人／soak未驗。
- Freeze：explicit owner單次 patch verification限支援profile由RED→YELLOW；舊trusted copy入口不獲untrusted認證。generated enabled worker、autonomous mutation／release／latest-data rollback仍RED，RI-004／005須各自驗。FIX-002／005／006 gate保留。

## 2026-10-10 FIX-010 risk變更

- 降低：unknown dispatch換新UUID/fullmode相同內容自動再執行；交易內pending/CAS/ledger check＋固定manual警告，45反例與真Chrome驗收。
- 保留：single owner/controller與stored arguments_hash信任、semantic等價不同參數/其他cap；本卡不認證任意multiwriter或DBtamper。read exception不給新grant。
- TECH_DEBT：old unknown結果人工resolution與永久scan/retention可能增加手動摩擦，未量到資源事故；不因age放行。特殊numeric key/lexeme保守hold明示限制。
- DEFER：既有gateway completed snapshot與agent waiting_tool、整頁reload pending card未接入；WS reconnect PASS不是reload。FIX-006語意/005聲音/002搜尋與RI-003–005各自gate不變，未部署。[證據](../evidence/FIX-010-2026-10-10/REPORT.md)。


## 2026-10-10 FIX-006 risk變更

- 降低：own failure context缺失、unconditional全語音/connected body保證；五欄fixedsource/15min/privacy與off/legacy fences、40tests及rollback已驗。
- 已修候選：invalid updated_at排序復活舊故障、SQLite TEXT length遇NUL；獨立memory DB反例/最終source guard驗證。
- 未解除：voice demand correction截斷、unknown-effect重送的模型語意、雲模型local-only記憶distinction/style/CAPTCHA；總品質root causeUNKNOWN，FIX-006 PARTIAL。status不是diagnosis/效果授權；model不能依metadata擅自重試。
- 限制：固定owner store≠通用多tenant，latestrecord≠每個UI/TTS故障，15min snapshot≠continuoushealth。只調composition不能證明intelligence提升。下一個usage/reasoning實驗不保存hidden reasoning、私人chat/secrets，不先調backend/budget。 [證據](../evidence/FIX-006-2026-10-10/REPORT.md)。

FIX-006補充量測已完成：[8次synthetic allocation](../evidence/FIX-006-2026-10-10/COMPLETION_ALLOCATION.md) 支持reasoning與visible verbosity混合；low仍有length與錯誤語意，REJECT本輪改production effort，不提高budget/換backend。新429有量到但不回推原事件，零自動重試。

## 2026-10-10 FIX-007 風險變化

R26-01 approved package換碼／換root漏洞已局部修復VERIFIED，完整digest與stored root/hash、同一bytes snapshot與取消cleanup有反例/真bwrap驗收。准备時8 slots限副本，concurrency按完整批准identity；無新增registry/權限。Generated skill接入仍RED gate：OS/review/明確enable；host/dependency/import-origin全closure不在此卡認證，blocked host IO取消SLO未驗。Idle semaphore retention屬TECH_DEBT、無OOM證據，不為此擴state manager。R26-01/02/04局部fix均閉合，R26-03 OS和發布/資料gates保持。[證據](../evidence/FIX-007-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-009 風險變化

R26-04 unsigned compatibility漏洞已局部修復VERIFIED，範圍／版本／digest與明確format完整簽署，legacy拒絕不fallback。canonical、strict範圍與入口重驗已有反例／zeroeffects／真CLI測試；FIX-009本身gate解除。發布整體仍RED：launcher consume、人工批准／single-writer／最新資料保留回退未驗；既有bundle-copy race/symlink語意不在本卡认证。FIX-007與untrusted checks OS gate保留。[證據](../evidence/FIX-009-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-008 風險變化

R26-02 的 protected delete/rename 漏判已局部修復並驗收，FIX-008 gate 解除。有限格式仍明確拒絕 ambiguous/unsupported input；不把 partial parse 當完整授權。PatchVerifier 的 temp copy 仍不是 OS sandbox；R26-03 untrusted checks isolation、FIX-007 package identity、FIX-009 release signature 與 launcher／資料回退風險保留。未發現 production 事故，不改標 REGRESSION。[證據](../evidence/FIX-008-2026-10-10/REPORT.md)。下方「PLANNED」為當時快照。

## 2026-10-10 FIX-002風險變化

browser failure透明度、主frame拒絕與owned teardown error風險下降；live browser仍YELLOW。useful public search／自動研究保持RED gate：Bing無結果、DDG驗證頁、兩次4s cleanup根因UNKNOWN。閉源模型不當bypass建議歸FIX-006semantic負向case，未被執行。無擴origin／deadline／權限；不能把最後一次cleanup PASS當可靠性SLO已達。

[實際證據](../evidence/FIX-002-2026-10-10/REPORT.md)。


## 2026-10-09 現況增補（下方F01–F12原快照保留）

範圍／證據：[最新架構review](ARCHITECTURE_REVIEW.md)、[source/call chains](CURRENT_ARCHITECTURE_AUDIT.md)、[T1–T40矩陣](ROADMAP_RECONCILIATION.md)、[合成安全反例](../evidence/RI-architecture-2026-10-09/REPORT.md)。風險不是全已發生production事故；新FIX-007/008/009只定義、**PLANNED，未修復**。沒有證據將它們歸因某個RT或標為已確認REGRESSION。

### 歷史風險對照

| 原ID | 本輪狀態 | 保留的界線 |
|---|---|---|
| F01／F02 | 原native role/pairing與batch缺口CLOSED；RT-002/003及相關FIX已解 | 長任務理解與新provider contract仍需各自驗收，不重造loop |
| F03／F10 | owned foreground cancel／bounded drain原缺口CLOSED；RT-004/005已解 | escaped daemon／已ack detach／任意host副作用不保證全部可回收 |
| F04 | MITIGATED；RT-008 readback/reconciliation/unknown已接 | 不代表OS效果可自動查證或任務可盲目續跑；不再新增第二journal |
| F05 | owned Qwen lifecycle原缺口CLOSED；RT-006及FIX-005有歷史取消/cleanup證據 | 語音速度／人耳品質仍OPEN，另列R26-08；不重開同child bug |
| F06 | OPEN／PARTIAL；catalog/effective config已改善 | JSON/env/不同backend scope仍分立；metadata不是grant，不為統一入口重寫policy |
| F07 | 「main未接wrapper」CLOSED；RT-009已接單backend bounded retry | 非多backend自動routing；無成本/privacy授權不增cloud fallback |
| F08 | explicit ingress與bounded canonical restore原缺口CLOSED；RT-010/014 | 不是所有聊天自動facts；cloud privacy、raw history與memory deletion範圍分開 |
| F09 | stateless browser原缺口CLOSED；RT-012已有session fill/click | public搜尋FIX-002、pool availability／TTL與credential persistence是不同範圍 |
| F11 | migration expectation原缺口CLOSED；RT-001及當前升級測試通過 | source rollback不證DB downgrade或live restore安全 |
| F12 | MITIGATED；現況前置、唯一矩陣與日期分離 | 舊friction/Hermes/baseline不作今日事實；保留歷史不全表改DONE |

### 當前風險與接入gate

| ID | Severity | Risk / evidence | Owner／分類 | 降低風險／解除條件 |
|---|---|---|---|---|
| R26-01 | HIGH | skill換plugin碼manifest_hash不變；同enabled id/version可達supervisor；`core/skills.py:65`、`adapters/skill_worker.py:138` | skill package/dispatcher；IMPLEMENTATION_BUG/BAD_INTERFACE/TEST_GAP | BLOCKED_BY_FIX：FIX-007；完整code/deps package identity、不可變安裝來源、dispatch重驗；另需sandbox/review/explicit enable |
| R26-02 | HIGH | protected delete加普通修改，PatchVerifier回passed並漏delete；`core/evolution.py:84` | patch verifier；IMPLEMENTATION_BUG/TEST_GAP | BLOCKED_BY_FIX：FIX-008；完整path parser＋delete/rename/不支援格式拒絕；rename未重現細節先查證 |
| R26-03 | HIGH | same-user check可寫temp copy外合成marker；`evolution.py:49,100` | candidate execution；BAD_INTERFACE/MISSING_INTEGRATION | RI-003真OS/FS/env/network/CPU/RAM/output/descendant隔離；缺隔離就拒不可信候選，copy只作workspace |
| R26-04 | HIGH | max_schema變更不重簽仍activated；`core/releases.py:103` | release integrity；IMPLEMENTATION_BUG/BAD_INTERFACE/TEST_GAP | BLOCKED_BY_FIX：FIX-009；canonical signed manifest涵蓋全部compat欄位，舊manifest不可靜默升級信任 |
| R26-05 | HIGH | active.json無launcher consumer；whole DB rollback覆蓋備份後新寫入；`releases.py:95`、launcher／operations | release/data owner；MISSING_INTEGRATION/TEST_GAP | RI-005獨立驗真版本、stopped-writer、code rollback保latest DB、schema不兼容拒絕；資料restore明確人工操作，不自部署 |
| R26-06 | MEDIUM | ToolDescriptor缺output/permissions/risk/version/provenance/timeout/failure；risk／固定能力宣告與readiness分散 | catalog/composition；TECH_DEBT/BAD_INTERFACE | RI-002從同catalog唯讀投影，unknown明示；不執行discovery、不改grant，既有API相容 |
| R26-07 | MEDIUM | dev source graph可能stale／漏動態callback；binary checksum非attestation；chat未hot reload | dev Codebase Knowledge；工具維護風險 | 固定版本/source hash、manual reindex、watcher=false；無網路source projection/clean env/read-only tools；graph結論用source/tests查證，不自刪死碼 |
| R26-08 | HIGH | FIX-005速度未達標：歷史首段22.446s、暖RTF約1.75；human_listening NOT_RUN | audio product；既有REQUIRED_FIX/PARTIAL | 保原聲線/completion-v2/single owner/有界prefetch，窄benchmark與當前真人首尾/自然度/取消驗收；本輪701PASS不解體驗gate |
| R26-09 | MEDIUM | 搜尋ScopeViolation整體rootcause與對話理解根因仍UNKNOWN；error reason不足 | browser/companion；FIX-002/006 | 合成重現＋安全reason code＋乾淨public搜尋E2E／多輪對照；不因猜測URL格式放寬scope |
| R26-10 | MEDIUM | retention／single-owner／mutable callback與長時資源風險尚未由24h資料覆蓋 | runtime composition/organizer/browser/governor；TECH_DEBT/TEST_GAP | 量測再局部清理；保持foreground優先、bounded lifecycle；不把RT-015唯讀view完成當一般scheduler完成 |
| R26-11 | HIGH | 有helper就誤宣稱自主技能、桌寵全動作、硬體/多節點、完整產品發布 | 產品驗收責任；DOCUMENTATION_DRIFT/MISSING_INTEGRATION | 能力/卡片分層；T35/T39/T40仍Planned Only；實際L3/24h/人工批准逐項解除，未完成需求不CANCEL |

### 驗證與freeze

本輪實跑before **671PASS／5 deselected／3 warnings**、after **701PASS／5 deselected／3 warnings**；Rust6PASS；Ruff check/269files format與mypy204files PASS。新增30個developer tests只驗開發工具；安全反例仍未修。原251個source/tests/locks hash零變；8026 root/live/live2d HTTP200；未重啟服務、讀私人資料或跑GPU／人耳／設備／第二節點／遠端CI／24h。[保留與回退證據](../evidence/runtime-intelligence-2026-10-09/preservation-and-rollback.json)。本輪local MCP已索引250files/3092nodes/16700edges，mutation/source writes拒絕、watcher關閉；不等於SIRO runtime具有MCP能力。

GREEN：文件／受限dev graph／已驗局部invariants。YELLOW：catalog/context/browser/provider/organizer組合、trusted worker、Web body/voice與產品配置。RED：R26-01–05相關自主執行/發布接入，以及identity/schema/grant wire/licensed assets/實體firmware原保護區。AR-06/07已修，不延用舊RED；RT-011 summary/013/015不重新DEFER。新FIX gate只阻擋其相關promotion，唯讀盤點與其他獨立產品修復可繼續。

Rollback（本輪開發整合）：disable/remove新增project MCP設定、停止owned dev server、移除指定可丟棄projection/index或撤本輪helper/docs/tests；不撤先前dirty成果、不還原私人DB、不重啟SIRO。Codex disable→restore已測。這不是generated-code／deployed-service或DB rollback已通過；未來各卡另驗。Hermes只REUSE已落地概念、REJECT平行framework/registry/memory/router，DEFER缺caller或安全gate的進階部分，不重做已解問題。

---

## 2026-09-30 歷史風險快照（不覆蓋上方現況）

風險不是全部已重現的故障。owner 為 subsystem 維護責任，非新建人員或任務。

| ID | Severity | Risk / evidence | Owner | 驗證或降低風險的條件 |
|---|---|---|---|---|
| F01 | HIGH | 工具續作失去原生訊息結構；`integrated.py:continue_after_tool / conversation.py:respond` | 多步任務與不可信 tool output | 在既有 ports/core 上接 native messages；先保留 prompt compatibility；變更前保留 baseline，變更後測 `provider schema、歷史對話相容` 相關回歸 |
| F02 | HIGH | 多工具 batch 逐一遞迴；`integrated.py:_propose_tool_calls` | multi-call model responses | 先收齊當批結果再 continuation；用合成兩工具案例確認；變更前保留 baseline，變更後測 `批准/錯誤順序行為改變` 相關回歸 |
| F03 | HIGH | 取消沒有貫穿執行程序；`integrated.py:cancel / gateway.py:execute_computer` | 長程序與 UI 控制 | 把現有取消訊號包進 executor context/handle；變更前保留 baseline，變更後測 `誤殺 detach 或已完成 child` 相關回歸 |
| F04 | HIGH | 持久 run 不等於可恢復 run；`services/agent/runs.py / integrated.py:continue_after_tool` | 長任務/安裝流程 | 先辨識 interrupted/unknown，再做 observation reconciliation；變更前保留 baseline，變更後測 `不得自動重播 side effects` 相關回歸 |
| F05 | HIGH | Qwen child/回覆生命周期不完整；`services/audio/tts.py:QwenReferenceTTS` | 4GB GPU、頻繁取消 | wrapper 管理 terminate/wait/restart 與 request correlation；變更前保留 baseline，變更後測 `冷啟動成本/語音回歸` 相關回歸 |
| F06 | HIGH | 配置與權限有分立入口；`gateway.py:main / config.py / runtime rpc` | budget/privacy/OS expansion | 先做 effective-config 與能力/權限對照；保留 full 授權偏好；變更前保留 baseline，變更後測 `配置相容與既有操作受影響` 相關回歸 |
| F07 | MEDIUM | fallback 元件未用於 main；`gateway.py:main / adapters/models/failover.py` | local/cloud reliability | 沿用 wrapper；先訂副作用/串流可重试边界；變更前保留 baseline，變更後測 `重複工具/雲端費用` 相關回歸 |
| F08 | MEDIUM | memory 沒有完整 ingress/restore；`core/companion.py / core/memory.py` | 長期人格/關係 | 先驗證事件→候選 memory→commit→recall，不搬 repository；變更前保留 baseline，變更後測 `誤記憶/隱私保存` 相關回歸 |
| F09 | MEDIUM | 瀏覽器狀態每步結束；`gateway.py:browser_tool` | 跨頁任務 | session wrapper 管理既有 driver；變更前保留 baseline，變更後測 `資源釋放、session 隔離` 相關回歸 |
| F10 | MEDIUM | output 限制發生在讀完之後；`gateway.py:execute_computer` | 大量 stdout/stderr | bounded drain wrapper；變更前保留 baseline，變更後測 `stdout/stderr 排序及錯誤可見性` 相關回歸 |
| F11 | MEDIUM | 基線測試已落後 schema；`tests/integration/test_sqlite_store.py:48` | migration/release | 先核對 migration invariant 再更新正確 expectation；變更前保留 baseline，變更後測 `只改 assertion 會漏真正 schema 回歸` 相關回歸 |
| F12 | LOW | 文件狀態過期；`docs/STATUS.md` | 交接 | 以此次 evidence index 作目前事實入口；變更前保留 baseline，變更後測 `低；預設不進 migration roadmap` 相關回歸 |

## 稽核自身的限制

- R-A01：測試通過可能只代表注入 mock 的組裝。降低方式：在報告中逐項標層級；真 main/hardware 保持 UNKNOWN。
- R-A02：dirty tree 與 HEAD 不同。以 SOURCE_INVENTORY SHA256 固定此次 Python source；不以 commit 單獨重現。
- R-A03：靜態 import closure 會高估 runtime 使用範圍。constructor/caller 為最終判斷；不刪除疑似 dead code。
- R-A04：Hermes snapshot 是外部參考，不是 SIRO 可用性證據。沒有採取 framework migration。
- R-A05：模型/cache 在 git status 顯示 untracked；本次沒有 stage/commit，後續發布前須核對資料與資產政策。

Rollback（本次）：只新增稽核文件與 STATUS 記錄；刪除本次文件即可撤回文件交付，不影響 production。這不是未來程式修改的 rollback 設計。
