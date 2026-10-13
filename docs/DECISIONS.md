# 決策紀錄

目前均為 2026-09-23 的規劃基線，T00 核對環境後可補充實作版本。使用者明確修改需求時優先更新此表與受影響文件。

| ID | 決策 | 原因與取捨 | 重新評估條件 |
|---|---|---|---|
| D01 | 新 SiroV2 核心，不直接接續舊 Bridge | 使用者要求重新規劃；舊版能力逐項契約移植 | 已證明可獨立复用的模組 |
| D02 | Python Core、Rust Runtime、TS 身體接口 | 認知開發效率與 OS 權限分界；需承擔跨語言 schema | 實測成本或依賴不成立 |
| D03 | 模組在 Core 內，風險服務分程序 | 降低服務數量，同時隔離音訊、模型與工具 | 可觀察瓶頸／故障耦合 |
| D04 | SQLite 為核心持久狀態；NATS 用作傳輸 | 明確 durable ownership，避免所有模組寫同 DB | 真正需要多核心寫入或更高吞吐 |
| D05 | 採最小 Web renderer；AIRI 保留參考 | 鎖定 AIRI 外部協定沒有 direct speech/emotion/cancel body commands | T11 ADR 與 source 稽核 |
| D06 | 完整電腦能力分類＋有範圍授權 | 保留使用者需求，將決策與執行權限分開 | 新平台或新 capability |
| D07 | 任務分派進 v1.1；模型切層做 R01 | 前者可工程交付，後者受硬體／網路強烈影響 | 實驗證明容量或延遲收益 |
| D08 | 優先 Linux 實測，跨平台逐項標示 | 開發環境已知，但未確認部署 OS | T00 使用者目標平台 |
| D09 | 用 Markdown 文件包交付規劃 | 方便 Sol 在 repo 按任務讀取、diff、更新 | 需要對外印刷時再產生 DOCX/PDF |
| D10 | 本次只寫規劃與交接規範 | 使用者要求計劃書，沒有要求立即實作程式 | 使用者後續啟動實作 |
| D11 | 延期 WoT 產品整合，保留有限 TD translator | spike 可減少基本 descriptor 手寫，但 forms/security/transport/readback 仍需專屬 adapter；現在導入完整 WoT stack 只增加依賴與攻擊面 | 出現至少兩種已授權 WoT 設備，且共用 binding 可明顯減少實作 |

## 新決策範本

```text
ID / 日期 / 狀態：proposed | accepted | superseded
問題與證據：
選項及取捨：
決策：
影響任務、schema、migration、驗收：
回退／退出方式：
取代哪一項舊決策：
```

## D12 / 2026-10-01 / accepted / RT-002

在既有 ConversationEngine/CompanionCore 加 optional native message passthrough。IntegratedCompanion 的 candidate profile 每個 run 持有原始 user goal、context system message、assistant/tool call_id 配對；legacy 預設保持原 prompt 路徑。主入口使用 SIRO_RUNTIME_PROFILE，無 public HTTP/WS 或 DB schema 變更。工具結果不追加為 user working memory。此階段 history 僅 RAM；重啟恢復另屬 RT-008，多工具 batch 另屬 RT-003。回退：drain candidate 後新 run 用 legacy。

## D13 / 2026-10-01 / accepted / RT-003

candidate profile 在同批所有工具 terminal 後才接續模型；結果按 assistant call 順序附加，callback 去重。取消/錯誤有唯一 run terminal gate；不在此卡終止 OS process（RT-005）。拒絕提案為 terminal result 不執行。Gateway 原拒絕仍execute的路徑需最小修正，屬本卡caller必要修復。無DB enum/schema或provider/body算法變更。

RT-003 caller discrepancy：ToolApprovalInput 原先只允許 Literal[True]，所以 HTTP 層根本無法送拒絕。改為 bool 是新增接受 false 的相容擴充；既有 true payload/response不變，未另建公開端點。

## D14 / 2026-10-01 / accepted / RT-004

candidate computer.execute 的 subprocess I/O 使用有界 facade；stdout/stderr並行drain/discard，共用64KiB保留預算，避免read完才截斷。保留argv/cwd/returncode/stdout/stderr/truncated觀測欄位與原權限驗證。legacy仍走原closure。兩管道競爭共用預算，所以大輸出時各管道保留份額不保證；一般未超限結果相同。OS process tree取消仍RT-005。


## D15 / 2026-10-01 / accepted / RT-005

candidate run建立不可變ExecutionContext（run/session/call/proposal/epoch，shared cancellation token，已批准metadata與monotonic deadline），ToolOrchestrator可選contextual_executors保留舊arguments-only handler。Gateway驗證argv等參數後才傳context，deadline沿用timeout上限；不新增Linux/root權限、HTTP必填欄位、DB enum/schema或Rust改動。

取消先claim terminal/fence dispatch，cancel_run等待owned foreground executor cleanup；獨立session/process group由argv backend建立，TERM 250ms後KILL並reap直接child，drain保持有界；cleanup最多4.5s，run等待最多4.75s，失敗用現有FAILED+ExecutionCleanupError明報。取消中的proposal使用現有FAILED+ExecutionCancelled，不新增state格式。晚到自動及手動HTTP工具輸出均fence。

Gateway為roadmap未列出的必要caller：candidate turn_id映射到state.active_turns的session，只取消該session；unknown ID不殺任何run。既有explicit active alias保留全active取消；legacy callback行為維持。正常完成/取消同時發生時token check與唯一terminal gate決定結果，不重播副作用。

Detach明確沿用已ack started/pid/argv相容觀測：ack後交付給既有session/使用者管理，run取消不殺已啟動應用；ack前取消仍清理owned group。現行無session teardown hook，不宣稱detach自動session-close cleanup。此相容限制已明列，未擴張RT卡新增GUI lifetime manager。


## D16 / 2026-10-01 / RT-005 delivery-fence repair

獨立writer驗證揭露urgent/normal公平仲裁可讓queued舊工具事件晚於terminal送達。candidate由controller為每次回覆建立固定optional stream_id，Hub依proposal關聯補上手動工具事件的ID；同run events帶同一ID，不新增必填HTTP/WS欄位。ClientChannel在唯一writer送達terminal後丟棄該stream後續queued progress/duplicate terminal；新stream與其他session不受影響。前端也依optional stream_id作bounded terminal fence，legacy無stream_id事件保持既有消費。urgent burst/queue capacities不改，不僅調高terminal priority。stream是UI delivery identity，非持久AgentRun ID。

競態測試的entered等待原先包含Core/SQLite初始化，2秒產品停止門檻被誤用為fixture啟動上限。分離prewarm與entered診斷等待（同時監看respond task，以呈現原始異常/iteration/stack），取消後2秒要求維持。歷史一次超時的精確I/O來源無法从摘要復原，不聲稱已重現其因果。


## D17 / 2026-10-01 / RT-006 candidate Qwen lifecycle

render bytes/public HTTP/WAV與音色保持；candidate私有worker JSONL加入request_id/epoch，舊worker requests仍可使用。adapter startup failure/timeout/cancel/mismatch隔離並kill/wait舊worker，未完成cleanup不得spawn替代。單adapter單worker，有界8個active+waiting render；close取消active並封鎖queued/新請求，Gateway lifespan finally回收candidate。legacy render path保留。無新增依賴/模型資產更動。


## D18 / 2026-10-01 / RT-006 frontend cancel repair

原cancel只取消turn、沒有abort TTS。保留HTTP/backend；前端每筆speech有AbortController與generation fence，cancel即使currentTurn已清空也停止pending request及播放器；新輸入/新speech也停止舊speech，late blob/play/error不能復活或覆寫新狀態。人工相容性未驗不得標DONE。


## D19 / 2026-10-02 / RT-007 catalog/effective config

candidate descriptor以同筆definition/handler/context handler/readiness/backend包既有兩個model工具；process.start仍hidden compatibility handler。每model round取可用definition snapshot，dispatch時再查switch/readiness及原schema，不改授權模式/argument hash/state格式。舊arguments-only constructor與legacy靜態tools保留。新增authenticated /v1/runtime diagnostic只輸出明列profile/routes/permission/tools，不序列化env或JSONsettings/credentials；Gateway既有env composition優先不改，JSON SiroSettings仍獨立未接入，明報config source/env。


## D20 — RT-008 additive durable journal / read-only recovery (2026-10-03)

