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
CREATE INDEX idx_run_journal_calls_proposal ON run_journal_calls(proposal_id);
