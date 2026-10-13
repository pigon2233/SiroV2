# SIRO 2 目前進度與接續點

## 2026-10-10 — FIX-010 未知效果自動重送邊界已 VERIFIED（最新）

實際controller合成反例證實換call UUID能逃old replay fence；現在auto pending→approved原交易查同session/cap的unknown dispatch，same hash或binding不明需manual。只有orchestrator/integrated/UI三production＋44backend/1frontend新cases，原manual/grants/ledger/DB/模型/語音不變。45修前FAIL→122專項相鄰PASS，全套991PASS／5real_provider未選／3warnings（118.71s）；真Chrome21/21驗警告、零auto效果、WS reconnect不重送、explicit一次與duplicate404、exact ledger不變/cleanup。獨立review＋RED修正payload/Unicode/numeric/duplicate邊界；format226/mypy216/lint/schema/零scoped secrets，229oldsource只3變、exact5file source回退PASS。

FIX-010局部gate解除，不代表FIX-006語意DONE、FIX-002搜尋或FIX-005速度／人耳完成。頁reload卡恢復/active snapshot差異與unknown resolution/retention仍有局限；不增加新state manager。沒有8026restart/私人DB/WAV/key/部署。下一張RI-003先確認可支援的真Linux single-process profile、source-only projection／可信checks／取消，有實證才接入口；完整multiprocess需aggregate资源界線另驗。[證據與回退](evidence/FIX-010-2026-10-10/REPORT.md)。


## 2026-10-10 — FIX-006 局部故障事實已驗；理解仍PARTIAL（最新）

修復下一轮無自身失敗事實的缺口，並撤除每則文字都能念完/Live2D必連線的錯誤保證。只既有runs/integrated兩檔＋40專項；fixed五欄同session/privacy/15min摘要、原restore gate與failed-intent fence不變，無raw payload/效果/DB改動。獨立review抓到invalid-time排序及SQLite NUL length並局部修復。40修前FAIL→55新舊PASS，全套946PASS／5real_provider未選／3warnings（114.33s），format224／mypy214／lint/schema PASS；228現有檔僅2production變，exact3file reverse/reapply SHA PASS。

同配置真模型的合成對照支持「知道自己的HTTPStatusError/原因UNKNOWN」，**不支持整體理解DONE**：語音需求更正仍ProviderOutputTruncated、unknown-effect重做語意FAIL、memory cloud區別/style/CAPTCHA仍未全驗。FIX-006保持PARTIAL與產品gate，不換backend/加tokens/廣泛prompt/執行模型新指令；下一步僅量completion usage與reasoning allocation的窄幅假設。FIX-002有用搜尋、FIX-005語音速度/人耳驗收與RI-003–005接入gates原樣保留；沒有8026restart／私人DB/WAV／發布。 [完整證據](evidence/FIX-006-2026-10-10/REPORT.md)。

FIX-006補充量測已完成：[8次synthetic allocation](evidence/FIX-006-2026-10-10/COMPLETION_ALLOCATION.md) 支持reasoning與visible verbosity混合；low仍有length與錯誤語意，REJECT本輪改production effort，不提高budget/換backend。新429有量到但不回推原事件，零自動重試。

## 2026-10-10 — FIX-007 技能 package identity 已 VERIFIED（最新）

只在既有skills/registry/dispatcher三檔修復：完整versioned digest、批准root/hash、legacy fail closed、owned byte snapshot、取消/清理不復活、最多8副本與worker concurrency綁內容。原source43新cases42FAIL／1PASS；最終新舊/adjacent66PASS、全套906PASS／5real_provider未選／3既有warnings（113.93s），format223／mypy213／lint／schemas PASS。227既有來源中只3production變動、原skill tests未改、精確4檔temp reverse/reapply SHA PASS。

FIX-007／008／009局部gates已解除；**generated skill接入仍需sandbox/review/明確enable，untrusted checks真OS隔離與可信check allowlist、發布launcher／批准／最新資料保留回退仍未驗**。沒有runtime skill catalog/自改/自動發布，也沒讀私人資料或重啟8026。保留既有RT/voice/session；下一張FIX-006，優先驗文字對話是否能正確描述能力與當次故障，避免無來源全知/繞驗證建議。[交付与回退](evidence/FIX-007-2026-10-10/REPORT.md)。
## 2026-10-10 — FIX-009 完整簽署已 VERIFIED（最新）

已修復 release schema bounds 未簽署漏洞：明確版本化 canonical 全 manifest HMAC、strict bounds、legacy無fallback與入口重驗。只1個production檔、舊fixture＋34新tests；修前真activated反例→新舊36PASS，全套863PASS／5 real_provider未選／3既有warnings（111.19s），format222／mypy212／lint／schema PASS。226份existing hash中只本卡production／fixture變動，精確3檔temp reverse/reapply SHA PASS。

FIX-008／009局部gate解除；**FIX-007技能身份、untrusted checks真OS隔離與可信check allowlist、launcher／人工批准／最新資料保留回退仍阻擋相關自主執行／發布**。沒有live service/key/私人資料/deployment；原whole-DB rollback語意未變，不能當保留最新記憶。既有搜尋／語音速度／理解產品gate仍保留。下一張繼續FIX-007，修既有registry/dispatcher的完整package identity，不新增另一套技能系統。[驗收與回退](evidence/FIX-009-2026-10-10/REPORT.md)。
## 2026-10-10 — FIX-008 path保護已VERIFIED（最新）

完成protected delete／rename來源與目的完整辨識、canonical path與whole-input preflight。只改core/evolution.py，支援的text dialect明示D38；歧義格式拒絕、hunk內標頭文字按counts正常處理。精確舊source46FAIL／16PASS→新舊63PASS；獨立17反例未找到證實bypass；全套829PASS／5 real_provider未選／3既有warnings（112.86s），mypy211／lint／schemas PASS。225基準檔僅1production變動、兩檔精確temp reverse/reapply SHA PASS，前序RI-002／browser／voice/session保留。

FIX-008局部gate解除，**untrusted checks的OS隔離／可信checks、FIX-007技能身份、FIX-009發布簽署及launcher/資料回退仍各自阻擋promotion**。沒有正式服務、private資料或live候選apply。FIX-002搜尋PARTIAL／FIX-005速度／FIX-006理解仍保留；下一張繼續FIX-009，不重編或重做RT。[交付與驗收](evidence/FIX-008-2026-10-10/REPORT.md)。


## 2026-10-10 — FIX-002局部修復驗收；搜尋仍PARTIAL（最新）

完成safe browser reason、同一failed observation投影、可讀主頁partial、主frame／redirect拒絕與關閉期callback收束；只6個production檔，沒有scope／hash／授權／DB／依賴變動。新51專項納入離線全套767PASS／5 real_provider未選／3既有warnings（111.45s）；真Chrome10 scope fixtures、18 UI renderer情境、2 slow-route close/cancel均PASS。精確10檔temp reverse/reapply SHA回退與221既有source保存PASS，原RI-002／voice/session工作保留。

真configured provider→批准browser→native續談已驗，但Bing僅頁首、DDG human challenge，沒有有用search結果；自動研究保持BLOCKED_BY_FIX：FIX-002。原私人事件root cause及兩次public4s cleanup的具體阻塞步驟仍UNKNOWN；最後一次close0.069s、零殘留不能抵銷原失敗。模型不當繞驗證建議保留為FIX-006負向case，未實際bypass。沒有重啟8026／讀私人DB、WAV或輸出credentials；source需之後啟動載入，不稱deployment。

[FIX-002交付、真結果與回退](evidence/FIX-002-2026-10-10/REPORT.md)。使用者要求一直做；下一張獨立已確認局部漏洞為FIX-008 protected delete/rename辨識，仍先測試、局部修復與回退，不讓不可信checks或自主發布越過各自gate。


## 2026-10-10 — RI-002 能力說明已實作與驗收（最新）

完成既有ToolCatalog純metadata／單次capture：保留name/schema/executor來源，optional欄位缺失明示null；安全availability/reason只描述當次可用性，exception不外送，unknown不向模型提供工具也不能dispatch。沒有新增registry／executor／endpoint／worker／DB migration／依賴，沒有更改批准或full-mode語意。

candidate首輪與工具續輪用同次capture提供ToolDefinition與capability context；在既有checkpoint更新首system message末端唯一SIRO-owned block，無message累積、不動user/assistant/tool pairing或memory。legacy原schema/prompt保持。authenticated /v1/runtime沿原tools欄位加metadata，UI「電腦協助→我現在能做什麼」顯示能力與停用原因，刷新只讀取狀態，metadata以textContent呈現。

驗收：15新專項PASS（1.03s）、既有相鄰26PASS、完整離線716PASS／5 real_provider未選／3既有warnings（98.91s）；Ruff271格式檔／lint、mypy206、export_schemas --check PASS。真Chrome154／HTTP13checks PASS，停用／恢復／未授權401／HTML injection／零executor與零pageerror；readiness/provider為合成，不包裝成人工模型語意、聲音或Live2D驗收。初次產品fixture漏LanguageModel.name導致1FAIL，僅補fixture並保留失敗log；未改production門檻。

只改4個production檔與新增2個tests；本輪前256份source/test/script/locks除明列4檔外全部SHA不變，保留既有voice/session dirty work。精確6檔temp反向／重套SHA回退PASS；既有8026 health/root/live2d HTTP200，未重啟、未讀私人DB／WAV／key。新後端需下次啟動載入；不稱正式deployment。

[RI-002交付／驗收／回退](evidence/RI-002-2026-10-09/REPORT.md)。MCP本輪被既有owner lease占用，未關owner／繞鎖／重索引；重用同source hash的RI-001 graph，source/AST補callers並誠實記NOT_RUN。下一張可開始FIX-002搜尋診斷與公開查詢驗收；FIX-005語音速度／人工語意與FIX-006理解仍未完成；生成技能／自改／發布仍受FIX-007–009及真隔離／批准／資料回退gate。


## 2026-10-09 — Runtime Intelligence現況盤點與開發期MCP（最新）

使用者本輪要求Preserve First／Understand Second／Extend Third／Verify Always，已完成RI-001的低風險開發切片。原main／c1d2d41與FIX-003／004／005 dirty source、私人資料和聲線都保留；未改production source／API／schema／runtime dependencies，原251個source/tests/locks雜湊零變。本機8026 health、首頁、Live2D mount仍HTTP200；沒有重啟服務或對私人對話送測試訊息。

官方Codebase Memory v0.11.0固定archive checksum核對後手動安裝；本機受限stdio MCP已initialize/tools-list/query成功，250 source files、3092 nodes、16700 edges。只讀analysis profile＋client allowlist、source-only投影、真無網路／只讀mount、乾淨env、watcher／auto-index／UI停用；無遺留程序。這不是SIRO長期記憶，也不是自主部署。current workspace設定已由Codex CLI讀到；nested Git root project trust未更改，本輪chat工具清單仍待重載，不聲稱已hot reload。升級/手動index/排除/資源樣本/回滾見CODEBASE_MEMORY_INTEGRATION_REPORT。

