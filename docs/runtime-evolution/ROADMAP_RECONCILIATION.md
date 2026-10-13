# T1–T40 Implementation Matrix / Roadmap Reconciliation

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

## 2026-10-11 RI-004 strict worker 核對

D46限定worker切片VERIFIED：真fixed candidate執行、51新cases／完整1,202PASS／exact7回退；RI-004整體PARTIAL。[REPORT](../evidence/RI-004-worker-2026-10-11/REPORT.md)。**KEEP／SPLIT** next package-bound ownerreview/install-disabled/explicit enable/revoke/catalog；不再把已驗fixedOSprofile列missing，也不把未接chat/approval列DONE。不重編RT、不重新開已解決的卡；RI-005/006与產品品質gate維持。

## 2026-10-10 RI-004 接續核對

**KEEP RI-004，SPLIT activation gate**：D44 fixed template→typedexistingcheck→realverification→review/export已VERIFIED，整卡PARTIAL；下一窄切片獨立驗現有skillworker固定用途的bytes/OS/cancel/permissions，才能接package-bound securityreview／明確owner批准／registry與catalog／撤銷。沒有新registry／planner或重新編RT；不能因reviewPASS直接enabled。[驗收與回退](../evidence/RI-004-2026-10-10/REPORT.md)。

**KEEP RI-005** code/data rollback分離與singlewriter／launchergate；FIX-002／005／006產品品質仍PARTIAL，不被1,127PASS解除。**REJECT**泛用學習planner／第二executor／全域state；**DEFER**跨平台/dependency/multiprocessprofile到具體caller。這不改RT-011/013/015原DONE、不重新延期已實作RT。沒有新的reality evidence要求CANCEL既有RT；原不必要重構仍不做。

## 2026-10-10 RI-003 增量核對

T31對應RI-003現在有真owner CLI／async caller與Linux x86_64／system CPython3.14／stdlib單程序profile，這個有限切片VERIFIED；T31整體保持Partially Implemented。48新cases與111相鄰、完整1,039PASS／真OS及SIGINT／六檔精確回退。[報告](../evidence/RI-003-2026-10-10/REPORT.md)。下方copy verifier反例保留為舊trusted API限制，不作新backend已測能力的否定；general multiprocess/deps與actual enabled skill worker不在本卡認證。

FIX-007／008／009／010各自局部已VERIFIED，T22技能接入／T32 launcher與latest-data rollback仍独立gate；FIX-002／005／006產品品質仍PARTIAL。原T/RT編號与DONE不變；不以fullsuite或候選自己寫的test PASS當enable／deployment批准。

更新：2026-10-09（Asia/Taipei）。沿用既有 reconciliation 作唯一逐卡矩陣，不另建重複文件。對照 [TASKS](../TASKS.md)、[STATUS](../STATUS.md)、實際 source/tests、`docs/evidence/Txx/` 與 Git。基準 `main` / `c1d2d41b2afc8844ff46f328043f7d2e8bf3cabe`；先前 FIX-003／004／005 dirty source 均保留，本輪未執行那些修復。

**狀態評估原卡範圍，另列產品接線與驗證層級。元件已驗證不等於整體產品可用，也不表示必須立刻接線。** 原 T 編號、TASKS 與歷史 DONE 不變；本表不能替後續工作解除未滿足的安全／整合門檻。

## 狀態與證據規則

Current State 僅用：`Implemented and Verified`、`Implemented but Unverified`、`Partially Implemented`、`Planned Only`、`Missing`、`Deprecated`、`Duplicated`、`Unknown`。

- `Implemented and Verified`：本次重跑支持該卡的既有元件範圍，仍保留 L1／本機 SQLite 等邊界。
- `Implemented but Unverified`：來源及歷史證據存在，但本次未重驗其主要環境／research gate；這不是重寫要求。
- `Partially Implemented`：可用子元件存在，但整卡整合、安全或真實運作要求仍有缺口。
- `Planned Only`：整體驗收／發布只有計畫或阻擋報告，依賴元件通過不算成品。
- 沒有把任何整張 T 卡標成 `Missing`、`Deprecated` 或 `Duplicated`；目前證據不足以取消其原始需求。舊 provider、不同 permission 路徑與未接線元件的風險另列，不因此刪除整卡。

