# SIRO V2 Architecture Review

## 2026-10-13 — actual cloud follow-up / FIX-017 owner boundary

Overall architecture health YELLOW。Recent improvements：既有checks coldboot已修；真SQLite兩版manualguard保持，fixture只移除version-specific假設；TTS的optionalSDK改既有offlooplazy載入，5RED→PASS/34related/exact2rollback。

Architecture drift found：existingpresentation→TTS→Kokoro→ONNX module-top import在owner前做device discovery；brokenSDK可阻止Busy回報，違反D50。FIX-017 REQUIRED_FIX/MEDIUM是局部implementation/integration leakage，原owner設計有效；不需原design重設或新provider loader。Gateway/owner/SQL/權限/其他runtime保留。

Regression risk changes：本機tool/profile遮住freshCI環境缺失，cloud54FAIL如實保留；supportedUbuntu26.04+nativesandboxpreflight將真正跑原102environment-skippedcases，不能新增skip或mutewarning放行。final9filelocal/remote尚待驗，原五檔1697PASS不是本輪全部驗收。Technicaldebt：publicblob變更需re-audit、extraPython3.12預裝保持；nativehardcancel/voicequality/otherOS/powerloss不因本卡完成。

Roadmap adjustments / New blockers：FIX-016/FIX-017 IN_PROGRESS；RI-005/006後續BLOCKED_BY_FIX到actualfullacceptance。KEEP原RTDONE，KEEP/SPLIT RI-005adoption/approvedhandoff，KEEP RI-006readonlyproposal。Hermes REJECT duplicateSDKloader/owner/updater抽象，不為新功能重構主架構。

Freeze zone changes：CI與TTS本卡YELLOW pendingfull；tests/evidenceGREEN；liveDB/permission/releaseRED，其他runtime原YELLOW。Recommendednext3既有scope（非ranking）：old/unmanagedwriterabsence；immutableapprovedexacthandoff；source-boundreadonlyproposal。

[CI](../evidence/FIX-016-2026-10-13/REPORT.md)／[one-leaf boundary repair](../evidence/FIX-017-2026-10-13/REPORT.md)。


## 2026-10-13 — FIX-016 / D53 clean CI verification review

Overall architecture health仍YELLOW：本卡是buildbootstrap／verification integration局部缺陷，不是productionarchitecture drift。Recent improvements：freshisolatedRust明確工具declared、secretreview只綁六個actualverifiedpublicpins；24meaningful新tests與exact5rollbackPASS。原責任/介面/依賴/DB/API全保留，沒有新runtimeglobalstate或繞過compatibilityboundary。

Regression risk changes：舊本機預裝Rust遮住freshrunner缺components，已cold RED→PASS；原secretgate6公開digest誤報的blockingpath已重現→局部修復。完整clean scripts/check及exactheadActions尚待完成；不可用歷史1673PASS代稱本次CI。Wrong3.12harness的brokerhang為TEST_GAP/DEFER、rootcauseUNKNOWN；已stop/join，正確本機3.14.4重跑。

Technical debt introduced：publicprofileblob改動需要再審；不自動扩allowlist。Python3.12預裝/actual3.14不一致是既有TECH_DEBT，此卡不動versions/locks。Rollback僅sourcebuildpatch，不動data或已安裝tools。

Roadmap adjustments / New blockers：FIX-016 REQUIRED_FIX/MEDIUM IN_PROGRESS；RI-005/006後續實作BLOCKED_BY_FIX: FIX-016到完整local+remote驗收。KEEP原RTDONE；KEEP/SPLIT RI-005剩餘adoption/handoff；KEEP RI-006readonlyproposal。沒有重編/ranking或重做DONE。Hermes REJECT第二updater/owner/secretframework；不用新runtime抽象修CI。

Freeze zone changes：CIbuild zone YELLOW直到完整驗收；tests/evidenceGREEN；runtime元件沿原YELLOW，liveDB/migrations/permissions/release仍RED。Recommended next3既有scope（非ranking）：RI-005old/unmanagedwriterabsence；RI-005immutableapprovedexacthandoff；RI-006source-boundreadonlyproposal。產品搜尋/voice/理解与正式releasegates不因本卡解除。

[本次實際證據與限制](../evidence/FIX-016-2026-10-13/REPORT.md)。


Remote refinement：f253dec已過fmt/build，cargo unit fixture硬編/usr/bin/python3.14而failed；只允許cfg(test)三個literal改/usr/bin/python3，所有asserts/productionprefix保持。完整Rust checks/6tests與exact5rollbackPASS；final完整local與newheadremote仍PENDING，不能把先前4file驗收稱成finalsourcePASS。

## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

**Overall architecture health — YELLOW。** D52沿已簽版本/單一owner方向演進，actualsourceidentity不再只靠pointer/env label；整卡仍PARTIAL。只改既有ReleaseManager/read-schema fact、productlauncher與Gateway composition/ready；新增4份tests。complete manifest/CLI stage-rollback、D49/D50/D51、Core人格/記憶/權限/模型/語音/UI/SQL/deps保留。

**Recent improvements。** operator明確SIRO_RELEASE_ROOT＋原signing-key opt-in；bounded complete signed active package與actualreadonlyschema→fresh-I/-B selectedsrc→existing D50 owner內實際SIRO/Core/Gateway來源及schemaepoch重驗→startup完成後HTTPready version/digest。簽署key不進childenv；originalcwd/data/assets保持，signedmode不provision、不fallback，不隱含migrate。

**Architecture drift found。** confirmed missing integration（MISSING_INTEGRATION/INCOMPLETE_TASK/TEST_GAP）限定切片已接；Core只公開read-only verifiedtarget，沒有引用Gateway/UI；Gateway只composition guard/readback。無第二updater/registry/owner、hiddenglobalstate或provider/device bypass。schema fact局部重用且D48AST語意相同。

**Regression risk changes。** 95新cases；最終相鄰335 PASS／3既有warnings／25.63s，完整 **1,673 PASS／5 real_provider未選／3既有warnings／199.58s**。Ruff315、mypy250（含launcher）、schema、source/tests/docs diff PASS。 新origin/schemaepoch/readiness/原defaultshape與true2version/rollback作baseline，不能只用mock exec或activepointer當作actualversion。

**Technical debt introduced。** D52-compatible bootstrap ABI、shared pinned interpreter/deps與同schema限制明示；不擴成通用更新framework。不讀childkey、不讓codeversion切换換DB或造bytecode；未知/unsupported拒而不hostfallback。

**Roadmap adjustments。** KEEP RI-005/SPLIT remainingfirstadoption與immutable approvedhandoff；D52resolver/loadedidentity/同schemaready scopedVERIFIED。KEEP RI-006唯讀提案。沒有實證支持額外CANCEL/MERGE/REORDER numberedtask，不改原RT歷史。

**New blockers。** 無剩餘confirmedD52局部blocker；RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：舊／非受管writer停止、parent驗簽後sameUID換包、maintenance→exec CLOEXEC空窗與人工批准handoff未解除。D52只證同schema／D52-compatible src package，任意deps/ABI/migration/其他OS/powerloss/正式deployment未證。FIX-002/005/006產品gates、RT-011/013/015原scopedDONE不變。

**Freeze zone changes。** selector/launcher/Gateway YELLOW；合成tests/evidence GREEN；運行DB/migration/permission/發布 RED。273baseline中270不改；exact7 source-only disposable reverse/reapply PASS，保所有資料與Git歷史。D48 schema helper抽出前後AST相同；D51 backup/CLI四檔與D50 owner/operations source保持。

**Hermes relevance。** REJECT第二updater/owner/schemaengine；DEFER任意自改/自動發布/deps/跨平台到具體caller與獨立批准安全gate。既有source切片解決即停止重構。

**Recommended next 3 existing task scopes（不排名）。** RI-005 knownoldwriter gracefuljoin/adoption；RI-005immutable exactapprovedpackage＋maintenance/runtimehandoff；RI-006source-backed failure→唯讀proposal。FIX-002/005/006品質驗收各自保持。

