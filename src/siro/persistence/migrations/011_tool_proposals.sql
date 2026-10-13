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

CREATE INDEX idx_tool_proposals_session_state
ON tool_proposals(session_id, state, updated_at);
