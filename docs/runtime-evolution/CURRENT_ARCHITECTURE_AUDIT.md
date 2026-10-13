# SIRO V2 現況稽核

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

## 2026-10-11 strict worker 現況

D46新增developerexplicitprofile實際caller：現有WorkerSupervisor→completecapture frozenpackage／canonicaltypedmetadata→sharedlowerprocessowner→RI-003共用minimalbwrap／trustedrestrictions→fixedplugin.run→boundedJSON/schema／cleanup。Core不importOS，adapter無service逆向依賴；patchprivatefacade／原runner主流程/defaulttrusted/D45/Dispatcher保持。同一sandboxpolicy与processowner，不創另一套。51新cases／完整1,202PASS／exact7回退支持限定VERIFIED。[證據](../evidence/RI-004-worker-2026-10-11/REPORT.md)。目前產品仍只有D44待審入口，沒有ownerinstall-enable-revoke／enabledchatcaller；下一切片按此實碼接入，不能把測試PASS當批准。

## 2026-10-10 RI-004 現況更新

當前已接explicit-owner固定template候選與待審UI：Gateway兩個owner-onlyPOST與唯讀runtime/snapshot metadata→SkillCandidatePreparer(single owned job)→ToolCatalog.capture全typedinventory→capture_skill complete bytes→RI-003 verify_isolated_patch→review/export。三個production範圍（Gateway/index、新service）；Core、ports、registry/worker、model、memory/DB/locks不變。88新cases／1,127full／真Chrome23checks／exact6回退支持局部切片。[驗收與回退](../evidence/RI-004-2026-10-10/REPORT.md)。

下方「尚無skill產品caller」為原時點快照：現已有candidate prepare/review caller，仍沒有SkillDispatcher enabled產品caller／procedural repeatedtrace intake／registrymutation/approval。ReportPASS固定installed=false/enabled=false/authorizes_execution=false；patchprofile不充當skillworker认证。本輪codebaseMCP未暴露，未假稱query/reindex，使用實際source/caller核查。

## RI-003 actual caller addendum — 2026-10-10

現在有實際 untrusted patch-check caller：`cli._verify_patch` → `services.tools.patch_verification.verify_isolated_patch` → Core pure `preflight_patch` → no-follow source projection／owned temporary Git apply → `execute_bounded_argv` → bubblewrap → 候選外 trusted stdlib runner → bounded report／cleanup。只有明確 owner CLI／async入口，沒有 model/Gateway／registry enable／release接線；Core不import具體backend。

Linux x86_64／system CPython3.14／stdlib synchronous unittest單程序profile已VERIFIED，RI-003整體PARTIAL。48新cases、111相鄰、1,039完整回歸及actualOS／SIGINT／精確回退；一般multiprocess/deps/aggregate kernel RAM與enabled worker仍須各自驗。舊PatchVerifier仍trusted-only；下方source-copy安全反例是它的原缺口，不能把新backend的PASS套到舊API。[驗收與限制](../evidence/RI-003-2026-10-10/REPORT.md)。FIX-007/008/009局部漏洞已由各卡修復，FIX-002/005/006產品品質與RI-004/005 integration gates仍保留。

## RI-002 completion addendum — 2026-10-10

ToolCatalog已加入同次readiness capture的typed唯讀metadata與safe reason；candidate首輪／續輪的model definitions與context同源，既有 /v1/runtime／UI已有真caller。下方當時metadata缺口已局部解決；未宣告的output/timeouts仍null，metadata不是grant。716 offline／15新專項／真Chrome13checks及temp回退通過；不改批准／DB／Core ports或接生成技能。詳 [RI-002 REPORT](../evidence/RI-002-2026-10-09/REPORT.md)。原FIX-007–009／sandbox／release integration與產品品質gate保留。


## 2026-10-09 現況增補（優先於下方 2026-09-30 歷史）

範圍：`main`，HEAD `c1d2d41b2afc8844ff46f328043f7d2e8bf3cabe` 加既有 dirty working tree。保留既有語音修復與使用者檔案。本節由 source、caller、測試與合成反例交叉核對，不把文件 DONE 當產品驗收。

**整體健康：可漸進擴充，產品與安全接入仍有 gate。** 原有 Core/ports/provider、SQLite、Web Live2D 與 ToolOrchestrator 可以沿用。RT-001–015 已處理多個原有缺口，沒有證據支持重做 native messages、catalog、summary、Rust read-only workspace 或 idle memory digest。尚不能把獨立 skill、proactivity、patch/release 元件當成已接通的自主 Agent。

### 真實技術棧與入口