唯一ROADMAP_RECONCILIATION已逐項核對T01–T40：8個限定元件Implemented and Verified、4個Implemented but Unverified、25個Partially Implemented、3個Planned Only；未把歷史DONE等同正式產品。CURRENT_ARCHITECTURE_AUDIT、CAPABILITY_MATRIX與Runtime Intelligence設計已對齊native messages/catalog/session memory/summary/Rust/organizer實際caller；不重做已解決RT。新增RI-001–006小卡及P0–P3分類，原T／RT編號與歷史不變。

合成反例證明skill code未綁完整package identity、protected deletion漏判、same-user copy不是sandbox、release schema bounds未簽署。FIX-007／008／009已定義REQUIRED_FIX／HIGH／PLANNED，尚未修production；只阻擋各自generatedskill／patchcheck／release promotion。OS驗證、launcher consume與保留最新資料回退另設接入gate；沒有證據推翻整體Runtime Evolution設計，不新增ARCHITECTURE_CORRECTION或平行registry／scheduler／memory DB。

本輪基線671PASS；最後全套701PASS／5 real_provider未選／3既有warnings／147.01s，新增30個開發tool測試；Ruff269 files、mypy204、schemas、Rust6 tests PASS。真bubblewrap12項隔離與開發MCP停用／恢復回滾PASS。另140／40項離線子集與四類安全反例不是額外相加的產品完成數。證據 [runtime-intelligence REPORT](evidence/runtime-intelligence-2026-10-09/REPORT.md)；安全反例 [RI architecture REPORT](evidence/RI-architecture-2026-10-09/REPORT.md)。未跑真provider／新GPU／人耳／真人Live2D／真HA或ESP32／24h／遠端CI／attestation；沒有以HTTP200取代實際互動驗收。

下一個可開始窄切片為RI-002既有catalog純metadata與唯讀inventory；既有FIX-002搜尋、FIX-005語音速度／人工語意、FIX-006自身故障理解仍未完成，應按產品問題各自驗收。任何生成技能／不可信checks／發布接入先滿足FIX-007–009與隔離／批准／資料回退gate。此處列接續關係，不表示另建或重排原RT。

---

以下為原先各時點的歷史進度；與上方矛盾時以最新現況與實碼證據為準。

更新：2026-09-26

## 當前狀態

**T00–T34、T36–T38 與 R02–R03 已完成各列所標示的驗證層級。** T36–T38 已補持久節點設定、資源 heartbeat、可執行 loopback worker、lease/cancel/stream/result fence，以及 A23 假雙節點路由；同機 simulator 不取代 T39 真雙節點。原 repo 初始 commit `c060f1b`，所有新工作仍未提交。

已完成：分享對話解析與需求追蹤、架構與介面規格、使用體驗、威脅/隱私與資料生命週期、41 張實作任務卡、3 張研究卡、24 個驗收情境、Sol 啟動/續作/除錯手冊、初始 ADR，以及逐項規劃完成度稽核。

尚未完成：T35–T40、R01、R03 完整產出、完整產品驗收與其他平台／ESP32 與真實 Home Assistant instance 測試。AIRI 已完成鎖定 source/license/API 稽核。

## 下一個具體動作

本機可完成的已知缺口已清除；下一步需外部條件到位後執行 T35（24 小時／真人／真設備）或 T39（第二台真實節點），最後才是 T40。

## 外部條件清單

| 項目 | 目前狀態 | 最遲影響任務 |
|---|---|---|
| 最終部署 OS/CPU/RAM/GPU | 第一開發基線已盤點；最終部署仍未確認，NVIDIA driver 不可用 | T33 |
| 模型 backend 認證與費用上限 | Groq 免費 API 與本機 Ollama 已完成 L2；正式費用上限未設定 | 發布前 |
| Live2D/聲音資產與授權 | Cubism Web SDK 5-r.5/Haru 與 Orpheus 條款已接受並通過本機驗收；發布前另確認 Publication License | 發布前 |
| 麥克風/喇叭測試環境 | speaker AEC 與 20 次真人打斷通過；實體 headset 未測 | T16 完成，headset 未宣稱已驗 |
| ESP32/HA instance 與設備 | ESP32 及真實 HA instance 未確認；T28 mock integration 已通過 | T27–T29 |
| 第二台算力節點 | 未確認 | T39 |
| Windows 支援範圍和實測主機 | 未確認 | T24/T25 |

## 任務狀態

T00–T34 已完成相應 L1/L2、限定平台 L3 或 simulator/mock gate；其餘狀態如下。不能從文件數推算產品完成百分比。

| 範圍 | 狀態 | 證據 |
|---|---|---|
| 規劃文件包 | COMPLETE | 本 repo 的 13 份 Markdown 文件與 `docs/evidence/planning-check.json`；逐項證據見 PLANNING_AUDIT |
| T00 | DONE | `docs/ENVIRONMENT.md`、`DEPENDENCIES.md`、`DEPLOYMENT_POLICY.md`、`evidence/T00/README.md` |
| T01 | DONE | `pyproject.toml`、`uv.lock`、`src/siro`、`scripts/check`、CI、`evidence/T01/README.md` |
| T02 | DONE | `src/siro/contracts`、`schemas/events`、`tests/contract`、`evidence/T02/README.md` |
| T03 | DONE | `src/siro/ports/events.py`、`src/siro/events/local.py`、24 tests、`evidence/T03/README.md` |
| T04 | DONE | `src/siro/persistence`、migrations、SQLite integration tests、`evidence/T04/README.md` |
| T05 | DONE | identity/world、35-test gate、`evidence/T05/README.md` |
| T06 | DONE | conversation/mock/CLI、A01/A02 L1、100-race、`evidence/T06/README.md` |
| T07 | DONE | 兩 adapter/L1、Groq L2、Ollama L2、A03 backend swap，見 `evidence/T07/README.md` |
| T08 | DONE (L1) | persistent memory/persona/demo、A03 L1、`evidence/T08/README.md` |
| T09 | DONE | JetStream/outbox/redelivery/quarantine/replay、A04 L2、`evidence/T09/README.md` |
| T10 | DONE | loopback gateway/control UI/single writer、A05/A06 L2、`evidence/T10/README.md` |
| T11 | DONE (research + L1) | AIRI commit/license/API 阻礙、body contract、最小 Web adapter，見 `ADR-embodiment.md` 與 `evidence/T11/README.md` |
| T12 | DONE (L1 + local L2) | Cubism Web 5-r.5/Haru、真 WebGL renderer、56-file manifest、body WS、kill/restart A07，見 `evidence/T12/README.md` |
| T13 | DONE (L1 + local L2) | binary header、Python/Node golden、mic/output WS、single owner、ring buffer，見 `evidence/T13/README.md` |
| T14 | DONE (L1 + Groq L2) | VAD、partial/final、endpoint、Groq Whisper 真實 fixture，見 `evidence/T14/README.md` |
| T15 | DONE (L1 + Groq L2) | 分句、stream transport、ACK/口型/文字降級與 Orpheus→Whisper 真實閉環，見 `evidence/T15/README.md` |
| T16 | DONE (L1 + speaker L3) | barge-in、generation fence、100 races、故障矩陣、speaker AEC 與 20 次真人打斷完成；headset 明列未驗，見 `evidence/T16/README.md` |
| T17 | DONE (L1 + SQLite integration) | 五類 memory、FTS、版本/來源/scope、A10/A11、管理 API，見 `evidence/T17/README.md` |
| T18 | DONE (L1 + SQLite integration) | bounded/resumable scheduler、A12、trait clamps、relationship revisions，見 `evidence/T18/README.md` |
| T19 | DONE (L1 + SQLite integration) | Attention/Drives/Workspace、hard gates、Goal lifecycle/budgets、noise replay，見 `evidence/T19/README.md` |
## 2026-09-27／產品整合狀態

T00–T40 的完成標記只代表各任務所列的元件或測試層級，不代表使用者產品已完成。產品閉環改以
`docs/INTEGRATION_PLAN.md` 的 I01–I05 驗收。

| 整合項目 | 狀態 | 已驗證／仍缺 |
|---|---|---|
| I01 文字 Companion | DONE (L2) | 真瀏覽器經 Gateway → persistent Core → Groq 串流回答；provider 與 route 可見 |
| I02 角色與情緒 | IN-PROGRESS | `siro-affect-cpm-1` 版本化參數、混合 appraisal、時間衰減、PAD mood、homeostatic drives、coping、關係 revision、goal/action/memory contracts、room/systemd/browser/process/file readback、單一 affect decision loop、Live2D 表情抑制、瀏覽器 prosody 與 30 天模擬已接；只剩真人長期驗證尚未完成 |
| I03 語音 | DONE (L2 + owner acceptance) | mic → Groq Whisper → 對話 → TTS/Live2D 同頁閉環已通；預設改為 Qwen3-TTS 0.6B Base 使用 `qwen3-siro-anime-daughter-v1.wav` 做 zero-shot voice clone，獨立常駐 worker 與文字快取已接入。RTX 3050 已驗證 `torch 2.12.0+cu130`/CUDA；第一次 2.48 秒合成含載入約 26.8 秒，仍需優化串流首包延遲 |
| I04 電腦操作 | IN-PROGRESS | 模型 tool catalog → persistent proposal/grant → executor observation → 模型 continuation 已完成並以真 Groq 驗證；正式路徑停用關鍵字 routing，新增有界 `computer.execute` argv 執行。Migration 012 已持久化 AgentRun goal/state/step/observation，並接入現行工具回路。尚缺原生 multi-message tool protocol、持續 GUI/browser session、in-flight process cancel、authorization profiles 與 sudo broker |
| I05 設備與發布 | NOT-INTEGRATED | simulator/release 元件存在；產品 UI、真硬體與 soak 尚未完成 |