Candidate stores versioned canonical message checkpoints, ordered batch calls, model-round/tool-call budgets and startup profile/backend/privacy/epoch in migration 013. Existing agent_runs/steps/enums and legacy behavior stay intact. Assistant batch commits before any proposal/dispatch; one optional orchestrator lifecycle hook records dispatch intent before handler and observation before delivery, covering auto and HTTP approval. Observation commits independently of whole batch completion. Recovery runs at candidate Gateway startup and lazy initialization: incomplete actions become outcome_unknown if dispatched (or persisted proposal running), otherwise interrupted/not_dispatched. It fences queued persisted proposals, builds complete paired readback context, and marks old active run FAILED using existing error fields. No handler/model replay; no live context binding to restored runs. Missing readback remains unknown, not inferred from process exit or retried. Authenticated per-session readback exposes recovered context/budgets and uncertainty; UI warns owner on boot. No general session restoration (RT-010), provider retry (RT-009), active process discovery or exactly-once claim.

Repository transaction and unique run/call keys make checkpoint and duplicate observation writes deterministic; reserve model budget before every candidate model request. Atomic journal checkpoints do not replace private DB retention policy; evidence only uses temporary synthetic databases. Recovery disabled via legacy startup keeps schema/readers, never downgrades or auto-restores DB. Gateway/UI caller and optional orchestrator hook are necessary scope additions to roadmap's expected files, not unrelated refactoring.

## D21 / 2026-10-04 / FIX-001 accepted-generation gate

Both initial and continuation controller paths accept tool batches only from COMPLETED generations. FAILED/CANCELLED TurnResult keeps partial text, calls and original error for diagnosis; CompanionCore appends partial text without rejected tool calls to canonical accepted history. Final agent_steps payload adds optional rejected_tool_calls for audit (not an executable batch). Previously committed observations remain intact. Existing terminal enums, successful messages, authorization, provider transport and migrations stay unchanged; no retry/fallback added.

## D22 / 2026-10-04 / RT-003-FIX-01 candidate call ownership

Provider call ID is local to a run; candidate tool_proposals.call_id uses the existing unique proposal UUID as private storage identity, while run_journal_calls retains original provider call ID. Proposal insertion and exact journal proposal_id binding share one transaction; public ToolProposal/readback/HTTP/provider payload return original ID via that binding. Legacy rows/callers remain readable; unbound historical candidate crash-gap matching is allowed only with an unambiguous matching session/call/capability/arguments owner. Dispatch/callback/recovery use exact proposal binding. RAM dedup is run-scoped and cleared at terminal. No migration or provider interface change.

## D23 / 2026-10-04 / RT-005-FIX-01 candidate arguments-only ownership

Register every candidate invocation at the common orchestrator boundary. Contextual argv keeps its token/PGID cleanup; arguments-only task receives cancellation once and owner waits at most 4.75s. Tasks remain owned until actually done; a refusing/delayed cleanup reports FAILED/ExecutionCleanupError plus journal unknown, never external-stop success. Old callable signature and legacy remain. Browser startup failures/cancellation must close acquired browser and Playwright; application caller keeps an owned spawn/PGID until its original acknowledgment, then keeps existing user-managed detach lifetime. Use existing protected group cleanup; do not change argv backend. Only local owned handles, no process-name cleanup.


## D24 / 2026-10-05 / RT-009 bounded provider attempts

Extend existing FailoverModel, no router or LanguageModel port change. A generation gets at most two total backend invocations, including initial and retry/fallback; retry only transport/connection/timeout and HTTP429/502/503/504 failures before text/tool/finished emission. Retry uses a new private generation ID with original prompt/messages/privacy/output budget. Backoff is short, fixed and cancellation-aware; no retry after token/task cancellation or terminal/emission. Selected candidate Gateway provider is wrapped; legacy uses original single provider. SIRO_MODEL_RETRY_ENABLED=0 disables only this wrapper for new startup; env provider priority is unchanged. No new cloud fallback backend is composed. Existing authorized primary cloud first request remains; any additional cloud attempt requires cloud_allowed AND an explicit additional-cloud-request budget. Main has no configured cost budget and therefore uses zero extra cloud attempts; no USD/daily spend enforcement claim or new JSON config semantics. Direct callers can explicitly budget additional cloud requests, capped by global two attempts. Actual OpenAICompatibleAdapter is recognized as cloud, explicit cloud indices support injected adapters.

OpenAI SSE buffers partial tool deltas before yielding ToolCall. If the transport fails after such a fragment, a private standard exception note fences fallback while preserving the original provider exception class; otherwise wrapping only visible chunks would retry after provider tool intent. This is a necessary precise adapter scope addition. Existing FIX-001 accepted-generation dispatch gate remains untouched and must regress PASS. No migrations, journal/session restore, model weights, audio/body, grants, identity or device changes. Tests/evidence use isolated temporary data and synthetic credentials.

## D25 / 2026-10-05 / RT-009 selected provider metadata repair

FailoverModel captures its primary selected provider name at construction. Existing Integrated caller persists that stable name unchanged, not policy wrapper identity or a mutable last-attempt name shared across concurrent runs. No port/schema/readback format changes. Multi-provider direct callers retain selected-primary provenance; this field is not a per-attempt execution trace. Historical failover rows cannot be inferred safely and are not rewritten. Standard main tests must assert live API, raw SQLite and fresh-store readback for local/cloud retry on/off.

## D26 / 2026-10-05 / RT-010 bounded session hydration

Reuse version1 candidate terminal COMPLETED run_journal as the sole restoration source; no second journal or reconciliation loop. Read at most12 completed runs for the exact session and current privacy class, extract each run's last raw user matching immutable goal and final assistant without tool calls, retain newest complete dialogue pairs within12 messages. Native user/assistant messages precede the new raw user; a fresh system prompt supplies current identity/memory/affect/runtime context and excludes RAM recent text to prevent duplicates. Old system prompts, intermediate tool batches/results, partial/failed/interrupted runs and legacy conversation rows are not restored. Unknown actions remain solely in RT-008 readback, never replayed. Invalid version1 canonical text fails explicitly, not parsed as legacy. Existing readback marks legacy_unrestorable. This is recent dialogue hydration, not full historical tool transcript reconstruction, token budgeting, summarization, or memory ingress.

Integrated loads this once before creating each candidate run and Core remains the single append owner. Core optional recent_messages defaults None for old callers; continuation does not rehydrate. SIRO_SESSION_RESTORE_ENABLED=0|1 is frozen at candidate main startup, default1; feature-off and legacy keep existing paths. No schema/state/API break; current startup identity is fixed siro, privacy class equality prevents old local-only text from entering a cloud run. Stored checkpoints remain compatible bounded native messages. Necessary runtime wiring in integrated.py/gateway.py is beyond the original expected list, recorded explicitly.

## D27 / 2026-10-05 / RT-011 request byte budget slice

The architecture review SPLIT authorizes hard request-size measurement/rejection only; summary remains DEFER. A LanguageModel wrapper in services/agent/context.py measures compact UTF-8 JSON of the complete logical ModelRequest, including tools/schema, messages/arguments/results, prompt fallback, privacy and output-token setting. It rejects over-limit requests before any provider invocation; no dropping, rewriting, summarization or memory writes. Byte units are exact for this canonical representation, not provider token count or HTTP wire size. No verified provider tokenizer/context-window metadata exists in current composition; do not invent bytes-to-token ratios or claim native context-window enforcement. Record this discrepancy; provider-token part of RT-011 remains unverified and task must stay PARTIAL while this requirement remains.

Candidate main binds a default65536-byte cap at startup via SIRO_CONTEXT_MAX_BYTES positive integer; 0 explicitly disables only this guard for rollback. Legacy ignores the setting. Wrapper encloses FailoverModel so oversized input cannot cause retries/fallback. name captures selected provider name, retaining RT-009 durable provenance. Prompt/messages are untouched; pending pairs, goal, authorization/source remain in journal when ConversationEngine catches ContextBudgetExceeded and publishes existing failed/error terminal. No port/schema/config JSON change, no Core import of service implementation. Gateway caller is a necessary expected-list addition.

## D28 / 2026-10-05 / RT-011 native GPT-OSS budget completion