`F1/F2` 為下方本次離線合成重驗；`H:Txx` 為 `docs/evidence/Txx/README.md` 歷史結果，不能當本次真模型／硬體重跑。source/test 路徑以 repo root 為準，行號為本次閱讀位置。未接線判斷另核對啟動及動態註冊，沒有依圖譜疑似死碼刪除模組。

## T00 基線補充（不計入 T1–T40）

T00 原盤點存在，部分硬體、Git與部署條件已過期：Git 有 `5d83b05`、`a27001d`、`c1d2d41` 後續提交，不是「所有新工作仍未提交」。FIX-005 2026-10-08 報告已實測 RTX 3050 Laptop CUDA；2026-09-26「沒有GPU runtime」不能作現況。最終部署機／所有宣稱平台仍未因此驗收。新基線見 [CURRENT_ARCHITECTURE_AUDIT](CURRENT_ARCHITECTURE_AUDIT.md)。

## P0–P1：基線與文字認知

| Task / Feature | Expected Behavior | Existing Implementation / Evidence | Current State | Dependencies | Product wiring / Risks | Recommendation / smallest next action |
|---|---|---|---|---|---|---|
| T01 開發骨架／統一命令 | 可重現安裝、CLI、CI、檢查、secret排除 | `pyproject.toml`、`uv.lock`、`src/siro/cli.py:226`、`scripts/check`；F2 config/redaction；H:T01 clean checkout | Implemented but Unverified | T00 | 本輪未重做全新checkout/遠端CI；check會provision tokenizer，非完全無網路入口 | KEEP骨架；對當前來源補乾淨安裝／CI gate |
| T02 事件契約／相容性 | 非法envelope/version拒絕、依賴邊界 | `src/siro/contracts/events.py`、`src/siro/contracts/boundaries.py`、`schemas/events/`；F2 `tests/contract/test_events.py`、`tests/contract/test_boundaries.py` | Implemented and Verified | T01 | 合成契約／靜態import已驗，不涵蓋任意動態plugin權限 | KEEP；新能力先補必要契約，不造第二envelope |
| T03 有界Event Bus | 優先級、去重、TTL、慢consumer隔離、關閉清理 | `src/siro/events/local.py:225`；F2 `tests/test_local_event_bus.py`；H:T03 | Implemented and Verified | T02 | 元件已驗；GatewayHub直接傳輸，main未用它作全部事件owner | KEEP；無實際caller需求不強迫再接bus |
| T04 SQLite／migration | 升級、交易、outbox/inbox、一致backup/restore | `src/siro/persistence/sqlite.py:45,124`；F1 `tests/integration/test_sqlite_store.py` 的升級/checksum/rollback；001–013 migrations | Implemented and Verified | T02 | 真SQLite＋暫存合成資料；未還原私人DB；source rollback不證schema降版安全 | KEEP；舊migration失敗已解，不重建storage |
| T05 Identity／World | 身份持久、core owner授權、觀測來源/TTL/unknown | `src/siro/core/identity.py:87`、`src/siro/core/world.py:58`；F1 `tests/integration/test_identity_world.py` | Implemented and Verified | T03,T04 | Identity已進companion；World主要device/room caller；無sensor不能虛構在場 | KEEP；新設備沿用observation contract |
| T06 Conversation | mock閉環、串流、取消/timeout/late chunk | `src/siro/core/conversation.py:74`、`src/siro/adapters/models/mock.py`；F1 `tests/integration/test_conversation.py` 含100-race | Implemented and Verified | T05 | 此卡mock狀態機已驗；真provider與整批工具取消另有RT/FIX gate | KEEP generation/terminal invariant，不重寫engine |
| T07 真模型／failover | 兩backend、privacy/budget/cancel、安全替代 | `src/siro/adapters/models/openai_compatible.py`、`src/siro/adapters/models/ollama.py`、`src/siro/adapters/models/failover.py`；`src/siro/services/presentation/gateway.py:1165` 已接單provider retry；H:T07兩真backend | Partially Implemented | T06 | main開機只選一backend；FailoverModel只有該backend，非跨backend routing；本輪未叫真provider；FIX-003另有完成性證據 | KEEP adapters；先保partial intent不retry，真需求出現才接第二backend |
| T08 持續人格／核心 | 三次重啟有來源、adapter swap保identity、離線demo | `src/siro/core/companion.py:14`、`src/siro/core/memory.py:116,246`；F1 `tests/integration/test_persistent_companion.py`；F2 `tests/integration/test_session_restore.py`；H:T08/T07 | Implemented and Verified | T06,T04；真展示另需T07 | Verified限離線核心/SQLite/fake adapter；candidate已恢復canonical dialogue，不證真人自然度 | KEEP Identity/Memory；具體失敗例局部修context，不造人格DB |

