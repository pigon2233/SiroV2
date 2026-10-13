# SIRO 2 介面與資料契約

狀態：設計契約 v1；T02–T04 轉成 schema、程式型別與 migration。下列欄位是實作基線，不是現成 API。

## 1. 事件 Envelope

```json
{
  "schema_version": 1,
  "event_id": "01900000-0000-7000-8000-000000000001",
  "type": "conversation.user_text.v1",
  "source": "cli.local",
  "subject_id": "owner",
  "occurred_at": "2026-09-23T06:00:00Z",
  "received_at": "2026-09-23T06:00:00.010Z",
  "trace_id": "trace-001",
  "causation_id": null,
  "session_id": "session-001",
  "turn_id": "turn-001",
  "sequence": 1,
  "priority": "interactive",
  "ttl_ms": 30000,
  "privacy": "local_only",
  "payload": {"text": "SIRO，你記得我們在做什麼嗎？", "language": "zh-TW"}
}
```

- 必填：schema_version、event_id、type、source、occurred_at、received_at、trace_id、sequence、priority、privacy、payload。subject/session/turn/causation/ttl 可 null，按類型進一步限制。
- 時間為 UTC RFC3339；排程顯示用 IANA timezone。延遲用同程序 monotonic clock；跨機需記 clock skew，不能直接拿不同主機 wall clock 算精確毫秒。
- event_id 全域唯一；sequence 只在 `(source, session_id, turn_id, stream)` 有序，不保證全域排序。媒體 stream 在 payload 指明。
- type 版本是 payload 語义版；envelope schema_version 是外框版。新增選填欄位可同版；刪欄位／改型別升版。未知主要版本拒收並產生診斷。
- privacy 為 local_only、trusted_lan、cloud_allowed。只允許向更受限方向收斂，adapter 不能自行提升。
- priority 為 urgent、interactive、background、telemetry；禁止模型自行把任意事件升為 urgent。
- 對外 envelope 單筆最大 64 KiB；文字過長回傳 validation error 或經明示分段。大型檔案、影像和聲音走 artifact reference。
- schema 驗證失敗不得觸發副作用；回覆錯誤碼及 trace_id，不回顯 token／密鑰。

## 2. 事件目錄與 ownership

| 類型 | 必要 payload | Producer → Consumer |
|---|---|---|
| conversation.user_text.v1 | text, language | CLI/Gateway → Core |
| conversation.turn_started.v1 | generation_id | Core → UI/Audio |
| conversation.text_delta.v1 | generation_id, index, text | Core → UI |
| conversation.turn_finished.v1 | generation_id, reason | Core → UI/Audio |
| conversation.cancel_requested.v1 | target_turn_id, reason | UI/Audio → Core |
| conversation.turn_cancelled.v1 | target_turn_id, generation_id | Core → 所有輸出端 |
| speech.intent.v1 | speech_id, text, voice_ref, affect | Core → Audio |
| audio.playback_started.v1 | speech_id, stream_id | Playback owner → Core/UI |
| audio.playback_stopped.v1 | speech_id, reason, last_sequence | Playback owner → Core/UI |
| presentation.intent.v1 | emotion, gesture, attention_target | Core → Renderer |
| world.observed.v1 | entity_id, property, value, confidence, expires_at | Adapter → Core |
| action.requested.v1 | action_id, capability, arguments, deadline | Core → Dispatcher |
| action.status_changed.v1 | action_id, attempt_id, state, result_ref, error | Runtime/Dispatcher → Core |
| memory.candidate.v1 | kind, text, source_event_ids | Consolidator → Memory |
| memory.committed.v1 | memory_id, revision | Memory → 投影／索引 |
| system.health.v1 | component, state, reason, observed_at | 各程序 → Monitor |
| compute.job_status.v1 | job_id, attempt_id, lease_epoch, state | Worker → Router |

`conversation.turn_finished` reason 只允許 completed、cancelled、failed。text_delta 與 TTS segment 各有 index，不能混用彼此序號。工具與 observation 的 payload schema 再由 capability schema 驗證。

## 3. Delivery、重送與 backpressure

| 資料 | 傳輸／保存 | 滿載策略 |
|---|---|---|
| text delta、pose、telemetry | NATS Core／WS；短暫資料 | pose/telemetry 合併最新；文字缺段用 snapshot 補 |
| action、memory commit、goal terminal | SQLite outbox → JetStream → durable consumer | 有界排隊；無容量時回 busy，不能静默丟棄 |
| cancel | urgent 即時通知＋Core turn tombstone | 獨立 urgent queue；重送仍冪等 |
| raw audio/image | 專用 stream／artifact store | 音訊 buffer 超限終止該 stream 並報錯，不無限堆積 |

初值：單連線 urgent queue 32、control queue 256；每 producer 有速率限制。writer 在 urgent 與 normal 間仲裁；有界 burst 保護，避免正常訊息永久飢餓。單一 frame 寫出超過 1 秒視為慢 client，斷開重連；不能從第二個 writer 搶寫 cancel。

outbox 與 domain mutation 同一 SQLite transaction；dispatcher 發送成功後標 sent。consumer 在本機 inbox 保存 event_id，業務提交成功後 ack。crash 導致重送時由 inbox/action ledger 去重。預設最多 5 次 delivery，之後 quarantine queue＋明確告警。去重紀錄保留不能短於重試／重播窗口；初值 30 天。

Replay 設為 read-only projection mode：可重建 world、memory index、trace；所有 runtime/设备 dispatch port 必須替換成拒絕副作用的 port。事件紀錄不能自動重播 shell 或開燈。

## 4. Gateway 與媒體

目標 endpoint：

```text
GET  /health/live                  程序存活
GET  /health/ready                 migration/broker/core readiness
GET  /v1/snapshot                  輕量狀態，需認證
POST /v1/conversations/{id}/turns  建立 turn，回 turn_id
POST /v1/turns/{id}/cancel         冪等取消
WS   /ws/control                  文字、狀態、取消、snapshot
WS   /ws/audio/input              麥克風 frames
WS   /ws/audio/output             播放 frames
```

預設 loopback；LAN 不可僅依「同網段」信任。瀏覽器 gateway 驗證 Origin、短效 session credential、目標 session；WebSocket 不把長效密鑰放 query string。remote 使用 TLS 或受驗證隧道。gateway 的 session 認證不等同 tool grant。

連線 hello 包含 protocol_version、client_id、capabilities、last_seen sequence。重連用 snapshot + 新 generation；不回放已取消音訊。Snapshot 包含 identity 公開摘要、有效 turn 狀態、body intent、service health，不能包含私密記憶全文。

音訊 stream metadata：stream_id、session_id、turn_id、generation_id、speech_id、codec、sample_rate、channels、frame_samples。初版 PCM s16le mono，20 ms frame；sample_rate 協商 16000/24000/48000，其一；每個 binary frame 固定 header 表示 stream token、sequence、sample offset，再接 PCM。確切 byte order、header 長度在 T13 寫入 schema 並做跨語言 golden tests，不可由兩端自行猜測。

input ring buffer 初值 2 秒、output 預取 500 ms；realtime 切到取消時先停 playback owner，再清該 generation buffers。應用每個 session 只有一個聲音輸出擁有者：若 AIRI 播放，audio service 不再本機播放；renderer mouth 隨實際 playback 時鐘，不隨 TTS 產生時鐘。

## 5. Conversation 狀態機

```text
idle → listening → transcribing → planning → responding → completed
                         └──────────────→ failed
任何未終止狀態 → cancelling → cancelled
```

文字輸入略過 listening/transcribing。同 session 最多一個前景 turn；新輸入在既有 responding 時先取消舊 turn，再啟動新 generation。completion/cancel 競爭以 Core transaction 先提交者決定 terminal state，取消後任何旧 chunk 都不得進播放器。保留 cancelled turn tombstone 至所有 producer 結束且過遲到窗口。

`cancel()` 是 request；`audio.playback_stopped` 才是停止確認。取消已開始的外部不可逆動作只代表停止後續步驟，不宣稱已撤銷；action 可回 `completed_after_cancel` 並呈現實際結果。

Provider port 最少有 `stream(request, cancellation) → AsyncIterator[ModelChunk]`、`capabilities()`、`health()`。chunk 分 text/tool_request/usage/finished；provider 不能直接執行 tool。fallback 使用同 identity snapshot，但新的 generation。未向使用者輸出前可重試一次；已輸出後不能混接另一模型的剩句，先終止並明示新的回答。

初值：connect 5 秒、首 chunk 15 秒、整個 turn 120 秒；均可設定。工具有獨立 deadline，與 turn 取較短者。mock provider 能注入 timeout、非法 JSON、斷流、取消無效和超長輸出。

## 6. 持久化 Schema 最低要求

所有表有 schema migration；時間 UTC；JSON 欄位需要 application schema 驗證。SQLite foreign_keys 開啟。WAL DB 放本機檔案系統，其他節點經 service API 存取，不把 WAL 放共享網路磁碟。索引不是唯一來源。

| 表 | 核心欄位／約束 |
|---|---|
| identities | identity_id PK, core_json, core_version, created_at |
| identity_revisions | identity_id FK, revision, patch_json, source_ids, created_at；複合 UNIQUE |
| relationships | identity_id, person_id, revision, state_json, source_ids |
| events | event_id PK, type, envelope_json, received_at；type/time/trace 索引 |
| outbox | event_id UNIQUE FK, subject, payload, state, retry_at, attempts |
| inbox | consumer_id, event_id, processed_at；複合 PK |
| conversations | session_id PK, identity_id FK, created_at, status |
| turns | turn_id PK, session_id FK, generation_id, state, revision, ended_at |
| world_observations | observation_id PK, entity_id, property, value_json, confidence, observed_at, expires_at, source_id |
| world_current | entity_id, property, observation_id FK, revision；複合 PK |
| memories | memory_id PK, identity_id, kind, text, status, confidence, valid_from, valid_to, revision, deleted_at |
| memory_sources | memory_id FK, source_event_id FK；複合 PK |
| memory_derivations | parent_memory_id, child_memory_id, revision；防 cycle |
| semantic_facts | memory_id FK, subject, predicate, object_json, verification；非唯一以保留衝突 |
| consolidation_runs | run_id PK, source_cursor_start/end, status, checkpoint, model_ref |
| goals | goal_id PK, state, next_step, deadline, budget_json, revision |
| actions | action_id PK, idempotency_key UNIQUE, state, skill_id, args_hash, grant_id, deadline |
| action_attempts | attempt_id PK, action_id FK, executor_id, lease_epoch, state, outcome_json |
| grants | grant_id PK, actor, capability, scope_json, args_hash, expires_at, uses_remaining, revoked_at |
| audit | audit_id PK, action_id, decision, reason_code, policy_version, timestamp |
| skills | skill_id, version, manifest_hash, state, path_ref；複合 PK |
| devices | device_id PK, adapter_id, descriptor_json, availability, last_seen |
| entity_edges | from_id, relation, to_id；複合 UNIQUE |
| compute_nodes | node_id PK, capabilities_json, version, last_seen, trust_scope |
| compute_jobs | job_id PK, state, privacy, deadline, input_ref, selected_node |
| compute_attempts | attempt_id PK, job_id FK, lease_epoch, state, output_ref |

