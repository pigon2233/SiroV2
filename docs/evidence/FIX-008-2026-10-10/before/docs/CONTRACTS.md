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