## P2–P3：通道、身體與語音

| Task / Feature | Expected Behavior | Existing Implementation / Evidence | Current State | Dependencies | Product wiring / Risks | Recommendation / smallest next action |
|---|---|---|---|---|---|---|
| T09 Broker／outbox／replay | JetStream redelivery、commit去重、replay無副作用 | `src/siro/events/nats.py:15,66`、`src/siro/events/replay.py`；`tests/integration/test_nats_delivery.py`；H:T09 broker L2 | Implemented but Unverified | T03,T04,T06 | 本輪未重跑broker；Gateway main非subscriber；不應只為架構圖改全部傳輸 | KEEP；新增跨程序caller時才補接線/fault gate |
| T10 Gateway／UI | Origin/session、每socket一writer、有界佇列、snapshot/reconnect/cancel | `src/siro/services/presentation/gateway.py:66,144,239,437`、`src/siro/services/presentation/static/index.html`；F2 `tests/integration/test_tool_catalog.py` main fixture；`tests/integration/test_gateway.py`/`tests/integration/test_frontend_control.py`；H:T10/FIX-004 | Partially Implemented | T09 | FIX-004有renewal/control recovery證據；本輪未重演100次真browser重連；UI存在不等於陪伴UX通過 | KEEP hub/token/terminal fence；對具體UI問題驗收 |
| T11 AIRI可行性 | 鎖source/license、四項proof或阻礙、renderer選型 | `docs/ADR-embodiment.md`、H:T11固定AIRI commit；`src/siro/adapters/body/web.py`；F2 `tests/contract/test_body_adapter.py` | Implemented but Unverified | T10 | 歷史source稽核支持最小Web renderer；本輪未重拉AIRI。是research決策，非缺AIRI runtime | KEEP決策；不重做選型、不恢復Unity |
| T12 真Live2D | 真模型idle/emotion/gesture/look/speech、kill/reconnect隔離 | `src/siro/adapters/body/web.py`、`src/siro/services/presentation/static/body.html`、`scripts/repair_companion_renderer.py`；F2 body contract；`tests/integration/test_body_failure_isolation.py`；H:T12真WebGL | Implemented but Unverified | T11 | 本輪未載真WebGL/逐動作可視重驗；自由走動桌寵/完整素材並非既有交付 | KEEP Web/Live2D；驗實際模型動作，缺素材另定asset卡 |
| T13 媒體／播放owner | binary header、sample/frame/buffer有界、單owner | `src/siro/services/audio/protocol.py`、`src/siro/services/audio/session.py:15`；F2 `tests/contract/test_audio_protocol.py` Python/Node golden、`tests/test_barge_in.py` | Partially Implemented | T10,T12 | protocol元件已驗；主頁HTTP WAV/native Audio，不能稱當前Qwen PCM streaming；兩路適用範圍需明確 | KEEP同一frontend owner，不造第二媒體stack |
| T14 VAD／STT | partial/final、單utterance一turn、靜音/噪音/拔除 | `src/siro/services/audio/input.py:31,54`、`src/siro/services/audio/stt.py`；F2 `tests/test_audio_pipeline.py`；`tests/real/test_speech_providers.py`；H:T14 | Partially Implemented | T13 | endpoint有合成測試；主頁HTTP錄音不等於component streaming VAD；真麥克風/provider未重驗 | KEEP；先測當前輸入鏈，再決定partial接線 |
| T15 TTS／分句／口型 | 不讀tool JSON、播放時鐘口型、末音才完成、文字降級 | `src/siro/services/audio/tts.py:32,69,193,492`、`src/siro/services/presentation/gateway.py:585,599`、`src/siro/services/presentation/static/index.html`；F2 audio；`tests/integration/test_speech_plan.py`/`tests/integration/test_frontend_speech_queue.py`；H:T15/FIX-005 | Partially Implemented | T13,T07 | FIX-005 A/B有真Qwen/native browser歷史功能證據；首段22.446s、暖RTF約1.75，速度未達標；真人首尾/自然度未驗；final前committed-sentence/PCM未實作 | 完成既有FIX-005窄效能/聽驗gate；保原聲線/completion-v2/有界prefetch，不把播完稱流暢 |
| T16 Barge-in／AEC | speech onset取消player/TTS/LLM、20次真人/裝置矩陣 | `src/siro/services/audio/session.py:15`；F2 `tests/test_barge_in.py`100-race/late audio；H:T16 speaker L3、FIX-005 worker cancel | Partially Implemented | T14,T15,T12 | 舊speaker harness不自動驗新Qwen/UI；headset未驗；manual stop/HTTP cancel非真人自動barge-in或p95實體停音 | KEEP；以現聲線/輸入/輸出重演真機，不降門檻 |

