CREATE TABLE run_checkpoints (
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    plan_id TEXT,
    capability TEXT NOT NULL,
    arguments_json TEXT NOT NULL CHECK (json_valid(arguments_json)),
    effect TEXT NOT NULL CHECK (effect IN ('read', 'write', 'unknown_class')),
    phase TEXT NOT NULL CHECK (phase IN ('planned', 'dispatched', 'acked', 'saved')),
    idempotency_key TEXT NOT NULL,
    outcome TEXT CHECK (outcome IS NULL OR outcome IN ('success', 'failed', 'unknown')),
    resolved_by TEXT CHECK (resolved_by IS NULL OR resolved_by IN ('readback', 'owner')),
    observation_json TEXT CHECK (observation_json IS NULL OR json_valid(observation_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, step_id)
);
CREATE UNIQUE INDEX idx_run_checkpoints_seq ON run_checkpoints(run_id, seq);