- Python/FastAPI/asyncio/Uvicorn，Pydantic contracts、SQLite/FTS、HTTP provider、Playwright；`pyproject.toml:43` 的 `siro-gateway` 指向 `gateway.main`。既有 companion launcher 在 `scripts/launch_companion.py:11` 組裝並執行既有入口。
- `gateway.py:1118` 組裝 provider、body、ToolOrchestrator、IntegratedCompanion。candidate profile 在 `gateway.py:1159` 接 retry＋context budget；沒有新增競爭的模型 router。
- Rust `siro-runtime` 經 local RPC 提供 scoped read/list；`gateway.py:1468` → `WorkspaceRuntime`，不是所有 PC 命令都經 Rust。一般 `computer.execute` 仍是 `gateway.py:1390` → bounded Python argv。此兩種 scope 的存在有明確 caller，不要求強制搬到同一語言。
- Live2D 是既有 Web renderer：`gateway.py:512` mount 檢查、`index.html:48` iframe、`scripts/prepare_live2d_renderer.py:30` 與 `scripts/repair_companion_renderer.py:11`。預設 `static/body.html` 只作 fallback，不能當真 Cubism renderer。沒有重新引入 Unity 的理由。
- NATS、MQTT、HA、compute worker、skill worker 等模組存在，但 constructor/caller 不等於都在 Gateway lifespan 啟用。設備與 worker 的 L2/L3 證據分開看。

### 關鍵呼叫鏈（目前 source 行號）

| 使用情境 | 實際 call chain | 驗證與限制 |
|---|---|---|
| 文字訊息 | `gateway.py:727 create_turn` → `integrated.py:166 respond` → `core/companion.py:27 respond` → `core/conversation.py:90 respond` → `LanguageModel.stream` → delta callback → GatewayHub → `static/index.html` | candidate 已傳 native messages（`companion.py:77`）；HTTP accepted 與 assistant terminal 不應混為一個結果。文字品質與產品驗收仍由 FIX-006 處理 |
| 模型工具 | `integrated.py:472` accepted completed tool calls → `:755 _propose_tool_calls` → `ToolCatalog.require` → `ToolOrchestrator.propose/resolve/execute`（`orchestrator.py:481/503/537`）→ contextual executor → paired tool observation → `integrated.py:554 continue_after_tool` | run/call/proposal 與 args hash 綁定；journal 在 dispatch 前／observation 後記錄。不是第二個 dispatcher；不恢復重播未知副作用 |
| 記憶寫入／檢索 | 原 `UserTextEvent` → `integrated.py:374 MemoryService.ingest_owner_request` → `core/memory.py:125` → existing repository；檢索 `companion.py:46` → `MemoryService.recall` | 明確 owner「記住」才 ingress；不是所有對話自動推論成 facts。privacy 過濾在 request composition；更正／刪除 `gateway.py:918/953` 使摘要失效 |
| context／背景整理 | session journal 完成歷史 `integrated.py:181` → extractive summary／`ContextBudgetModel` 最終 guard；`gateway.py:1593` 建唯一 MemoryOrganizer → lifespan start／foreground cancel／shutdown | summary 與 digest 不新增 Memory DB；`organization.py:98` 限 100 sources／5s，輸出可丟棄 view、不寫 facts；不等於主動聊天或 task scheduler 已產品接通 |
| provider／工具失敗 | `conversation.py:139` 捕捉 timeout/provider error → TurnResult failed → `integrated.py:881 _finish_candidate` → cancel/discard/journal/terminal；tool executor error → `orchestrator.py:616` failed observation → continuation | 未正常完成的 tool intent 不 dispatch；UI partial text 不當完整語音。錯誤目前多保留 type，scope 原因／可操作診斷仍不足，不能猜 FIX-002 根因 |
| Live2D 狀態 | affect/expression → `integrated.py:360` set_emotion、`:490` completed speak → `MinimalWebBodyAdapter`（`adapters/body/web.py:118/102`）→ bounded single-writer transport → `/ws/body`（`gateway.py:997`）→ current Web renderer | attach 重送最後 emotion（`web.py:41`），不重播舊 speech。本次未做人眼 WebGL／全身走路驗收；現有 renderer 能力不能推出桌寵自由動作已完成 |

### 已解決問題與保留邊界

1. ToolCatalog 已提供同一來源的 schema、executor、availability 與 snapshot（`orchestrator.py:146–199`）。`gateway.py:1516` 檢查 kill switch／Rust process／browser executable，model tools 在每次 request 取可用 definitions。舊「沒有動態 availability」結論已過時；這不是完整 dependency health check。
2. native multi-call batching、terminal fence、bounded argv cleanup、session hydration、provider retry、memory ingress、summary/Rust/organizer 都有真 caller 與對應測試。保留現在的 compatibility profile，不因新研究再造 runtime。
3. FIX-005 的分段播放／EOS/cap/cancel 有歷史真 Qwen 證據，但首段 22.446s 與段間空檔仍未達體驗門檻，人耳驗收未跑。不能用完成協定取代聲音品質與延遲驗收。