沒有重啟live8026／讀privateDB/chat/WAV/key/config/models/GPU或正式deploy；全部程序/DB/HTTP為self-owned合成fixture，只讀health，無provider/TTS請求或效果重播。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

**Overall architecture health — YELLOW。** 單一owner與既有backup boundary方向成立；本輪修復已證local defect，不需推翻runtime設計。只改SQLiteStore既有backup方法與CLI `_backup` wrapper，新增兩份專項tests；operations、D49 restore body/SQL、D50 owner/Gateway/原tests、Core/權限/providers/voice/UI/launcher/deps不變。

**Recent improvements。** retained executor Future＋copy_context＋backup-local cancel Event讓writer lock持有至真正IO／明確connection close／cleanup完成；ZIP沿原context順序清理。CLI單次backup在main thread把SIGINT轉成owned task.cancel並喚醒同loop，反覆中斷等待收尾，finally恢復原handler；primarytypederror優先，plainCancelledError不改，signal cancellation才轉KeyboardInterrupt/130。 真SIGINT先暴露selector盲區再局部修掉。

**Architecture drift found。** 已修responsibility leakage：backup coroutine先退但thread仍寫，外層ZIP失去cleanup時間權威。未新增duplicated abstractions／Core lower dependency／global registry／circular coupling／compatibility bypass；CLI只composition-level signal lifetime。

**Regression risk changes。** 新25 cases、相鄰240 PASS（17.60s）；完整 **1,578 PASS／5 real_provider 未選／3既有 warnings／198.40s**。Ruff311／mypy245／schema／diff PASS。 真8OS cancellation及25新cases成為新baseline；原D50 callers保持。actual blocking selector不能僅靠controlled task.cancel測試代替。

**Technical debt introduced。** signalhandler lifetime和private optional cancel Event為最小operation-local obligation；D49restore與backup不硬抽共用manager。未知OS阻塞、cleanup refusal、備份retention與跨檔atomic仍DEFER/TECH_DEBT，無新立即重構依據。

**Roadmap adjustments。** KEEP RI-005，SPLIT stopped-old-writer/actual approved launcher/handoff；FIX-015 DONE解除其局部block。KEEP RI-006唯讀proposal。CANCEL/REORDER/MERGE/額外DEFER numbered tasks無新增實證需求，不硬套動作、不重編RT。

**New blockers。** 無剩餘confirmed FIX-015 scoped blocker；RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：first-adoption舊／非受管writer停止、真正signed launcher/version/readiness與人工批准handoff仍待各自驗收。FIX-002有用搜尋、FIX-005語音速度／人耳、FIX-006理解產品gate保持；RT-011/013/015原scopedDONE及編號不改。

**Freeze zone changes。** backup取消staging由FAILED_VERIFICATION恢復限定VERIFIED，但module仍YELLOW；owner/Gateway YELLOW，合成tests/evidence GREEN，live DB/migration/權限/發布 RED。269/271既有baseline bytes保持，exact4 source-only temporary reverse/reapply PASS；保留所有資料與Git歷史，source rollback不授權再用舊危險取消路徑。

**Hermes relevance。** REJECT重複backup/owner/executor/state-manager抽象；DEFER一般自改/自動發布及更多profiles至有caller、收益和獨立gate證据。已有局部行為已解決，不再重構。

**Recommended next 3 RT task scopes（不排名、不換號）。** RI-005 first-adoption stopped-old-owner證明；RI-005 exact approved signed launcher/version/readiness/handoff；RI-006 sourced-failure→唯讀proposal，不自啟用/發布。產品FIX-002/005/006保持獨立品質驗收。

沒有操作live8026、私人DB/chat/WAV/key/config/models/GPU或正式部署。所有DB/OS probes是自有合成資料；pause/fault injection明示，不能冒充真人產品或power-loss驗收。

[驗收、分類、限制與回退](../evidence/FIX-015-2026-10-13/REPORT.md)。

## 2026-10-12 — RI-005 D50 owner / FIX-014 限定切片 VERIFIED

受管Gateway與CLI demo/backup/restore/有DBrelease在實際操作前取得同一canonical data owner，持有到startup/server drain/owned SQLite IO完成；備份來源、explicit目的地、ZIP固定.tmp共同有序去重（最多3keys）、一份IOjoin fence。真正foreignowner/alias與連續SIGINT反例先RED→局部修復；禁止output/tmp覆寫sourceDB/inputsettings/archive或tmp指向final，不改Core/SQLite/operations/release/權限/voice/UI/launcher/deps。沒有第二套registry/restore/lockmanager或globalstate。FIX-014 **DONE/VERIFIED**。

70新cases；最終相鄰**215PASS/10.58s**，完整**1,553PASS/5 real_provider未選/3既有warnings/157.81s**；Ruff309/mypy243/schema/diff PASS。真offline Gateway HTTP、kernel contention/fork/exec/aliases、raw/demo/ZIP三次SIGINT、3FD join/partialcleanup；fault/timing控制明示。baseline268中266不改、exact5source-only temporary reverse/reapply PASS、D47/D48/D49保留。獨立contract16PASS並重綁final5，lifecycle reviewer最後turn碰accountlimit，不假稱三份final批准；final OS probe另列。敏感掃描與cutoff見報告。

另真ZIP backup-stage probe確認未改的backup_to取消早退→TemporaryDirectory先清理→late IO重建staging，command join後仍留snapshot/sidecars：**FIX-015 REQUIRED_FIX/MEDIUM PLANNED / FAILED_VERIFICATION**，不是D50 lease失效。原dir0700、重建0775，實測DB/sidecars0600，沒有其他UID可讀內容證據。只要求既有backup局部canceljoin/明確close，不在本卡擴全SQLite。RI-005整體**PARTIAL / BLOCKED_BY_FIX: FIX-015 / BLOCKED_BY_RELEASE_INTEGRATION**；ZIP完整cleanup、firstadoption舊owner停止、signedlauncher真正版本/readiness/批准handoff仍未驗，禁止用source切片PASS放行發布。

Architecture **YELLOW**；owner/Gateway **YELLOW**、合成tests/evidence **GREEN**；runningDB/migration/權限/發布 **RED**。KEEP RI-005並SPLIT remaininglauncher/handoff，KEEP RI-006只到唯讀提案；REJECT重複owner/restore abstraction，未證任何 numberedtask冗餘，不硬CANCEL。RT-011/013/015原scopedDONE/編號不變，FIX-002/005/006產品gate保持。接續三窄卡（非ranking）：FIX-015局部backup cleanup、RI-005人工批准version/readiness/handoff、RI-006來源失敗→唯讀提案。沒有live8026重啟、私人DB/chat/WAV/key/config/model/GPU或發布。

[實際驗收、限制與精確回退](../evidence/RI-005-owner-2026-10-12/REPORT.md)。

### D50 review areas（以本次實測為準）

