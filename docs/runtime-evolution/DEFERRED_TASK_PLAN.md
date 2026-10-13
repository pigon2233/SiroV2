# Deferred Runtime Evolution tasks — 解除延期規劃

> 2026-10-06 後續交付：使用者已明確授權三項實作，有界產品切片已完成。本文的 DEFER 是規劃時狀態；目前狀態與限制見 [PRODUCT_QUICKSTART.md](PRODUCT_QUICKSTART.md) 和 roadmap 最新交付段落。

日期：2026-10-06。依據 [Architecture review](ARCHITECTURE_REVIEW.md) 與現有程式；本文件只規劃，未實作、未量測以下目標。保留 RT 編號、DONE 歷史及三項 **DEFER**，不以計畫完成代替功能驗收。

## 共用決策方式

每項沿用原 RT 卡，先做 evidence slice，再決定 KEEP／縮小 scope／DEFER／CANCEL，通過後才改為可施工。三項無排名，也不互相構成自動開工依據。

- Evidence slice 產出放在 `docs/evidence/RT-013/`、`RT-015/`、`RT-011/summary/`（後者為規劃路徑）。使用合成資料、暫存 DB、隔離服務；記錄 source revision／digest、命令、原始結果與未驗項。
- 解除 DEFER 必須有具體 caller、可量測收益、最小 scope、已滿足依賴、相容／回滾方案。缺少收益保持 DEFER；證據證明原需求已由現況解決則 CANCEL 該未實作切片，保留歷史。
- 本文件的數值是**待驗收目標**，不是已量測成果；施工前固定資源上限與基線，不在測試失敗後放寬門檻。
- AR-06/07 仍阻擋依賴 native 多工具閉環／乾淨 native 測試環境的驗收。Rust／排程的隔離只讀驗證可獨立進行；不可宣稱整體 runtime gate 因此通過。
- 不新增通用 framework、不修改 persona／affect／授權原則、不以新抽象掩蓋既有缺陷。預設 off、startup 固定設定、進行中工作先 drain；所有功能關閉時保留既有安全邊界。

## RT-013 — Rust read-only backend

**Status：DEFER。** RT-005/007 已完成，但「有 client」不是「需要對接」的證据。

### 已知現況與待回答問題

`src/siro/adapters/runtime.py` 的 LocalRuntimeClient 已提供 bounded Unix socket health／execute／revoke；execute 帶 scope 與 signed grant，RPC 上限 64 KiB。現有 `tests/contract/test_runtime_client.py`、`tests/integration/test_runtime_boundary.py` 可作基線。尚未指定有收益的 production scoped-read caller；不能以 health probe 當成工具接入完成。

### Evidence slice（尚不接 production）

1. 列出現有 catalog 的實際 read/list caller、目前 Python 路徑、權限與 result 格式，對照 Rust 已支援 capability。只選一個語義一致的候選；找不到即保持 DEFER。
2. 對同一份合成目錄／檔案建立 parity matrix：正常、空內容、缺檔、invalid／expired／revoked grant、scope escape／symlink、oversized output、取消、runtime offline。區分 broker 真執行與 client mock。
3. 比較 Python 與 Rust 在該 caller 的 scope enforcement、結果／錯誤、資源與部署成本。記錄相同 fixture 的 latency／輸出大小；至少證明一項目前 caller 缺少且 Rust 確實提供的必要邊界或收益。純粹「Rust 應較快」不成立。
4. 產出一頁決策：caller、原問題、實測改善、接入成本、是否值得維護第二個 backend。若 Python 已滿足需要而無可辨識收益，CANCEL 此接入切片；若需求尚未出現則 DEFER。

### 通過後的最小 implementation slice

只把選定的一個 read 或 list 能力經既有 execution facade 接到 LocalRuntimeClient；在 Gateway composition 選 backend，沿用現有 catalog／Policy／grant。工具名稱、arguments、observation、call ID 與 journal ownership 不改。不支援或 runtime offline 明報；不得失敗後偷轉較弱 Python path。

- 預期檔案：`src/siro/services/tools/execution.py`、`src/siro/adapters/runtime.py`、必要的 Gateway composition、上述 runtime tests 與該 caller integration test；實際 scope 須由 parity 結果確認。
- 禁改：Rust wire/schema、grant 信任模型、sudo、write/install、Core identity／memory、設備與音訊。若必須改這些才有收益，原 slice 不開工，另作最小設計評估。
- Acceptance：選定 caller 真正經 Rust 執行有可查證證據；parity 全部成立或差異有既有契約支持；拒絕／越界零執行；offline 時文字對話正常；無隱性降級；取消後零 late observation。
- Regression：runtime client/boundary、tool catalog、bounded execution、batch／journal／cancel、candidate-off 與既有 Python caller；涉及 native 閉環時先解除 AR-06/07。
- Rollback：停新 dispatch、收斂 Rust-owned 工作，再於新 run 切回已驗證且符合相同權限邊界的 Python profile；不在失敗 request 內 fallback，不重送 unknown 工作。
- Risk：HIGH；重點為 scope／grant 語義不一致及雙 backend 維護，而非語言選擇。