查詢按 identity/person scope 過濾後才檢索。FTS/vectors 不跨 identity 洩漏。Memory deletion transaction 標記並移除 FTS/vector、撤銷依賴摘要；重新 consolidation 必須跳過被刪來源。event retention 与 memory provenance 分離：刪除原文後可保留不含內容的來源 tombstone 以維持可稽核關係。

備份採 SQLite 支援的 backup 流程或一致性停寫快照，不能運行中只拷貝 `.db` 而忽略 WAL。還原在新資料目錄演練，先 integrity check，再用實際版本 migration；失敗不能覆蓋原資料。

## 7. Skill Manifest 與 Runtime

```yaml
id: computer.file.read
version: 1.0.0
contract_version: 1
description: Read a scoped UTF-8 text file
entrypoint: builtin:file_read
input_schema: schemas/skills/file_read.input.json
output_schema: schemas/skills/file_read.output.json
permissions:
  - capability: filesystem.read
    scope_required: path_roots
risk: observe
timeout_ms: 3000
concurrency: 2
resource_limits:
  memory_mb: 128
  output_bytes: 1048576
network: denied
idempotency: read_only
cancellation: cooperative
compensation: none
```

Runtime request：action_id、attempt_id、skill_version、arguments、args_hash、idempotency_key、grant_token、deadline、trace_id。Runtime 自行驗簽／驗 scope，不能相信 Core 傳入 `allowed=true`。確認對話只能對應該 action 的 arguments hash；修改參數要重新判定。

Action 狀態：proposed → authorized／denied／waiting_permission → queued → running → succeeded／failed／cancelled／unknown／completed_after_cancel。unknown 不自動變 failed，以免重試造成第二次副作用。

錯誤碼最少：VALIDATION、UNAUTHORIZED、UNSUPPORTED、BUSY、TIMEOUT、CANCELLED、UNAVAILABLE、CONFLICT、UNKNOWN_OUTCOME、INTERNAL。回傳 retryable 與 reason，不單純 throw 字串。

檔案操作正規化路徑、symlink、scope、輸出大小，寫入使用暫存檔 atomic replace。shell 用 argv 與 cwd allowlist，不拼接模型字串成 shell；如明確提供 shell 語言能力，獨立高權限 capability。程序使用 process group/job object 取消子程序，stdout/stderr 有上限。UI driver 對 window/screen 版本檢查，畫面改變就重新觀察，不盲點舊座標。

本機 IPC 的 OS 權限不能等同完整 sandbox。無法落實的 network／filesystem 限制必須宣告 unsupported 並拒绝需要該隔離的第三方 skill，不能只寫 manifest 就聲稱安全隔離。

## 8. Device Descriptor

```json
{
  "device_id": "bedroom-light-01",
  "adapter": "home_assistant",
  "location": "bedroom",
  "properties": {"power": {"type": "boolean", "readable": true}},
  "actions": {"light.set": {"input_schema": "light_set.v1"}},
  "events": ["device.state_changed.v1"],
  "availability_ttl_ms": 30000,
  "privacy": "trusted_lan"
}
```

借鑑 WoT properties/actions/events，但此內部 descriptor 不宣稱完整 W3C TD 相容。MQTT topic 基線 `siro/devices/{id}/{state|availability|command|ack}`；command 含 command_id、desired_state、expires_at。命令不設 retained；重新連線不得因舊 retained command 動作。ack 只是收件或執行狀態，成功還需要 state readback。初值設備動作 deadline 3 秒；超時為 unknown 或 offline，不能產生假的確定狀態。

## 9. Compute 契約

Node advertisement：node_id、protocol_version、capabilities、models（id/revision/quantization/context）、hardware、available_resources、queue_depth、allowed_privacy、heartbeat_at。僅信任預先配對節點；不自動接受未知 LAN 廣播的算力。

Job：job_id、attempt_id、lease_epoch、required_capability、model_constraints、privacy、input_ref/inline_small_input、deadline、budget、cancel_token。初值 heartbeat 5 秒，15 秒未見為 unhealthy，30 秒 lease 過期。retry 新 attempt，舊 epoch 結果只存診斷，不可提交為目前結果。

stream chunk 包括 job/attempt/epoch/index；節點換手不拼接不同 generation 的 token。推論取消是 best effort，但 Core 必須確實丟棄遲到結果。Compute API 不提供任意 shell；需要控制電腦走 Runtime，兩種權限不可混用。

## 10. 相容性與版本管理

T02 建立 golden fixtures：Python、TS、Rust 都讀同一份合法/非法 JSON。T13 補 binary audio fixture。變更 schema 時先列 producer/consumer、migrations、replay、舊版客户端影響。版本協商不支持時顯示 incompatibility，不能默默失去取消或權限欄位。

## RT-002 optional native model messages（2026-10-01）

ModelRequest.prompt positional callers 保持相容；messages 有值時 adapters 送 native role/content/tool_calls/tool_call_id。ConversationEngine 可接 optional messages；CompanionCore 的 optional message_history 僅供同一 run 接續，首次建立 context/system 與原始 user，之後只追加 assistant 與 tool observation。工具內容是資料，不當作新的使用者 utterance。IntegratedCompanion 預設 legacy；candidate history 在 run 建立後固定，terminal 清除；history 缺失明報，不假稱可重啟恢復。批次 dispatch/恢復不屬 RT-002。

## RT-003 candidate batch（2026-10-01）

批次建立後呼叫 ID 固定；每個terminal proposal只收一次結果。全部收齊才按原順序追加 tool messages並接續一次。拒絕回傳error=denied，不dispatch。重複call ID或超限batch在任何新dispatch前終止run；candidate同session提案ID限制沿用既有DB唯一約束。取消可封鎖排隊/後續工具與晚到UI輸出，已在執行的OS process清理仍屬RT-005。legacy預設保留。

## RT-004 candidate computer output（2026-10-01）

computer.execute既有argv/cwd/timeout/detach驗證不變。candidate facade並行讀stdout/stderr，合計最多保留65536 raw bytes，超出繼續排空且truncated=true；結果欄位不變。未超限輸出與legacy相同，超限雙管道保留份額依讀取順序。timeout清理直接child並重啟drain避免pipe堵塞，cleanup最多5秒；process tree/run cancel仍RT-005。legacy default binding保留。


## RT-004 profile freeze 修正（2026-10-01）

Gateway main啟動時擷取一次SIRO_RUNTIME_PROFILE，controller與computer.execute共用同一值；server內後續env變動不得切換executor。切換profile須排空現有工作後重啟，僅新run使用新profile；legacy仍預設。


## RT-005 candidate cancellation（2026-10-01）

ToolOrchestrator新增optional contextual executor註冊，舊execute(proposal_id)與arguments-only handlers不變；run/proposal context僅RAM，不改持久格式。context傳run/session/proposal/call/epoch、shared token、authorization metadata，computer.execute由既有timeout生成monotonic deadline。

candidate取消先封鎖新dispatch，再停止owned foreground group並等待有界cleanup後送唯一terminal；TERM→250ms→KILL→drain/wait。direct child reap，group後代停止；不能跨PGID/name掃描。cleanup錯誤用既有failed/error=ExecutionCleanupError明報，不能回報成功或自動重送。HTTP approval在取消後不發late tool_result；turn_id只映射已知session，unknown ID不影響其他run。explicit active alias仍為全active取消。

ack後detach沿用原started/pid/argv且不受run取消；ack前取消清理。沒有session teardown/escaped process session管理；不把run/group清理等同Qwen、browser或所有使用者程序清理。


### RT-006 candidate Qwen private lifecycle

candidate私有JSONL請求/回覆配對request_id及epoch；不改public render bytes、HTTP、reference WAV。啟動、render timeout/cancel/protocol failure必先回收worker再重建，單owner及最多8個render active/waiting；滿額明報RuntimeError，仍可文字對話。Gateway shutdown close candidate；legacy worker不要求新欄位。


### RT-007 candidate catalog and effective configuration (2026-10-02)

Optional ToolCatalog wraps existing tool descriptors without changing old executor signatures or persistent/protocol formats. Candidate takes a fresh model schema snapshot per round, validates current arguments/readiness at proposal and dispatch, including scheduled contextual invocation. Hidden process.start remains compatible; legacy retains static model schemas.

Authenticated GET /v1/runtime is additive: captured runtime_profile, configuration_source, catalog_enabled, json_settings_applied=false, current authorization_mode, whitelisted kill_switches/routes and redacted tools metadata. Never serialize environment/provider keys. Gateway main keeps env precedence and startup profile capture; JSON SiroSettings remains unapplied. Browser readiness only reflects existing Chrome/Chromium discovery, not successful navigation. Existing tools-off policy is enforced by candidate catalog; legacy behavior remains unchanged.


### RT-008 candidate journal and readback (2026-10-03)

Migration 013 is additive; old agent enums and HTTP/WS fields stay unchanged. A candidate run persists runtime version/profile/backend/privacy/epoch and separate model-round/tool-call counts. Durable batch precedes execution intent, which precedes handler effects; durable observations precede model continuation. Recovery never dispatches or calls a provider: it fences pending approvals, pairs persisted results and explicit unknown/not_dispatched observations, marks interrupted old runs FAILED, and exposes them via authenticated GET /v1/agent-runs/{session_id}. Old legacy rows are marked legacy_unrestorable in readback, never parsed as canonical messages. Current budget and immutable goal remain available after reopening. Unknown actions require external readback/owner confirmation; this card supplies local journal readback only, not automatic reconciliation of OS effects. Candidate startup invokes this before accepting traffic. Legacy startup does not reconcile candidate runs; old pending candidate approvals are blocked at execution by persistent ownership guard. New run may start normally, but recovered run cannot silently resume.

RT-008 implementation detail: CompanionCore.respond adds optional on_messages_ready async callback after canonical context assembly and before ConversationEngine invocation; callback absence preserves legacy callers. Candidate AgentRun/journal metadata inserts share one transaction; epoch uses existing ExecutionContext run_id epoch. Journal backend names selected model route, while executor remains the already frozen startup profile binding; no new execution backend is added.

### FIX-001 generation acceptance (2026-10-04)

Only COMPLETED generation tool calls may become proposals or canonical accepted batches, in both legacy and candidate initial/continuation paths. FAILED/CANCELLED terminates without another model round and retains the original error/state/partial text. TurnResult retains raw partial intent; optional final-step rejected_tool_calls preserves it for diagnosis, never replay. Canonical candidate history includes partial assistant text without rejected calls; earlier accepted calls/observations remain paired. Legacy persisted cancellation uses the existing CANCELLED enum. Public tool IDs, approval, authorization and successful loop behavior are unchanged.

### RT-003-FIX-01 candidate ownership (2026-10-04)

Candidate dedup lifetime is one run. Different runs may reuse provider call IDs, including after restart. Private proposal storage identity does not change public ToolProposal.call_id or model tool pairing; original ID is persisted in exact run_journal_calls.proposal_id binding, atomic with proposal insertion. Legacy call_id rows remain unchanged. Old callbacks cannot match a newer batch merely by session/call ID. Historical unbound crash-gap rows must have one unambiguous matching owner or execution fails closed. Recovered candidate approvals never execute in legacy/current runtime without matching live owner/hook. Rollback keeps identity reader and replay guard when mapped rows exist; no DB downgrade/delete.