| Area | Current conclusion |
|---|---|
| Overall architecture health | YELLOW；小型OS adapter只在composition接入，有實際單owner/取消/目的地保護價值，Core與D49不改。 |
| Recent improvements | 真Gateway/CLI共同canonical boundary，startup/drain/IO joined才釋放；ZIP已知write scope不再繞過來源owner。 |
| Architecture drift found | FIX-014 source-only boundary與fixed .tmp角色滲漏已局部修復；FIX-015舊backup cancellation仍缺IO/cleanup ordering，單列未完成，不把adapter當萬能清理層。沒有確認circular/provider/tool/device責任新增滲透。 |
| Migration quality | 無schema migration；正常CLI/API格式保持，unsafe aliases新增拒絕。Exact5source reverse/reapply保留dirty baseline與全部資料。Old/raw/library owner明確UNMANAGED，firstadoption不可拿free lease冒充已停止；半新半舊接入保留可辨識gate。 |
| Regression risk changes | 管理startup/drain與multi-write coordination風險上升，新增70baseline；真正backup-stage probe另外捕捉215/1553綠燈未覆蓋的ZIP staging盲區，FIX-015需補case。 |
| Technical debt introduced | 保留empty stable key files而無retention cleanup、每owned loop一份local stdlib pool；不是永久legacy adapter或另一registry。D49 candidate capacity/backup retention維持TECH_DEBT；沒有量測需求不擴新service。 |
| Roadmap adjustments | KEEP RI-005、SPLIT已驗owner與remainingapprovedlauncher/handoff；插入FIX-015，不撤原RT DONE或改編號。KEEP RI-006 proposal-only。沒有證實冗餘 numberedtask，不為湊分類CANCEL。 |
| New blockers | FIX-015 REQUIRED_FIX/MEDIUM：ZIP staging重建留snapshot，BLOCKED_BY_FIX僅其cleanup/相關RI-005接入；firstadoption/實際signedversion/readiness/批准gate仍保留。 |
| Freeze zone changes | Scoped owner/Gateway YELLOW，合成tests/evidence GREEN；runningDB/migrations/權限/發布RED，ZIPcleanup不升GREEN。 |
| Hermes relevance | REJECT duplicate owner/restore/evolution abstraction；DEFER任意self-change/deploy直到caller與批准有證據。已有有效能力不再重造。 |
| Recommended next 3 tasks（不排名） | FIX-015 local backup cancellation/cleanup；RI-005 approved signedlauncher/version/readiness/handoff；RI-006 sourced failure→readonly proposal。 |

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

## 2026-10-11 D46 limited worker review

**Overall health：局部往既有方向演進，產品未完成。** RI-003最小runtime/不可逆限制下移同一adapter實作，WorkerSupervisor明確profile接入；services保留facade/Core無OS耦合，無雙sandbox/registry/executor。Actual D44template→worker可運行、原D45/default/Dispatcher保留，51新cases／完整1,202PASS／exact7回退支持限定VERIFIED。[REPORT](../evidence/RI-004-worker-2026-10-11/REPORT.md)。

Drift／regression risk：prototype從caller metadata作authority、staticadmission太晚、relativeclock漏spawn三缺口均先反例後同檔rootcause修復，無剩餘confirmedscopedblocker。TypedJSON比對與captured authority局部落在adapter，不另造schemaframework。Technicaldebt：舊trustedmetadata equality、semaphore retention／通用schema子集保留；aggregateRAM/blockedIO/runtime供應鏈未認證，不因coretestPASS硬擴profile。

**KEEP RI-004／SPLIT接入**：下一產品control owner審閱／明確批准／disabledinstall／exactidentityenable/revoke／原catalog；RI-005／RI-006按各自依賴和產品品質gatesKEEP，這三張是接續識別而非ranking。身份/DB/grants/發布與generatedenable RED；限定strictworker YELLOW、syntheticdocs/tests GREEN。不重做已完成RT-011/013/015、不增加Hermes abstraction或把圖譜當memory/authority。

## 2026-10-11 FIX-011 局部演進 review

**健康：局部改善、全產品未完成。** 確認worker绕過既有boundedprocess lifecycle；將同一owner下移adapter、service保留compatibility façade，沒有Core/adapter→service新反向依賴／雙executor。独立review发现relocation遺漏privatecaller與strictJSON UTF-8语義，已先RED→最小修復；既有Dispatcher cleanup error masking同檔局部處理，完整identity不重構。24新case、完整1,151PASS及exact5回退支持有限驗收。[證據](../evidence/FIX-011-2026-10-11/REPORT.md)。

**KEEP RI-004／SPLIT**：下一個strict fixed stdlib worker，再package-bound owner review/enable/revoke接原catalog；FIX-011局部block已解除，strictOS/approval仍RED。trusted worker/facade維持YELLOW，isolated synthetic tests／docs GREEN；identity/DB/permission與release RED不變。沒有新abstraction理由、沒有original design error證據，不重開已解決RT或為取得PASS放寬gates。Recommended接續三張仍RI-004、RI-005、RI-006，各自按依賴與產品門檻；此列不作ranking，RI-005／006不因本卡獲准自動部署／背景任務。

## 2026-10-10 RI-004 增量 review

Overall architecture health：**YELLOW**。固定候選產品切片已可實際準備／隔離驗證／檢查／匯出，不等於完整自主學習。88新tests／1,127full／真Chrome23checks與精確六檔回退有證據；既有248source中只Gateway/index兩檔預期改動。[驗收與回退](../evidence/RI-004-2026-10-10/REPORT.md)。

Recent improvements：同一ToolCatalog全inventory的typedaliases查找、既有complete packagecapture、RI-003固定trustedprofile再利用；單一明確owner/offloopIO/canceljoin、safeUI與source/test/proposal binding。沒有hostimport、model生成、registry/DB新增或執行權；Gateway保留傳輸與gate，workflow在composition。

Architecture drift found：獨立review发现catalogorder遺漏一般alternative與service/UIfailurecode不一致，兩個localdefects已修、actualpayloadfollow-up已驗。未發現確認的CoreOS引用／layerpenetration／循環依賴／compatibility bypass或重複registry。沒有證據originaldesign須重設；不重構已解RT。

Regression risk changes：候選控制與metadata/UI由未接到有測试，風險下降；enabled worker仍未認證，不能把patchPASS升格。5real_provider本輪未選，語音/搜尋/理解產品gate保持。Technical debt introduced：固定profile刻意有限、不持久化review；exacttypedinventory不搜索installedregistry／語意等價。這些明列scope，不為完整欄位建立新framework。

Roadmap adjustments／new blockers：**KEEP RI-004，SPLIT** review切片與worker/approval/enable/revoke切片，整卡PARTIAL；下一步先worker固定用途bytes/OS/cancel證據，再接批准。**KEEP RI-005**launcher/singlewriter/latestdata回退。没有剩餘confirmed本卡修復blocker；既有BLOCKED_BY_SKILL_INTEGRATION與releasegate保持，不重編號／不改原DONE。

Freeze zone changes：typedmetadata/manifest/相容contracts **GREEN**；明確owner候選準備、已驗Linux固定sandbox/review **YELLOW**（產品接線已驗）；generatedenabledworker、任意自主修改／權限／發布與資料還原 **RED**。旧trustedcopy與一般argv不因此取得sandbox身份。

Hermes relevance：**REJECT**新全域statemanager／第二registry/executor／通用generationplanner；**DEFER**dependency/multiprocess/crossplatformprofiles至有實際caller。下一三個既有續作範圍（非ranking／無新RT編號）：RI-004固定用途worker與明確批准接入；FIX-006有實證的理解局部修復；RI-005temporaryDB/launcher資料保留驗收。RT-011/013/015DONE保持，候選入口不解除其他產品品質gates。

## 2026-10-10 RI-003 增量 review

Overall architecture health：**YELLOW**。新的明確 owner 單程序驗證入口改善 source-copy 被誤當 sandbox 的缺口，沒有讓 Core 引用具體 OS driver。只抽 pure preflight、重用既有 report／process owner／FIX-008 parser；没有平行 permission、registry、scheduler、provider 或 memory。真 OS／111專項／1,039完整回歸與精確六檔回退支持這個局部切片，不支持整套自主產品已完成。[驗收](../evidence/RI-003-2026-10-10/REPORT.md)。

Recent improvements／drift：no-follow source-only capture、候選外 trusted runner、固定 profile、不支援即拒絕、取消後清理均已驗。獨立 review 抓到 private IPC kernel allocation 与 late SIGINT status；先 RED 再 local repair，follow-up 無剩餘 confirmed scoped blocker。沒有證據原 Runtime Evolution 方向錯誤，不為此重設 subsystem 或重構已解決的 RT。

Regression risk／technical debt：本機 48 新 cases 全跑，其他平台 skip 不代表 verified。AS/scratch 不認證 aggregate kernel RAM，threads／multiprocess／pytest/deps 仍未支援；可見 `.py` allowlist 不辨識 source 裡的秘密。Candidate tests 可偽造，不能充當批准；trusted runtime、blocked arbitrary host IO、未接 product admission/owner lifecycle 是明列限制。這些不是新增 abstraction 的理由，需求出現時才擴 profile。

