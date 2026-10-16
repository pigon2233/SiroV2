> 歷史報告：原 2026-10-03 review；目前結論見 ../../ARCHITECTURE_REVIEW.md。

# SIRO V2 Architecture Review

日期：2026-10-03（Asia/Taipei）。範圍：RT-001–008 完成後的工作區；HEAD `a27001d32349841002f3a5a02c97c18544f8ce40`，包含尚未提交的 tracked changes 與新增檔案。這是架構檢查，未實作新功能或修改 production code。

## Overall architecture health

**YELLOW：演進方向正確，但 run／session／proposal 的責任界線開始漂移，擴張前需要修補交界。**

原生工具訊息、batch barrier、有界 argv、程序群組取消、Qwen lifecycle、catalog 與 durable journal 都有正式 caller，也有可重現測試。Core 仍透過 LanguageModel 與既有 memory 邊界工作，未引入 Hermes framework、設備依賴或 Rust 重寫。已解決的功能不應再建立第二套 abstraction。

問題集中在不同階段接合處：run-scoped journal 與 session-scoped tool identity 不一致；candidate 接受 arguments-only handler，卻沒有把它納入 run 的取消等待；模型 generation 的 FAILED 狀態未成為 dispatch gate。這些問題不需要重設整個系統，但不能以全套測試通過推定不存在。

RT-001–008 的 DONE 保留為各卡既有、有限的驗收紀錄。RT-003/005 需要追加修補與回歸，RT-008 的 local readback 成果保留。**G1–G3 尚不能提升為可發布 runtime 基礎版本**：本次反例未修、真選用 provider 工具閉環及部署 rollback rehearsal 仍缺。

### 證據與判讀範圍

- 已讀題列十份文件、AGENTS、STATUS、SOL_RUNBOOK、RT-001–008 evidence、相關獨立驗證與契約／決策；對照現有 code、HEAD diff、RT scoped patches。ModelMessage 與 serializer 在 Phase 1 前已存在，不歸功於 RT-002 新增。
- RT-008 所列十個 source/test digest 全部與目前檔案一致；本次另保存 [source digests](../../verification/architecture_review_2026-10-03/source-digests.json)。不能只用 HEAD 重現本次結論。
- 本次 `uv run pytest -q`：**285 passed、5 skipped、3 warnings，52.53s，exit 0**。`uv run ruff check src tests` PASS；`uv run mypy` PASS，174 files。
- [隔離探針](../../verification/architecture_review_2026-10-03/probe.py)／[結果](../../verification/architecture_review_2026-10-03/probe-result.json)：合成模型、真 Core／controller／SQLite，全部資料置於 TemporaryDirectory；handler 的副作用是測試 list。探針 exit 0 表示反例成立，**不是產品 acceptance PASS**。標準 pytest 不收集此文件目錄，後續修補必須納入正式 tests。
- 未重跑真 provider、GPU、GUI、Rust、硬體、24h soak 或部署 rollback。RT-006 的 GPU／GUI／owner 人工驗收是已讀的歷史證據，不冒稱本次實測。未操作使用者服務或私人 DB。

## Recent improvements

| RT | 實際改善與 code 證據 | 本次決定 |
|---|---|---|
| RT-001 | migration invariant 與隔離 installed Gateway smoke 已進正式 suite；原 F11 assertion failure 消失 | KEEP；不再改 schema 期待值掩蓋問題 |
| RT-002 | `CompanionCore.respond` → `ConversationEngine.respond` → `ModelRequest.messages`；tool observation 保留 role／call ID，續作不再新增假 user utterance | KEEP；不另造 message framework |
| RT-003 | `integrated.py:477–505,638–758` 收齊 batch、拒絕 batch 內重複 ID、唯一 terminal；已有 deny／error／manual callback 測試 | 保留 batch 設計；修正 identity scope 與 generation gate |
| RT-004/005 | `execution.py:75` 有界 drain、owned PGID TERM→KILL／reap；`gateway.py:1184` candidate 確實接入；writer／frontend terminal fence 已補 | 保留 facade 與 writer；不要重寫 executor，只補未納管 handler |
| RT-006 | `tts.py:288` queue cap、request／epoch、poisoned worker 隔離、close；HTTP disconnect 與前端 AbortController 接入 | KEEP；音色／模型／Live2D 不動，不增設 GPU broker |
| RT-007 | `ToolCatalog` 共用 definition、executor、readiness；模型快照及 dispatch 再查；`/v1/runtime` 如實揭露 JSON settings 未套用 | KEEP；不要另建 registry，不能把診斷當配置整合完成 |
| RT-008 | `runs.py:start/checkpoint/record_dispatch/reconcile`；run＋journal atomic start、dispatch 前 commit、partial observation、unknown 配對、startup fence；013 為 additive | KEEP local readback；不再另做 run journal 或自動重播 |

