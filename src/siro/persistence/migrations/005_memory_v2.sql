ALTER TABLE memories ADD COLUMN person_id TEXT NOT NULL DEFAULT 'owner';
ALTER TABLE memories ADD COLUMN supersedes_memory_id TEXT REFERENCES memories(memory_id);

CREATE INDEX memories_scope_lookup_idx
    ON memories(identity_id, person_id, status, kind, valid_from);

CREATE TABLE memory_revisions (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    kind TEXT NOT NULL,
    person_id TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    valid_from TEXT,
    valid_to TEXT,
    source_ids_json TEXT NOT NULL CHECK (json_valid(source_ids_json)),
    reason TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    PRIMARY KEY (memory_id, revision)
);

INSERT INTO memory_revisions(
    memory_id, revision, kind, person_id, text, status, confidence,
    valid_from, valid_to, source_ids_json, reason, changed_at
)
SELECT
    m.memory_id, m.revision, m.kind, m.person_id, m.text, m.status, m.confidence,
    m.valid_from, m.valid_to,
    COALESCE(
        (SELECT json_group_array(ms.source_event_id)
         FROM memory_sources ms WHERE ms.memory_id = m.memory_id),
        json('[]')
    ),
    'migration', COALESCE(m.valid_from, CURRENT_TIMESTAMP)
FROM memories m;

CREATE VIRTUAL TABLE memory_fts USING fts5(
    memory_id UNINDEXED,
    identity_id UNINDEXED,
    person_id UNINDEXED,
    text,
    tokenize = 'unicode61'
);

INSERT INTO memory_fts(memory_id, identity_id, person_id, text)
SELECT memory_id, identity_id, person_id, text
FROM memories
WHERE status = 'committed' AND deleted_at IS NULL;
