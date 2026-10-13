# Risk register

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