| T20 | DONE (L1) / L3 PENDING | 預設關閉、quiet/busy/speaking/cooldown/day limit、7-day replay，見 `evidence/T20/README.md` |
| T21 | DONE (L1 + L2) | Runtime clock、SQLite grant/revoke/audit/action、跨程序 A14、ASK workflow，見 `evidence/T21/README.md` |
| T22 | DONE (Linux L2) | Bubblewrap network/filesystem/env isolation、resource limits、Core heartbeat，見 `evidence/T22/README.md` |
| T23 | DONE (Linux L2) | Rust Runtime grant → filesystem/process driver、持久 action ledger、A16，見 `evidence/T23/README.md` |
| T24 | DONE (Linux Chrome L2 + visible L3) | scoped origin/redirect、stale-screen fence、form/key/pointer/screenshot readback、local pixel analyzer；Wayland desktop unsupported，見 `evidence/T24/README.md` |
| T25 | DONE (Linux L2 + A17 L3) | allowlisted user-systemd、exact-hash critical install、可視 Chrome＋PipeWire＋service failure isolation；Windows/macOS unsupported，見 `evidence/T25/README.md` |
| T26 | DONE (SQLite integration + simulators) | descriptor/schema、room edges、canonical actions、TTL/stale/unknown、light/presence/temperature/camera simulators，見 `evidence/T26/README.md` |
| T27 | DONE (authenticated broker + simulator) / HARDWARE PENDING | Argon2 auth、LWT、retained state、non-retained command、expiry/dedup/ack-readback、ESP32 source，見 `evidence/T27/README.md` |
| T28 | DONE (official protocol mock integration) / REAL HA PENDING | REST descriptor/snapshot/readback、WebSocket auth/state_changed、action ledger、token env-only、revoked/unavailable 降級，見 `evidence/T28/README.md` |
| T29 | DONE (L1 closed-loop simulator) / L3 PENDING | presence→world→salience→candidate→policy→light→readback、bounce/feedback/manual/offline 抑制，見 `evidence/T29/README.md`；需至少一個真 sensor 和 actuator |
| T30 | DONE (L1 + SQLite integration) | repeated trusted successful traces、secret redaction、fixture、source trace、review-only candidate persistence；不安裝或 enable，見 `evidence/T30/README.md` |
| T31 | DONE (L1 isolated workspace) | unified diff、獨立 temporary workspace、argv-only checks、pass/fail report、production digest 和 permission-policy protection，見 `evidence/T31/README.md` |
| T32 | DONE (L1 isolated release) | signed/hash manifest、SQLite backup/integrity、schema compatibility、staging healthcheck、atomic activate/last-known-good rollback，見 `evidence/T32/README.md` |
| T33 | DONE (L1 + local telemetry) | /proc telemetry、model slots、high/low hysteresis、background pause/resume、cloud budget hard gate、control/cancel pressure test，見 `evidence/T33/README.md` |
| T34 | DONE (L1 + Linux L2 A22) | locked clean install、user units、doctor、health/graceful stop、14-day logs、hashed DB+settings backup/restore，見 `evidence/T34/README.md` |
| T35 | BLOCKED-EXTERNAL | v1.0 24-hour soak、真人 UX、真 HA/ESP32、正式 provider profile，見 `evidence/T35/README.md` |
| T36 | DONE (L1 + loopback L2 simulator) | persistent pre-pair config、capability/resource heartbeat、TTL/revocation、假雙節點，見 `evidence/T36/README.md` |
| T37 | DONE (L1 + loopback L2 simulator) | worker executable、bounded stream/input、cancel/lease/epoch/result fence、artifact cleanup/fault，見 `evidence/T37/README.md` |
| T38 | DONE (L1 + loopback A23 L2 simulator) | location/privacy/model/budget hard filters、cost/latency、trace/calibration，見 `evidence/T38/README.md` |
| T39 | BLOCKED-EXTERNAL | 需要第二台真實節點，見 `evidence/T39/README.md` |
| T40 | BLOCKED-EXTERNAL | 依賴 T35/T39；發布稽核見 `evidence/T40/README.md` |
| R01 | RESEARCH-BLOCKED-EXTERNAL | 需要 T39 真雙節點與適合推論硬體 |
| R02 | RESEARCH-DONE (synthetic) | fixed-seed rules/attention/drives/dream ablation；不調整 scorer/traits，見 `evidence/R02.md` |
| R03 | RESEARCH-DONE (limited spike) | limited WoT TD translation、相容矩陣、工時比較與延期 ADR D11，見 `evidence/R03.md` |

## 2026-09-23／T00 交接

- 完成與變更：盤點 OS/CPU/RAM/GPU/audio/tooling/repo，定義 dependency 與保守 deployment policy。
- 驗收：真實 shell 查詢與官方 dependency 文件；證據見 `docs/evidence/T00/README.md`。
- 工作區：`main`，原有規劃與本次 T00 均未提交；無 secret。
- 真實／mock：環境盤點真實；模型、身體、設備、第二節點尚未驗證。
- 下一步：T01 建立 `pyproject.toml`、`uv.lock`、`src/siro/cli`、`scripts/check`、CI 與測試。

## 2026-09-23／T01 交接

- 完成與變更：Python package、settings schema v1、CLI doctor/config schema、locked dependencies、統一 checks、CI、redaction 和測試。
- 驗收：`scripts/check` 通過 format/lint/mypy/6 tests/secret scan；doctor exit 0；證據見 `docs/evidence/T01/README.md`。
- 工作區：`main`，所有規劃/T00/T01 變更仍未提交；`.venv` 已 gitignore，無 secret。
- 真實／mock：CLI 與環境診斷為真實本機；沒有模型或外部整合。
- 下一步：T02 建立 `src/siro/contracts`、`schemas/events` 和 contract/boundary tests。

## 2026-09-23／T02 交接

- 完成與變更：event envelope、9 個首批 typed events、有界 JSON validation、causal session guard、JSON Schema export/stale check、Core import boundary。
- 驗收：`scripts/check` 通過 format/lint/mypy/17 tests/schema/secret scan；證據見 `docs/evidence/T02/README.md`。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：純 deterministic contract tests；沒有 broker 或跨程序 transport。
- 下一步：T03 實作 `src/siro/ports/events` 與 bounded local bus，驗證慢 consumer、expiry、priority 和 shutdown cleanup。

## 2026-09-23／T03 交接

- 完成與變更：EventBus/Clock ports、有界 priority buffers、每訂閱者 worker、TTL/dedup、滿載結果、例外隔離及 shutdown cleanup。
- 驗收：`scripts/check` 通過 format/lint/mypy/24 tests/schema/secret scan；10,000-event、slow consumer、priority/fairness、expiry/duplicate、worker cleanup 均通過。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：asyncio 本機 bus 為真實程式，測試資料合成；沒有 broker/durability。
- 下一步：T04 建立 SQLite WAL schema/migrations、transaction、outbox/inbox 與一致 backup/restore。

## 2026-09-23／T04–T08 交接

- 完成與變更：SQLite WAL/migrations/outbox/inbox/backup、identity/world、conversation 狀態機與 durable messages、OpenAI-compatible/Ollama/failover adapters、source-backed memory、persona prompt 與 offline CLI demo。
- 驗收：`scripts/check` 通過 format/lint/mypy/47 tests/schema/secret scan，2 個真 provider tests 因外部條件明確 skip；A01 單 trace/有序 delta/唯一 terminal、A02 100 次 race、三次 DB 重啟記憶、adapter 切換 identity、unknown 無假來源均通過。證據見 `docs/evidence/T04` 至 `T08`。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：T05、SQLite 與 CLI 為真實本機程式；A01/A02 為 L1 deterministic。Groq `openai/gpt-oss-20b`、Ollama 0.34.3 + `qwen3:4b` 與 A03 backend swap 已通過 L2。
- 新決策與缺陷：雲端外送必須明示 `cloud_allowed`；failover 只准在尚未顯示文字前發生；Groq SSE 與 Ollama NDJSON 已改為真正 streaming，取消會關閉 response。
- 下一步：有 credential/model 時補 T07 L2；否則進 T09 broker/outbox replay。

## 2026-09-24／T09 交接

- 完成與變更：NATS JetStream adapter、SQLite outbox dispatcher、bounded retry/quarantine、durable inbox dedup、read-only replay runtime、broker config 與 CI broker install。
- 驗收：`scripts/check` 通過 50 tests（另 3 個明示 opt-in provider tests skip）；真實 JetStream crash-before-ack redelivery 保持單次副作用；broker outage 與 replay safety 通過。
- 工作區：`main`，所有變更仍未提交；Groq key 只在 ignored mode-600 `.env.local`，tracked prefix scan clean。
- 真實／mock：NATS server 2.15.0 與 nats-py 2.16.0 為真實 L2；故障時點由測試控制。
- 下一步：T10 gateway/session/Origin/single-writer/snapshot/reconnect 與小型控制 UI。

## 2026-09-24／T10 交接

- 完成與變更：FastAPI loopback gateway、短效 session/Origin/Bearer auth、single-writer per client、bounded urgent/normal queues、snapshot/reconnect、turn/cancel/kill-switch APIs 與小型控制 UI。
- 驗收：`scripts/check` 通過 55 tests（3 real-provider opt-in skips）；慢 client 隔離、50 producers、100 reconnect、真瀏覽器 walkthrough 及 disconnect cleanup regression 通過。
- 工作區：`main`，所有變更仍未提交；Groq key 保持於 ignored mode-600 `.env.local`。
- 真實／mock：Uvicorn/HTTP/WebSocket/browser 為本機真實 L2；Core turn handler 尚為注入 port，T10 不執行工具或音訊。
- 下一步：T11 核實 AIRI commit/license/API，完成 speech/emotion/cancel/offline adapter spike 或記錄可重現阻礙。

## 2026-09-24／T11 交接

- 完成與變更：鎖定並稽核 AIRI `595ea7260d95d25a654572cfdd52e96cb9441290`；確認 MIT；提交公開 body API 的可重現缺口；選定最小 Web renderer；建立 speech/emotion/cancel/status port 與 fail-closed adapter。
- 驗收：`tests/contract/test_body_adapter.py` 覆蓋三種控制與 offline；完整 gate 結果見 T11 evidence。
- 工作區：`main`，所有變更仍未提交；Groq key 保持於 ignored mode-600 `.env.local`。
- 真實／mock：AIRI source/license/API 稽核為真實；body adapter 為 L1 合成 transport；未使用或宣稱假 Live2D 資產。
- 新決策與缺陷：AIRI 的 body 原語是 Stage 內部 API，公開 extension protocol 無直接 speech/emotion/cancel；改採最小 Web renderer。
- 下一步：T12 先完成 renderer transport/故障隔離；真 Live2D 動作與畫面因缺合法資產保持 BLOCKED-EXTERNAL。

## 2026-09-24／T12 部分交接

- 完成與變更：新增獨立 `/ws/body`、單 owner/單 writer renderer transport、有界 queue、offline/reconnect isolation，以及可實際開啟的 `/body` renderer shell。
- 驗收：`scripts/check` 通過 61 tests（3 real-provider opt-in skips）；A07 L1 證明 body failure 後文字/記憶持續及重連；真 Uvicorn/browser 顯示 renderer online，HTTP session 與 body WebSocket 成功。
- 真實／mock：gateway/browser/WS 為本機真實 L2 transport；角色只是明示 placeholder，沒有宣稱 Live2D。
- 外部阻礙：Cubism Core 為專有授權，官方 sample models 另受 Free Material License；需要 owner 接受適用條款並由官方來源取得 SDK/模型。
- 下一步：取得合法 SDK Core 與模型後接上 motion/expression/idle/look target，執行 kill/restart A07。

## 2026-09-24／T17 交接

- 完成與變更：五類記憶、migration 005/FTS5、identity/person/time/source/kind filters、衝突 semantic facts、revision/correction/deletion/derived invalidation，以及認證管理 API。
- 驗收：A10 固定 20 組為 20/20 top-5；A11 更正、刪除、scope、FTS rebuild、backup/restore 均通過；`scripts/check` 66 passed、3 opt-in skips。
- 工作區：`main`，所有變更仍未提交；secret 維持 ignored。
- 真實／mock：SQLite、FTS5、migration、backup/restore、ASGI API 為真實 integration；資料為 deterministic 合成 L1。
- 下一步：T18 實作 bounded/cancellable/idempotent consolidation、provenance、relationship revisions 與 trait clamps。

