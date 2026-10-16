# RT-009 Independent Verification — 2026-10-05

Final verdict: **REGRESSION_DETECTED**.

建議不保留 RT-009 DONE，改為 **FAILED_VERIFICATION**，待修復 durable backend provenance 並重驗。三項本卡 measurable retry criteria 通過，但 compatibility / regression gate 失敗。未修改 production code、原測試、roadmap、STATUS 或私人 DB；本輪新增內容只在此 verification 目錄。

## 1 — Identify target

讀取目前 RUNTIME_EVOLUTION_ROADMAP，依 DONE 與 completion date 自動選 RT-009（2026-10-05）。RT-003 的 10-04 FIX 晚於其原完成日期但早於 RT-009；RT-010 等仍 PLANNED/DEFER/BLOCKED，不作開發。

## 2 — Reconstruct intent

閱讀 RT-009 的 Objective / Problem / F07 audit evidence / scope / acceptance / compatibility / tests / rollback，以及 ARCHITECTURE_FRICTION_MAP、RUNTIME_EVOLUTION_SPEC、REGRESSION_BASELINE、COMPATIBILITY_PLAN、D24、CONTRACTS、STATUS、AGENTS 與相關交付規格。implementation REPORT 僅作 evidence 索引，並非通過依據。

F07 是 FailoverModel 未進 main，原邏輯可逐個 backend 嘗試、任何 exception 都 fallback、只用非空文字作 emission fence。目標為每 generation 最多兩次 total invocations；只在 transient pre-emission 且 privacy/budget 允許時 retry/fallback；cancel 中斷 backoff；text/tool intent 後停止；保持 legacy、env provider priority、port、schema、授權與前卡修復。Rollback 是下一次 startup 關 SIRO_MODEL_RETRY_ENABLED，保留原單 provider 與既有 journal/fences。

## 3 — Actual code / callers / consumers

* gateway.main:1015–1052 先依舊 priority 選 Ollama / configured cloud / offline；只有 candidate 包 FailoverModel，startup 固定 SIRO_MODEL_RETRY_ENABLED=0|1。main 包單一既有 provider，額外 cloud budget 固定0，未偷偷構造 cloud fallback。legacy / feature-off 路徑是真正 compatibility 開關。
* FailoverModel.stream:51 的 range(2) 是唯一 attempt tier。ConnectionError / TimeoutError / httpx.TransportError 或429/502/503/504 可重試；nonempty text、任何 tool_request、finished fence；維持 messages/privacy/output budget，第二次 private generation ID 更新。token/task cancellation、backoff 與整體 ConversationEngine timeout 均有實際 caller。
* OpenAI _stream_response 緩衝 tool fragments，已有 calls 時 exception note 阻止 wrapper 重試；原 exception class 保留。這個額外 adapter 修改必要，D24 有記錄，provider public port 未改。
* wrapper 輸出由 ConversationEngine 消費，Core / Integrated 接續；只有 COMPLETED generation 的工具 batch 被接受，FIX-001 initial / continuation gate 保留。main tests 經實際 Core、SQLite、ASGI 與真 Python file-write subprocess，不是 detached helper。
* 未發現 TODO/NotImplemented/stub 替代核心行為。backoff 的 except TimeoutError: pass 代表等待已到期後第二次 attempt，並非未實作。舊元件沒有另開 retry tier。wrapper 與 adapter 各負責可見 chunk / 下層緩衝 intent fence，非重复 fallback 邏輯。
* **錯誤 consumer wiring**：Integrated.respond 將 self._model.name 存 runtime_backend。現在 main 注入 wrapper，其 name 固定 failover，導致 SQLite run_journal.backend 及 readback backend 失去原 selected provider 名稱。/v1/runtime.routes 仍正確，不會修復已持久資料。

## 4 — Scope discipline

scope.json 記錄目前五個 source/test digests 全吻合 task evidence。僅在 temporary copy reverse scoped implementation.patch，三個 before source digests 全吻合；沒有回退 actual working tree。

直接變更三個 production files：failover、gateway、openai adapter；兩個測試。adapter 超 roadmap 原 expected 兩檔，但 D24 已明確記錄 buffered intent 的必要增量。未見 mass rename/move、unnecessary refactor、port/required API/protocol/schema/權重/identity/config JSON format 變更。新增 optional startup env switch 有 validation 與 feature-off tests。

然而「不改 journal 檔」不等於沒有 journal regression：wrapper name 經原 caller 寫入 durable metadata，屬此次組裝變更造成的間接跨 subsystem 影響。RT-008 的固定 backend provenance 被破壞。

## 5 — Tests rerun / quality

本輪 related.log：**183 passed，0 skipped/xfail，3 dependency warnings，59.20s**，exit0。包含新 failover_policy / provider_retry，舊 model_adapters、conversation、integrated_companion、agent_batches、run_journal、gateway、gateway_main、execution_lifecycle、tool_catalog、gateway_terminal_fence。

ruff.log PASS；mypy.log **176 source files PASS**。未重跑全套；implementation 的376 passed/5 opt-in skipped 是歷史 evidence，不當作本輪測試結果。