Roadmap／new blockers：**KEEP RI-004，SPLIT** disabled read-only candidate／verification／review 與實際 enabled worker／explicit approval。前者可用已驗 profile；後者仍需自身 runtime boundary 驗收。**KEEP RI-005** 的 launcher／single-writer／latest-data rollback gate。一般多程序 aggregate gate未解除，沒有新理由 CANCEL 原 RT 或重開已 DONE RT-011／013／015。

Freeze zones：pure preflight／舊相容 contracts **GREEN**；explicit owner／已驗 Linux single-process patch profile **YELLOW**；autonomous mutation、generated enabled worker、release/data rollback **RED**。舊 trusted copy API 仍只供 trusted checks；不得用新profile通過將它放行。

Hermes relevance：**REJECT** 為此新增全域 state manager／第二 executor／planner／registry；**DEFER** 跨平台、多程序與 dependency profiles 至具體 caller 需要。下一個三個既有續作範圍（不是 ranking／不新增 RT 編號）：RI-004 disabled candidate review、FIX-006 有實證的理解局部修復、RI-005 temporary DB／launcher 資料保留式驗收。搜尋與語音仍保留各自品質 gate。

## 2026-10-10 FIX-010 增量 review

Overall architecture health仍YELLOW。發現的drift是舊proposal fence與full auto新proposal之間missing integration，局部批准交易/UI修復，沒有新ledger、owner、scheduler、provider或Core耦合。歷史args/receipt只在SQLite驗證，不外送，manual/DB/hash/grants相容。45反例、122相鄰、991全套與真Chrome21checks/5file回退支持局部invariant恢復。

Freeze：unknown-effect exact auto approval由局部RED回YELLOW；語意等價動作、自主失敗重送/自改/發布仍RED，FIX-006理解及RI-003–005 gate保留。Unknown resolution/retention與reload recovery仍列debt，不加Hermes state/planner abstraction，不以自動TTL清未知結果。來源/Unicode/numeric邊界的候選defects已先RED再修；無證據原RuntimeEvolution整體design錯誤。下一窄卡RI-003先驗OS支援/可信profile，不重做已完成RT。[證據](../evidence/FIX-010-2026-10-10/REPORT.md)。


## 2026-10-10 FIX-006 review 更新

Overall architecture health仍YELLOW：same owner/compatibility邊界保留，只既有read repository和composition切片，不新增health service/cache/memory/provider abstraction。局部改善為自己的安全狀態進prompt、撤完整語音/連線過度保證；不把「最近recorded dialog」推成TTS診斷或全知。獨立review已修invalid-time選舊故障與SQLite NUL byte bound兩個候選defects，未證實Core redesign需求。40新tests/946全套/3file rollback支持局部穩定性，真模型voice correction與unknown-effect語意仍FAIL，不能把元件PASS升為產品DONE。

Freeze：既有run persistence/composition維持YELLOW（有界投影已驗）；自主失敗重送/自我修复執行維持RED，metadata非授權。FIX-006 PARTIAL gate保留，FIX-002/005與RI-003–005原gate不變。Hermes不加新planner/state/memory abstraction；廣泛prompt無穩定收益已REJECT。下一步以usage/terminal數值驗原512 completion行為，不以假設提高budget。無新已確認original design error/architecture correction。 [證據](../evidence/FIX-006-2026-10-10/REPORT.md)。

## 2026-10-10 FIX-007 增量 review

