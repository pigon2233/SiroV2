# Sol 逐項實作任務卡

## 2026-10-16 D61 局部修復接續點

使用者六項急修已核對，真正缺口分為 [FIX-022／023／024／025](runtime-evolution/FIX_REGISTER.md)：MQTT ACK／有界追蹤、模型protocol錯誤、SQLite連線關閉、Rust回收與完整輸出。**DONE / LOCAL_VERIFIED**：最終隔離Git完整check EXIT0、2129 Python PASS／5原opt-in SKIP、24 Rust PASS，見 [本輪證據](evidence/D61-resilience-2026-10-16/REPORT.md)。原WAL／RT-009 failover／D43固定sandbox profile不重做；不改RT編號／原任務歷史。

已解除本四卡的local BLOCKED_BY_FIX；不以軟體PASS宣告發布或真ESP32完成。T27仍需真Broker／toolchain／板子驗收，擴大process權限與正式release仍有原先獨立gate。

所有任務初始為 TODO；實際狀態以 [STATUS.md](STATUS.md) 的任務表為準。依賴是開工前條件；每張卡還必須遵守 [契約](CONTRACTS.md)、[體驗](EXPERIENCE.md)、[安全與隱私](SECURITY_PRIVACY.md)、[驗收](ACCEPTANCE.md) 和 [操作手冊](SOL_RUNBOOK.md)。路徑為目標產出；目前尚未建立的程式檔不代表遺漏。

每張卡執行同一流程：讀輸入 → 檢查現況 → 補驗收 fixture → 實作 → 跑相關檢查 → 記錄證據 → 更新狀態。每張卡的證據放 `docs/evidence/Txx/`，至少含環境、執行命令、結果、限制；真實私人資料只保存脫敏摘要。任務不應越界實作後續整個階段。

## P0：基線、契約與資料

### T00 環境盤點與規格落定

- 依賴：無。輸入：PLAN、SOURCES、目前 repo。
- 步驟：盤點 OS、CPU、RAM、GPU/VRAM、音訊/顯示能力、Python/Rust/Node/容器可用性；確認 repo 乾淨與既有 AGENTS；核實所需官方套件版本，記錄舊 SIRO 可取得範圍；將資料保存、provider 外送、backup 加密和目標平台選項寫成可設定的部署政策，不猜使用者的敏感資料偏好。
- 產出：`docs/ENVIRONMENT.md`、`docs/DEPENDENCIES.md`、`docs/DEPLOYMENT_POLICY.md`、必要 ADR；列模型／硬體／資產未提供項目。
- 驗收：另一位執行者能看出 baseline 硬體、尚缺條件、第一個可跑 profile；不得把開發機當成已確認的部署機。
- 界線：不安裝巨大模型，不改系統全域設定。

### T01 開發骨架與統一命令

- 依賴：T00。輸入：PLAN §4。
- 步驟：建立 Python package、版本化設定 schema、lockfile、CLI；新增 lint/typecheck/unit test、CI；設定 runtime data 與 secrets 的 gitignore，加入 secret scan 與最小 log redaction 測試。
- 產出：`pyproject.toml`、`uv.lock`、`src/siro/cli`、`scripts/check`、CI、README setup。
- 驗收：乾淨 checkout 可安裝並跑 `scripts/check`；`siro doctor` 缺依賴時可讀報錯；不需雲端 key。

### T02 型別、事件 schema 與相容性

- 依賴：T01。輸入：CONTRACTS §1–2、§10。
- 步驟：將 envelope 與首批事件轉為型別/schema；建立合法、缺欄位、超限、未知版本、跨 session fixtures；建立 dependency boundary test。
- 產出：`src/siro/contracts`、`schemas/events`、`tests/contract`。
- 驗收：拒絕非法事件；schema export 可重現；Core 引用 adapter 内部會使邊界測試失敗。

### T03 有界本機 Event Bus

- 依賴：T02。輸入：CONTRACTS §3。
- 步驟：做 publish/subscribe port、本機實作、優先級、bounded queues、取消與訂閱清理；注入 clock。
- 產出：`src/siro/ports/events`、本機 bus、負載 fixture。
- 驗收：1 萬個合成事件不無限長記憶體；慢 consumer 不拖住其他 consumer；過期/重複規則可測；停止後無殘留 task。