### RT-005-FIX-01 arguments-only cancellation (2026-10-04)

Candidate foreground invocations, including arguments-only executor(arguments), are owned tasks. Cancel fences dispatch, cancels arguments-only tasks once (contextual executors retain cooperative token), waits bounded cleanup before terminal. Noncooperative/refused cleanup reports existing FAILED/ExecutionCleanupError within 5s with uncertain dispatched journal outcome; late completion cannot produce UI or restart dispatch. Browser startup/exit cleanup closes acquired resources even on failure; candidate application spawn retains only owned group until acknowledgment. Acknowledged app lifetime remains user-managed. Legacy signatures/profile/authorization/schema and existing argv cap/PGID/ack semantics unchanged. This does not claim control of escaped daemon/external effects.


### RT-009 provider attempt policy (2026-10-05)

FailoverModel preserves LanguageModel.stream request/iterator shape and caps total attempts at two. A single configured local backend may retry once; supplied second backend is fallback, not an additional retry tier. Only connection/transport/timeout or HTTP429/502/503/504 is retryable, before nonempty text, any tool_request or finished. OpenAI buffered partial-tool stream failure is marked nonretryable using an exception note; original error type is preserved. Cancellation interrupts backoff and prevents all later dispatch. Retry request preserves messages/privacy/output budget and changes only private generation ID. Additional cloud attempts require both cloud_allowed and explicit request budget; default zero. Main candidate wraps only the existing selected provider; no cloud egress route is added and legacy/env priority remain unchanged. SIRO_MODEL_RETRY_ENABLED=0 disables candidate retry wrapper at startup. Request budget is not a monetary/daily cost limit; main forbids extra cloud attempts while cost budget integration remains unconfigured.

## RT-010 candidate recent session context

Candidate new runs hydrate at most12 native recent dialogue messages from same-session, same-privacy completed version1 journal rows. Each row contributes its final raw user (equal to its immutable goal) and final assistant text, preserving complete turn pairs; no old system prompt, tool intent or unknown action is hydrated/replayed. Current system context is rebuilt and current user is appended once. Legacy messages remain unread as canonical and readback retains legacy_unrestorable. Partial/cancelled/interrupted history remains available through RT-008 readback. Feature-off SIRO_SESSION_RESTORE_ENABLED=0 affects only new startup, retains data, and uses previous working-memory path. Corrupt version1 dialogue raises an explicit error. This bounded recent dialogue feature does not imply token-budget or long-term fact ingestion.

## RT-011 logical request size guard (budget slice)

Candidate applies startup SIRO_CONTEXT_MAX_BYTES (default65536 UTF-8 bytes;0 disables) to compact JSON of the complete logical ModelRequest before invoking the selected provider/retry policy. Over-limit means failed/error=ContextBudgetExceeded, no provider call, no trimming of system/user/pending tool messages, no summary or long-term-memory change. Under-limit requests pass unchanged; name/privacy/cancellation remain unchanged. This is an exact logical request byte ceiling, not verified provider tokenizer/context-window or exact HTTP payload accounting; provider-token acceptance remains unverified. Summary is deferred.


## RT-011 native budget completion (D28)

The preceding byte-only PARTIAL description is historical. Candidate defaults SIRO_CONTEXT_TOKEN_BUDGET_ENABLED=1 independently of the byte cap. Verified Groq openai/gpt-oss-20b uses pinned official tokenizer/template over the actual adapter request payload; reference input tokens + requested output +256 must fit SIRO_CONTEXT_WINDOW_TOKENS (default131072, may only reduce). This reference policy does not claim exact Groq internal framing. Missing/tampered assets, unknown native profiles and unsupported template shapes raise ContextBudgetUnavailable before provider/fallback calls; over-limit raises ContextBudgetExceeded. No truncation, summary or fact writes. Counting is off the event loop with cancellation checked before dispatch. Offline retains byte cap, legacy is unchanged. Native0 disables only token policy; byte0 disables only byte policy. Explicit public-asset provisioning and completion evidence: docs/evidence/RT-011/token-completion/REPORT.md. Summary remains DEFER.

## RT-012 browser session contract (D29)

Candidate browser.navigate+read preserves its name/url arguments and returns url/title/text/screen_version; when session feature is enabled it requires trusted ExecutionContext ownership. Additional browser.read, browser.fill, browser.click and browser.close are catalog descriptors. Fill requires role/name/screen_version/value; click requires role/name/screen_version. Successful actions return fresh readback; stale/cross-session/recreated-driver versions are rejected before effect. Same-origin state lasts across completed runs, never across different sessions. Origin change resets driver state; no credentials saved. IdleTTL300s, max8 sessions, action timeout30s. Cancellation/error/explicit close/shutdown clean owned browser resources; disconnected clients expire through idleTTL, not ambiguous shared WS identity. Legacy and startup feature0 remain stateless. Pool cleanup failures are explicit ExecutionCleanupError, not success. Restart loses browser state and does not replay actions.

## RT-014 explicit owner memory ingress (D30)

Candidate enabled SIRO_MEMORY_INGRESS_ENABLED=1 commits only explicit leading 記住：/請記住：/幫我記住： (ASCII colon also accepted) or remember:/please remember: statements from the server-created, recorded siro.presentation UserTextEvent. Original content/session/event provenance is retained; person is fixed owner and identity is the existing siro identity. This is an episodic owner statement, not an inferred semantic/personality fact. No arbitrary prose, quoted instructions, model output or tool observations are ingested. Same event ID maps to the same UUID5 memory. Durable commit confirmation is supplied in existing verified runtime context to the model, with memory ID and local-storage limitation; failure finishes candidate FAILED before generation. Existing authenticated memory browse/recall/correct/delete/revisions endpoints remain mutation/readback paths.

Candidate recall applies the selected route: cloud requires every memory source to explicitly allow cloud; unknown/missing/local-only sources are excluded. Original user ingress events remain local_only, so remembered statements remain readable locally and in the owner's memory API but are not silently disclosed to cloud. Legacy and API recall default behavior are unchanged. Optional keyword filtering is additive; no schema or event-format change. Feature0 stops future ingress on drained startup, does not erase memories/revisions or remove safe candidate privacy filtering. Deletion invalidates active memory recall; conversation history retention remains unchanged and is not a promise to purge raw historical user messages.

## 2026-10-06 native completed-batch counting (D31)

The counting adapter accepts completed multi-call batches only when all calls have unique IDs and immediately following tool results form an exact pairing. It counts a private one-call/result reference view plus a serialized-batch token reserve. Wire payload, journal and executor order remain unchanged. Incomplete/malformed batches fail closed; exceed does not replay already executed tools. This is the configured local reference-token policy, not an exact bound on remote Groq framing. Single-call behavior and existing byte/output limits are unchanged. Public tokenizer assets are prepared by scripts/check, never downloaded at runtime.

## Runtime product slices — 2026-10-06 (D31)

Candidate exposes filesystem.read/list backed by an owned unprivileged Rust runtime with a dedicated configured root and signed, argument-bound, single-use grants. Model reads retain proposal/journal authorization. Authenticated explicit owner POST /v1/workspace/{read|list}?path=... uses the same service and tools kill switch, without model involvement. No write endpoint or implicit weaker-backend fallback. UTF-8 file reads are capped at 8 KiB; separate computer.execute permissions are unchanged.

GET/POST /v1/memory-organization exposes a bounded local derived view, enabled/refresh controls and source revisions. Single owner, coalesced trigger, foreground preemption, at most 100 source memories, 5-second batch. It never commits new facts, changes identity, sends notifications or calls cloud. Correction/deletion invalidates displayed derived results; restarting rebuilds disposable state. UI toggle is process-scoped; startup flag is the persistent deployment choice.

SIRO_CONTEXT_SUMMARY_ENABLED selects extractive, source-hashed summaries of completed old responses with explicit omission markers. User/system/pending/latest observations remain intact; final request still passes byte/native guard. Summary restore is bounded to 24 same-session/privacy completed pairs and is invalidated conservatively by memory revisions/deletion. Original journal remains canonical; no summary schema or semantic-fact write. Turning the flag off preserves the prior six-pair raw restore path.

## FIX-003 provider output completion (2026-10-07, D33)

OpenAI-compatible length terminates as FAILED/ProviderOutputTruncated; content_filter as FAILED/ProviderOutputFiltered; unsupported reason or SSE EOF without a successful reason/[DONE] as FAILED/ProviderOutputIncomplete. These ValueError subclasses are nonretryable; no partial tool call is yielded before successful termination. Partial visible text survives in the existing failed result and journal, with exactly one terminal. Cancellation remains CANCELLED. A valid stop/tool_calls reason permits EOF; reason-less [DONE] and complete non-stream JSON with omitted/null reason retain legacy compatibility. Empty/usage-only output still fails. Later markers cannot override a rejected reason. Other adapters and all output/context budgets retain their contracts. UI must show failure even after nonempty partial text; it must not speak that partial as completed output.

## FIX-004 session lifetime (2026-10-07, D34)

Session bootstrap remains POST /v1/session → token/expires_in_seconds, loopback + allowed Origin only; TTL300 remains default. At most128 unexpired tokens; full capacity returns429 without evicting live tokens. UI uses one on-demand single-flight renewal, with a5s bootstrap timeout and3s failure cooldown. Only relative /v1/ calls receive Bearer; redirects fail. Only401 with exact gateway detail `session token is invalid or expired` is retried once after renewal because every affected handler checks this before accepting effects. Other errors and ambiguous disconnects are never resubmitted. Cancellation while awaiting shared renewal cannot dispatch cancelled work. HTTP renewal does not replace healthy sockets; control reconnect waits for authenticated snapshot, fences prior sockets and only restores status. No effect/speech replay.

## FIX-005 A/B 有界朗讀（2026-10-07，D35；實作中）

既有 POST /v1/audio/speech 與 bytes caller保留。新增同Origin／Bearer的 POST /v1/audio/speech/plan，body只含canonical `text`（最多16,000字），不執行推論；重用prepare_spoken_text及speech_segments，回傳 `segments`、`spoken_text`、`version`、`max_chars`、`max_segments`、`max_total_chars`、`deadline_seconds`。初始有界設定為每段80字、最多128段／8,000可朗讀字／1,200秒；這是資源限制，非速度成果，待真硬體量測。超額413，不截尾假成功；空朗讀422。程式區塊沿用明示「程式碼內容先不念」的朗讀規則，canonical fenced文字先處理，不能從格式化DOM失去code語義。

UI沿用唯一音訊generation／AbortController，final後先取得plan、逐段依序播放，最多一段預取；完成等待每段實際ended，晚回應／取消／新turn／重連不能復活。顯示已播段數、停止／失敗／上限，只有末段ended才顯示全文朗讀完成；畫面全文保留並有重新朗讀入口。不存在已提交句子契約的C不實作，不宣稱逐音塊串流。

