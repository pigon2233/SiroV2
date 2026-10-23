CREATE TABLE memory_vectors (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
    profile_key TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision > 0),
    source_hash TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK(dimensions BETWEEN 32 AND 1024),
    vector BLOB NOT NULL,
    PRIMARY KEY(memory_id, profile_key)
);
