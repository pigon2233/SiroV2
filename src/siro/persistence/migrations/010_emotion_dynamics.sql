CREATE TABLE appraisal_records (
    appraisal_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    appraisal_json TEXT NOT NULL CHECK (json_valid(appraisal_json)),
    occurred_at TEXT NOT NULL
);

CREATE TABLE emotion_activations (
    appraisal_id TEXT NOT NULL REFERENCES appraisal_records(appraisal_id),
    emotion TEXT NOT NULL,
    intensity REAL NOT NULL CHECK (intensity >= 0 AND intensity <= 1),
    reason TEXT NOT NULL,
    PRIMARY KEY (appraisal_id, emotion)
);

CREATE TABLE mood_states (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    pleasure REAL NOT NULL CHECK (pleasure >= -1 AND pleasure <= 1),
    arousal REAL NOT NULL CHECK (arousal >= 0 AND arousal <= 1),
    dominance REAL NOT NULL CHECK (dominance >= -1 AND dominance <= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (identity_id, session_id)
);

CREATE TABLE drive_states (
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    session_id TEXT NOT NULL,
    safety REAL NOT NULL CHECK (safety >= 0 AND safety <= 1),
    connection REAL NOT NULL CHECK (connection >= 0 AND connection <= 1),
    competence REAL NOT NULL CHECK (competence >= 0 AND competence <= 1),
    curiosity REAL NOT NULL CHECK (curiosity >= 0 AND curiosity <= 1),
    autonomy REAL NOT NULL CHECK (autonomy >= 0 AND autonomy <= 1),
    rest REAL NOT NULL CHECK (rest >= 0 AND rest <= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (identity_id, session_id)
);

CREATE TABLE coping_decisions (
    appraisal_id TEXT PRIMARY KEY REFERENCES appraisal_records(appraisal_id),
    strategy TEXT NOT NULL,
    urgency REAL NOT NULL CHECK (urgency >= 0 AND urgency <= 1),
    reason TEXT NOT NULL
);

CREATE INDEX appraisal_records_session_idx
ON appraisal_records(identity_id, session_id, occurred_at);
