CREATE TABLE affect_states (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    valence REAL NOT NULL CHECK (valence >= -1 AND valence <= 1),
    arousal REAL NOT NULL CHECK (arousal >= 0 AND arousal <= 1),
    intensity REAL NOT NULL CHECK (intensity >= 0 AND intensity <= 1),
    reason TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (identity_id, session_id)
);

CREATE TABLE emotion_episodes (
    episode_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    valence REAL NOT NULL CHECK (valence >= -1 AND valence <= 1),
    arousal REAL NOT NULL CHECK (arousal >= 0 AND arousal <= 1),
    intensity REAL NOT NULL CHECK (intensity >= 0 AND intensity <= 1),
    reason TEXT NOT NULL,
    source_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX emotion_episodes_session_idx
ON emotion_episodes(identity_id, session_id, occurred_at);

CREATE TABLE preferences (
    preference_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    person_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('siro', 'owner', 'shared')),
    subject TEXT NOT NULL,
    polarity REAL NOT NULL CHECK (polarity >= -1 AND polarity <= 1),
    strength REAL NOT NULL CHECK (strength >= 0 AND strength <= 1),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    context TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'committed', 'deleted')),
    source_ids_json TEXT NOT NULL CHECK (json_valid(source_ids_json)),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (identity_id, person_id, scope, subject, context)
);