Qwen worker ready可宣告 `completion_protocol: 2`。此worker成功audio須帶 `completion`：`status: complete`、`eos_observed: true`、`cap_reached: false`、`generated_tokens`正整數且小於`max_new_tokens`、`observer_calls: 1`；缺失／未知／無EOS／觸頂回固定error且無audio。EOS與cap同時成立仍保守未完成。舊未宣告protocol的injected worker維持相容，新protocol不得降級略過metadata。單owned worker局部觀察該talker instance原generate結果後原樣交回SDK，finally還原；不改site-packages或生成演算法。只驗EOS不等於已證全文念對，真聲音首尾仍必驗。

新版cache獨立namespace，綁實際模型／reference聲線／library與生成設定／分段版本；必須有效完整性metadata與audio hash才命中，原子提交、未知不得成功快取、不退讀舊純文字hash WAV。保留舊cache、聲線、request_id／epoch、single-worker cancel／reap／bounded pending及Core／DB／grants。

D35 2026-10-08局部profile補充：CUDA使用已量測SDPA，CPU維持eager，cache fingerprint綁同一實際attention選擇；不互讀eager／sdpa快取。相同model／reference／sampling／512上限保留。這是推論時間改善，非聲線切換或1秒SLO達成；正常EOS與native播放仍不代替人工語意聽驗。


### RI-002 — Read-only capability inventory (2026-10-09)

Candidate ToolCatalog.capture produces detached definitions and inventory from one readiness sample per descriptor. Existing name/available/backend/effect/model_visible keys and ToolDefinition input schemas remain compatible. Additive fields: availability (available/unavailable/unknown), reason_code (closed safe codes), checked_at, display_name, description, input_schema, output_contract, required_permissions, risk_level, version, provenance, timeout_seconds and failure_behavior. Undeclared metadata is null; unknown/check_failed omits the executable model definition. checked_at is snapshot time, not continuous health or navigation success. Browser executable discovery and workspace process readiness retain their existing limited meaning. timeout_seconds is the declared maximum operation timeout, not a default or promise; computer.execute retains its 30s default, configurable maximum120s and shorter run deadlines. Cleanup has separate bounded deadlines. Undeclared timeouts and output contracts remain null.

Authenticated GET /v1/runtime exposes this inventory through existing tools. Discovery only reads trusted bounded readiness predicates; it never invokes executors, subprocess/version commands, plugin imports, API/network or Rust actions. required_permissions describes requirements, never a current grant. Proposal and dispatch independently recheck readiness/schema/ownership/approval; stale inventory cannot authorize an effect. Exception messages, credentials and private workspace paths do not enter inventory.

Each candidate model round takes one capture; its definitions and SIRO-owned system capability block describe the same sample. on_messages_ready replaces only the owned block at the end of the first system message before the existing journal checkpoint. User/assistant/tool messages, call IDs, memory, permissions and public states remain untouched. Unknown/unavailable capabilities are described honestly, hidden compatibility handlers are excluded from model context. Legacy schema/prompt and positional constructors remain unchanged. UI displays readable labels/reasons and uses textContent, never trusted HTML from metadata.

### FIX-002 — Bounded browser reasons and partial page read (2026-10-10)

Browser scope failures retain public error=ScopeViolation and FAILED; optional existing observation JSON adds only fixed reason invalid_url/main_origin_denied/redirect_denied. Native paired tool messages, legacy prompt and run journal consume the same safe projection. Unknown/ordinary failures retain their previous error-only shape. No raw exception message, rejected URL, query, credentials or payload is copied into failure diagnostics. Existing DB, required tool parameters, approval/hash, profile/switch and cancellation contracts remain.

Explicit driver navigation admits HTTP/HTTPS with a valid host/port and no userinfo; catalog rejects malformed/Markdown inputs before proposal without normalization after approval. All requests and HTTP redirects retain the original authorized origin set. Main-frame rejection fails the action and is checked again on observation; it is never partial success. The rejected page is replaced before later use. Out-of-scope images/scripts/styles/iframes and their redirects are still blocked; when the authorized main page remains readable, optional string fields load_status=partial and reason=subresource_denied accompany the original url/title/text/screen_version. These markers are not proof of completeness, and a missing blocked resource may make the page unusable. No foreign content is fetched to improve readability.

Internal about/blob/data resource handling remains compatible; explicit main navigation does not accept them. Main navigation with unclassifiable frame fails conservatively. New BrowserObservation.blocked_resources defaults false after the four existing positional fields. Session and stateless wrappers preserve old four-key successful observations when no resource was blocked. New authorized navigate(B) retains session scope-reset semantics. The UI renders only fixed reason labels and partial wording using textContent; it never renders exception text as HTML or treats partial as complete research.

The driver retains route interception throughout owned teardown. Once closing starts, new intercepted requests are aborted; expected Playwright errors from already-running callbacks during that teardown are consumed, while live errors propagate. This does not widen origins, remove routes while an open page can issue requests, retry effects, extend the four-second session cleanup bound or hide cleanup failures. A late callback cannot report an observation/success. Public cleanup timeout remains a separate unverified cause; local teardown tests do not prove every public shutdown succeeds.

### FIX-008 — Complete paths in a bounded text-diff dialect (2026-10-10)

PatchVerifier validates the entire input before copying, applying or running trusted checks. Supported files have paired unquoted --- a/path / +++ b/path headers and counted text hunks; one side may be /dev/null for add/delete. Consistent diff --git and validated index/new-file/deleted-file metadata are optional. Content-bearing renames require consistent Git old/new paths and rename from/to metadata. changed_paths is the stable first-seen union of both sides, excluding /dev/null; either protected source/destination produces rejected_policy_change before effects.

Hunk body lines consume declared old/new counts, so literal --- or +++ text cannot introduce ghost paths. Paths must be canonical relative POSIX paths without absolute, dot/dot-dot, backslash, whitespace/control/quoted names or any .git component. The verifier never normalizes/re-writes the raw diff before apply. Conflicting headers, truncated/malformed hunks, unconsumed content, timestamp headers, binary/copy/mode-only/rename-only or unknown metadata fail closed as rejected_invalid_diff for the whole proposal; unsupported is never an empty successful patch. Existing plain unified modification/add/delete and supported content-bearing rename retain the original apply/check behavior. Public report/status/limits and protection set remain unchanged.

Temp-copy verification still runs only trusted synthetic checks in this card. It is not OS isolation for untrusted generated code, and this repair does not enable automatic checks or promotion without that separate gate.

The bounded dialect uses LF separators and a final LF, rejects CR/NUL and input exceeding the existing 500000-character limit. Standard no-newline-at-end-of-file hunk markers are supported; patch separators are distinct from the source file's final newline. These restrictions are explicit rather than accepting an unrecognized format as a partial/empty successful patch.

### FIX-009 — Versioned complete release signatures (2026-10-10, D39)

ReleaseManifest supports explicit signing_format="siro-release-manifest-v1". Missing/null marks a readable legacy artifact that ReleaseManager rejects; unknown format and unknown fields fail validation. No legacy HMAC fallback, automatic upgrade/re-sign, new signer service or deployment hook is introduced. Positive min_schema/max_schema are strict integers (no bool/string/float coercion), with min_schema<=max_schema. The staging entry revalidates the typed value, including unvalidated model_copy/construct input, before effects.

signing_payload() produces UTF-8 JSON bytes with sort_keys=True, compact comma/colon separators, ensure_ascii=True and no trailing newline. It serializes all declared manifest fields except signature, including the domain/version string signing_format, version, source_sha256 and both schema bounds. HMAC-SHA256 remains the algorithm; the actual bundle digest must also match. Legacy payload creation fails explicitly. Independent fixed byte/HMAC vectors and tamper fixtures must verify the contract.

Existing compatibility-first status and stage/activate/backup/rollback flows remain: incompatible_schema or invalid_manifest (or invalid wire parsing) must happen before backup, copy, healthcheck or pointer writes. Legacy schema rejection is not a successful fallback. Temporary CLI fixtures exercise the real model_validate_json caller. Maintenance re-sign requires explicit trusted validation of complete manifest/bundle; this card never upgrades live artifacts or enables promotion. Launcher consumption, OS isolation, human approval and latest-data-preserving rollback remain separate gates; the old whole-DB rollback test does not prove new-data retention.

### FIX-007 — Approved executable package identity (2026-10-10, D40)

SkillManifest v1 and the five InstalledSkill fields remain. manifest_hash uses siro-skill-package-v1:<sha256>; its deterministic, framed digest binds each included relative UTF-8 path, bytes and executable bits, including manifest/schemas/all modules/data/dependency metadata. Existing path_ref independently binds canonical approved root. Only normal __pycache__ directories are excluded and never delivered; known unsupported bytecode/native file extensions, symlinks/hardlinks/nonregular files, escaping schema paths, missing entrypoint source or oversized packages fail closed. Bounds:512 files,1024 entries,32 directory levels,4MiB/file,16MiB total. No-follow handles capture the actual bytes without following package aliases.

Registry install/enable validate actual full identity. Default disabled and explicit trusted owner enable remain; legacy manifest-only rows are preserved but cannot enable/dispatch until explicit verification/reapproval, never automatic migration. is_enabled(id,version) remains a status query; dispatch additionally supplies full identity and compares stored id/version/hash/root. Invalid or modified caller objects cannot substitute metadata/schema/hash.

Dispatcher captures off-loop and prepares a private owned snapshot from the same verified bytes. Changes during preparation reject; after frozen handoff, source changes cannot replace approved worker bytes. It rechecks enabled identity before calling the existing supervisor. Snapshot cleanup is guaranteed on preparation failure, cancellation and completion, including joined preparation threads. This is identity consistency within the existing worker path, not a general OS sandbox, authorizer or generated-skill activation pipeline. Existing network/env/resources/concurrency/cancel behavior and DB schema remain. Trusted host/runtime dependencies and hostile same-UID mutation are separate limitations; no auto-enable/deploy. Reverting requires dispatch disabled and preserves registry rows/private data.

D40 snapshot admission 補充：既有 Dispatcher 自己持有最多8個 active snapshot/preparation slots，包含排隊於 worker semaphore 的 job，完成清理後才釋放；候位取消不建立 snapshot。這是新增owned副本的局部資源上限（最多128MiB package bytes on disk），不是新scheduler/background owner，也不改原worker per-skill concurrency。總體CPU/RAM/IO SLO未量測。

D40 concurrency identity 補充：原 WorkerSupervisor semaphore 也以 id/version/package hash 作key，避免同id/version明確重新批准後仍沿用舊concurrency上限。固定未變 package的原行為保留；cache retention未量測，不在本卡另造state manager。

### FIX-006 — Bounded own-runtime status projection (2026-10-10, D41)

Within the existing single-owner store, recent_runtime_status(session_id, privacy) reads the latest same-session agent row before the new run starts. It selects fixed status columns and EXISTS(dispatched=1), never raw goal/messages/arguments/observations/steps/backend. Validation happens after selecting the latest row: candidate journal v1, terminal/interrupted AND failed/cancelled, exact current local_only/cloud_allowed privacy, canonical UUID, timezone-aware timestamp and age0..900seconds. Newer completed/active/legacy/private/invalid rows suppress older eligible failures. Wrong session, malformed identity/time, stale/future row or unknown privacy returns no fact.

