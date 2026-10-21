ALTER TABLE memory_derivations ADD COLUMN source_hash TEXT;

CREATE TABLE memory_derivation_metadata (
    child_memory_id TEXT PRIMARY KEY REFERENCES memories(memory_id),
    generator_version TEXT NOT NULL,
    policy_revision INTEGER NOT NULL CHECK (policy_revision >= 1),
    route_privacy TEXT NOT NULL CHECK (route_privacy IN ('local_only','trusted_lan','cloud_allowed')),
    captured_at TEXT NOT NULL
);

CREATE TABLE memory_source_revocations (
    source_event_id TEXT PRIMARY KEY REFERENCES events(event_id),
    revoked_at TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE INDEX memory_derivations_child_idx ON memory_derivations(child_memory_id);
CREATE INDEX memory_sources_event_idx ON memory_sources(source_event_id);