F01、F02、F03、F05、F10 的改善主要限於 candidate 與已驗證路徑；default legacy 仍保留舊執行方式。F04 已縮小成 session restore、外部效果查證與下述交界問題。F06 的 catalog／診斷部分改善，JSON settings／Rust grants 分立仍存在。

## Architecture drift found

### AR-01：tool identity 從 run 洩漏到 session（HIGH，已重現）

`integrated.py:645` 用 `_seen_calls[session_id]`，terminal 未清除；但 013 的 canonical key 是 `(run_id, call_id)`。同 session 的第二個獨立 run 回傳相同 `call-0`，即得到 `duplicate_or_excess_tool_calls`，第二次工具未執行。這不是同一 run 的重複 dispatch。

重啟清空 RAM 後仍失敗：011 的 `UNIQUE(session_id, call_id)` 造成 `sqlite3.IntegrityError`，例外未被 propose 的 ValueError／RuntimeError 分支處理。RT-008 的 `orchestrator.py:222–233 journal_owner` 也以 session＋call ID 查找；`runs.py:reconcile` 跨表匹配沿用相同範圍。**只清 `_seen_calls` 不足以修好。**

歸因：DB unique constraint 是既有設計；session-wide `_seen_calls` 由 RT-003 加入；RT-008 延續不相容的擁有權匹配，而非最初造成這個 failure。既有 RT-008 independent verification 已指出跨 run 問題，本次再次確認，並重現 restart 的 DB failure。Ollama 自產 ID 含 generation，可降低觸發；LanguageModel port 並未要求所有 provider 跨 run 永遠不重用 ID。

最小修補：在既有 proposal／journal 邊界明確區分 provider call ID 與 runtime operation identity，讓 exact proposal/run ownership 主導 dispatch、callback 與 recovery。保留 provider pairing，保留舊 rows／API；如需 schema 補充，只能新增 migration，不能改 011／013。驗收涵蓋同 run 去重、不同 run 合法重用、重啟、舊 approval fence 與 A/B session。歸入 RT-003 修補，RT-008 加 ownership 回歸；不新增通用 ID framework。

### AR-02：相容 handler 越過 candidate 的 lifecycle 邊界（HIGH，已重現）

`orchestrator.py:442–469` 只有 contextual executor 被放進 `_active[run_id]`；arguments-only 分支直接 await handler。`cancel_run:343` 僅等待 `_active`，因此這類 handler 不在取消／cleanup ownership 內。

探針讓 arguments-only handler 等待 Event，呼叫 cancel 後 readback 已是 CANCELLED，但 handler task 還在；釋放 Event 後副作用仍發生。這證明 terminal fence 只抑制輸出，沒有停止 handler。正式 main 的 `browser.navigate+read` 與 `process.start` 都未配置 contextual executor（`gateway.py:1245–1257`）；本次沒有實測真 browser／桌面副作用，不能把合成結果冒稱真程序殘留。

歸因：舊 handler 相容性本身合理；RT-005 的 lifecycle 管理只完成 contextual argv，RT-007 descriptor 保留這個缺口。最小修補是讓 candidate adapter 具有明確 task／cleanup ownership，區分可取消 foreground、已確認 detach 及無法確認的結果。不要假設 `task.cancel()` 一定能停止外部程序。RT-005 追加修補 gate，RT-012 的持續 browser session 必須等待這項 gate。

CONTRACTS 的 RT-005 限制已明說不涵蓋 browser／所有使用者程序。因此此反例沒有推翻該卡「owned argv foreground」的既有 PASS；它揭露的是較廣 runtime lifecycle 目標與相容 handler 路徑之間仍有缺口，不能將有限完成升格為所有工具皆可取消。

### AR-03：provider FAILED 狀態未阻擋工具 dispatch（HIGH，既有缺陷已重現）