### T04 SQLite、migration 與一致性

- 依賴：T02。輸入：CONTRACTS §6。
- 步驟：建立首版核心表、repository ports、transaction、outbox/inbox；後續表可隨任務增 migration；建立 backup/restore 基礎。
- 產出：`src/siro/persistence`、migration、`tests/integration/storage`。
- 驗收：空 DB 建立、版本升級、transaction 中斷、重複 event、backup 還原均通過；資料目錄不可寫時明確失敗。

## P1：文字認知核心

### T05 World State、Identity 與來源

- 依賴：T03、T04。輸入：PLAN §6、CONTRACTS §6。
- 步驟：實作 identity_id、不可由 agent 改的 core、versioned traits；world observation 投影、TTL、來源與 unknown 狀態。
- 產出：`core/identity`、`core/world`、合成 fixtures。
- 驗收：重新啟動身份不變；舊觀測不能覆蓋新觀測；sensor 過期為 unknown；未授權更新 immutable core 被拒。

### T06 Conversation 狀態機與 mock 模型

- 依賴：T05。輸入：CONTRACTS §5。
- 步驟：建立 session/turn/generation、stream port、cancel token、mock provider 與 CLI 文字閉環；整合基本 memory port。
- 產出：`core/conversation`、`adapters/models/mock`、CLI demo。
- 驗收：正常、取消、並發新輸入、late chunks、timeout 都到正確 terminal state；離線可演示；A01/A02 通過。

### T07 真實模型 adapter 與 failover

- 依賴：T06。輸入：provider 官方文件、T00 的環境/預算。
- 步驟：接兩種獨立 backend（預設一個允許的雲端、一個本地或第二個可用 backend）；適配 text/tool/usage；加入 timeout、budget、cancel 與 generation failover。
- 產出：兩個 adapter、範例 env、真實測試 opt-in 標記。
- 驗收：同一 fixtures 運作兩者；拒絕未授權外送；真實無 key 時明示 blocked-external；mock 不算 provider 實測。

### T08 最小持續人格與可展示核心

- 依賴：T06、T04；真實展示另依 T07。輸入：PLAN §6.3–6.4、Identity 與 Memory ports。
- 步驟：接 working/episodic 儲存、身份 prompt 組裝、記憶來源查詢、使用者可修改初始 persona；提供一鍵文字 demo。
- 產出：`core/memory` 初版、P1 walkthrough、identity example。
- 驗收：連續 3 次重啟後仍能找回指定事件；換 adapter 保留 identity_id；無來源時回答未知，A03 通過。
- D67 接續修正：普通聊天明確採 1–3 句短答，詳解依使用者要求展開；保留原輸出上限、取消及截斷失敗裁決，不自動續寫。見 `evidence/T08-REPLY-LENGTH-2026-10-17/REPORT.md`。

## P2：跨程序通道與 Live2D

### T09 Broker、outbox 與重播

- 依賴：T03、T04、T06。輸入：CONTRACTS §3。
- 步驟：接 NATS/JetStream、ack、redelivery、outbox dispatcher、quarantine；實作無副作用 replay；CI 啟動測試 broker。
- 產出：bus adapter、broker config、fault fixtures。
- 驗收：發送後/ack 前 crash 重送不重複提交；broker 斷線能保存 pending；replay 不呼叫 runtime；A04 通過。

### T10 Gateway、控制 UI 與 Single Writer

- 依賴：T09。輸入：CONTRACTS §4。
- 步驟：獨立 gateway；session/Origin 認證；單 writer、控制佇列、snapshot/reconnect；小型 UI 顯示對話、取消、健康狀態、資料路由與本機 kill switches。
- 產出：`services/presentation`、`ui`、WS contract tests。
- 驗收：慢 client／多 producer／反覆連線不破壞 event loop；一個 client 不影響另一個；A05/A06 通過。

#### T10-UI-01 介面重設計與獨立工作畫面

