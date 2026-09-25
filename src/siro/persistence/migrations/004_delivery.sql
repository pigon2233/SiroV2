ALTER TABLE outbox ADD COLUMN last_error TEXT;

ALTER TABLE outbox ADD COLUMN updated_at TEXT;

CREATE INDEX outbox_state_attempts_idx ON outbox(state, attempts);