The one optional JSON fact has exactly source_run_id,state,error_class,tool_dispatch_recorded,root_cause. Error names use a closed safe set; unknown/raw/null errors become UNKNOWN. Root cause always UNKNOWN: HTTPStatusError is not an HTTP code or diagnosis. A dispatch record is not proof of execution or success. Total serialized bytes stay below1024. Selection is read-only and does not authorize/replay/reconcile effects, write memories or create proposals. Existing candidate/session-restore startup gate controls this addition; direct commands/legacy/restore-off do not read/inject it.

Composition uses one short conditional own-failure instruction alongside that fact. Failed executable history stays excluded; completed pairs, summaries, provider-native pairing, budgets, privacy and grants remain. Speech/Live2D/microphone interfaces can be described as integrations; actual readiness/full playback/connection requires observations, never an unconditional promise. Mock wiring PASS and a single real-provider sample cannot certify overall intelligence, no-repeat semantics or complete speech.

D41 latest-row補充：獨立修後review及合成反例證實updated_at=''／'0000'會把較新無效行排到舊失敗之後；不能用尚未驗證的時間欄位選source。固定以既有agent_runs的rowid DESC選最後建立的recorded run，updated_at只供新鮮度驗證，不因舊run更新或格式排序復活舊故障。新增反例先FAIL；不改DB/index，也不弱化constraint。原unsupported version被DB CHECK拒絕，測試不造假插入；missing journal先在合成DB移除其call rows，保留production FK。

D41 bounded SQL補充：SQLite TEXT length遇NUL只計前綴；獨立review證實NUL-tail可把超長raw欄位載入Python（exact allowlist仍不外送，非已證實LLM leak）。SELECT長度守衛改以CAST AS BLOB的UTF-8 byte length，完整raw錯誤超64 bytes即NULL，不截前綴誤分類；UUID36 bytes／時間64 bytes同理。加入NUL-tail拒絕例，不更改原資料。

## D42 — FIX-010 unknown effects不能以新UUID取得auto批准（2026-10-10）

獨立合成反例已證實fullmode新call同cap/hash自動執行1次；現有old-proposal replay fence保留但不足。只在既有pending→approved交易中增加automatic guard，CURRENT pending/CAS先驗。對同owned store/session/capability的candidatev1 fenced journal、dispatch intent1與精確outcome_unknown：valid linked oldproposal的args hash相同，或binding無法驗證（null/orphan/cross-session/cap mismatch）則fixed PriorOutcomeUnknown，pending不變。LEFT JOIN ownership條件不能漏無FK的orphan。跨oldprivacy但零raw egress；不依old proposal/run state認定效果已知，不設TTL/historical cutoff、不把manual新批准當old resultresolved。

只有當前trusted ToolDescriptor.effect=read免額外重送hold（原full/manual/grants/schema/availability仍需原流程）；proposal.risk/名稱/argv猜測/模型/optionalmetadata不能免。resolve automatic=False維持manual相容，model auto路徑顯式True。controller先決定auto結果再發一次既有tool_proposal，fixed automatic_approval_blocked=prior_outcome_unknown；full UI顯示未知/可能重複並保留manual一次批准鈕，不假稱auto已批准。取消/fence先於progress輸出，batch一held一normal可繼續但run仍等人工。

只exact内容auto guard，不是semantic dedup framework/新state service/DB。依現行singlecontroller finish-before-new-run與既有dispatch cancel fence，不證明任意多writer post-approval競態。Page reload pending-card恢复已有gap另記，不拿reconnect卡保留當reload已完成。rollback先safe/manual、drain，逆精確source，保留所有ledger/DB/D41。

D42 missing receipt補充：fenced＋dispatched但observation SQL NULL或invalid JSON也屬無法确认的結果，固定manual hold；validJSON且非精確outcome_unknown維持原已知result語意。使用json_valid守衛避免malformedJSON讓批准檢查崩潰；不解析/外送rawobs。read exemption僅額外hold的分類，不取得新權限，仍由原catalog require/availability、fullmode/人為grant與driver執行邊界判斷。

D42 binding payload補充：獨立postreview另重現同owner/cap但指向不同args proposal的binding可逃hold。只看ID/session/cap不能稱validbinding，與原journal_owner的deep payload驗證不一致。修正前追加RED反例；在SQLite内對兩側最多65536 UTF-8 bytes、合法object JSON做json_tree(fullkey,type,atom)双向EXCEPT，保留nested/keyorder/Unicode等價而辨別array位置/typed值。超長/invalid/不同payload則linked無法驗證、同cap保守manual；CASE byte/JSON守衛不得讓badJSON先崩潰。沒有rawargs讀入Python或外送，不改表/limits/既有hash算法；currentargs仍用原arguments_hash授權。這修本卡候選的局部不一致，不推翻原RuntimeEvolution identity/replay設計，不另造semantic dedup。

D42 structural-location補充：修後正向例證實SQLite json_tree.fullkey保留原Unicode key escape，不能當canonical位置。改在SQLite內以每份tree的parent/key递迴构造JSON array path（decoded文字object key／整数array index），原id只作同document traversal。比較path/type/atom；integer/real另外保留document->fullkey取得的原number lexeme，避免超64bit integer轉float後碰撞。duplicate object keys不可當validbinding，需保守manual；不以字串取代escape或讀入Python。正常既有checkpoint/proposal json.dumps的numeric表示相同；不同numeric lexeme保守hold，不宣稱任意外來JSON numeric等價。先新增巨大integer與duplicatekey反例，再修source。

D42 numeric extraction補充：SQLite目前版本在包含literal double quote的object key上，document->fullkey可能NULL；不能把兩側NULL當numeric相同。numeric lexeme無法抽取的binding保守manual，保留pending／ledger，不自造JSON parser或降級atom值。新增wrongbound反例先RED；這類特殊key的number即使相同也可能需manual，明示保守限制。

## D43 — RI-003 明確owner的Linux single-process候選驗證（2026-10-10）

新增唯一services/tools/patch_verification.py verify_isolated_patch(project_root,proposal,profile="python-unittest-single",context=None) async入口與CLI `siro verify-patch PROPOSAL_JSON --project-root ROOT --profile python-unittest-single`。不接模型/自啟用/activation；不存在任意argv/profile/plugin/安裝依賴。只支援已驗Linux與system CPython標準函式庫single-process候選：固定compile projected .py＋stdlib unittest discover tests/test_*.py，必須至少一個test。CLI結果是未信任候選的本機review evidence，不是批准/部署。

Core只新增pure preflight_patch(proposal)->VerificationReport(status ready/rejected_invalid_diff/rejected_policy_change)，舊trusted PatchVerifier與新入口共享FIX-008 parser/protectedpaths。旧API仍只可信checks，不把copytree/cwd稱OS isolation；Core不import新driver。VerificationReport五欄及protected集合不改。

入場先preflight/profile/support；source只從canonical root下src/tests投影可見*.py，dot components/其他類型/private/config/DB/audio/Git/evidence/venv不讀不複製；改動只能落在支援的src/tests .py。No-follow directory/file handles捕捉normal single-link bytes，拒絕symlink/hardlink/special/changed-during-capture；最多512files／1024entries／32levels／4MiB perfile／16MiB total。來源整棵tree digest禁止；元資料僅證明捕捉時一致，不認證敵意同UID之後改host或自動promotion。捕捉非event-loop，取消時join準備再清owned temp，原工作區不寫。

可信git只在owned投影檔apply bounded canonical diff，潔淨固定env、拒policy/invalid/unsupportedpaths、unappliable。候選checks唯一owned execute_bounded_argv：wall10s／retained stdout+stderr64KiB、drain/PGID/repeatedcancel cleanup。bwrap獨立user/PID/net/IPC/UTS namespaces、disable userns、new session/die-with-parent、readonly projected candidate/必要system interpreter+stdlib/libs/固定trustedrunner；新proc/dev與8MiB scratch。原root/home/.env/private/DBus/host sockets不mount、環境不繼承。

trustedrunner放在候選外，system Python -I -S -B先載trusted標準庫、設no_new_privs及不可提升hard RLIMIT（AS256MiB、CPU5s、FSIZE1MiB、NOFILE64、CORE0），在第一次候選compile/import前安裝不可撤销seccomp：fork/vfork/clone/clone3、execve/execveat、socket/connect/其他escape syscalls拒絕；載入/resolve/filter失敗即unsupported且不跑候選、不host fallback。候選只能一個process；不把RLIMIT說成一般多程序aggregate limit，也不宣稱整套pytest/依賴/GPU profile可跑。trusted launcher固定overhead非已量aggregate SLO；完整multiprocess需delegatedcgroup另驗。

支援失敗應為固定unsupported_sandbox／unsupported_platform或rejected_profile，不吞成passed；所有effects owned temp/process，workspace_removed只有實際finally cleanup後才true。取消傳遞，不把cancel轉成功；unknown輸出不执行，不將candidate stdout當authority。固定runner/backend與profiles可回退停用；新CLI移除後保持原trusted入口/private data/registry/ledger，不退回host跑候選。

驗收先RED接口/caller與privacy projection，再真OS malicious import讀寫外部、socket/fork/exec、memory/CPU/file/output洪水、timeout/repeatedcancel/cleanup、policyrename/delete與unsupported failclosed；synthetic secrets/外部canary、無私人材料/8026/release操作。若個別限制不能實測就保持未驗gate，不增加抽象掩蓋。

D43 fixed support/status補充（實作前）：本卡只認證Linux x86_64、/usr/bin/python3.14及匹配stdlib/必要libs，未知OS/arch為unsupported_platform，缺runtime/git/bwrap/libseccomp或namespace/filter能力為unsupported_sandbox，未知profile rejected_profile，source/path/alias/limits拒絕rejected_source。wall10s到期failed_checks＋固定timeout，context cancellation/deadline保持既有exception傳遞。無test/輸出truncated不能passed。CLI verification passed exit0、已解析拒絕exit1、JSON/參數/input錯exit2；proposal JSON最多4MiB UTF-8、regular單link/no-follow檔，非法不印raw內容，Ctrl-C需cleanup後exit130。

明列bwrap --unshare-user搭--unshare-all/--disable-userns；seccomp bad-arch kill，額外拒絕setrlimit/prlimit64與escape syscalls，在hard limits設定後才load。-I忽略PYTHONPATH，trustedrunner安裝限制後才加/candidate/src及/candidate。socketpair/threads/IsolatedAsyncioTestCase/pytest/多程序不是支援profile；候選可偽造自己的test結果，passed不可作批准權。只把有量測的singleprocess界線當成果。

D43 writable/kernel-object補充：除8MiB /tmp外，sandbox root/proc/dev皆remount readonly，避免另寫top-level tmpfs；seccomp另拒絕memfd_create、SysV shm建立、perf_event_open與keyring syscalls，避免未納scratch/AS界線的kernel物件或繼承keyring入口。測試只試benign synthetic syscall／無效keyctl command，不讀任何hostkeys。git apply後對owned candidate再做同一source bounds驗證，patch不能把起始capture上限放大；該offloop驗證取消同樣join後才移除workspace。先追加RED實證再修source。