- 2026-10-18 **T10-UI-01-INTEGRATION DONE／LOCAL_VERIFIED（自動可驗範圍）**：對比／鍵盤／狀態回饋／重啟重連修正9項；新10、相關525、桌寵69 PASS；真main＋真Live2D整合9/9。[證據](evidence/T10-INTEGRATION-2026-10-18/REPORT.md)。整卡PARTIAL，剩人工項目見[手動驗收指南](evidence/T10-INTEGRATION-2026-10-18/MANUAL_TEST_GUIDE.md)。

- 2026-10-18 **T10-UI-01-REFLOW DONE／LOCAL_VERIFIED**：六viewport×九頁＋detail（含200%等效）水平reflow實測；修權限頁未知長開關按鈕被裁。新2、相關514、桌寵69 PASS，source-only回退驗證。[證據](evidence/T10-REFLOW-2026-10-18/REPORT.md)。只完成水平reflow，整卡PARTIAL；對比／讀屏／完整真人流程未完。

- 2026-10-18 **T10-UI-01-KEYBOARD DONE／LOCAL_VERIFIED**：首Tab可見skip link，Enter focus目前heading／main fallback，路由／draft／snapshot／工具不變。新3、相關512（重疊）、桌寵69 PASS；真CUA focus與source-only回退驗證。[證據](evidence/T10-KEYBOARD-2026-10-18/REPORT.md)。只完成keyboard bypass，整卡仍PARTIAL，窄窗／對比／讀屏／完整真人流程未完。

- 2026-10-18 **T10-UI-01-SETTINGS DONE／LOCAL_VERIFIED**：permissions補既有mode，三個功能開關中文名稱／狀態／下一動作；原API／callback／授權不變。相關509、Python3.12相容64 PASS（重疊）、真CUA3步／backend readback與source-only回退通過。[證據](evidence/T10-SETTINGS-WORDING-2026-10-18/REPORT.md)。整體仍PARTIAL；完整可及性／真人流程未完。

- 2026-10-18 DETAIL證據修補：獨立PARTIAL後重跑8步真CUA含missing snapshot，receipt與AX／JPEG一致；baseline commit／dirty snapshot回退package可對目前checkout正常check，107相關tests PASS，專屬REGRESSION_BASELINE已補。只恢復DETAIL限定DONE供重驗，整卡PARTIAL；production未變，真active-child取消／部署rollback未驗。[修補報告](evidence/T10-TASK-DETAIL-2026-10-18/REPORT.md)。

- 2026-10-18 **T10-UI-01-DETAIL DONE／LOCAL_VERIFIED**：單UUID詳情／返回／history／explicit readback，沿原批准及取消；新11、相關480、相容150 PASS，真CUA＋main／SQLite／Rust與source-only rollback通過。[證據](evidence/T10-TASK-DETAIL-2026-10-18/REPORT.md)。僅本切片DONE，整卡PARTIAL；設定用語／完整可及性與真人流程仍未完。

- 2026-10-18 搜尋切片 **LOCAL_VERIFIED**：既有記憶query API接入前端搜尋／清除／結果狀態、取消與晚到fence；相關476 PASS、新專項12 PASS（重疊）、真瀏覽器→main→SQLite搜尋通過。[證據](evidence/T10-MEMORY-SEARCH-2026-10-18/REPORT.md)／[未完成盤點](evidence/T10-MEMORY-SEARCH-2026-10-18/OPEN_TASKS.md)。整卡仍PARTIAL；下一切片任務詳情未開始。

