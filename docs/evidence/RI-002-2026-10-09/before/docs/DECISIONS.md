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