D43 cancel/session補充（真CLI反例後）：首個SIGINT在bwrap啟動時造成owned group cleanup超4.5s，不能宣稱取消PASS。原execute_bounded_argv已start_new_session=True；bwrap額外--new-session把namespace runner移到另一group，早期parent-death註冊前有逃ownedgroup風險。改只由既有owner建立session，移除重複bwrap setsid；stdin DEVNULL／輸出pipe／無hosttty mounts且保持PID/userns、die-with-parent及seccomp，仍無host controlling terminal。不能改cleanup期限或吞exception；須重跑actualCLI SIGINT、repeatedcancel及子PID消失，不成立則保留本卡gate。

D43 session隔離修後補充：兩個actual取消cases已PASS（0.90s），保持owner單次setsid。seccomp還需拒candidate自己的setsid/setpgid，不能在restriction後主動逃離owner group。驗hosttty不可開啟只用O_NONBLOCK立即close，絕不讀輸入；候選session改動先負向重現，再加deny。原processowner/cleanup時限不變。

D43 late-cancel補充：兩個新反例已證實checks成功但正在disk cleanup時，task取消可被join吞掉、context取消亦未末端檢查，使caller收到passed。修正常finally shield cleanup；若caller cancel，join完成後重新raise；cleanup後再檢查原context，token/deadline取消不得轉成功。保留準備cancel的join及typed cleanupfailure，不延長時限／跳清理。先2RED再修source。

D43 CLI repeatedSIGINT補充：完整子PID驗收重現第二次SIGINT後CLI exit130但尚有owned PID，不能把一次PASS當全部取消通過。Python Runner第二次SIGINT立即KeyboardInterrupt，loop shutdown直接cancel cleanup task可能截斷原PGID TERM/KILL流程。只在verify-patch command暫存並恢復SIGINT handler，所有SIGINT排為同一owned async task取消；不讓第二次signal直接退出cleanup，不改shared executor/4.5s grace。第一個signal早於task建立時記本地flag並在入口raise，正常完成後恢復原handler。須重跑real單/雙SIGINT完整PIDtree與所有cancel cases，不新增daemon/全域owner/重試。

D43 IPC資源補充（review後、修碼前）：private IPC namespace只能隔離名稱，不會將SysV semaphore/message queues或POSIX queue的kernel allocation計入AS／scratch上限。先用每類一個最小合成物件驗semget/msgget/mq_open；若成功立即IPC_RMID／unlink，不做壓力分配。確認可建立即局部漏口，將這三個creation syscall納不可撤銷deny，不擴multiprocess profile或宣稱aggregate cgroup gate已完成。

D43 CLI結束signal補充：verify task已完成而asyncio.run仍在關loop時，SIGINT handler只記interrupted，原入口檢查不再執行。用受控完成task／loop關閉時signal fixture先驗不得打印passed或exit0；同一command在恢復handler後、輸出前重查interrupted，收到中止就exit130。此為status局部修復，不改process owner／cleanup。

## D44 — RI-004 owner candidate contract（2026-10-10）

`SkillCandidatePreparer(catalog).prepare(capability)` fixed profile `markdown-checklist-v1`, exact capability `text.checklist.parse`, aliases `siro.text.checklist`／`skill.siro.text.checklist`。All registered inventory rows (including unavailable/unknown/hidden) participate. Match returns `existing_available|existing_unavailable|existing_unknown`, no generation/verification. Unknown template returns `unsupported_capability`. Search is exact typed-name matching, not semantic proof. Show `computer.execute` as a general existing alternative when present; no executor invocation.

Generated fixed v1 package has exactly manifest.json/input.json/output.json/plugin.py, no requested code/schema/deps/paths. Empty permissions, observe/network denied/read_only/concurrency1/process cancellation. Input only text: UTF-8≤16384 bytes,≤256lines;≤128 task rows,≤256characters/task. Support nonempty `-/*/+ [ ]/[x]/[X]` items, ignore ordinary lines and triple-backtick/tilde-fenced sections; not full Markdown. Return pending/completed string arrays plus integer counts. Static capture uses existing complete package digest and exact schemas; no host import.

Disposable source projection starts with fixed trusted tests. Proposal adds only src/plugin.py using captured bytes; RI-003 `verify_isolated_patch` runs fixed stdlib single-process profile. Review binds actual proposal UUID/changed paths/cleanup, full package/source/tests/proposal digests, source provenance, catalogue sample time, and four file contents. Provenance/report live outside package. Failed/unsupported/truncated/binding mismatch cannot await review as passed; raw candidate results never authorize execution. `awaiting_review`, `trust_level=unreviewed`, `enabled=false`, `installed=false`, `authorizes_execution=false`, `approval_required=true` remain fixed even after test PASS.

One active owned preparation per service, no queued/background work or persisted candidates. Preparation/cleanup IO offloop with repeated-cancel join; cleanup failure remains ExecutionCleanupError; late cancellation cannot return successful report. `cancel()` and `close()` affect only this job. No registry install/set_enabled/dispatcher/model calls. Repeated explicit preparations do not replace installed skill rows. Installed registry is not claimed searched; this slice checks registered typed catalog only.

`create_app(skill_candidates=None)` keeps legacy unchanged. Candidate composition injects current catalog. Authenticated same-origin owner `POST /v1/skills/candidates` body only bounded capability; cancel endpoint affects single active job. Missing service/legacy rejects503, tools-off rejects403 and cancels active job, busy409, cancelled preparation409, cleanup failure503. Runtime metadata shows available/busy/profile but does not prove sandbox readiness. UI prepare/cancel/export uses authenticated control, safe text rendering, no automatic retry/reconnect replay, no enable/approval action. Lifecycle shutdown closes owner. RI-004 overall PARTIAL until real security review/explicit approval/enabled worker gates, RI-005 unchanged.
## D45 — FIX-011 worker process ownership（2026-10-11）

WorkerSupervisor.execute(skill,arguments)與SkillDispatcher批准/frozen identity不變。trusted worker只處理≤65536-byte JSON request；json serialization不得NaN/Infinity；input/object/schema照原subset，不宣稱完整JSONschema。固定env SIRO_SKILL_REQUEST=/request.json；request位於owned ephemeral workspace、offloop建立/刪除、read-only獨立mount，不插入package、不改completehash。legacy direct worker stdin保留有界read。

adapter process_execution提供既有ExecutionContext/ExecutionCancelled/ExecutionCleanupError與execute_bounded_argv；services.tools.execution是相容入口，現有private _signal_owned_group monkeypatch可影響原入口cleanup。新worker不反向引用services。bounded helper仍sole PGID/session owner；bwrap使用unshare-pid、無new-session，取消只signal owned group，namespace關閉reap descendants，無host process掃描。

Manifest timeout只管worker collect（preparation IO bounded-by-content但blocked hostIO SLO未certified），float秒timeout保留ms期限，不round成整秒。stdout+stderr sharedbudget=max(manifest.output_bytes,4096)，stdout另外驗manifest限制；truncation拒絕，洪水仍drain到timeout/cancel，非JSON或nonobject拒絕。stdin-file準備/spawn/collect/cleanup取消均join，latecancel不回result；ExecutionCleanupError必須保留。supported trusted-local worker behavior保留，無untrusted/profile fallback或新的execution authority。

D45 independent review補充：保留services private `_protected_cleanup(process, readers)` 動態caller及signal hook；shared owner optional `stdout_errors="strict"` 在collect/reap後解码，worker必須拒絕非法UTF-8，舊一般argv文字輸出仍容許replace。真正U+FFFD不可誤拒。pending ExecutionCleanupError不能被後續request/snapshot cleanup的取消吞掉；成功時latecancel仍須傳回取消。新增反例先RED，再作局部修復。

## D46 — RI-004 strict worker contract（2026-10-11）

`WorkerSupervisor(*, profile="trusted-local")`：預設保留既有D45；唯一新增`python-stdlib-single`，unknown constructor profile ValueError。strict只Linux x86_64/systemPython3.14，missingruntime/namespace/filter failclosed SkillExecutionError("strict skill sandbox unavailable")，unsupportedmanifest/package SkillExecutionError("unsupported strict skill profile")，identity mismatch SkillExecutionError("skill package verification failed")。未發生hostcandidate import／trusted fallback。

strict profile requires exactly four normal captured files manifest.json/input.json/output.json/plugin.py, python:plugin:run, emptypermissions/observe/read_only/networkdenied/concurrency1/processcancel/compensationnone, memory≤256MiB/CPU≤5s/output≤131072/timeout≤10000ms (existing model lower bounds remain). 原Core/schema/registry/hash不改；完整capture/current identity比對offloop，frozen snapshot/root只傳owned bytes。request JSON≤65536bytes/allow_nanFalse，readonly trustedrequest不列packagehash。prep取消join再清ownedworkspace；cleanup取消不得回success，primary ExecutionCleanupError保留。

lower `adapters/isolated_python.py` 提供RI003原runtime mounts/sandbox argv，固定candidate/trusted readonly mounts及8MiB tmp；`adapters/python_restrictions.py` 承接同不可逆OS限制，optional memory_mb/cpu_seconds only tighter allowed limits (default256/5保持patchprofile)。patch_verification私有_mounts/_sandbox_argv facade保留原signatures，runner restrict仍可import/monkeypatch；trustedrestrictionscopy放/trusted，在candidate sys.path之前載入。

new trusted skill runner at `/trusted/runner.py` loads only trusted stdlib and readonlylimits/request, install restrictions before candidate import, explicit fixed plugin.run, boundedJSON object input/output。--probe固定`SIRO_SKILL_PROFILE_READY_V1\n`；probe/execution同manifestcollectdeadline，只用existinglowerexecute_bounded_argv(sharedstdout/stderr budget, strictUTF8)。probe非零/truncated/marker不精確全部unavailable；execution78 unavailable，其餘非零為workerfailed，輸出超量/壞JSON拒絕。候選自稱PASS不能授權。

API不接Gateway/UI/model/install/enable；只developer trusted synthetic verification。ActualD44fixedparser可用不代表安裝批准；其他OS、依賴、multiprocess、aggregatekernelRAM、blockedhostIO SLO、安全審查與明確ownerapproval保持未驗gates。source rollback停止新profiledispatch、只逆exactsource，不回退DB或以舊trustedfallback。

D46 independent-review correction（先RED再修）：Python metadata equality將False／0、1／True視為相等，不足作strict identity。strict捕捉時將完整manifest/schema canonical JSON（sorted／nonfinite拒絕）作typed JSON比較；`_prepare_strict(workspace,skill)->InstalledSkill` 返回verifiedcaptured snapshot。parent在probe之前以verifiedinput重驗arguments，limits/deadline/outputschema都取自verifiedidentity，不信caller metadata。原trusted-local與Core/D40 schema subset不擴。strict static profile拒絕在semaphore admission之前，以免偽造concurrency0先掛住；profilenumeric lower bounds保持。這是尚未啟用slice局部defect，不是新registry或schemaengine。

D46 deadline補充：synthetic實際spawn publication延遲反例證實相對timeout在spawn後才起算，不能滿足probe+run共同absolute deadline。strict caller沿用現有ExecutionContext(deadline=deadline)，helper於spawn前／後及completion fence重查；不改原helper或trusteddefault、不延長門檻。Manifest metadata先以model_dump(mode="python")保留實際bool/int，再canonicalJSON；mode="json"會coerce invalid model_copy欄位而不是identity證據。