- 狀態：**PARTIAL**（2026-10-15）。首個網頁分頁／視覺切片 LOCAL_VERIFIED：九工作畫面、333前端PASS、真main／Rust／SQLite三次啟動與24 CUA檢查；[證據／限制](evidence/T10-UI-01-2026-10-15/REPORT.md)。真Live2D切頁、任務詳情／記憶搜尋等補完及真人體驗未完，原 T10 傳輸驗收及 T／RT 編號保持。
- 依賴：T10 現有 session／Origin／single writer 與 D34 續期；各畫面重用現有 API。桌面外殼／動作沿 T12 及既有 Companion plan，不阻擋先交付網頁分頁。
- 輸入與產出：[INTERFACE_REDESIGN_PLAN](runtime-evolution/INTERFACE_REDESIGN_PLAN.md) 的入口對照、視覺草案、分開的可操作原型、逐頁移轉與回退；參考 frontend-design／Hallmark／VPet。
- 最小切片：先對話＋任務獨立畫面，再移記憶、能力、設定／診斷；共用同一 control／session，避免每頁開第二 renderer／音訊 owner。不能只換配色或將全部功能折疊。
- 驗收：逐頁直接進入／後退／重新整理；聊天→審查任務→返回、更正記憶、停止工具三流程；狀態／來源／批准／取消／unknown 保持，跨頁不重送動作或舊音。窄窗／鍵盤／真 renderer 與真桌面分開取證。
- 回退：只撤新前端／外殼／資產，保留最新 DB 與任務；本卡不改 Core／DB schema／授權／provider／release。桌面自由活動及缺少動作仍按 [COMPANION_EVOLUTION_PLAN](runtime-evolution/COMPANION_EVOLUTION_PLAN.md) 各自驗收，不以規劃或原型冒稱完成。
- 2026-10-18 補充：修復聊天輸入法組字期間 Enter 被當成送出的 T10 regression，合成回歸及實際 WSL 部署通過，見 [T10 IME evidence](evidence/T10-IME-2026-10-18/REPORT.md)；真人原生輸入法體驗尚待確認，T10-UI-01 其餘項目仍維持 PARTIAL。
- 2026-10-18 後續：使用者確認是「注音根本打不出來」，定位 WSLg 缺 Windows IME 轉送與 Ubuntu 注音引擎；安裝 IBus Chewing 並接入桌寵啟動流程，見 [T10 注音證據](evidence/T10-ZHUYIN-2026-10-18/REPORT.md)。真人按鍵體驗待驗，T10-UI-01 仍為 PARTIAL。

### T11 AIRI 身體接入可行性

- 依賴：T10。輸入：SOURCES 的 AIRI、PLAN 身體 port。
- 步驟：核實並鎖 commit、授權與外部 API；做 speech、emotion、cancel、offline 四個控制 proof；最多兩個工作單元，不無限 fork 改造。
- 產出：`docs/ADR-embodiment.md`、最小 adapter spike、依賴/資產清單。
- 驗收：能展示四項操作或提交可重現阻礙，選定 AIRI／最小 Web renderer；選型完成不等於 Live2D 功能完成。

### T12 實際 Live2D 與故障隔離

- 依賴：T11。輸入：T11 決策、合法 Live2D 資產。
- 步驟：實作 body port、emotion mapping、idle、gesture、look target、disconnect fallback；renderer 不持有 identity database。
- 產出：adapter、asset 配置、body conformance tests、實際畫面證據。
- 驗收：真 Live2D 可動；慢工具/LLM 不卡住 idle；kill renderer 後 Core 可繼續文字及重連，A07 通過。假 avatar 不能驗收為 Live2D。

## P3：語音

### T13 媒體協定與播放擁有者

- 依賴：T10、T12。輸入：CONTRACTS §4–5。
- 步驟：寫完整 binary header spec，TS/Python golden tests；分 mic/output channels；single playback owner、stream metadata、ring buffer。
- 產出：audio service skeleton、audio protocol、recorded synthetic frames。
- 驗收：不同 sample rate 協商、遺失 frame、out-of-order、buffer overflow 明確處理；不會兩端同時發聲。

### T14 VAD、STT 與輸入終點

- 依賴：T13。輸入：授權測試音檔、選定 STT 官方介面。
- 步驟：實作 VAD、partial/final transcript、endpoint、language；過長/靜音截斷；mock 與一個真 STT。
- 產出：STT adapter、語音 fixtures、麥克風選擇與靜音設定。
- 驗收：短句、長句、靜音、背景噪音、裝置拔除皆有確定結果；同 utterance 只建立一個 user turn。

### T15 TTS、分句與口型