`ConversationEngine.respond:157–175` 在 provider exception 後保留已收到的 tool calls，結果為 FAILED。`IntegratedCompanion.respond:385` 與續作分支（約 601 行）先看 `result.tool_calls`，沒有先處理 FAILED／CANCELLED。探針先送 tool_request 再丟 ConnectionError，工具仍執行一次，下一 generation 回答後 run 最終是 COMPLETED。

HEAD 已有相同 dispatch 優先順序，所以不是 RT-008 新 regression。RT-003 的 terminal 收斂與 RT-008 journal 沒有消除它；journal 會把這次動作正常記下，而不是修正錯誤決策。這違反 SPEC「輸出後失敗停止並保留狀態」的要求。

最小修補：在既有 orchestration 邊界先裁決 generation 結果，再決定 accepted batch；失敗時不得開始新 dispatch，也不得透過另一 round 抹掉失敗。RT-009 接入 retry/fallback 前先補這項 gate，並覆蓋第一 round、continuation、取消及部分 tool stream。不需更換 LanguageModel port。

### AR-04：terminal 狀態長期留在 process RAM（MEDIUM，source＋計數確認）

`IntegratedCompanion._terminated`、`_seen_calls`，以及 `ToolOrchestrator._run_contexts/_proposal_contexts` 沒有 terminal eviction。兩個 terminal runs 後探針仍有 2 個 terminated IDs、2 個 run contexts、1 個 proposal context。`_active` 只 discard task，也保留 run key。

這些是 process-lifetime instance state，**不是新增 module-global singleton**。但其 lifetime 超出 run，會隨使用時間增長，並已與 AR-01 的功能錯誤交織。未做長時 RSS 量測，不宣稱已 OOM。

沿用現有 fence，在 delivery／cleanup 完成後做有界保留與清理；不可單純清空，否則 late callback 可能復活。先補固定 run 數量後的 state-bound 與 late-event 測試，再做 soak。不要增加另一個 state manager。

### AR-05：資料表與 mutable callback 成為隱含 runtime 契約（MEDIUM，靜態證據）

RT-008 的 proposal repository 直接讀 journal／agent_runs，run repository 的 reconciliation 直接改 tool_proposals；`IntegratedCompanion._ensure_core:930` 事後指定公共 `journal_hook`。原本分開的 repositories 現在需要共同理解 ownership、狀態與初始化次序。Single Gateway owner 下可運作，但若擴增 controller 或背景工作，最後指定的 hook 及全庫 reconciliation 會成為風險。

這不是已重現的 multi-owner corruption，也不是必須立刻新增 repository interface 的理由。先固定單 owner 契約、精確 proposal binding 與 failure injection；後續 RT-010/015 不能自行建立另一套 journal 或第二個未協調 owner。

### 其他 review areas 的結論

| 檢查項 | 判斷 |
|---|---|
| Core → UI／provider／device direct dependency | 本批新增 Core 參數只有 ModelMessage 與 optional async callback；未見新增具體 UI／OS／MQTT import。現有 boundary tests 通過 |
| Circular dependency | `integrated` 引用 GatewayHub，Gateway main local-import IntegratedCompanion 是既有相互依賴；本批未見新增 import-time cycle。維持風險註記，不為消除檔案相依就搬家 |
| Tool/provider/device 滲透 | tools 依賴 ports.models 的 ToolCall／ToolDefinition／CancellationToken，屬共用 port types；沒有把 provider transport 或 device driver 放進工具服務 |
| Gateway responsibility leakage | main 仍有 executor validation／composition closures，屬既有集中責任；RT-004 已移出程序 lifecycle。新增 readback、effective config 與 writer fence 有實際用途，不再要求全面拆 Gateway |
| Duplicated abstractions | agent_steps 舊 ledger 與 canonical journal 是相容與恢復的不同用途；目前無需合併。DEFAULT_MODEL_TOOLS、catalog 與 legacy alias 不構成第二套 runtime registry |
| Compatibility boundary bypass | AR-02 已確認。Rust 未接主入口是已記錄的分立路徑，不是最近偷偷繞過原本已啟用的 Rust grants |

## Migration quality / Technical debt introduced

遷移仍是 incremental：optional messages、startup-fixed profile、additive migration、相同 HTTP/WS 入口都有保留；未見整包搬移或改寫角色算法。RT-004 profile freeze 修補有價值，不能恢復成 dispatch 時重讀 env。