## P4–P5：記憶、主動性與工具

| Task / Feature | Expected Behavior | Existing Implementation / Evidence | Current State | Dependencies | Product wiring / Risks | Recommendation / smallest next action |
|---|---|---|---|---|---|---|
| T17 五類Memory | FTS、來源/scope/時間/衝突、更正刪除與衍生失效 | `src/siro/core/memory.py:17,116`、`src/siro/persistence/memory.py:15`、`src/siro/services/presentation/gateway.py:870,919,954`；F1 `tests/integration/test_memory_v2.py`20-case/A10/A11；F2 `tests/integration/test_memory_ingress.py` | Implemented and Verified | T08 | 真SQLite/FTS/合成HTTP已驗；candidate explicit remember有來源/privacy，不代表embedding或每句變facts | KEEP；已解ingress/correct/delete不重構；MCP不作第二人格DB |
| T18 Dream／關係演變 | 有界cursor/batch/來源/clamp、cancel/crash/replay冪等 | `src/siro/core/consolidation.py:66,118`、`src/siro/persistence/consolidation.py`；F1 `tests/integration/test_consolidation.py`含子程序crash；H:T18 | Partially Implemented | T17 | 元件通過，Gateway無ConsolidationScheduler caller；RT-015 organizer是唯讀view，非Dream自動改facts/traits | KEEP可沿用元件；無真候選需求不開Dream寫入、不重造scheduler |
| T19 Attention／Goals | clock/hard gates、有限goals/events、step/cost/deadline | `src/siro/core/cognition.py:135,162,174,270,375`、`src/siro/persistence/goals.py:13`；F1 `tests/test_cognition.py`/`tests/integration/test_goals.py` | Partially Implemented | T17,T05,T06 | Gateway AgentRun是turn/tool scope；Planner/GoalService未成一般行動入口；兩scope不可直接合併 | KEEP；先指定caller/event，擴既有gates |
| T20 主動陪伴 | quiet/busy/speaking/cooldown/day cap、可拒絕/可停/L3回饋 | `src/siro/core/proactivity.py:34`、`src/siro/core/rooms.py:51`；F1 `tests/test_proactivity.py`；F2 room simulator；H:T20 | Partially Implemented | T19,T18 | rules/room demo有；Gateway無proactivity pump。organizer foreground preemption非自主發話 | KEEP；先一個有來源低風險觸發用途，驗quiet/cancel/真人干擾 |
| T21 Runtime／grant | server-side scope/hash/expiry/revoke/audit；離線Core可用 | `src/siro/core/authorization.py:37`、`runtime/siro-runtime/src/lib.rs:64`/`rpc.rs:67`、`src/siro/adapters/runtime.py:20`；F2 auth；`tests/integration/test_runtime_boundary.py`；H:T21 | Partially Implemented | T09,T19 | Rust workspace有caller；main其他computer.execute走Python argv/Orchestrator，不能稱Rust grant保護全部電腦能力 | KEEP邊界；新能力明示enforcement path，不讓discovery自授權 |
| T22 Skill Registry／worker | manifest/version/enable/disable、I/O/timeout/cancel/resource/sandbox | `src/siro/core/skills.py:34,76`、`src/siro/persistence/skills.py`、`src/siro/adapters/skill_worker.py:23,132`；`tests/integration/test_skill_registry.py`；H:T22 Bubblewrap | Partially Implemented | T21 | catalog未接SkillDispatcher；load_skill hash只manifest+兩schema，無entrypoint/code/deps；任意生成code不能直接信任；本輪未重驗OS sandbox | KEEP registry/supervisor；先補候選artifact完整性/隔離負測，生成僅candidate |
| T23 檔案／程序 | scoped files、symlink/escape拒絕、cancel清child、ledger/readback | `runtime/siro-runtime/src/linux.rs:189`、`src/siro/services/tools/workspace.py:41`、`src/siro/services/tools/execution.py`；`tests/integration/test_workspace_runtime.py`/`tests/integration/test_computer_driver.py`/`tests/integration/test_bounded_execution.py`；H:T23 | Partially Implemented | T22 | scoped read/list與Python computer.execute權限不同；argv不是OS sandbox；排除sudo/shell字串不證全電腦受Rust scope保護 | KEEP bounded取消；新增write前定scope/ledger，不誇大工作目錄能力 |
| T24 Browser／UI | observe→target→act→readback、origin/stale-screen/vision/平台 | `src/siro/adapters/browser.py:44`、`vision.py:15`、`src/siro/services/tools/browser_session.py:37`；`src/siro/services/presentation/gateway.py:1487`已有session navigate/read/fill/click/close；`tests/integration/test_browser_sessions.py`/`tests/integration/test_browser_driver.py`；H:T24 | Partially Implemented | T23 | 舊模型只navigate/read已過期；一般Wayland desktop/Windows/macOS unsupported；FIX-002 ScopeViolation根因未驗，不能稱已修 | KEEP session；先重現/局部修搜尋，保origin/redirect/stale-target fence |
| T25 系統服務 | allowlisted service/readback、critical install批准、支援範圍 | `src/siro/adapters/services.py:33,132`、`src/siro/core/computer.py:18`；`tests/integration/test_service_driver.py`、`scripts/t25_linux_a17.py`；H:T25 | Partially Implemented | T24,T21 | systemd driver非main結構化模型工具；可用argv非service approval gate全接；跨平台未驗 | KEEP Linux；真caller時接既有driver/catalog，保exact-hash critical批准 |

