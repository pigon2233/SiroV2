# SIRO V2 Architecture Review

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