合法實作狀態：TODO → IN-PROGRESS → VERIFYING → DONE；有問題可標 BLOCKED-EXTERNAL/FAILED，解除後回 IN-PROGRESS。若只有模擬測試完成，寫「L1 完成，L2/L3 待驗」，不改成完整 DONE。

## 每次交接追加

```text
日期／任務：
完成與變更檔案：
驗收命令、結果、證據路徑：
目前 branch/commit/dirty state：
真實／mock／尚未驗證：
新的決策與缺陷：
下一步具體動作：
```

## 2026-09-30／Phase 1 現況稽核

依使用者新要求停止 integration implementation，只做 inspect/trace/verify/document。
稽核入口：[CURRENT_ARCHITECTURE_AUDIT](runtime-evolution/CURRENT_ARCHITECTURE_AUDIT.md)，完整索引見 [DOCUMENT_STATUS](runtime-evolution/DOCUMENT_STATUS.md)。原 T00–T40 任務卡與完成表未重寫；新增 reconciliation 說明產品接入與元件完成的差異。

本次 baseline：Python 193 passed / 1 failed / 5 skipped；失敗為 migration test 期待 10、實際 12。Rust 6 passed；ruff/mypy 通過。localhost:8000 health 連線失敗，未啟動服務或聲稱真 provider/硬體通過。既有原生 ModelMessage 介面仍未接 ConversationEngine；本次不繼續修改。Phase 1 文件完成，Phase 2 未開始。

## 2026-09-30／Phase 2 Runtime Evolution 設計

使用者授權設計 Phase 2。新增 runtime-evolution 的 SPEC、COMPATIBILITY_PLAN、MIGRATION_PLAN、ROADMAP；RT-001–015 全為 PLANNED。保留現有 Core/Character/Live2D/Qwen v1 音色，分階段補工具loop、執行取消、worker lifecycle、journal/recovery，再接 session/provider/browser/memory/scheduler。未修改 production，未執行migration或重启服务。規格門檻為設計目標而非實測。下一個可實作任務 RT-001。

## 2026-10-01／RT-001 完成

核對真 migration 升級/重跑/資料保留與正式 Gateway subprocess 啟停，僅修改測試。全套 198 passed、5 skipped；mypy/ruff 通過。證據見 `docs/evidence/RT-001/README.md`。真 provider/硬體未驗；下一卡 RT-002。

## 2026-10-01／RT-002 完成

optional native messages從IntegratedCompanion/CompanionCore送到ConversationEngine/adapters；主入口candidate opt-in，legacy預設保留。兩轮assistant/tool call_id與原目標payload整合測試通過。全套199 passed、5 skipped；最後相關5 passed；ruff/mypy通過。證據docs/evidence/RT-002/README.md。history僅RAM；本轮停止，不提前做RT-003。

## 2026-10-01／RT-003完成

candidate整批terminal才續模型、callback去重、唯一final、排隊取消及late輸出fence。HTTP拒絕輸入從true-only擴充bool，拒絕不執行。相關38 passed、全套206 passed/5 skipped、mypy/ruff/format通過；100合成交錯測試。證據docs/evidence/RT-003/README.md。未做RT-004，OS running清理仍RT-005；本輪停止。

## 2026-10-01／RT-004完成

candidate computer.execute接有界argv facade，兩pipe持续drain、共用64KiB；legacy保持原binding。真main兩profile結果回歸、100MiB洪流/timeout/exit測試通過；相關41 passed、全套213 passed/5 skipped、ruff/mypy/format通過。本機parent RSS採樣delta400KiB，測量界線詳evidence/RT-004。未做RT-005；本輪停止。


## 2026-10-01／RT-001–004 verification findings修正

修正RT-004 controller/executor profile不一致，startup binding固定。正式main兩profile中途env變動回歸先兩例FAIL、修後PASS；timeout測試確認PID回收；RT-003增加100completion-first與100cancel-first順序驗證。相關43 passed、最後batch8 passed、其餘baseline69 passed；ruff/mypy/format通過。未做RT-005，未真provider/GUI/GPU驗收；證據docs/evidence/RT-004/profile-freeze-fix/README.md。舊verification報告保留歷史，RT-004 DONE附修後證據。


## 2026-10-01／RT-005完成

candidate ExecutionContext從run/proposal傳到真argv executor；cancel/timeout owned group TERM→KILL/reap/drain，有界cleanup failure明報；auto/manual tool output fence。Gateway turn→session取消避免影響其他session，unknown ID不殺程序；legacy/explicit active alias相容。相關74 passed，全套229 passed/5 skipped，最後task-specific14 passed；ruff/mypy/format通過。三次parent-child取消約0.252s，100合成context交錯零late UI。scope patch/digests/evidence見docs/evidence/RT-005/README.md。

ack detach、escaped daemon、RAM guards/recovery、真服務/GPU/GUI仍受所列限制；未做RT-006，本輪停止。下一張可執行task為RT-006，但未開始。


## 2026-10-01／RT-005獨立驗證修補

原DONE被獨立writer驗證推翻：terminal後18個queued工具事件。candidate固定UI stream identity，補唯一writer與前端consumer fence，manual proposal關聯metadata；原queue公平仲裁、legacy、DB/config保持。競態fixture啟動與2秒cancel門檻分離、增加原task異常/iteration/stack診斷；歷史超時精確原因仍NOT VERIFIED。

原獨立反例1 passed、專項重跑15 passed、最終全套237 passed/5 skipped、ruff/mypy169files/format PASS。RT-005恢复DONE限已測fixture acceptance；原FAILED_VERIFICATION報告不改，修後證據docs/evidence/RT-005/delivery-fence-fix/README.md。真provider/GUI/GPU、active shutdown與部署rollback未驗；RT-006未實作，本輪停止。


## 2026-10-01／RT-006完成

candidate Qwen worker私有request/epoch配對、有界8個render、startup/render失敗及取消回收、poisoned隔離、close；真HTTP disconnect/active Gateway lifespan接入。保留v1 reference/model/語音演算法，legacy render相容。task14 passed、相關46 passed、全套251 passed/5 skipped，ruff/mypy170files/format PASS。真RTX3050首次25.7s、cache0.0022s、cancel0.277s、restart/close reaped、WAV PCM16/24kHz與reference SHA相容。

未人工聽測/真GUI/soak/部署rollback；單adapter owner，legacy故障路徑保留。精確patch、digests、測試/GPU metrics與限制見docs/evidence/RT-006/README.md。未做RT-007，本輪停止。


## 2026-10-01／RT-006維持PARTIAL／前端取消修補

原DONE撤回。原報告「前端取消fetch」不實已更正；補每speech AbortController/generation、pause/revoke與晚到結果fence，既有button在currentTurn已清空時仍能停止speech。新actual frontend Node6cases，相關25 passed；真隔離candidate頁面觀察生成中/播放中取消返回待命、Cubism角色可見。owner人工聲線/聽覺取消/畫面相容待回報，不能算PASS。最終全套257 passed/5 skipped、ruff/mypy171files PASS；scope patch見docs/evidence/RT-006/frontend-cancel-fix。保留獨立報告歷史；未做RT-007。


## 2026-10-02／自動選RT-006／PARTIAL人工gate

讀全部RT tasks/dependencies，排序最前未完成仍RT-006（RT-001 DONE）。前端/worker接線已存在；重跑相關25 passed，ruff/mypy171files PASS，127.0.0.1:8000驗收服務alive。只補roadmap過時current implementation註記/證據，未改production/test，未做RT-007。owner人工聲線/聽覺取消/畫面確認仍待回覆，不能升DONE；詳docs/evidence/RT-006/acceptance-followup-2026-10-02/REPORT.md。


## 2026-10-02／RT-006 DONE／owner人工驗收確認

owner針對聲線、聽覺停止、角色畫面驗收問題回覆「可以」，記錄於docs/evidence/RT-006/acceptance-followup-2026-10-02/OWNER_ACCEPTANCE.md；人工gate PASS，結合修後自動/GPU/GUI證據，RT-006更新DONE。原PARTIAL與獨立報告保留歷史，本輪只改文件，未重跑測試。長期soak/跨processGPUbroker/部署rollback仍未驗；未開始RT-007。


## 2026-10-02／RT-007 DONE

依全部task狀態/依賴自動選RT-007，RT-003/004 DONE。candidate descriptor統一現有schema/handler/readiness，逐回合快照及dispatch再查（含contextual task入口）；新增授權且去密鑰/v1/runtime診斷，保留legacy/env priority/public formats。

專項16 passed、相關73 passed、全套273 passed/5 opt-in provider skipped，ruff/mypy172files PASS；真Gateway network診斷與tools-off smoke PASS，精確scope reverse patch check PASS。JSON settings未載入如實報告；browser/model測試替身、真computer子程序；真provider/GUI/GPU/soak/部署rollback未驗，既有port8000未重啟。證據docs/evidence/RT-007/README.md。只完成本卡，未開始RT-008。


## 2026-10-03／RT-008 DONE

自動選最前PLANNED RT-008，RT-003/005/007 dependencies DONE。candidate同transaction建立run/journal，canonical context在provider前checkpoint，batch先commit，common orchestrator dispatch/observation hook覆蓋auto/manual；持久round/tool預算，startup unknown/not_dispatched配對與舊提案fence，不重播。新增授權readback與前端中斷提醒；既有enum/舊migration/config/body/voice保持。

四個真process crash + real file副作用fixture、partial batch/duplicates/budget/reopen/schema相容、真installed main network recovery PASS。最終專項12+launcher1共13 passed，相關92 passed，全套285 passed/5 skipped；ruff/mypy174files/format/reverse patch check PASS。

中途full suite有launcher failure，根因舊測試沿用default data套初版013後draft SQL變動；恢復最初013，未改DB checksum/刪資料，唯讀integrity ok；測試改隔離env/data，保留default DB additive013與歷史fail evidence。無私有內容進證據。恢復僅local readback、非自動續跑/OS效果驗證；真provider/GUI/GPU/soak/power loss/部署rollback未驗，port8000未重啟。詳docs/evidence/RT-008/README.md。只完成本卡，未開始RT-009。

## 2026-10-03／RT-001–008 Architecture Review

完成 `docs/runtime-evolution/ARCHITECTURE_REVIEW.md`，依十份設計／稽核輸入、RT evidence、實際 code/diff 與隔離反例評估 drift。整體 YELLOW，成果方向正確；run/proposal identity、dispatch terminal decision、handler cancellation 交界列 RED，只允許窄修補。未修改 production、既有測試、migration 或 roadmap 編號／狀態。