Overall仍YELLOW。舊InstalledSkill/registry/dispatcher恢復approved bytes/root與worker交付一致；不用平行registry、scheduler、resolver或DB。原manifest_hash名字沿用作package digest，是文件化compatibility選擇，不為命名重構。Approved identity boundary由局部RED回YELLOW；unreviewed generated activation／untrusted checks／自主發布仍RED。Legacy rows不清除不自動升級，需可信owner重新批准；精確4檔temp回退保持dispatch disabled。66專項與906全套有實證。新增owned snapshot bounded8、限16MiB每份，未把copy稱sandbox；cache retention/host dependency為TECH_DEBT或接入gate。原RT保留，下一張FIX-006解實際文字理解問題，不因安全repair完成再擴抽象。[驗收](../evidence/FIX-007-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-009 增量 review

Overall仍YELLOW。單一ReleaseManifest/Manager驗證邊界恢復「所有決策欄位皆簽署」invariant，不新增signing service、registry、runtime耦合或依賴。Local signature freeze zone由RED回YELLOW；promotion／資料回退仍RED。明確legacy拒絕為必要安全相容限縮，可信owner需重驗／重簽，不能為舊artifactfallback；staging/backup/rollback原owner與流程保持。修前真反例、新舊36與全套863PASS、3檔temp回退有證據。FIX-007尚待修；原已完成RT保留，不重構已解問題。[驗收](../evidence/FIX-009-2026-10-10/REPORT.md)。
## 2026-10-10 FIX-008 增量 review

Overall architecture health 仍 YELLOW。既有 PatchVerifier 以有限 text-diff dialect 恢復完整 old/new path invariant；只改一個 production 檔，沒有新增執行 owner、抽象或依賴。刪除／改名漏判的局部 drift 已修；真 Git temp apply、63 專項、全套 829 PASS 與精確兩檔回退皆驗。這不能解除 untrusted checks 的 OS isolation、可信 check allowlist、技能批准或發布／資料保留 gate。

Freeze zone：受保護路徑的格式與入場驗證由局部 RED 回到 YELLOW；不可信執行及自主 promotion 仍 RED。FIX-007、FIX-009 尚未完成。保留已解 RT 能力，不擴通用 diff parser 或重構 Core。[證據](../evidence/FIX-008-2026-10-10/REPORT.md)。下方日期段落為各時點快照，現況以最新驗收為準。

## 2026-10-10 FIX-002增量review

既有browser/session/catalog/observation邊界內完成6檔局部修復，未新增registry／scheduler／owner／schema或Core耦合。仍overall YELLOW；手動受限read與UI reason改善，automatic public research保持局部RED；其他freeze zone與RT歷史不改。原origin設計仍有效，partial契約D37解決非必要resource整頁拒絕，沒有理由再重構browser。

[實際證據](../evidence/FIX-002-2026-10-10/REPORT.md)。


## 2026-10-09 Current review（優先於下方歷史）

範圍：`main` / `c1d2d41b2afc8844ff46f328043f7d2e8bf3cabe` 加本輪開始時既有 dirty source。已重新閱讀 CURRENT_ARCHITECTURE_AUDIT、CAPABILITY_MATRIX、ARCHITECTURE_FRICTION_MAP、HERMES_GAP_ANALYSIS、RUNTIME_EVOLUTION_SPEC、COMPATIBILITY_PLAN、MIGRATION_PLAN、RUNTIME_EVOLUTION_ROADMAP、REGRESSION_BASELINE、RISK_REGISTER，並對照 source、caller、Git、tests 及合成安全反例。十份文件各有日期；舊 friction/Hermes/baseline 的診斷不自動代表現在仍存在。

### Overall architecture health

**YELLOW；generated skill 啟用、不可信 patch checks、自動 release／資料回退為局部 RED。** RT 演進仍朝原方向：native tool pairing、整批 barrier、run/proposal ownership、bounded cancel、journal readback、catalog、history hydration、context budget／extractive summary、Rust scoped read/list、idle memory digest 都有實際 caller。**RT-011 summary、RT-013、RT-015 的已完成有界切片保留，不再延期或重做。** 新概念應延伸這些邊界，沒有換 Core、Live2D 或新增平行 runtime 的必要。

新反例在既有 T22／T31／T32 helper，而非已證實某個 RT 引入的 regression。它們尚未作自主產品接線，現在可以用小修復恢復 invariant；不能因元件測試 green 就讓 SIRO 自行執行或部署候選。FIX-007／008／009 **PLANNED，尚未修復 production**。完整狀態：[唯一 T1–T40 矩陣](ROADMAP_RECONCILIATION.md)、[本輪現況](CURRENT_ARCHITECTURE_AUDIT.md)、[能力表](CAPABILITY_MATRIX.md)。

### Recent improvements

| 現況 | 價值與界線 |
|---|---|
| RT-002／003／005／008 與已驗 FIX | 已有 native messages、batch barrier、exact proposal ownership、terminal fence、owned child cleanup、unknown readback；不重造 journal／executor，不盲目重播 |
| RT-007／009／010／012／014 | 同 catalog 驅動 schema/handler/readiness；candidate 單 provider retry 已接；canonical completed dialogue 可恢復；browser 可 session fill/click；明確 remember/correct/delete 有來源與 privacy gate |
| RT-011／013／015 | extractive summary 保留 pending/goal、最終 budget guard；Rust UI/model read/list 有 scope caller；single-owner MemoryOrganizer 做有來源可丟棄 view、前景取消，不自動寫人格 facts |
| FIX-003／004 | 已有 provider completion 與 session/control lifecycle 修復證據；不是本輪新修，不因此解除搜尋／理解／語音全部產品 gate |
| RI-001 開發期 Codebase Memory | 真 local stdio MCP 查詢／索引已驗：250 files、3,092 nodes、16,700 edges；source-only projection、clean env、無網路、watcher=false，mutation tools／source writes 拒絕。與 Agent Memory／Runtime State 分離，不進正常 runtime；目前 chat catalog 未 hot reload 不冒稱直接出現新 tools |

### Architecture drift found

| 發現／分類 | 實際證據 | 最小處置 |
|---|---|---|
| 技能批准身分與 executable package 脫節；IMPLEMENTATION_BUG／BAD_INTERFACE／TEST_GAP | `src/siro/core/skills.py:65` 只 hash manifest+兩 schema；`src/siro/adapters/skill_worker.py:138` 只查 id/version enabled；合成換 plugin 碼 hash 不變且到 recording supervisor | FIX-007；完整 package identity／dispatch revalidation，保留 registry/worker，不新增 registry |
| Patch protected-path 判定漏 delete；IMPLEMENTATION_BUG／TEST_GAP | `src/siro/core/evolution.py:84` 只取 `+++ b/`；同時刪 authorization fixture 並改 calc，verifier 回 passed，reported paths 漏刪除 | FIX-008；完整 changed-path parser＋delete fixtures；未重現 rename 細節維持待驗，不只擴黑名單 |
| source copy 被誤當執行隔離；BAD_INTERFACE／MISSING_INTEGRATION | `evolution.py:49,100` temp copy 與同 user subprocess；候選 import 可寫 copy 外合成 marker | RI-003 真 OS/env/network/resource/descendant gate；保留 copy 作 workspace，現階段僅可信 developer checks |
| release 相容欄位不在簽章；IMPLEMENTATION_BUG／BAD_INTERFACE／TEST_GAP | `src/siro/core/releases.py:103` HMAC 只簽 version:digest；不重簽修改 max_schema，原不相容 bundle 仍 activated | FIX-009；canonical 完整 signed manifest，沒有真部署事故證據，不猜成 regression |
| release pointer／資料生命週期尚未接成產品；MISSING_INTEGRATION／TEST_GAP | launcher 不讀 active.json；`releases.py:95` 整 DB restore；現 release test 回到較新寫入前狀態 | RI-005 分別驗真啟動版本、stopped writer、code rollback 保最新資料；不把整 DB 還原當普通 source rollback |
| capability 宣告／權限範圍分散；TECH_DEBT／BAD_INTERFACE | `ToolDescriptor` metadata 不完整；`integrated.py:789` 風險特判、`:443` 固定能力宣告；Rust scoped read/list 與 Python argv 是不同 enforcement paths | RI-002 唯讀 inventory／真實 unknown；metadata 不作 grant，不為統一圖面改權限或搬全 Rust |

反例與已確認根因見[安全報告](../evidence/RI-architecture-2026-10-09/REPORT.md)。**反例中的 passed/activated 是缺陷重現，不是修復通過。** 無證據顯示本輪新增 Core→具體 provider/device import cycle 或 bypass compatibility boundary；原 251 個 source/tests/locks hash 零變。這是限定檢查，不能當全系統無循環依賴證明。Gateway／Integrated 的集中組裝與 Core evolution/release host I/O 是既有債；未找到必須大拆 subsystem 的根因。

### Migration quality／Technical debt introduced

本輪只新增開發工具、隔離設定、測試與必要文件；**沒有 runtime schema／API／grant／模型／聲線／Live2D migration**。開發 MCP 可獨立停用、重建可丟棄 index，Codex 設定 disable→restore 已實驗，不重啟 SIRO、不還原私人 DB。existing feature switches 仍是 drained startup 邊界；candidate/legacy 保留明確 compatibility 用途，尚不宜刪除。

半新半舊的風險在「元件存在就被當產品可用」：SkillDispatcher／ProactivityRules／PatchVerifier 無 Gateway 產品 caller，ReleaseManager 為 CLI；它們不是應刪死碼，也不是已完成自我進化。ToolCatalog／SkillRegistry／DeviceRegistry 分別負責可調用能力、安裝版本、已配對設備，不是三個重複 registry。

新增開發債僅限 pinned Codebase Memory binary、source projection／index freshness、Linux bubblewrap 配置與人工刷新；固定來源/checksum不等於供應鏈 attestation，graph inference 仍須 source/tests 核對。watcher 保持關閉；不把此開發 sandbox 的證據轉移成 generated skill/patch sandbox 已完成。retention／single-owner 擴張、mutable composition callbacks 與 env/JSON 分立繼續列債；無新反例前不為消債重構。

### Regression risk changes

本輪基線 **671 passed／5 real_provider deselected／3 warnings，156.91s**；加入開發工具驗證後 **701 passed／5 deselected／3 warnings，147.01s**。Rust **6 passed**；Ruff check／269 files format、mypy **204 files** PASS。這不是效能比較；新增30個開發工具案例不增加產品能力。[before](../evidence/runtime-intelligence-2026-10-09/full-suite-before.log)、[after](../evidence/runtime-intelligence-2026-10-09/full-suite-after.log)、[保留／回退](../evidence/runtime-intelligence-2026-10-09/preservation-and-rollback.json)。本代理另有140個離線窄測，與全套重疊，不相加當更多覆蓋。

| Subsystem | 風險變化／保留 baseline | 新增盲區或解除條件 |
|---|---|---|
| native/batch/cancel/history/memory | 舊 F01/02/03/07/08/09/10/11 與 AR-06/07 的原缺口已解；保留回歸，不重開同缺陷 | snapshot/metadata非完整健康；source已驗不證真provider長時品質 |
| Skill／patch／release safety | 風險由「元件有測試」提升為具體接入 RED | FIX-007換碼/依賴/dispatch，FIX-008 delete/rename/格式拒絕，FIX-009 schema tamper；另驗候選 OS sandbox 與資料保留回退 |
| 語音 | 完整性/owned取消有歷史改善，速度與人耳品質仍高風險 | FIX-005仍PARTIAL：首段約22.446s／暖RTF約1.75；本輪未GPU合成/真人聽驗，不重宣語音完成 |
| 搜尋／理解 | FIX-002／006保留 | Bing ScopeViolation整體根因及對話品質根因仍不可猜；需最小可重現輸入／安全reason code／合成多輪對照 |
| 開發 MCP | local RPC/無網路/唯讀/排除來源驗證降低外送與誤改風險 | source freshness、動態callback／註冊漏判；圖譜疑似死碼禁止自動刪除 |

8026 `/health/live`、`/`、`/live2d/` HTTP200，既有服務未重啟；這僅 readiness，**不是人眼WebGL、真互動、GPU、人耳、實體設備、第二節點、遠端CI或24h驗收**。251個既有檔案hash與locks不變，私人資料未讀。原 baseline invariants 仍有效；舊 193PASS/1FAIL 報告保存為歷史，不能作今日測試結果。

### Roadmap adjustments／New blockers

| 決定 | 範圍與理由 |
|---|---|
| KEEP | RT-001–015已完成切片與FIX-003/004；RT-011 summary、013、015不重新DEFER。保留所有T/RT號與歷史證據 |
| REORDER | 只在相關promotion前插既有FIX-002/005/006、新FIX-007/008/009；不是全roadmap停工或重排名 |
| SPLIT | skill package invariant、候選sandbox、批准/enable；release簽章、launcher、資料保留回退各自驗收，沿新RI小卡，不混成大重構 |
| MERGE | 無須合併原卡；相同source inventory/graph沿RI-001，不再建第二矩陣／memory graph |
| DEFER | 未經真隔離/批准的候選執行、autodeploy、無具體caller的跨provider/多owner擴張、未授權硬體與反編譯；不是取消其產品需求 |
| CANCEL | 沒有整張原T/RT需求被證明不再需要；僅排除重做已解journal/restore/summary/Rustcaller及平行framework的重複子工作 |

**BLOCKED_BY_FIX：FIX-007** 限 generated skill activation／executable catalog；**FIX-008** 限自動patch checks/protected-path promotion，另需RI-003；**FIX-009** 限release promotion，另需RI-005與人工批准。唯讀metadata、提案、產品語音/搜尋局部修復、合法動作素材可依各自gate繼續；不能讓後續執行者把新增安全反例當已修。[詳細FIX](FIX_REGISTER.md)、[原號碼roadmap與RI小卡](RUNTIME_EVOLUTION_ROADMAP.md)。

### Freeze zone changes

| Zone | 目前範圍 | 調整與規則 |
|---|---|---|
| GREEN | docs／dev code graph、已驗native pairing/journal/generation/來源不變量 | AR-06/07不再保持舊RED；保留回歸，沒有新缺陷不再重構 |
| YELLOW | ToolCatalog metadata、provider/context/browser組合、既有trusted skill worker、memory organization ownership、Web body/語音/產品配置 | 局部變更需真caller/明確scope；HTTP200不升GREEN，單owner不推論多Gateway |
| RED（新接入gate） | generated skill enabled identity、untrusted patch checks、release compatibility/autodeploy/DB restore | FIX-007/008/009與RI-003/005未驗前不得擴權；只准窄修復/隔離驗證 |
| RED（維持保護） | immutable Identity／affect與relationship原則、既有schema/grant wire、licensed Live2D資產／實體firmware | 不為新概念改動；正式需求若涉及，先獨立契約/授權/驗收，不等於永不開發 |

### Hermes relevance

只重新對照既有固定 Hermes snapshot，未宣稱查驗新版本或執行其runtime。

- **REUSE** SIRO已落地的native transcript/batch、catalog readiness、retry、取消、journal、bounded restore、summary、browser lifecycle；它們已解原gap，不從Hermes再搬一份。
- **REJECT** framework replacement、平行registry/memory/vector DB/scheduler/router、為七層圖建立七個service、把Codebase Memory當人格記憶、工具discovery自執行／自授權。
- **DEFER** 更一般semantic memory consolidation、無caller的多provider／multi-owner、網路技能自動安裝與發布、逆向工程全套依賴；具體需求與安全收益成立才擴充。已完成extractive summary／Rust read/list／idle digest不在此DEFER內。

### Recommended next 3 RT tasks（既有卡續作，不排名）

- **RT-007 → RI-002：**同一ToolCatalog補真實有界唯讀能力說明與unknown；不改執行／授權語意，不新建registry。
- **RT-012 → FIX-002：**重現搜尋ScopeViolation並保留安全可判讀原因，驗乾淨公開查詢端到端；不先放寬origin，不重寫session。
- **RT-006 → FIX-005：**沿既有聲線／單owner完成已量測語音瓶頸的窄驗證與真人首尾／自然度驗收；owned-worker lifecycle DONE保留，速度／C切片不假裝完成。

三項可依各自依賴安排，沒有先後排名；FIX-007/008/009並列為相關自主能力的前置修復，不改原RT歷史或要求Sol跳過gate。沒有新反例的已解問題標KEEP—NO CHANGE REQUIRED。

---

## 2026-10-07／10-06 歷史 review（不覆蓋上方現況）

> 2026-10-07 產品驗證補充：正式入口已接真實模型與單一 Haru；修復表情投影／連線 ownership、HTTP 回覆復活 turn、多提案顯示、空模型回覆及偏好來源隱私邊界。整體仍 YELLOW：本機閉環可用，真實 provider 偶發 continuation 錯誤根因未確認，語音口型／長 soak／發布門檻仍需驗證；不重構已解決的 RT 切片、不改 RT 編號。見 [本輪證據](../evidence/companion-experience-2026-10-06/REPORT.md)。

> 2026-10-06 後續狀態：本 review 保存審查當時證據。AR-06/07 已由後續修復解除；使用者之後授權 RT-013/015/011 summary，三項有界產品切片已交付。最新範圍、限制與 437 項回歸結果見 [交付報告](../evidence/runtime-product-2026-10-06/REPORT.md)。不把本頁歷史 DEFER／阻擋當成目前狀態。

日期：2026-10-06（Asia/Taipei）；程式與測試檢查於 10-05 開始。範圍：RT-001–014 的現有工作區，以最近完成的 RT-009/010/011/012/014 與三項 FIX 為重點；RT-013/015 尚未實作。包含未提交變更，不能只用 HEAD 代表被審查版本。本輪僅更新 review／證據／STATUS，未修改 production code。

## Overall architecture health

**YELLOW：方向仍符合原設計，但 native context budget 與既有多工具 batch 的相容性未成立，不能把各卡 DONE 合併解讀為完整 runtime 驗收。**

Core、provider、工具執行與設備的主要邊界仍在；近期變更有實際 caller，沒有為模仿 Hermes 新建整套框架。持續 browser、受限 history restore、明確 memory ingress 均可保留。已解決的 journal identity、failed generation dispatch、取消 ownership 不應再重構。

新的問題主要是跨卡契約：RT-003 允許多工具 batch，RT-011 的預設 native guard 卻不能計算該 batch 留下的訊息。效果已完成後，下一輪模型請求失敗。另一個問題是 native 測試的資產準備未接入乾淨 CI。兩者需要局部修復／驗收，不足以支持重設 SIRO。

### 證據與限制

- 已對照 CURRENT_ARCHITECTURE_AUDIT、CAPABILITY_MATRIX、ARCHITECTURE_FRICTION_MAP、HERMES_GAP_ANALYSIS、RUNTIME_EVOLUTION_SPEC、COMPATIBILITY_PLAN、MIGRATION_PLAN、RUNTIME_EVOLUTION_ROADMAP、REGRESSION_BASELINE、RISK_REGISTER，並檢查近期 scoped patches、code、決策與測試。早期文件代表設計意圖，不代表目前完成度。
- [舊 review 歸檔](verification/architecture_review_2026-10-05/previous-review.md)保留 10-03 結論；下列狀態取代其未修復判定。現有 [FIX_REGISTER](FIX_REGISTER.md) 的三項 DONE 有實作支持。
- [來源指紋](verification/architecture_review_2026-10-05/source-digests.json)記錄本次版本；[完成證據指紋核對](verification/architecture_review_2026-10-05/completion-digest-check.json)中近期證據覆蓋的 26 個檔案全部一致。這不是全工作區已提交或所有行為皆通過的證明。
- 本輪七組專項：**81 passed、3 warnings、23.98s，exit 0**；ruff PASS；mypy PASS（184 files）。命令見[驗證紀錄](verification/architecture_review_2026-10-05/README.md)。本輪未重跑 full suite。
- RT-014 歷史 full suite 為 **426 passed／5 opt-in skipped／3 warnings**；不將 skipped 或歷史測試列成本次實測。先前 FIX 驗證紀錄保留，沒有重新宣稱執行全部 FIX 測試。
- [組合探針](verification/architecture_review_2026-10-05/probe.py)使用合成模型、真 Core／Integrated／SQLite／orchestrator 與 native counter；副作用為測試 list，資料在暫存目錄。未呼叫真 provider、操作私人 DB 或重啟服務。
- 未驗證 remote CI、實際部署 rollback、GPU／真人 GUI、硬體、長時間 soak。本機既有 tokenizer cache 可用，不等於 clean checkout 可重現。

## Recent improvements

| Task | 已證實的演進 | 保留界線 |
|---|---|---|
| FIX-001 | generation 成功才接受 dispatch batch；失敗時部分 calls 僅供 audit | 不再重開 failed-generation 派送缺陷 |
| RT-003-FIX-01 | 內部 proposal UUID、journal ownership／binding 與 run-scoped dedup；provider call ID 保持原值 | 不新增第二套 tool identity |
| RT-005-FIX-01 | candidate handlers 納入 task ownership，取消 bridge 與 bounded cleanup；無法確認時明報 unknown | 不以 timeout 自動重送有副作用操作 |
| RT-009 | FailoverModel 有界 attempts；看到 tool intent 後停止 retry，cloud 額外嘗試需明確 budget | main 仍可只有一個 backend；不是已完成多 provider 自動切換 |
| RT-010 | 同 session／privacy 的最近六組完成 user＋final assistant pairs，以 native roles 還原；fresh system | 不還原工具執行、不 replay；十二則訊息不等於十二個 run |
| RT-011 | 獨立 JSON UTF-8 byte guard、pinned GPT-OSS native profile、output reserve 與 fail-closed | budget 成果保留；summary DEFER；多工具續作相容性見 AR-06 |
| RT-012 | trusted ExecutionContext 擁有 session browser；epoch＋DOM fence、cap 8、TTL 300s、action 30s、close／cancel／shutdown | ephemeral single-Gateway；origin change reset；不是 credential persistence |
| RT-014 | 明確 leading remember:/記住：寫入有來源 episodic statement、same-event idempotence；既有 correct/delete/revision | 不把 tool output 當 fact；candidate cloud recall 要求所有來源 cloud_allowed |

主要證據入口：[RT-009](../evidence/RT-009/REPORT.md)、[RT-010](../evidence/RT-010/REPORT.md)、[RT-011 native completion](../evidence/RT-011/token-completion/REPORT.md)、[RT-012](../evidence/RT-012/REPORT.md)、[RT-014](../evidence/RT-014/REPORT.md)。

## Architecture drift found

### 已關閉的舊問題

AR-01（identity scope）→ RT-003-FIX-01；AR-02（arguments-only handler cancellation）→ RT-005-FIX-01；AR-03（failed generation dispatch）→ FIX-001：**CLOSED，保留原設計及測試**。新的 native failure 不代表 AR-03 復發：這次工具來自成功 generation，失敗發生於後續 request。

### AR-06 — native guard 與多工具 batch 契約衝突

**REQUIRED_FIX／HIGH；BAD_INTERFACE + REGRESSION；來源 RT-011 × RT-003。**

- Evidence：`src/siro/services/agent/native_context.py` 的 `GPTOSSBudget.count_input` 對單則 assistant message 的 `tool_calls` 長度 > 1 拋出 `ContextBudgetUnavailable`。`gateway.py` candidate 預設啟用 native guard。Integrated 接受多工具 batch，Conversation 保留其 native assistant／tool transcript，再進 guard。
- [同一組合探針結果](verification/architecture_review_2026-10-05/probe-result.json)：native 關閉時 provider calls=2、effects=2、run completed；啟用時 provider calls=1、effects=2、run failed，錯誤為 ContextBudgetUnavailable。
- Expected：合法且已接受的多工具 batch 完成後，可在 budget 內繼續生成；不能因自身產生的合法 transcript 而失去續作能力。
- Root cause 已確認：counter 支援的 message shape 小於 executor／conversation 的合法 shape。既有 native tests 明確驗證拒絕 multi-call，batch tests 又未組合 native guard，因此單卡 green 無法證明相容。
- 影響：預設 candidate 的多工具閉環驗收阻擋。沒有證據顯示工具被重播或未授權執行；修復也不得重送已完成效果。
- 最小方向：在 RT-011 邊界修正可驗證的 counting／支援 shape 契約，加入實際 batch continuation 回歸。若暫時無法支援，必須在接受效果前明確處理能力限制，不能靜默關閉 guard 或把合法 batch 改寫成假 user 訊息。不要重寫 Core／executor／journal。
- 決策：保留 budget 子項完成證據；**RT-011「與既有 batch 的完整整合」應視為 PARTIAL**，不可宣稱整體 native rollout 完成。本輪只提出 review 建議，不改寫原 DONE 歷史。

### AR-07 — native 測試依賴未 provision 的本機資產

**REQUIRED_FIX／MEDIUM；MISSING_INTEGRATION + TEST_GAP；來源 RT-011。**

- Evidence：`tests/integration/test_native_context_budget.py:30` 指向被忽略的 `.siro-data/tokenizers/gpt-oss-20b`；測試無條件建立 GPTOSSBudget。`scripts/setup_context_tokenizer.py` 提供 pinned／hash-checked 安裝，但 `.github/workflows/check.yml` → `scripts/check` 只有 dependency sync 等步驟，未執行資產準備。
- Expected：乾淨 checkout 的正式 gate 能重現 native 測試；缺資產時可明確定位 bootstrap 問題。
- Actual：本機測試利用預先準備的 cache；CI 定義未滿足此先決條件。這是靜態已確認的整合缺口，**不是已觀測 remote CI failure**。
- 最小方向：將既有 pinned setup 接入正式驗證入口，或提供等價、可驗證的測試資產機制；在乾淨環境驗證。不得用 skip 掩蓋正式 gate，亦不需新增 runtime 自動下載。

### 其餘边界判讀

- 未發現近期變更新增 Core → OS／具體 provider 依賴、tool → device 越界或新的 import cycle。Gateway／Integrated 既有局部循環接線不等於新發現循環；本次不是全 repo 形式化依賴證明。
- FailoverModel 對 OpenAICompatibleAdapter 的具體型別與私有 tool-intent exception note 有耦合，但仍在 adapter 層，且實際防止重試已出現工具意圖的串流。列 TECH_DEBT，沒有第二個必要 caller 前不要建通用 retry framework。
- GPTOSSBudget 位於 services/agent 並接收 payload builder；Core port 未綁 tokenizer。此部署特定 profile 有價值，暫不抽出多 provider tokenizer registry。
- BrowserSessions 包住 ScopedBrowserDriver，沿用 trusted context 與 dispatch policy，未建立第二套 runtime journal。mutable hook／shutdown callback ownership 仍依賴 single owner，不代表支援多 Gateway。
- candidate memory cloud filter 是必要相容邊界。原始 user request 依選定 cloud route 傳送，與禁止 local-only retained memory 被 recall 外送是不同路徑；沒有把前者誤報為 RT-014 新洩漏。

## Migration quality / Technical debt introduced

整體仍 incremental：feature switches 在 startup 固定、舊入口仍可選、近期這批工作未新增 013 之後的 schema migration。恢復 conversation 不 replay，browser 不持久化 credentials，memory ingress 復用 existing repository／revision，沒有雙寫第二套 state store。

但「可切回」有邊界：需 drained restart、關閉 owned browser、保留 journal／memory revisions；停 ingress 只停未來寫入，不撤 cloud recall privacy filter。不應以切回 legacy 當成新 safety invariants 仍成立的證明。歷史 isolated rollback fixture 不等於真部署 rollback rehearsal。

| Debt / 限制 | 判斷 | 退出條件／目前處置 |
|---|---|---|
| AR-04：terminated/run/proposal/active 等索引及 SQLite journal 保存 | TECH_DEBT；seen-call 已改為 run 清理，不重報舊 identity bug | 量測長時間 retention／owner cleanup，再定局部清理；RT-015 前是 gate |
| AR-05：repository／mutable callbacks 的 single-owner 接線 | TECH_DEBT | 維持單一 Gateway owner；有實際 multi-owner 需求才拆分 |
| 新 switches／profile readiness 未完整出現在 `/v1/runtime` | TECH_DEBT + DOCUMENTATION_DRIFT | endpoint 尚未涵蓋 retry/restore/native/assets/browser/ingress 的 effective state；補診斷需求，不順便合併 JSON settings |
| 舊 legacy／candidate 雙路 | 有明確 rollback 用途，暫不移除 | 完成選定 provider 閉環、組合 baseline、部署回滾才另審移除；無證據表明現在該刪 |
| native tokenizer／Jinja 資產與依賴 | 有實際 guard 價值，新增部署成本 | AR-07 接入 provision；保持 pinned hash，不擴張 profile 清單填滿 roadmap |
| browser disconnect 走 idle TTL | 已揭露限制，非假裝即時釋放 | shared WS 缺 canonical owner mapping；先量測 cap／TTL，避免發明新連線 owner 系統 |

native 預設只接受已 profile 的 Groq GPT-OSS 路徑；其他 model／local Ollama／缺資產 fail closed，可能讓原可聊天設定停止生成。D28 已明定限制，因此不是未知實作錯誤，但**不能再聲稱所有原 provider 設定均透明 backward compatible**。應將 supported profile、effective flag、缺資產診斷納入 rollout acceptance；禁用 native 是明確安全能力取捨，不是功能等價修復。

## Regression risk changes

REGRESSION_BASELINE 原有 identity、取消、journal、compatibility 與禁止 replay 等 invariant 仍有效；原先的 case 集合不足以代表近期組合行為。既有驗收保留，不降低門檻或把 warnings／skip 改稱 pass。

| Subsystem | 風險變化 | 必要驗證／盲區 |
|---|---|---|
| Tool identity／failed generation／cancel | 已下降 | 保留三項 FIX regression，不再重構 |
| Native budget × batch × retry | 上升，AR-06 已重現 | batch effects 恰一次、guard 下第二次模型 request 成功或安全的預先拒絕契約、錯誤不觸發效果重送 |
| 資產／乾淨安裝 | 上升，AR-07 | empty checkout cache 的正式 check；missing／corrupt hash 仍 fail closed |
| Restore × privacy × memory revisions | 專項已通過，組合風險待補 | 同 session correct/delete/restart＋fresh request；不得從已刪 memory recall，但 raw dialogue history 仍可能保有原文；不是全資料抹除 |
| Browser pool | lifecycle 專項改善；session 範圍擴大 | cap／TTL 長測、A session cleanup failure 對 B 的可用性；目前 cleanup failure 可關閉整個 pool，屬明確 fail-closed availability 代價 |
| Native counting cancellation | 不確定 | to_thread 取消可阻止後續 dispatch，不能保證已運行 CPU thread 被終止；需併發／取消壓力資料，未證實 leak |
| Retry | 有界 attempt 降低風險 | tool-intent 後不 retry；main 單 backend 的證據不可推論成 provider failover soak |

RT-011 歷史兩個合成 Groq probe 的 reference/server 差值落在 256 margin 內，只支持該樣本，不足以證明所有 server framing 的上界。

## Roadmap adjustments

本表是 review disposition，不改 RT 編號、不修改歷史完成證據，也不建立新 feature task。

| RT / slice | 決定 | 依 reality 的理由 |
|---|---|---|
| RT-001–008 與三項 FIX | KEEP 已完成成果 | 舊問題已解決；取消任何「再造 journal／重新修 identity」的重複工作需求，不取消原任務歷史 |
| RT-009 | KEEP | bounded retry 已有 caller；不需為名稱再造多 provider router |
| RT-010 | KEEP | 六組 raw history 已解决 bounded restore；無需再建 conversation storage |
| RT-011 budget | KEEP + REORDER 局部修復驗收 | AR-06/07 先於擴大 rollout；完整整合 PARTIAL，不作通用 tokenizer 重設 |
| RT-011 summary | SPLIT 範圍、維持 DEFER | budget 與 summary 不同；前者完成不強迫實作後者。不另編 RT 號 |
| RT-012 | KEEP 成果 | 下一步只驗證 cleanup isolation／長時 ownership，不新增 persistence abstraction |
| RT-013 Rust scoped backend | DEFER | 真 caller／契約 parity 前提仍未滿足；沒有證據說永遠無需，所以不擅自 CANCEL |
| RT-014 | KEEP 成果 | explicit sourced memory 已完成；不改成自動知識抽取 |
| RT-015 background pump | DEFER | RT-014 依賴已解，但 retention／single owner／idempotent lifecycle gates 未解；不能沿用舊「等待 RT-014」理由，也不能自動啟動 |

**MERGE：無需要合併的剩餘卡。CANCEL：沒有足夠證據永久取消 RT-013/015；已解問題的重複重構與額外 framework 工作直接排除，不為湊進度新增卡。**

## New blockers

- **BLOCKED_BY_FIX（AR-06）：**native enabled 的多工具 runtime rollout、任何依賴該組合的後續 acceptance。RT-003 功能本身保留；不可讓後續工作假定組合已可用。
- **BLOCKED_BY_FIX（AR-07）：**native clean-checkout／CI reproducibility gate；本機 green 不解除此阻擋。
- 非 native 路徑的獨立 review／測試可繼續；不因此解除 RT-013/015 各自 DEFER，也不擴大 freeze 到整套 SIRO。
- 真 provider 完整工具閉環、部署 rollback、長時間 retention 仍為既有 release gates；不是本轮已觀測的新 production failure。

## Freeze zone changes

| Zone | 現況 | 規則 |
|---|---|---|
| GREEN | native roles、journal ownership、generation gate、bounded execution 的已修復局部 invariant | 保持並允許局部 regression；不再抽象化 |
| GREEN | 明確來源 ingress 的 marker／event idempotence 邊界 | 保留；不擴展為自動 fact extraction |
| YELLOW | restore/privacy/memory 組合、browser session pool、retry coupling、effective configuration | 可進行有界驗證與局部修補；不要新增 owner／持久化框架 |
| RED | default native guard × multi-call continuation；clean CI native gate | 限 AR-06/07 修復與驗證，暫停依賴其完成的擴張 |
| RED（維持） | Identity／affect／relationship 原則、硬體政策、無證據 Rust 替換及 background autonomous effects | 本輪無證據支持解凍；不觸碰 |

GREEN 代表該局部責任邊界可保持，不是全產品可發布。

## Hermes relevance

以既有 HERMES_GAP_ANALYSIS 的概念對照現況，沒有重新查驗外部 Hermes 版本或新增其能力主張。

- KEEP 已落地且有 caller 的 native tool transcript、bounded execution、catalog、journal、bounded history、browser lifecycle；不需要導入 Hermes framework。
- DEFER summary／compression：先解原始 transcript 的 native guard 相容性，不能用摘要遮住合法 multi-call shape。
- DEFER background queue/pump 與更一般 memory consolidation：明確 sourced ingress 已解最初寫入缺口，未證實需要自主提煉。
- REJECT 為對齊參考架構而新增 parallel registry、第二套 memory store、通用 tokenizer/router framework 或自動 replay；現有 port／repository 已有足夠責任邊界。
- DEFER Rust scoped backend：以真 caller 和 parity 決定，不以 roadmap 已列入作理由。

## Recommended next 3 RT tasks（不排名）

目前沒有三張符合條件的全新 feature RT 卡。以下是三個既有 RT 的有界續作範圍，不另編號、不假裝 RT-013/015 已解除 DEFER：

- **RT-011：**處理 AR-06/07，補 default native＋多工具閉環及 clean-checkout gate；保留 byte/native guard，summary 不加入此範圍。
- **RT-012：**驗證 pool cap／TTL／cleanup failure 對其他 session 的影響；僅有反例才局部修補。這是驗證 follow-up，不撤回已完成的 session 功能。
- **RT-014（連同 RT-010）：**補 correct/delete/restart／restore／cloud privacy 的組合 baseline，明確區分 memory recall 與 raw history retention；不新增資料清除或自動 memory 功能。

三者不構成優先序；依賴 native guard 的驗收需先解除 AR-06/07。修復任務詳細定義與 production implementation 不在本輪 review 範圍。