## P6：環境與硬體

| Task / Feature | Expected Behavior | Existing Implementation / Evidence | Current State | Dependencies | Product wiring / Risks | Recommendation / smallest next action |
|---|---|---|---|---|---|---|
| T26 Device Registry | descriptor/property/action/event、brand alias、availability/TTL、保守presence、owner按需camera | `src/siro/core/devices.py:30,74`、`src/siro/persistence/devices.py`、`src/siro/adapters/devices.py`；F2 `tests/integration/test_device_registry.py` | Implemented and Verified | T19,T22 | Verified限registry/SQLite/跨品牌simulator；main無device discovery feed，不代表已控制家庭或常駐camera | KEEP descriptor；探索只metadata/readback，不自動硬體命令 |
| T27 MQTT／ESP32 | auth/LWT/retained state、非retained command、expiry/dedup/ack+state、真sensor/LED | `src/siro/services/devices/mqtt.py:19,47,79`、`firmware/esp32/src/main.cpp:38,78`；`tests/integration/test_mqtt_gateway.py`；H:T27真broker+simulator | Partially Implemented | T26 | source非燒錄真板證據；本輪未編譯/連ESP32；模擬dedup不證真板跨重啟冪等 | KEEP protocol；固定板型/接線再驗，Agent不送未驗底層指令 |
| T28 Home Assistant | REST/WS descriptor/state、憑證隔離、ledger+回讀 | `src/siro/adapters/home_assistant.py:191,275,323`；F2 `tests/integration/test_home_assistant.py` mocks/auth/readback/降級；H:T28 | Partially Implemented | T26,T21 | 官方protocol mock已驗，真instance/設備未驗；REST200/ack非成功；discovery不得自取token | KEEP adapter；授權instance後一個低風險entity真回讀 |
| T29 房間閉環 | presence→world→attention→policy→light/readback，bounce/feedback/manual/offline | `src/siro/core/rooms.py:51`、`scripts/t29_room_demo.py`；F2 `tests/integration/test_room_automation.py`；H:T29 simulator | Partially Implemented | T20,T27,T28 | 模擬閉環已驗；真sensor+actuator、主頁事件接線/L3未完成；不可猜人在房間 | KEEP場景/抑制；真硬體後驗A18，不先讓main自動控制 |

