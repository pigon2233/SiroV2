CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    envelope_json TEXT NOT NULL CHECK (json_valid(envelope_json)),
    received_at TEXT NOT NULL,
    trace_id TEXT NOT NULL
);

CREATE INDEX events_type_time_idx ON events(type, received_at);
CREATE INDEX events_trace_idx ON events(trace_id);

CREATE TABLE outbox (
    event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    payload BLOB NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'sent', 'quarantined')),
    retry_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    sent_at TEXT
);

CREATE INDEX outbox_pending_idx ON outbox(state, retry_at);

CREATE TABLE inbox (
    consumer_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (consumer_id, event_id)
);