test_failover_policy 執行 production wrapper，涵蓋兩/三 backend、same backend retry、request preservation、429/503/timeout、permanent errors、text/tool/finished、cloud privacy / explicit request budget、pre/token/task cancel。兩個真 localhost HTTP fixture 使用 actual Ollama / OpenAI adapter + Httpx transport，測429與 premature EOF after buffered tool intent；server 回應為 synthetic，非真 model provider。

test_provider_retry 進 actual main composition + Core/SQLite/ASGI；model adapters 是 synthetic；成功工具寫檔是真 subprocess。涵蓋 legacy、feature-off、startup env flip、兩次失敗、partial text/tool failure、continuation failed intent、primary cloud one request。Error path 有覆蓋，但沒有 assertion 檢查 journal.backend，因此可全綠卻漏掉 regression。

本輪獨立 test_independent.py 顯式執行（不屬 pytest default testpaths=tests）：重用現有 actual-main cloud-failure fixture，其原 assertions 全通過，再直接讀真 temporary SQLite run_journal.backend。

* **Before：1 passed**（before.log）。只在 temporary copy reverse RT-009 patch，並顯式 assertion import 路徑為該 temporary src；before source digests 已驗證。
* **Current：1 failed**（current.log）。expected synthetic-cloud，actual failover。不是只 spy/mock repository；SQL 查的是實際持久 row。

沒有發現本卡測試 skip/xfail 或未收集 dedicated tests；真 provider opt-in cases 本輪沒跑，NOT VERIFIED。沒有長期 repetition/soak 資料，不宣稱已排除 flaky。fixtures 的有限 timeout 與 cancellation synchronization 已檢查。

## 6 — Relevant REGRESSION_BASELINE

| Baseline | Result | Evidence / limits |
|---|---|---|
| fallback/retry main wiring / emission boundary | PASS | actual main cases、兩 attempt cap、buffered fragment + real local HTTP EOF fence |
| provider calls / adapter contract | PASS | adapter contracts + localhost transport fixtures；真服務 NOT VERIFIED |
| conversation/streaming | PASS | conversation、Integrated、Gateway、terminal fence；partial failure 沒有替換輸出 |
| tool calls / failed generation intent | PASS | initial/continuation tests，沒有新增錯誤 file effect，existing batch/cancel cases |
| cancellation/timeouts | PASS | token/task/pre-cancel、backoff cancel、conversation deadline與execution suite；不擴張為硬體音訊宣稱 |
| config / legacy / selected route | PASS | original provider priority、startup switch freeze、cloud額外budget0、diagnostic key canary |
| restart recovery / durable backend provenance | **FAIL** | 新 journal backend=failover；同一 actual-main案例前版 synthetic-cloud PASS、本版 FAIL；舊 crash suite仍通過不能抵銷 |
| real provider E2E / browser / deployed rollback / soak | NOT VERIFIED | 本輪不呼叫付費/真 provider、不碰現有8000服務；未做GUI或部署回滾 |

## 7 — Each acceptance criterion

| Criterion | Result | Evidence |
|---|---|---|
| 最多2 attempt（含首試） | PASS | range(2)、same backend/three backend cases；actual main最多兩次，後續 tool round 是另一 generation |
| emission 後零 fallback | PASS | text / tool / malformed empty intent / finished tests、buffered tool fragment fail note、真HTTP premature EOF；failed initial/continuation無新effect |
| 無未設定 cloud 外送 | PASS | LOCAL_ONLY gate、additional request budget0、cloud one original authorized request、local/cloud都配置不新增fallback |

PASS 限定執行過的場景與 production 組裝；cloud request count 不等於USD/day預算。main未設monetary budget故額外cloud attempt為0，符合保守限制。

## 8 — Issues / severity / required fixes / verdict

**P2 / MEDIUM — selected backend provenance regression。** gateway.py:1046 將 wrapper 作 selected model；failover.py:25 的固定 name 由 integrated.py:199 消費並持久保存；runs.py:474 原樣輸出。candidate retry預設啟用時，local/cloud/offline 的 durable backend 名稱皆變為相同 failover。未證明造成工具重播或外送，但妨礙 restart/audit 辨識原 provider，違反 RT-008 metadata 保留與本卡 compatibility。不是既有問題：before/current 相同 fixture分別PASS/FAIL。

Required fixes：保持 selected provider identity 與 retry policy wrapper identity 的區別，確保 journal 寫入穩定的 selected backend metadata；不改 public port 或 DB schema。將此 actual-main SQLite/readback assertion 加入標準 regression suite，至少覆蓋 local/cloud、retry on/off、reopen，重跑本輪相關 gate。不要把歷史 failover rows 靜默猜回原provider；需要明示未知或有證據的遷移。

Optional improvements： 釐清 implementation report 的「Protocol errors不重試」表述；目前 httpx.TransportError 類別很廣，應另測 LocalProtocolError / RemoteProtocolError / UnsupportedProtocol 的政策。這是文件/覆蓋建議，未用來增加本次 FAIL。補真provider/部署feature-off rollback/soak只在相应驗收授權與條件到位後執行。

**Final verdict：REGRESSION_DETECTED。DONE 建議改 FAILED_VERIFICATION。** 三項 measurable criteria 可保留PASS evidence，但不得以此略過已重現的 compatibility regression。