## P7–P8：受控改善、資源、操作與分散式

| Task / Feature | Expected Behavior | Existing Implementation / Evidence | Current State | Dependencies | Product wiring / Risks | Recommendation / smallest next action |
|---|---|---|---|---|---|---|
| T30 Procedural候選 | 重複可信成功trace→參數化/redacted/來源/fixture，不自enable | `src/siro/core/procedural.py:55`、`src/siro/persistence/procedural.py`；F1 `tests/integration/test_procedural_candidates.py`；H:T30 | Partially Implemented | T18,T22 | generator/repo已驗；無Gateway trace feed/候選審閱入口。輸出workflow fixture，非任意skill code生成/安裝閉環 | KEEP；先唯讀proposal→既有registry比對，candidate/enabled分離 |
| T31 Patch提案／隔離 | 提案→隔離checks/report，失敗不active、不改policy/production | `src/siro/core/evolution.py:30,39,100`；F1 `tests/integration/test_patch_verifier.py`；H:T31 | Partially Implemented | T30,T01 | tempfile/cwd copy不是OS sandbox：subprocess同user/承襲env/無network-resource隔離；兩protected paths不是完整安全邊界 | KEEP提案/report；先secret-free allowlist artifact＋真隔離負測，再測候選；禁production自改 |
| T32 Release／回滾 | 驗真manifest/staging health/active-LKG/crash安全/資料相容 | `src/siro/core/releases.py:17,32,43,94,112`、`src/siro/cli.py:114`；F1 `tests/integration/test_release_manager.py`；H:T32 | Partially Implemented | T31,T04 | HMAC只簽version+digest，未綁min/max_schema；active.json無launcher consumer；整DB rollback會蓋新writes（現測試正驗此行為），無live writer fence | BLOCK autonomous deployment；先完整manifest/launcher/資料恢復契約，隔離驗後才接線；人工部署批准保留 |
| T33 Compute Governor | telemetry/admission/slots、水位hysteresis、pause/budget/control優先 | `src/siro/core/governor.py:28,37`；F1 `tests/test_governor.py`；H:T33；FIX-005局部真GPU | Partially Implemented | T16,T18,T22 | 元件已驗，main model/TTS未經admission；Qwen benchmark非整體GPU壓力/SLO/長時治理 | KEEP；先一個重工作caller接admission/cancel，驗control latency |
| T34 安裝／操作／備份 | lock install/doctor/clean data/graceful stop/DB+settings恢復 | `src/siro/operations.py:34`、`scripts/start`、`scripts/stop`、`scripts/backup`、`scripts/restore`、`scripts/launch_companion.py:11`；`tests/integration/test_operational_cli.py`/`tests/integration/test_companion_launcher.py`；H:T34 clean L2 | Partially Implemented | T25,T29,T32,T33 | user unit直接siro-gateway；專用launcher才強制candidate/model/Live2D；generic啟動非正式companion readiness/all-child-cleanup或release切換證據 | KEEP；對齊產品啟動/doctor readiness，再乾淨目錄實演；restore保live writer |
| T35 v1.0／24h | A01–A22、真音訊/身體/設備、24h/真人UX/安全發布 | `docs/evidence/T35/README.md`、`docs/ACCEPTANCE.md` checklist；`scripts/soak-smoke`僅短時 | Planned Only | T00–T34必要卡 | 無完整24h/真HA+ESP32/真人三輪/全部SLO新證據；元件PASS不可相加當release | KEEP gate；先解本地缺口、逐項解除外部條件，不標發布 |
| T36 節點／信任 | 預配對profile/heartbeat/TTL/revoke/privacy，不自抬權 | `src/siro/core/nodes.py:22,44,95`；F1 `tests/test_nodes.py`；`tests/integration/test_compute_fabric.py`；H:T36 | Partially Implemented | T33,T09 | registry已驗，main不路由nodes；worker wire protocol不等於LAN mutual auth；假雙節點仍simulator | KEEP；有第二主機前只隔離驗信任/protocol，不開正式遠端listener |
| T37 Worker／lease | job/stream/cancel/result、lease/epoch、bounded input/artifact/late fence | `src/siro/core/jobs.py:18`、`src/siro/services/compute/worker.py:20,76`；F1 `tests/test_jobs.py`；`tests/integration/test_compute_fabric.py`；H:T37 | Partially Implemented | T36 | executable以payload.split回words+hash，是protocol worker，非真LLM/STT backend；TCP成功非安全遠端推論 | KEEP lease/fence；真用途時只接一現有adapter，不造模型runtime |
| T38 Router／政策 | privacy/location/model/budget hard filter、latency/cost/trace | `src/siro/core/router.py:21,37`；F1 `tests/test_router.py`；`tests/integration/test_compute_fabric.py`；H:T38 | Partially Implemented | T37,T07 | 演算法已驗；main仍env if/elif，未用ComputeRouter；單provider retry非fabric路由 | KEEP filter；真節點需求時才接線，硬限制先評分、不造第二router |
| T39 真雙節點 | 兩主機真model/STT、LAN故障/重啟/cancel、late epoch/量測 | `docs/evidence/T39/README.md`演練計畫；T36–38元件 | Planned Only | T38＋第二台已配對主機 | 無第二台真機/遠端模型/A24量測；同機兩程序不可替代 | KEEP真機gate；條件到位才實演，不把loopback標分散式 |
| T40 v1.1發布 | A01–A24、distributed24h、回滾/安全/需求追蹤 | `docs/evidence/T40/README.md`發布稽核；`docs/ACCEPTANCE.md` | Planned Only | T35,T39 | 上游完整產品/雙節點/24h/資料相容未通過；無可發布v1.1證據 | KEEP gate；不全表改DONE，依真成果解除條件 |