本次全套 `uv run pytest -q`：285 passed、5 skipped、3 warnings，52.53s；ruff PASS、mypy174files PASS。隔離 probe 確認跨run call-ID／restart衝突、provider FAILED後仍dispatch並completed、arguments-only handler取消terminal後仍執行；probe exit0代表反例成立，不是acceptance PASS。另記run/proposal RAM retention及跨repository耦合。證據在 `docs/runtime-evolution/verification/architecture_review_2026-10-03/`，RT-008十個完成digests吻合。未重跑真provider/GPU/GUI/Rust/硬體/soak/部署rollback；既有RT-006 owner人工驗收保留。

建議下一組RT-009、RT-010、RT-011 budget切片（不排序），先滿足報告中的RT-003/005/008交界修補gate；RT-011摘要與RT-013/015 DEFER，取消RT-010重複run recovery子工作，保留其他已解決成果。新阻擋項是candidate promotion與功能擴張gate，不把有限DONE歷史改寫成整體runtime已驗收。

## 2026-10-04／Architecture review 修復任務定義

新增 `docs/runtime-evolution/FIX_REGISTER.md`：AR-01/02/03 分為 REQUIRED_FIX，分別建立 RT-003-FIX-01、RT-005-FIX-01、FIX-001，均 PLANNED／未執行。各卡含來源、確認根因、最小範圍、禁止修改區、相容、測試、驗收、rollback 與風險。AR-04/05 保持 TECH_DEBT，不建立立即改造卡；其餘文件漂移、未驗條件、已修歷史事故與排除指控逐項分類。SPEC 不變條件仍成立，無證據推翻 Runtime Evolution 設計，未建立 ARCHITECTURE_CORRECTION。

更新 RUNTIME_EVOLUTION_ROADMAP：RT-003→PARTIAL；其餘已完成卡保持限定 DONE／歷史證據；插入三張 FIX、RT-009–015 各自 BLOCKED_BY_FIX，列直接／傳遞依賴及解除條件。RT-013/015 解除 FIX 後仍延期，RT-011 摘要延期。原 RT 編號不變。

本輪只有文件變更，未修改 production、tests、migrations、私人 DB 或運行中服務；沿用 2026-10-03 review 的反例與測試結果，未重跑產品測試，不宣稱修復成功。檢查 register 必填欄位、roadmap 狀態／gate、連結、source digest 不變與 diff whitespace。下一步只能依已定義 FIX 執行窄修補及獨立驗證，不能直接開發受阻 RT 卡；本輪授權止於定義任務。

## 2026-10-04／FIX-001 DONE

只修 AR-03 failed/cancelled generation dispatch gate；第一輪／續作先判斷 COMPLETED，Core partial text 保留但 rejected calls 不進 canonical accepted history，原錯誤/取消狀態及 rejected intent 留 final 診斷，既有 observation 不抹除。production 只改 integrated.py／companion.py；不改 transport、schema、executor 或配置。

修前24正式反例FAIL；最終32專項PASS（加真generation deadline）、相關91PASS、全套317PASS/5 opt-in real-provider/speech skipped、ruff/mypy174files PASS。另組HTTP四情境＋真effect file、隔離修前caller回退reader/text-only/no-replay PASS；部署rollback/真provider/GUI/GPU/soak NOT VERIFIED。完整原失敗/fixture修正紀錄、patch、scope與逐項驗收見 docs/evidence/FIX-001/REPORT.md。108個其他review指紋與013 checksum不變，原dirty工作保留。

FIX-001 DONE；RT-009此gate解除為PLANNED但未開始；RT-011/015保留其他blockers/DEFER。RT-003維持PARTIAL，RT-002/008限定DONE不擴大。剩餘兩張FIX仍PLANNED。本輪完成停止，不自動開始下一FIX或RT。

## 2026-10-04／RT-003-FIX-01 DONE

provider-local call ID 與 candidate private storage identity 分離，既有 proposal UUID＋exact journal binding 同transaction建立；公開call ID、HTTP approval、model pairing保留。callback/reconcile精確owner、legacy crash-gap/no-replay相容；run-scoped dedup terminal清理。不新增migration/架構，production限integrated/orchestrator/runs，保留全部既有dirty與FIX-001。

修前2FAIL、專項/原source65PASS、擴大相關125PASS、全套326PASS/5 opt-in skip、ruff/mypy174files PASS。真process before/after atomic binding crash與transaction rollback、混合新舊row/unknown、manualHTTP、A/B、oldcallback、same-run duplicate PASS；獨立真file三run/restart各一次效果及保留reader/guard的caller回退無重播PASS。部署rollback/真provider/GPU/GUI/soak未驗。見 docs/evidence/RT-003-FIX-01/REPORT.md。

RT-003恢復DONE/VERIFIED；RT-010、RT-011 budget的FIX gate解除，summary/RT-014仍有原依賴。RT-012/015仍待RT-005-FIX-01。使用者本輪授權剩餘FIX逐張處理；本卡已完整通過後才開始RT-005-FIX-01，未開始任何後續RT。

## 2026-10-04／RT-005-FIX-01 DONE／剩餘 FIX 修復完成

candidate共用invocation納管arguments-only task，取消一次並最多4.75s等待；拒絕/延遲cleanup用FAILED/ExecutionCleanupError與journal unknown，保留task owner至實際結束，無late UI/新dispatch。fixture先證明browser enter取消洩漏，再修startup acquisition/close/finally stop；現有application caller保護spawn與ack前ownedgroup，ack後user-managed維持。只改orchestrator/gateway既有caller/browser；execution.py、schema、授權與其他已完成FIX保持。

修前handler/browser3FAIL；launcher spawn/pre-ack2FAIL、ackPASS。最終專項33PASS、相關147PASS、全套344PASS/5 opt-in real-provider/speech skipped、ruff/mypy174files PASS。真本機headless Chrome取消關閉connection/Playwright、GTK/Firefox caller真synthetic程序spawn/ack、A/B、HTTP manual、shutdown、5s cleanup failure/unknown與原argv/batch/races/terminal fence PASS。獨立真filecleanup前於terminal約0.027s、精確pre-FIX source legacy text-only回退保留journal/no-replay PASS。真GUI/escaped daemon/GPU/soak/部署rollback NOT VERIFIED，不能聲稱所有外部效果停止。詳 docs/evidence/RT-005-FIX-01/REPORT.md。

FIX_REGISTER三張FIX全DONE；RT-003 DONE/VERIFIED；RT-009/010/012、RT-011 budget解除FIX gate但未實作。RT-011 summary/RT-013/015仍DEFER，RT-014仍依賴RT-010，retention/single-owner與外部release gates保留。本輪依使用者授權逐張完成剩餘兩FIX後停止，沒有開始新的RT、重構或重啟私人服務。

## 2026-10-05／修復請求現況核對

使用者要求修復後，核對工作區發現三張 FIX 已於 10-04 完成；本輪閱讀修復 evidence 並查核 generation gate、run-scoped dedup／atomic proposal binding、共用 handler task ownership，未重複修改 production 或開發後續 RT。

本次執行 `uv run pytest -q tests/integration/test_agent_batches.py tests/integration/test_run_journal.py tests/integration/test_tool_orchestrator.py tests/integration/test_execution_lifecycle.py tests/integration/test_gateway_main.py tests/integration/test_gateway_terminal_fence.py`：103 passed、3 dependency warnings，42.33s，exit0。`uv run ruff check src tests` PASS；`uv run mypy` PASS／174 files。本輪未重跑全套、真provider/GPU/GUI/soak/部署rollback，先前344PASS/5skip仍為歷史結果。三FIX維持DONE，無新已確認修復缺口；技術債與其他RT保持原狀。


## 2026-10-05／RT-009 DONE

自動核對全部RT/dependencies/FIX gates，選最前PLANNED RT-009（RT-007/008 DONE、FIX-001 gate解除）。candidate main沿用原provider priority，包既有FailoverModel；每generation最多2invocations，僅transient pre-emission重試，text/tool/finished與OpenAI緩衝片段failure均禁止再attempt。取消backoff、request privacy/messages/output budget與新private generation ID保留；legacy與SIRO_MODEL_RETRY_ENABLED=0使用原單provider，startup固定。

main沒有費用budget，額外cloud request固定0，不因local旁已有key就新增cloud fallback；direct wrapper explicit request-count budget不代表USD/day會計。必要adaptererror note保留原error class；不改port/schema/FIX/core/body/audio/identity。專項32PASS、相關153PASS、全套376PASS/5 opt-in skip，ruff/mypy176files/format/reverse patch check PASS。真local HTTP transport fixture與main/Core/SQLite/ASGI＋真Python fileeffect通過；models合成，真provider/GUI/GPU/soak/部署rollback未驗，私人DB/服務不碰。詳docs/evidence/RT-009/REPORT.md。本輪只完成此卡，未開始RT-010。

## 2026-10-05／RT-009 verification repair DONE

獨立報告指出wrapper固定name=failover造成selected provider durable backend regression；已重現並先標FAILED_VERIFICATION。最小修正僅failover.py在constructor捕捉primary.name，保持Integrated→SQLite→readback原consumer鏈；名稱不隨attempt變動，無schema/API/配置格式變更。補main local/cloud retry on/off真SQLite與fresh-store readback assertions及fallback name穩定契約。修復前6FAIL/3PASS；修復後專項含原獨立test35PASS，全套378PASS/5 opt-in skip/3dependency warnings；ruff/mypy176files/scoped reverse patch dry check/diff whitespace PASS，roadmap恢復DONE。

既有failover rows不猜回provider；metadata是selected-primary、不是attempt audit。真provider/GUI/部署rollback/soak仍NOT VERIFIED，未碰私人DB或重啟8000，未開始RT-010。D25與 docs/evidence/RT-009/provider-metadata-fix/REPORT.md 保留修復diff/logs/digests；原獨立驗證與原implementation report保留歷史。

## 2026-10-05／RT-010 DONE

自動掃15張RT選最前PLANNED、dependency滿足的RT-010；RT-008 DONE且FIX gates解除，RT-009 metadata修復保留。重用completed version1 canonical journal，exact session/同privacy取最新6完整raw user/final assistant pairs（12messages），接新system/current raw user native roles。Core為單一append owner，continuation不重hydrate；不讀legacy assembled messages、不複製舊system/tool intents或unknown effects，恢復未知run仍RT-008 readback-only；無journal重建、migration/identity/memory/affect/audio變更。candidate startup固定SIRO_SESSION_RESTORE_ENABLED，0保留舊working path。必要Integrated/Gateway接線超expected清單記D26。

改4production：core/companion.py、agent/runs.py、presentation/integrated.py、gateway.py；加test_session_restore.py，native serialization舊test分restore on/off保留原pair斷言。temp pre-task source在第二startup重現缺dialogue；專項/相關15PASS，最終全套388PASS/5 opt-in skip/3dependency warnings（89.73s）、ruff/mypy177files/format/scoped reverse patch dry check/whitespace PASS。首輪full386PASS/1FAIL是舊test對candidate無跨run對話假設，已按D26新契約分on/off驗收，保留初次log；首個before launcher系統Python無pytest亦保留並修正。

