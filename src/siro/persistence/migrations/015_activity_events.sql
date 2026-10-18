CREATE TABLE activity_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    entity TEXT NOT NULL CHECK (entity IN ('run', 'tool')),
    entity_id TEXT NOT NULL,
    state TEXT NOT NULL,
    phase TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX idx_activity_events_entity ON activity_events(entity, entity_id, seq);