### 架構 drift／技術債與明確缺口

| 發現 | 證據／影響 | 分類與最小處理 |
|---|---|---|
| 能力 metadata 不完整且風險描述分散 | `ToolDescriptor` 只有 name/definition/executor/availability/backend/effect；`integrated.py:789` 只特判 navigate+read，read/list/browser.read 未直接使用 catalog effect；`integrated.py:443` 固定宣告 mic/TTS/body | BAD_INTERFACE／metadata gap；先以 catalog 做唯讀 inventory，增加 version/provenance/output/failure/permissions；unknown 明示，不能當授權或執行健康證明 |
| skill code 與 enabled identity 未綁定 | `core/skills.py:65–74` 只 hash 三個 JSON；`adapters/skill_worker.py:138` 只查 id/version；合成 code mutation hash 不變且達到 supervisor | REQUIRED_FIX（接生成技能前）；補 package digest／immutable installed object／dispatch revalidation，不另造 registry |
| patch protection 漏掉刪除 | `core/evolution.py:84–95` 只讀 `+++ b/`；刪 authorization 加另一合法修改，合成 verifier 回 passed | REQUIRED_FIX；先完整 changed-path parser 與 delete/rename fixtures；不能只擴黑名單 |
| patch copy 被當成 sandbox 的風險 | `evolution.py:49` temp copy、`:100` same-user subprocess；合成 candidate import 能寫 copy 外 fixture | MISSING_INTEGRATION／BAD_INTERFACE（untrusted checks 隔離宣稱）／integration gate；只允許可信 developer checks；候選程式執行需 OS isolation、env/network/resource scope。copy 可沿用作 source workspace |
| release compatibility 未簽署且 DB rollback 可能丟資料 | `releases.py:103–113` HMAC 未含 schema bounds；合成未重簽 schema tamper 仍 activated；`:95–100` restore whole DB，既有 release test 會回復較新寫入前狀態 | REQUIRED_FIX（自動發布前）；canonical signed manifest、launcher consume semantics、stopped-writer／data rollback policy 各自小卡；保持人工維護，不接 Agent deploy |
| integration/composition 耦合 | Gateway 1705 行、IntegratedCompanion 1108 行，tools/providers/body/environment/lifecycle 匯集；`core/evolution.py`／`releases.py` 同時直接做 host I/O | TECH_DEBT；不按行數拆 class。只在下一項確定 caller 需要時局部抽純 metadata／composition，維持 Core ports |
| 主動／skills／proposal 未產品接通 | `ProactivityRules` caller 在 test/demo；SkillDispatcher 在 tests；PatchVerifier 在 tests；ReleaseManager 在 CLI。全 repo source caller 搜尋可重現 | MISSING_INTEGRATION，不判為 dead code／Duplicated；先重用、後以窄用途接入，不新增 scheduler／registry／executor |

沒有在 `src/siro/core`／`ports` 發現對 adapters/services 的直接 import（本次 `rg`）。這是局部方向檢查，不是全系統無循環依賴的證明；MCP graph 的 import/call inference 與動態註冊需交叉確認。`ToolCatalog`、`SQLiteSkillRegistry`、`DeviceRegistry` 分別負責產品可調用能力、安裝版本狀態、已配對設備，不能僅因都稱 registry 就合併或宣稱重複。

### 驗證、freeze 與下一步

本輪獨立窄測：**40 passed／9.49s／3 existing warnings**。4 類合成安全反例已重現；[命令、fixture 與原始結果](../evidence/RI-architecture-2026-10-09/REPORT.md)。主代理的全套與 MCP evidence 另外記錄；本節不冒稱真硬體、UI、provider 或 24h 已驗。

| 區域 | 現況 | 調整 |
|---|---|---|
| docs／開發期 code graph | GREEN | 可安全補盤點；不讀私人 DB、不掛 runtime MCP、不先開 watcher |
| ToolCatalog／現有工具／conversation／body | YELLOW | 有 caller/回歸保護；只改確定 metadata 或局部修復，語音／搜尋／理解 gate 仍存在 |
| Skill worker（既有可信 fixture） | YELLOW | 保留已驗 bwrap/network/env/resource path；不等於任意生成 package 安全 |
| generated skill 啟用、untrusted patch checks、自動 release/DB rollback | RED | 新反例形成接入 blocker；不擴 autonomous execution，先修 invariant |
| SQLite schema／identity／grants／Live2D licensed assets／實體 firmware | RED | 維持舊 freeze，不因整合新概念重寫 |

下一步依既有 FIX／新 RI 小卡執行；能力探索只讀 existing catalog，skill 生成只到候選，self-improvement 只到 proposal／審核 patch。完整整合設計見 [RUNTIME_INTELLIGENCE_DESIGN.md](RUNTIME_INTELLIGENCE_DESIGN.md)，逐項現況見 [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md)。這些文件不改既有 RT/T 編號，不把未接入功能標 DONE。