## 本次驗證

環境：既有 project `.venv` Python 3.14，當前 dirty source。命令 exit code 均0；synthetic fixtures、pytest tmp_path、ASGI/fake HTTP、臨時子程序。沒有呼叫8026、使用者DB/私人對話/reference WAV、真provider/GPU、真ESP32/HA/第二節點，也未啟停現有使用者服務。

**F1：54 passed，2個既有pypinyin warnings，5.74秒。**

```bash
.venv/bin/python -m pytest -q \
  tests/integration/test_identity_world.py tests/integration/test_conversation.py \
  tests/integration/test_persistent_companion.py tests/integration/test_memory_v2.py \
  tests/integration/test_consolidation.py tests/integration/test_goals.py \
  tests/test_cognition.py tests/test_proactivity.py \
  tests/integration/test_procedural_candidates.py \
  tests/integration/test_patch_verifier.py tests/integration/test_release_manager.py \
  tests/test_governor.py tests/test_router.py tests/test_nodes.py tests/test_jobs.py \
  tests/integration/test_sqlite_store.py -m 'not real_provider'
```

**F2：86 passed，3個既有pypinyin/Starlette warnings，7.34秒。**

```bash
.venv/bin/python -m pytest -q \
  tests/contract/test_events.py tests/contract/test_boundaries.py \
  tests/test_config.py tests/test_redaction.py tests/test_local_event_bus.py \
  tests/contract/test_body_adapter.py tests/contract/test_audio_protocol.py \
  tests/test_audio_pipeline.py tests/test_barge_in.py tests/test_authorization.py \
  tests/integration/test_device_registry.py tests/integration/test_home_assistant.py \
  tests/integration/test_room_automation.py tests/integration/test_tool_catalog.py \
  tests/integration/test_session_restore.py tests/integration/test_memory_ingress.py \
  tests/integration/test_context_summary.py tests/integration/test_memory_organization.py \
  -m 'not real_provider'
```

