CREATE TABLE memory_candidate_reviews (
    memory_id TEXT PRIMARY KEY REFERENCES memories(memory_id),
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    person_id TEXT NOT NULL CHECK (person_id = 'owner'),
    session_id TEXT NOT NULL REFERENCES conversations(session_id),
    source_event_id TEXT NOT NULL REFERENCES events(event_id),
    source_hash TEXT NOT NULL CHECK (length(source_hash) = 64),
    source_policy_revision INTEGER NOT NULL CHECK (source_policy_revision > 0),
    source_policy_hash TEXT NOT NULL CHECK (length(source_policy_hash) = 64),
    generator_version TEXT NOT NULL,
    candidate_kind TEXT NOT NULL CHECK (candidate_kind IN ('preference','episode','todo')),
    captured_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending','approved','rejected','withdrawn')),
    memory_revision INTEGER NOT NULL CHECK (memory_revision > 0),
    replaces_id TEXT REFERENCES memories(memory_id)
);
CREATE INDEX memory_candidate_review_scope_idx
    ON memory_candidate_reviews(identity_id,person_id,session_id,state,captured_at);

CREATE TABLE memory_candidate_actions (
    action_id TEXT PRIMARY KEY,
    command_hash TEXT NOT NULL CHECK (length(command_hash) = 64),
    memory_id TEXT NOT NULL REFERENCES memory_candidate_reviews(memory_id),
    identity_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('stage','approve','reject','withdraw','replace')),
    memory_revision INTEGER NOT NULL CHECK (memory_revision > 0),
    state_at_commit TEXT NOT NULL,
    policy_revision INTEGER NOT NULL CHECK (policy_revision > 0),
    policy_hash TEXT NOT NULL CHECK (length(policy_hash) = 64),
    committed_at TEXT NOT NULL
);