Pin official openai/gpt-oss-20b tokenizer/template/config/license at6cee5e81ee83917806bbde320786a8fb61efebee with SHA256 manifest. For selected Groq openai/gpt-oss-20b, use official131072 context/65536 output limits (Groq docs + config), same OpenAI adapter payload builder for measurement and send, official sandboxed chat template + tokenizers BPE on CPU thread. Parse serialized function arguments into dictionaries for official HF tool-template input without changing wire payload; multi-call batches unsupported by this template fail closed rather than count only first. Reference template token count + requested max_output_tokens +256 server framing safety must fit startup cap (optional SIRO_CONTEXT_WINDOW_TOKENS can only reduce model limit). Groq server internal formatting cannot be claimed identical; reference count plus margin is the explicit policy.

SIRO_CONTEXT_TOKEN_BUDGET_ENABLED=0 disables only native guard; byte limit independent. Candidate defaults token guard enabled, unknown provider/model or missing/tampered tokenizer fails ContextBudgetUnavailable before any provider call. Offline model performs no model inference and needs only existing byte ceiling. Legacy keeps original behavior. Tokenizer asset loading only uses local files, checks pinned hashes; no runtime network/download. scripts/setup_context_tokenizer.py explicitly provisions public pinned assets without credentials or model weights. Dependencies tokenizers0.23/Jinja2 3.1 (Apache2.0/BSD), lock updated. Native guard imports adapters only in service composition, Core port/schema remain intact. Prior synthetic main fixtures explicitly disable native guard, retaining their scoped byte/retry/session/catalog baselines; new actual-main tests exercise selected native policy. Summary remains DEFER per existing SPLIT.

## D29 / 2026-10-05 / RT-012 session-owned browser wrapper

Candidate adds a bounded, in-memory session browser pool around the existing ScopedBrowserDriver, keeping legacy/stateless browser.navigate+read untouched. The contextual executor owns session identity from ExecutionContext, never model arguments. Additional candidate tools browser.read/fill/click/close use the same catalog and authorization checks; fill/click require the observed screen_version, role and exact name. Namespace driver screen hashes by a random driver epoch, rejecting cross-session/recreated-page targets. Same-origin navigation preserves page/cookies; explicitly navigating another origin closes the previous scoped driver and creates a new one, not an expanded origin allowlist. No saved credentials/profiles or driver-core changes.

Default idle TTL300seconds and maximum8 session drivers, bounded per-action30seconds. Pool reaper starts in Gateway lifespan; cancellation/error closes the affected driver, idle expiry/explicit close/shutdown clean session resources. Existing cancel endpoint also closes idle owned browser sessions. A WebSocket control connection has no canonical conversation session identity, so disconnect alone cannot safely close a driver's owner: idle TTL is the disconnected-client cleanup boundary. Unknown/sessionless contextual invocation fails; no stateless fallback for candidate stateful tools. Startup SIRO_BROWSER_SESSION_ENABLED=0 preserves stateless candidate navigate and exposes no added tools. Gateway gets an optional shutdown callback so browser and TTS/hub cleanup stay guaranteed. This additive caller/schema work is needed beyond the original tentative adapter-wrapper file list; Core, driver internals, protocol/state formats and authorization defaults remain unchanged.

## D30 / 2026-10-05 / RT-014 explicit owner memory ingress

Candidate authenticated user-turn entry calls MemoryService.ingest_owner_request on the original recorded UserTextEvent only. Exact leading 記住：/請記住：/幫我記住：/remember:/please remember: marks an explicit owner statement; prose, quoted instructions, assistant/tool continuations and inferred affect never create memory. Source/session/type validated, identity exists from Core startup, person fixed owner by caller. Commit an episodic memory via existing remember/revision repository, not SemanticFact or persona. UUID5 from source event and identity makes repeated same-event ingress idempotent using existing source lookup. No persistence format/schema change.

Original user event remains local_only; newly stored memory does not automatically gain cloud permission. Candidate recall uses additive route-privacy filter: cloud receives only memories whose every source event explicitly allows cloud; missing/unknown sources fail closed. Legacy recall/API browsing retains old behavior. Confirmation adds sourced runtime context with memory ID and local-storage limitation, only after durable commit; no new HTTP/WS event type is needed. Persistence failure finishes candidate FAILED before provider invocation. Existing correct/delete/revision HTTP endpoints remain the supported mutation paths; no fuzzy text-based correction/deletion or new grammar for those operations. SIRO_MEMORY_INGRESS_ENABLED=0 disables writes at next candidate startup, not deletion of committed memories; safe recall filtering remains. Necessary repository/Core/Gateway wiring exceeds tentative files but preserves contracts with optional keywords/defaults.

## D31 / 2026-10-06 / AR-06 native batch counting, AR-07 clean gate

For completed multi-call assistant batches, normalize only a private counting view into each original call paired with its call-ID-matched tool result using the pinned one-call Harmony template. Preserve original wire payload, roles, message order and journal; no executor replay or truncation. Require exact unique IDs and complete results for multi-call counting, reject malformed/incomplete batches. Single-call reference counts remain unchanged. Multi-call policy additionally reserves the full serialized original batch payload token length, a conservative local allowance rather than a claim of exact Groq server framing. Every call/name/argument/result is counted; reserve and byte limits still enforced.

scripts/check explicitly runs the existing pinned/hash-checked public tokenizer setup after dependency sync and before pytest; CI uses that shared entry point. No runtime download, skip, profile registry or credential use. Validate an empty isolated cache through the same preparation/native test commands; report full check failures separately rather than replacing the whole gate with native-only tests. Summary remains DEFER pending need/source evidence. Deferred items get disposition only from their evidence gates, not from the user's request alone.

## D31 — RT-013/015/011 product slices (2026-10-06)

Owner explicitly requests implementation of all three previously deferred slices. Preserve RT IDs; implement sequentially. Candidate gets an owned unprivileged Rust read/list backend rooted at configured SIRO_WORKSPACE_DIR (default dedicated data_dir/workspace), signed single-use grants only after trusted tool authorization, no fallback on failure. No access to home/root by default. Runtime binary absence must not block conversation; UI reports readiness. Existing broader computer.execute permission is separate; scoped read is not a sandbox for all tools.

Background memory organization is a single lifespan-owned, bounded, local deterministic derived view of existing committed owner episodic memories. No new facts, personality changes, cloud call or unsolicited speech. Source revision snapshots are checked on read; foreground preempts work, completed tasks are reaped. No new schema: restart rebuilds disposable view. Owner can switch off and inspect/correct/delete originals in UI. This is useful organization, not automatic semantic consolidation.

Context summary is explicitly extractive with omitted-content markers and source hashes, not invented facts. Compact completed old assistant/tool text only, preserve all user goals/system/authorization and pending pairs, keep newest observations raw. Guard still validates final payload. No cache/store; raw journal unchanged. Bounded restore may include older completed dialogue only in summary mode; any memory correction/deletion invalidates restoration of older runs conservatively. Current in-flight source mutations fence the active context. No extra model or cloud use. Expose feature state and local product entry points; rollback flags at drained restart.

D31 UI refinement: an authenticated, explicit owner read/list endpoint uses the same WorkspaceRuntime scope checks and signed Rust grants, with the tools kill switch enforced. It does not infer approval from model output. This allows offline file inspection in the product panel; model-proposed reads still use the existing orchestrator/journal path. No write or arbitrary path grant endpoint is added.

## D32 — Repair the actual companion experience (2026-10-06)

Owner rejects offline fixture replies and debug-centric UI. Prioritize one verified Live2D character + real configured conversation + persistent renderer emotion projection. Product launcher loads allowlisted local model settings without printing secrets and discovers the existing licensed renderer; production launch fails clearly if no model is configured instead of silently shipping OfflineDemoModel. Main injection/test mode remains compatible.

Keep only Haru in the current renderer until per-model expressions are verified. Latest emotion is replayable presentation state; speech, gesture and actions are never replayed on reconnect. Detaching an old socket must not detach its replacement. Preserve Core affect/identity algorithms. Existing computer.execute capability already accesses files/programs under the ordinary OS account; surface it as computer assistance, retaining actual authorization/kill-switch boundaries. The scoped workspace is a secondary optional read interface, not the definition of computer capability.


D32 verification refinement (2026-10-07): the ordered control stream owns active turn state; the HTTP response must not revive an already completed turn. Tool approvals remain visible for every proposal. Disable the SDK's random expression mutation so rendered emotion has one owner; use the page stage background. Explain local memory persistence, automatic source recording, bounded dialogue restoration and cloud/local-only isolation using actual runtime facts. Preserve privacy filters. Configured cloud chat starts with its cloud permission enabled; disabling it rejects new cloud turns and cancels active work through the existing cancellation path. Unsupported native-budget model configurations fail at the product launcher with an actionable explanation rather than accepting a configuration that makes every turn fail.