- 2026-10-17 D65 聲音品質子任務：使用者真人回報 Kokoro 機械／音色不合／破碎，指定動漫、可愛活潑；先做獨立本機 VoiceDesign 三聲線試聽及波形診斷。試聽結果與使用者聽選前不得稱品質通過，正式接入另須原取消／單 owner 驗收。見 DECISIONS D65，D64 功能證據不替代此品質驗收。
- D66接續：使用者選B後已固定reference，真Base clone／原生播放／推論取消／正式入口B路由及431相關回歸通過，已重開供使用者。新台詞主觀品質／破音設備聽驗、首音SLO仍待驗；不把局部接入列整張T15 DONE。見 evidence/T15-VOICE-B-2026-10-17/REPORT.md。
- 依賴：T13、T07。輸入：語音模型/資產與授权。
- 步驟：句段緩衝、TTS streaming、playback ack、口型依播放時鐘、語音失效轉文字；不朗讀 tool JSON。
- 產出：TTS adapter、prosody mapping、speech events。
- 驗收：字幕/口型與播放同 speech_id；TTS 故障仍有文字；合成已完成但未播放不可提前標記說完。

### T16 Barge-in、AEC 與真機壓測

- 依賴：T14、T15、T12。輸入：真麥克風／喇叭或耳機。
- 步驟：speech onset 觸發 cancel，清播放器、TTS/LLM；測 echo/AEC、耳機與喇叭模式；儲存支援矩陣。
- 產出：真機測試報告、audio fault tests、限制說明。
- 驗收：A08/A09 與打斷 SLO；連續 100 次合成競爭無舊音復活、至少 20 次真人打斷；不支援 AEC 明示，不能將半雙工寫全雙工。

## P4：記憶與主動性

### T17 五類 Memory 與檢索

- 依賴：T08。輸入：CONTRACTS §6。
- 步驟：五類記憶、FTS、來源與時間過濾、scope、衝突事實；建立可檢查 UI/API；embedding 只作可選索引。
- 產出：memory stores/retriever、檢視/更正/刪除入口、20 組以上 fixtures。
- 驗收：A10/A11；更正不丟歷史版本，刪除使衍生摘要失效，多使用者 fixture 不互漏。

### T18 Dream 與關係演變

- 依賴：T17。輸入：PLAN §6.3–6.4。
- 步驟：cursor、bounded batch、candidate validation、provenance、trait clamp、relationship revision；支援中斷與重跑。
- 產出：consolidator、排程/取消、合成 30 天資料。
- 驗收：同批重跑不重複；推測標為推測；沒有事件不能捏造經歷；不可修改 immutable core；A12 通過。

### T19 Attention、Drives、Workspace、Goals

D57 產品接入子切片／FIX-021：已批准的固定文件唯讀任務，沿現有GoalService/Planner/goals→Rust→來源結果。契約D57、修復卡/證據見runtime-evolution/FIX_REGISTER.md與evidence/T19-goal-loop-2026-10-14/REPORT.md。原L1成果保留；完整自主goal不以此子切片宣告DONE。

- 依賴：T17、T05、T06。輸入：PLAN §6。
- 步驟：注入 clock、固定初始 scorer、hard gates、有限 context、goal 狀態、步數/費用預算、候選 action 及原因記錄。
- 產出：認知模組、planner structured schema、replayable fixtures。
- 驗收：相同事件/clock 得同一選擇；噪音 flood 不觸發大量 LLM；user input/cancel 不被背景驅動蓋過。

### T20 主動陪伴與使用者控制

D57 跨任務控制沿本卡：owner明確批准後離開可繼續有界讀取，foreground/tools-off/shutdown取消join；重開只保留待續，不能自批/自動執行。這不是新增自發問候或通用排程框架。

- 依賴：T18、T19、T16。輸入：quiet/busy/cooldown 配置。
- 步驟：加入回家、久未完成任務、環境變化候選；do_nothing、每日上限、靜音、勿擾、理由可查。
- 產出：proactivity rules、設定介面、使用者體驗腳本。
- 驗收：A13；合成 7 天無 quiet/busy 違規；有允許情境才說話；先由使用者啟用，不強迫頻繁打擾。

## P5：Runtime 與 Skill

### T21 Runtime 邊界、Policy 與 grant

- 依賴：T09、T19。輸入：CONTRACTS §7。
- 步驟：Rust workspace、健康檢查、受限本機 RPC、schema client；policy allow/deny/ask、scope、token/args hash、revocation、審計。
- 產出：`runtime`、policy evaluator、fake OS driver、授權介面。
- 驗收：偽造/過期/撤销/改參數 grant 都不能執行；Runtime 離線 Core 照常回應；A14 通過。