驗收層級actual main/Core/SQLite/ASGI lifecycle三次重啟＋actual Python subprocess；provider/transport合成，未等同真daemon/GUI/provider/GPU/soak/power loss/部署rollback。只恢復completed recent dialogue，不含整段工具transcript、cancel/failed/direct-command history；12則不是token budget，retention/single-owner限制不擴張。私人DB/8000服務未碰。docs/evidence/RT-010/REPORT.md保存selection/source snapshots/patch/digests/logs/rollback。只完成RT-010，RT-011及其他卡不開始；下一輪重新選卡。

## 2026-10-05／RT-011 PARTIAL（byte guard實作完成）

自動核對15RT，選最前PLANNED且RT-002/010依賴滿足的RT-011 budget切片；summary仍DEFER，只此卡。D27先記discrepancy：目前無provider tokenizer/context-window metadata，byte cap不能當token-limit PASS；整卡PARTIAL不標DONE。services/agent/context.py新增最小LanguageModel wrapper，測complete logical ModelRequest compact JSON UTF-8 bytes；candidate main包在FailoverModel外，預設65536bytes，SIRO_CONTEXT_MAX_BYTES=0關guard，startup固定；name保留selected provider，無超限retry。超限ContextBudgetExceeded走原Core FAILED/terminal/journal/readback，goal/system授權來源/pending pair不截斷、不刪。必要gateway.py接線超expected清單已記；不改Core/migration/model port/音色/affect/memory，也不做summary。

test_context_budget.py專項8PASS；最終全套396PASS/5 opt-in skip/3dependency warnings（85.84s）；ruff/mypy179files/format/scoped reverse patch dry check/whitespace PASS。before main重現64-byte cap未生效仍COMPLETED；actual main/Core/SQLite/ASGI feature-on/off/legacy、exact UTF-8 boundary、request identity、cancel、provider provenance、400k工具結果先一次handler後零continuation provider、完整goal/tool pair readback通過。provider/executor合成，不能標真服務/副作用PASS。measurements.json只合成size數字；無私有資料。

Required remainder：verified selected provider tokenizer/context-window metadata、input+reserved-output budget及真token boundary gate；byte/logical-json尺寸不等於token/HTTP framing/peak RSS。真provider/GUI/GPU/soak/power loss/部署rollback仍NOT VERIFIED。SIRO_CONTEXT_MAX_BYTES=0下次drained startup回滾、DB保留；私人DB/8000未碰。docs/evidence/RT-011/REPORT.md含selection/snapshots/patch/digests/logs/measurement。只此卡並停止，未開始RT-012。


## 2026-10-05／RT-011 budget DONE／native gate補完

依使用者繼續補完授權，只補RT-011剩餘native gate。pinned GPT-OSS20b官方tokenizer/template/hash、selected Groq profile/context/output reserve、同adapter payload、thread counting/cancellation、missing/unknown fail-closed已接candidate實際路徑；byte guard獨立。D28記scope必要adapter/gateway/dependencies調整；不改Core/schema/affect/音色。Summary仍DEFER。

專項23PASS、executor34PASS、full411PASS/5 opt-in SKIP/3 dependency warnings；ruff/mypy181files/format/wheel inclusion/scoped reverse dry check PASS。官方HF四case counts一致；兩組真Groq合成probe79/83、176/170差異在256餘量內，未保存key/private dialogue。官方reference與server framing不宣稱完全相同。初次harness及synthetic fixture失敗log全部保留。

GUI/GPU/power loss/soak/deployed rollback NOT VERIFIED；其他models未profile時明報，fresh checkout需setup public assets。私人DB/8000服務未碰。Native0/byte0各自停對應guard，下次drained startup回滾；無migration。完整證據docs/evidence/RT-011/token-completion/REPORT.md。只本卡budget DONE並停止，未開RT-012。


## 2026-10-05／RT-012 DONE／持續 browser session

自動核對15RT，選最前PLANNED且RT-005/007與FIX依賴滿足的RT-012。新增service BrowserSessions wrapper包既有ScopedBrowserDriver；candidate main/catalog/contextual executor以trusted ExecutionContext.session_id擁有driver。保持navigate+read舊url契約，加read/fill/click/close candidate工具；同origin跨run保留page/sessionStorage，epoch+原DOM hash拒cross-session/recreated/stale目標，操作回fresh readback。TTL300s/cap8/action30s、token/repeated task cancel/explicit close/shutdown及cleanup failure明報；無credential persistence。driver Core、Core identity/affect/audio/model assets與DB格式未改。D29記必要caller/schema與shutdown hook；shared WS無canonical owner mapping，disconnect走idleTTL。

專項/相鄰33PASS；full419PASS/5 opt-in SKIP/3 dependency warnings（127.82s）；ruff/mypy183files/format/hash/reverse patch dry check/whitespace PASS。真headless Chromium本機合成跨頁form/A-B/stale/cancel、actual main兩run模型consumer/SQLite/lifespan及feature-off/legacy回stateless驗證PASS；model/body合成，未當成真人GUI/真provider規劃驗收。before source真main無actions/readback反例與初次inventory2FAIL保留logs。Source精確5files patch/snapshots/digests見docs/evidence/RT-012/REPORT.md。

Remaining implementation blockers：NONE。限制是ephemeral single-Gateway/browser scope、origin change reset、error close、already-performed effects不可undo；更廣GUI/long soak/power loss/private deployment屬產品release gate，不列本卡未完成feature。Rollback於下次drained startup SIRO_BROWSER_SESSION_ENABLED=0，先close owned browsers，保留DB；isolated行為已驗，私人部署未動。未重啟8000或碰privateDB、未開始RT-014/任何下一卡；下一輪重新核對roadmap。


## 2026-10-05／RT-014 DONE／有來源的 owner memory ingress

核對15RT，RT-013/015 DEFER；RT-014舊BLOCKED依賴RT-010實已DONE，記discrepancy後只選RT-014。candidate server-recorded UserTextEvent明確leading記憶要求接MemoryService/既有SQLite add/revision，固定identity siro/person owner與original source/session。UUID5 same-event去重、episodic user statement不寫SemanticFact/persona；model/tool continuation不接ingress。Commit後提供sourced verified context，失敗FAILED且零model；cancel/terminal fence保留。既有correct/delete/revisions API與active recall跨重啟通過。

D30必要Core/repository/Gateway wiring加optionalroute filter：candidate cloud僅可讀all sources cloud_allowed，local/unknown sources不外送，原user event local_only不降privacy；legacy/defaultAPI保持。SIRO_MEMORY_INGRESS_ENABLED startup固定、0停未來writes但不刪memory/撤filter。無schema/dependency/HTTPWSformat/identity/affect/relationship/retention改變。

專項/相鄰27PASS；full426PASS/5 opt-in SKIP/3 dependency warnings（152.36s）；ruff/mypy184files/6fileformat/hash/reverse dry check/whitespace PASS。actual main/ASGI/Core/SQLite四lifecycle、source/provenance及fresh model consumption、真argv malicious remember output不成fact、synthetic cloud無localmemory、failure/empty zero-provider與rollbackfixturesPASS。before main missingmemory反例與initialfixture診斷均保留。docs/evidence/RT-014/REPORT.md含精確6source/test檔patch/digests/before。

Remaining production blockers：NONE。限制為explicit markers／existingAPI mutations、owner statement非外部truth、localonlymemory不自動授cloud、memorydelete不清rawconversation；原retention維持。更廣真人GUI/longsoak/private deployment另releasegate，未假稱完成。下次drained startup flag0回滾futureingress，DB/revisions保留；私人DB/8000未碰。完成只此卡並停止，RT-015保持DEFER。

## 2026-10-06／Runtime Evolution architecture review（無 production 修改）

更新 docs/runtime-evolution/ARCHITECTURE_REVIEW.md，審查近期 RT-009/010/011/012/014 與舊 FIX，整體 YELLOW。舊 AR-01/02/03 已由三項 FIX 解決，不重開。隔離組合探針確認 AR-06：native guard 不接受多 tool_calls transcript，兩個效果完成後 continuation 失敗；native off 同案例 completed。AR-07 為靜態確認的 clean CI tokenizer provisioning 缺口，未執行 remote CI。建議完整 native integration PARTIAL、相關 rollout BLOCKED_BY_FIX；不改原 RT 編號或 DONE 歷史。本輪未改 roadmap、production、私人 DB 或服務。

10-05 本輪專項七組 81 PASS／3 warnings（23.98s）；ruff PASS、mypy 184 files PASS。未重跑 full suite；RT-014 的 426 PASS／5 SKIP 僅歷史證據。26 個近期 evidence source digest 一致。探針、結果、指紋、舊 review 歸檔與執行紀錄見 docs/runtime-evolution/verification/architecture_review_2026-10-05/。

下一範圍：RT-011 局部相容性與資產驗證修復；RT-012 pool lifecycle、RT-014/010 privacy/revision/restore 組合驗證，無排名。RT-013/015 與 summary 維持 DEFER，不為湊三張任務啟動新功能。部署 rollback、真 provider 完整閉環及長時間 soak 仍未驗證。

## 2026-10-06／三項 DEFER 規劃

新增 docs/runtime-evolution/DEFERRED_TASK_PLAN.md，定義 RT-013 caller/parity/收益、RT-015 retention/single-owner/foreground、RT-011 summary 需求與 source invalidation 的 evidence slice、解除條件、最小 scope、tests、rollback 與 CANCEL 條件。三項保持 DEFER，無排名／新 RT 編號／production 修改。Roadmap 更正 RT-015 依賴已完成，補上 AR-06/07 目前 gate 與規劃連結，不覆寫原完成歷史。本轮僅文件檢查，未執行功能測試或規劃中的量測；下一步為依各項 gate 收集隔離證據，再決定是否施工。

## 2026-10-06 / AR-06 + AR-07 repair; DEFER gate evidence

Private counting-only normalization now permits exact completed multi-call batches and conservatively counts all arguments/results; no wire/journal/executor change or effect replay. scripts/check provisions pinned public tokenizer before pytest. Before rejection now passes; actual main/Core/SQLite + real tool subprocess normal/oversized regression fixtures PASS. Native suite 19PASS; full430PASS/5 opt-in SKIP/3 dependency warnings; adjacent9PASS; product ruff/mypy184files/schema/changed-file format/shell syntax and isolated reverse-patch dry run PASS. Evidence docs/evidence/RT-011/ar06-ar07/REPORT.md.

Whole-repository lint/format remain failing due evidence artifacts and existing formatting in two unrelated tests; remote/full clean-check CI not executed. Do not report overall CI PASS. No private data/provider calls/live8000 restart.

DEFER gates checked: RT-013 has no matching scoped production caller/benefit; RT-015 retained100 completed keys after active0, cleared only onclose; RT-011 six-pair synthetic history fits6736 tokens, summary need/source gate unproven. Three remainDEFER with reasons in DEFERRED_TASK_PLAN, not merely forgotten status. Next bounded work is identifying a necessary background caller and specifying bounded owner/retention before RT-015 pump implementation; no automatic Rust/summary feature.

## 2026-10-06／DEFER 能力需求研究（無程式變更）

