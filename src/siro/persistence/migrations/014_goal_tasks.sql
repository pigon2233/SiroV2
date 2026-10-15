ALTER TABLE goals ADD COLUMN task_json TEXT
CHECK (task_json IS NULL OR json_valid(task_json));