D32 privacy verification (2026-10-07): preference-derived context follows the same source privacy boundary as memory. Local affect appraisal may use local preferences; model-facing cloud context must omit preferences whose sources are local-only or unknown, and must not leak their subjects through affect explanations. Keep the original source metadata and schema. The real UI test uses isolated synthetic storage; the persistent product entry uses the original local store only after an on-machine consistent SQLite backup. No private chat is exported as verification evidence.

## D33 — Repair provider completion at its boundary (FIX-003, 2026-10-07)

Keep the LanguageModel/Core/HTTP/WS contracts and output budget unchanged. OpenAI-compatible responses with length, content_filter or unsupported termination fail through fixed ValueError subclasses so existing terminal persistence retains a safe reason and FailoverModel cannot retry them. Preserve partial text, but buffer all tool intents until valid completion; retain the existing partial-intent exception note for transport failures. SSE completion accepts stop/tool_calls or reason-less [DONE]; a bare EOF without either fails. Complete non-stream JSON may omit/null finish_reason for existing compatible providers. Cancellation takes precedence; no universal OpenAI termination requirement is imposed on other adapters.

UI preserves partial text and visibly marks failed/cancelled replies, including continuation failures with nonempty bubbles. It does not speak partial output as a completed reply. This corrects a demonstrated false-success path; it does not prove the root cause of historical cutoffs or authorize automatic continuation/replay. Official termination semantics checked against [Chat API reference](https://developers.openai.com/api/reference/resources/chat).

## D34 — One on-demand page session owner (FIX-004, 2026-10-07)

Preserve 300-second credentials, Origin/loopback bootstrap and Bearer checks. The page renews on demand through one single-flight owner using returned expiry and monotonic time; no perpetual refresh loop. All HTTP calls share it, including STT/TTS/cancel, preserving body types and cancellation. Retry once only for the exact same-origin gateway pre-accept expired-token 401; never retry ambiguous network errors, provider failures or accepted effects. Late old-token 401 cannot invalidate a newer token. Server issuance prunes expiry, caps active tokens128 and rejects capacity rather than evicting valid clients.

Keep healthy control/body connections during token rotation. Reconnect control through one bounded attempt/timer, fence stale callbacks, wait for authenticated snapshot before sending a new turn/approval, and synchronize active-turn state without replaying voice, tools or messages. Original body owner/fence remains unchanged. A failed connection request is not permission to resend an accepted operation.

## D35 — 修復既有語音caller的完成判定與分段交付（FIX-005 A/B，2026-10-07）

重用既有聲線／segmenter／owned worker，補局部completion protocol與有界plan，不新增Core音訊owner。final後分段、最多一段預取，等待實際ended才記全文成功；取消與未知結果不重播。限制與HTTP／worker欄位見CONTRACTS的FIX-005 A/B。每段80字等初值是待量測資源設定，不是已達成TTS首音一秒目標。

本機qwen-tts0.1.1外層會丟棄自訂stopping_criteria／streamer；WAV回傳前亦已裁掉codec EOS證據。因此只在owned worker內暫時觀察該talker.generate的原始result.sequences，保留原回傳、例外與finally還原，不修改第三方檔。Transformers4.57.3原始sequence保留sampled EOS；metadata同時記EOS／cap，缺證據fail closed，cache只能採完整版本。SDK版本與shape須驗，不能以40.88秒推定原因。[Transformers版本文件](https://huggingface.co/docs/transformers/v4.57.3/en/internal/generation_utils)

採獨立版本cache、不刪舊資料，A／B可分開精確回退。原本沒有可辨識已提交final-answer句子的契約，因此C仍需單獨確認，不用未完成文字提早講話；不改聲線、擴GPU workers或以換backend掩蓋缺失。

### D35 補充：已量測的 CUDA attention profile（2026-10-08）

在 RTX3050Laptop、現有qwen-tts0.1.1／torch2.12.0+cu130／transformers4.57.3上，固定原model／reference、22字合成句、seed、512上限，eager暖無快取正式樣本12.891／12.655s；CPU intra-op1／4沒有實質收益，REJECT該調整。SDK與官方Transformers4.57.3確認支持SDPA，實際model／talker／code_predictor／tokenizer四層皆sdpa；正式樣本8.158／8.133s。EOS正常，數值運算差異使63token／4.96s音訊改為59token／4.64s，不能宣稱bitwise相同或已完成人耳語意驗收；速度仍不達SLO。只採CUDA worker的attn_implementation=sdpa，CPU保留eager；同一effective值進cache fingerprint，互不讀取不同attention快取。無新依賴、backend／聲線／生成上限／Core變動。先做profile/cache反例，再改worker並真機重驗。證據：docs/evidence/FIX-005-2026-10-07/benchmark-inference-results.json、benchmark-sdpa-results.json；https://huggingface.co/docs/transformers/v4.57.3/en/attention_interface 。


## D36 — RI-002 同一catalog的唯讀能力說明（2026-10-09）

沿用ToolDescriptor／ToolCatalog與authenticated GET /v1/runtime。新增optional typed metadata與closed availability reason codes；舊positional descriptor／bool readiness及舊HTTP keys保留。未知欄位為null，availability probe exception不洩漏文字，unknown不提供model工具且dispatch仍fail closed。每次capture只讀一次trusted readiness predicate，同一snapshot產生當round工具及inventory；不執行executor／CLI／network／plugin。此metadata只作描述，不替Policy／grant批准，也不改既有full/ask與風險批准語意。

candidate模型在既有on_messages_ready checkpoint中更新first system message末端唯一SIRO-owned capability block；initial與continuation沿同次capture，不累積messages／改user-tool配對或將metadata寫成記憶。legacy保留舊model schema與prompt行為。UI從同一runtime API顯示人可理解的能力與停用原因，純textContent；不新增endpoint／registry／worker／依賴／DB migration。回退只撤本卡source/UI metadata與相關契約，保留原dirty voice/session修復及使用者資料。

## D37 — FIX-002 browser failure 與可讀主頁的局部契約（2026-10-10）

先取得隔離A/B真Chromium修前證據。既有driver把被擋image/script/iframe與主frame共用_blocked_url，導致可讀主頁整頁失敗；錯誤回路又只保留exception名。採最小同卡切片：browser專用ScopeViolation subtype攜closed enum reason（invalid_url／main_origin_denied／redirect_denied），可信orchestrator映回原error=ScopeViolation並在既有failed observation JSON加reason。ToolProposal同一model_observation投影供journal/native／legacy continuation使用，非browser例外維持舊契約，未知reason及例外文字不得外送。不新增DB schema／錯誤registry／授權抽象。

主URL仍只接受有效HTTP/HTTPS且無userinfo，原raw arguments與hash不改；Markdown在candidate proposal前拒絕。主frame越界或其redirect仍拒絕並丟棄受影響page，observe也檢查pending主frame拒絕，避免click/read回報舊頁成功。非必要越界子資源仍abort，原origin集合不擴張；主頁可讀時回傳optional load_status=partial、reason=subresource_denied，不能宣稱完整讀取。BrowserObservation新欄位附於四個原positional欄位後；candidate session與legacy stateless wrapper使用相同標記。UI用固定中文原因＋textContent。

驗收包括零B server hits、直接／redirect／image／script／iframe／主frame導向與取消，以及pool明確新navigate(B)仍依法重建scope。遵照[Playwright Request](https://playwright.dev/python/docs/api/class-request)的is_navigation_request＋frame/main_frame分類與[Route](https://playwright.dev/python/docs/api/class-route)的fetch(max_redirects=0)；無法分類的navigation保守視為主frame。當次私人Bing事件根因仍UNKNOWN；合成修復與乾淨public query/provider閉環各自記錄，後者未PASS不得解除自動研究gate。

D37 teardown補充：同卡新增本機慢HTTP response的真Chromium負向驗收；close/cancel原先均有未處理SDK listener TargetClosedError，cleanup自身約0.06s、沒有程序殘留。只加driver-owned closing旗標：關閉開始後新route直接abort，原route的Playwright Error只在已進入teardown時消化，live-route Error仍傳遞。保留route scope到browser實際關閉，不能提前unroute造成存取空窗；不新增owner／workers／deadline或重試。這解決已確認teardown例外，不宣稱修復兩次公網4s cleanup timeout；該阻塞步驟仍UNKNOWN，其他兩次instrumented public close正常不足以抵銷失敗。

## D38 — FIX-008 完整text-diff path集合與有限支援格式（2026-10-10）

只修既有PatchVerifier的入場辨識；不改protection清單、執行器、API、依賴或OS sandbox。修前protected delete搭配普通修改會漏判；唯讀Git2.53 metadata另證實numstat只報rename目的，timestamp／quoted escape與非canonical alias也不能安全直接比對raw blacklist。因此不以numstat作完整授權證據。

支援完整成對unquoted --- a/path／+++ b/path與至少一個計數text hunk；add/delete可有一側/dev/null。可有一致diff --git及validated index/new-file/deleted-file metadata；content-bearing rename需一致Git old/new及rename from/to。收集舊／新路徑first-seen聯集，protected任一側在copy/apply/check之前拒絕。hunk按old/new行數消耗，內容中的---／+++不能變成新檔header。合法一般modify/add/delete及符合此格式的rename仍可走原temp-copy驗證。

此有限dialect輸入只用LF行尾並以LF結束；CR、NUL、超過原500000字元上限或缺最後separator拒絕。標準「No newline at end of file」hunk marker仍支援，這與patch本身的行separator不同。這些格式限制明示，不把以前可能只在git apply才失敗的輸入靜默視為成功。

不支持timestamp／quoted／whitespace／backslash／非canonical路徑、binary/copy/mode-only/rename-only；矛盾header、畸形或截斷hunk、未消耗內容都rejected_invalid_diff，不能只略過一部分繼續。path需安全相對POSIX、無absolute／.／..或.git component；不把rawdiff重寫後apply。既有rejected_policy_change／rejected_unappliable／failed_checks／passed與report必填欄位不改。這是窄幅格式限縮，非通用Git parser；真source不套候選、same-user copy不是不可信程式sandbox，OS隔離gate保留。

## D39 — FIX-009 版本化完整 release manifest 簽署（2026-10-10）

修前 HMAC 只簽 version:digest，schema bounds 可在未重簽情況下放寬。沿用既有 ReleaseManifest／ReleaseManager／CLI staging caller，採明確 string discriminator signing_format="siro-release-manifest-v1"。缺欄位或 null 的舊 artifact 可讀，但驗簽拒絕；未知 format／額外欄位拒絕，沒有舊 HMAC fallback、自動重簽或新 signing service。repo 唯一產生 caller 是合成測試 fixture；CLI 仍讀既有 JSON，不更改 launcher 或部署。

ReleaseManifest.signing_payload() 是固定 UTF-8 JSON：sort_keys=True、separators=(",", ":")、ensure_ascii=True、無末端 newline。payload 含完整 declared manifest 除 signature 本身，包含作為 domain／version 的 signing_format、version、source_sha256、min_schema、max_schema；以既有 HMAC-SHA256 驗證。schema bounds 保留正整數語意並嚴格拒絕 bool／string／float，要求 min<=max；stage 入口重驗 typed object，不能把 frozen 或未驗 model_copy 當安全校驗。已有效完整簽署的固定 bundle 才能進既有 staging；digest 仍核對實際 bundle。

保留既有 compatibility-first rejection/status 與 activation／backup／rollback 流程；不相容範圍先回 incompatible_schema，同樣零 staging/backup/healthcheck/active/LKG effects。其餘不合法簽署回 invalid_manifest，invalid wire fields 在既有 model parsing 拒絕。驗收須獨立固定 payload/HMAC vector、逐欄位 tamper、JSON order、legacy 拒絕、invalid range/type、未知 format/field、actual CLI temp caller 與 zero effects，不能共用 helper 自證一致。

舊 artifact 只能在可信 owner 維護流程重新檢查 bundle 與完整 manifest 後明確重簽；本卡不執行重簽既有 artifact，不讀 key／私人資料／live pointers。FIX-009 局部完成不能解除 launcher consume、人工批准、OS 隔離或最新資料保留式 rollback gate。精確回退本卡 dirty-baseline patch 前需停 promotion；舊驗簽漏洞不作安全 fallback。

## D40 — FIX-007 approved package identity 與 owned snapshot（2026-10-10）

沿用 SkillManifest v1、InstalledSkill、SQLiteSkillRegistry、SkillDispatcher、WorkerSupervisor；不新增 registry/installer/resolver/runtime catalog。原 manifest_hash 欄位以明確 siro-skill-package-v1:<sha256> 表示完整內容身分。SHA256 使用 domain separator 與逐檔相對 UTF-8 path length/path、byte length/bytes、executable permission bits，排序固定；包括 manifest、schema、所有 source/module、資料與 dependency metadata。不同 package root 即使內容相同也不共享批准，root 另外綁 existing path_ref。

支援 canonical 本機 package root，拒絕 symlink、hardlink、非regular file、schema path escape、entrypoint 缺 source；已知 bytecode/native 副檔名不作支援的 package executable。只略過普通 __pycache__ transient directory，snapshot 不複製該 cache，避免舊 bytecode 換碼。讀檔使用 no-follow directory/file handles，捕捉同一份 bytes；最多512 files／1024 entries／32層、每檔4MiB／總16MiB，超限拒絕；不將這些資源設定當效能SLO。

install 只存 caller 與實際 package 完整一致的固定身分，預設 disabled；enabled=True 保留既有可信 owner API語意，不替生成碼批准。set_enabled=True 要重驗 current digest/root，不改舊批准來迎合換碼。舊64hex manifest-only rows原樣保留，is_enabled fail closed，enable明確提示需要重新驗證／批准；不 migration/auto upgrade/清資料。可信 owner 若重裝新的已驗 package，仍由既有明確 install/enable control flow處理。

Dispatcher 以 stored enabled id/version/hash/root 核對 caller，再在非event-loop thread捕捉與比對實際完整內容。用同一批已驗 bytes 建私有 owned temporary snapshot，worker只收到該snapshot，原 package 之後改動不能變成執行另一份內容；準備期間來源變更要拒絕，handoff後來源變更時可以執行已批准 frozen bytes，不宣稱執行變更來源。對 typed InstalledSkill 的 manifest/schema/hash/root 也比較，不能信任caller偽造 hash。handoff前重查 enabled identity以支援撤銷。失敗/取消/完成清理 owned snapshot；準備thread在取消時join並清理，不留下無owner副本。

原bwrap mounts／network denied／乾淨env／worker CPU/memory/output/concurrency/timeout/cancel保持。snapshot檔只讀並保留已簽 executable bits；不把同UID host視為被此copy隔離，也不簽整個可信Python/venv/OS環境或解決所有import collision。任意敵意生成技能仍需獨立sandbox/review/explicit enable gates，沒有本卡runtime接入或部署。先RED反例、再三個現有production檔局部修改，保留精確dirty baseline回退；回退前停技能dispatch，不把舊身份漏洞作fallback。

D40 snapshot admission 補充：既有 Dispatcher 自己持有最多8個 active snapshot/preparation slots，包含排隊於 worker semaphore 的 job，完成清理後才釋放；候位取消不建立 snapshot。這是新增owned副本的局部資源上限（最多128MiB package bytes on disk），不是新scheduler/background owner，也不改原worker per-skill concurrency。總體CPU/RAM/IO SLO未量測。

D40 concurrency identity 補充：原 WorkerSupervisor semaphore 也以 id/version/package hash 作key，避免同id/version明確重新批准後仍沿用舊concurrency上限。固定未變 package的原行為保留；cache retention未量測，不在本卡另造state manager。

## D41 — FIX-006 有界唯讀故障事實；理解品質仍獨立驗收（2026-10-10）

同配置provider的合成paired ablation先完成：既有greeting/記憶能力已正常，不再重寫Core規則；短提示＋自己的HTTPStatusError使單一自身故障案例從一般API checklist變成兩句已知/未知。廣泛長指引沒有稳定收益、語音更正仍ProviderOutputTruncated、未知效果重做語意未通過，因此不合併整段長prompt、不換backend/加token/自動重试，不把局部事實改善當整體理解PASS。

只在既有agent run repository加readonly projection、IntegratedCompanion composition加一段fixed fact。於candidate＋原session_restore_enabled＋非direct command分支、supersede之後且新run start之前取樣；只查同owned SQLite store/session的最新agent run，LEFT JOIN journal，先選最新再驗條件。較新的completed/active/legacy/不同privacy行必須抑制更舊failed行。只接受candidate journal v1、terminal/interrupted與failed/cancelled同時成立、當前privacy精確相同、canonical UUID、UTC可解析updated_at、0..900秒新鮮度。無owner欄位的現有single-owner store假設不擴為多tenant。

只有source_run_id/state/error_class/tool_dispatch_recorded/root_cause=UNKNOWN五欄；error用closed machine-name集合，未知/null/raw診斷全映UNKNOWN；派送紀錄來自EXISTS(dispatched=1)，不是執行/成功證據。SQL不選goal、messages、arguments、observations、backend或agent_steps，不增加DB欄/endpoint/cache/服務，不恢復failed user/assistant/tool intents。各自最多一筆，固定內容上限1024 UTF-8 bytes；原completed history/summary/privacy/budget/native pairing/權限/取消仍保留。

事實旁僅採短條件指引：追問自身錯誤時用短句陳述已知未知、承接更正，不給憑證教學或猜原因；有派送需先回讀結果，不能由metadata自動重做。這是模型提示而非新的授權guard，未知效果語意仍要真provider验收。原過度保證每則reply能念完/Live2D已連線，改為存在整合介面；readiness/complete playback需實際觀測。沒有新readiness服務，也不聲稱現在已取得ACK。精確source rollback不動DB/既有卡；FIX-006最多PARTIAL，全部語意驗收未PASS前不解除product gate。

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

## D44 — RI-004 明確 owner 的待審 Markdown 清單技能（2026-10-10）

只接 `text.checklist.parse`（明示 aliases `siro.text.checklist`、`skill.siro.text.checklist`）的固定 stdlib 模板：owner 提供文字，解析有界 Markdown checkboxes，無檔案／network／process／credential／device權限。不是一般自然語言缺能力偵測或LLM程式生成，不能宣稱「computer.execute做不到」；review顯示它作為既有通用替代，不執行。

唯一新 services/tools/skill_candidates.py `SkillCandidatePreparer(catalog)`：`prepare(capability)` 先 capture 原ToolCatalog完整inventory，包括 unavailable/unknown/hidden；exact或明示alias命中即existing_available/existing_unavailable/existing_unknown，不建立workspace、不跑verifier。沒有同名typed能力才用固定模板，unsupported要求固定回覆。沒有新catalog／registry／executor，無fake successful traces或procedural存檔。

固定package沿用SkillManifest v1／capture_skill完整digest，精確四檔manifest/input/output/plugin；permission空、observe/network denied/read_only/concurrency1/process cancel。固定input只允許text，UTF-8≤16KiB、≤256lines；最多128tasks，每task≤256chars；output pending/completed字串arrays及counts。支援`-/*/+ [ ]/[x]/[X]`非空文字，跳過以三backticks／tilde開關的fenced區段，普通行忽略；不是完整Markdown parser。未支援外部deps／任意code/schema/profile/paths。JSON/provenance/review不放進hash package，以免自引用。

每次owned disposable workspace內capture exact bytes，再在獨立baseline tests建立fixed trusted unittest，PatchProposal只新增src/plugin.py，bytes與captured plugin相同；呼叫RI-003唯一已驗verify_isolated_patch，不傳真SIRO root、不host import。report須proposalID/changed_paths/workspace_removed綁同一proposal，package/fullsource/test/proposal digests和source provenance一併外部回傳。review payload包含四檔文字可匯出；無host root／私人輸入／policy/env資料。candidate tests仍不給authority，status awaiting_review≠security approval。

每個preparer只一個active task，busy直接拒絕，無queue／background loop／永久artifact／DB。準備/清理IO offloop、重複cancel join owned IO／process，成功後late cancel不回review；cleanup failure typed。cancel/close皆清此owner，不掃其他程序或私有資料。API token/origin gate、tools switch、legacy缺service拒絕；關閉tools需取消activeprepare、shutdown close；無auto retry／reconnect重送。UI明確準備/取消/匯出review，顯示未啟用與尚需人工審查，不提供approve或enablebutton；HTML以textContent呈現。

Gateway composition只把現有candidate catalog注入一個preparer，HTTP `POST /v1/skills/candidates` JSON僅capability，`POST /v1/skills/candidates/cancel`取消owned單job；runtime snapshot加當前是否可準備／busy的純metadata。這是明確owner操作，不新增modeltool或動到full autoapproval。**零registry install/set_enabled/dispatch**，既有installed技能不變；僅查typedcatalog，未聲稱已遍歷installed registry。真正security review／approval／enabled worker隔離／catalog接線仍RI-004 remainder gate，RI-005發布 gate不變。

先新增RED契約/actualOS/HTTP/UI反例，再分service、thinGateway、UI各檔實作；保存exact dirty baseline，驗counter零工具/model/registry、existing unavailable不繞、projection binding、unsupported/cancel/busy/shutdown、full回歸与source精確回退。沒有8026restart／private chats/DB/WAV/key／正式部署。
## D45 — FIX-011 trusted worker owned lifecycle repair（2026-10-11）

RI-004 actual worker接入前，合成probe確認existing WorkerSupervisor stdout/stderr洪水使1.5s逾時無法返回（外層5s才終止），cancel during spawn/stdin留owned bwrap/worker，fork child可setsid離開PGID。這是既有trusted-local API的IMPLEMENTATION_BUG/TEST_GAP，不是已證實私人產品regression。先修最小parent lifecycle，不把trusted worker升格untrusted認證。

將既有bounded argv process owner移到下層adapter，services.tools.execution保留原API/errors/context及私有signal測試相容wrapper；不是再造executor。WorkerSupervisor沿用manifest/schema/concurrency/registry與舊trusted source/runtime mounts，只以同一owned helper執行，移除bwrap --new-session、加入PIDnamespace與die-with-parent，使worker descendants結束隨owned namespace。CPU/stdlib/seccomp正式skillprofile為後續獨立slice，本卡不把trusted允許fork/exec當safe generated boundary。

輸入不再寫未受控stdin：64KiB有界JSON，以owned offloop temporary read-only request.json獨立mount到/request.json；skill_worker從明確trusted env選取此檔，保留舊stdin入口但read有界。parent preparation/spawn/collect/TERM-KILL/cleanup均在取消owner內；單次及重複cancel需join，latecancel不能成功，cleanupfailure typed且不洗掉主語意。total rawstdout/stderr有界drain，不因先waitprocess造成pipe堵塞。無default grants/policy／registry／DB／model/UI／8026改動。

FIX-011驗收後才能推RI-004 strict single-process worker；新的seccomp/mount profile不fallback trusted path。Task歷史不重編。

## D46 — RI-004 固定 stdlib single-process worker（2026-10-11）

FIX-011已1,151PASS與exact5回退驗收。下一窄切片只驗真正worker，不install/enable或改產品catalog。`WorkerSupervisor(profile="python-stdlib-single")` 顯式選用；預設trusted-local保持D45相容，未知profile拒絕。strict failure無trusted/host fallback。

重用RI-003最小runtime mounts／bwrap argv與不可逆restrictions到lower adapters，原patch service/runner保留thin delegates與private test seams；不得复制第二套sandbox或反向import service。Linux x86_64／systemCPython3.14 stdlib限定；package精確manifest.json/input.json/output.json/plugin.py、固定python:plugin:run、permissions空／riskobserve／read_only／networkdenied／concurrency1／processcancel／compensationnone。limits memory16..256MiB、CPU1..5s、output≤131072bytes、timeout≤10000ms；其他profile/依賴/權限拒絕。

trusted runner在candidate之外，先載trusted stdlib/設定no_new_privs、hard RLIMIT與same seccomp deny，然後才import plugin；limits從readonly trusted config取得。hard CPU等於soft，不可提高。owned offloop捕捉完整package並核對suppliedidentity，用同批bytes寫readonly/canonical candidate；readonly boundedrequest置trusted目录外於packageidentity。無venv、whole/usr、production source、home/private/socket mounts；8MiB scratch、root/proc/devreadonly，拒socket/fork/exec/session/IPC/keyring及limit提升。仍不聲稱aggregatekernelRAM/cgroup/任意生成碼已安全。

使用FIX-011唯一process owner；先固定--probe確認restrictions可用，probe/execution共享manifestcollectdeadline，任何unsupported不import候選、不降級。strict prepare/spawn/run/cleanup repeatedcancel join；latecancel不成功、cleanupfailure保留。Dispatcher registry批准/frozenbytes仍沿原流程，直接supervisor僅為trusted developer verification入口、不提供新modelauthority。

先REDAPI/profile/staticidentity/OS反例，再最小實作。真OS驗固定D44parser輸入→輸出與synthetichostcanary/env/net/fork/exec/session/limits/IPC/outputflood/CPU/AS/scratch；實際PID與取消/offloopcleanup同驗。獨立review、完整回歸、exactsource回退後才解除此profile接入門檻；產品serverheldreview/明確批准/install-enable-revoke仍下一切片。

## D47 — RI-004 固定技能的明確 owner 安裝與啟用（2026-10-11）

D46 strict single-process worker 已 VERIFIED；本卡只把 D44 固定 checklist 模板接進既有 registry/catalog/orchestrator/dispatcher。不是任意生成、依賴安裝、模型自行批准或發布。沿現有 skills table，不改 Core、policy/grants/schema、模型/聲線、release 或預設 trusted worker。

Server-held review 只有一份，15分鐘 monotonic TTL、runtime owner epoch、完整四檔/來源/tests/proposal/evidence 綁定；客戶端只傳 review_id/package_hash，不接受檔案、schema/path 或自報 PASS。實際 owner 審閱後按安裝，只新增不存在的同版 registry，初始 disabled；另一明確按鈕 enable。重複/衝突同版不得覆寫 hash/path/state。既有 install UPSERT 保留相容；新增 insert-if-absent 与 expected-identity CAS，撤銷即使檔案毀損也可 disabled。

無 dormant descriptor 阻擋第一次準備。精確批准/managed package 才 additive catalog registration，重複名稱拒絕、deepcopy/capture穩定；disabled/revoked descriptor 留 unavailable。實際呼叫沿原 tool proposal/approval/authorized ExecutionContext → strict dispatcher，沒有直接執行 endpoint 或第二套 executor registry。可信固定 parser 對 text 與 output 的 nested/counts bounds 做局部檢查。

Control single owner；IO/SQLite mutation cancellation 必須 join，再回應；tools-off/revoke/close 先阻 admission，再取消並等待所有 active/queued jobs。期限與取消 token 傳遞，late成功不得復活。startup只恢復固定 managed path 的完整 exact template/receipt/registry identity；未知 row/receipt/path fail closed，無自動製作或修復。回退先停用/回收 owned jobs，source exact4既有 +新檔 reversible；不倒回私人DB/最新資料。先 contracts/RED、真臨時SQLite與OS/HTTP/UI、獨立review/full regression/source rollback，再標驗收。


## D48 — RI-005 / FIX-012 code rollback 保留最新資料（2026-10-11）

Original T32 rollback 將code pointer與whole DB restore綁一起，原測試明確要求after-release寫入消失；這是ORIGINAL_DESIGN_ERROR，不強迫實作繼續服從已被新資料保留需求否定的契約。D39完整簽署維持，僅撤其保留舊資料回退語意。最小更正：ReleaseManager.rollback只回code pointer，永不restore/replace/initialize/migrate DB；已有獨立siro restore保留明確資料還原，不在本卡執行或修改。

New stage 將既有完整ReleaseManifest保存於root/manifests/version.json sidecar，位於signed bundle之外，先於active pointer保存。版本已存在則拒覆寫，保留原可信rollback target；沒有舊artifact自動re-sign/信任升級。Rollback只接受strict semver LKG、完整sidecar signature與exact version/source digest，拒symlink/aliased receipt與target source；未知/壞receipt拒絕，從不按LKG的database_backup自動讀取或還原資料。

有database時，僅mode=ro SQLite查schema_migrations的嚴格遞增完整prefix（最多4096），不能用caller current_schema猜live DB版本；missing/corrupt/unknown metadata固定schema_unknown，future超目前manager支援或target min/max外為incompatible_schema。沒有database則保留既有trusted current_schema相容檢查。這是pointer元件的snapshot gate，不是假造stopped-writer reservation，也不证明舊binary能啟動/loader checksums/實際migration/health。Launcher consume version、single-writer owner、shutdown/start/readiness與latest-data rollback integration仍BLOCKED；不啟動/部署現用服務。

先定契約與RED cases，再修改唯一production releases.py＋原錯誤fixture＋一新test。保留latest conversation/memory/ledger/WAL與所有D47 source，不新增updateframework、schema engine、scheduler、lockservice或policy。source-only回退不能用來恢復旧危險data-restore行為；實際operator不得呼叫舊rollback，資料一律保留。

D48 identity supplement before production: actual staging bytes after trusted healthcheck must still match original complete manifest before capturing immutable sidecar; test mutating app.txt must first reject. This repairs the same persisted rollback-authority binding locally, not a new check runner.

## D49 — FIX-013 還原先驗證副本，再取代資料（2026-10-12）

D48 真合成 probe 已證 `SQLiteStore._restore_sync` 先 backup(live) 再 checksum/migration，失敗仍遺失 latest rows；這是 IMPLEMENTATION_BUG/BAD_INTERFACE/TEST_GAP，原設計要求資料一致，不另造 architecture correction。最小修補限既有 SQLiteStore：mode=ro 來源→owned temp candidate→原遷移與完整性驗證→SQLite backup promotion。Shared apply_migrations/SQL、ReleaseManager D48、CLI/ZIP API、Core/權限/模型/UI/launcher/依賴不改。

Restore-local applied-version validation 拒絕 unknown future/gaps/type-invalid metadata；不因既有 apply_migrations 忽略未知版本而擴張全球 migration abstraction。以原 per-store writer lock 加 owned offloop join，取消可停止未完成 copy、完成 commit 後只能回報取消並保有收尾，不偽造撤銷結果。Cleanup 拒絕要可見且不得洗掉原 migration error。先 RED 再實作，保存 266-file dirty baseline、真 SQLite 與受影響回歸、獨立 review、exact source 回退；不讀 private DB/WAV/chat/keys、不重啟8026、不發布。

D49 independent-review supplement：新 shield 等待方式在 Python3.14 late cancel/primary error race 會額外記錄 shielded-future error。分類同卡 MINOR_FIX/LOW/TEST_GAP，先已有真 SQLite case 加 loop handler 作 1 FAIL/1 PASS RED；只改 `asyncio.wait((job,))` 等待 primitive 和移除不用的 error catch，保有原 lock/join/primary-result，不新增 abstraction 或吞 error。重新凍結實作、全回歸與 source-only 回退；初次全套為 pre-supplement 歷史結果，不當 final。

## D50 — RI-005 單一受管資料 owner（2026-10-12）

D49局部restore已1,483PASS，下一窄slice沿原singlewriter requirement，不另造updater或schemaengine。實際gateway main在lifespan前initialize DB；CLI demo/backup也可寫。per-store asyncio.Lock/PIDfile不足跨程序maintenance gate。加一個lower OS fd context，在真正Gateway/CLI composition入口保有nonblocking exclusive flock；Core/SQLite/ReleaseManager不引用OSdriver、不重入鎖，existingAPI與原body保留。

D49負向驗收要求壞backup不建立target directory；data-parent sidecar先mkdir會regress，所以採固定帳戶state namespace＋canonical DB SHA256 key，明示空coord artifacts，永不unlink lock。不能用TMPDIR/XDG/HOME env作權威，systemd PrivateTmp與shellnamespace可能不同。沒有PID資料/新lease服務/權限或授權變更。Linux sameUID/localFS只證受管process互斥，不證所有SQLiteconnection唯一或舊版/external已停；first adoption需另有真stopped-old-owner證據，本輪不重啟現用服務。

Busy failclosed且zero DB/pointer/config/provider effects；同步外層context包asyncio.run讓default executor cancellation/join與D49cleanup完成才close。Normal close而不LOCK_UN，fork持fd保持busy；CLOEXEC防helper exec延長lease，owner不跨launcher exec。先actualOS/caller RED，最後独立audit/fullregression/exactsource回退更新status；nextactual approved launcher/version/readiness仍獨立gate，不以lock綠燈冒充部署。

D50 pre-implementation correction：獨立actual prototype已否定「asyncio.run退出一定完整join」；Python3.14 Runner repeatedSIGINT及其300s timeout可使outerlease先close、oldIO晚寫覆蓋下一owner。不能僅文件縮範圍後宣稱stopped gate。最小仍在同owner resource：顯式factory為managedloops配置其stdlibdefaultpools，退出先不可被mainSIGINT打斷的owned jointhread完成各poolshutdown，main repeatedinterrupt保fd并最後傳原error/interrupt。Local runtime resource無globalregistry/新executorservice；加入必要true mapped CLI反例，Gatewayinit與uvicorn同owner不同ownedloop都覆蓋。真正job未join不釋放，join失敗failclosed直到process exit；不修改D49SQLite或legacyCore。

D50 / FIX-014 verification correction：原singlewriter設計仍有效，這是IMPLEMENTATION_BUG/MISSING_INTEGRATION/BAD_INTERFACE/TEST_GAP。新CLI owner只保source而backup實際replace explicitdestination；真child持destination lease仍被覆蓋、inode變動、oldconnection/freshread不一致，REQUIRED_FIX/HIGH。本卡不以局部綠燈放行。最小增加同resource的optionalwrite_target（backupdest／restoreconfig），有序去重key、partialfailure清理、同一IOjoin後closeall；不建lockmanager/registry或改低層backup/restore。另actualselfZIP backup能把siro.db改成ZIP，與config自覆寫角色一併先RED拒絕。Source-onlyrollback保全部資料與舊ownerstate，不重新允許危險caller；不增加ARCHITECTURE_CORRECTION，原Runtime Evolution設計沒有被否定。

D50 / FIX-014 final temporary-write correction：獨立actual ZIP probe證實fixed destination.tmp/config.tmp可刪除readonly input，或靜態alias使final target成selfloop；root新增8actual RED（temporary-target-before-all.log），包含自身DB與正在受管foreignDB暫存alias。此為同一confirmed missing-write-scope/collision根因，不新建RT或重設operations。原context僅增加optional temporary_write_target，最多source/explicit/fixed-temp三份canonical FD，仍一次有序去重partialcleanup與joint ownedIOjoin。只有ZIP caller依既有with_suffix(suffix+".tmp")捕捉fixedtemp；raw SQLite exclusive mkstemp不新增key。Temporary不得canonical等於sourceDB/readonly settings或archive/explicitfinal；正常明確distinctpaths保持。兩個write target全部持有到actualIOjoined；未知join仍保全部FD，不能nested提早釋放。Final三key/alias/repeatedSIGINT與全套必須重驗；歷史兩key綠燈不代表完成。

## D51 — FIX-015 backup cancellation owns actual IO and staging cleanup（2026-10-13）

Confirmed unchangedbackup_to bareto_thread exitswriterlock/ZIP TemporaryDirectory beforethreadjoined; trueCLI1/3SIGINT leavesrecreatedstaging/DB/WAL/SHM. REQUIRED_FIX/MEDIUM，IMPLEMENTATION_BUG/MISSING_INTEGRATION/TEST_GAP；不是D50OSownerfailure。只existingSQLiteStore backup_to/_backup_sync，新18focusedtests＋syntheticactualsignalprobe；operations、D49restorebody/SQL、D50adapter/CLI/Gateway、Core/policy/identity/providers/voice/UI/launcher/deps全保留。

Backup async同D49retainedjob/asyncio.wait/result：writerlock持到actualoffloopwork/explicitconnectionsclosed/cleanupresolved，repeatedtaskcancel不能提前放棄；primarybackupfailure先於pendingcallerCancellation，無unobservedduplicateerror。Backup-local ThreadEvent在knowncancel時set；private _backup_sync新增optionalcancelled=None，directoldsingleargumentcaller/正常publicAPI保留。Beforemkdir、nonDONEcopyprogress、beforefinalpublication檢查cancel。Copy的SQLITE_DONE只代表ownedtmpcopycommit；finalos.replace前仍可拒，不破壞prioroutput。已finalpublished後cancel不得假稱回滾，需readback不自動retry。

Exactownedsource/target都必須嘗試explicitclose，close/unlink失敗保留原typedprimaryerror並附type-onlynote；無primary的cleanupfailure必須可見，不吞/假cleanup成功。Finaloutput只在copy/integrity/connectionclose成功後原os.replace發布；不改backupformat/一致性檢查、不新增manager/executorservice/schemaengine。ZIPcontext由既有operations在backupresolved後正常清理；若hardRunnerprocessSIGINT打斷coroutine，synccancelguard與D50ownedpooljoin仍須真實驗到staging無late重建/無orphan，不能只用mock或套D49結論。

Tests distinguishdirect1/3cancel/writerqueue、actualmulti-pageSQLite(nonDONE/DONEtmp)、rawlatepublishedcommit、typedcopy/close/unlinkrefusalcontrols，和trueCLI1/3SIGINT。Fences/cleanup失敗/未知OSIO不可標DONE或重送；不做全SQLite連線掃蕩。不操作live8026/privateDB/chat/WAV/key/models/GPU或正式deploy。Exactsource-only rollback保latestdata；cap/backupretention/powerloss/oldunmanagedowner/真正signedlauncher版本/readiness/批准handoff門檻仍保留。

D51 pre-implementation process-cancellation refinement：真SIGINT審查顯示Runner.close會cancel_all_tasks，ownedto_thread Task也可能被全局cancel而誤判thread已完成。Backup-local retainedjob用原loopdefault executor的Future（run_in_executor＋copy_context.run保持to_thread context傳播），asyncio.wait不把caller取消傳到future，也不是all_tasks成員；同一ThreadEvent跨已知cancel到syncguard。原D50ownedpools/owner不改、不新建executor或manager。Actualprocess3SIGINT可打斷Runner.close，syncfences＋原ownerjoin仍需probe證實工作完成/staging清除/無遺留；不能把Future選擇當作證據或改D49restore。

D51 verification correction（local caller only）：firstSQLite-onlyguard已19cases與真8casesdata/stagingPASS，但所有3SIGINT進Runner.close的cases有Taskdestroyedpending警告。MINOR_FIX/LOW，REGRESSION/MISSING_INTEGRATION/TEST_GAP，不是新資料loss；不能遮warnings。修正範圍最小允許CLI既有_backup wrapper在mainthread的單次backup operation臨時把SIGINT轉成該ownedcoroutine.cancel，反覆signal仍等backup IO/cleanup；finally恢復原handler。Signal導致的CancelledError才轉原KeyboardInterrupt/130；普通callerCancelledError/primarytypederror保留，其他commands/Gateway/OSgrant/全局永久signalpolicy不變。新增5focusedcallerrestoration/primaryerror/threadfallbackcases＋更新真8SIGINTprobe。無新的Runner/manager/framework；sourcebackup與CLIbeforebytes捕捉，exact4sourceonlyrollback必須驗。

D51 actual-selector correction：true signal初版8cases與既有D50backup init2casesRED，customhandler缺stdlibRunner對blockedselector的threadsafewakeup。ConfirmedIMPLEMENTATION_BUG/REGRESSION/TEST_GAP；只補同loop.call_soon_threadsafe(noop)，不改D50測試/owner/shutdown、不另建Runner。CLIlate-signal/body-success補第6case；actual8＋原全部caller＋全套重新綁final4source，舊controlled24PASS不算finalacceptance。

## D52 — RI-005 signed source launcher限定接入（2026-10-13）

Current launcher imports installed working source and health.ready has no executed version. Reuse ReleaseManager complete signed receipt and actual readonly schema through one public read-only resolve_launch_target; no second updater/signature format/permission grant. Explicit operator opt-in SIRO_RELEASE_ROOT uses existing signing key env only in parent. Fresh -I/-B child imports selected package/Core/Gateway and validates origins; signing key omitted from child env. Original cwd/data/resources kept, absolute data captured; signed code never self-builds/provisions or writes bytecode. No fallback to installed source when a selected package fails.

New immutable VerifiedRelease is passed explicitly at composition, not an env version label. Actual origin and current data schema rechecked under original D50 owner before startup; same-schema source launch only, required migration refuses instead of implicitly altering data. Existing rollback schema SQL fact locally extracted for reuse, old retention semantics remain. Ready publishes version/digest only after actual startup; default health shape unchanged. First-adoption unknown writer absence, maintenance→exec CLOEXEC gap, post-verification sameUID package mutation and formal approval/deploy stay blocked; not fixed by a healthy pointer or advisory SQLite lock. True synthetic two-version source/HTTP/latest-data rollback and negative gate evidence required; no real service/key/data/model access.