### T22 Skill Registry 與隔離 worker

- 依賴：T21。輸入：manifest schema。
- 步驟：install/enable/disable/version、input/output validation、worker resource limits、timeout/cancel、能力宣告與相容性。
- 產出：registry、sample skill、worker supervisor、plugin 開發指南。
- 驗收：壞 manifest 拒絕；CPU hog/memory hog/output flood 被限制；停用阻止新 job；A15 通過。

### T23 檔案、程序與 shell

- 依賴：T22。輸入：scope/grant、測試暫存目录。
- 步驟：read/list/write/move、process list/start/stop、argv execution；路徑與 symlink 防逃逸、child process cancellation、結果 readback。
- 產出：built-in computer skills、Linux driver、平台 capabilities 表。
- 驗收：A16；無越界讀寫，timeout 能收掉子程序，重送相同 action 不重複副作用；全用隔離測試資料。

### T24 瀏覽器、視窗與 UI 操作

- 依賴：T23。輸入：目標 OS 授權與 UI API。
- 步驟：browser navigate/read/fill/click、window/screenshot/key/pointer；觀察→選目標→動作→讀回；改畫面使舊目標失效；加入按需 VisionModel port 與一個實際 screen-analysis adapter，輸出具來源與信心的觀測；顯示支援平台。
- 產出：browser/UI adapters、合成網站、至少一個真桌面流程。
- 驗收：完成登入以外的測試表單/開程式流程，拒絕未授權目標；視覺可辨識合成測試畫面，辨識失敗不盲點擊；Wayland/Windows 限制明示；不能以 DOM 成功聲稱所有桌面程式可控。

### T25 系統服務與完整能力整合

- 依賴：T24、T21。輸入：能力分類與 T00 平台清單。
- 步驟：服務狀態/啟停、安裝等系統動作 adapter；critical 類別有明確 permission/人工接口；Windows adapter 或對應子卡和真機驗收。
- 產出：電腦能力矩陣、使用範例、端到端 demo。
- 驗收：各能力明示 supported/blocked/unsupported；A17；測試服務故障不阻斷 Live2D/語音；未驗平台不能標已支援。

## P6：智慧環境

### T26 Device Registry 與能力圖

- 依賴：T19、T22。輸入：CONTRACTS §8。
- 步驟：device descriptor、properties/actions/events、room 關聯、能力 alias、availability、未知/過期處理；相機以同一 capture capability 接入，使用者啟用後才擷取，依按需或變化觸發而非永久送進 LLM。
- 產出：registry、模擬 light/presence/temperature adapters。
- 驗收：新增另一品牌虛擬燈不改 Core；無所在位置或失效 sensor 不推斷使用者肯定在房間。

### T27 MQTT Gateway 與 ESP32 firmware

- 依賴：T26。輸入：板型/感測器設定；缺硬體先 simulator。
- 步驟：broker 認證、availability/LWT、state、command/ack；ESP32 提供設定式 presence 或 temperature sensor 與低風險 LED actuator 範例。
- 產出：gateway、`firmware/esp32`、接線/燒錄指南、simulator。
- 驗收：重複/retained/過期命令與離線測試；真板讀值及 LED readback；無硬體只標 simulator 通過。

#### T27-FIX-01 MQTT／ESP32 時間格式與對時修復

