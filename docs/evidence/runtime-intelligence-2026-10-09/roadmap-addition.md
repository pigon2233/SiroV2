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
- Current State: Planned Only
- Objective: SIRO能正確辨識已註冊能力與不可用原因，減少錯選工具／誤稱權限。
- Affected Modules: ToolDescriptor／ToolCatalog／既有模型工具描述；需要時既有UI snapshot。
- Dependencies: RT-007既有catalog；FIX-002搜尋診斷仍獨立；不依賴新MCP runtime。
- Implementation Scope: 先補typed純metadata投影：identity/description/schema/I-O/permissions/effects/risk/availability/version/provenance/timeout/failure；未知值明示。保持原definition及executor來源唯一。
- Acceptance Criteria: inventory與definitions/executor/availability一致；無探索副作用；未註冊能力不捏造；metadata不是grant；unknown不自動放行。
- Tests: schemas、缺依賴／停用／stale availability、沒有executor invocation、原tool/batch/cancel回歸。
- Risks: metadata重複或risk誤分類；不得為UI顯示改授權語意。
- Rollback: 撤純metadata/讀取入口，保留既有catalog、proposal、grant與journal。
- Status: PLANNED；可獨立小切片開始，不因自主skill gate全面阻擋。

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
