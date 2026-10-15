BEGIN TRANSACTION;
CREATE TABLE action_attempts (
    attempt_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    executor_id TEXT NOT NULL,
    lease_epoch INTEGER NOT NULL CHECK (lease_epoch >= 0),
    state TEXT NOT NULL,
    outcome_json TEXT CHECK (outcome_json IS NULL OR json_valid(outcome_json))
);
CREATE TABLE actions (
    action_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    args_hash TEXT NOT NULL,
    grant_id TEXT REFERENCES grants(grant_id),
    deadline TEXT
);
CREATE TABLE affect_states (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    valence REAL NOT NULL CHECK (valence >= -1 AND valence <= 1),
    arousal REAL NOT NULL CHECK (arousal >= 0 AND arousal <= 1),
    intensity REAL NOT NULL CHECK (intensity >= 0 AND intensity <= 1),
    reason TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (identity_id, session_id)
);
CREATE TABLE agent_runs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    state TEXT NOT NULL,
    step_count INTEGER NOT NULL DEFAULT 0,
    max_steps INTEGER NOT NULL,
    current_proposal_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE agent_steps (
    run_id TEXT NOT NULL REFERENCES agent_runs(run_id),
    step_index INTEGER NOT NULL,
    kind TEXT NOT NULL,
    capability TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, step_index)
);
CREATE TABLE appraisal_records (
    appraisal_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    appraisal_json TEXT NOT NULL CHECK (json_valid(appraisal_json)),
    occurred_at TEXT NOT NULL
);
CREATE TABLE audit (
    audit_id TEXT PRIMARY KEY,
    action_id TEXT REFERENCES actions(action_id),
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE TABLE compute_attempts (
    attempt_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES compute_jobs(job_id),
    lease_epoch INTEGER NOT NULL CHECK (lease_epoch >= 0),
    state TEXT NOT NULL,
    output_ref TEXT
);
CREATE TABLE compute_jobs (
    job_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    privacy TEXT NOT NULL,
    deadline TEXT,
    input_ref TEXT,
    selected_node TEXT REFERENCES compute_nodes(node_id)
);
CREATE TABLE compute_nodes (
    node_id TEXT PRIMARY KEY,
    capabilities_json TEXT NOT NULL CHECK (json_valid(capabilities_json)),
    version TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    trust_scope TEXT NOT NULL
);
CREATE TABLE consolidation_outputs (
    candidate_key TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES consolidation_runs(run_id),
    memory_id TEXT NOT NULL UNIQUE REFERENCES memories(memory_id),
    created_at TEXT NOT NULL
);
CREATE TABLE consolidation_runs (
    run_id TEXT PRIMARY KEY,
    source_cursor_start TEXT,
    source_cursor_end TEXT,
    status TEXT NOT NULL,
    checkpoint TEXT,
    model_ref TEXT
, identity_id TEXT REFERENCES identities(identity_id), run_key TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE conversations (
    session_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE coping_decisions (
    appraisal_id TEXT PRIMARY KEY REFERENCES appraisal_records(appraisal_id),
    strategy TEXT NOT NULL,
    urgency REAL NOT NULL CHECK (urgency >= 0 AND urgency <= 1),
    reason TEXT NOT NULL
);
CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    adapter_id TEXT NOT NULL,
    descriptor_json TEXT NOT NULL CHECK (json_valid(descriptor_json)),
    availability TEXT NOT NULL,
    last_seen TEXT
);
CREATE TABLE drive_states (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    safety REAL NOT NULL CHECK (safety >= 0 AND safety <= 1),
    connection REAL NOT NULL CHECK (connection >= 0 AND connection <= 1),
    competence REAL NOT NULL CHECK (competence >= 0 AND competence <= 1),
    curiosity REAL NOT NULL CHECK (curiosity >= 0 AND curiosity <= 1),
    autonomy REAL NOT NULL CHECK (autonomy >= 0 AND autonomy <= 1),
    rest REAL NOT NULL CHECK (rest >= 0 AND rest <= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (identity_id, session_id)
);
CREATE TABLE emotion_activations (
    appraisal_id TEXT NOT NULL REFERENCES appraisal_records(appraisal_id),
    emotion TEXT NOT NULL,
    intensity REAL NOT NULL CHECK (intensity >= 0 AND intensity <= 1),
    reason TEXT NOT NULL,
    PRIMARY KEY (appraisal_id, emotion)
);
CREATE TABLE emotion_episodes (
    episode_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    valence REAL NOT NULL CHECK (valence >= -1 AND valence <= 1),
    arousal REAL NOT NULL CHECK (arousal >= 0 AND arousal <= 1),
    intensity REAL NOT NULL CHECK (intensity >= 0 AND intensity <= 1),
    reason TEXT NOT NULL,
    source_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE entity_edges (
    from_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    to_id TEXT NOT NULL,
    UNIQUE (from_id, relation, to_id)
);
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    envelope_json TEXT NOT NULL CHECK (json_valid(envelope_json)),
    received_at TEXT NOT NULL,
    trace_id TEXT NOT NULL
);
CREATE TABLE goals (
    goal_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    next_step TEXT,
    deadline TEXT,
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    revision INTEGER NOT NULL CHECK (revision >= 1)
, task_json TEXT
CHECK (task_json IS NULL OR json_valid(task_json)));
INSERT INTO "goals" VALUES('synthetic-legacy-goal','waiting_external','preserve-legacy-next-step','2026-10-16T00:00:00+00:00','{"steps_used":2,"max_steps":8,"cost_used":0,"max_cost":0}',3,NULL);
INSERT INTO "goals" VALUES('16c10d93-d478-4f02-8069-c064673611b4','completed',NULL,'2026-10-15T18:12:37.051947+00:00','{"steps_used":1,"max_steps":8,"cost_used":0.0,"max_cost":0.0}',7,'{"profile":"document-checklist-v1","owner_session_id":"synthetic-owner","workspace":"/tmp/g57r-vju6ziis/synthetic-fixture/workspace","paths":["checklist.md"],"approved_at":"2026-10-14T18:12:37.055359Z","intent_path":null,"pause_reason":null,"observations":[{"path":"checklist.md","status":"completed","sha256":"136af48b26f5a325fa877ee78a78b6b84340a02d2cb19824887426a0997ea4c8","read_at":"2026-10-14T18:12:37.065532Z","matches":[{"line":2,"text":"- [ ] retain newest task evidence"},{"line":3,"text":"TODO: preserve additive schema14"},{"line":4,"text":"FIXME: never restore an old database"}],"truncated":false,"error":null}]}');
CREATE TABLE grants (
    grant_id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    capability TEXT NOT NULL,
    scope_json TEXT NOT NULL CHECK (json_valid(scope_json)),
    args_hash TEXT,
    expires_at TEXT,
    uses_remaining INTEGER,
    revoked_at TEXT
);
CREATE TABLE identities (
    identity_id TEXT PRIMARY KEY,
    core_json TEXT NOT NULL CHECK (json_valid(core_json)),
    core_version INTEGER NOT NULL CHECK (core_version >= 1),
    created_at TEXT NOT NULL
);
CREATE TABLE identity_revisions (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    patch_json TEXT NOT NULL CHECK (json_valid(patch_json)),
    source_ids TEXT NOT NULL CHECK (json_valid(source_ids)),
    created_at TEXT NOT NULL,
    PRIMARY KEY (identity_id, revision)
);
CREATE TABLE inbox (
    consumer_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (consumer_id, event_id)
);
CREATE TABLE memories (
    memory_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    valid_from TEXT,
    valid_to TEXT,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    deleted_at TEXT
, person_id TEXT NOT NULL DEFAULT 'owner', supersedes_memory_id TEXT REFERENCES memories(memory_id));
CREATE TABLE memory_derivations (
    parent_memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    child_memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    CHECK (parent_memory_id <> child_memory_id),
    PRIMARY KEY (parent_memory_id, child_memory_id, revision)
);
PRAGMA writable_schema=ON;
INSERT INTO sqlite_master(type,name,tbl_name,rootpage,sql)VALUES('table','memory_fts','memory_fts',0,'CREATE VIRTUAL TABLE memory_fts USING fts5(
    memory_id UNINDEXED,
    identity_id UNINDEXED,
    person_id UNINDEXED,
    text,
    tokenize = ''unicode61''
)');
CREATE TABLE 'memory_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
INSERT INTO "memory_fts_config" VALUES('version',4);
CREATE TABLE 'memory_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2, c3);
CREATE TABLE 'memory_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
INSERT INTO "memory_fts_data" VALUES(1,X'');
INSERT INTO "memory_fts_data" VALUES(10,X'00000000000000');
CREATE TABLE 'memory_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
CREATE TABLE 'memory_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
CREATE TABLE memory_revisions (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    kind TEXT NOT NULL,
    person_id TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    valid_from TEXT,
    valid_to TEXT,
    source_ids_json TEXT NOT NULL CHECK (json_valid(source_ids_json)),
    reason TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    PRIMARY KEY (memory_id, revision)
);
CREATE TABLE memory_sources (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    source_event_id TEXT NOT NULL REFERENCES events(event_id),
    PRIMARY KEY (memory_id, source_event_id)
);
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL REFERENCES turns(turn_id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    UNIQUE(turn_id, sequence)
);
CREATE TABLE mood_states (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    pleasure REAL NOT NULL CHECK (pleasure >= -1 AND pleasure <= 1),
    arousal REAL NOT NULL CHECK (arousal >= 0 AND arousal <= 1),
    dominance REAL NOT NULL CHECK (dominance >= -1 AND dominance <= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (identity_id, session_id)
);
CREATE TABLE outbox (
    event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    payload BLOB NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'sent', 'quarantined')),
    retry_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    sent_at TEXT
, last_error TEXT, updated_at TEXT);
CREATE TABLE planning_decisions (
    decision_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    selected_candidate_id TEXT NOT NULL,
    candidates_json TEXT NOT NULL CHECK (json_valid(candidates_json)),
    rejected_json TEXT NOT NULL CHECK (json_valid(rejected_json)),
    reasons_json TEXT NOT NULL CHECK (json_valid(reasons_json)),
    decided_at TEXT NOT NULL
);
INSERT INTO "planning_decisions" VALUES('5c31c3bb-0abb-4940-84ed-05d5593d5c74','16c10d93-d478-4f02-8069-c064673611b4','read:checklist.md','[{"candidate_id":"read:checklist.md","capability":"filesystem.read","arguments":{"path":"checklist.md"},"expected_result":"actual UTF-8 readback and source lines","cost":0,"deadline":"2026-10-15T18:12:37.051947+00:00","score":1,"reasons":["owner-approved exact document"],"allowed":true},{"candidate_id":"none","capability":"none","arguments":{},"expected_result":"keep pending","cost":0,"deadline":null,"score":0,"reasons":["foreground first"],"allowed":true}]','[]','["owner-approved exact document"]','2026-10-14T18:12:37.059694+00:00');
CREATE TABLE preferences (
    preference_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    person_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('siro', 'owner', 'shared')),
    subject TEXT NOT NULL,
    polarity REAL NOT NULL CHECK (polarity >= -1 AND polarity <= 1),
    strength REAL NOT NULL CHECK (strength >= 0 AND strength <= 1),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    context TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'committed', 'deleted')),
    source_ids_json TEXT NOT NULL CHECK (json_valid(source_ids_json)),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (identity_id, person_id, scope, subject, context)
);
CREATE TABLE procedural_candidates (
    candidate_id TEXT PRIMARY KEY,
    source_trace_ids_json TEXT NOT NULL CHECK (json_valid(source_trace_ids_json)),
    workflow_hash TEXT NOT NULL,
    capabilities_json TEXT NOT NULL CHECK (json_valid(capabilities_json)),
    fixture_json TEXT NOT NULL CHECK (json_valid(fixture_json)),
    status TEXT NOT NULL CHECK (status = 'candidate'),
    created_at TEXT NOT NULL
);
CREATE TABLE relationships (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    person_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    state_json TEXT NOT NULL CHECK (json_valid(state_json)),
    source_ids TEXT NOT NULL CHECK (json_valid(source_ids)),
    PRIMARY KEY (identity_id, person_id, revision)
);
CREATE TABLE run_journal (
    run_id TEXT PRIMARY KEY REFERENCES agent_runs(run_id),
    version INTEGER NOT NULL CHECK (version = 1),
    runtime_profile TEXT NOT NULL,
    backend TEXT NOT NULL,
    privacy TEXT NOT NULL,
    epoch TEXT NOT NULL,
    messages_json TEXT NOT NULL CHECK (json_valid(messages_json)),
    model_rounds INTEGER NOT NULL DEFAULT 0,
    max_model_rounds INTEGER NOT NULL,
    tool_calls INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE run_journal_calls (
    run_id TEXT NOT NULL REFERENCES run_journal(run_id),
    call_id TEXT NOT NULL,
    batch_index INTEGER NOT NULL,
    call_index INTEGER NOT NULL,
    capability TEXT NOT NULL,
    arguments_json TEXT NOT NULL CHECK (json_valid(arguments_json)),
    proposal_id TEXT,
    dispatched INTEGER NOT NULL DEFAULT 0,
    observation_json TEXT CHECK (observation_json IS NULL OR json_valid(observation_json)),
    PRIMARY KEY (run_id, call_id)
);
CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
INSERT INTO "schema_migrations" VALUES(1,'events','972363352f3cb1839fb5ff120dfdf1e3ad52bef59dd1ec823499b8c6b17b1582','2026-10-14T18:12:37.041376+00:00');
INSERT INTO "schema_migrations" VALUES(2,'domain','184f8f15e885dd575ae9a03bf22e973d374b801ba60fd23be99b57d48c24ecb4','2026-10-14T18:12:37.042942+00:00');
INSERT INTO "schema_migrations" VALUES(3,'conversation','00e7a8897efb83eeadadfbc158b507be949453f2deab6904917f0429284539bf','2026-10-14T18:12:37.043429+00:00');
INSERT INTO "schema_migrations" VALUES(4,'delivery','0a10ae7e09e136dc531bc3dd1b464f7a5729d51476b82d9112b2760fe0889989','2026-10-14T18:12:37.044165+00:00');
INSERT INTO "schema_migrations" VALUES(5,'memory_v2','f47703d2d4e83e6ae29f47b3bd46b685ec463ac84d6c9af2567a626ebc904c1e','2026-10-14T18:12:37.045264+00:00');
INSERT INTO "schema_migrations" VALUES(6,'consolidation','945dc07b64d433d524d5bf6e83b575342d29626f57096e70c55c1d3bc8bf9ee3','2026-10-14T18:12:37.046780+00:00');
INSERT INTO "schema_migrations" VALUES(7,'planning','4dd84131db23f3684e85ac1f981e76527ad61461e8ea29fa658bfde9a951211c','2026-10-14T18:12:37.046996+00:00');
INSERT INTO "schema_migrations" VALUES(8,'procedural_candidates','7c8d374aa271bdc04c3c35dcd26dc03e5f89404a9af80d98b8bd34d7158eded0','2026-10-14T18:12:37.047173+00:00');
INSERT INTO "schema_migrations" VALUES(9,'affect_preferences','1dcaf5dcb0bd9b50f5ce9491f6d92b6653c8f5799978ce9607770a40c9d2194f','2026-10-14T18:12:37.047567+00:00');
INSERT INTO "schema_migrations" VALUES(10,'emotion_dynamics','0c14509417ff69a90c0dad1bfb6292d9056a2214ea2202a23b0ede2f115c27e9','2026-10-14T18:12:37.048132+00:00');
INSERT INTO "schema_migrations" VALUES(11,'tool_proposals','14ad240b19630f058f3d5d2607de9e43952fe36df1461ee939713c6513c57e4c','2026-10-14T18:12:37.048404+00:00');
INSERT INTO "schema_migrations" VALUES(12,'agent_runs','35b3df0252df97239c0f48319190d95cd0e108810139f28e0774dd23e3f1c97f','2026-10-14T18:12:37.048650+00:00');
INSERT INTO "schema_migrations" VALUES(13,'run_journal','1336a458e0a6f3d09d7f1d8186a69b897bfdd2927a1bb032b47a75013646061a','2026-10-14T18:12:37.048963+00:00');
INSERT INTO "schema_migrations" VALUES(14,'goal_tasks','e1c1a72259d354bab9229a5cf4256935cc702d8cbdf5a153cf5683f594628e34','2026-10-14T18:12:37.049705+00:00');
CREATE TABLE semantic_facts (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_json TEXT NOT NULL CHECK (json_valid(object_json)),
    verification TEXT NOT NULL,
    PRIMARY KEY (memory_id, subject, predicate)
);
CREATE TABLE skills (
    skill_id TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    path_ref TEXT NOT NULL,
    PRIMARY KEY (skill_id, version)
);
CREATE TABLE tool_proposals (
    proposal_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    arguments_json TEXT NOT NULL CHECK (json_valid(arguments_json)),
    arguments_hash TEXT NOT NULL,
    risk TEXT NOT NULL,
    state TEXT NOT NULL,
    observation_json TEXT CHECK (observation_json IS NULL OR json_valid(observation_json)),
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, call_id)
);
CREATE TABLE trait_projections (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    trait TEXT NOT NULL,
    value REAL NOT NULL CHECK (value >= -1 AND value <= 1),
    weekly_delta REAL NOT NULL CHECK (weekly_delta >= -0.05 AND weekly_delta <= 0.05),
    week_start TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    source_ids_json TEXT NOT NULL CHECK (json_valid(source_ids_json)),
    PRIMARY KEY (identity_id, trait)
);
CREATE TABLE turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES conversations(session_id),
    generation_id TEXT NOT NULL,
    state TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    ended_at TEXT
);
CREATE TABLE world_current (
    entity_id TEXT NOT NULL,
    property TEXT NOT NULL,
    observation_id TEXT NOT NULL REFERENCES world_observations(observation_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    PRIMARY KEY (entity_id, property)
);
CREATE TABLE world_observations (
    observation_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    property TEXT NOT NULL,
    value_json TEXT NOT NULL CHECK (json_valid(value_json)),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    observed_at TEXT NOT NULL,
    expires_at TEXT,
    source_id TEXT NOT NULL
);
CREATE INDEX events_type_time_idx ON events(type, received_at);
CREATE INDEX events_trace_idx ON events(trace_id);
CREATE INDEX outbox_pending_idx ON outbox(state, retry_at);
CREATE INDEX world_observations_lookup_idx
    ON world_observations(entity_id, property, observed_at);
CREATE INDEX messages_turn_idx ON messages(turn_id, sequence);
CREATE INDEX outbox_state_attempts_idx ON outbox(state, attempts);
CREATE INDEX memories_scope_lookup_idx
    ON memories(identity_id, person_id, status, kind, valid_from);
CREATE UNIQUE INDEX consolidation_runs_key_idx ON consolidation_runs(run_key);
CREATE INDEX planning_decisions_trace_idx ON planning_decisions(trace_id, decided_at);
CREATE UNIQUE INDEX procedural_candidates_workflow_idx
ON procedural_candidates(workflow_hash);
CREATE INDEX emotion_episodes_session_idx
ON emotion_episodes(identity_id, session_id, occurred_at);
CREATE INDEX appraisal_records_session_idx
ON appraisal_records(identity_id, session_id, occurred_at);
CREATE INDEX idx_tool_proposals_session_state
ON tool_proposals(session_id, state, updated_at);
CREATE INDEX idx_agent_runs_session_updated
ON agent_runs(session_id, updated_at DESC);
CREATE INDEX idx_run_journal_calls_proposal ON run_journal_calls(proposal_id);
PRAGMA writable_schema=OFF;
DELETE FROM "sqlite_sequence";
COMMIT;