## D47 — RI-004 activation contract（2026-10-11）

SQLiteSkillRegistry.install_if_absent(skill, *, enabled=False)->bool：核對完整型別敏感 identity，INSERT OR IGNORE；False 不修改既有 hash/root/state。set_enabled(..., enabled, identity=None) optional expected identity 比對 id/version/hash/root，enable/disable mismatch False；原 callers 保持。ToolCatalog.register(descriptor) 同 constructor name/schema/duplicate/deepcopy guards，以 additive copy-on-write 保留已 capture snapshot。

SkillActivationOwner(catalog, registry, dispatcher, managed_root): async initialize(), remember(result)->result+review_id (只成功 fixed-template review), install(review_id,package_hash), enable(package_hash), revoke(package_hash), suspend(), close(); snapshot() 純 metadata。Review TTL900秒/單份/owner epoch，immutable captured files，source/test/proposal digest 與 verification proposal id/changedpaths/pass/workspace_removed exact binding。固定 package 幾何和內容只由 trusted template；receipt 位於 package 外，只承認 fixed complete identity 與 owner 批准，無 client supplied source。

install 回傳 installed true/enabled false；enable 僅精確 identity、captured template/receipt 重驗後，strict WorkerSupervisor profile。catalog 現有能力 alias 不重造。descriptor.available 不做IO，model工具 text.checklist.parse；executor 必須 authorized context（argument-only executor拒絕），context cancellation/deadline fenced。text only、UTF8≤16384bytes/256lines、output pending/completed≤128total、每项≤256chars、counts exactint且等於array lengths。prepare 原服務不 install/enable。

create_app optional skill_activation；candidate profile only。沿原 same-origin/sessionToken。POST /v1/skills/activation/install 僅 strict review_id/package_hash；/enable /revoke 僅 package_hash。install/enable tools-off拒絕，revoke允許。runtime skill_activation snapshot 純讀。shutdown/tools-off join owner停止；request取消後不得有 late enable，cleanupfailure typed公開固定訊息。UI分開審查/install-disabled/enable/revoke，顯示狀態并填入既有 chat（不另設execute）。HTTP敗/unknown不重送。

D47補充：is_installed(skill_id,version,*,identity:InstalledSkill)->bool 只核對當前 registry stored id/version/hash/root（enabled/disabled都可），不驗source、不暴露store，startup沿此facade確認receipt對应row。close停止runtime admission與ownedjobs，保留已批准persistentenabled state供精確restart；tools-off suspend持久disabled，恢復tools仍需explicit enable。


### RI-005 D48 / FIX-012 — code-only rollback identity and data retention

Existing ReleaseManager constructor/stage_and_activate/rollback and CLI argument/result shape remain. Complete siro-release-manifest-v1 wire/signature unchanged. Staged version is immutable: after manifest/compatibility rejection, existing release/sidecar refuses release_version_exists before backup/copy/health/pointer effects. New complete signed sidecar root/manifests/<semver>.json is saved before pointer publication; failure leaves active pointer unchanged.

rollback statuses: rolled_back; original no_last_known_good for missing history/directory; invalid_rollback_target for malformed/untrusted history/receipt/package; schema_unknown for missing/bad/empty/non-prefix/over-limit actual DB metadata or invalid current_schema; incompatible_schema for known unsupported actual schema or target bounds mismatch. It never invokes backup, healthcheck, restore, migration, binary launch, effects replay or data writes. Old database_backup field is historical advisory metadata only and is never dereferenced. Missing/corrupt old backup is irrelevant to code rollback.

Target version strict semver, complete stored manifest validates and version matches history; verify existing complete signature and actual target digest; symlink/hardlink receipt/source refuse, receipt JSON bounded65536 bytes. Actual DB connection mode=ro/query_only; schema_migrations versions form exact [1..N], N<=4096, N<=manager current_schema, within signed target bounds. SQLite read-only WAL participation may access its bookkeeping; no DB/WAL content restore/replacement/checkpoint/migration is performed. Same-UID hostile filesystem races and concurrent schema change between snapshot and pointer are not certified; stopped-writer/launcher gate remains mandatory before any runtime switch.

Acceptance separates actual temp SQLite/WAL/CLI from controlled pointer-write failure. Published bundle readonlyness/OS isolation/stopped writer/genuine process version/readiness/deployment are NOT proved by a pointer test. Existing explicit restore path is unchanged and requires separate acceptance. D47/control/model/voice/permission/interface baselines must remain identical.

D48 staged identity supplement before production: after healthcheck, exact staging digest/signature is reverified before publishing sidecar/release/pointer; healthcheck-mutated bytes cannot acquire the original signed approval. Existing trusted checks must leave the signed bundle unchanged.

## D49 — FIX-013 explicit SQLite restore prevalidation（2026-10-12）

`SQLiteStore.restore_from(source)->None` 與 CLI/raw/ZIP callers 不改。這是 operator 明確要求的資料還原，成功可用備份取代新資料；code rollback 永不隱含呼叫它。來源以 SQLite mode=ro/query_only 讀取（WAL bookkeeping 不等於主資料修改），SQLite backup API 捕捉到自有 ephemeral candidate。所有既有遷移名稱/checksum、精確已知版本 prefix（允許 v0）、現有 apply_migrations 與最終 integrity_check 必須在 candidate 通過，才開啟 live target。未知 future/non-prefix/malformed schema、遷移 SQL 或檔案失敗不能改 live rows，也不能遷移 backup source。

Candidate→live 仍使用 SQLite backup API，保留 WAL 語意，不用主檔 replace/copy，不新增 schema engine/restore service 或跨程序 lease。每份 store 的既有 writer lock 必須持有到 offloop job、連線和 owned candidate cleanup 完全收尾；等待鎖時取消不開始 job。Single/repeated cancellation 通知 thread，source-copy/progression 與 promotion 前檢查；SQLite 尚未完成的 copy 可中止。若 SQLite 已完成 commit，取消仍向 caller 傳回且 join 完成，但不宣稱資料未變或自動重送/回退。阻塞 OS/SQLite IO 不承諾新延遲 SLO。

獨立終審在 Python3.14 實測 shield＋late cancel＋MigrationError 雖保有資料，仍向 loop handler 額外輸出 shielded-future error。已先 RED：同一 lifecycle case 加 exception-handler 觀測，1 FAIL/1 PASS。改為 `asyncio.wait((job,))` 等待 owned task，不取消 job，仍只由 `job.result()` 回報 primary error。已處理的錯誤不得再被本 restore owner 誤報為未觀察錯誤；不宣稱全產品零 log/error。

已確認 migration/SQLite/OSError 保留原型別；cleanup 失敗不得冒充成功。若已有主錯誤，附 sanitized cleanup-failure note 保留主錯誤；成功操作後 cleanup 失敗則傳回其錯誤。不能宣稱 cleanup 被 OS 拒絕時已移除 workspace。ZIP DB/config 的跨檔原子性、多 owner/外部 writer、power loss 與實際 launcher/version/readiness 為原 RI-005 另項 gates，本卡不解除。

先寫真臨時 SQLite/CLI/ZIP、WAL/遷移/取消與負向資料保留測試，再修唯一 production sqlite.py；D47/D48 完整 dirty source 基線必須保留。source-only 回退在 disposable 副本演練，永不回退實際資料。

## D50 — RI-005 managed data owner／stopped-runtime boundary（2026-10-12）

唯一 lower OS adapter `siro.adapters.data_ownership.exclusive_data_owner(database:Path)` 為 synchronous context，Linux/same effective UID/local FS/cooperating entrypoints profile。Canonical intended DB absolute path 作 SHA256 key；固定 pwd account home 下 `.local/state/siro/data-owners`（directory700，lock600），不依 HOME/TMPDIR/XDG/env override，避免 PrivateTmp 與尚不存在 target dir 使 namespace分離。空 lockfiles 是明示 OS coordination artifacts，不是 PID/TTL authority、registry 或資料；不讀內容、不刪/替換 lockfile，不因 stale metadata 偷鎖。D49 rejected restore 不能建立 target data directory。

Open lock O_CREAT/O_RDWR/O_CLOEXEC/O_NOFOLLOW/O_NONBLOCK；normal owned regular file、single link、same UID；固定 directory 同類型/UID/private mode。既有 DB 若非 regular 或有 hardlink alias拒絕，目錄/DB symlink canonical key核對；same-UID path replacement/hostile filesystem race不certify。fcntl LOCK_EX|LOCK_NB；同程序不同open也busy。Context fd保留到完整operation結束，只close、不LOCK_UN（fork shared description）；exec不繼承fd，raw fork child仍持fd則保守busy。Unknown OS/ownership failure拒絕，不PID fallback、kill、wait-spin或automatic retry。`DataOwnerBusyError`、`DataOwnerUnavailableError`固定safe text；已有primary error不能被close failure洗掉，清理失敗可見。

Gateway main在任何 provider/composition/SQLite初始化前取得，固定capture data_dir傳給既有body，保持到uvicorn返回/async lifespan/drain；legacy/candidate都用，existing create_app injectable API不變。CLI main針對demo/backup/restore（backup目前initialize可migrate）與release stage/rollback有明確database者取得同key，包住handler/asyncio.run、ZIP config/source cleanup/readback與executor shutdown。Busy/unavailable回原CLI非零＋新固定status data_in_use/data_owner_unavailable；不得開DB/生成candidate/寫config/backup/pointer/healthcheck/serve。NoDB standalone release原行為保持，明確不證data-writer停止。Direct SQLiteStore/IntegratedCompanion/ReleaseManager library calls不另取第二把鎖。

scripts/start、productlauncher、已安裝unit都走Gateway main；stop送TERM不代表stopped。新維護必須取得同lease，服務startup/drain期間不能取到。沒有自動停止/掃描/kill現用process；first adoption的舊版與raw SQLite/external writers不參與，lease空閒不能证明其停止。舊8026不碰；真正launcher consume signed release/version/readiness與maintenance→runtime handoff另驗，RI-005整體仍PARTIAL。

先契約/真OS與caller RED，再局部newadapter＋existing CLI/Gateway wrapper＋focused tests；268-file dirtybaseline、D49SQLiteStore和D47/D48/Core/policy/SQL不變。Unknown busy不重送，有failure/cancel須完整join後才能release。跨檔ZIP atomic/powerloss/networkFS/allSQLiteconnections singlewriter不列PASS。

D50 pre-implementation review correction：真SQLite/flock prototype證Python3.14第二次SIGINT可中断Runner.shutdown_default_executor，釋放outer fd時old thread仍覆蓋newowner資料；Runner亦有300s join timeout。因此只包asyncio.run的原提案不足。Context yield一份local owned resource，`loop_factory()`提供standard event loop/default ThreadPoolExecutor，Gateway initialization與uvicorn、CLI async handlers顯式用其factory；不改全局policy或SQLite body。退出時先用owned join-thread把僅本owner每pool.shutdown(wait=True,cancel_futures=True)完成，main wait對repeatedKeyboardInterrupt仍持fd；thread收尾後才能closefd。Primary error保留，成功後lateinterrupt傳KeyboardInterrupt；join未完成不假釋放，join失敗保留fd直到process退出而不是繼續維護。無host thread掃描/kill/第二套IOservice/背景scheduler。Actual mapped CLI repeatedSIGINT與Gateway loops必須獨立驗，不用prototype冒充接入完成。

