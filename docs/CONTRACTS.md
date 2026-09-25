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