- 狀態：**LOCAL_VERIFIED / HARDWARE PENDING**（2026-10-16）；不更改 T27 原本真板驗收門檻。
- 來源／根因：Python command 缺 firmware 必需的 `expires_at_epoch`，Python state 只接受 ISO，且 `configTime` 啟動 SNTP 後 firmware 未等時間就連 MQTT。原版本對新增驗收有5個失敗；屬已確認的 implementation／integration defect。
- 最小修復：保留 ISO、加 epoch mirror；simulator 只接受已核對一致的已知 mirror；state 接受 UTC 數值 epoch且寫入前驗時。firmware 30秒有界等待及 loop guard；新增 aiomqtt 單次 probe，重用現有 tracker／projector／registry，applied ACK加新鮮無矛盾state才確認。
- 相容／範圍：舊 ISO、non-retained、expiry／dedup／LWT／auth 不變；不改 Core、World 排序、schema、授權、UI、依賴或既有 RT 編號。腳本單次點亮授權 LED，無自動重送／補償動作。
- 驗收／回退：時間格式、真 Broker＋合成 peer、既有相鄰回歸及 host clock control-flow；只撤本卡 MQTT／firmware hunk與新增 probe／tests，不還原 DB。2026-10-16 已補真 PlatformIO `esp32dev` cross-compile PASS；真板燒錄／NTP／LED仍待驗。[時間與整合證據](evidence/T27-mqtt-time-2026-10-16/REPORT.md)／[完整編譯證據](evidence/T27-firmware-build-2026-10-16/REPORT.md)。

### T28 Home Assistant Adapter

- 依賴：T26、T21。輸入：HA 測試 instance/授權。
- 步驟：官方 API 轉 descriptor、狀態訂阅、light.set、action ledger、回讀；憑證只由服務持有。
- 產出：HA adapter、entity mapping 設定、integration tests。
- 驗收：服務呼叫成功但狀態未變時不可宣告已開燈；撤销憑證與設備 unavailable 正確降級。

### T29 房間閉環與環境情境

- 依賴：T20、T27、T28。輸入：至少一個真 sensor 和 actuator。
- 步驟：sensor → world → salience → candidate → policy → device → state；用回家問候與燈光兩個場景實測；抑制 bouncing 和自己事件回授循環。
- 產出：兩個示範場景、時序 trace、離線處理報告。
- 驗收：A18；一次進房不連續重複問候，設備命令不自激循環，手動關閉設備仍可反映。

## P7：迭代、資源與發布

### T30 Procedural Memory 與技能候選

- 依賴：T18、T22。輸入：已成功完成的多次 trace。
- 步驟：提取 workflow 候選、參數化、來源關聯、去除 secret、推導權限、測試 fixtures；候選與 enabled 分開。
- 產出：candidate generator、候選檢視/測試入口。
- 驗收：沒有授權不自動 enable；失敗或惡意 trace 不擴權；A19。

### T31 程式修改提案與隔離驗證

- 依賴：T30、T01。輸入：一個刻意放入測試 repo 的小 bug。
- 步驟：生成 patch proposal，獨立 workspace 執行 lint/test/行為驗證，生成 diff/report；不覆蓋 production source。
- 產出：evolution pipeline、審閱入口、失敗隔離證據。
- 驗收：通過與失敗 patch 各一例；測試失敗不能變 active；提案無權改 permission policy。

### T32 版本發布、回滾與資料相容

- 依賴：T31、T04。輸入：兩個测试 release。
- 步驟：release manifest、來源/hash/signature 驗證、staging install、backup、healthcheck、activate、last-known-good；兼容/非兼容 migration 分路徑。
- 產出：update/rollback scripts、恢復手冊。
- 驗收：A20；新版本啟動失敗能回舊版與一致資料；update crash 不中途遺失活躍版本。

### T33 Compute Governor 與資源 profiling

- 依賴：T16、T18、T22。輸入：T00 硬體、PLAN §10。
- 步驟：resource telemetry、active model slots、admission、high/low water hysteresis、pause/resume、budget；做負載 profile。
- 產出：governor、各 deployment profile 預算表、基準報告。
- 驗收：A21；memory pressure 暫停背景，cancel/UI 仍可用；雲端禁用時不能偷偷外送。

### T34 安裝、啟停、診斷、備份與還原

- 依賴：T25、T29、T32、T33。輸入：全部 services。
- 步驟：乾淨機安裝腳本、鎖版、doctor、user service、health UI、graceful shutdown、備份復原、log retention。
- 產出：`scripts/install`、start/stop/doctor/backup/restore、操作文件。
- 驗收：A22；在全新資料目錄從頭跑起、還原身份/記憶/設定；缺 key/設備列出而不 crash loop。

### T35 v1.0 整合與 24 小時運行