---

## 2026-09-30 歷史快照（下列結論不覆蓋上方現況）

日期：2026-09-30（Asia/Taipei）。範圍：目前 dirty working tree，HEAD `a27001d32349841002f3a5a02c97c18544f8ce40`，不是單獨 HEAD 的發布版本。

## 結論

SIRO 已有可組裝的文字、情緒、關係、儲存、語音與工具產品路徑，也有大量獨立可測元件。它尚不是一個完整接通排程、目標、Rust 執行層、設備與恢復機制的統一智能體。不能說 T00–T40 全部完成，也不能說它們都是空殼。

目前正式入口是 `pyproject.toml` 的 `siro-gateway` → `services/presentation/gateway.py:main`。`IntegratedCompanion` 在同一 Python 程序中承擔業務整合。Core 的 provider、memory ports 仍可保留。Rust 是獨立可啟動 RPC 程序，但 Gateway 的通用電腦工具直接啟動 Python subprocess，沒有走 Rust grant/driver 路徑。

## 證據層級

1. 本次閱讀正式入口、constructor、caller、executor、輸出 consumer，見 call graph 與 matrix。
2. 本次 Python 全套：193 passed、1 failed、5 skipped；Rust：6 passed。不能把 mock provider 和 simulator 算成真服務驗收。
3. 本次 `curl --max-time 3 http://127.0.0.1:8000/health/live` 連線失敗。沒有重啟使用者服務、呼叫付費 API、使用私人 DB 或進行硬體動作。
4. 舊 `docs/evidence/Txx` 與 STATUS 是歷史線索；本次未完整重演的實測不提升為 VERIFIED_COMPLETE。
5. `SOURCE_INVENTORY.json` 保存每個 Python source 的 SHA256、符號行號、import 與 Gateway 靜態依賴閉包。閉包可能包含未實例化的 imports，不能當成 runtime invocation 證據。

## 稽核前既有變更

原生 ModelMessage、兩 adapter serializer 與合約測試已在此稽核指令之前修改；目前 ConversationEngine 不傳 messages，因此屬 IMPLEMENTED_UNVERIFIED（產品接入未完成）。Qwen worker、migration 012、AgentRun integration 亦為既有未提交變更。此次不回退、不繼續實作。禁止將稽核文件當作完成這些實作的證據。

## 實際責任與 freeze zones

| 責任 | 現有承擔者 | 區域 | 依據及決定 |
|---|---|---|---|
| Character | core/affect、relationships、expression；IntegratedCompanion 組裝；Web body | YELLOW | 已接入、狀態敏感；修改需情緒/關係與畫面回歸 |
| Brain | cognition、goals、proactivity、affect/planner | YELLOW | 元件測試存在；Gateway 未實例化主要 planner，先補路徑證據 |
| Agent Runtime | ConversationEngine、IntegratedCompanion、ToolOrchestrator | YELLOW | 高耦合、取消與續作不完整，需端到端回歸 |
| Execution | Gateway closures、adapters/computer、Rust LinuxDriver | YELLOW | 新舊路徑並存，先定義能力與權限對照 |
| SQLite schema/identity/grant wire contracts | persistence、contracts、Rust RPC | RED | 資料與權限敏感；KEEP，除非 blocking issue |
| Live2D 資產與 ESP32 firmware | SDK 外部資產、firmware/esp32 | RED | 授權/硬體依賴；不因美化架構改動 |
| 稽核/測試證據文件 | docs/runtime-evolution | GREEN | 無 production caller，可補證據 |

## Python / Rust 邊界

| 責任 | 分類 | 理由 |
|---|---|---|
| AI、情緒、memory 邏輯、provider | SHOULD_STAY（Python） | 現有邊界合理；無搬移收益證據 |
| Rust grant ledger、Linux scoped driver、RPC | SHOULD_STAY（Rust） | 已有獨立測試，優先保留 |
| Gateway 內 argv process lifecycle | EVENTUALLY_MOVE | 意指透過既有 execution 邊界接入；不要求重寫成 Rust，需先證明取消/授權收益 |
| 系統級 supervision | SHOULD_STAY（systemd/現有操作工具） | 不必為語言分工自造 supervisor |
| MUST_MOVE | 無 | 本次沒有證據支持強制語言搬移 |

## 能力時序（非 migration 設計）

NOW：釐清產品基線、取消/工具觀測、TTS lifecycle、配置和測試差異。
NEXT：可恢復 session、工具可用性、現有 provider fallback 與 goal/scheduler 的有界接入。
LATER：真 ESP32/HA、第二節點、擴充 plugins、長期主動人格與硬體擴張。

Phase 1 到此只形成事實、缺口與最小修復候選。未建立 RT task，未開始 Phase 2。