## RT-015 — 既有排程的有界接入

**Status：DEFER。** RT-008/014 已完成；剩餘 gate 為 retention、single-owner 與 foreground 優先，不能再寫成等待 RT-014。

### 已知現況與待回答問題

`src/siro/core/consolidation.py` 的 ConsolidationScheduler 以 `_runs` 擁有 task；`wait()` 才 pop，`close()` 才清空。現有 schedule 會拒絕同 key，不能直接推論成全域 queue cap／長期去重。`core/proactivity.py` 已有 disabled、quiet、busy、speaking、daily limit、cooldown 規則。先沿用這些邊界，不新增獨立排程框架。

### Evidence slice

1. 定義唯一 lifecycle owner：單一 Gateway lifespan 建立／關閉一個 pump，producer 不能各自啟動 pump。測 double-start／double-close；多進程／多 Gateway 不在 scope，不能以 process-local singleton 宣稱跨進程互斥。
2. 列出 `_runs`、runtime run/proposal/terminal 索引、候選 queue、journal／cursor 的建立與移除時點；區分 RAM 清理與持久資料 retention，不順便改 audit 保存政策。
3. 在隔離 harness 用 fake clock 跑七天的 normal／flood／cancel／restart；每批收尾量測 map／queue 數量、pending tasks、DB 增量與 cleanup 延遲。wall-clock RSS soak 另記，fake clock 不替代真時間資源測試。
4. 先固定 capacity、每 tick batch、timeout／shutdown 上限與資料保留責任；壓測驗證 queue 不超 cap、完成工作不持續佔 active map、停機無 owned tasks。無法成立時只修 ownership／cleanup 局部根因，不建立持久 queue 平台。
5. 釐清 restart 去重的既有 durable key／cursor 能否復用。沒有可用機制就維持 DEFER，先寫最小持久化設計與 migration／rollback；不得假稱已有 cursor，也不得沿用 RAM key 宣稱跨重啟 exactly-once。

### 通過後的最小 implementation slice

只接一種合成可驗的只讀／候選工作，單 owner、單一執行 worker、有界 backlog；預設 off。第一版不派送主動訊息、不執行設備／工具效果、不自動寫 memory facts。foreground 開始時停止接收背景工作並依既有 cancellation 收尾；quiet／busy 等規則照用。

- 預期檔案：Gateway lifespan／composition、必要的局部 scheduler adapter、`tests/integration/test_consolidation.py`、`tests/test_proactivity.py` 與 lifespan integration；只有證據支持時才修改 consolidation cleanup。
- 禁改：Core scoring、persona／affect、設備、音訊、grant、主動發話預設、memory provenance。新 schema 不屬預先授權 scope。
- Acceptance：disabled 零排程／訊息；quiet／busy 零違規；一個 owner、同一候選零重複接受；queue／active count 守 cap；foreground 不被背景 task 等待鏈阻塞；有界 shutdown；restart 不自動重播積壓效果。
- Regression：consolidation crash／idempotence、proactivity rules、gateway startup/shutdown、run journal、取消與 memory ingress privacy。任何 LLM 工作還須遵守原 budget／retry，不另造模型路徑。
- Rollback：停 producer、cancel/drain owned task、保存既有且已驗的 cursor／journal，再以 off 重啟；未執行候選不自動 replay。若無 cursor，不假造保存動作，按已驗證的丟棄／重建候選契約處理。
- Risk：MEDIUM，若引入 durable storage 或自主效果則超出本 slice。通過 gate 僅允許有界候選 pump，不解除多 owner 或自主效果限制。
- CANCEL 條件：没有一種必需的背景 caller，且現有 explicit foreground 流程已滿足需求；需求只是尚未明確則維持 DEFER。

## RT-011 — 可撤銷 summary 切片

**Status：DEFER。** budget 子項已完成不代表 summary 有必要；AR-06 的合法 multi-call shape 問題不能用壓縮繞過。

### Evidence slice