- 依賴：T00–T34 所有必要卡。輸入：ACCEPTANCE、真實設備/模型。
- 步驟：所有 A01–A22、KPI、真語音/Live2D/電腦/房間場景、24 小時 soak；修復阻擋缺陷。
- 產出：v1.0 release checklist、evidence、已知限制、使用者驗收記錄。
- 驗收：沒有未揭露 BLOCKED 卡；零已知資料毀損/越權/取消失效缺陷；完成 EXPERIENCE 的 v1.0 walkthrough 與 SECURITY_PRIVACY 發布門檻；未完成 Windows 實測則不得標跨平台完成。

## P8：Compute Fabric

### T36 節點註冊與信任

- 依賴：T33、T09。輸入：CONTRACTS §9。
- 步驟：預先配對、node capability/model profile、heartbeat、版本/資源、trust/privacy scopes、revocation。
- 產出：registry、假雙節點、節點配置文件。
- 驗收：未知節點拒絕，撤销後不再接新 job，失聯移除路由；node 不能自己抬高資料權限。

### T37 Compute Worker 與 job lease

- 依賴：T36。輸入：job/attempt/epoch schema。
- 步驟：job submit/stream/cancel/result、lease、有限輸入、artifact transfer、結果校驗、read-only retry。
- 產出：worker executable、fault simulator。
- 驗收：過期 epoch 丟棄；worker crash 不重複提交 memory；大輸入有流量上限及清理。

### T38 Router 與資料／成本政策

- 依賴：T37、T07。輸入：PLAN §10.2。
- 步驟：hard filter、latency/cost 估算、模型載入成本、privacy/budget、local/LAN/cloud 明示路由。
- 產出：scheduler、決策 trace、校準器。
- 驗收：local_only 永不離機；沒有符合节点明確 unavailable；成本上限不被 failover 繞過；A23。

### T39 真實雙節點與失聯演練

- 依賴：T38。輸入：第二台實機/可信遠端 worker。
- 步驟：本機 Core＋遠端 LLM/STT 任一實際任務；斷網、過载、重啟、取消，測 LAN latency 與流量。
- 產出：雙節點 setup、實测資料與單機對照。
- 驗收：A24；保持身份與現有資料，late result 不回覆舊 turn；同一台兩個程序只算模擬，不算真雙節點。

### T40 v1.1 完整基線發布

- 依賴：T35、T39。輸入：完整需求追蹤矩陣。
- 步驟：重跑受分散式變更影響的整合/故障案例、雙節點 24 小時 soak、回滾；完成 distributed node walkthrough；核對所有需求與安全證據。
- 產出：v1.1 release、完整 setup/runbook、任務與能力狀態表。
- 驗收：A01–A24 皆有對應證據；硬體阻礙逐項解除；研究支線與產品已交付能力清楚區分。

## R：研究支線（報告也是有效結論）

### R01 跨節點模型切層

- 依賴：T39、兩個適合推論節點。輸入：SOURCES GPipe/EdgePipe/Mensa。
- 步驟：核實可用推論 backend 的官方 multi-device 能力；固定模型與量化；測整模遠端/小本機/切層三組，batch=1 與 throughput 分開。
- 產出：`research/model-partitioning/` benchmark 配置、原始合成結果、報告、採納 ADR。
- 驗收：符合 PLAN §10.3 才提產品整合；硬體不足就報告可驗證瓶頸，不宣稱已有分層加速。

### R02 認知模型與神經架構消融

- 依賴：T20。輸入：來源中的 FlyWire、記憶研究。
- 步驟：在同一合成事件集比較 rules-only、加 Attention、加 Drives、加 Dream；測適切行為、打擾率、成本及記憶正確率。
- 產出：評測集、消融報告、是否調整 scorer/traits 的決策。
- 驗收：有基準組、固定 seeds/clock 和限制；不把改善宣稱為意識或生物腦重建。

### R03 語義設備與擴充協定

- 依賴：T29。輸入：W3C WoT。
- 步驟：做一個 WoT TD 到内部 descriptor 的有限轉譯；列未支援欄位、驗证 properties/actions/events；比較新增設備工時。
- 產出：轉譯 spike、相容矩陣、採納/延期 ADR。
- 驗收：新設備不改 Core；不完整相容時明示範圍，不為外掛性先引進不必要的 ontology server。