| 負債／相容路徑 | 是否現在移除 | 收斂條件 |
|---|---|---|
| legacy/candidate 分支分布在 controller、executor、TTS、catalog、UI | 不移除；目前仍是 rollback 路徑，但缺少明確退場 gate | 真 provider 閉環、owner 相容驗收、隔離資料 rollback rehearsal、未完成動作 fence 全部完成後，再決定 default promotion／舊路徑退役 |
| arguments-only handler adapter | 保留 public callable 相容；修 AR-02，不能永久繞過 cancellation | candidate 中每個 handler 都有可驗證 lifetime；已 detach 的例外明示 |
| agent_steps＋journal 雙寫 | 保留；terminal finish_journal 與 append 分兩次 transaction，現有 crash-window test 已處理 restart | 補 commit failure／同程序 retry，明定 canonical source；不建立第三份 history |
| `start_journal()` 非 atomic 入口 | production 使用 atomic `start(runtime_backend=...)`；目前是 repository 測試入口，沒有逾期 production caller 證據 | 禁止後續產品 caller 用拆開 start/journal 方式建立 run；無需現在刪 helper |
| mutable history＋`on_messages_ready` callback | 接線有 pre-provider checkpoint 價值；目前可保留 | RT-010 重用既有 context，避免 Core 與 controller 各自 restore／append |
| retention／identity scope | 已造成 AR-01/04，不應等到 scheduler 才處理 | run 結束清理、重啟 pairing 與 late-output fence 一起驗 |

**Rollback 尚有條件。**已驗的是新 binary 切 legacy、舊 migration loader／table reader 相容，以及 source reverse patch applicability；不是正在執行工作時的部署回滾。回退必須先停止新工作、清理 owned jobs、保存 unknown，保留 013、新 reader 與 persistent proposal guard。任意回退 RT-008 前 binary 會失去該 guard，不能因 old loader 接受 schema 就宣稱安全。

RT-008 evidence 已記錄舊 operational test 誤將 draft 013 套入 default DB。後來恢復原 SQL、隔離測試目錄且 launcher 回歸通過，但這仍是違反事前隔離／backup 程序的歷史事故。不能將它解釋為 DB downgrade 成功；本次未獨立驗證私人 DB 事故前後內容。

## Regression risk changes

2026-09-30 的 REGRESSION_BASELINE 仍可作歷史基線，**不能繼續作目前完整 gate**：F11 已解、RT candidate 與 schema13 未包含其中；DOCUMENT_STATUS 還寫 implementation 未開始／全部 PLANNED。Roadmap 與 STATUS 已更新，但讀者仍可能把不同日期的文件當同一現況。本 review 作本次增量基線，不改寫歷史測量。

| Subsystem | 風險變化 | 必要補充 baseline |
|---|---|---|
| Native loop / batch | 單批正確性改善；跨 run identity、失敗 generation 仍有缺口 | AR-01/03 的失敗案例；同 session 連續 run＋restart＋不同 provider ID 策略；失敗時零 dispatch |
| Execution / cancellation | argv bounded output、owned child cleanup 風險下降；非 contextual handler 仍高風險 | AR-02；browser/application 合成阻塞、manual approval、active shutdown、取消後零新副作用或明確 unknown |
| Persistence / recovery | crash 後盲目重播風險下降；跨表 ownership 與 commit failure 的耦合增加 | checkpoint/dispatch/observation/final transaction 失敗；同程序 cancel/retry；舊 approval 不能污染新 run；版本不支援時 fail closed |
| Long-lived runtime | 新 run/proposal maps 增加累積風險 | terminal 後 map size 有界＋仍能拒 late callback；之後才做 soak/RSS 驗證 |
| Qwen / frontend | 已有 worker＋前端取消、GPU 與 owner 歷史驗收，風險下降 | 保留 fake-worker／actual JS／HTTP disconnect gates；只有改動 audio lifecycle 才重跑相鄰真機驗收 |
| Context / memory | journal 增加可恢復來源；run history 不受 WorkingMemory 12 則限制 | 巨大工具結果、多 round context budget、pending pair 保存；session A/B、legacy assembled prompt 不重解析 |
| Provider policy | main 還是單 provider；未新增 fallback 外送風險 | RT-009 必測 tool emission 後 failure、local_only、未配置 cloud budget、cancel backoff；synthetic 過後另做真選用 provider 閉環 |

