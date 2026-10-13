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

CREATE INDEX idx_agent_runs_session_updated
ON agent_runs(session_id, updated_at DESC);

CREATE TABLE agent_steps (
    run_id TEXT NOT NULL REFERENCES agent_runs(run_id),
    step_index INTEGER NOT NULL,
    kind TEXT NOT NULL,
    capability TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, step_index)
);