新增 docs/runtime-evolution/CAPABILITY_NEEDS_RESEARCH.md。對照 PLAN/EXPERIENCE 與 consolidation、memory revision/delete 實作，支持先研究 RT-015 閒置來源記憶整理；第一步限定候選與來源核對，不直接啟用目前可 committed 的 consolidator。記錄 event provenance 與 parent-memory derivation/revision 的差異，須驗證更正刪除閉環。RT-013 尚缺真 caller／目錄需求；RT-011 用合成案例分辨窗口遺失、超限及 AR-06，不直接採摘要。三項維持 DEFER，未寫程式、未跑新功能測試、未使用私人資料；CI 格式未驗，與 AR-07 資產問題區分。

## 2026-10-06／RT-013、RT-015、RT-011 summary 產品交付 DONE

依使用者「不要延期了，都做，要看到產品成果」明確授權，完成 D31 有界切片。RT-013：專用工作目錄，signed scoped Rust read/list，同時供模型 orchestrator 與明確 owner UI 讀取；中文路徑、越界、tools switch、取消與程序收尾已驗。RT-015：單一 lifespan owner、本機有來源記憶歸組、100筆/5秒、合併trigger、前景取消、更正／刪除後來源核對與可丟棄view；不自動寫facts／人格或送cloud。RT-011：24組bounded restore、本機extractive source-hash摘要、保留目標/system/pending/latest，最終仍經原budget；memory mutation fence/cutoff，raw journal保留。三張原編號保留，DEFER解除；通用semantic consolidation／無限歷史不在完成宣稱。

新控制頁提供工作目錄讀取、整理開關、記憶更正刪除、摘要狀態。scripts/start-runtime-product 可啟動；PRODUCT_QUICKSTART.md 記設定與回滾。隔離離線預覽 http://127.0.0.1:8026 已啟動，只有合成資料；未取代私人服務、未動私人DB／key／GPU／角色資產。

最終 full suite 437 PASS／5 opt-in SKIP／3 warnings（93.84s）；last stat-check refinement後 workspace 2 PASS；Rust workspace tests PASS（library6）；ruff format/check whole repo PASS，mypy191files PASS、schema/shell syntax PASS。瀏覽器真UI Rust列檔讀檔、更正刪除、整理暫停/重整與零page errors PASS。七天fakeclock不是七天soak。初次6個舊catalog/shutdown fixture failure已修，原log保留；中文grant hash相容性另補實測。remote CI、真provider/語音/GPU/private部署rollback與長soak未驗，不把skip算PASS。

證據 docs/evidence/runtime-product-2026-10-06/REPORT.md，包含source-only patch/digests/isolated reverse dry-check、UI截圖與log。既有未提交變更保留。回滾採drained restart三個flags off，保留DB/journal/native/privacy guards；不倒回整個dirty working tree。下一步是以實際模型與使用者工作檔操作這三個入口，產品品質驗收不再以這三張DEFER為由停住。

## 2026-10-07／Companion 真實產品體驗修復

依使用者對文字、工作目錄與角色體驗的回饋，完成 D32 局部修復。正式 launcher 載入既有 allowlisted 模型設定、校驗 native profile 與本機 Live2D；缺條件明報，不再用 offline 固定回答充當產品。首頁以單一 Haru 與自然對話為主，既有 computer.execute 一般帳號能力露出，工作目錄退為次要讀檔入口。最新表情可在載入／斷線恢復，不重播 speech/effects；舊 socket 不會斷開新 owner。移除 SDK 隨機表情／切換及 sample voice，表情以真 Cubism files 套用，保留本機 licensed assets。

修正 HTTP 晚回應復活已完成 turn、多提案互相覆蓋／授權藏起、空 provider output 被誤判完成；final reply 用安全 DOM 格式化，語音可獨立關閉。補記憶保存／自動來源／bounded restore／雲端可見範圍的 runtime facts；偏好也依原來源 privacy 過濾，雲端不含本機 preference subjects 或衍生自由文字 affect reason。本機 appraisal／完整畫面不變，無新 schema／抽象／provider fallback／RT 改號。

最終 full pytest：460 PASS／5 opt-in SKIP／3 existing warnings，105.31s。整 repo Ruff check／format PASS（255 files），mypy195files PASS；schema／shell syntax／diff whitespace PASS。實際已設定模型＋隔離合成 DB＋本機真 Linux 工具＋licensed Cubism 的 greeting／記憶能力問答／uname與df→自然結果整理 PASS；F05 reload/tap與F08像素畫面變化、手機無橫向 overflow、零 page error PASS。Renderer tsc/vite build與idempotent PASS。較早一次 continuation HTTPStatusError 尚UNKNOWN，fresh合成probe與完整新run成功；未重送已完成工具，不把後續成功稱為根因已修。

原8026離線示範以 owned PID／cmd／data dir核對後正常停止；原.siro-data/siro.db已先做本機一致備份（backups/pre-companion-20261007/siro.db），新8026沿用原持久資料與設定。未將私人聊天／DB／key寫入evidence；真模型驗證只用隔離合成資料。已刷新使用者 in-app browser 並看到新版路由與 Live2D 已就緒，未對私人 store 提交測試對話。

證據 docs/evidence/companion-experience-2026-10-06/REPORT.md（沿用啟動修復時資料夾名；本輪日期10-07），含測試log、真模型合成結果、畫面、來源hash／process metadata。自動審核曾拒絕已保存對話的診斷重播，未執行；改用全新合成訊息。既有dirty內容保留。語音GPU口型、長soak、remote CI／發布與部署回滾仍未驗；雲端不自動讀本機限定記憶。下一步為產品實際使用與間歇provider錯誤可重現診斷；不以新抽象或重做既有RT代替體驗改善。

## 2026-10-07／桌寵、主動性、安全技能成長規劃與搜尋 FIX 定義

依使用者「只規劃就好」，新增 docs/runtime-evolution/COMPANION_EVOLUTION_PLAN.md，涵蓋桌寵真平台驗收、單一 body／音訊 owner 與安全換證、未完成任務主動追蹤、既有技能 catalog／worker 接入、OS 隔離的候選驗證、可信啟用與保留最新資料的程式回退。規劃沿用原 Core／Identity／Memory／Runtime，不新增平行工具框架、不重開已完成 RT、不把 helper 當成產品整合完成。

靜態確認 ProactivityRules／SkillDispatcher／procedural candidates 尚未進 Gateway 產品閉環；PatchVerifier 為同帳號目錄複製與 checks，不是 OS sandbox；技能 hash 未涵蓋執行碼／依賴；ReleaseManager 的 active pointer 尚非 launcher 部署，簽章未覆蓋全部相容欄位且 DB rollback 可能覆蓋較新寫入。這些是自主能力接線前的驗收門檻，尚未啟用或修復。本輪核對基準 c1d2d41，開始時 git status clean。

使用者另回報 Bing 搜尋 ScopeViolation。新增 FIX_REGISTER 的 FIX-002（REQUIRED_FIX／BAD_INTERFACE＋TEST_GAP／MEDIUM／PLANNED）：已確認 orchestrator 只留 exception 類名造成診斷資訊遺失；當次搜尋根因 UNKNOWN — NEEDS INVESTIGATION。畫面 Markdown 可能不是 raw arguments，candidate 完整 Markdown 理應先遭 schema 拒絕；driver 另有任何跨 origin 子資源被擋即整頁失敗的機制，尚未證明當次由此觸發。規劃以合成頁面分辨原因，不放寬 origin／redirect 邊界、不重播私人查詢。

Roadmap 只追加本輪規劃入口與 BLOCKED_BY_FIX：自動網路研究 promotion；桌寵與本機唯讀提醒不受該 gate 阻擋。RT-012 與其餘 RT 的 DONE／歷史編號保留。未建立 ARCHITECTURE_CORRECTION：目前證據未推翻原受限 Runtime／相容／來源設計。

本輪僅文件變更與靜態檢視，官方 OpenClaw／Electron 文件研究；沒有 production 修改、安裝、服務操作、私人 DB 讀取、功能測試或上述規劃驗收。git diff --check exit0；三份規劃／FIX／roadmap 的本機文件連結檢查零缺失，新規劃無尾端空白；變更範圍僅四份 Markdown。未重跑先前460PASS，不能將歷史結果算本輪通過。下一步待使用者要求實作時，先依 FIX-002 重現搜尋；桌寵按選型驗收做最小外殼，主動唯讀用途可獨立推進；自主啟用嚴守隔離與資料回退 gates。

## 2026-10-07／桌寵定義更正：自由活動與動作製作（只規劃）

使用者明確表示桌寵要能自主在螢幕走動、選擇活動，缺少動作由我們生成製作。更新 COMPANION_EVOLUTION_PLAN 與 roadmap，將自由漫遊／玩耍／休息列為正式完成條件；固定停靠、只可拖曳、站姿平移只能算降級／原型。拆清低頻活動選擇→單一 presentation 場景 owner→renderer，不將逐幀路徑／動作放入 Core、不把桌面玩耍當成任意 OS 操作權限。

唯讀檢查本機 Haru metadata：42 個現有參數無腿／膝／腳步；27 motion 中 model3 只掛 Idle2／TapBody4，無已驗 walk／play；本機資料夾無 PSD／CMO3／CAN3。未讀 binary／texture，不能據此判斷畫面裁切。新增我們負責的角色設計／圖像生成／可編輯分層／全身 rig／motion／資產包驗證流程；圖片生成不當成已完成綁定。核實官方 Haru 可編輯來源與 Cubism 製作／輸出說明、Editor Windows／macOS 支援；Linux renderer 不等於 rig 製作環境已備妥。

規劃補上情緒／身體位置／嘴型獨立控制、停止走路不清 expression、活動 generation fence、真 GNOME／Wayland 全 output 透明場景候選、動作包版本與回退。桌面場景原型、全身製作可並行，兩者與活動控制通過後才算自由桌寵。搜尋 FIX-002 gate 保留且只影響自主網路研究。

本輪仍只改規劃文件，未生成圖像／動作、改程式、安裝／啟動服務、操作私人資料或執行功能驗收；原有未提交變更保留。下一步實作時先打通場景透明／命中／漫遊與可編輯全身資產工具鏈，再以站立→起步→步行→停止／轉向→坐下／玩耍→可打斷的真畫面驗收，不將 helper 或影片預覽當完整產品。

## 2026-10-07／對話紀錄唯讀檢視與語音需求澄清（只規劃）

使用者追加授權「檢查最近的對話紀錄」，並澄清語音為生成等待太久、長文講不完。本輪依授權以 SQLite mode=ro／query_only 檢視當日15:40–16:07的14個run，另檢查服務狀態碼與8個WAV headers；未播放、生成、重播或匯出私人內容。早先條目「未讀私人DB」描述其原時點，本條為後續已授權唯讀檢視。

新增 docs/runtime-evolution/CONVERSATION_VOICE_REVIEW.md，僅存匿名現象／聚合與合成驗收。10 completed／4 failed（3 HTTPStatusError、1 ValueError）；至少3個completed final句中結束。failed journal所帶舊assistant不算本輪回覆，4個failed均無新的非空final。靜態確認adapter忽略finish_reason／非空EOF誤完成；實際截斷原因尚UNKNOWN。Gateway token TTL300秒、UI不續期，受檢log有4筆turns401；不能因此把上游HTTPStatusError全部歸因token。

