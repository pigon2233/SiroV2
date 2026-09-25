ALTER TABLE consolidation_runs ADD COLUMN identity_id TEXT REFERENCES identities(identity_id);
ALTER TABLE consolidation_runs ADD COLUMN run_key TEXT;
ALTER TABLE consolidation_runs ADD COLUMN created_at TEXT;
ALTER TABLE consolidation_runs ADD COLUMN updated_at TEXT;

CREATE UNIQUE INDEX consolidation_runs_key_idx ON consolidation_runs(run_key);

CREATE TABLE consolidation_outputs (
    candidate_key TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES consolidation_runs(run_id),
    memory_id TEXT NOT NULL UNIQUE REFERENCES memories(memory_id),
    created_at TEXT NOT NULL
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