標準全套雖綠，以上探針仍重現缺陷，說明需要新增 baseline cases，而不是再次重跑同一套當成更多信心。Rust／設備未改，不因本輪 Python review 擴增不相干驗收。

## Roadmap adjustments

保留原 RT 編號；下列為 scope／dependency 修正建議，不是 priority ranking。本次不批次改 roadmap Status。

| Task | 決定 | 依 implementation reality 調整 |
|---|---|---|
| RT-001–008 已完成成果 | KEEP | 不重做已通的 message/batch/execution/catalog/journal；RT-003/005 記修補 gate，RT-008 ownership 回歸附在既有卡 |
| RT-009 | KEEP；MERGE 卡內重複 policy | retry/fallback 沿用 FailoverModel，一份 attempt／privacy／emission policy。先修 AR-03；新 fallback 不得早於此 gate。不要另建 Router framework；main 的完整 JSON settings 合併不是本卡必要重構 |
| RT-010 | KEEP；CANCEL 已被 RT-008 解決的重複子工作 | 僅將既有 canonical records 接回 session 的近期 context；取消重建 run journal／再做 startup replay/reconcile 的子工作。RT-008 readback 沒有跨 run history hydration，故不能取消整張 RT-010。先解 AR-01，明確 raw user 與 assembled system context，避免重複注入舊 prompt |
| RT-011 | SPLIT；REORDER／DEFER | 卡內拆「量測＋hard budget／明確超限」及「有來源摘要」。budget 可依 RT-002/008 先於 RT-010 的 restore 擴大，因現有 per-run history 已會增長；pending pair 必須完整。摘要待 restore 與超限實測證明需要後再做，不強迫新增 context.py |
| RT-012 | KEEP，但暫緩擴張 | stateless browser 缺口仍真實；先完成 AR-02 cancellation／close gate，再包現有 driver 做 session ownership／TTL。不要趁此重寫 browser 或加入 credential persistence |
| RT-013 | DEFER | Python bounded execution 已解 lifecycle／output 問題，不需為語言分工搬移。Rust scoped grant/read 能力仍有不同價值，尚不能判整卡無用；需先有具體 scoped read caller 與 parity 驗收，再啟動 |
| RT-014 | KEEP，維持 RT-010 後 | journal 是對話／工具 provenance，不是正式 long-term memory ingress；沿用現有 revision／correct／delete，無需新 memory store |
| RT-015 | DEFER | 前景 ownership、retention、session restore／memory ingress 完成前，背景 pump 會放大現有耦合；維持預設 off，不為排程而新增第二個 runtime owner |

目前沒有證據支持取消 RT-009–015 任一整卡；明確 CANCEL 的是 RT-010 重複 run-recovery 子工作。RT-013/015 是延期而非假裝需求已解決。若日後量測顯示 hard budget 已足夠，應 CANCEL RT-011 摘要子工作，不以原規格曾寫摘要為理由硬做。

## New blockers

「新」指本次 review 納入後續 gate，不表示每項都是最近引入。

- **Candidate promotion／多 run session gate：**AR-01 identity scope 與持久 ownership 未修；錯誤可能變成未處理 DB exception。RT-010 不能繞過。
- **Lifecycle／browser 擴張 gate：**AR-02；run terminal 不代表所有 handler 已停止。不得把 argv 測試外推成所有工具取消完成。
- **Provider retry/fallback gate：**AR-03；失敗 generation 仍 dispatch。先固定 terminal/error 行為，再接重試。
- **長期運行／背景工作 gate：**AR-04 retention 未界定；single owner／journal failure handling 尚無足夠測試。
- **發布 gate（既有未解）：**真選用 provider 工具閉環、隔離資料部署 feature-off rollback、24h soak。RT-006 owner 驗收已完成，不能重新列為待確認。ESP32／HA／第二節點仍不阻擋前景 Python 的小幅修補。

## Freeze zone changes

RED 表示凍結功能擴張，只允許有證據的窄修補與必要契約／測試；不是禁止修已重現缺陷。