D50 / FIX-014 write-scope correction：真受管target child仍持lease/openSQLite，CLI backup只鎖source卻replace foreigntarget，返回成功且兩份連線看到不同資料。已有singlewriter requirement不允許這種bypass。原context增加唯一optional `write_target:Path|None`，同一local resource捕捉最多兩份canonical key（os.fsencode、排序/去重），全取得後才body；partial acquire拒絕並清理。一次owned-pool join完成後才close全部FD；joinfailure保有全部FD直到process exit，不以nested contexts讓其中一份先釋放。Backup target、ZIP restore config都是實際explicit write target，必須同邊界。

CLI backup destination不得canonical等於source DB或inputsettings；ZIP restore config不得等於自身DB或sourcearchive。固定statuses invalid_backup_destination／invalid_restore_configuration、非零、zeroDB/config/sourceartifact effects。正常成功shape不變；samecanonical helperdedupe保留，但錯誤caller角色不能靠dedupe允許self-overwrite。不改SQLiteStore/operations/Core，不證ZIP多檔atomic或任意hostwriter安全；FIX-014在D50驗收完成前BLOCKED_BY_FIX。

D50 / FIX-014 final temporary-write correction：獨立actual ZIP probe證實fixed destination.tmp/config.tmp可刪除readonly input，或靜態alias使final target成selfloop；root新增8actual RED（temporary-target-before-all.log），包含自身DB與正在受管foreignDB暫存alias。此為同一confirmed missing-write-scope/collision根因，不新建RT或重設operations。原context僅增加optional temporary_write_target，最多source/explicit/fixed-temp三份canonical FD，仍一次有序去重partialcleanup與joint ownedIOjoin。只有ZIP caller依既有with_suffix(suffix+".tmp")捕捉fixedtemp；raw SQLite exclusive mkstemp不新增key。Temporary不得canonical等於sourceDB/readonly settings或archive/explicitfinal；正常明確distinctpaths保持。兩個write target全部持有到actualIOjoined；未知join仍保全部FD，不能nested提早釋放。Final三key/alias/repeatedSIGINT與全套必須重驗；歷史兩key綠燈不代表完成。

## D51 — FIX-015 backup cancellation owns actual IO and staging cleanup（2026-10-13）

Confirmed unchangedbackup_to bareto_thread exitswriterlock/ZIP TemporaryDirectory beforethreadjoined; trueCLI1/3SIGINT leavesrecreatedstaging/DB/WAL/SHM. REQUIRED_FIX/MEDIUM，IMPLEMENTATION_BUG/MISSING_INTEGRATION/TEST_GAP；不是D50OSownerfailure。只existingSQLiteStore backup_to/_backup_sync，新18focusedtests＋syntheticactualsignalprobe；operations、D49restorebody/SQL、D50adapter/CLI/Gateway、Core/policy/identity/providers/voice/UI/launcher/deps全保留。

Backup async同D49retainedjob/asyncio.wait/result：writerlock持到actualoffloopwork/explicitconnectionsclosed/cleanupresolved，repeatedtaskcancel不能提前放棄；primarybackupfailure先於pendingcallerCancellation，無unobservedduplicateerror。Backup-local ThreadEvent在knowncancel時set；private _backup_sync新增optionalcancelled=None，directoldsingleargumentcaller/正常publicAPI保留。Beforemkdir、nonDONEcopyprogress、beforefinalpublication檢查cancel。Copy的SQLITE_DONE只代表ownedtmpcopycommit；finalos.replace前仍可拒，不破壞prioroutput。已finalpublished後cancel不得假稱回滾，需readback不自動retry。

Exactownedsource/target都必須嘗試explicitclose，close/unlink失敗保留原typedprimaryerror並附type-onlynote；無primary的cleanupfailure必須可見，不吞/假cleanup成功。Finaloutput只在copy/integrity/connectionclose成功後原os.replace發布；不改backupformat/一致性檢查、不新增manager/executorservice/schemaengine。ZIPcontext由既有operations在backupresolved後正常清理；若hardRunnerprocessSIGINT打斷coroutine，synccancelguard與D50ownedpooljoin仍須真實驗到staging無late重建/無orphan，不能只用mock或套D49結論。

Tests distinguishdirect1/3cancel/writerqueue、actualmulti-pageSQLite(nonDONE/DONEtmp)、rawlatepublishedcommit、typedcopy/close/unlinkrefusalcontrols，和trueCLI1/3SIGINT。Fences/cleanup失敗/未知OSIO不可標DONE或重送；不做全SQLite連線掃蕩。不操作live8026/privateDB/chat/WAV/key/models/GPU或正式deploy。Exactsource-only rollback保latestdata；cap/backupretention/powerloss/oldunmanagedowner/真正signedlauncher版本/readiness/批准handoff門檻仍保留。

D51 pre-implementation process-cancellation refinement：真SIGINT審查顯示Runner.close會cancel_all_tasks，ownedto_thread Task也可能被全局cancel而誤判thread已完成。Backup-local retainedjob用原loopdefault executor的Future（run_in_executor＋copy_context.run保持to_thread context傳播），asyncio.wait不把caller取消傳到future，也不是all_tasks成員；同一ThreadEvent跨已知cancel到syncguard。原D50ownedpools/owner不改、不新建executor或manager。Actualprocess3SIGINT可打斷Runner.close，syncfences＋原ownerjoin仍需probe證實工作完成/staging清除/無遺留；不能把Future選擇當作證據或改D49restore。

D51 verification correction（local caller only）：firstSQLite-onlyguard已19cases與真8casesdata/stagingPASS，但所有3SIGINT進Runner.close的cases有Taskdestroyedpending警告。MINOR_FIX/LOW，REGRESSION/MISSING_INTEGRATION/TEST_GAP，不是新資料loss；不能遮warnings。修正範圍最小允許CLI既有_backup wrapper在mainthread的單次backup operation臨時把SIGINT轉成該ownedcoroutine.cancel，反覆signal仍等backup IO/cleanup；finally恢復原handler。Signal導致的CancelledError才轉原KeyboardInterrupt/130；普通callerCancelledError/primarytypederror保留，其他commands/Gateway/OSgrant/全局永久signalpolicy不變。新增5focusedcallerrestoration/primaryerror/threadfallbackcases＋更新真8SIGINTprobe。無新的Runner/manager/framework；sourcebackup與CLIbeforebytes捕捉，exact4sourceonlyrollback必須驗。

D51 actual-selector correction：初版temporary handler僅task.cancel，true pausedIO 8 cases與原D50 backup init2cases均不喚醒blockedselector；不是測試需放寬。沿stdlib Runner既有cancel＋loop.call_soon_threadsafe(noop)，立即喚醒同ownedloop讓取消處理。原D50測試不改；新增late-signal/body-success case後CLI6＋SQLite19。先保留actualRED、重凍finalsource再完整驗收；未知blockingIO仍須等待，不能假定cancel能中止OS。

## D52 — RI-005 opt-in signed source launch / actual readiness identity（2026-10-13）

Existing product launcher default, CLI release stage/rollback, complete signed manifest and data formats retain behavior. Explicit operator SIRO_RELEASE_ROOT plus existing SIRO_RELEASE_SIGNING_KEY opts into signed source launch; this is not model approval, stop/deploy or automatic release. ReleaseManager.resolve_launch_target()->immutable VerifiedRelease(version,source_sha256,directory,schema_version) reads bounded strict active.json/complete receipt, exact version/signature/current source regular tree and actual readonly known schema. Missing actual DB/prefix => schema_unknown; unsupported => incompatible_schema; no pointer/DB/backup/check writes. Static symlink/hardlink/special package nodes refuse, fixed src/siro package/Core/Gateway paths required. Status errors ReleaseLaunchError: no_active_release,invalid_active_release,invalid_release_target,schema_unknown,incompatible_schema. Existing read-schema fact is locally reused, not another manager.

Launcher keeps original working cwd/data/assets semantics and captures absolute data path. Signed mode uses preexisting assets only, no cargo/renderer/tokenizer provisioning, exec fresh interpreter -I -B with selectedsrc first, no preimport host SIRO or fallback. Exec environment copy removes release signing key; public version/path/digest/schema only bootstrap arguments. A D52-compatible selected Gateway receives VerifiedRelease as explicit composition argument, not ambient version env. Under its existing D50 data owner, before provider/DB init, validate actual package/Core/Gateway __file__ against selectedsrc and re-read actual schema. Target migration count must equal selected actual schema; required migration refuses (schema_migration_required), intervening data schema change refuses (data_schema_changed); no implicit schema migration by selecting a version. Wrong origin => wrong_loaded_source. Same-UID mutation after parent verification remains unproven; origin is not cryptographic live-byte attestation.

create_app optional verified_release, default None keeps exact health shape. Only this opt-in reports release version/source_sha256 on /health/ready after all startup callbacks succeed; before startup or after drain has no release-ready metadata. Static siro.__version__/activepointer/env label is not actual loaded identity. Complete lifecycle follows original owner/UVicorn/drain/ownedIO. Parent lease cannot cross CLOEXEC; no double-owner attempt or automatic old-process kill. First-adoption old/nonmanaged writer absence, maintenance→exec gap, exact approval/handoff, powerloss and arbitrary code remain separate gates.

Tests before production: selector true temporary SQLite/signed paths/negative records/read-only retention; launcher no fallback/key removal/no provisioning/data continuity; opt-in ready lifecycle; true two source versions start isolated HTTP, code rollback retains latest conversation/memory/completed ledger; corruption/unsupported/missing startup rejects with no provider/action effects; all fixture children joined/temp roots removed. No live8026/privateDB/chat/WAV/key/config/models/GPU or formal deployment. Preserve D48/D49/D50/D51 behavior; 273-file baseline, exact3 existing sources plus only necessary new tests source-only rollback.

## D53 — FIX-016 clean CI bootstrap and exact public-pin secret review（2026-10-13）

Build-only correction. Existing pinned Rust 1.97.1/minimal declares rustfmt and clippy; fmt/build/test/clippy and all Python/schema/secret gates remain. No Python pin/lock/workflow/runtime changes. Secret detection still scans the same public source scope. Only six independently verified public GPT-OSS revision/checksum findings may be acknowledged, bound to exact repository path, full profile blob SHA256, detector type, line and hashed finding. Changed profile bytes, new credential, other path/type/fingerprint, verified secret or malformed report fails closed. Helper emits location/type only, never raw secret. Public constant lines may have explicit per-line scanner annotation; no whole-file/plugin suppression. Tests use actual detect-secrets reports and synthetic credentials, exercise positive/public and negative/changed/new/malformed paths before implementation. Cold isolated Rust installation and complete clean public archive scripts/check plus exact-head GitHub Actions are required; earlier partial pytest or component success is not full CI PASS. Runtime source, users' data and production service remain untouched. Source-only disposable rollback restores the two existing build files and removes only new helper/test, preserving all prior work.
