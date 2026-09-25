CREATE TABLE planning_decisions (
    decision_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    selected_candidate_id TEXT NOT NULL,
    candidates_json TEXT NOT NULL CHECK (json_valid(candidates_json)),
    rejected_json TEXT NOT NULL CHECK (json_valid(rejected_json)),
    reasons_json TEXT NOT NULL CHECK (json_valid(reasons_json)),
    decided_at TEXT NOT NULL
);

CREATE INDEX planning_decisions_trace_idx ON planning_decisions(trace_id, decided_at)