合計 **140 passed**，兩組不重疊；不是全套check/遠端CI/OS sandbox重測/真Live2D/產品驗收通過。其他執行者本輪全套結果另記新證據；FIX-005歷史671 tests不計入這140。

Git交叉核對：`git log -4 --format='%h %ad %s' --date=iso-strict -- docs/TASKS.md docs/STATUS.md src/siro runtime/siro-runtime` 實際顯示 c1d2d41（2026-10-07）、a27001d（2026-09-30）、5d83b05（2026-09-25）。提交證明有後續工作，title不能證逐卡驗收，仍以source/tests為準。

## 舊快照取代與文件不一致

舊 reconciliation 可重現：`git show c1d2d41:docs/runtime-evolution/ROADMAP_RECONCILIATION.md`。以下舊診斷由本次source/tests取代，原task/evidence歷史保留。

| 舊判斷 | 當前證據 | 最小處置 |
|---|---|---|
| T04 migration期待10/實際12而fail | `tests/integration/test_sqlite_store.py:43`已動態比對load_migrations；001–013存在；F1升級/保資料通過 | 已解，不重構migration |
| T07 fallback未接main | `src/siro/services/presentation/gateway.py:1165` candidate接FailoverModel((model,)) | 更正為單backend retry已接，非兩backend failover |
| T08 重啟不恢復context | F2 `tests/integration/test_session_restore.py` main fixture三次重啟，只恢復canonical completed dialogue | 不造第二restore；partial僅readback、工具不重放 |
| T17 chat無remember ingress | `src/siro/services/presentation/integrated.py:371` explicit ingress；F2 remember/correct/delete/restart/privacy/偽來源通過 | 明示explicit可撤銷，不記每句fact |
| Context compression MISSING | `src/siro/services/agent/summary.py:11`、`src/siro/services/agent/context.py:41`、`src/siro/services/agent/native_context.py:28`及Gateway flag；F2 compaction | extractive summary/budget已接，不增第二摘要器 |
| T24模型只有navigate/read | session handlers/catalog已有fill/click/close；F2真main fixture驗可見工具路由 | 保caller，另修具體搜尋失敗 |
| Qwen新鏈取消未測/child cleanup未知 | FIX-005歷史真owned worker cancel/reap/native cleanup/source rollback | 可引用功能證據，不推論真人barge-in/p95/deployment rollback |
| 新工作全未提交/無GPU | 後續commits存在；FIX-005 RTX3050 CUDA/SDPA歷史真測 | 修現況摘要，保舊報告日期，不沿用過期blocker |
| T31 isolated workspace可跑任意生成code | `src/siro/core/evolution.py:100`同權限subprocess，只有cwd copy | 候選自動執行仍blocked；先secret/resource/OS隔離負測 |
| T32 atomic activate即產品自主更新 | signature缺compat fields、active無launcher consumer、整DB回退覆寫新writes | 保模組；deployment/data回退獨立blocked，不開自動更新 |

## 後續邊界

由 [RUNTIME_EVOLUTION_ROADMAP](RUNTIME_EVOLUTION_ROADMAP.md) 小卡承接具體caller、能力盤點、候選隔離；不改T1–T40歷史。Identity、Memory、Conversation、ToolCatalog、ToolOrchestrator、SkillRegistry、DeviceRegistry、lease/router、Live2D沿用，不重造。Codebase Knowledge、Agent Memory、Runtime State分離；discovery僅讀metadata，權限仍由既有執行邊界決定。
