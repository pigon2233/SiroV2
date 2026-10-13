# Runtime evolution roadmap

## 2026-10-09 Runtime Intelligence incremental plan（現況優先）

使用者本輪授權現況盤點、開發期 Codebase Memory 與必要低風險改善；不是授權正常運作中的 SIRO 自改核心或部署。沿用原 T01–T40／RT-001–015／FIX 歷史，新增 RI 識別碼不表示排名。不重新延期或重做已完成 RT-011／013／015。

產出入口：[現況與 call chains](CURRENT_ARCHITECTURE_AUDIT.md)、[唯一 T1–T40 矩陣](ROADMAP_RECONCILIATION.md)、[Codebase Memory](CODEBASE_MEMORY_INTEGRATION_REPORT.md)、[Runtime Intelligence 契約設計](RUNTIME_INTELLIGENCE_DESIGN.md)。既有桌寵／動作／主動追蹤沿 [COMPANION_EVOLUTION_PLAN](COMPANION_EVOLUTION_PLAN.md)，不另造平行產品計畫。

| Phase | 保留／新增工作 | 狀態與接入條件 |
|---|---|---|
| P0 現況、穩定性、開發理解 | RI-001；既有 FIX-002／005／006；新 FIX-007／008／009 | 先驗真問題。005仍PARTIAL；三個新FIX只定義、尚未修復。全套PASS不能解開自主安全gate |
| P1 工具理解與探索 | RI-002 | 擴現有ToolCatalog唯讀metadata，不新增registry／executor。探索不得啟動CLI/API/MCP副作用 |
| P2 候選技能與安全測試 | RI-003、RI-004 | BLOCKED_BY_FIX：FIX-007／008及真隔離／批准驗收。先candidate，未批准不可enabled |
| P3 受控改善、發布、軟體理解 | RI-005、RI-006；授權軟體分析後續切片 | BLOCKED_BY_FIX：發布promotion需FIX-009；正式啟用另需launcher與最新資料保留回退。proposal可與發布分離 |

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
- Current State: Partially Implemented（可信checks的copy verifier與skill worker存在）
- Objective: 候選程式跑測試時無法讀私人資料、改host／政策或繞過取消。
- Affected Modules: 既有PatchVerifier與WorkerSupervisor測試入口；重用現有bwrap經驗。
- Dependencies: BLOCKED_BY_FIX：FIX-008；明確支援OS與可信check allowlist。
- Implementation Scope: 一個OS驗證backend；最小source/deps mounts、private scratch、無network／credential、process tree cancel、CPU/RAM/time/output caps。缺隔離即拒絕，不以cwd冒充。
- Acceptance Criteria: 惡意import讀host/寫外部/網路/子程序與洪水全部拒絕；cleanup；原source不變；trusted/unsupported狀態明確。
- Tests: 跨邊界負面fixtures、timeout/cancel/kill／OOM／output flood、原patch/worker回歸；實際OS測試不以mock代替。
- Risks: dependencies供應鏈與kernel邊界；不把本輪開發MCP sandbox當成此能力完成。
- Rollback: 停用untrusted candidate checks；保留proposal/static review；不需資料schema回退。
- Status: PLANNED／BLOCKED_BY_FIX：FIX-008（僅候選執行接入）。

### RI-004

- Task ID: RI-004
- Title: 從缺能力到待批准的skill候選
- Current State: Partially Implemented（manifest／registry／dispatcher／procedural candidates已有）
- Objective: 真的缺能力才生成可審核候選，保留擁有者啟用與撤銷。
- Affected Modules: 既有procedural、skill registry/dispatcher、catalog extension point。
- Dependencies: RI-002／003；BLOCKED_BY_FIX：FIX-007／008；批准者與候選程式權限分離。
- Implementation Scope: request→existing tool search→spec→candidate→static→sandbox→review→approval→registry；先一個唯讀本機用途。禁止下載即執行／自授權。
- Acceptance Criteria: 已有tool不重造skill；package與批准digest一致；未批准永不enabled；取消／撤銷有效；來源／測試／trust level可見。
- Tests: 既有能力命中、不明來源/篡改/缺依賴、負向權限、重複註冊、撤銷、worker cancel；catalog/registry相容回歸。
- Risks: candidate及網頁內容注入；不將test PASS等同review批准。
- Rollback: 停用新增capability註冊與該版本；保留原工具、approval audit和使用者資料。
- Status: PLANNED／BLOCKED_BY_FIX：FIX-007／008及RI-003真隔離gate。

### RI-005

- Task ID: RI-005
- Title: 可辨識啟動版本與保留最新資料的人工發布回退
- Current State: Partially Implemented（ReleaseManager／CLI與專用launcher已有）
- Objective: 區分active pointer、真正執行版本與資料恢復；不因code rollback覆蓋後來的對話／記憶。
- Affected Modules: 既有ReleaseManager、operations／companion launcher；不重做update framework。
- Dependencies: BLOCKED_BY_FIX：FIX-009；T34產品readiness；人工maintenance窗口與schema兼容政策。
- Implementation Scope: 先設計code rollback保持live data的測試；單一stopped-writer gate；驗launcher實際consume版本／last-known-good readiness。schema不兼容就拒自動回退；資料還原為獨立明確操作。
- Acceptance Criteria: 兩版啟動source identity可讀；新寫入在code rollback後仍在；中斷/migration失敗無雙writer；已完成效果不重播；未批准不deploy。
- Tests: 暫存DB晚寫、WAL/active writer、schema incompat、activation crash、launcher實際版本與health；不使用私人DB。
- Risks: migration與資料生命週期屬RED；沒有證據不可降低gate。
- Rollback: 撤新發布接入／保持舊可信launcher及最新DB；人工復原不能靜默restore舊backup。
- Status: PLANNED／BLOCKED_BY_FIX：FIX-009（自動或產品發布promotion）；不是本輪deployment。

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