1. 先解除 AR-06/07 對 native 組合驗收的阻擋，再在支援的 profile 量測「六組 raw history＋工具閉環」的 token 分布與拒絕原因，區分合法超限、unsupported shape、巨大單一 observation。使用合成長對話與明確任務目標，不能蒐集私人對話作測試 fixture。
2. 記錄可重複的任務失敗：哪個已完成區段佔用 budget、保留哪些事實才可繼續、summary 是否真的比現有有界錯誤／recent window 改善。若現有窗口已足夠則保持 DEFER；原需求已消失才 CANCEL summary。
3. 建立不可壓縮集合：fresh system、原始目標、授權與來源、pending tool pairs。只選完整且已完成的舊區段，不能拆 assistant/tool pair，不能刪原始 journal/history。
4. 定義 derived summary 的 source event IDs、source version/hash、session、privacy 與生成版本；來源修正／刪除／不可讀時必須失效。不得只依記憶文字相同判斷來源有效。
5. 用固定 acceptance fixtures 比較 raw 與 summary 的任務相關 facts／pending／policy 保留；記錄 compression ratio、額外 latency／model attempts。收益需同時滿足可放入現有 budget 與不損失必要內容；縮短文字本身不是 acceptance。

### 通過後的最小 implementation slice

只提供 candidate 的可丟棄 context 衍生物，先不新增 summary DB/table 或 memory store；復用現有 model port／privacy route。若使用 LLM 產摘要，其 input/output、attempts、timeout 與取消也有預算，且不可呼叫工具。summary 只能當有來源資料，不能升格 system／授權指令或 persona facts。

- 預期檔案：`src/siro/services/agent/context.py` 的局部接合或同目錄小型 helper、必要 conversation context wiring、context／native budget／session restore tests。正式檔案清單由 source-version 能力調查固定，不預先重構 ConversationEngine。
- 禁改：journal 原始紀錄、memory／identity schema、persona facts、provider wire、tool policy、既有 budget guard；不擴張新 provider profiles。
- Acceptance：摘要只含完成區段；目標／授權／pending 配對完整；source correction/delete 後舊 summary 零使用；跨 session/privacy 零混入；摘要後仍經 byte/native guard；timeout／cancel／malformed summary 不派送工具。
- Fallback：raw context 仍可在 budget 內則使用 raw；否則維持明確有界錯誤。不得截斷 pending pair、放寬 guard 或無限再摘要。第一版每次 context 建立最多一次摘要嘗試，為待驗證上限。
- Regression：native multi-call continuation、context exceed、session restore、memory revision/privacy、failed generation zero dispatch、cancel／restart；測 source hash 變化與 summary 失效競態。
- Rollback：新 run 停用 summary、丟棄 derived cache、保留 raw sources／journal，回到原 bounded context 路徑；進行中 run 不混換 context 版本。
- Risk：HIGH；主要為失真、來源失效、privacy 與額外模型成本。若需要持久摘要才能有收益，先評估最小 schema 設計，不藉此做 memory consolidation。

## 每項開工前要附的判定表

| 必填項 | 通過標準 |
|---|---|
| Caller 與問題 | 真實入口／call path，說明現況不能滿足什麼 |
| Evidence | 可重現命令、source digest、合成 fixture、before 結果；mock 與真整合分開 |
| Benefit | 對照現有路徑的必要改善，非新增 abstraction 數量 |
| Scope／非 scope | 最小 files、禁止改動範圍、相容性與依賴 |
| Gate | 原阻擋逐項通過；未驗不寫 PASS |
| Rollback | isolated rehearsal；不丟 provenance、不重播效果、不降低權限 |
| Disposition | KEEP 並解除 DEFER，或縮小／DEFER／CANCEL；附理由且不重編 RT |

本輪沒有執行上列 evidence slice 或 production repair；三項維持 DEFER。此規劃使後續工作可從明確驗證開始，不預先承諾三項都需要實作。

## 2026-10-06 authorized evidence follow-up

本輪已執行隔離 evidence slice 的第一個否決門檻，不是完整功能驗收。原先「未量測」敘述為本文件初版歷史。

| 切片 | 本輪 evidence | Disposition | 尚缺門檻 |
|---|---|---|---|
| RT-013 | Rust linux executor 有 filesystem.read/list；目前 production catalog/dispatch 沒有語義相同的 scoped read/list caller，computer.execute 的 argv 契約不能直接替換 | DEFER | 指定實際 caller 與必要收益，再進行 parity/rollback；health/client 測試不能代替接入 |
| RT-015 | 合成 scheduler 100 個 unique key 工作完成後 active=0、retained=100；close 後=0 | DEFER | bounded retention、pump owner、foreground優先、restart與有界shutdown；單次 close 能清空不能证明七天運作有界 |
| RT-011 summary | 六組合成中文 history reference input=6736 tokens，default window 下 validate 通過；不是 production workload 的需求證明 | DEFER | 任務相關的可重現超限需求、source/version失效、收益及安全比較；不可用人工縮小 window 代替需要摘要的證據 |

原始輸出、可重跑 synthetic probe、相鄰基線及修復證據：`docs/evidence/RT-011/ar06-ar07/`。沒有私人對話或模型呼叫。AR-06 局部缺陷已修復、AR-07 provisioning 已補，但 whole-check/遠端 CI 不宣稱 PASS。三項未解除，因上述 gate 尚不成立，不是忘記更新 status。
