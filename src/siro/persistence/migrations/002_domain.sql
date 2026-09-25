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

CREATE TABLE relationships (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    person_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    state_json TEXT NOT NULL CHECK (json_valid(state_json)),
    source_ids TEXT NOT NULL CHECK (json_valid(source_ids)),
    PRIMARY KEY (identity_id, person_id, revision)
);

CREATE TABLE conversations (
    session_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES conversations(session_id),
    generation_id TEXT NOT NULL,
    state TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    ended_at TEXT
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

CREATE INDEX world_observations_lookup_idx
    ON world_observations(entity_id, property, observed_at);

CREATE TABLE world_current (
    entity_id TEXT NOT NULL,
    property TEXT NOT NULL,
    observation_id TEXT NOT NULL REFERENCES world_observations(observation_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    PRIMARY KEY (entity_id, property)
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
);

CREATE TABLE memory_sources (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    source_event_id TEXT NOT NULL REFERENCES events(event_id),
    PRIMARY KEY (memory_id, source_event_id)
);

CREATE TABLE memory_derivations (
    parent_memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    child_memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    CHECK (parent_memory_id <> child_memory_id),
    PRIMARY KEY (parent_memory_id, child_memory_id, revision)
);

CREATE TABLE semantic_facts (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_json TEXT NOT NULL CHECK (json_valid(object_json)),
    verification TEXT NOT NULL,
    PRIMARY KEY (memory_id, subject, predicate)
);

CREATE TABLE consolidation_runs (
    run_id TEXT PRIMARY KEY,
    source_cursor_start TEXT,
    source_cursor_end TEXT,
    status TEXT NOT NULL,
    checkpoint TEXT,
    model_ref TEXT
);

CREATE TABLE goals (
    goal_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    next_step TEXT,
    deadline TEXT,
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    revision INTEGER NOT NULL CHECK (revision >= 1)
);

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

CREATE TABLE actions (
    action_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    args_hash TEXT NOT NULL,
    grant_id TEXT REFERENCES grants(grant_id),
    deadline TEXT
);

CREATE TABLE action_attempts (
    attempt_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    executor_id TEXT NOT NULL,
    lease_epoch INTEGER NOT NULL CHECK (lease_epoch >= 0),
    state TEXT NOT NULL,
    outcome_json TEXT CHECK (outcome_json IS NULL OR json_valid(outcome_json))
);

CREATE TABLE audit (
    audit_id TEXT PRIMARY KEY,
    action_id TEXT REFERENCES actions(action_id),
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE skills (
    skill_id TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    path_ref TEXT NOT NULL,
    PRIMARY KEY (skill_id, version)
);

CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    adapter_id TEXT NOT NULL,
    descriptor_json TEXT NOT NULL CHECK (json_valid(descriptor_json)),
    availability TEXT NOT NULL,
    last_seen TEXT
);

CREATE TABLE entity_edges (
    from_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    to_id TEXT NOT NULL,
    UNIQUE (from_id, relation, to_id)
);

CREATE TABLE compute_nodes (
    node_id TEXT PRIMARY KEY,
    capabilities_json TEXT NOT NULL CHECK (json_valid(capabilities_json)),
    version TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    trust_scope TEXT NOT NULL
);

CREATE TABLE compute_jobs (
    job_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    privacy TEXT NOT NULL,
    deadline TEXT,
    input_ref TEXT,
    selected_node TEXT REFERENCES compute_nodes(node_id)
);

CREATE TABLE compute_attempts (
    attempt_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES compute_jobs(job_id),
    lease_epoch INTEGER NOT NULL CHECK (lease_epoch >= 0),
    state TEXT NOT NULL,
    output_ref TEXT
);