語音現路徑為完整文字terminal→整段生成→完整blob→播放；現有segmenter未接此caller。Qwen worker codec max_new_tokens512，與文字output budget512不同；兩個近期WAV header同為40.88秒，未聽驗或取得EOS，僅為觸頂假設。現行冷／暖速度、尾句缺失根因未知，歷史cold25.700秒／cache hit不當成本輪效能。規劃先沿用聲線、單worker／一段預取分句播放與完成／版本快取，再有條件接final-answer完整句提早生成；保留cancel／epoch／owner，不能只翻streaming旗標或暗中省略全文。

FIX_REGISTER追加FIX-003（終止完整性）、FIX-004（session續期）、FIX-005（分段語音與延遲／尾句）、FIX-006（自身故障context與合成多輪ablation），均REQUIRED_FIX／PLANNED，每卡含evidence、未知根因、最小scope、禁改區、測試、acceptance、rollback與risk。COMPANION_EVOLUTION_PLAN及ROADMAP合併自由活動桌寵／對話／語音三項補充；搜尋FIX-002保留。BLOCKED_BY_FIX只限各相關產品promotion，不阻擋素材／場景原型／本機唯讀整理，不重編RT、不撤原DONE、不新增無證據architecture correction。

文件檢查：git diff --check PASS；四份規劃／review／register／roadmap共67個本機連結零缺失，FIX-003–006必填欄位完整，無尾端空白。只改五份Markdown；工作樹另有未追蹤本機WAV，本輪未修改、刪除或納入證據。未重跑歷史460PASS、未跑功能／真provider／語音／桌面驗收，未改production、寫DB、安裝、生成資產或操作服務。下一步待要求實作時逐卡重現／局部修復，理解品質需真provider合成對照，不能以mock或更多abstraction代替產品改善。

## 2026-10-07／FIX-003 實作與限定驗收完成

使用者已授權「照三份文件開始實作，驗收重要」。依AGENTS逐張進行，先完成FIX-003：OpenAI-compatible以typed nonretryable原因區分length/filter/不明終止/裸EOF；partial保留、工具終止前不yield，取消優先、串流確實收尾，cleanup error不洗掉主原因／buffered-intent fence；UI半句後仍顯示未完成且不朗讀成功。原Core/ports/其他provider/budget/schema不變，沒有私有DB寫入或服務重啟。

證據 docs/evidence/FIX-003-2026-10-07/REPORT.md。修前15FAIL；相鄰149PASS/3warnings；最終adapter/retry/UI/真HTTP→controller→SQLite81PASS/3existing warnings(7.05s)；mypy196files與changedRuff PASS。真配置模型只用合成新訊息，共兩輪4個有界request，最終正常短答與故意output-limit PASS；首輪發現asyncgen關閉警告後補explicit close與新反例，修後無該警告。兩個新整合fixture先誤認candidate私有call ID，已改精確proposal/journal binding、不改production契約；獨立review再指出cleanup錯誤覆蓋／取消／retry問題，新增修前3FAIL反例並修復，最終review無剩餘本卡blocker。

隔離source apply/reverse/完全恢復PASS，source.patch/digests/rollback.json保存；非部署rollback。未跑本輪full pytest/remote CI、未修改私人資料／語音快取、未驗桌寵／TTS。既有dirty文件／本機WAV保留。FIX-003 DONE/VERIFIED只限本卡，近期樣本截斷根因仍UNKNOWN；FIX-004/005/006及搜尋gate保留。下一張已獲授權FIX-004：在FIX-003 UI基線做single-flight換證、跨TTL真UI／無效果重送與token retention驗收，再推進語音與桌寵。

## 2026-10-07／FIX-004 session lifecycle 實作與驗收完成

FIX-004 DONE / VERIFIED，報告 `docs/evidence/FIX-004-2026-10-07/REPORT.md`。沿用300秒TTL／Origin／loopback／Bearer；頁面單一按需換證、5秒bootstrap timeout／3秒冷卻，只有精確pre-accept401可補證後重試一次，其他未知結果不重送。Gateway過期token清理與128有效token上限／滿額429，不驅逐有效頁面。控制連線snapshot才ready，owner／epoch／retired fence與最多三次自動重連；正常換證不動control/body。逾時／關頁清等待，取消與新輸入阻止舊的排隊發送；復原未送草稿，不將已送unknown當未送。

修前factory兩反例與control五反例均轉綠；相鄰123 PASS，獨立control18＋factory26共44 PASS。整體首輪552 PASS／2 FAIL：journal test舊擷取接點、completion-before-cancel fixture2秒等待在SQLite await逾時；局部修fixture後兩組61 PASS。前置completion wait有界10秒，取消後2秒及effects／terminal斷言保留；另Gateway直接cancel2秒仍驗。實際SQLite慢因未知，不臆測磁碟／鎖／排程問題。最終 `.venv/bin/pytest -q -m 'not real_provider'`：554 PASS／5 opt-in未選／3既有warnings，99.87秒。mypy199 files、全repo Ruff lint與261檔format PASS，未跑remoteCI或重建未改Rust。

真Chromium＋隔離Uvicorn/Gateway/index最終固定源碼跨306.581秒PASS／exit0；main-script at-load／finish hashes一致、JS errors0，三輪合成訊息與150ms靜音Audio playing／ended成功。過期只換HTTP證、不拆body/control；合成token失效401→200單次受理；斷control重連snapshot無turn/TTS重播，原body不變。browser／body／control／server／listener均清理後才PASS。第一輪306.743秒另存first-run，不混作final。這不是聲線、模型智慧、Live2D或私人服務部署驗收。

`verify_rollback.py`隔離reverse/reapply6原檔／3新測試PASS，保留FIX-003基線與最新資料；未操作8026、私人DB／快取或既有未追蹤WAV。FIX-004只解除session gate。下一張FIX-005 A完成判定／版本快取→B有界分句播放，保留原聲線；C未有已提交句子契約不能宣稱完成。搜尋FIX-002、理解FIX-006及桌寵／自主技能仍各自未完成。

## 2026-10-08 — FIX-005 A／B驗收中（尚未完成）

已實作新版Qwen正常EOS／生成上限判定、completion-v2獨立原子快取、無推論的有界語音計畫，以及前端最多預取一段、依序播完、明確停止／全文未完成／重聽。原聲線與既有worker所有權保留。複查先紅後綠修正分段空白遺失、明示無效protocol降級、empty/error音訊及零sample生成；零sample快取的紅證據亦已保存。相鄰completion最終90 PASS，前端89 PASS；這些是合成驗證，實際瀏覽器／原聲線／首段延遲／回退與全體回歸尚待執行。8026尚未重啟，私人DB與舊快取未修改，不能宣稱FIX-005 DONE。

FIX-005真聲線首輪：157字合成故事3段native playing/ended順序、EOS完整回報、最多一段預取、fresh推論中取消/reap及無晚音均PASS。RTX3050Laptop真cold短句31.195s；cache hit0.003664s（不當暖推論）；故事warm未快取30.337／36.196／21.221s，首播30.472s、段間23.289／6.387s，速度不合格，未宣稱修復完成／SLO達成，人工首尾聽驗尚未做。全體回歸669PASS／5 real_provider未選／3existing warnings；首輪中斷log的3個F未保留trace，續跑未重現，根因UNKNOWN。source隔離回退164PASS、重套279PASS，003/004基線雜湊保留。已先一致備份本機DB、graceful停原owner、隔離原聲線驗收後finally恢復8026（pid1507781），health及auth plan PASS。這是本機candidate載入，非全產品發布；未讀取私人聊天或修改原reference/舊cache。下一步同卡局部量測torch threadpool，無效就不改設定。

## 2026-10-08 — FIX-005 SDPA 最後驗收 checkpoint

同卡局部推論比較：CPU intra-op8／1／4無收益，REJECT調整；CUDA SDPA已核實SDK及實際四層配置，固定22字／seed／原聲線／512上限，正式暖未快取8.158／8.133s，對eager12.891／12.655s；63→59token、4.96→4.64s且wave hash不同，不能稱bitwise或人工語意相同。D35先補契約，production僅CUDA用SDPA、CPU保持eager，effective attention綁cache fingerprint；2個profile/cache反例先2FAIL後PASS。最終completion94PASS／10.14s；full-suite-final671PASS／5real_provider未選／3existing warnings／113.00s；mypy203(src+tests)、Ruff265 PASS。最終source reverse/reapply164PASS／281PASS，003004 baseline保留，patch f3ae57f230c7a9b7c806179dcfd99be94dbf05c3d4f7bd2eea2cb05f4b4382c5。

前次SDPA真probe被聊天中斷，僅2/3段完成、不算PASS；private8026亦停止，已用正式launch_companion入口恢復pid11535、healthPASS（interruption-recovery.json），未匯出環境密鑰。最後真probe加四production起訖hash，STALE_SOURCE拒PASS；以獨立supervisor21857執行，以免聊天中斷再次連同清理恢復被殺。續作先讀 ignored `.siro-data/verification/FIX-005-2026-10-08/controlled-check-service.json`、`sdpa-verified/result.json`、`detached-final-check.log`；若LOCAL_CHECK_RUNNING且pid仍活，勿啟第二GPU模型或擅自重啟8026，等驗收自行finally恢復。此時speed與人工語意gate未解除，card保持PARTIAL。不要把舊中斷JSON或基線PASS當成最後SDPA真機PASS。

### FIX-005最後結果（取代上方running checkpoint）

最後SDPA真Qwen／native Chromium probe PASS，四production起訖SHA一致、worker70941aca…匹配最後source回退；safe evidence real-voice-final.json。157字3段160/165/122正常EOS tokens，首次playing時只生成1/3段、最終ended才完成、fresh推論cancel/reap/no晚Audio、所有資源與temp cache cleanup PASS。cold短句24.582s；cache0.005001s獨列；warm故事22.327/22.927/16.945s、RTF約1.75；首段22.446s（原示例30.472）、gap10.053/3.719s（原23.289/6.387），仍未達體驗／SLO且人工語意聽驗NOT_RUN，不標DONE。最終671PASS／94completion／mypy203／Ruff265與source回退164/281見REPORT。

Supervisor已結束並finally恢復8026，pid22624，health與auth plan PASS；不是仍在驗收中，不需再啟第二服務。open_in_codex browser http://127.0.0.1:8026/ 返回queued，尚未確認使用者畫面已導航；避免使用file://畫面當產品入口。卡片PARTIAL／BLOCKED_BY_FIX語音體驗gate保留；005C無已提交句子契約未做，006理解、002搜尋、桌寵與自主技能各自未完成。下一個窄步驟針對已測talker瓶頸／可取消的受支持音訊chunk接入作實證，不換聲線、不擴Core；先完成合成首尾的人耳聽驗，不把EOS當語意正確。