| Subsystem | 前次 → 本次 | 邊界與解凍條件 |
|---|---|---|
| Run/proposal identity、journal reconciliation | YELLOW／schema RED → runtime 交界 RED | AR-01 修補＋restart／old approval regressions；既有 001–013 不改 |
| Dispatch terminal decision、handler cancellation | YELLOW → RED（交界） | AR-02/03 反例轉正式測試並通過；其他 argv 程式群組功能保留 |
| Bounded argv implementation | YELLOW → YELLOW，風險降低 | 不重構；變更需 flood／PGID／timeout／detach 回歸 |
| Qwen lifecycle／speech consumer | YELLOW → YELLOW，已有驗收 | worker 單 owner 與音色維持；缺 soak 不代表重新開音色／GPU架構計畫 |
| Catalog / effective config | YELLOW → YELLOW，catalog 較穩定 | 限現有 schema subset；新增工具前明定 readiness、lifetime 與授權 |
| Character / affect / relationship | YELLOW → YELLOW | 沒有近期 algorithm drift 證據；保持既有 state／畫面回歸 |
| Brain / proactivity / scheduler | YELLOW → YELLOW；接入 DEFER | 不因 runtime 多了 journal 就啟動 planner／背景 pump |
| SQLite schema、identity、grant wire | RED → RED | 只能因 blocker 做 additive 變更及 upgrade／rollback gate |
| Live2D assets、ESP32 firmware | RED → RED | 無本次改動需求 |
| Review／evidence／隔離測試 | GREEN → GREEN | 可補反例、文件時點及驗收證據；避免對 default data 跑 migration |

## Hermes relevance

以 repo 已保存的固定 Hermes snapshot analysis 為比較基線；本次判斷只依 SIRO reality，不重新宣稱外部 Hermes 新版本能力，也不新增依賴。

| 原 concept | 本次決定 |
|---|---|
| Agent loop | KEEP SIRO batch loop；REJECT 再移植一套 loop，只修 AR-01/03 |
| Tool registry／availability | KEEP RT-007 descriptor；REJECT 第二個 registry 或為比照 Hermes 擴充 plugins |
| Provider abstraction | KEEP LanguageModel；REJECT framework replacement |
| Routing | DEFER 完整多 provider router；RT-009 只處理有需求的 bounded policy |
| Retry／fallback | KEEP RT-009，沿用 FailoverModel；先解 emission/error gate |
| Session | KEEP RT-010 的 session context hydration，重用 RT-008 sources |
| Memory | KEEP SIRO source/revision 模型；REJECT 用 Hermes memory 取代人格記憶 |
| Context compression | KEEP hard budget；DEFER summary，無量測收益就取消 summary 子工作 |
| Cancellation | KEEP 現有 token/context/group cleanup；REJECT 通用新 supervisor；補 arguments-only ownership |
| Persistence | KEEP SQLite／journal；REJECT 新 persistence framework 或再做一個 run store |
| Error wrapping | KEEP 最小可辨識 failure／unknown；不建立無 caller 的 error taxonomy；優先修真實失敗被轉成功 |
| Execution backend abstraction | KEEP 已有 argv facade；DEFER Rust backend，REJECT 為抽象而加 backend 層 |
| 整體 framework replacement | REJECT，近期成果沒有提供更換架構的理由 |

## Recommended next 3 RT tasks

下列是有明確工作範圍的下一組卡，**不排序、不改編號**；上列修補 gate 是依賴，不可跳過。

- **RT-009：**先以 AR-03 的失敗 generation／tool emission 案例鎖定 dispatch 規則，再用既有 FailoverModel 實作最多兩次 attempt、取消 backoff、privacy／cost gate。驗收後不新增 router abstraction。
- **RT-010：**先完成 RT-003／RT-008 的 AR-01 ownership 修補，再從既有 canonical journal 還原有限 session context；涵蓋三次 restart、A/B、legacy raw/assembled 區分，不重建 journal、不自動重送 unknown。
- **RT-011 的 budget 切片：**量測現有 run history 及工具輸出的 request size，限制 provider request 並保持目標／pending pairs；可先於 RT-010 擴充 restore 範圍。摘要子工作維持 DEFER。

RT-005 的 AR-02 修補與 AR-04 retention 應列入既有卡的追加 acceptance，先於 candidate promotion、RT-012／015。它們是修正本批已承諾的 lifecycle 邊界，不是新增功能卡或重新設計 runtime。
