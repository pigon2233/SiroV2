CREATE TABLE procedural_candidates (
    candidate_id TEXT PRIMARY KEY,
    source_trace_ids_json TEXT NOT NULL CHECK (json_valid(source_trace_ids_json)),
    workflow_hash TEXT NOT NULL,
    capabilities_json TEXT NOT NULL CHECK (json_valid(capabilities_json)),
    fixture_json TEXT NOT NULL CHECK (json_valid(fixture_json)),
    status TEXT NOT NULL CHECK (status = 'candidate'),
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX procedural_candidates_workflow_idx
ON procedural_candidates(workflow_hash);
