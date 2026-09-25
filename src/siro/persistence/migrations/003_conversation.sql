CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL REFERENCES turns(turn_id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    UNIQUE(turn_id, sequence)
);

CREATE INDEX messages_turn_idx ON messages(turn_id, sequence);
